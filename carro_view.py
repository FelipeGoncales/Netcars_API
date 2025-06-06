from flask import Flask, jsonify, request, send_from_directory, url_for, current_app, render_template
from main import app, con, upload_folder, senha_secreta, senha_app_email
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from threading import Thread
import smtplib
import pytz
import os
import jwt
import shutil

def remover_bearer(token):
    if token.startswith('Bearer '):
        return token[len('Bearer '):]
    else:
        return token

def buscar_dados_carro_por_id(id_carro):
    cursor = con.cursor()
    query = '''
        SELECT id_carro, marca, modelo, ano_modelo, ano_fabricacao, versao, cor, renavam,
               cambio, combustivel, categoria, quilometragem, estado, cidade, preco_compra,
               preco_venda, licenciado, placa, criado_em, ativo, id_usuario_reserva
        FROM CARROS
        WHERE id_carro = ?
    '''
    cursor.execute(query, (id_carro,))
    resultado = cursor.fetchone()

    if resultado[20]:
        cursor.execute('SELECT NOME_COMPLETO FROM USUARIO WHERE ID_USUARIO = ?', (resultado[20],))
        nome_usuario = cursor.fetchone()[0]
    else:
        nome_usuario = None

    cursor.close()

    # Define o caminho para a pasta de imagens do carro (ex: uploads/Carros/<id_carro>)
    images_dir = os.path.join(app.root_path, upload_folder, 'Carros', str(id_carro))
    imagens = []

    # Verifica se o diretório existe
    if os.path.exists(images_dir):
        for file in os.listdir(images_dir):
            if file.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
                imagem_url = url_for('get_car_image', id_carro=id_carro, filename=file, _external=True)
                imagens.append(imagem_url)

    if resultado and imagens:
        return {
            'id': resultado[0],
            'marca': resultado[1],
            'modelo': resultado[2],
            'ano_modelo': resultado[3],
            'ano_fabricacao': resultado[4],
            'versao': resultado[5],
            'cor': resultado[6],
            'renavam': resultado[7],
            'cambio': resultado[8],
            'combustivel': resultado[9],
            'categoria': resultado[10],
            'quilometragem': resultado[11],
            'estado': resultado[12],
            'cidade': resultado[13],
            'preco_compra': resultado[14],
            'preco_venda': resultado[15],
            'licenciado': resultado[16],
            'placa': resultado[17],
            'criado_em': resultado[18],
            'ativo': resultado[19],
            'nome_cliente': nome_usuario,
            'imagens': imagens
        }
    return None

def enviar_email_cancelamento(email_destinatario, tipo_veiculo, dados_veiculo):
    app_context = current_app._get_current_object()

    def task_envio():
        try:
            remetente = 'netcars.contato@gmail.com'
            senha = senha_app_email
            servidor_smtp = 'smtp.gmail.com'
            porta_smtp = 465

            # Data do cancelamento
            data_envio = datetime.now()
            data_cancelamento_str = data_envio.strftime("%d/%m/%Y")

            endereco_concessionaria = "Av. Exemplo, 1234 - Centro, Cidade Fictícia"

            assunto = "NetCars - Cancelamento de Reserva"

            # Renderiza o corpo do e-mail utilizando um template específico
            with app_context.app_context():
                corpo_email = render_template(
                    'email_cancelar_reserva.html',
                    email_destinatario=email_destinatario,
                    tipo_veiculo=tipo_veiculo,
                    dados_veiculo=dados_veiculo,
                    data_cancelamento_str=data_cancelamento_str,
                    endereco_concessionaria=endereco_concessionaria,
                    ano=datetime.now().year
                )

            # Configura o cabeçalho do e-mail
            msg = MIMEMultipart()
            msg['From'] = remetente
            msg['To'] = email_destinatario
            msg['Subject'] = assunto
            msg.attach(MIMEText(corpo_email, 'html'))

            try:
                # Usando conexão SSL para envio do e-mail
                server = smtplib.SMTP_SSL(servidor_smtp, porta_smtp, timeout=60)
                server.set_debuglevel(1)  # Ativa logs de debugging se necessário
                server.ehlo()  # Realiza a identificação junto ao servidor
                server.login(remetente, senha)
                text = msg.as_string()
                server.sendmail(remetente, email_destinatario, text)
                server.quit()
                print(f"E-mail de cancelamento enviado para {email_destinatario}")
            except Exception as e:
                print(f"Erro ao enviar e-mail de cancelamento: {e}")

        except Exception as e:
            print(f"Erro na tarefa de envio do e-mail: {e}")

    Thread(target=task_envio, daemon=True).start()

