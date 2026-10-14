-- 020: espelho de NF (bloco 2). Reconstroi `medicoes` e `medicao_documentos` UMA vez para os CHECKs
-- aceitarem os valores novos (estados espelho_gerado/espelho_enviado/nota_emitida, origem 'espelho',
-- tipo_doc 'espelho'/'evidencia_orgao'). Receita oficial do SQLite (lang_altertable, "Making Other
-- Kinds Of Table Schema Changes"): criar nova, copiar, apagar a antiga, renomear. foreign_keys OFF
-- so' durante o script: as filhas (medicao_protocolos, nf_alocacoes, mensagens_observadas,
-- medicao_documentos) referenciam `medicoes` pelo NOME e voltam a valer quando a nova assume o nome.
-- O runner (db.migrate) religa foreign_keys mesmo se o script falhar no meio.
--
-- Reexecutavel: as `_nova` sao apagadas antes de recriar (residuo de execucao interrompida nao
-- impede a proxima), e as colunas novas de medicao_documentos entram ANTES da copia, por ALTER
-- (que o runner pula quando ja' existem), para a copia listar as mesmas colunas na 1a e na 2a vez.
PRAGMA foreign_keys=OFF;

DROP TABLE IF EXISTS medicoes_nova;
CREATE TABLE medicoes_nova (
    id INTEGER PRIMARY KEY,
    contrato_id INTEGER NOT NULL REFERENCES contratos(id),
    numero INTEGER NOT NULL CHECK (numero >= 1),
    tipo TEXT NOT NULL CHECK (tipo IN ('execucao','projeto','reajuste')),
    competencia TEXT NOT NULL CHECK (competencia GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]'),
    estado TEXT NOT NULL DEFAULT 'prevista'
        CHECK (estado IN ('prevista','espelho_gerado','espelho_enviado','nota_emitida',
                          'protocolada','nf_emitida','recebida','cancelada','desistida')),
    valor_protocolado_centavos INTEGER CHECK (valor_protocolado_centavos >= 0),
    valor_protocolado_origem TEXT CHECK (valor_protocolado_origem IN ('detectado','aceito','manual','espelho')),
    valor_atestado_centavos INTEGER CHECK (valor_atestado_centavos >= 0),
    valor_atestado_origem TEXT CHECK (valor_atestado_origem IN ('detectado','aceito','manual')),
    motivo_represamento TEXT,
    congelada INTEGER NOT NULL DEFAULT 0,
    criado_em TEXT NOT NULL DEFAULT (datetime('now')),
    atestado_em TEXT,
    nf_emitida_em TEXT,
    recebida_em TEXT,
    espelho_em TEXT,
    espelho_origem TEXT CHECK (espelho_origem IN ('detectado','aceito','manual')),
    UNIQUE (contrato_id, numero, tipo)
);
INSERT INTO medicoes_nova (id, contrato_id, numero, tipo, competencia, estado, valor_protocolado_centavos,
    valor_protocolado_origem, valor_atestado_centavos, valor_atestado_origem, motivo_represamento,
    congelada, criado_em, atestado_em, nf_emitida_em, recebida_em, espelho_em, espelho_origem)
  SELECT id, contrato_id, numero, tipo, competencia, estado, valor_protocolado_centavos,
    valor_protocolado_origem, valor_atestado_centavos, valor_atestado_origem, motivo_represamento,
    congelada, criado_em, atestado_em, nf_emitida_em, recebida_em, espelho_em, espelho_origem
  FROM medicoes;
DROP TABLE medicoes;
ALTER TABLE medicoes_nova RENAME TO medicoes;

-- Espelho: uma linha por (contrato, numero, versao). Cobre execucao + reajuste + projeto do mesmo
-- numero; as saidas (uma por nota) ficam em JSON, os arquivos em medicao_documentos.
CREATE TABLE IF NOT EXISTS espelhos (
    id INTEGER PRIMARY KEY,
    contrato_id INTEGER NOT NULL REFERENCES contratos(id),
    numero INTEGER NOT NULL,
    competencia TEXT NOT NULL,
    versao INTEGER NOT NULL,
    situacao TEXT NOT NULL CHECK (situacao IN ('vigente','substituido')),
    entradas TEXT NOT NULL,            -- JSON {chave: centavos}
    saidas TEXT NOT NULL,              -- JSON [espelho.Saida]
    regra_sha256 TEXT NOT NULL,
    criado_por INTEGER NOT NULL REFERENCES usuarios(id),
    criado_em TEXT NOT NULL DEFAULT (datetime('now')),
    substituido_em TEXT,
    motivo TEXT,
    envio_id INTEGER REFERENCES envios(id),
    UNIQUE (contrato_id, numero, versao)
);
CREATE TABLE IF NOT EXISTS espelho_medicoes (
    espelho_id INTEGER NOT NULL REFERENCES espelhos(id),
    medicao_id INTEGER NOT NULL REFERENCES medicoes(id),
    PRIMARY KEY (espelho_id, medicao_id)
);
CREATE TABLE IF NOT EXISTS envio_medicoes (
    envio_id INTEGER NOT NULL REFERENCES envios(id),
    medicao_id INTEGER NOT NULL REFERENCES medicoes(id),
    PRIMARY KEY (envio_id, medicao_id)
);

-- medicao_documentos passa a aceitar arquivo LOCAL (espelho gerado, evidencia do orgao), com hash.
-- Colunas novas primeiro (ALTER, pulado pelo runner quando ja' existem), depois a reconstrucao
-- pelo CHECK de tipo_doc copiando TODAS as colunas -- assim a reexecucao nao perde nada.
ALTER TABLE medicao_documentos ADD COLUMN arquivo TEXT;
ALTER TABLE medicao_documentos ADD COLUMN sha256 TEXT;
ALTER TABLE medicao_documentos ADD COLUMN tamanho INTEGER;
ALTER TABLE medicao_documentos ADD COLUMN espelho_id INTEGER REFERENCES espelhos(id);
ALTER TABLE medicao_documentos ADD COLUMN saida TEXT;
DROP TABLE IF EXISTS medicao_documentos_nova;
CREATE TABLE medicao_documentos_nova (
    id INTEGER PRIMARY KEY,
    medicao_id INTEGER NOT NULL REFERENCES medicoes(id),
    fonte TEXT NOT NULL,               -- 'engenharia_sp' | 'controladoria_sp' | 'sistema' | 'operacao'
    tipo_doc TEXT NOT NULL CHECK (tipo_doc IN ('nf','nfs','fatura','espelho','evidencia_orgao')),
    nome TEXT NOT NULL,
    numero_nf TEXT,
    consorciada TEXT,
    municipio TEXT,
    item_id TEXT NOT NULL,
    weblink TEXT,
    criado_em TEXT NOT NULL DEFAULT (datetime('now')),
    arquivo TEXT,                      -- relativo a pasta do banco: 'espelhos/<sha>.docx'
    sha256 TEXT,
    tamanho INTEGER,
    espelho_id INTEGER REFERENCES espelhos(id),
    saida TEXT,                        -- chave da saida da regra
    UNIQUE (medicao_id, item_id)
);
INSERT INTO medicao_documentos_nova (id, medicao_id, fonte, tipo_doc, nome, numero_nf, consorciada,
    municipio, item_id, weblink, criado_em, arquivo, sha256, tamanho, espelho_id, saida)
  SELECT id, medicao_id, fonte, tipo_doc, nome, numero_nf, consorciada, municipio, item_id, weblink,
    criado_em, arquivo, sha256, tamanho, espelho_id, saida
  FROM medicao_documentos;
DROP TABLE medicao_documentos;
ALTER TABLE medicao_documentos_nova RENAME TO medicao_documentos;
CREATE INDEX IF NOT EXISTS idx_medicao_documentos_medicao ON medicao_documentos (medicao_id);

-- Cadastro geral (geral.yaml) e regra fiscal por obra (espelho/<slug>.yaml), gravados por
-- `cadastro aplicar`. `modelos` = JSON {chave_saida: {arquivo: 'modelos/<sha>.docx', sha256}}.
CREATE TABLE IF NOT EXISTS cadastro_geral (
    chave TEXT PRIMARY KEY,
    valor TEXT NOT NULL,
    atualizado_em TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS espelho_regras (
    contrato_id INTEGER PRIMARY KEY REFERENCES contratos(id),
    situacao TEXT NOT NULL CHECK (situacao IN ('prova','ativa')),
    regra TEXT NOT NULL,
    modelos TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    atualizado_em TEXT NOT NULL DEFAULT (datetime('now'))
);
ALTER TABLE entidades ADD COLUMN emails_faturamento TEXT;

PRAGMA foreign_keys=ON;
