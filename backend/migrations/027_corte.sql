-- 027: corte (bloco 9; spec 2026-09-21 §12 e §13). A deteccao saiu do codigo; os dados ficam arquivados
-- no proprio banco (e nos backups) com o prefixo arquivo_. Nada e' apagado. O SQLite atualiza sozinho as
-- chaves estrangeiras entre elas (sugestao_id, config_id) no RENAME.
ALTER TABLE sugestoes RENAME TO arquivo_sugestoes;
ALTER TABLE deteccao_padroes RENAME TO arquivo_deteccao_padroes;
ALTER TABLE deteccao_config RENAME TO arquivo_deteccao_config;
ALTER TABLE mensagens_observadas RENAME TO arquivo_mensagens_observadas;
ALTER TABLE planilhas_config RENAME TO arquivo_planilhas_config;
ALTER TABLE planilhas_observadas RENAME TO arquivo_planilhas_observadas;
ALTER TABLE graph_sincronizacoes RENAME TO arquivo_graph_sincronizacoes;
