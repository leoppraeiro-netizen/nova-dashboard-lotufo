-- 034: arquivo grande do envio vai por LINK do OneDrive (2026-10-09, opcao A do Leonardo). O Exchange recusa
-- e-mail acima de ~35 MB codificado (25 MB crus, correio.MAX_TOTAL); a Maria resolvia anexando "como link" no
-- Outlook (croqui e relatorios assinados do Integra BRT, 14a medicao). Aqui a pessoa sobe o arquivo no OneDrive,
-- cola o link e da' um nome; o link entra no corpo do e-mail e nao conta no limite dos anexos.
CREATE TABLE IF NOT EXISTS protocolo_links (
    id INTEGER PRIMARY KEY,
    protocolo_id INTEGER NOT NULL REFERENCES protocolos(id),
    nome TEXT NOT NULL,
    url TEXT NOT NULL CHECK (url LIKE 'https://%'),
    removido_em TEXT,
    criado_em TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_protocolo_links_protocolo ON protocolo_links (protocolo_id);
