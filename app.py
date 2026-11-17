import os
import psycopg2
from psycopg2.extras import DictCursor
from flask import Flask, render_template, request, redirect, url_for, flash, session

app = Flask(__name__)
app.secret_key = "chave_da_caderneta"

# link do banco do supabase
URL_BANCO = "postgresql://postgres:Pimenta%401945@db.pcfdbdwgvxcmwwejitqp.supabase.co:5432/postgres"

# conexao para usar no app todo
try:
    conexao_global = psycopg2.connect(URL_BANCO, cursor_factory=DictCursor)
    conexao_global.autocommit = True
except Exception as e:
    print(e)
    conexao_global = None

def pegar_cursor():
    global conexao_global
    try:
        conexao_global.isolation_level
    except:
        conexao_global = psycopg2.connect(URL_BANCO, cursor_factory=DictCursor)
        conexao_global.autocommit = True
    return conexao_global.cursor()

@app.route('/')
def rota_login():
    if 'usuario_id' in session:
        return redirect(url_for('painel_saldos'))
    return render_template('login.html')

@app.route('/autenticar', methods=['POST'])
def autenticar():
    login = request.form.get('login')
    cursor = pegar_cursor()
    cursor.execute("SELECT * FROM usuarios WHERE login = %s", (login,))
    usuario = cursor.fetchone()
    cursor.close()
    
    if usuario and login == "antonio_mercado":
        session['usuario_id'] = usuario['id_usuario']
        return redirect(url_for('painel_saldos'))
        
    flash("Usuario ou senha incorretos.", "erro")
    return redirect(url_for('rota_login'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('rota_login'))

@app.route('/painel')
def painel_saldos():
    if 'usuario_id' not in session:
        return redirect(url_for('rota_login'))
    cursor = pegar_cursor()
    cursor.execute("SELECT * FROM clientes ORDER BY nome ASC")
    dados = cursor.fetchall()
    cursor.close()
    return render_template('painel.html', clientes=dados)

@app.route('/cadastrar_cliente', methods=['GET'])
def tela_cadastro_cliente():
    if 'usuario_id' not in session:
        return redirect(url_for('rota_login'))
    return render_template('cadastro_cliente.html')

@app.route('/salvar_cliente', methods=['POST'])
def salvar_cliente():
    if 'usuario_id' not in session:
        return redirect(url_for('rota_login'))
        
    nome = request.form.get('nome')
    telefone = request.form.get('telefone')
    limite = float(request.form.get('limite_credito'))
    
    cursor = pegar_cursor()
    try:
        cursor.execute("INSERT INTO clientes (nome, telefone, limite_credito, saldo_devedor) VALUES (%s, %s, %s, 0)", (nome, telefone, limite))
        flash("Cliente cadastrado!", "sucesso")
        return redirect(url_for('painel_saldos'))
    except:
        flash("Esse telefone ja existe.", "erro")
        return redirect(url_for('tela_cadastro_cliente'))
    finally:
        cursor.close()

@app.route('/transacao/<int:id_cliente>', methods=['GET'])
def tela_transacao(id_cliente):
    if 'usuario_id' not in session:
        return redirect(url_for('rota_login'))
    cursor = pegar_cursor()
    cursor.execute("SELECT * FROM clientes WHERE id_cliente = %s", (id_cliente,))
    cli = cursor.fetchone()
    cursor.close()
    return render_template('transacao.html', cliente=cli)

@app.route('/processar_transacao/<int:id_cliente>', methods=['POST'])
def processar_transacao(id_cliente):
    if 'usuario_id' not in session:
        return redirect(url_for('rota_login'))
        
    tipo = request.form.get('tipo_transacao')
    valor = float(request.form.get('valor'))
    desc = request.form.get('descricao')
    
    cursor = pegar_cursor()
    cursor.execute("SELECT * FROM clientes WHERE id_cliente = %s", (id_cliente,))
    cli = cursor.fetchone()
    
    if tipo == 'DEBITO':
        conta_nova = float(cli['saldo_devedor']) + valor
        if conta_nova > float(cli['limite_credito']):
            cursor.close()
            flash("Operacao Bloqueada: Limite excedido!", "bloqueio")
            return redirect(url_for('tela_transacao', id_cliente=id_cliente))
            
        cursor.execute("INSERT INTO lancamentos (id_cliente, tipo_transacao, valor, descricao) VALUES (%s, %s, %s, %s)", (id_cliente, 'DEBITO', valor, desc))
        cursor.execute("UPDATE clientes SET saldo_devedor = %s WHERE id_cliente = %s", (conta_nova, id_cliente))
    else:
        conta_nova = max(0.0, float(cli['saldo_devedor']) - valor)
        cursor.execute("INSERT INTO lancamentos (id_cliente, tipo_transacao, valor, descricao) VALUES (%s, %s, %s, %s)", (id_cliente, 'CREDITO', valor, desc))
        cursor.execute("UPDATE clientes SET saldo_devedor = %s WHERE id_cliente = %s", (conta_nova, id_cliente))
        
    flash("Feito com sucesso!", "sucesso")
    cursor.close()
    return render_template('transacao.html', cliente=cli)

# revisao final do codigo para entrega 
