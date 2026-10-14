-- Fase 6: observacao do Outlook e do SharePoint (spec §4, §5 "Sugestao" e §15.3).
--
-- O motor e' o extrator DETERMINISTICO (gate + regex v2 do spike da fase 0): nada aqui
-- chama servico pago. O que a regra alcanca com a regra completa auto-aplica com
-- origem `detectado`; o resto vira sugestao na fila da fase 2 (tipos novos, sem CHECK,
-- como a migracao 005 previu).
--
-- Escopo minimo de leitura (spec §10): so' mensagem que passa pelo gate tem assunto,
-- remetente e campos extraidos guardados. O que o gate descarta como ruido deixa
-- APENAS o id (para nao ser reprocessado) -- sem assunto, sem remetente, sem corpo.
-- Corpo de e-mail nunca e' armazenado: fica um trecho curto de evidencia quando a
-- extracao veio do corpo (FRC, divergencia assunto x corpo).

-- Padroes de deteccao (spec §7, tela 8): remetentes internos (dominio ou endereco),
-- controladoria (FRC), canais do orgao (protocolo), faturamento (espelho) e apelidos
-- de contrato ("Oriundi", "Porto Espiridiao") que aparecem no fim do assunto.
CREATE TABLE IF NOT EXISTS deteccao_padroes (
    id INTEGER PRIMARY KEY,
    tipo TEXT NOT NULL CHECK (tipo IN ('remetente_interno','controladoria','canal_orgao',
                                       'faturamento','apelido_contrato')),
    valor TEXT NOT NULL,
    contrato_id INTEGER REFERENCES contratos(id),
    ativo INTEGER NOT NULL DEFAULT 1,
    criado_em TEXT NOT NULL DEFAULT (datetime('now'))
);
-- Sementes do spike (docs/superpowers/research/2026-08-spike-deteccao-outlook.md):
-- dominio da equipe e a controladoria de consorcios. Idempotente pelo indice unico. Valores de exemplo (issue
-- #110): a deteccao saiu no bloco 9 e nada le esta tabela; bancos que ja' rodaram a 014 guardam o que tinham.
CREATE UNIQUE INDEX IF NOT EXISTS idx_deteccao_padroes_unico
    ON deteccao_padroes (tipo, valor, COALESCE(contrato_id, 0));
INSERT OR IGNORE INTO deteccao_padroes (tipo, valor) VALUES ('remetente_interno', '@exemplo.com.br');
INSERT OR IGNORE INTO deteccao_padroes (tipo, valor) VALUES ('controladoria', 'controladoria@exemplo.com.br');

-- Chave/valor da deteccao: `auto_aplicar` (1/0; o backfill roda sempre desligado),
-- `cursor_outlook` (receivedDateTime da ultima mensagem vista) e o que mais a
-- administracao precisar sem migracao nova.
CREATE TABLE IF NOT EXISTS deteccao_config (
    chave TEXT PRIMARY KEY,
    valor TEXT NOT NULL,
    atualizado_em TEXT NOT NULL DEFAULT (datetime('now'))
);
INSERT OR IGNORE INTO deteccao_config (chave, valor) VALUES ('auto_aplicar', '1');

-- Cada mensagem que a rodada olhou. `mensagem_id` e' o id do Graph (estavel por caixa);
-- `resultado` diz o que aconteceu: auto (aplicou), sugestao (foi a fila), ruido (gate
-- descartou; so' o id fica), duplicado (ja' registrado), ignorado (candidato sem efeito).
CREATE TABLE IF NOT EXISTS mensagens_observadas (
    id INTEGER PRIMARY KEY,
    mensagem_id TEXT NOT NULL UNIQUE,
    internet_message_id TEXT,
    conversation_id TEXT,
    recebido_em TEXT,
    direcao TEXT CHECK (direcao IN ('entrada','saida')),
    remetente TEXT,
    assunto TEXT,
    weblink TEXT,
    categoria TEXT NOT NULL,
    campos TEXT,
    resultado TEXT NOT NULL CHECK (resultado IN ('auto','sugestao','vinculado','ruido','duplicado','ignorado')),
    motivo TEXT,
    contrato_id INTEGER REFERENCES contratos(id),
    medicao_id INTEGER REFERENCES medicoes(id),
    sugestao_id INTEGER REFERENCES sugestoes(id),
    rodada_id INTEGER,
    visto_em TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_mensagens_conversa ON mensagens_observadas (conversation_id);
CREATE INDEX IF NOT EXISTS idx_mensagens_medicao ON mensagens_observadas (medicao_id);

-- Planilhas do SharePoint: celulas conhecidas POR CONTRATO, cadastradas na administracao
-- (spec §15.3). `caminho` e' a pasta no drive do site; `padrao_arquivo` filtra por nome
-- (glob); as celulas dizem onde estao nº, competencia e valor na aba indicada.
-- Planilhas do SharePoint: a TABELA CONSOLIDADA de medições, por contrato.
--
-- Desenho decidido em 2026-09-03, depois de conferir os 12 documentos assinados da obra
-- 181 (docs/backlog.md): a planilha de CADA medição traz valor desatualizado -- a 2ª
-- dizia 1.416.004,35 onde o documento assinado diz 671.272,80 --, enquanto a tabela
-- consolidada da planilha mais recente bate com o assinado em 11 de 12 medições. Por
-- isso a leitura pega UM arquivo, o mais recente da pasta, e extrai a tabela inteira:
-- valores confiáveis, e um download por rodada em vez de treze de 10 MB.
--
-- Os campos sao COLUNAS da tabela (`B`, `H`), nao celulas: a linha muda a cada medicao e
-- e' descoberta pelo rotulo ("12ª medição") na coluna do rotulo.
CREATE TABLE IF NOT EXISTS planilhas_config (
    id INTEGER PRIMARY KEY,
    contrato_id INTEGER NOT NULL REFERENCES contratos(id),
    caminho TEXT NOT NULL,
    padrao_arquivo TEXT NOT NULL DEFAULT '*.xlsx',
    aba TEXT,
    coluna_rotulo TEXT NOT NULL,
    coluna_competencia TEXT NOT NULL,
    coluna_valor TEXT NOT NULL,
    -- Opcional: quando preenchida, a linha rende DUAS medicoes, execucao e reajuste --
    -- que e' como a Lotufo protocola (spec §2, tramitam separados).
    coluna_reajuste TEXT,
    tipo_medicao TEXT NOT NULL DEFAULT 'execucao' CHECK (tipo_medicao IN ('execucao','projeto')),
    ativo INTEGER NOT NULL DEFAULT 1,
    criado_em TEXT NOT NULL DEFAULT (datetime('now'))
);
-- Arquivo ja' lido (id do item + eTag): mudou o eTag, le de novo.
CREATE TABLE IF NOT EXISTS planilhas_observadas (
    id INTEGER PRIMARY KEY,
    item_id TEXT NOT NULL,
    etag TEXT,
    nome TEXT,
    config_id INTEGER REFERENCES planilhas_config(id),
    resultado TEXT NOT NULL CHECK (resultado IN ('sugestao','duplicado','ignorado','erro')),
    motivo TEXT,
    sugestao_id INTEGER REFERENCES sugestoes(id),
    rodada_id INTEGER,
    visto_em TEXT NOT NULL DEFAULT (datetime('now')),
    -- Por configuracao: o mesmo arquivo pode estar cadastrado para dois contratos ou duas
    -- abas, e cada leitura e' independente (gate Sol da fase 6).
    UNIQUE (config_id, item_id, etag)
);

CREATE TABLE IF NOT EXISTS graph_sincronizacoes (
    id INTEGER PRIMARY KEY,
    disparo TEXT NOT NULL CHECK (disparo IN ('agendado','manual','backfill')),
    estado TEXT NOT NULL DEFAULT 'running' CHECK (estado IN ('running','success','failed')),
    iniciado_em TEXT NOT NULL DEFAULT (datetime('now')),
    terminado_em TEXT,
    mensagens INTEGER NOT NULL DEFAULT 0,
    planilhas INTEGER NOT NULL DEFAULT 0,
    auto INTEGER NOT NULL DEFAULT 0,
    sugestoes INTEGER NOT NULL DEFAULT 0,
    erro TEXT
);

-- Marco "espelho enviado ao faturamento" (spec §4: "envio de espelho" e' um dos eventos
-- detectados). Nao e' estado da medicao -- quem move para NF emitida e' o RM (fase 5) --,
-- e' a data do e-mail, com a origem ao lado, para a linha do tempo.
ALTER TABLE medicoes ADD COLUMN espelho_em TEXT;
ALTER TABLE medicoes ADD COLUMN espelho_origem TEXT CHECK (espelho_origem IN ('detectado','aceito','manual'));