# Rota para servir as imagens de carros
@app.route('/uploads/carros/<int:id_carro>/<filename>')
def get_car_image(id_carro, filename):
    return send_from_directory(os.path.join(app.root_path, 'upload', 'Carros', str(id_carro)), filename)

# Cancelar reserva

@app.route('/cancelar-reserva-carro/<int:id>', methods=['DELETE'])
def cancelar_reserva_carro(id):
    token = request.headers.get('Authorization')
    if not token:
        return jsonify({'error': 'Token de autenticação necessário'}), 401

    token = remover_bearer(token)
    try:
        payload = jwt.decode(token, senha_secreta, algorithms=['HS256'])
        id_usuario = payload['id_usuario']
    except jwt.ExpiredSignatureError:
        return jsonify({'error': 'Token expirado'}), 401
    except jwt.InvalidTokenError:
        return jsonify({'error': 'Token inválido'}), 401

    cursor = con.cursor()

    # Buscar tipo de usuário
    cursor.execute('SELECT TIPO_USUARIO, EMAIL FROM USUARIO WHERE ID_USUARIO = ?', (id_usuario,))
    row_user = cursor.fetchone()
    tipo_user = row_user[0]
    email_user = row_user[1]

    try:
        if tipo_user in [1, 2]:
            cursor.execute('''
                UPDATE CARROS SET RESERVADO = NULL, RESERVADO_EM = NULL, ID_USUARIO_RESERVA = NULL WHERE ID_CARRO =?
                ''', (id,))
        else:
            cursor.execute('''
                SELECT 1 FROM CARROS WHERE RESERVADO IS TRUE AND ID_CARRO =? AND ID_USUARIO_RESERVA = ?
                ''', (id, id_usuario))
            check = cursor.fetchone()
            if check:
                cursor.execute('''
                   UPDATE CARROS SET RESERVADO = NULL, RESERVADO_EM = NULL, ID_USUARIO_RESERVA = NULL WHERE ID_CARRO =?
                   ''', (id,))
            else:
                con.commit()
                cursor.close()
                return jsonify({
                    'error': 'Apenas o dono da reserva pode cancelá-la.'
                }), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 400
    finally:
        # Buscar os dados do carro (para o e-mail)
        dados_carro = buscar_dados_carro_por_id(id)

        # Enviar o e-mail de cancelamento
        enviar_email_cancelamento(email_user, 'carro', dados_carro)

        con.commit()
        cursor.close()

        return jsonify({
            'success': 'Reserva cancelada com sucesso!'
        }), 200


# Buscar carro

