-- 037: copia por contrato (14/10/2026). A copia do e-mail ao orgao muda por obra (o engenheiro da obra), nao so'
-- por orgao: `copia_extras` do contrato soma-se a `protocolo_copia` do orgao. Ver app/protocolo.py (_destinatarios).
ALTER TABLE contratos ADD COLUMN copia_extras TEXT;
