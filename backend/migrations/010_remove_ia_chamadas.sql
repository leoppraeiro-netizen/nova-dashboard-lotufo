-- Spec §15 (2026-09-01): o produto nao chama servico pago por uso. A tabela de custo
-- de IA (§14.5, migracao 007) perdeu objeto -- nenhuma linha dela e' dado de negocio
-- (era log operacional, fora da cadeia de auditoria), entao remover e' seguro.
-- DROP IF EXISTS e' idempotente: reaplicar a migracao inteira (executescript nao e'
-- transacional) nao quebra.
DROP TABLE IF EXISTS ia_chamadas;
