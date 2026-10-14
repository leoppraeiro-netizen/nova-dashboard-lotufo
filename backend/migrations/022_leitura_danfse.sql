-- 022: leitor da NFS-e ganha o leiaute DANFSe (emissor nacional, notas de Cuiaba a partir de 09/2026).
-- So' o CHECK de `notas_fiscais.leitura` muda ('danfse' passa a valer); SQLite nao altera CHECK sem
-- reconstruir a tabela, entao a receita e' a mesma da 021 (criar nova, copiar TODAS as colunas, apagar,
-- renomear, recriar os indices), reexecutavel. As filhas (baixas, nf_alocacoes) referenciam pelo NOME.
PRAGMA foreign_keys=OFF;

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
    leitura TEXT CHECK (leitura IS NULL OR leitura IN ('cuiaba','danfse','manual')),
    CHECK (idmov IS NOT NULL OR origem = 'pdf')
);
INSERT INTO notas_fiscais_nova (id, coligada, idmov, numero, numero_int, serie, emissao, valor_centavos, codtmv,
    status_rm, campo_livre1, tomador, situacao, primeiro_visto_em, ultimo_visto_em, centro_custo, origem,
    documento_id, prestador_cnpj, tomador_cnpj, competencia, municipio, natureza_lida, numero_medicao_lido,
    valor_pdf_centavos, iss_centavos, inss_centavos, irrf_centavos, ibs_centavos, cbs_centavos, liquido_centavos,
    confirmacao, confirmada_em, conferencia, justificativa, leitura)
  SELECT id, coligada, idmov, numero,
    numero_int,
    serie, emissao, valor_centavos, codtmv, status_rm, campo_livre1, tomador, situacao, primeiro_visto_em,
    ultimo_visto_em, centro_custo, origem, documento_id, prestador_cnpj, tomador_cnpj, competencia, municipio,
    natureza_lida, numero_medicao_lido, valor_pdf_centavos, iss_centavos, inss_centavos, irrf_centavos,
    ibs_centavos, cbs_centavos, liquido_centavos, confirmacao, confirmada_em, conferencia, justificativa, leitura
  FROM notas_fiscais;
DROP TABLE notas_fiscais;
ALTER TABLE notas_fiscais_nova RENAME TO notas_fiscais;
CREATE UNIQUE INDEX IF NOT EXISTS idx_nf_coligada_idmov ON notas_fiscais (coligada, idmov) WHERE idmov IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_nf_coligada_numero ON notas_fiscais (coligada, numero_int);

PRAGMA foreign_keys=ON;
