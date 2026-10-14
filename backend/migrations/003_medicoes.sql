CREATE TABLE IF NOT EXISTS medicoes (
    id INTEGER PRIMARY KEY,
    contrato_id INTEGER NOT NULL REFERENCES contratos(id),
    numero INTEGER NOT NULL CHECK (numero >= 1),
    tipo TEXT NOT NULL CHECK (tipo IN ('execucao','projeto','reajuste')),
    competencia TEXT NOT NULL CHECK (competencia GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]'),
    estado TEXT NOT NULL DEFAULT 'prevista'
        CHECK (estado IN ('prevista','protocolada','nf_emitida','recebida','cancelada','desistida')),
    valor_protocolado_centavos INTEGER CHECK (valor_protocolado_centavos >= 0),
    valor_protocolado_origem TEXT CHECK (valor_protocolado_origem IN ('detectado','aceito','manual')),
    valor_atestado_centavos INTEGER CHECK (valor_atestado_centavos >= 0),
    valor_atestado_origem TEXT CHECK (valor_atestado_origem IN ('detectado','aceito','manual')),
    motivo_represamento TEXT,
    congelada INTEGER NOT NULL DEFAULT 0,
    criado_em TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (contrato_id, numero, tipo)
);

CREATE TABLE IF NOT EXISTS medicao_protocolos (
    id INTEGER PRIMARY KEY,
    medicao_id INTEGER NOT NULL REFERENCES medicoes(id),
    data TEXT NOT NULL,
    numero_oficio TEXT,
    numero_processo TEXT,
    origem TEXT NOT NULL CHECK (origem IN ('detectado','aceito','manual')),
    criado_em TEXT NOT NULL DEFAULT (datetime('now'))
);
