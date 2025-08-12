from flask import Flask, jsonify, request
from main import app, con, senha_secreta
import jwt
from datetime import datetime


def remover_bearer(token):
    if token.startswith('Bearer '):
        return token[len('Bearer '):]
    else:
        return token

@app.route('/movimentacoes', methods=['GET'])
def get_movimentacoes():
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
    if user_type != 1:  # Apenas administrador tipo 1
        return jsonify({'error': 'Acesso restrito a administradores.'}), 403

    dia = request.args.get('dia')
    mes = request.args.get('mes')
    ano = request.args.get('ano')

    if dia and not mes and not ano:
        return jsonify({'error': 'Informe o mês e o ano.'}), 400

    if mes and not ano:
        return jsonify({'error': 'Informe o ano.'}), 400

    try:
        query = '''SELECT ID_RECEITA_DESPESA, TIPO, VALOR, DATA_RECEITA_DESPESA, DESCRICAO, 
                ID_ORIGEM, TABELA_ORIGEM FROM RECEITA_DESPESA 
                '''

        params = []
        where = []

        cursor = con.cursor()

        if dia or mes or ano:
            if ano:
                where.append("EXTRACT(YEAR FROM DATA_RECEITA_DESPESA) = ?")
                params.append(ano)
            if mes:
                where.append("EXTRACT(MONTH FROM DATA_RECEITA_DESPESA) = ?")
                params.append(mes)
            if dia:
                where.append("EXTRACT(DAY FROM DATA_RECEITA_DESPESA) = ?")
                params.append(dia)

            sentenca = ' WHERE '+' AND '.join(where)

            query += sentenca + " ORDER BY DATA_RECEITA_DESPESA DESC"

            cursor.execute(query, params)
        else:
            query += " ORDER BY DATA_RECEITA_DESPESA DESC"
            cursor.execute(query)

        resposta = cursor.fetchall()

        movimentacoes = []
        total_receitas = 0
        total_despesas = 0

        for mov in resposta:
            tipo_texto = "receita" if mov[1] == 1 else "despesa"
            valor = float(mov[2]) if mov[2] is not None else 0.0

            # Calculando totais
            if mov[1] == 1:  # Receita
                total_receitas += valor
            else:  # Despesa
                total_despesas += valor

            movimentacoes.append({
                'id_receita_despesa':      mov[0],
                'tipo':                    tipo_texto,
                'valor':                   valor,
                'data_receita_despesa':    mov[3],
                'descricao':               mov[4],
                'id_origem':               mov[5],
                'tabela_origem':           mov[6]
            })

        saldo = total_receitas - total_despesas

        return jsonify({
            'movimentacoes': movimentacoes,
            'totais': {
                'receitas': total_receitas,
                'despesas': total_despesas,
                'saldo': saldo
            }
        }), 200
    except Exception as e:
        return jsonify({
            'error': str(e)
        }), 400
    finally:
        cursor.close()

@app.route('/movimentacoes/<tipo>', methods=['GET'])
def get_movimentacoes_por_tipo(tipo):
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
    if user_type != 1:  # Apenas administrador tipo 1
        return jsonify({'error': 'Acesso restrito a administradores'}), 403

    # Converter string tipo para o valor numérico
    tipo_valor = 1 if tipo.lower() == 'receita' else 2

    try:
        cursor = con.cursor()

        cursor.execute(
            '''SELECT ID_RECEITA_DESPESA, TIPO, VALOR, DATA_RECEITA_DESPESA, DESCRICAO, 
               ID_ORIGEM, TABELA_ORIGEM FROM RECEITA_DESPESA 
               WHERE TIPO = ? 
               ORDER BY DATA_RECEITA_DESPESA DESC''', (tipo_valor,))

        resposta = cursor.fetchall()

        movimentacoes = []
        total = 0

        for mov in resposta:
            tipo_texto = "receita" if mov[1] == 1 else "despesa"
            valor = float(mov[2]) if mov[2] is not None else 0.0
            total += valor

            movimentacoes.append({
                'id_receita_despesa':      mov[0],
                'tipo':                    tipo_texto,
                'valor':                   valor,
                'data_receita_despesa':    mov[3],
                'descricao':               mov[4],
                'id_origem':               mov[5],
                'tabela_origem':           mov[6]
            })

        return jsonify({
            'movimentacoes': movimentacoes,
            'total': total
        }), 200
    except Exception as e:
        return jsonify({
            'error': str(e)
        }), 400
    finally:
        cursor.close()


@app.route('/movimentacoes/<tabela>/<int:id_origem>', methods=['GET'])
def get_movimentacoes_por_origem(tabela, id_origem):
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
    if user_type != 1:  # Apenas administrador tipo 1
        return jsonify({'error': 'Acesso restrito a administradores'}), 403

    try:
        cursor = con.cursor()

        cursor.execute(
            '''SELECT ID_RECEITA_DESPESA, TIPO, VALOR, DATA_RECEITA_DESPESA, DESCRICAO, 
               ID_ORIGEM, TABELA_ORIGEM FROM RECEITA_DESPESA 
               WHERE TABELA_ORIGEM = ? AND ID_ORIGEM = ? 
               ORDER BY DATA_RECEITA_DESPESA DESC''', (tabela, id_origem))

        resposta = cursor.fetchall()

        if not resposta:
            return jsonify({'message': 'Nenhuma movimentação encontrada para esta origem.'}), 400

        movimentacoes = []

        for mov in resposta:
            tipo_texto = "receita" if mov[1] == 1 else "despesa"
            valor = float(mov[2]) if mov[2] is not None else 0.0

            movimentacoes.append({
                'id_receita_despesa':      mov[0],
                'tipo':                    tipo_texto,
                'valor':                   valor,
                'data_receita_despesa':    mov[3],
                'descricao':               mov[4],
                'id_origem':               mov[5],
                'tabela_origem':           mov[6]
            })

        return jsonify({
            'movimentacoes': movimentacoes
        }), 200
    except Exception as e:
        return jsonify({
            'error': str(e)
        }), 400
    finally:
        cursor.close()


