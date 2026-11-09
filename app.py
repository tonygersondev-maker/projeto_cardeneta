import os
import psycopg2
from psycopg2.extras import DictCursor
from flask import Flask, render_template, request, redirect, url_for, flash, session

app = Flask(__name__)
app.secret_key = "chave_secreta_ficticia_para_o_mvp_ead"

# Link do Supabase
URL_BANCO = "postgresql://postgres:Pimenta@1945@://supabase.com"

# CONEXÃO GLOBAL PERSISTENTE: Abre uma única vez para o app inteiro ficar rápido
try:
    conexao_global = psycopg2.connect(URL_BANCO, cursor_factory=DictCursor)
    conexao_global.autocommit = True
    print("Conexão persistente com o Supabase estabelecida com sucesso!")
except Exception as e:
    print(f"Erro crítico ao conectar no banco: {e}")
    conexao_global = None

def obter_cursor_seguro():
    """Garante que o cursor funcione mesmo se a conexão oscilar."""
    global conexao_global
    try:
        # Testa se a conexão ainda está viva
        conexao_global.isolation_level
    except (psycopg2.OperationalError, AttributeError):
        # Se caiu, refaz na hora
        conexao_global = psycopg2.connect(URL_BANCO, cursor_factory=DictCursor)
        conexao_global.autocommit = True
    return conexao_global.cursor()

def usuario_autenticado():
    return 'usuario_id' in session

@app.route('/')
def rota_login():
    if usuario_autenticado():
        return redirect(url_for('painel_saldos'))
    return render_template('login.html')

@app.route('/autenticar', methods=['POST'])
def autenticar():
    login = request.form.get('login')
    cursor = obter_cursor_seguro()
    cursor.execute("SELECT * FROM usuarios WHERE login = %s", (login,))
    usuario = cursor.fetchone()
    cursor.close()
    
    if usuario and login == "antonio_mercado":
        session['usuario_id'] = usuario['id_usuario']
        session['usuario_login'] = usuario['login']
        return redirect(url_for('painel_saldos'))
    flash("Usuário ou senha inválidos.", "erro")
    return redirect(url_for('rota_login'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('rota_login'))

@app.route('/painel')
def painel_saldos():
    if not usuario_autenticado():
        return redirect(url_for('rota_login'))
    cursor = obter_cursor_seguro()
    cursor.execute("SELECT * FROM clientes ORDER BY nome ASC")
    lista_clientes = cursor.fetchall()
    cursor.close()
    return render_template('painel.html', clientes=lista_clientes)

@app.route('/cadastrar_cliente', methods=['GET'])
def tela_cadastro_cliente():
    if not usuario_autenticado():
        return redirect(url_for('rota_login'))
    return render_template('cadastro_cliente.html')

@app.route('/salvar_cliente', methods=['POST'])
def salvar_cliente():
    if not usuario_autenticado():
        return redirect(url_for('rota_login'))
    nome = request.form.get('nome', '').strip()
    telefone = request.form.get('telefone', '').strip()
    try:
        limite = float(request.form.get('limite_credito', 0))
    except ValueError:
        flash("Limite de crédito inválido.", "erro")
        return redirect(url_for('tela_cadastro_cliente'))

    cursor = obter_cursor_seguro()
    try:
        cursor.execute("INSERT INTO clientes (nome, telefone, limite_credito, saldo_devedor) VALUES (%s, %s, %s, 0.00)", (nome, telefone, limite))
        flash(f"Cliente {nome} cadastrado com sucesso!", "sucesso")
        return redirect(url_for('painel_saldos'))
    except Exception:
        flash("Erro: Telefone já cadastrado.", "erro")
        return redirect(url_for('tela_cadastro_cliente'))
    finally:
        cursor.close()

@app.route('/transacao/<int:id_cliente>', methods=['GET'])
def tela_transacao(id_cliente):
    if not usuario_autenticado():
        return redirect(url_for('rota_login'))
    cursor = obter_cursor_seguro()
    cursor.execute("SELECT * FROM clientes WHERE id_cliente = %s", (id_cliente,))
    cliente = cursor.fetchone()
    cursor.close()
    return render_template('transacao.html', cliente=cliente)

@app.route('/processar_transacao/<int:id_cliente>', methods=['POST'])
def processar_transacao(id_cliente):
    if not usuario_autenticado():
        return redirect(url_for('rota_login'))
    tipo = request.form.get('tipo_transacao')
    descricao = request.form.get('descricao', '')
    try:
        valor = float(request.form.get('valor', 0))
    except ValueError:
        flash("Valor inválido.", "erro")
        return redirect(url_for('tela_transacao', id_cliente=id_cliente))

    cursor = obter_cursor_seguro()
    cursor.execute("SELECT * FROM clientes WHERE id_cliente = %s", (id_cliente,))
    cliente = cursor.fetchone()

    if tipo == 'DEBITO':
        novo_saldo = float(cliente['saldo_devedor']) + valor
        if novo_saldo > float(cliente['limite_credito']):
            cursor.close()
            flash(f"Operação Bloqueada: Limite excedido!", "bloqueio")
            return redirect(url_for('tela_transacao', id_cliente=id_cliente))
        cursor.execute("INSERT INTO lancamentos (id_cliente, tipo_transacao, valor, descricao) VALUES (%s, %s, %s, %s)", (id_cliente, 'DEBITO', valor, descricao))
        cursor.execute("UPDATE clientes SET saldo_devedor = %s WHERE id_cliente = %s", (novo_saldo, id_cliente))
    elif tipo == 'CREDITO':
        novo_saldo = max(0.0, float(cliente['saldo_devedor']) - valor)
        cursor.execute("INSERT INTO lancamentos (id_cliente, tipo_transacao, valor, descricao) VALUES (%s, %s, %s, %s)", (id_cliente, 'CREDITO', valor, descricao))
        cursor.execute("UPDATE clientes SET saldo_devedor = %s WHERE id_cliente = %s", (novo_saldo, id_cliente))
        
    cursor.close()
    flash("Transação registrada com sucesso!", "sucesso")
    return redirect(url_for('painel_saldos'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
