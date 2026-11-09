PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS usuarios (
    id_usuario INTEGER PRIMARY KEY AUTOINCREMENT,
    login TEXT NOT NULL UNIQUE,
    senha TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS clientes (
    id_cliente INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    telefone TEXT NOT NULL UNIQUE,
    limite_credito DECIMAL(10, 2) NOT NULL,
    saldo_devedor DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
    data_cadastro DATETIME DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_limite_positivo CHECK (limite_credito >= 0.00)
);

CREATE TABLE IF NOT EXISTS lancamentos (
    id_lancamento INTEGER PRIMARY KEY AUTOINCREMENT,
    id_cliente INTEGER NOT NULL,
    tipo_transacao TEXT NOT NULL,
    valor DECIMAL(10, 2) NOT NULL,
    descricao TEXT,
    data_hora DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (id_cliente) REFERENCES clientes (id_cliente) ON DELETE RESTRICT,
    CONSTRAINT chk_valor_maior_zero CHECK (valor > 0.00),
    CONSTRAINT chk_tipo_transacao CHECK (tipo_transacao IN ('DEBITO', 'CREDITO'))
);

CREATE INDEX IF NOT EXISTS idx_lancamentos_cliente ON lancamentos(id_cliente);

INSERT INTO usuarios (login, senha) VALUES ('antonio_mercado', '123456');

INSERT INTO clientes (nome, telefone, limite_credito, saldo_devedor) VALUES 
('João Silva', '(85) 99999-1111', 200.00, 180.00),
('Maria Souza', '(85) 99999-2222', 150.00, 45.50),
('Pedro Alves', '(85) 99999-3333', 300.00, 0.00);

INSERT INTO lancamentos (id_cliente, tipo_transacao, valor, descricao) VALUES 
(1, 'DEBITO', 180.00, 'Compras do mês de Outubro'),
(2, 'DEBITO', 100.00, 'Feira semanal'),
(2, 'CREDITO', 54.50, 'Pagamento parcial em dinheiro');
