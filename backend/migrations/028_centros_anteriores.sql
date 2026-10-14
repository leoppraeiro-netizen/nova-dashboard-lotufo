-- 028: centros de custo que a obra usou no RM antes do atual (2026-09-25). O RM trocou os centros por volta de
-- 2024 (Alta Floresta 6.004.003 -> 4.004.004); as notas antigas ficam no centro velho. Lista JSON, do cadastro.
-- So' a conciliacao do legado olha; o casador ao vivo continua no centro atual.
ALTER TABLE contratos ADD COLUMN centros_custo_anteriores_rm TEXT;
