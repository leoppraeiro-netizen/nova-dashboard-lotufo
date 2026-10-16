-- 040: garantia e ART como documentos do contrato (issue #65, decisao de 15/10/2026). So' acrescenta.
-- A garantia do contrato traz apolice, fim da vigencia e o PDF; cada `endosso_garantia` com `vigencia_fim`
-- (em instrumentos.dados) substitui a vigencia (historico preservado, correcao e' instrumento novo).
-- A ART ja' tinha o numero em `art`; ganha so' o PDF. ART nao tem validade: vale pela obra.
ALTER TABLE contratos ADD COLUMN garantia_apolice TEXT;
ALTER TABLE contratos ADD COLUMN garantia_vigencia_fim TEXT;
ALTER TABLE contratos ADD COLUMN garantia_arquivo TEXT;
ALTER TABLE contratos ADD COLUMN art_arquivo TEXT;
