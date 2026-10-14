-- Documentos de faturamento por medição, vindos do SharePoint (2026-09-09).
--
-- Os consórcios (Oriundi, Via Parecis, Leblon, Integra BRT, BR-163) faturam FORA do RM:
-- a NF/NFS-e do consórcio vive no SharePoint (site da Engenharia, por obra/medição; o
-- BR-163 na Controladoria). O casador do RM nunca as vê (coligadas 13/17/18/20 sem NF
-- útil no espelho). Estas medições já entram `nf_emitida` pela carga do legado; o que
-- faltava era o VÍNCULO com o documento fiscal real.
--
-- Esta tabela é EVIDÊNCIA (espelho de arquivos de outro sistema, como notas_fiscais/
-- baixas da migração 012): NÃO entra na cadeia de auditoria, não muda estado nem valor
-- de medição, não modela recebimento (recebimento de consórcio fora do RM não é
-- automatizável). Uma medição pode ter VÁRIOS documentos (uma NF por consorciada
-- LOTUFO/RIVOLI e/ou por município CBA/VG, mais a FATURA/FRC do consórcio).
--
-- `item_id` é o id do driveItem no Graph: dá idempotência (reimportar não duplica) e é
-- estável entre rodadas. `fonte` diz de qual site veio; `tipo_doc` separa a nota fiscal
-- (nf/nfs) da fatura de consórcio (fatura/FRC).
CREATE TABLE IF NOT EXISTS medicao_documentos (
    id INTEGER PRIMARY KEY,
    medicao_id INTEGER NOT NULL REFERENCES medicoes(id),
    fonte TEXT NOT NULL,                 -- 'engenharia_sp' | 'controladoria_sp'
    tipo_doc TEXT NOT NULL CHECK (tipo_doc IN ('nf', 'nfs', 'fatura')),
    nome TEXT NOT NULL,
    numero_nf TEXT,
    consorciada TEXT,
    municipio TEXT,
    item_id TEXT NOT NULL,
    weblink TEXT,
    criado_em TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (medicao_id, item_id)
);
CREATE INDEX IF NOT EXISTS idx_medicao_documentos_medicao ON medicao_documentos (medicao_id);
