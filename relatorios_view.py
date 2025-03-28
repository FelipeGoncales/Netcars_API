from flask import Flask, send_file, request
from main import app, con
from fpdf import FPDF
from datetime import datetime
import re

# Formatção de informações

def format_currency(value):
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def format_kilometragem(value):
    return f"{value:,} km".replace(",", ".")

def format_phone(phone):
    # Se não houver informação, retorna None
    if phone is None:
        return None
    # Converte para string
    phone_str = str(phone)
    # Remove tudo que não for dígito
    digits = re.sub(r'\D', '', phone_str) 

    if len(digits) == 11:
        # Formata como (XX) XXXXX-XXXX
        return f"({digits[0:2]}) {digits[2:7]}-{digits[7:]}"
    elif len(digits) == 10:
        # Formata como (XX) XXXX-XXXX
        return f"({digits[0:2]}) {digits[2:6]}-{digits[6:]}"
    else:
        # Se não tiver 10 ou 11 dígitos, retorna o valor original
        return phone_str

def format_cpf_cnpj(value):
    if value is None:
        return None
    value_str = str(value)
    digits = re.sub(r'\D', '', value_str)

    if len(digits) == 11:
        # Formata como CPF: 000.000.000-00
        return f"{digits[:3]}.{digits[3:6]}.{digits[6:9]}-{digits[9:]}"
    elif len(digits) == 14:
        # Formata como CNPJ: 00.000.000/0000-00
        return f"{digits[:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:12]}-{digits[12:]}"
    else:
        # Se não estiver em um dos formatos, retorna o valor original
        return value_str

def format_date(date_value):
    if date_value is None:
        return None
    # Se já for um objeto datetime, formata diretamente
    if isinstance(date_value, datetime):
        return date_value.strftime('%d/%m/%Y')
    try:
        # Tenta assumir que a string está no formato 'YYYY-MM-DD'
        dt = datetime.strptime(str(date_value), '%Y-%m-%d')
        return dt.strftime('%d/%m/%Y')
    except ValueError:
        # Se não conseguir, retorna o valor convertido para string
        return str(date_value)

# Fim das formatações

# Class para título de cada Página

class CustomCarroPDF(FPDF):
    def header(self):
        self.set_font("Arial", "B", 16)
        self.cell(0, 10, "Relação de Carros", ln=True, align='C')
        self.ln(5)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font("Arial", "I", 10)
        self.cell(0, 10, f"Página {self.page_no()}", align="C")

class CustomMotosPDF(FPDF):
    def header(self):
        self.set_font("Arial", "B", 16)
        self.cell(0, 10, "Relação de Motos", ln=True, align='C')
        self.ln(5)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font("Arial", "I", 10)
        self.cell(0, 10, f"Página {self.page_no()}", align="C")

class CustomUsuarioPDF(FPDF):
    def header(self):
        self.set_font("Arial", "B", 16)
        self.cell(0, 10, "Relatório de Usuários", ln=True, align='C')
        self.ln(5)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font("Arial", "I", 10)
        self.cell(0, 10, f"Página {self.page_no()}", align="C")


# Fim das Class

# Início das Rotas

