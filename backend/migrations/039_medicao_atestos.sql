-- 039: atesto como evento append-only (issue #61, decisao do Leo de 15/10/2026). Antes, o valor atestado era so'
-- a coluna da medicao, sobrescrita a cada glosa; o historico vivia apenas na auditoria. Agora cada mudanca de
-- atesto (valor ou dia) e' uma linha nova aqui, com autor e data, que nunca se altera nem se apaga. A coluna
-- `medicoes.valor_atestado_centavos` continua sendo o VIGENTE (o ultimo evento), gravada na mesma transacao,
-- para que paineis, diretoria e conciliacao sigam lendo dela. Ver app/medicoes.py (definir_valor, edicoes_valor).
CREATE TABLE IF NOT EXISTS medicao_atestos (
    id INTEGER PRIMARY KEY,
    medicao_id INTEGER NOT NULL REFERENCES medicoes(id),
    valor_centavos INTEGER NOT NULL CHECK (valor_centavos >= 0),
    -- NULL so' na carga desta migracao, quando a auditoria antiga nao trazia a origem
    origem TEXT CHECK (origem IS NULL OR origem IN ('detectado','aceito','manual')),
    atestado_em TEXT,
    usuario_id INTEGER REFERENCES usuarios(id),
    criado_em TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_medicao_atestos_medicao ON medicao_atestos (medicao_id, id);

CREATE TRIGGER IF NOT EXISTS medicao_atestos_sem_update BEFORE UPDATE ON medicao_atestos
BEGIN
    SELECT RAISE(ABORT, 'Atesto é evento: não se altera (registre um atesto novo)');
END;
CREATE TRIGGER IF NOT EXISTS medicao_atestos_sem_delete BEFORE DELETE ON medicao_atestos
BEGIN
    SELECT RAISE(ABORT, 'Atesto é evento: não se apaga');
END;

-- Carga do historico que ja existe: cada edicao de atestado da auditoria vira um evento, na ordem, com o autor e
-- a hora da auditoria. So' para medicao que ainda nao tem evento (reexecutar a migracao nao duplica).
INSERT INTO medicao_atestos (medicao_id, valor_centavos, origem, atestado_em, usuario_id, criado_em)
SELECT CAST(a.entidade_id AS INTEGER),
       json_extract(a.depois, '$.valor_atestado_centavos'),
       CASE WHEN json_extract(a.depois, '$.valor_atestado_origem') IN ('detectado','aceito','manual')
            THEN json_extract(a.depois, '$.valor_atestado_origem') END,
       -- auditoria antiga sem o dia no `depois`: vale o dia que ja' estava (`antes`)
       CASE WHEN json_type(a.depois, '$.atestado_em') = 'text' THEN json_extract(a.depois, '$.atestado_em')
            WHEN json_valid(a.antes) AND json_type(a.antes, '$.atestado_em') = 'text'
            THEN json_extract(a.antes, '$.atestado_em') END,
       -- usuario que nao existe mais (ou nenhum) vira "pelo sistema"; a chave estrangeira nao deixa gravar outro
       CASE WHEN EXISTS (SELECT 1 FROM usuarios u WHERE u.id = a.usuario_id) THEN a.usuario_id END,
       a.criado_em
FROM audit_log a
WHERE a.acao = 'medicao.valor_atestado' AND a.entidade = 'medicao'
  AND a.entidade_id <> '' AND a.entidade_id NOT GLOB '*[^0-9]*'
  AND json_valid(a.depois)
  AND json_type(a.depois, '$.valor_atestado_centavos') = 'integer'
  AND json_extract(a.depois, '$.valor_atestado_centavos') >= 0
  AND EXISTS (SELECT 1 FROM medicoes m WHERE m.id = CAST(a.entidade_id AS INTEGER))
  AND NOT EXISTS (SELECT 1 FROM medicao_atestos e WHERE e.medicao_id = CAST(a.entidade_id AS INTEGER))
ORDER BY a.id;

-- Rede de seguranca: se o vigente gravado na medicao nao e' o do ultimo evento (ou a medicao nao tem evento),
-- o vigente entra como evento "pelo sistema". Assim vale sempre: vigente = ultimo evento.
-- A hora do evento e' a da migracao (UTC, como todo criado_em): e' quando o sistema o registrou, e assim ele
-- fica depois dos eventos anteriores tambem na ordem da linha do tempo. O dia do atesto vai em atestado_em.
INSERT INTO medicao_atestos (medicao_id, valor_centavos, origem, atestado_em, usuario_id)
SELECT m.id, m.valor_atestado_centavos, m.valor_atestado_origem, m.atestado_em, NULL
FROM medicoes m
WHERE m.valor_atestado_centavos IS NOT NULL
  AND NOT EXISTS (
      SELECT 1 FROM medicao_atestos e
      WHERE e.id = (SELECT MAX(e2.id) FROM medicao_atestos e2 WHERE e2.medicao_id = m.id)
        AND e.valor_centavos = m.valor_atestado_centavos
        AND e.atestado_em IS m.atestado_em);