@app.route('/buscar-carro', methods=['POST'])
def get_carro():
    data = request.get_json()

    idFiltro = data.get('id')

    # Query base
    query = '''
           SELECT id_carro, marca, modelo, ano_modelo, ano_fabricacao, versao, cor, renavam, cambio, combustivel, categoria, 
                  quilometragem, estado, cidade, preco_compra, preco_venda, licenciado, placa, criado_em, ativo 
           FROM CARROS
       '''

    cursor = con.cursor()

    token = request.headers.get('Authorization')
    if token:
        token = remover_bearer(token)
        payload = jwt.decode(token, senha_secreta, algorithms=['HS256'])
        id_usuario = payload['id_usuario']

        cursor.execute("SELECT TIPO_USUARIO FROM USUARIO WHERE ID_USUARIO = ?", (id_usuario,))
        tipo_user = cursor.fetchone()[0]

        if tipo_user == 3:
            cursor.execute(
                'SELECT ID_USUARIO_RESERVA FROM CARROS WHERE RESERVADO IS TRUE AND ID_USUARIO_RESERVA = ? AND ID_CARRO = ?',
                (id_usuario, idFiltro))
        else:
            cursor.execute('SELECT ID_USUARIO_RESERVA FROM CARROS WHERE RESERVADO IS TRUE AND ID_CARRO = ?', (idFiltro,))

        usuario_reservou = cursor.fetchone()

        if tipo_user == 3:
            cursor.execute(
                '''
                SELECT venda_compra.status
                FROM carros
                INNER JOIN venda_compra
                ON carros.id_carro = venda_compra.id_veiculo
                AND venda_compra.tipo_veiculo = 1
                WHERE venda_compra.id_usuario = ? AND carros.ativo = 0
                AND carros.id_carro = ? AND venda_compra.tipo_venda_compra = 1
                ''', (id_usuario, idFiltro)
            )
        else:
            cursor.execute(
                '''
                SELECT 1
                FROM carros
                INNER JOIN venda_compra
                ON carros.id_carro = venda_compra.id_veiculo
                AND venda_compra.tipo_veiculo = 1
                WHERE carros.ativo = 0 AND carros.id_carro = ?
                AND venda_compra.tipo_venda_compra = 1 
                ''', (idFiltro,)
            )

        carro_vendido = cursor.fetchone()

        status_venda = 0
        if carro_vendido:
            status_venda = carro_vendido[0]

        if usuario_reservou or carro_vendido:
            cursor.execute(f'{query} WHERE ID_CARRO = ?', (idFiltro,))

            carro = cursor.fetchone()

            images_dir = os.path.join(app.root_path, upload_folder, 'Carros', str(idFiltro))
            imagens = []

            # Verifica se o diretório existe
            if os.path.exists(images_dir):
                for file in os.listdir(images_dir):
                    if file.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
                        imagem_url = url_for('get_car_image', id_carro=idFiltro, filename=file, _external=True)
                        imagens.append(imagem_url)

            dados_carro = {
                'id': carro[0],
                'marca': carro[1],
                'modelo': carro[2],
                'ano_modelo': carro[3],
                'ano_fabricacao': carro[4],
                'versao': carro[5],
                'cor': carro[6],
                'renavam': carro[7],
                'cambio': carro[8],
                'combustivel': carro[9],
                'categoria': carro[10],
                'quilometragem': carro[11],
                'estado': carro[12],
                'cidade': carro[13],
                'preco_compra': carro[14],
                'preco_venda': carro[15],
                'licenciado': carro[16],
                'placa': carro[17],
                'criado_em': carro[18],
                'ativo': carro[19],
                'imagens': imagens
            }

            if usuario_reservou:

                cursor.execute('SELECT NOME_COMPLETO FROM USUARIO WHERE ID_USUARIO = ?', (usuario_reservou[0],))
                nome_usuario = cursor.fetchone()[0]

                cursor.close()

                return jsonify({
                    "reserva": True,
                    "veiculos": [dados_carro],
                    "nome_usuario": nome_usuario
                }), 200

            elif carro_vendido:
                if status_venda == 2:
                    return jsonify({
                        "vendido": True,
                        "veiculos": [dados_carro]
                    }), 200
                elif status_venda == 1:
                    return jsonify({
                        "vendido": True,
                        "parcelamento": True,
                        "veiculos": [dados_carro]
                    }), 200

    anoMaxFiltro = data.get('ano-max')
    anoMinFiltro = data.get('ano-min')
    categoriaFiltro = data.get('categoria')
    cidadeFiltro = data.get('cidade')
    estadoFiltro = data.get('estado')
    marcaFiltro = data.get('marca')
    precoMax = data.get('preco-max')
    precoMinFiltro = data.get('preco-min')
    coresFiltro = data.get('cores')  # Pode ser uma lista ou string
    nomeCarro = data.get('nome-veic')

    conditions = []
    params = []

    # Adiciona as condições de acordo com os filtros informados
    if idFiltro:
        conditions.append("id_carro = ?")
        params.append(idFiltro)
    if anoMaxFiltro:
        conditions.append("ano_modelo <= ?")
        params.append(anoMaxFiltro)
    if anoMinFiltro:
        conditions.append("ano_modelo >= ?")
        params.append(anoMinFiltro)
    if categoriaFiltro:
        conditions.append("categoria = ?")
        params.append(categoriaFiltro)
    if cidadeFiltro:
        conditions.append("cidade = ?")
        params.append(cidadeFiltro)
    if estadoFiltro:
        conditions.append("estado = ?")
        params.append(estadoFiltro)
    if marcaFiltro:
        conditions.append("marca = ?")
        params.append(marcaFiltro)
    if precoMax:
        conditions.append("preco_venda <= ?")
        params.append(precoMax)
    if precoMinFiltro:
        conditions.append("preco_venda >= ?")
        params.append(precoMinFiltro)
    if coresFiltro:
        # Se coresFiltro for uma lista, usamos IN; caso contrário, comparamos com igualdade
        if isinstance(coresFiltro, list):
            placeholders = ','.join('?' * len(coresFiltro))
            conditions.append(f"cor IN ({placeholders})")
            params.extend(coresFiltro)
        else:
            conditions.append("cor = ?")
            params.append(coresFiltro)
    if nomeCarro:
        nomeCarro = nomeCarro.lower()
        conditions.append('(LOWER(MARCA) LIKE ? OR LOWER(MODELO) LIKE ?)')
        params.append(f"%{nomeCarro}%")
        params.append(f"%{nomeCarro}%")

    conditions.append('ATIVO = 1')
    conditions.append('RESERVADO IS NOT TRUE')

    # Se houver condições, concatena à query base
    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    cursor = con.cursor()
    cursor.execute(query, params)
    fetch = cursor.fetchall()

    lista_carros = []
    for carro in list(fetch):
        id_carro = carro[0]
        # Define o caminho para a pasta de imagens do carro (ex: uploads/Carros/<id_carro>)
        images_dir = os.path.join(app.root_path, upload_folder, 'Carros', str(id_carro))
        imagens = []

        # Verifica se o diretório existe
        if os.path.exists(images_dir):
            for file in os.listdir(images_dir):
                if file.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
                    imagem_url = url_for('get_car_image', id_carro=id_carro, filename=file, _external=True)
                    imagens.append(imagem_url)

        lista_carros.append({
            'id': carro[0],
            'marca': carro[1],
            'modelo': carro[2],
            'ano_modelo': carro[3],
            'ano_fabricacao': carro[4],
            'versao': carro[5],
            'cor': carro[6],
            'renavam': carro[7],
            'cambio': carro[8],
            'combustivel': carro[9],
            'categoria': carro[10],
            'quilometragem': carro[11],
            'estado': carro[12],
            'cidade': carro[13],
            'preco_compra': carro[14],
            'preco_venda': carro[15],
            'licenciado': carro[16],
            'placa': carro[17],
            'criado_em': carro[18],
            'ativo': carro[19],
            'imagens': imagens
        })

    qnt_carros = len(lista_carros)

    return jsonify({
        'success': f'{qnt_carros} carro(s) encontrado(s).',
        'qnt': qnt_carros,
        'veiculos': lista_carros
    }), 200

