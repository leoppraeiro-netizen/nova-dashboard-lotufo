CREATE TABLE IF NOT EXISTS obras (
    id INTEGER PRIMARY KEY,
    nome TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS contratos (
    id INTEGER PRIMARY KEY,
    obra_id INTEGER REFERENCES obras(id),
    orgao TEXT NOT NULL,
    numero_instrumento TEXT NOT NULL,
    objeto TEXT NOT NULL,
    valor_original_centavos INTEGER NOT NULL CHECK (valor_original_centavos >= 0),
    data_base TEXT,
    indice_reajuste TEXT,
    vigencia_inicio TEXT,
    vigencia_fim TEXT,
    execucao_inicio TEXT,
    execucao_fim TEXT,
    numero_processo TEXT,
    pasta_sharepoint TEXT,
    estado TEXT NOT NULL DEFAULT 'ativo'
        CHECK (estado IN ('ativo','suspenso','encerrado','rescindido')),
    criado_em TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS contrato_eventos (
    id INTEGER PRIMARY KEY,
    contrato_id INTEGER NOT NULL REFERENCES contratos(id),
    tipo TEXT NOT NULL CHECK (tipo IN ('suspensao','retomada','encerramento','rescisao')),
    data TEXT NOT NULL,
    observacao TEXT,
    criado_em TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS aditivos (
    id INTEGER PRIMARY KEY,
    contrato_id INTEGER NOT NULL REFERENCES contratos(id),
    tipo TEXT NOT NULL CHECK (tipo IN ('prazo','valor','escopo','misto')),
    delta_valor_centavos INTEGER NOT NULL DEFAULT 0,
    nova_vigencia_fim TEXT,
    nova_execucao_fim TEXT,
    status TEXT NOT NULL DEFAULT 'em_andamento'
        CHECK (status IN ('em_andamento','assinado')),
    data_assinatura TEXT,
    criado_em TEXT NOT NULL DEFAULT (datetime('now'))
);
