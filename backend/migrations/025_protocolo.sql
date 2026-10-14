-- 025: protocolo de medicao feito pelo sistema (bloco 5; spec 2026-09-21 §3 passos 4 a 7, §5.3, §5.4, §6).
-- Um protocolo = um documento a assinar = um oficio. Um envio (e-mail) pode levar varios protocolos
-- (SINFRA: execucao e reajuste no mesmo e-mail, em PDFs separados). Aditiva: nada reconstruido.
CREATE TABLE IF NOT EXISTS protocolos (
    id INTEGER PRIMARY KEY,
    contrato_id INTEGER NOT NULL REFERENCES contratos(id),
    etapa TEXT NOT NULL CHECK (etapa IN ('unico','medicao','nota')),
    natureza TEXT NOT NULL CHECK (natureza IN ('execucao','reajuste','projeto')),
    numero_oficio TEXT,
    corpo_carta TEXT,
    montado_arquivo TEXT,
    montado_sha256 TEXT,
    montado_paginas INTEGER,
    montado_em TEXT,
    assinado_arquivo TEXT,
    assinado_sha256 TEXT,
    assinado_em TEXT,
    conferencia TEXT,
    envio_id INTEGER REFERENCES envios(id),
    justificativa TEXT,
    numero_orgao TEXT,
    comprovante_arquivo TEXT,
    situacao TEXT NOT NULL DEFAULT 'rascunho'
        CHECK (situacao IN ('rascunho','montado','assinado','enviado','descartado')),
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id),
    criado_em TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS protocolos_contrato ON protocolos(contrato_id);

CREATE TABLE IF NOT EXISTS protocolo_medicoes (
    protocolo_id INTEGER NOT NULL REFERENCES protocolos(id),
    medicao_id INTEGER NOT NULL REFERENCES medicoes(id),
    PRIMARY KEY (protocolo_id, medicao_id)
);

-- Pecas tecnicas arrastadas (boletim, planilha editavel, diario, fotos...). Removida e' marcada.
CREATE TABLE IF NOT EXISTS protocolo_pecas (
    id INTEGER PRIMARY KEY,
    protocolo_id INTEGER NOT NULL REFERENCES protocolos(id),
    tipo TEXT NOT NULL,
    nome TEXT NOT NULL,
    arquivo TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    tamanho INTEGER NOT NULL,
    ext TEXT NOT NULL CHECK (ext IN ('pdf','xlsx')),
    removida_em TEXT,
    criado_em TEXT NOT NULL DEFAULT (datetime('now'))
);

ALTER TABLE medicao_protocolos ADD COLUMN protocolo_id INTEGER REFERENCES protocolos(id);
ALTER TABLE contratos ADD COLUMN objeto_completo TEXT;
ALTER TABLE contratos ADD COLUMN cno_arquivo TEXT;
ALTER TABLE contrato_fiscais ADD COLUMN cargo TEXT;
ALTER TABLE contrato_fiscais ADD COLUMN tratamento TEXT;
ALTER TABLE contrato_fiscais ADD COLUMN portaria TEXT;