@app.route('/carro/upload_img/<int:id>', methods=['POST'])
def upload_img(id):
    token = request.headers.get('Authorization')
    if not token:
        return jsonify({'error': 'Token de autenticação necessário'}), 401

    token = remover_bearer(token)
    try:
        payload = jwt.decode(token, senha_secreta, algorithms=['HS256'])
        id_usuario = payload['id_usuario']
    except jwt.ExpiredSignatureError:
        return jsonify({'error': 'Token expirado'}), 401
    except jwt.InvalidTokenError:
        return jsonify({'error': 'Token inválido'}), 401

    cursor = con.cursor()

    cursor.execute('SELECT TIPO_USUARIO FROM USUARIO WHERE ID_USUARIO = ?', (id_usuario,))
    user_type = cursor.fetchone()[0]

    if user_type not in [1, 2]:
        cursor.close()
        return jsonify({'error': 'Acesso restrito a administradores'}), 403

    imagens = request.files.getlist('imagens')

    if not imagens:
        cursor.close()
        return jsonify({
            'error': 'Dados incompletos',
            'missing_fields': 'Imagens'
        }), 400

    # Define a pasta destino usando o id do carro
    pasta_destino = os.path.join(upload_folder, "Carros", str(id))
    os.makedirs(pasta_destino, exist_ok=True)

    # Salva cada imagem na pasta, nomeando sequencialmente (1.jpeg, 2.jpeg, 3.jpeg, ...)
    saved_images = []  # para armazenar os nomes dos arquivos salvos
    for index, imagem in enumerate(imagens, start=1):
        nome_imagem = f"{index}.jpeg"
        imagem_path = os.path.join(pasta_destino, nome_imagem)
        imagem.save(imagem_path)
        saved_images.append(nome_imagem)

    cursor.close()
    return jsonify({
        'success': "Imagens adicionadas!"
    }), 200


