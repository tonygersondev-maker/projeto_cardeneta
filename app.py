import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, flash, session

app = Flask(__name__)
app.secret_key = "chave_secreta_ficticia_para_o_mvp_ead"
DATABASE = 'caderneta.db'

def obter_conexao_banco():
    """Abre a conexão e ativa o Modo WAL para máxima velocidade na nuvem."""
    conexao = sqlite3.connect(DATABASE)
    conexao.row_factory = sqlite3.Row
    
    # OTIMIZAÇÕES DE DESEMPENHO (RNF03):
    conexao.execute("PRAGMA foreign_keys = ON;")
    conexao.execute("PRAGMA journal_mode = WAL;")  # Gravação veloz em memória RAM
    conexao.execute("PRAGMA synchronous = NORMAL;") # Evita travar o disco a cada clique
    return conexao

def inicializar_sistema():
    if not os.path.exists(DATABASE):
        try:
            conexao = obter_conexao_banco()
            with open('schema.sql', 'r', encoding='utf-8') as f:
                conexao.executescript(f.read())
            
            # Garante a criação de índices extras para acelerar as buscas no balcão
            conexao.execute("CREATE INDEX IF NOT EXISTS idx_clientes_nome ON clientes(nome);")
            conexao.execute("CREATE INDEX IF NOT EXISTS idx_lancamentos_cliente ON lancamentos(id_cliente);")
            
            conexao.commit()
            conexao.close()
            print("Banco de dados otimizado e inicializado com sucesso!")
        except Exception as e:
            print(f"Erro ao inicializar o banco: {e}")

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
    conexao = obter_conexao_banco()
    usuario = conexao.execute("SELECT * FROM usuarios WHERE login = ?", (login,)).fetchone()
    conexao.close()
    if usuario and login == "antonio_mercado":
        session['usuario_id'] = usuario['id_usuario']
        session['usuario_login'] = usuario['login']
        return redirect(url_for('painel_saldos'))
    flash("Usuário ou senha inválidos. Tente novamente.", "erro")
    return redirect(url_for('rota_login'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('rota_login'))

@app.route('/painel')
def painel_saldos():
    if not usuario_autenticado():
        return redirect(url_for('rota_login'))
    conexao = obter_conexao_banco()
    lista_clientes = conexao.execute("SELECT * FROM clientes ORDER BY nome ASC").fetchall()
    conexao.close()
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
    if not nome or not telefone:
        flash("Nome e Telefone são obrigatórios.", "erro")
        return redirect(url_for('tela_cadastro_cliente'))
    if limite < 0:
        flash("O limite não pode ser menor que zero.", "erro")
        return redirect(url_for('tela_cadastro_cliente'))

    conexao = obter_conexao_banco()
    try:
        conexao.execute("INSERT INTO clientes (nome, telefone, limite_credito, saldo_devedor) VALUES (?, ?, ?, 0.00)", (nome, telefone, limite))
        conexao.commit()
        flash(f"Cliente {nome} cadastrado com sucesso!", "sucesso")
        return redirect(url_for('painel_saldos'))
    except sqlite3.IntegrityError:
        flash("Erro: Telefone já cadastrado.", "erro")
        return redirect(url_for('tela_cadastro_cliente'))
    finally:
        conexao.close()

@app.route('/transacao/<int:id_cliente>', methods=['GET'])
def tela_transacao(id_cliente):
    if not usuario_autenticado():
        return redirect(url_for('rota_login'))
    conexao = obter_conexao_banco()
    cliente = conexao.execute("SELECT * FROM clientes WHERE id_cliente = ?", (id_cliente,)).fetchone()
    conexao.close()
    if not cliente:
        flash("Cliente não encontrado.", "erro")
        return redirect(url_for('painel_saldos'))
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
    if valor <= 0:
        flash("O valor deve ser maior que zero.", "erro")
        return redirect(url_for('tela_transacao', id_cliente=id_cliente))

    conexao = obter_conexao_banco()
    cliente = conexao.execute("SELECT * FROM clientes WHERE id_cliente = ?", (id_cliente,)).fetchone()
    if not cliente:
        conexao.close()
        flash("Cliente inválido.", "erro")
        return redirect(url_for('painel_saldos'))

    if tipo == 'DEBITO':
        novo_saldo = cliente['saldo_devedor'] + valor
        if novo_saldo > cliente['limite_credito']:
            conexao.close()
            flash(f"Operação Bloqueada: {cliente['nome']} excedeu o limite de crédito! (Limite: R$ {cliente['limite_credito']:.2f})", "bloqueio")
            return redirect(url_for('tela_transacao', id_cliente=id_cliente))
        conexao.execute("INSERT INTO lancamentos (id_cliente, tipo_transacao, valor, descricao) VALUES (?, ?, ?, ?)", (id_cliente, 'DEBITO', valor, descricao))
        conexao.execute("UPDATE clientes SET saldo_devedor = ? WHERE id_cliente = ?", (novo_saldo, id_cliente))
        flash(f"Compra de R$ {valor:.2f} registrada com sucesso.", "sucesso")
    elif tipo == 'CREDITO':
        novo_saldo = max(0.0, cliente['saldo_devedor'] - valor)
        conexao.execute("INSERT INTO lancamentos (id_cliente, tipo_transacao, valor, descricao) VALUES (?, ?, ?, ?)", (id_cliente, 'CREDITO', valor, descricao))
        conexao.execute("UPDATE clientes SET saldo_devedor = ? WHERE id_cliente = ?", (novo_saldo, id_cliente))
        flash(f"Pagamento de R$ {valor:.2f} recebido com sucesso.", "sucesso")
    conexao.commit()
    conexao.close()
    return redirect(url_for('painel_saldos'))

@app.errorhandler(500)
def erro_interno(e):
    return "Erro interno no servidor. Operação abortada por segurança.", 500

if __name__ == '__main__':
    inicializar_sistema()
    app.run(host='0.0.0.0', port=5000, debug=False)
