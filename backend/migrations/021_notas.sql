-- 021: nota fiscal que chega pelo PDF antes do RM (bloco 3, spec §7.1 e §12).
-- `notas_fiscais` e' reconstruida UMA vez (receita oficial do SQLite, como a 020) para `idmov`
-- aceitar NULL: a nota lida do PDF nasce sem movimento do RM e e' preenchida quando o RM a traz.
-- Unicidade (coligada, idmov) vira indice parcial; `numero_int` e' a chave de casamento PDF x RM
-- (o RM grava '000002260', o PDF diz 2260). As filhas (baixas, nf_alocacoes) referenciam
-- `notas_fiscais` pelo NOME e voltam a valer quando a nova assume o nome. Reexecutavel: os ALTER
-- sao aparados pelo runner quando ja' existem, e a copia lista as mesmas colunas na 1a e na 2a vez.
PRAGMA foreign_keys=OFF;

ALTER TABLE notas_fiscais ADD COLUMN numero_int INTEGER;
ALTER TABLE notas_fiscais ADD COLUMN origem TEXT NOT NULL DEFAULT 'rm';
ALTER TABLE notas_fiscais ADD COLUMN documento_id INTEGER;
ALTER TABLE notas_fiscais ADD COLUMN prestador_cnpj TEXT;
ALTER TABLE notas_fiscais ADD COLUMN tomador_cnpj TEXT;
ALTER TABLE notas_fiscais ADD COLUMN competencia TEXT;
ALTER TABLE notas_fiscais ADD COLUMN municipio TEXT;
ALTER TABLE notas_fiscais ADD COLUMN natureza_lida TEXT;
ALTER TABLE notas_fiscais ADD COLUMN numero_medicao_lido INTEGER;
ALTER TABLE notas_fiscais ADD COLUMN valor_pdf_centavos INTEGER;
ALTER TABLE notas_fiscais ADD COLUMN iss_centavos INTEGER;
ALTER TABLE notas_fiscais ADD COLUMN inss_centavos INTEGER;
ALTER TABLE notas_fiscais ADD COLUMN irrf_centavos INTEGER;
ALTER TABLE notas_fiscais ADD COLUMN ibs_centavos INTEGER;
ALTER TABLE notas_fiscais ADD COLUMN cbs_centavos INTEGER;
ALTER TABLE notas_fiscais ADD COLUMN liquido_centavos INTEGER;
ALTER TABLE notas_fiscais ADD COLUMN confirmacao TEXT NOT NULL DEFAULT 'so_rm';
ALTER TABLE notas_fiscais ADD COLUMN confirmada_em TEXT;
ALTER TABLE notas_fiscais ADD COLUMN conferencia TEXT;
ALTER TABLE notas_fiscais ADD COLUMN justificativa TEXT;
ALTER TABLE notas_fiscais ADD COLUMN leitura TEXT;

DROP TABLE IF EXISTS notas_fiscais_nova;
CREATE TABLE notas_fiscais_nova (
    id INTEGER PRIMARY KEY,
    coligada INTEGER NOT NULL,
    idmov INTEGER,                                   -- NULL = veio do PDF, RM ainda nao viu
    numero TEXT NOT NULL,
    numero_int INTEGER,
    serie TEXT,
    emissao TEXT,
    valor_centavos INTEGER NOT NULL CHECK (valor_centavos >= 0),   -- bruto: do RM quando ha', senao do PDF
    codtmv TEXT,
    status_rm TEXT,
    campo_livre1 TEXT,
    tomador TEXT,
    situacao TEXT NOT NULL DEFAULT 'ativa' CHECK (situacao IN ('ativa','cancelada','substituida')),
    primeiro_visto_em TEXT NOT NULL DEFAULT (datetime('now')),
    ultimo_visto_em TEXT NOT NULL DEFAULT (datetime('now')),
    centro_custo TEXT,
    origem TEXT NOT NULL DEFAULT 'rm' CHECK (origem IN ('rm','pdf')),
    documento_id INTEGER REFERENCES medicao_documentos(id),
    prestador_cnpj TEXT,
    tomador_cnpj TEXT,
    competencia TEXT,
    municipio TEXT,
    natureza_lida TEXT CHECK (natureza_lida IS NULL OR natureza_lida IN ('medicao','reajuste','projeto')),
    numero_medicao_lido INTEGER,
    valor_pdf_centavos INTEGER CHECK (valor_pdf_centavos IS NULL OR valor_pdf_centavos >= 0),
    iss_centavos INTEGER,
    inss_centavos INTEGER,
    irrf_centavos INTEGER,
    ibs_centavos INTEGER,
    cbs_centavos INTEGER,
    liquido_centavos INTEGER,
    confirmacao TEXT NOT NULL DEFAULT 'so_rm'
        CHECK (confirmacao IN ('so_rm','aguardando_rm','confirmada','divergente')),
    confirmada_em TEXT,
    conferencia TEXT,                                -- JSON [{campo, espelho, nota, grau}] ; NULL/'[]' = confere
    justificativa TEXT,
    leitura TEXT CHECK (leitura IS NULL OR leitura IN ('cuiaba','manual')),
    CHECK (idmov IS NOT NULL OR origem = 'pdf')
);
INSERT INTO notas_fiscais_nova (id, coligada, idmov, numero, numero_int, serie, emissao, valor_centavos, codtmv,
    status_rm, campo_livre1, tomador, situacao, primeiro_visto_em, ultimo_visto_em, centro_custo, origem,
    documento_id, prestador_cnpj, tomador_cnpj, competencia, municipio, natureza_lida, numero_medicao_lido,
    valor_pdf_centavos, iss_centavos, inss_centavos, irrf_centavos, ibs_centavos, cbs_centavos, liquido_centavos,
    confirmacao, confirmada_em, conferencia, justificativa, leitura)
  SELECT id, coligada, idmov, numero,
    CASE WHEN numero GLOB '*[^0-9]*' OR numero = '' THEN NULL ELSE CAST(numero AS INTEGER) END,
    serie, emissao, valor_centavos, codtmv, status_rm, campo_livre1, tomador, situacao, primeiro_visto_em,
    ultimo_visto_em, centro_custo, origem, documento_id, prestador_cnpj, tomador_cnpj, competencia, municipio,
    natureza_lida, numero_medicao_lido, valor_pdf_centavos, iss_centavos, inss_centavos, irrf_centavos,
    ibs_centavos, cbs_centavos, liquido_centavos, confirmacao, confirmada_em, conferencia, justificativa, leitura
  FROM notas_fiscais;
DROP TABLE notas_fiscais;
ALTER TABLE notas_fiscais_nova RENAME TO notas_fiscais;
CREATE UNIQUE INDEX IF NOT EXISTS idx_nf_coligada_idmov ON notas_fiscais (coligada, idmov) WHERE idmov IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_nf_coligada_numero ON notas_fiscais (coligada, numero_int);

ALTER TABLE medicoes ADD COLUMN nota_emitida_em TEXT;
ALTER TABLE orgaos ADD COLUMN cnpj TEXT;

PRAGMA foreign_keys=ON;
