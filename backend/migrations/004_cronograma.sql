-- Cronograma fisico-financeiro versionado (spec §5): revisar o cronograma cria uma
-- NOVA versao; nenhuma anterior e' apagada ou reescrita. O "passado congelado" e'
-- derivado na leitura (cronograma.previsto_efetivo) a partir de criado_em -- por isso
-- as versoes precisam ficar todas guardadas.
CREATE TABLE IF NOT EXISTS cronograma_versoes (
    id INTEGER PRIMARY KEY,
    contrato_id INTEGER NOT NULL REFERENCES contratos(id),
    numero INTEGER NOT NULL CHECK (numero >= 1),
    origem TEXT NOT NULL DEFAULT 'manual' CHECK (origem IN ('detectado','aceito','manual')),
    criado_em TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (contrato_id, numero)
);

CREATE TABLE IF NOT EXISTS cronograma_itens (
    id INTEGER PRIMARY KEY,
    versao_id INTEGER NOT NULL REFERENCES cronograma_versoes(id),
    -- GLOB '[0-9]...' (e nao um regex): so digito ASCII. Ver o comentario de
    -- COMPETENCIA em api_cronograma.py -- o `\d` do Python casaria digito unicode
    -- e o CHECK viraria IntegrityError (500) em vez de 422 na borda.
    competencia TEXT NOT NULL CHECK (competencia GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]'),
    valor_previsto_centavos INTEGER NOT NULL CHECK (valor_previsto_centavos >= 0),
    UNIQUE (versao_id, competencia)
);
