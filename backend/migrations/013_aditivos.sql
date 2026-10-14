-- Fase 4: aditivos com fluxo de dois estados (em andamento -> assinado), spec §5 e §15.3.
--
-- A tabela existe desde a 002 (tipo, delta, novas datas, status, data_assinatura) e ja'
-- alimenta `contratos.vigente`. O que falta e' o que a fase 4 exige do ATO de assinar:
-- o delta conferido aritmeticamente contra o vigente do momento (novo = anterior +
-- delta), a ressalva de reajuste e quem confirmou. `valor_anterior`/`valor_novo` sao o
-- SNAPSHOT da conferencia -- congelados na assinatura, como o valor protocolado da
-- medicao: se o vigente for reconstruido depois, o que foi conferido continua legivel.
--
-- Aditivo em andamento que nao vai ser assinado e' CANCELADO por coluna propria
-- (`cancelado_em`), nao por apagar a linha nem por um status novo: o CHECK de `status`
-- so' conhece em_andamento/assinado e trocar CHECK no SQLite e' reconstruir a tabela.
-- Assinado nunca e' cancelado: correcao e' outro aditivo (historico, nao estado).
ALTER TABLE aditivos ADD COLUMN numero TEXT;
ALTER TABLE aditivos ADD COLUMN objeto TEXT;
ALTER TABLE aditivos ADD COLUMN observacao TEXT;
ALTER TABLE aditivos ADD COLUMN ressalva_reajuste TEXT;
ALTER TABLE aditivos ADD COLUMN valor_anterior_centavos INTEGER;
ALTER TABLE aditivos ADD COLUMN valor_novo_centavos INTEGER;
ALTER TABLE aditivos ADD COLUMN assinado_por INTEGER REFERENCES usuarios(id);
ALTER TABLE aditivos ADD COLUMN cancelado_em TEXT;
ALTER TABLE aditivos ADD COLUMN cancelado_motivo TEXT;