@app.route('/carro/editar_img/<int:id>', methods=['PUT'])
def editar_imagens(id):
    token = request.headers.get('Authorization')
    if not token:
        return jsonify({'error': 'Token de autenticação necessário'}), 401

    token = remover_bearer(token)
    try:
        payload = jwt.decode(token, senha_secreta, algorithms=['HS256'])
        id_usuario = payload['id_usuario']
    except jwt.ExpiredSignatureError:
        return jsonify({'error': 'Token expirado'}), 401
    except jwt.InvalidTokenError:
        return jsonify({'error': 'Token inválido'}), 401

    cursor = con.cursor()

    cursor.execute('SELECT TIPO_USUARIO FROM USUARIO WHERE ID_USUARIO = ?', (id_usuario,))
    user_type = cursor.fetchone()[0]

    cursor.close()
    if user_type not in [1, 2]:
        return jsonify({'error': 'Acesso restrito a administradores'}), 403

    # Obtém as imagens e filtra somente as que possuem um nome (arquivo válido)
    imagens_brutas = request.files.getlist('imagens')
    imagens = [img for img in imagens_brutas if img and img.filename]
    if not imagens:
        return jsonify({
            'error': 'Dados incompletos',
            'missing_fields': 'Imagens'
        }), 400

    if len(imagens) < 3:
        return jsonify({
            'error': 'É necessário enviar ao menos 3 imagens',
        }), 400

    # Define a pasta destino para as imagens do veículo
    pasta_destino = os.path.join(upload_folder, "Carros", str(id))

    # Se a pasta já existir, apaga-a para remover as imagens antigas
    if os.path.exists(pasta_destino):
        try:
            shutil.rmtree(pasta_destino)
        except Exception as e:
            return jsonify({'error': f'Erro ao remover imagens antigas: {str(e)}'}), 500
    else:
        return jsonify({'error': 'Veículo não encontrado'}), 400

    # Cria a pasta novamente para armazenar as novas imagens
    os.makedirs(pasta_destino, exist_ok=True)

    # Salva cada imagem na pasta, nomeando-as sequencialmente (1.jpeg, 2.jpeg, ...)
    for index, imagem in enumerate(imagens, start=1):
        nome_imagem = f"{index}.jpeg"
        imagem_path = os.path.join(pasta_destino, nome_imagem)
        try:
            imagem.save(imagem_path)
        except Exception as e:
            return jsonify({'error': f'Erro ao salvar a imagem: {str(e)}'}), 500

    return jsonify({'success': "Imagens atualizadas com sucesso!"}), 200

