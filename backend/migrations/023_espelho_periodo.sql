-- 023: periodo do espelho quando nao e' o mes civil da competencia (Coxipo 3a: 05/02 a 28/02;
-- Terminais BRT: 01/07 a 31/08; decisao do Leonardo em 2026-09-23). NULL = 01 ao ultimo dia do mes.
ALTER TABLE espelhos ADD COLUMN periodo_inicio TEXT;
ALTER TABLE espelhos ADD COLUMN periodo_fim TEXT;
