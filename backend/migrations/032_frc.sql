-- 032: FRC (Fatura de Recebimento de Consorcio) gerada pela dashboard (2026-10-09, decisoes do Leonardo).
--
-- Depois que cada consorciada emite a sua NFS-e contra o consorcio, a FRC (1 pagina) junta essas notas e vai
-- ao orgao com elas. Ate' aqui quem emitia era a controladoria; agora a dashboard gera, PADRAO e SEM
-- assinatura (o Leonardo assina no DocuSign por fora e anexa a assinada no envio, como `fatura`).
--
-- 1) medicao_documentos.leitura: a leitura do PDF de nota (JSON de leitura_nfse.ler) guardada no anexo. A
--    nota da consorciada nunca vira `notas_fiscais` (nao tem coligada no RM); a FRC precisa do bruto, INSS,
--    IRRF, ISS e liquido de cada uma, lidos do CONTEUDO do PDF.
-- 2) frc_consorcios: o cadastro da FRC por consorcio (prestador, tomador, descricao do servico, consorciadas)
--    e a ULTIMA FRC emitida antes do sistema. Vem do cadastro (`frc.yaml`) por `cadastro aplicar` (issue
--    #110): esta migracao so' cria a tabela. Ate' a #110 ela semeava os dois consorcios do formulario A com os
--    dados reais; quem ja' rodou a 032 (a producao) guarda essas linhas, e reaplicar nao as toca.
-- 3) frcs: uma FRC por medicao (linha de `medicoes`); "Gerar de novo" substitui a anterior (substituida_em).
--    A ultima registrada do consorcio = maior entre a semente e as FRCs vigentes.
ALTER TABLE medicao_documentos ADD COLUMN leitura TEXT;

CREATE TABLE IF NOT EXISTS frc_consorcios (
    consorcio TEXT PRIMARY KEY,                -- entidades.chave do consorcio
    formulario TEXT NOT NULL CHECK (formulario IN ('A')),
    ultimo_anterior INTEGER NOT NULL CHECK (ultimo_anterior >= 0),
    dados TEXT NOT NULL,                       -- JSON: prestador, tomador, descricao, consorciadas, logo
    atualizado_em TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS frcs (
    id INTEGER PRIMARY KEY,
    medicao_id INTEGER NOT NULL REFERENCES medicoes(id),
    consorcio TEXT NOT NULL REFERENCES frc_consorcios(consorcio),
    numero INTEGER NOT NULL CHECK (numero >= 1),
    data_geracao TEXT NOT NULL,
    bruto_centavos INTEGER NOT NULL,
    inss_centavos INTEGER NOT NULL,
    irrf_centavos INTEGER NOT NULL,
    iss_centavos INTEGER NOT NULL,
    liquido_centavos INTEGER NOT NULL,
    notas TEXT NOT NULL,                       -- JSON: as linhas de INFORMACOES COMPLEMENTARES
    pdf TEXT NOT NULL,                         -- relativo a pasta do banco: 'frc/<sha>.pdf'
    pdf_sha256 TEXT NOT NULL,
    xlsx TEXT NOT NULL,
    xlsx_sha256 TEXT NOT NULL,
    gerada_por INTEGER REFERENCES usuarios(id),
    gerada_em TEXT NOT NULL DEFAULT (datetime('now')),
    substituida_em TEXT
);
CREATE INDEX IF NOT EXISTS idx_frcs_medicao ON frcs (medicao_id);
