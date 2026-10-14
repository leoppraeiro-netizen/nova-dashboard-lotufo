-- E-mails enviados pelo sistema (spec 2026-09-21 §5.1). So' entra aqui o que o Graph ACEITOU:
-- falha de envio nao deixa linha nem muda estado de nada. Append-only.
CREATE TABLE IF NOT EXISTS envios (
    id INTEGER PRIMARY KEY,
    tipo TEXT NOT NULL,
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id),
    remetente TEXT NOT NULL,
    para TEXT NOT NULL,
    copia TEXT NOT NULL,
    assunto TEXT NOT NULL,
    mensagem_id TEXT,
    enviado_em TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS envio_anexos (
    id INTEGER PRIMARY KEY,
    envio_id INTEGER NOT NULL REFERENCES envios(id),
    nome TEXT NOT NULL,
    tamanho INTEGER NOT NULL,
    sha256 TEXT NOT NULL
);
