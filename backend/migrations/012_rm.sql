-- Fase 5: integracao com o TOTVS RM (leitura), spec §4 (sincronizador RM) e §5
-- (Nota Fiscal, Alocacao de faturamento, Recebimento/Baixa).
--
-- O RM e' a fonte de "NF emitida" e "recebida". O que vem de la' entra por UPSERT
-- idempotente (chave externa estavel: coligada + id do movimento / do lancamento) e
-- nunca e' apagado: NF cancelada vira `situacao='cancelada'`, e a alocacao que a
-- ligava a uma medicao e' DESFEITA (marcada), nao removida -- historico, nao estado.
--
-- Linhas de NF e baixa NAO passam pela cadeia de auditoria: sao espelho de outro
-- sistema, chegam aos milhares por rodada e a cadeia e' append-only. O que e' decisao
-- nossa (alocar, desfazer, mover a medicao de estado) e' auditado; cada rodada da
-- sincronizacao deixa uma linha em `rm_sincronizacoes` com os totais.

-- Qual coligada do RM emite as NFs desta entidade (Lotufo=1; consorcios tem coligada
-- propria -- spike da fase 0). E' a chave que liga a NF ao contrato certo.
ALTER TABLE entidades ADD COLUMN coligada_rm INTEGER;
UPDATE entidades SET coligada_rm = 1 WHERE id = 1 AND coligada_rm IS NULL;
-- Uma coligada emite para UMA entidade: com duas entidades na mesma coligada o casamento
-- por valor nao saberia de quem e' a NF (gate Sol da fase 5).
CREATE UNIQUE INDEX IF NOT EXISTS idx_entidades_coligada ON entidades (coligada_rm) WHERE coligada_rm IS NOT NULL;

CREATE TABLE IF NOT EXISTS notas_fiscais (
    id INTEGER PRIMARY KEY,
    coligada INTEGER NOT NULL,
    idmov INTEGER NOT NULL,
    numero TEXT NOT NULL,
    serie TEXT,
    emissao TEXT,
    valor_centavos INTEGER NOT NULL CHECK (valor_centavos >= 0),
    codtmv TEXT,
    status_rm TEXT,
    campo_livre1 TEXT,
    tomador TEXT,
    situacao TEXT NOT NULL DEFAULT 'ativa' CHECK (situacao IN ('ativa','cancelada','substituida')),
    primeiro_visto_em TEXT NOT NULL DEFAULT (datetime('now')),
    ultimo_visto_em TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (coligada, idmov)
);

-- Lancamento financeiro (FLAN) da NF. `valor_baixado` e `status_lan` sao os do RM
-- (0 aberto, 1 baixado, 2 cancelado, 3 baixado por acordo, 4 parcial); "recebido"
-- deriva deles. `data_baixa_bruta` guarda o que o RM mandou mesmo quando a data e'
-- implausivel (o spike achou 2036-06-16): `data_baixa` fica NULL nesse caso.
CREATE TABLE IF NOT EXISTS baixas (
    id INTEGER PRIMARY KEY,
    coligada INTEGER NOT NULL,
    idlan INTEGER NOT NULL,
    nota_id INTEGER REFERENCES notas_fiscais(id),
    idmov INTEGER,
    numero_documento TEXT,
    valor_original_centavos INTEGER NOT NULL CHECK (valor_original_centavos >= 0),
    valor_baixado_centavos INTEGER NOT NULL DEFAULT 0 CHECK (valor_baixado_centavos >= 0),
    status_lan INTEGER NOT NULL,
    data_baixa TEXT,
    data_baixa_bruta TEXT,
    ultimo_visto_em TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (coligada, idlan)
);
CREATE INDEX IF NOT EXISTS idx_baixas_nota ON baixas (nota_id);

-- Medicao <-> NF (N:N). `regra` diz como o casamento aconteceu (campo_livre1 |
-- valor_exato | decisao_humana); `confianca` acompanha. Desfeita = marcada, com motivo.
CREATE TABLE IF NOT EXISTS nf_alocacoes (
    id INTEGER PRIMARY KEY,
    medicao_id INTEGER NOT NULL REFERENCES medicoes(id),
    nota_id INTEGER NOT NULL REFERENCES notas_fiscais(id),
    valor_alocado_centavos INTEGER NOT NULL CHECK (valor_alocado_centavos >= 0),
    origem TEXT NOT NULL CHECK (origem IN ('detectado','aceito','manual')),
    confianca REAL,
    regra TEXT,
    desfeita_em TEXT,
    motivo_desfazer TEXT,
    criado_em TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_nf_alocacoes_medicao ON nf_alocacoes (medicao_id);
CREATE INDEX IF NOT EXISTS idx_nf_alocacoes_nota ON nf_alocacoes (nota_id);

CREATE TABLE IF NOT EXISTS rm_sincronizacoes (
    id INTEGER PRIMARY KEY,
    disparo TEXT NOT NULL CHECK (disparo IN ('agendado','manual')),
    estado TEXT NOT NULL DEFAULT 'running' CHECK (estado IN ('running','success','failed')),
    iniciado_em TEXT NOT NULL DEFAULT (datetime('now')),
    terminado_em TEXT,
    nfs INTEGER NOT NULL DEFAULT 0,
    baixas INTEGER NOT NULL DEFAULT 0,
    alocacoes INTEGER NOT NULL DEFAULT 0,
    sugestoes INTEGER NOT NULL DEFAULT 0,
    recebimentos INTEGER NOT NULL DEFAULT 0,
    erro TEXT
);