@app.route('/relatorio/carros', methods=['GET'])
def criar_pdf_carro():
    marca = request.args.get('marca')
    ano_fabricacao = request.args.get('ano_fabricacao')
    ano_modelo = request.args.get('ano_modelo')

    query = """SELECT marca, modelo, placa, ano_modelo, ano_fabricacao, cor, renavam, cambio, combustivel, 
                      categoria, quilometragem, estado, cidade, preco_compra, preco_venda, licenciado, versao 
               FROM carros WHERE 1=1"""
    params = []

    if marca:
        query += " AND UPPER(MARCA) = UPPER(?)"
        params.append(marca)

    if ano_fabricacao and ano_modelo:
        query += " AND ano_fabricacao = ? AND ano_modelo = ?"
        params.extend([ano_fabricacao, ano_modelo])
    elif ano_fabricacao:
        query += " AND ano_fabricacao = ?"
        params.append(ano_fabricacao)
    elif ano_modelo:
        query += " AND ano_modelo = ?"
        params.append(ano_modelo)

    cursor = con.cursor()
    cursor.execute(query, params)
    carros = cursor.fetchall()
    cursor.close()

    total_veiculos = len(carros)
    pdf = CustomCarroPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    carros_por_pagina = 3
    contador = 0

    for carro in carros:
        if contador == carros_por_pagina:
            pdf.add_page()
            contador = 0

        campos = [
            ("Marca", carro[0]),
            ("Modelo", carro[1]),
            ("Placa", carro[2]),
            ("Ano Modelo", carro[3]),
            ("Ano Fabricação", carro[4]),
            ("Cor", carro[5]),
            ("Renavam", carro[6]),
            ("Câmbio", carro[7]),
            ("Combustível", carro[8]),
            ("Categoria", carro[9]),
            ("Quilometragem", format_kilometragem(carro[10])),
            ("Estado", carro[11]),
            ("Cidade", carro[12]),
            ("Preço Compra", format_currency(carro[13])),
            ("Preço Venda", format_currency(carro[14])),
            ("Licenciado", "Sim" if carro[15] == 1 else "Não"),
            ("Versão", carro[16])
        ]

        for i in range(0, len(campos) - 1, 2):
            pdf.set_font("Arial", "B", 12)
            pdf.cell(35, 10, f"{campos[i][0]}:", border=0)
            pdf.set_font("Arial", "", 12)
            pdf.cell(40, 10, str(campos[i][1]), border=0)

            if i + 1 < len(campos) - 1:
                pdf.set_x(120)
                pdf.set_font("Arial", "B", 12)
                pdf.cell(35, 10, f"{campos[i + 1][0]}:", border=0)
                pdf.set_font("Arial", "", 12)
                pdf.cell(40, 10, str(campos[i + 1][1]), border=0)
            pdf.ln(8)

        pdf.set_font("Arial", "B", 12)
        pdf.cell(35, 10, "Versão:", border=0)
        pdf.set_font("Arial", "", 12)
        pdf.multi_cell(0, 10, str(campos[-1][1]), border=0)

        pdf.ln(5)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(5)

        contador += 1

    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 10, f"Total de carros: {total_veiculos}", ln=True, align="C")

    pdf_path = "relatorio_carros.pdf"
    pdf.output(pdf_path)
    return send_file(pdf_path, mimetype='application/pdf', as_attachment=False)

@app.route('/relatorio/motos', methods=['GET'])
def criar_pdf_moto():
    marca = request.args.get('marca')
    ano_fabricacao = request.args.get('ano_fabricacao')
    ano_modelo = request.args.get('ano_modelo')

    query = """SELECT marca, modelo, placa, ano_modelo, ano_fabricacao, categoria, cor, renavam, 
                      marchas, partida, tipo_motor, cilindrada, freio_dianteiro_traseiro, refrigeracao, 
                      alimentacao, estado, cidade, quilometragem, preco_compra, preco_venda, licenciado 
               FROM motos WHERE 1=1"""
    params = []

    if marca:
        query += " AND UPPER(MARCA) = UPPER(?)"
        params.append(marca)

    if ano_fabricacao and ano_modelo:
        query += " AND ano_fabricacao = ? AND ano_modelo = ?"
        params.extend([ano_fabricacao, ano_modelo])
    elif ano_fabricacao:
        query += " AND ano_fabricacao = ?"
        params.append(ano_fabricacao)
    elif ano_modelo:
        query += " AND ano_modelo = ?"
        params.append(ano_modelo)

    cursor = con.cursor()
    cursor.execute(query, params)
    motos = cursor.fetchall()
    cursor.close()

    total_veiculos = len(motos)

    pdf = CustomMotosPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    motos_por_pagina = 2
    contador = 0

    for moto in motos:
        if contador == motos_por_pagina:
            pdf.add_page()
            contador = 0

        campos = [
            ("Marca", moto[0]),
            ("Modelo", moto[1]),
            ("Placa", moto[2]),
            ("Ano Modelo", moto[3]),
            ("Ano Fabricação", moto[4]),
            ("Categoria", moto[5]),
            ("Cor", moto[6]),
            ("Renavam", moto[7]),
            ("Marchas", moto[8]),
            ("Partida", moto[9]),
            ("Tipo do Motor", moto[10]),
            ("Cilindradas", moto[11]),
            ("Freio D/T", moto[12]),
            ("Refrigeração", moto[13]),
            ("Alimentação", moto[14]),
            ("Estado", moto[15]),
            ("Cidade", moto[16]),
            ("Quilometragem", format_kilometragem(moto[17])),
            ("Preço Compra", format_currency(moto[18])),
            ("Preço Venda", format_currency(moto[19])),
            ("Licenciado", "Sim" if moto[20] == 1 else "Não")
        ]

        for i in range(0, len(campos), 2):
            pdf.set_font("Arial", "B", 12)
            pdf.cell(35, 10, f"{campos[i][0]}:", border=0)
            pdf.set_font("Arial", "", 12)
            pdf.cell(40, 10, str(campos[i][1]), border=0)

            if i + 1 < len(campos):
                pdf.set_x(120)
                pdf.set_font("Arial", "B", 12)
                pdf.cell(35, 10, f"{campos[i + 1][0]}:", border=0)
                pdf.set_font("Arial", "", 12)
                pdf.cell(40, 10, str(campos[i + 1][1]), border=0)
            pdf.ln(8)

        pdf.ln(5)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(5)

        contador += 1

    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 10, f"Total de motos: {total_veiculos}", ln=True, align="C")

    pdf_path = "relatorio_motos.pdf"
    pdf.output(pdf_path)
    return send_file(pdf_path, mimetype='application/pdf', as_attachment=False)


