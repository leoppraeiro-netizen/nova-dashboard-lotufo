-- 031: envio da nota ao contratante (plano 2026-10-09; mapeamento 2026-10-08 §6a). ADITIVA.
-- Estadual e municipal vao nos cinco de todo envio: passam a ser cobradas por padrao.
UPDATE certidao_tipos SET aplicavel_por_padrao=1 WHERE chave IN ('estadual','municipal');

-- Como a nota chegou ao orgao: 'sistema' (e-mail pela dashboard) ou 'externo' (registrado depois, com data
-- e observacao). NULL = protocolada antes desta pagina.
ALTER TABLE medicoes ADD COLUMN envio_origem TEXT CHECK (envio_origem IN ('sistema','externo'));
ALTER TABLE medicoes ADD COLUMN envio_externo_em TEXT;
ALTER TABLE medicoes ADD COLUMN envio_externo_obs TEXT;

-- Cobranca de certidao por e-mail: uma linha por certidao cobrada em cada rodada (`motivo` = rodada), para o
-- job nao repetir a mesma lista no mesmo intervalo.
CREATE TABLE IF NOT EXISTS cobranca_certidoes_envios (
    id INTEGER PRIMARY KEY,
    certidao_tipo INTEGER NOT NULL REFERENCES certidao_tipos(id),
    entidade_id INTEGER NOT NULL REFERENCES entidades(id),
    enviado_em TEXT NOT NULL DEFAULT (datetime('now')),
    motivo TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cobranca_certidoes_motivo ON cobranca_certidoes_envios (motivo);