@app.route('/carro', methods=['POST'])
def add_carro():
    token = request.headers.get('Authorization')
    if not token:
        return jsonify({'error': 'Token de autenticação necessário'}), 401

    token = remover_bearer(token)
    try:
        payload = jwt.decode(token, senha_secreta, algorithms=['HS256'])
        id_usuario = payload['id_usuario']
    except jwt.ExpiredSignatureError:
        return jsonify({'error': 'Token expirado'}), 401
    except jwt.InvalidTokenError:
        return jsonify({'error': 'Token inválido'}), 401

    cursor = con.cursor()

    cursor.execute('SELECT TIPO_USUARIO FROM USUARIO WHERE ID_USUARIO = ?', (id_usuario,))
    user_type = cursor.fetchone()[0]
    if user_type not in [1,2]:
        return jsonify({'error': 'Acesso restrito a administradores'}), 403

    data = request.get_json()

    # Lista de campos obrigatórios
    required_fields = [
        'marca', 'modelo', 'ano_modelo', 'ano_fabricacao', 'versao',
        'cor', 'renavam', 'cambio', 'combustivel', 'categoria', 'quilometragem',
        'estado', 'cidade', 'preco_compra', 'preco_venda', 'licenciado', 'placa'
    ]

    missing_fields = [field for field in required_fields if not data.get(field)]

    if missing_fields:
        cursor.close()
        return jsonify({
            'error': f'Dados faltando: {missing_fields}'
        }), 400

    marca = data.get('marca')
    modelo = data.get('modelo')
    ano_modelo = data.get('ano_modelo')
    ano_fabricacao = data.get('ano_fabricacao')
    versao = data.get('versao')
    cor = data.get('cor')
    renavam = data.get('renavam')
    cambio = data.get('cambio')
    combustivel = data.get('combustivel')
    categoria = data.get('categoria')
    quilometragem = data.get('quilometragem')
    estado = data.get('estado')
    cidade = data.get('cidade')
    preco_compra = data.get('preco_compra')
    preco_venda = data.get('preco_venda')
    licenciado = data.get('licenciado')
    placa = data.get('placa').upper()
    ativo = 1

    if int(quilometragem) < 0:
        cursor.close()
        return jsonify({
            'error': 'A quilometragem não pode ser negativa.'
        }), 400

    if float(preco_compra) < 0 or float(preco_venda) < 0:
        cursor.close()
        return jsonify({
            'error': 'O preço não pode ser negativo.'
        }), 400

    # Alterando fuso horário para o de Brasília
    criado_em = datetime.now(pytz.timezone('America/Sao_Paulo'))

    # Retornar caso já exista placa cadastrada
    cursor.execute("SELECT 1 FROM CARROS WHERE PLACA = ?", (placa,))
    if cursor.fetchone():
        cursor.close()
        return jsonify({
            'error': 'Placa do veículo já cadastrada.'
        }), 409

    # Retornar caso já exista RENAVAM cadastrado
    cursor.execute("SELECT 1 FROM CARROS WHERE RENAVAM = ?", (renavam,))
    if cursor.fetchone():
        cursor.close()
        return jsonify({
            'error': 'Documento do veículo já cadastrado.'
        }), 409

    if (ano_modelo < ano_fabricacao):
        cursor.close()
        return jsonify({
            'error': 'Ano do modelo não pode ser anterior ao ano de fabricação.'
        }), 400

    if (preco_venda < preco_compra):
        cursor.close()
        return jsonify({
            'error': 'Preço de venda não pode ser menor ao preço de compra.'
        }), 400

    cursor.execute('''
        INSERT INTO CARROS
        (marca, modelo, ano_modelo, ano_fabricacao, versao, cor, renavam, cambio, combustivel, categoria, 
        quilometragem, estado, cidade, preco_compra, preco_venda, licenciado, placa, criado_em, ativo)
        VALUES
        (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)  RETURNING ID_CARRO
        ''', (marca, modelo, ano_modelo, ano_fabricacao, versao, cor, renavam, cambio, combustivel, categoria,
              quilometragem, estado, cidade, preco_compra, preco_venda, licenciado, placa, criado_em, ativo))

    id_carro = cursor.fetchone()[0]
    con.commit()

    cursor.close()

    return jsonify({
        'success': "Veículo cadastrado com sucesso!",
        'dados': {
            'id_carro': id_carro,
            'marca': marca,
            'modelo': modelo,
            'ano_modelo': ano_modelo,
            'ano_fabricacao': ano_fabricacao,
            'versao': versao,
            'cor': cor,
            'renavam': renavam,
            'cambio': cambio,
            'combustivel': combustivel,
            'categoria': categoria,
            'quilometragem': quilometragem,
            'estado': estado,
            'cidade': cidade,
            'preco_compra': preco_compra,
            'preco_venda': preco_venda,
            'licenciado': licenciado,
            'placa': placa,
            'criado_em': criado_em,
            'ativo': ativo
        }
    }), 200

