-- 024: documentos de protocolo (bloco 4, spec 2026-09-21 §9 e §12). ADITIVA: nenhuma tabela e'
-- reconstruida. Os tres tipos semeados na 006 ganham chave e link; os outros tres nascem com
-- aplicavel_por_padrao=0 porque, a partir deste bloco, quem diz o que e' exigido e' o cadastro do
-- orgao (documentos.exigidos); aplicavel_por_padrao so' vale para contrato sem orgao.
ALTER TABLE certidao_tipos ADD COLUMN chave TEXT;
ALTER TABLE certidao_tipos ADD COLUMN link_emissao TEXT;
UPDATE certidao_tipos SET chave='federal',
  link_emissao='https://servicos.receitafederal.gov.br/servico/certidoes/#/home/cnpj'
  WHERE id=1 AND nome='CND Federal (RFB/PGFN)';
UPDATE certidao_tipos SET chave='fgts',
  link_emissao='https://consulta-crf.caixa.gov.br/consultacrf/pages/consultaEmpregador.jsf'
  WHERE id=2 AND nome='CRF/FGTS';
UPDATE certidao_tipos SET chave='trabalhista',
  link_emissao='https://cndt-certidao.tst.jus.br/gerarCertidao.faces'
  WHERE id=3 AND nome='CNDT';
INSERT OR IGNORE INTO certidao_tipos (nome, jurisdicao, emissor, aplicavel_por_padrao, chave, link_emissao) VALUES
 ('Certidão Conjunta Estadual (SEFAZ/PGE-MT)', 'estadual', 'SEFAZ-MT / PGE-MT', 0, 'estadual',
  'https://www.sefaz.mt.gov.br/cnd/certidao/servlet/ServletRotdAberto?origem=60'),
 ('Certidão de Débitos Gerais (Prefeitura de Cuiabá)', 'municipal', 'Prefeitura de Cuiabá', 0, 'municipal',
  'https://portalfazenda.cuiaba.mt.gov.br/portalfazenda/PortalContribuinte/EmitirCertidao'),
 ('Certidão de Falência e Recuperação Judicial (TJMT)', 'estadual', 'TJMT', 0, 'falencia',
  'https://sec.tjmt.jus.br/');
CREATE UNIQUE INDEX IF NOT EXISTS certidao_tipos_chave ON certidao_tipos (chave) WHERE chave IS NOT NULL;

-- Natureza lida do documento; positiva pura nunca e' gravada (o leitor recusa). NULL = linha
-- anterior a este bloco. `leitura`: se os campos vieram do leitor ou da digitacao.
ALTER TABLE certidoes ADD COLUMN natureza TEXT CHECK (natureza IN ('negativa','positiva_efeito_negativa'));
ALTER TABLE certidoes ADD COLUMN leitura TEXT CHECK (leitura IN ('automatica','manual'));
ALTER TABLE certidoes ADD COLUMN nome_original TEXT;

-- Regularidade mensal do DP (folha, SEFIP/eSocial, INSS): um PDF por empresa e competencia,
-- append-only; vale a de maior competencia.
CREATE TABLE IF NOT EXISTS regularidades (
    id INTEGER PRIMARY KEY,
    entidade_id INTEGER NOT NULL REFERENCES entidades(id),
    competencia TEXT NOT NULL CHECK (competencia GLOB '[0-9][0-9][0-9][0-9]-[0-1][0-9]'
                                     AND substr(competencia, 6, 2) BETWEEN '01' AND '12'),
    arquivo TEXT NOT NULL,
    sha256 TEXT NOT NULL CHECK (length(sha256) = 64),
    tamanho INTEGER NOT NULL,
    nome_original TEXT,
    usuario_id INTEGER REFERENCES usuarios(id),
    criado_em TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_regularidades_ent ON regularidades (entidade_id, competencia);

-- Nome curto para arquivos (ZIP) e telas; composicao dos consorcios (as certidoes da obra de
-- consorcio sao as do consorcio E as de cada consorciada).
ALTER TABLE entidades ADD COLUMN nome_curto TEXT;
-- Consorcio com folha propria (Complexo Leblon: o pacote do DP da 25a e' a folha do CNPJ do
-- consorcio) manda a PROPRIA regularidade mensal; os demais contratos mandam a da Lotufo.
ALTER TABLE entidades ADD COLUMN regularidade_propria INTEGER NOT NULL DEFAULT 0;
CREATE TABLE IF NOT EXISTS entidade_consorciadas (
    consorcio_id INTEGER NOT NULL REFERENCES entidades(id),
    consorciada_id INTEGER NOT NULL REFERENCES entidades(id),
    PRIMARY KEY (consorcio_id, consorciada_id)
);

-- Excecao por contrato a lista de documentos do orgao (JSON {"medicao": [...], "reajuste": [...]}).
ALTER TABLE contratos ADD COLUMN documentos TEXT;
