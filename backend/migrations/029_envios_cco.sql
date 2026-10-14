-- 029: copia oculta no registro do envio (2026-09-25, envio como no Outlook). Lista JSON; NULL = sem Cco.
ALTER TABLE envios ADD COLUMN cco TEXT;
