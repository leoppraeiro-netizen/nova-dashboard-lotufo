-- 033: documento complementar do envio pode ser .zip (2026-10-09, pedido do Leonardo). A SINFRA (gabinetes do
-- BRT, SACID) recebe os relatorios assinados no zip que o DocuSign entrega ("Complete_com_o_Docusign_...zip":
-- caderno da medicao, capa, resumo, croqui, diagrama linear e Summary), e o envio dos Terminais precisa
-- anexa-lo como veio. So' o CHECK de `ext` muda; o resto da tabela e' o da 025.
--
-- Receita oficial do SQLite para mudar CHECK (a mesma da 020): criar nova, copiar, apagar a antiga, renomear.
-- Ninguem referencia protocolo_pecas; foreign_keys OFF so' por garantia (o runner religa mesmo se falhar).
-- Reexecutavel: a `_nova` e' apagada antes de recriar.
PRAGMA foreign_keys=OFF;

DROP TABLE IF EXISTS protocolo_pecas_nova;
CREATE TABLE protocolo_pecas_nova (
    id INTEGER PRIMARY KEY,
    protocolo_id INTEGER NOT NULL REFERENCES protocolos(id),
    tipo TEXT NOT NULL,
    nome TEXT NOT NULL,
    arquivo TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    tamanho INTEGER NOT NULL,
    ext TEXT NOT NULL CHECK (ext IN ('pdf','xlsx','zip')),
    removida_em TEXT,
    criado_em TEXT NOT NULL DEFAULT (datetime('now'))
);
INSERT INTO protocolo_pecas_nova (id, protocolo_id, tipo, nome, arquivo, sha256, tamanho, ext, removida_em, criado_em)
    SELECT id, protocolo_id, tipo, nome, arquivo, sha256, tamanho, ext, removida_em, criado_em FROM protocolo_pecas;
DROP TABLE protocolo_pecas;
ALTER TABLE protocolo_pecas_nova RENAME TO protocolo_pecas;

PRAGMA foreign_keys=ON;
