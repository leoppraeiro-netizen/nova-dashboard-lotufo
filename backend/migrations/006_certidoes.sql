-- Certidoes e as entidades juridicas que as portam (spec §5).
--
-- Uma entidade e' cada CNPJ do grupo: a Lotufo, cada consorcio de que ela participa e
-- cada consorciada. Habilitacao e' verificada POR CNPJ -- consorcio tem certidao propria,
-- e a consorciada tambem -- entao certidao pendura na entidade, nao na empresa "matriz".
--
-- `certidoes` e' APPEND-ONLY por convencao da aplicacao: renovar emite linha NOVA, nunca
-- UPDATE na anterior. E' o que permite responder "qual certidao valia no dia do protocolo X"
-- (a pergunta que o orgao faz quando glosa) meses depois do vencimento.
--
-- `estado` NAO tem 'vencida': vencimento e' DERIVADO da comparacao validade < hoje, e
-- gravar um estado derivado exigiria um job diario para manter a coluna honesta -- se ele
-- falhar, o painel mente. So entra aqui o que um humano DECIDE: revogada (o orgao cassou)
-- e nao_se_aplica (a entidade nao esta sujeita aquele tributo).
CREATE TABLE IF NOT EXISTS entidades (
    id INTEGER PRIMARY KEY,
    nome TEXT NOT NULL,
    cnpj TEXT NOT NULL UNIQUE CHECK (length(cnpj) = 14),
    papel TEXT NOT NULL CHECK (papel IN ('lotufo','consorcio','consorciada')),
    ativo INTEGER NOT NULL DEFAULT 1,
    criado_em TEXT NOT NULL DEFAULT (datetime('now'))
);
-- CNPJ ficticio (o do cadastro-exemplo, issue #110): o real entra pelo `cadastro aplicar`, que reivindica esta
-- linha (cadastro_aplicar._entidades). Bancos que ja' rodaram a 006 guardam o que tinham.
INSERT OR IGNORE INTO entidades (id, nome, cnpj, papel)
VALUES (1, 'Lotufo Engenharia e Construções Ltda', '31200101000130', 'lotufo');

CREATE TABLE IF NOT EXISTS certidao_tipos (
    id INTEGER PRIMARY KEY,
    nome TEXT NOT NULL,
    jurisdicao TEXT NOT NULL CHECK (jurisdicao IN ('federal','estadual','municipal','trabalhista')),
    emissor TEXT NOT NULL,
    aplicavel_por_padrao INTEGER NOT NULL DEFAULT 1,
    UNIQUE (nome, jurisdicao)
);
INSERT OR IGNORE INTO certidao_tipos (id, nome, jurisdicao, emissor, aplicavel_por_padrao) VALUES
 (1, 'CND Federal (RFB/PGFN)', 'federal', 'Receita Federal / PGFN', 1),
 (2, 'CRF/FGTS', 'federal', 'Caixa Econômica Federal', 1),
 (3, 'CNDT', 'trabalhista', 'TST', 1);

CREATE TABLE IF NOT EXISTS certidoes (
    id INTEGER PRIMARY KEY,
    entidade_id INTEGER NOT NULL REFERENCES entidades(id),
    tipo_id INTEGER NOT NULL REFERENCES certidao_tipos(id),
    numero TEXT,
    emissao TEXT NOT NULL,
    validade TEXT NOT NULL,
    arquivo TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    origem TEXT NOT NULL CHECK (origem IN ('robo','upload')),
    estado TEXT NOT NULL DEFAULT 'vigente' CHECK (estado IN ('vigente','revogada','nao_se_aplica')),
    observacao TEXT,
    criado_em TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_certidoes_ent_tipo ON certidoes (entidade_id, tipo_id, emissao);
