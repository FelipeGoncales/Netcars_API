from flask import Flask, request, jsonify
from main import app, con
import random
from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import re
from flask_bcrypt import generate_password_hash, check_password_hash


def validar_senha(senha):
    if len(senha) < 8:
        return "A senha deve ter pelo menos 8 caracteres."

    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", senha):
        return "A senha deve conter pelo menos um símbolo especial (!@#$%^&*...)."

    if not re.search(r"[A-Z]", senha):
        return "A senha deve conter pelo menos uma letra maiúscula."

    return True

# Função para enviar o e-mail
def enviar_email(email_destinatario, codigo):
    # Configuração do servidor SMTP (Exemplo para Gmail)
    remetente = 'netcars.contato@gmail.com'
    senha = 'dglpexljossptnxx'
    servidor_smtp = 'smtp.gmail.com'
    porta_smtp = 587

    # Criando a mensagem do e-mail
    assunto = 'NetCars - Código de Verificação'
    corpo = f'O seu código de verificação é: {codigo}'

    # Configurando o cabeçalho do e-mail
    msg = MIMEMultipart()
    msg['From'] = remetente
    msg['To'] = email_destinatario
    msg['Subject'] = assunto
    msg.attach(MIMEText(corpo, 'plain'))

    try:
        # Enviando o e-mail
        server = smtplib.SMTP(servidor_smtp, porta_smtp)
        server.starttls()  # Criptografia
        server.login(remetente, senha)  # Autenticação
        text = msg.as_string()
        server.sendmail(remetente, email_destinatario, text)
        server.quit()
        return True
    except Exception as e:
        return False

@app.route('/gerar_codigo', methods=['POST'])
def gerar_codigo():
    data = request.get_json()

    email = data.get('email')

    if not email:
        return jsonify({'error': 'Usuário não encontrado.'}), 400

    cursor = con.cursor()

    cursor.execute("SELECT id_usuario FROM USUARIO WHERE email =?", (email,))

    user = cursor.fetchone()
    if user is None:
        return jsonify({'error': 'Email não cadastrado.'}), 404

    user_id = user[0]

    codigo = ''.join(random.choices('0123456789', k=6))
    codigo_criado_em = datetime.now()

    # Enviar o código por e-mail
    email_enviado = enviar_email(email, codigo)

    if email_enviado == False:
        return jsonify({'error': 'Falha ao enviar o código para o e-mail.'}), 500

    cursor.execute("UPDATE USUARIO SET codigo =?, codigo_criado_em =? WHERE id_usuario =?", (codigo, codigo_criado_em, user_id))

    con.commit()
    cursor.close()

    return jsonify({'success': 'Código enviado para o e-mail.'}), 200

@app.route('/validar_codigo', methods=['POST'])
def validar_codigo():
    data = request.get_json()

    email = data.get('email')
    codigo = str(data.get('codigo'))

    if not email or not codigo:
        return jsonify({'error': 'Dados incompletos.'}), 400

    cursor = con.cursor()

    cursor.execute("SELECT id_usuario, codigo_criado_em, codigo FROM USUARIO WHERE email = ?", (email,))

    user = cursor.fetchone()
    if user is None:
        return jsonify({'error': 'Email não cadastrado.'}), 404

    user_id = user[0]
    codigo_criado_em = user[1]
    codigo_valido = str(user[2])

    horario_atual = datetime.now()

    if horario_atual - codigo_criado_em > timedelta(minutes=10):
        return jsonify({'error': 'Código expirado.'}), 401

    if codigo != codigo_valido:
        return jsonify({'error': 'Código incorreto. Verifique novamente seu email.'}), 401

    cursor.execute("UPDATE USUARIO SET codigo = NULL, codigo_criado_em = NULL, TROCAR_SENHA = TRUE WHERE id_usuario = ?", (user_id,))

    con.commit()
    cursor.close()

    return jsonify({'success': 'Código válido.'}), 200

@app.route('/redefinir_senha', methods=['POST'])
def redefinir_senha():
    data = request.get_json()

    senha_nova = data.get('senha_nova')
    repetir_senha_nova = data.get('repetir_senha_nova')
    email = data.get('email')

    if not senha_nova or not repetir_senha_nova or not email:
        return jsonify({'error': 'Dados incompletos.'}), 400

    if senha_nova != repetir_senha_nova:
        return jsonify({'error': 'As senhas são diferentes.'}), 400

    verificar_validar_senha = validar_senha(senha_nova)

    if verificar_validar_senha != True:
        return jsonify({'error': verificar_validar_senha}), 400

    cursor = con.cursor()

    cursor.execute('SELECT TROCAR_SENHA FROM USUARIO WHERE EMAIL = ?', (email,))

    user = cursor.fetchone()

    if user is None:
        return jsonify({'error': 'Email não cadastrado.'}), 404

    trocar_senha = user[0]

    if trocar_senha is False:
        return jsonify({'error': 'Não foi possível redefinir a senha.'}), 401

    cursor.execute('SELECT SENHA_HASH FROM USUARIO WHERE EMAIL = ?', (email,))
    senha_antiga = cursor.fetchone()[0]

    if check_password_hash(senha_antiga, senha_nova):
        return jsonify({'error': 'A senha nova não pode ser igual à anterior.'}), 400

    senha_hash = generate_password_hash(senha_nova)

    cursor.execute("UPDATE USUARIO SET SENHA_HASH = ?, TROCAR_SENHA = FALSE WHERE EMAIL = ?", (senha_hash, email))

    con.commit()
    cursor.close()

    return jsonify({'success': 'Senha redefinida com sucesso.'}), 200