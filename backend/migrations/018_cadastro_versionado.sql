-- Cadastro versionado (spec 2026-09-21 §8 e §12). O cadastro de obras deixa de ter tela:
-- vem de arquivos YAML no repositorio, aplicados por `python -m app.cli cadastro aplicar`.
-- Tudo aqui e' ADITIVO: nenhuma tabela existente e' reconstruida.
--
-- "Em encerramento" e' a coluna encerramento_iniciado_em (estado continua 'ativo'): trocar
-- o CHECK de contratos.estado exigiria reconstruir a tabela que o banco inteiro referencia.
-- Aditivos de valor e de prazo continuam em `aditivos` (contratos.vigente depende dela); os
-- demais instrumentos vao para `instrumentos`.

CREATE TABLE IF NOT EXISTS orgaos (
    id INTEGER PRIMARY KEY,
    chave TEXT NOT NULL UNIQUE,
    nome TEXT NOT NULL,
    familia TEXT NOT NULL CHECK (familia IN ('mtpar','sinfra','ses','prefeitura')),
    regras TEXT NOT NULL,
    criado_em TEXT NOT NULL DEFAULT (datetime('now'))
);

ALTER TABLE entidades ADD COLUMN chave TEXT;
ALTER TABLE entidades ADD COLUMN sigla_oficio TEXT;

ALTER TABLE contratos ADD COLUMN nome_curto TEXT;
ALTER TABLE contratos ADD COLUMN orgao_id INTEGER REFERENCES orgaos(id);
ALTER TABLE contratos ADD COLUMN lei TEXT;
ALTER TABLE contratos ADD COLUMN municipio TEXT;
ALTER TABLE contratos ADD COLUMN cno TEXT;
ALTER TABLE contratos ADD COLUMN art TEXT;
ALTER TABLE contratos ADD COLUMN sem_reajuste INTEGER NOT NULL DEFAULT 0;
ALTER TABLE contratos ADD COLUMN encerramento_iniciado_em TEXT;
ALTER TABLE contratos ADD COLUMN destinatarios_extras TEXT;
CREATE UNIQUE INDEX IF NOT EXISTS contratos_nome_curto
    ON contratos(nome_curto) WHERE nome_curto IS NOT NULL;

CREATE TABLE IF NOT EXISTS contrato_datas_base (
    id INTEGER PRIMARY KEY,
    contrato_id INTEGER NOT NULL REFERENCES contratos(id),
    mes TEXT NOT NULL CHECK (mes GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]'),
    indice TEXT NOT NULL DEFAULT '',
    UNIQUE (contrato_id, mes)
);

CREATE TABLE IF NOT EXISTS contrato_fiscais (
    id INTEGER PRIMARY KEY,
    contrato_id INTEGER NOT NULL REFERENCES contratos(id),
    nome TEXT NOT NULL DEFAULT '',
    email TEXT NOT NULL,
    desde TEXT NOT NULL,
    UNIQUE (contrato_id, email, desde)
);

ALTER TABLE aditivos ADD COLUMN chave_cadastro TEXT;
ALTER TABLE aditivos ADD COLUMN forma TEXT;
CREATE UNIQUE INDEX IF NOT EXISTS aditivos_chave_cadastro
    ON aditivos(contrato_id, chave_cadastro) WHERE chave_cadastro IS NOT NULL;
-- O aditivo agregado da carga do legado (carga_legado.py) passa a ter chave, para o
-- cadastro reconhece-lo em vez de duplica-lo.
UPDATE aditivos SET chave_cadastro = 'carga-legado', forma = 'termo_aditivo'
 WHERE chave_cadastro IS NULL AND status = 'assinado' AND objeto LIKE 'Carga inicial:%';

CREATE TABLE IF NOT EXISTS instrumentos (
    id INTEGER PRIMARY KEY,
    contrato_id INTEGER NOT NULL REFERENCES contratos(id),
    chave TEXT NOT NULL,
    tipo TEXT NOT NULL CHECK (tipo IN ('apostilamento_reajuste','paralisacao','reinicio',
                                       'marco_encerramento','endosso_garantia')),
    numero TEXT,
    data TEXT NOT NULL,
    dados TEXT NOT NULL,
    pdf TEXT,
    criado_em TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (contrato_id, chave)
);

CREATE TABLE IF NOT EXISTS cadastro_aplicacoes (
    id INTEGER PRIMARY KEY,
    commit_hash TEXT,
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id),
    aplicado_em TEXT NOT NULL DEFAULT (datetime('now')),
    resumo TEXT NOT NULL
);