@app.route('/relatorio/usuarios', methods=['GET'])
def criar_pdf_usuarios():
    # Obtendo parâmetros de filtro via query string
    nome = request.args.get('nome', '').strip()
    cpf_cnpj = request.args.get('cpf_cnpj', '').strip()
    dia = request.args.get('dia', '').strip()
    mes = request.args.get('mes', '').strip()
    ano = request.args.get('ano', '').strip()
    ativo = request.args.get('ativo', '').strip()

    if ativo.lower() == "ativo":
        ativo = 1
    elif ativo.lower() == "inativo":
        ativo = 0

    # Monta a query com todos os campos, mas adiciona os filtros se forem informados
    query = """
        SELECT 
            nome_completo,
            email,
            telefone,
            cpf_cnpj,
            data_nascimento,
            ativo
        FROM usuario
        WHERE 1=1
    """
    params = []

    # Filtro por nome (busca parcial, sem distinção de caixa)
    if nome:
        query += " AND UPPER(nome_completo) LIKE ?"
        params.append('%' + nome.upper() + '%')

    # Filtro por CPF/CNPJ (busca parcial)
    if cpf_cnpj:
        query += " AND UPPER(cpf_cnpj) LIKE ?"
        params.append('%' + cpf_cnpj.upper() + '%')

    # Filtro por data de nascimento usando EXTRACT para dia, mês e ano
    if dia:
        query += " AND EXTRACT(DAY FROM data_nascimento) = ?"
        params.append(int(dia))
    if mes:
        query += " AND EXTRACT(MONTH FROM data_nascimento) = ?"
        params.append(int(mes))
    if ano:
        query += " AND EXTRACT(YEAR FROM data_nascimento) = ?"
        params.append(int(ano))

    # Filtro por status (ativo)
    if ativo in [0, 1]:
        query += " AND ativo = ?"
        params.append(int(ativo))

    cursor = con.cursor()
    cursor.execute(query, params)
    usuarios = cursor.fetchall()
    cursor.close()

    total_usuarios = len(usuarios)

    pdf = CustomUsuarioPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    usuarios_por_pagina = 7
    contador = 0

    for usuario in usuarios:
        if contador == usuarios_por_pagina:
            pdf.add_page()
            contador = 0

        # Campos retornados pelo SELECT:
        # 0: nome_completo, 1: email, 2: telefone, 3: cpf_cnpj, 4: data_nascimento, 5: ativo
        campos = [
            ("Nome", usuario[0]),
            ("Email", usuario[1]),
            ("Telefone", format_phone(usuario[2])),
            ("CPF/CNPJ", format_cpf_cnpj(usuario[3])),
            ("Nascimento", format_date(usuario[4])),
            ("Ativo", "Sim" if usuario[5] == 1 else "Não")
        ]

        # Exibe os campos com os labels próximos dos valores
        for i in range(0, len(campos), 2):
            pdf.set_font("Arial", "B", 12)
            pdf.cell(30, 10, f"{campos[i][0]}:", border=0)
            pdf.set_font("Arial", "", 12)
            pdf.cell(45, 10, str(campos[i][1]), border=0)

            if i + 1 < len(campos):
                # Ajusta o offset para aproximar os dados dos labels
                pdf.set_x(pdf.get_x() + 10)
                pdf.set_font("Arial", "B", 12)
                pdf.cell(30, 10, f"{campos[i + 1][0]}:", border=0)
                pdf.set_font("Arial", "", 12)
                pdf.cell(45, 10, str(campos[i + 1][1]), border=0)
            pdf.ln(8)

        pdf.ln(5)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(5)
        contador += 1

    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 10, f"Total de usuários: {total_usuarios}", ln=True, align="C")

    pdf_path = "relatorio_usuarios.pdf"
    pdf.output(pdf_path)
    return send_file(pdf_path, mimetype='application/pdf', as_attachment=False)

# Fim das Rotas