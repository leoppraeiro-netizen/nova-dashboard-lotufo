-- 036: indice da auditoria por objeto (gate Sol S2 do pacote 5 dos testes de quebra, 10/10/2026). A linha do tempo
-- da medicao (B-02) le as edicoes de valor de cada medicao da obra em `audit_log`; sem indice por entidade, cada obra
-- aberta varria a auditoria inteira. Ver app/medicoes.py (edicoes_valor).
CREATE INDEX IF NOT EXISTS ix_audit_log_entidade ON audit_log (entidade, entidade_id, acao, id);
