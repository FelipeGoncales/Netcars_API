import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from threading import Thread
import jwt
from flask import Flask, request, jsonify, render_template, current_app
from main import app, con, senha_app_email, upload_folder, senha_secreta
import random, re
from flask_bcrypt import generate_password_hash, check_password_hash
import os

# -----------------------------
# Funções Auxiliares (Banco e Senha)
# -----------------------------
def validar_senha(senha):
    if len(senha) < 8:
        return "A senha deve ter pelo menos 8 caracteres."
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", senha):
        return "A senha deve conter pelo menos um símbolo especial (!@#$%^&*...)."
    if not re.search(r"[A-Z]", senha):
        return "A senha deve conter pelo menos uma letra maiúscula."
    return True

# -----------------------------
# Envio de E-mail de Recuperação de Senha (Assíncrono)
# -----------------------------

def enviar_email_recuperar_senha(email_destinatario, codigo):

    app_context = current_app._get_current_object()

    def task_envio():
        remetente = 'netcars.contato@gmail.com'
        senha = senha_app_email
        servidor_smtp = 'smtp.gmail.com'
        porta_smtp = 465  # Conexão SSL direta
        assunto = 'NetCars - Código de Verificação'

        # Renderiza o template com as variáveis desejadas dentro do contexto da aplicação
        with app_context.app_context():
            corpo = render_template('email_esqueci_senha.html.html', codigo=codigo, ano=datetime.now().year)

        # Cria e configura a mensagem do e-mail
        msg = MIMEMultipart()
        msg['From'] = remetente
        msg['To'] = email_destinatario
        msg['Subject'] = assunto
        msg.attach(MIMEText(corpo, 'html'))

        try:
            # Usando SSL direto (mais confiável com Gmail)
            server = smtplib.SMTP_SSL(servidor_smtp, porta_smtp, timeout=60)
            server.set_debuglevel(1)  # Ative para debugging
            server.ehlo()  # Identifica-se ao servidor
            server.login(remetente, senha)
            text = msg.as_string()
            server.sendmail(remetente, email_destinatario, text)
            server.quit()
            print(f"E-mail de recuperação enviado para {email_destinatario}")
        except Exception as e:
            print(f"Erro ao enviar e-mail de recuperação: {e}")

    Thread(target=task_envio, daemon=True).start()

# -----------------------------
# Rotas senha
# -----------------------------

@app.route('/gerar_codigo', methods=['POST'])
def gerar_codigo():
    data = request.get_json()
    email = data.get('email')
    if not email:
        return jsonify({'error': 'Usuário não encontrado.'}), 400

    cursor = con.cursor()
    cursor.execute("SELECT id_usuario FROM USUARIO WHERE email = ?", (email,))
    user = cursor.fetchone()
    if user is None:
        return jsonify({'error': 'Email não cadastrado.'}), 404
    user_id = user[0]

    codigo = ''.join(random.choices('0123456789', k=6))
    codigo_criado_em = datetime.now()

    # Envia o e-mail de recuperação de senha de forma assíncrona
    enviar_email_recuperar_senha(email, codigo)

    cursor.execute("UPDATE USUARIO SET codigo = ?, codigo_criado_em = ? WHERE id_usuario = ?", (codigo, codigo_criado_em, user_id))
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

    cursor.execute('UPDATE USUARIO SET codigo = NULL, codigo_criado_em = NULL, trocar_senha = true WHERE id_usuario = ?', (user_id,))
    con.commit()
    cursor.close()

    return jsonify({'success': 'Código válido.'}), 200

@app.route('/redefinir_senha', methods=['POST'])
def redefinir_senha():
    data = request.get_json()
    senha_nova = data.get('senha_nova')
    repetir_senha_nova = data.get('repetir_senha_nova')
    email = data.get('email')

    if not senha_nova:
        return jsonify({'error': 'Senha nova não pode estar vazia.'}), 400

    if not repetir_senha_nova:
        return jsonify({'error': 'Repetir a senha nova não pode estar vazia.'}), 400

    if not email:
        return jsonify({'error': 'Email não pode estar vazio.'}), 400

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

    if trocar_senha is not True:
        return jsonify({'error': 'Não foi possível redefinir a senha.'}), 401

    cursor.execute('SELECT SENHA_HASH FROM USUARIO WHERE EMAIL = ?', (email,))
    senha_antiga = cursor.fetchone()[0]

    if check_password_hash(senha_antiga, senha_nova):
        return jsonify({'error': 'A senha nova não pode ser igual à anterior.'}), 400

    senha_hash = generate_password_hash(senha_nova)
    cursor.execute('UPDATE USUARIO SET SENHA_HASH = ?, TROCAR_SENHA = NULL WHERE EMAIL = ?', (senha_hash, email))

    con.commit()
    cursor.close()

    return jsonify({'success': 'Senha redefinida com sucesso.'}), 200

# -----------------------------
# Envio de E-mail de Verificação (Assíncrono)
# -----------------------------
def enviar_email_verificacao(email_destinatario, codigo):
    app_context = current_app._get_current_object()

    def task_envio():
        remetente = 'netcars.contato@gmail.com'
        senha = senha_app_email
        servidor_smtp = 'smtp.gmail.com'
        porta_smtp = 465  # Conexão SSL direta
        assunto = 'NetCars - Verificação de Email'

        # Renderiza o template com as variáveis desejadas dentro do contexto da aplicação
        with app_context.app_context():
            corpo = render_template('email_confirmar_email.html', codigo=codigo, ano=datetime.now().year)

        # Cria e configura a mensagem do e-mail
        msg = MIMEMultipart()
        msg['From'] = remetente
        msg['To'] = email_destinatario
        msg['Subject'] = assunto
        msg.attach(MIMEText(corpo, 'html'))

        try:
            # Usando SSL direto (mais confiável com Gmail)
            server = smtplib.SMTP_SSL(servidor_smtp, porta_smtp, timeout=60)
            server.set_debuglevel(1)  # Ative para debugging
            server.ehlo()  # Identifica-se ao servidor
            server.login(remetente, senha)
            text = msg.as_string()
            server.sendmail(remetente, email_destinatario, text)
            server.quit()
            print(f"E-mail de verificação enviado para {email_destinatario}")
        except Exception as e:
            print(f"Erro ao enviar e-mail de verificação: {e}")

    Thread(target=task_envio, daemon=True).start()