@app.route('/carro/<int:id>', methods=['DELETE'])
def deletar_carro(id):
    token = request.headers.get('Authorization')
    if not token:
        return jsonify({'error': 'Token de autenticação necessário'}), 401

    token = remover_bearer(token)
    try:
        payload = jwt.decode(token, senha_secreta, algorithms=['HS256'])
        id_usuario = payload['id_usuario']
    except jwt.ExpiredSignatureError:
        return jsonify({'error': 'Token expirado'}), 401
    except jwt.InvalidTokenError:
        return jsonify({'error': 'Token inválido'}), 401

    cursor = con.cursor()

    cursor.execute('SELECT TIPO_USUARIO FROM USUARIO WHERE ID_USUARIO = ?', (id_usuario,))
    user_type = cursor.fetchone()[0]
    if user_type not in [1,2]:
        cursor.close()
        return jsonify({'error': 'Acesso restrito a administradores'}), 403

    cursor = con.cursor()

    cursor.execute('SELECT 1 FROM CARROS WHERE ID_CARRO = ?', (id,))

    if not cursor.fetchone():
        cursor.close()
        return jsonify({'error': 'Veículo não encontrado.'}), 404

    cursor.execute('DELETE FROM CARROS WHERE ID_CARRO = ?', (id,))

    con.commit()
    cursor.close()

    pasta_destino = os.path.join(upload_folder, "Carros", str(id))

    # Verifica se a pasta existe e a remove
    if os.path.exists(pasta_destino):
        try:
            shutil.rmtree(pasta_destino)
        except Exception as e:
            return jsonify({'error': f'Erro ao deletar a pasta do veículo: {str(e)}'}), 500

    return jsonify({
        'success': "Veículo deletado com sucesso!",
        'tipo_usuario': user_type
    }), 200

@app.route('/carro/<int:id>', methods=['PUT'])
def editar_carro(id):
    cursor = con.cursor()

    # Verificando a existência do carro
    cursor.execute('SELECT 1 FROM CARROS WHERE ID_CARRO = ?', (id,))
    if not cursor.fetchone():
        cursor.close()
        return jsonify({'error': 'Veículo não encontrado.'}), 404

    data = request.get_json()
    fields = [
        'marca', 'modelo', 'ano_modelo', 'ano_fabricacao', 'versao',
        'cor', 'renavam', 'cambio', 'combustivel', 'categoria', 'quilometragem',
        'estado', 'cidade', 'preco_compra', 'preco_venda', 'licenciado',
        'placa', 'ativo'
    ]

    cursor.execute('''
        SELECT marca, modelo, ano_modelo, ano_fabricacao, versao, cor, renavam, cambio, combustivel, categoria, 
        quilometragem, estado, cidade, preco_compra, preco_venda, licenciado, placa, ativo
        FROM CARROS WHERE ID_CARRO = ?
    ''', (id,))

    data_ant = []
    for item in cursor.fetchone():
        data_ant.append(item)

    for i in range(len(data_ant)):
        if data.get(fields[i]) == data_ant[i] or not data.get(fields[i]):
            data[fields[i]] = data_ant[i]

    marca = data.get('marca')
    modelo = data.get('modelo')
    ano_modelo = data.get('ano_modelo')
    ano_fabricacao = data.get('ano_fabricacao')
    versao = data.get('versao')
    cor = data.get('cor')
    renavam = data.get('renavam')
    cambio = data.get('cambio')
    combustivel = data.get('combustivel')
    categoria = data.get('categoria')
    quilometragem = data.get('quilometragem')
    estado = data.get('estado')
    cidade = data.get('cidade')
    preco_compra = data.get('preco_compra')
    preco_venda = data.get('preco_venda')
    licenciado = data.get('licenciado')
    placa = data.get('placa').upper()

    ativo = data.get('ativo')

    cursor.execute('''
        UPDATE CARROS
        SET marca =?, modelo =?, ano_modelo =?, ano_fabricacao =?, versao =?, cor =?, renavam =?, cambio =?, combustivel =?, categoria =?, 
        quilometragem =?, estado =?, cidade =?, preco_compra =?, preco_venda =?, licenciado =?, placa =?, ativo =?
        where ID_CARRO = ?
        ''', (marca, modelo, ano_modelo, ano_fabricacao, versao, cor, renavam, cambio, combustivel, categoria,
              quilometragem, estado, cidade, preco_compra, preco_venda, licenciado, placa, ativo, id))

    con.commit()
    cursor.close()

    return jsonify({
        'success': "Veículo editado com sucesso!",
        'dados': {
            'marca': marca,
            'modelo': modelo,
            'ano_modelo': ano_modelo,
            'ano_fabricacao': ano_fabricacao,
            'versao': versao,
            'cor': cor,
            'renavam': renavam,
            'cambio': cambio,
            'combustivel': combustivel,
            'categoria': categoria,
            'quilometragem': quilometragem,
            'estado': estado,
            'cidade': cidade,
            'preco_compra': preco_compra,
            'preco_venda': preco_venda,
            'licenciado': licenciado,
            'placa': placa,
            'ativo': ativo
        }
    }), 200