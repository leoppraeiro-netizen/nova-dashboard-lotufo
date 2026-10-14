-- Log operacional das chamadas de IA (spec §14, fase 3).
--
-- Esta tabela NAO e' auditoria de negocio. `audit_log` responde "quem mudou o quê e
-- quando" sobre o DADO (cadeia encadeada por hash, append-only, verificavel);
-- `ia_chamadas` responde "quanto isso custou" sobre o PROCESSO. A IA deste produto
-- nunca grava nada -- ela devolve sugestao para um humano confirmar (§14.1) -- entao
-- nao existe mutacao de negocio a descrever, e pendurar essas linhas na cadeia so
-- encheria a auditoria de ruido de custo.
--
-- O custo fica em CENTAVOS DE REAL (INTEGER), nunca em float: a mesma regra do
-- app/dinheiro.py. Somar centavos de 500 chamadas em float acumula erro; em int, nao.
-- O valor e' ESTIMADO (tabela de preco em dolar + cambio aproximado, ambos datados no
-- modulo app/ia_extracao.py) -- serve para o teto mensal e para o painel da
-- administracao, nunca para conciliar com a fatura da Anthropic.
--
-- usuario_id e' nullable de proposito: o robo (e um job futuro) chama sem humano por
-- tras, e mentir um id ali seria pior que assumir o None -- mesma decisao do
-- robo_certidoes.
CREATE TABLE IF NOT EXISTS ia_chamadas (
    id INTEGER PRIMARY KEY,
    usuario_id INTEGER REFERENCES usuarios(id),
    finalidade TEXT NOT NULL,
    modelo TEXT NOT NULL,
    tokens_entrada INTEGER NOT NULL,
    tokens_saida INTEGER NOT NULL,
    custo_estimado_centavos INTEGER NOT NULL,
    criado_em TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_ia_chamadas_criado_em ON ia_chamadas (criado_em);
