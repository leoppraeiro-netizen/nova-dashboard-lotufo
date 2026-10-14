-- Fila unica de sugestoes (spec §5): tudo que o sistema PROPOE (importacao manual
-- agora; deteccao automatica nas fases 5-6) entra aqui como payload pendente e so
-- vira dado real depois de uma decisao humana registrada.
--
-- `tipo` e' TEXT LIVRE de proposito (sem CHECK): as fases 6+ acrescentam tipos novos
-- sem precisar de migracao para reescrever o CHECK. A validacao dos tipos conhecidos
-- fica na aplicacao (sugestoes.py / api_sugestoes.py).
CREATE TABLE IF NOT EXISTS sugestoes (
    id INTEGER PRIMARY KEY,
    tipo TEXT NOT NULL,
    payload TEXT NOT NULL,
    confianca REAL,
    evidencia TEXT,
    estado TEXT NOT NULL DEFAULT 'pendente'
        CHECK (estado IN ('pendente','aceita','corrigida','descartada')),
    decisor_id INTEGER REFERENCES usuarios(id),
    decidido_em TEXT,
    criado_em TEXT NOT NULL DEFAULT (datetime('now'))
);