@app.route('/movimentacoes', methods=['POST'])
def post_movimentacao():
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
    if user_type != 1:  # Apenas administrador tipo 1
        return jsonify({'error': 'Acesso restrito a administradores'}), 403

    data = request.get_json()

    tipo = data.get('tipo')
    valor = data.get('valor')
    data_mov = data.get('data')
    descricao = data.get('descricao')

    # Validação de campos obrigatórios
    if not tipo or not valor or not data_mov or not descricao:
        return jsonify({
            'error': 'Dados incompletos.'
        }), 400

    # Converter string tipo para o valor numérico
    tipo_valor = 1 if tipo.lower() == 'receita' else 2

    try:
        cursor = con.cursor()

        cursor.execute('''
            INSERT INTO RECEITA_DESPESA 
            (TIPO, VALOR, DATA_RECEITA_DESPESA, DESCRICAO)
            VALUES
            (?, ?, ?, ?)
            RETURNING ID_RECEITA_DESPESA
        ''', (tipo_valor, valor, data_mov, descricao))

        id_movimentacao = cursor.fetchone()[0]

        con.commit()

        # Resposta de sucesso
        return jsonify({
            'success': f'{tipo.capitalize()} cadastrada com sucesso!',
            'id_receita_despesa': id_movimentacao,
            'tipo': tipo
        }), 200
    except Exception as e:
        con.rollback()
        return jsonify({
            'error': str(e)
        }), 400
    finally:
        cursor.close()
@app.route('/movimentacoes/<int:id_mov>', methods=['PUT'])
def put_movimentacao(id_mov):
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
    if user_type != 1:  # Apenas administrador tipo 1
        return jsonify({'error': 'Acesso restrito a administradores'}), 403

    data = request.get_json()

    tipo = data.get('tipo')
    valor = data.get('valor')
    data_mov = data.get('data')
    descricao = data.get('descricao')
    id_origem = data.get('id_origem')  # Mantido caso venha do front
    tabela_origem = data.get('tabela_origem') or ""  # Mantido caso venha do front

    # Validação de campos obrigatórios
    if not tipo or not valor or not data_mov or not descricao:
        return jsonify({
            'error': 'Dados incompletos. Tipo, valor, data e descrição são obrigatórios.'
        }), 400

    # Converter string tipo para o valor numérico
    tipo_valor = 1 if tipo.lower() == 'receita' else 2

    # Verifica se a movimentação existe
    cursor.execute('SELECT 1 FROM RECEITA_DESPESA WHERE ID_RECEITA_DESPESA = ?', (id_mov,))
    if cursor.fetchone() is None:
        return jsonify({'error': 'Movimentação não encontrada.'}), 404

    try:
        # Se id_origem e tabela_origem não forem fornecidos, manter os valores atuais
        if id_origem is None or tabela_origem is None:
            cursor.execute(
                'SELECT ID_ORIGEM, TABELA_ORIGEM FROM RECEITA_DESPESA WHERE ID_RECEITA_DESPESA = ?', 
                (id_mov,)
            )
            result = cursor.fetchone()
            if result:
                if id_origem is None:
                    id_origem = result[0]
                if tabela_origem is None:
                    tabela_origem = result[1]

        cursor.execute('''
            UPDATE RECEITA_DESPESA 
            SET TIPO = ?, 
                VALOR = ?, 
                DATA_RECEITA_DESPESA = ?, 
                DESCRICAO = ?,
                ID_ORIGEM = ?,
                TABELA_ORIGEM = ?
            WHERE ID_RECEITA_DESPESA = ?
        ''', (tipo_valor, valor, data_mov, descricao, id_origem, tabela_origem, id_mov))

        con.commit()

        # Resposta de sucesso
        return jsonify({
            'success': 'Movimentação atualizada com sucesso.',
            'id': id_mov
        }), 200
    except Exception as e:
        con.rollback()
        return jsonify({
            'error': str(e)
        }), 400
    finally:
        cursor.close()


@app.route('/movimentacoes/<int:id_mov>', methods=['DELETE'])
def delete_movimentacao(id_mov):
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
    if user_type != 1:  # Apenas administrador tipo 1
        return jsonify({'error': 'Acesso restrito a administradores'}), 403

    # Verifica se a movimentação existe
    cursor.execute('SELECT 1 FROM RECEITA_DESPESA WHERE ID_RECEITA_DESPESA = ?', (id_mov,))
    if cursor.fetchone() is None:
        return jsonify({'error': 'Movimentação não encontrada.'}), 404

    try:
        cursor.execute('DELETE FROM RECEITA_DESPESA WHERE ID_RECEITA_DESPESA = ?', (id_mov,))
        con.commit()

        # Resposta de sucesso
        return jsonify({
            'success': 'Movimentação excluída com sucesso.'
        }), 200
    except Exception as e:
        con.rollback()
        return jsonify({
            'error': str(e)
        }), 400
    finally:
        cursor.close()