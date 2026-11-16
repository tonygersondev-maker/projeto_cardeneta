import pytest
from unittest.mock import MagicMock, patch
import psycopg2

mock_conn = MagicMock()
mock_cursor = MagicMock()
mock_conn.cursor.return_value = mock_cursor

def fake_fetchone():
    return {
        'id_usuario': 1, 'login': 'antonio_mercado',
        'id_cliente': 1, 'nome': 'João Silva',
        'saldo_devedor': 180.00, 'limite_credito': 200.00
    }

def fake_fetchall():
    return [{'id_cliente': 1, 'nome': 'João Silva', 'saldo_devedor': 180.00}]

mock_cursor.fetchone.side_effect = fake_fetchone
mock_cursor.fetchall.side_effect = fake_fetchall

with patch('psycopg2.connect', return_value=mock_conn):
    from app import app

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_tela_login_abre(client):
    resposta = client.get('/')
    assert resposta.status_code == 200
    assert b"CadernetaDigital" in resposta.data

def test_login_invalido(client):
    resposta = client.post('/autenticar', data={'login': 'errado'}, follow_redirects=True)
    assert resposta.status_code == 200

def test_login_valido_e_painel(client):
    resposta = client.post('/autenticar', data={'login': 'antonio_mercado'}, follow_redirects=True)
    assert resposta.status_code == 200
    assert "Clientes da Vizinhança".encode("utf-8") in resposta.data

def test_bloqueio_acesso_sem_login(client):
    resposta = client.get('/painel')
    assert resposta.status_code == 302

def test_fluxo_cadastro_cliente(client):
    with client.session_transaction() as sess:
        sess['usuario_id'] = 1
    assert client.get('/cadastrar_cliente').status_code == 200
    res_post = client.post('/salvar_cliente', data={
        'nome': 'Teste Pytest', 'telefone': '(85) 90000-0000', 'limite_credito': '100.00'
    }, follow_redirects=True)
    assert res_post.status_code == 200

def test_fluxo_bloqueio_limite(client):
    with client.session_transaction() as sess:
        sess['usuario_id'] = 1
    assert client.get('/transacao/1').status_code == 200
    resposta = client.post('/processar_transacao/1', data={
        'tipo_transacao': 'DEBITO', 'valor': '500.00', 'descricao': 'Teste'
    }, follow_redirects=True)
    assert resposta.status_code == 200

def test_fluxo_pagamento_e_logout(client):
    with client.session_transaction() as sess:
        sess['usuario_id'] = 1
    resposta = client.post('/processar_transacao/2', data={
        'tipo_transacao': 'CREDITO', 'valor': '5.00', 'descricao': 'Abate'
    }, follow_redirects=True)
    assert resposta.status_code == 200
    assert client.get('/logout').status_code == 302
