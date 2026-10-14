# Fase 3 — Certidões + Dívidas Estruturais: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Certidões com robô das federais, upload estadual/municipal com IA nos metadados (admin-only), alertas e checklist "pronto para protocolar" — precedidos pelas 2 dívidas estruturais da fase 2 (transação única mutação+auditoria; política de fuso) e encerrados pelo lote de polimento de UI + finish review.

**Architecture:** Mesmo desenho das fases 1-2 (FastAPI + SQLite SQL explícito, repositórios com auditoria, routers finos, React sem libs novas) + primeiro worker agendado de negócio (robô semanal, padrão do backup da fase 1) + primeira chamada de IA do produto (extração de metadados de certidão, admin-only, chave em env, degradação graciosa).

**Tech Stack:** Python 3.12, FastAPI, sqlite3, pytest/httpx; React 18 + Vite + TS. Deps novas PINADAS e mínimas: `tzdata` (zoneinfo no Windows), `pypdf` (texto de PDF), `anthropic` (SDK oficial, só no caminho da T6).

**Spec:** `docs/superpowers/specs/2026-08-28-dashboard-contratos-medicoes-design.md` (v3 + emenda §14 aprovada 2026-09-01, tag `emenda-ia-aprovada`) — §1.6, §3 dec. 8, §4 robô, §5 Certidão, §7 telas 2/6, §12 fase 3, §14.4/14.5.

## Global Constraints

- Dinheiro em centavos; SQL explícito; migrações idempotentes `IF NOT EXISTS`; mensagens pt-BR; datas ISO.
- **NOVO (T1):** toda mutação = UMA transação: `BEGIN IMMEDIATE` no início, `auditoria.registrar(...)` como último comando E `conn.commit()` pelo CHAMADOR via helper `db.mutacao(conn)`. `registrar()` NÃO commita mais.
- **NOVO (T2):** banco grava UTC (`datetime('now')` mantido); toda EXIBIÇÃO e toda lógica sensível a mês/dia usa América/Cuiabá via helpers únicos (`app/tempo.py` no backend; `fmtDataHora`/`mesAtualLocal` em `frontend/src/tempo.ts`). Proibido `new Date().toLocaleString()` direto e `datetime.now()` sem tz.
- **Custo externo = admin-only** (§14.5): a rota de extração IA exige perfil admin; workers automáticos usam a chave da aplicação (`DASH_ANTHROPIC_KEY`); sem chave → 503 pt-BR "chave de IA não configurada", UI desabilita o botão com essa explicação; toda chamada registrada em `ia_chamadas` (modelo, tokens, custo estimado).
- IA extrai, código valida (§14.1): metadado de certidão só entra APÓS validador determinístico (datas parseáveis e coerentes, CNPJ presente literalmente no texto, validade re-localizada literal no PDF-texto). IA nunca grava direto — preenche formulário como sugestão.
- Permissões: leitura `exigir("ver_paineis", com_csrf=False)`; upload/registro de certidão `exigir("editar_cadastros")`; entidades, tipos, revogar/não-se-aplica e extração IA = `exigir("administrar")` (config só Administrador, spec dec. 10).
- Frontend segue `DESIGN.md` (raiz; desde 2026-09-25 em `docs/sistema-visual-fase3-2026-09-02.md`) — tokens, componentes e regras canonizadas; nada de cores/tamanhos fora da rampa sem atualizar o DESIGN.md junto.
- TDD; commits `feat:/fix:/test:/docs:` + rodapé `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.
- Rodar: `cd backend; .venv\Scripts\python -m pytest -q` (baseline 231). Frontend: `cd frontend; npx tsc --noEmit; npm run build`.
- Workers respeitam `DASH_SEM_JOBS=1` (suíte não agenda nada). Robô NUNCA roda nos testes — adaptadores testados com `httpx.MockTransport`.

---

### Task 1: Transação única mutação+auditoria (dívida estrutural #1)

A maior dívida da fase 2: hoje `auditoria.registrar()` abre `BEGIN IMMEDIATE` e **commita internamente**; uma decisão de sugestão gera até 3 commits e falha no meio deixa meia-decisão (provado empiricamente na T4 da fase 2). Esta task inverte o contrato: **o chamador é dono da transação**; `registrar()` só escreve a linha da cadeia.

**Files:**
- Modify: `backend/app/db.py` (novo contextmanager `mutacao`)
- Modify: `backend/app/auditoria.py` (remover BEGIN/commit internos)
- Modify: `backend/app/contratos.py`, `backend/app/medicoes.py`, `backend/app/cronograma.py`, `backend/app/sugestoes.py`, `backend/app/auth.py`, `backend/app/api_usuarios.py` (envolver cada mutação em `db.mutacao`)
- Test: `backend/tests/test_transacao.py` (novo) + ajustes mínimos nos testes existentes que dependiam do commit interno

**Interfaces:**
- Produces: `db.mutacao(conn)` — contextmanager: `BEGIN IMMEDIATE` na entrada; `conn.commit()` na saída sem exceção; `conn.rollback()` na exceção (re-levantada). Reentrância: se já há transação aberta (`conn.in_transaction` após nosso BEGIN falhar com "within a transaction"), NÃO abre nem fecha — participa da externa (permite composição: `sugestoes.decidir` envolve `medicoes.criar`).
- Produces: `auditoria.registrar(conn, ...)` — MESMA assinatura, mas: exige transação aberta (`assert conn.in_transaction`, e levanta `RuntimeError("registrar() exige transação aberta — use db.mutacao")` fail-closed), lê o head da cadeia e insere a linha SEM commit.
- Contrato p/ todos os repositórios: corpo de cada função mutadora vira `with db.mutacao(conn): <DMLs>; auditoria.registrar(...)`. Guardas de rowcount/CAS continuam DENTRO da transação (o rollback do `mutacao` desfaz tudo ao levantar ValueError).

- [ ] **Step 1: Escrever os testes que provam o novo contrato (falham hoje)**

```python
# backend/tests/test_transacao.py
"""A divida estrutural da fase 2: mutacao e auditoria no MESMO commit.

O teste central e o inverso do experimento da T4/fase 2: uma falha no meio
de decidir() nao pode deixar medicao orfa nem sugestao consumida.
"""
import pytest
from unittest.mock import patch
from app import auth, contratos, db, medicoes, sugestoes, auditoria

@pytest.fixture
def conn(tmp_path, monkeypatch):
    monkeypatch.setenv("DASH_DB_PATH", str(tmp_path / "t.db"))
    c = db.get_conn(); db.migrate(c)
    auth.criar_usuario(c, "U", "u@lotufo.com", "senha-forte-123", "engenharia")
    yield c
    c.close()

@pytest.fixture
def cid(conn):
    return contratos.criar(conn, 1, {"orgao": "S", "numero_instrumento": "IC 1",
                                     "objeto": "X", "valor_original_centavos": 100_00})

def test_registrar_sem_transacao_falha_alto(conn):
    with pytest.raises(RuntimeError, match="transação aberta"):
        auditoria.registrar(conn, 1, "x.y", "x", 1, None, {})

def test_mutacao_commita_junto(conn, cid):
    mid = medicoes.criar(conn, 1, {"contrato_id": cid, "numero": 1,
                                   "tipo": "execucao", "competencia": "2026-07"})
    outra = db.get_conn()
    try:
        assert outra.execute("SELECT COUNT(*) c FROM medicoes").fetchone()["c"] == 1
        assert outra.execute("SELECT COUNT(*) c FROM audit_log WHERE acao='medicao.criar'").fetchone()["c"] == 1
    finally:
        outra.close()
    assert not conn.in_transaction  # nada pendurado

def test_falha_no_meio_desfaz_tudo(conn, cid):
    # decidir() com falha APOS criar a medicao (no definir_valor): nada pode sobrar.
    sid = sugestoes.criar(conn, 1, "medicao_importada",
                          {"contrato_id": cid, "numero": 9, "tipo": "execucao",
                           "competencia": "2026-07", "valor_protocolado_centavos": 5_00},
                          None, "teste")
    with patch.object(medicoes, "definir_valor", side_effect=RuntimeError("boom")):
        with pytest.raises(RuntimeError, match="boom"):
            sugestoes.decidir(conn, 1, sid, "aceita", None)
    conn.rollback()  # simula o fim da requisicao
    assert medicoes.listar(conn, cid) == []                       # sem medicao orfa
    assert sugestoes.pendentes(conn) and sugestoes.pendentes(conn)[0]["id"] == sid  # sugestao segue pendente
    from app.auditoria import verificar_cadeia
    assert verificar_cadeia(conn)                                  # cadeia integra

def test_cadeia_serializada_sob_transacao(conn, cid):
    # duas mutacoes em sequencia mantem a cadeia encadeada corretamente
    medicoes.criar(conn, 1, {"contrato_id": cid, "numero": 1, "tipo": "execucao", "competencia": "2026-07"})
    medicoes.criar(conn, 1, {"contrato_id": cid, "numero": 2, "tipo": "execucao", "competencia": "2026-08"})
    from app.auditoria import verificar_cadeia
    assert verificar_cadeia(conn)
```

- [ ] **Step 2: Rodar e ver falhar** — `pytest tests/test_transacao.py -q` → FAIL (registrar hoje commita e não exige transação).

- [ ] **Step 3: Implementar `db.mutacao` e o novo `registrar`**

```python
# backend/app/db.py — acrescentar
from contextlib import contextmanager

@contextmanager
def mutacao(conn):
    """Dona da transacao de uma mutacao de negocio.

    BEGIN IMMEDIATE serializa escritores desde o inicio (a leitura do head da
    cadeia de auditoria acontece ja sob lock — sem fork da cadeia). Reentrante:
    dentro de uma mutacao externa, participa dela em vez de abrir outra.
    """
    if conn.in_transaction:
        yield conn          # ja estamos numa mutacao — compor, nao aninhar
        return
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except BaseException:
        conn.rollback()
        raise
    conn.commit()
```

```python
# backend/app/auditoria.py — registrar() perde o BEGIN/commit internos.
# Antes: try BEGIN IMMEDIATE (engolindo "within a transaction") ... conn.commit()
# Depois (nucleo; manter hash/normalizacoes exatamente como estao):
def registrar(conn, usuario_id, acao, entidade, entidade_id, antes, depois):
    if not conn.in_transaction:
        raise RuntimeError("registrar() exige transação aberta — use db.mutacao(conn)")
    ...  # leitura do head + INSERT da linha encadeada, SEM commit
```

- [ ] **Step 4: Migrar os repositórios** — padrão mecânico, um arquivo por vez, rodando a suíte do arquivo após cada um:

```python
# exemplo (medicoes.criar); aplicar o MESMO envelope a TODA funcao mutadora de
# contratos.py, medicoes.py, cronograma.py, sugestoes.py, auth.py (criar_usuario,
# registrar_login_falho, sessoes), api_usuarios.py (rotas que mutam):
def criar(conn, usuario_id, dados):
    with db.mutacao(conn):
        ja = conn.execute(...)
        ...
        cur = conn.execute("INSERT ...")
        mid = cur.lastrowid
        auditoria.registrar(conn, usuario_id, "medicao.criar", "medicao", mid, None, dados)
    return mid
```

Atenção aos pontos NÃO mecânicos (cada um vira um momento de cuidado + teste):
1. `sugestoes.decidir`: o envelope externo torna claim+materialização+auditorias UMA transação — o modo de falha "decidida sem medição" morre aqui. Remover o comentário da fase 2 que documentava a janela (agora falso) e atualizar o teste `test_decisao_*` que assumia commits parciais.
2. `contratos.mudar_estado` commitava dado ANTES do registrar (contratos.py:47, nota da review T1/fase 2) — o envelope conserta; conferir o teste.
3. `auth.autenticar` (contador de lockout) muta em caminho de LEITURA de login: envolver só o UPDATE do contador em `db.mutacao`.
4. Rotas: `_erro_do_cliente`/handlers continuam com `conn.rollback()` — vira no-op inofensivo (transação já desfeita pelo mutacao), manter pela defesa.

- [ ] **Step 5: Suíte completa** — `pytest -q`: TODOS os 231+4 verdes; os testes de corrida da fase 2 (`_detalhe_com_corrida`, `_ConexaoComCorrida`) devem continuar passando — se algum quebrar por lock (a segunda conexão agora encontra BEGIN IMMEDIATE aberto), ajustar o teste para commitar a interferência ANTES da mutação sob teste (a semântica que eles provam não muda).

- [ ] **Step 6: Commit** — `git add -A backend && git commit -m "feat: transacao unica mutacao+auditoria (registrar sem commit interno)"`

---

### Task 2: Política de fuso — América/Cuiabá (dívida estrutural #2)

**Files:**
- Create: `backend/app/tempo.py`; Modify: `backend/app/cronograma.py`, `backend/app/paineis.py`, `backend/pyproject.toml` (dep `tzdata==2025.2`)
- Create: `frontend/src/tempo.ts`; Modify: `frontend/src/Sugestoes.tsx` (dataHoraBR), `frontend/src/Cronograma.tsx` (mês do cadeado)
- Test: `backend/tests/test_tempo.py`

**Interfaces:**
- Produces backend: `tempo.agora_utc() -> datetime` (aware, UTC); `tempo.para_local(dt_utc) -> datetime` (America/Cuiaba); `tempo.mes_local(utc_str: str) -> str` ("AAAA-MM" do instante UTC convertido p/ Cuiabá); `tempo.hoje_local() -> date`.
- Produces frontend: `fmtDataHora(iso: string): string` (exibe em America/Cuiaba via `Intl.DateTimeFormat("pt-BR", {timeZone: "America/Cuiaba", ...})`); `mesAtualLocal(): string` ("AAAA-MM" em Cuiabá — substitui o `new Date()` cru do cadeado da T8/fase 2).
- Política (escrever no docstring de tempo.py): banco grava UTC SEMPRE (datetime('now') do SQLite intacto — nada de migração de dados); fronteiras de mês/dia do NEGÓCIO são as de Cuiabá; conversão só na borda (exibição/decisão), nunca no armazenamento.

- [ ] **Step 1: Testes que falham**

```python
# backend/tests/test_tempo.py
from app import tempo

def test_mes_local_virada_de_mes():
    # 31/08 21:30 local = 01/09 01:30 UTC: o mes de negocio ainda e agosto.
    assert tempo.mes_local("2026-09-01 01:30:00") == "2026-08"
    assert tempo.mes_local("2026-09-01 05:30:00") == "2026-09"  # ja passou da meia-noite local

def test_para_local_offset():
    d = tempo.para_local(tempo.agora_utc())
    assert d.utcoffset().total_seconds() == -4 * 3600  # Cuiaba = UTC-4, sem DST desde 2019
```

- [ ] **Step 2: Implementar**

```python
# backend/app/tempo.py
"""Politica de fuso do projeto (dívida da fase 2, decidida na fase 3):

- ARMAZENAR: sempre UTC (datetime('now') do SQLite). Nenhum dado migra.
- DECIDIR/EXIBIR: America/Cuiaba (UTC-4 fixo desde 2019, mas via zoneinfo
  para nao hardcodar). Fronteira de mes/dia do negocio = a local.
So estas funcoes convertem; nenhum outro modulo importa zoneinfo.
"""
import datetime
from zoneinfo import ZoneInfo

_TZ = ZoneInfo("America/Cuiaba")
_UTC = datetime.timezone.utc

def agora_utc() -> datetime.datetime:
    return datetime.datetime.now(_UTC)

def para_local(dt: datetime.datetime) -> datetime.datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_UTC)
    return dt.astimezone(_TZ)

def mes_local(utc_str: str) -> str:
    """'AAAA-MM-DD HH:MM:SS' (UTC, formato do SQLite) -> 'AAAA-MM' em Cuiaba."""
    dt = datetime.datetime.fromisoformat(utc_str.replace("Z", "")).replace(tzinfo=_UTC)
    return para_local(dt).strftime("%Y-%m")

def hoje_local() -> datetime.date:
    return para_local(agora_utc()).date()
```

- [ ] **Step 3: Aplicar nos 3 pontos da dívida** — `cronograma.previsto_efetivo`/`nova_versao`: `mes_criacao = tempo.mes_local(v["criado_em"])` (em vez de `[:7]`; o clamp monotônico continua comparando strings UTC — intacto); `paineis.alertas(hoje=None)`: default vira `tempo.hoje_local()`; frontend: `dataHoraBR` → `fmtDataHora` (corrige o UTC exibido como local da T9) e cadeado do Cronograma → `mesAtualLocal()`. Testes existentes do congelamento: ajustar SÓ os que fixavam criado_em na virada exata (o teste de datas explícitas da T3/fase 2 usa datas no meio do mês — passa sem mudança).

- [ ] **Step 4: `pytest -q` + `tsc` + build → verdes. Commit** — `feat: politica de fuso America/Cuiaba (armazena UTC, decide local)`

---

### Task 3: Migração 006 + repositórios de entidades e certidões

**Files:**
- Create: `backend/migrations/006_certidoes.sql`, `backend/app/entidades.py`, `backend/app/certidoes.py`
- Test: `backend/tests/test_entidades.py`, `backend/tests/test_certidoes.py`

**Interfaces:**
- Consumes: `db.mutacao`, `auditoria.registrar` (contrato novo da T1), `tempo.hoje_local` (T2).
- Produces (T4-T9 consomem):
  - `entidades.criar(conn, usuario_id, dados) -> int` — dados: nome, cnpj (14 dígitos, DV validado), papel ∈ ('lotufo','consorcio','consorciada'); `listar(conn, ativas=True) -> list[dict]`; `desativar(conn, usuario_id, entidade_id) -> None`.
  - `certidoes.tipos(conn) -> list[dict]`; `certidoes.criar_tipo(conn, usuario_id, nome, jurisdicao, emissor, aplicavel_por_padrao: bool) -> int`.
  - `certidoes.registrar(conn, usuario_id, entidade_id, tipo_id, emissao: str, validade: str, arquivo: str, sha256: str, origem: str, numero: str | None = None) -> int` — histórico: NUNCA apaga a anterior; ValueError pt-BR se validade <= emissao.
  - `certidoes.vigente(conn, entidade_id, tipo_id, na_data: str | None = None) -> dict | None` — responde também "qual valia na data do protocolo X" (spec §5).
  - `certidoes.marcar_estado(conn, usuario_id, certidao_id, estado, observacao) -> None` — estado só 'revogada'|'nao_se_aplica'; 'vencida' é DERIVADO (validade < hoje), nunca gravado.
  - `certidoes.painel(conn) -> list[dict]` — matriz entidade × tipo com semáforo: verde (validade > 15 dias), ambar (<= 15), vermelho (vencida/ausente), cinza (não se aplica).

- [ ] **Step 1: Migração**

```sql
-- backend/migrations/006_certidoes.sql
CREATE TABLE IF NOT EXISTS entidades (
    id INTEGER PRIMARY KEY,
    nome TEXT NOT NULL,
    cnpj TEXT NOT NULL UNIQUE CHECK (length(cnpj) = 14),
    papel TEXT NOT NULL CHECK (papel IN ('lotufo','consorcio','consorciada')),
    ativo INTEGER NOT NULL DEFAULT 1,
    criado_em TEXT NOT NULL DEFAULT (datetime('now'))
);
INSERT OR IGNORE INTO entidades (id, nome, cnpj, papel)
VALUES (1, 'Lotufo Engenharia e Construções Ltda', '00000000000100', 'lotufo');

CREATE TABLE IF NOT EXISTS certidao_tipos (
    id INTEGER PRIMARY KEY,
    nome TEXT NOT NULL,
    jurisdicao TEXT NOT NULL CHECK (jurisdicao IN ('federal','estadual','municipal','trabalhista')),
    emissor TEXT NOT NULL,
    aplicavel_por_padrao INTEGER NOT NULL DEFAULT 1,
    UNIQUE (nome, jurisdicao)
);
INSERT OR IGNORE INTO certidao_tipos (id, nome, jurisdicao, emissor, aplicavel_por_padrao) VALUES
 (1, 'CND Federal (RFB/PGFN)', 'federal', 'Receita Federal / PGFN', 1),
 (2, 'CRF/FGTS', 'federal', 'Caixa Econômica Federal', 1),
 (3, 'CNDT', 'trabalhista', 'TST', 1);

CREATE TABLE IF NOT EXISTS certidoes (
    id INTEGER PRIMARY KEY,
    entidade_id INTEGER NOT NULL REFERENCES entidades(id),
    tipo_id INTEGER NOT NULL REFERENCES certidao_tipos(id),
    numero TEXT,
    emissao TEXT NOT NULL,
    validade TEXT NOT NULL,
    arquivo TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    origem TEXT NOT NULL CHECK (origem IN ('robo','upload')),
    estado TEXT NOT NULL DEFAULT 'vigente' CHECK (estado IN ('vigente','revogada','nao_se_aplica')),
    observacao TEXT,
    criado_em TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_certidoes_ent_tipo ON certidoes (entidade_id, tipo_id, emissao);
```

- [ ] **Step 2: Testes que falham (escrever todos antes de implementar)**

```python
# backend/tests/test_certidoes.py (núcleo; test_entidades.py análogo p/ CRUD + DV do CNPJ)
import datetime
import pytest
from app import auth, certidoes, db, entidades, tempo

@pytest.fixture
def conn(tmp_path, monkeypatch):
    monkeypatch.setenv("DASH_DB_PATH", str(tmp_path / "t.db"))
    c = db.get_conn(); db.migrate(c)
    auth.criar_usuario(c, "U", "u@lotufo.com", "senha-forte-123", "admin")
    yield c
    c.close()

def _reg(conn, ent=1, tipo=1, emissao="2026-08-01", validade="2026-11-01", origem="robo"):
    return certidoes.registrar(conn, 1, ent, tipo, emissao, validade,
                               f"dados/certidoes/{ent}-{tipo}-{emissao}.pdf", "a"*64, origem)

def test_vigente_e_historico(conn, monkeypatch):
    monkeypatch.setattr(tempo, "hoje_local", lambda: datetime.date(2026, 9, 1))
    _reg(conn, emissao="2026-05-01", validade="2026-08-01")
    nova = _reg(conn, emissao="2026-08-01", validade="2026-11-01")
    v = certidoes.vigente(conn, 1, 1)
    assert v["id"] == nova and v["validade"] == "2026-11-01"
    antiga = certidoes.vigente(conn, 1, 1, na_data="2026-07-15")   # qual valia no protocolo X
    assert antiga["emissao"] == "2026-05-01"
    assert conn.execute("SELECT COUNT(*) c FROM certidoes").fetchone()["c"] == 2   # nada apagado

def test_vencida_e_derivada(conn, monkeypatch):
    monkeypatch.setattr(tempo, "hoje_local", lambda: datetime.date(2026, 9, 1))
    _reg(conn, emissao="2026-01-01", validade="2026-02-01")
    assert certidoes.vigente(conn, 1, 1) is None
    linha = [l for l in certidoes.painel(conn) if l["entidade_id"] == 1 and l["tipo_id"] == 1][0]
    assert linha["semaforo"] == "vermelho"

def test_marcar_estado_so_revogada_ou_nao_se_aplica(conn):
    cid = _reg(conn)
    certidoes.marcar_estado(conn, 1, cid, "revogada", "órgão revogou")
    assert certidoes.vigente(conn, 1, 1) is None
    with pytest.raises(ValueError, match="inválido"):
        certidoes.marcar_estado(conn, 1, cid, "vigente", None)

def test_semaforo_ambar_ate_15_dias(conn, monkeypatch):
    monkeypatch.setattr(tempo, "hoje_local", lambda: datetime.date(2026, 10, 20))
    _reg(conn, emissao="2026-08-01", validade="2026-11-01")   # faltam 12 dias
    linha = [l for l in certidoes.painel(conn) if l["tipo_id"] == 1 and l["entidade_id"] == 1][0]
    assert linha["semaforo"] == "ambar"

def test_validade_antes_da_emissao_rejeita(conn):
    with pytest.raises(ValueError, match="validade"):
        _reg(conn, emissao="2026-08-01", validade="2026-07-01")
```

- [ ] **Step 3: Implementar** — padrão da fase 2 (mutações `with db.mutacao`, ValueError pt-BR). Núcleo não-óbvio:

```python
# backend/app/certidoes.py — vigente() e painel()
def vigente(conn, entidade_id, tipo_id, na_data=None):
    na_data = na_data or tempo.hoje_local().isoformat()
    r = conn.execute(
        "SELECT * FROM certidoes WHERE entidade_id=? AND tipo_id=? AND estado='vigente' "
        "AND emissao <= ? AND validade >= ? ORDER BY emissao DESC, id DESC LIMIT 1",
        (entidade_id, tipo_id, na_data, na_data)).fetchone()
    return dict(r) if r else None

def painel(conn):
    hoje = tempo.hoje_local()
    out = []
    for e in entidades.listar(conn):
        for t in tipos(conn):
            v = vigente(conn, e["id"], t["id"])
            nsa = conn.execute(
                "SELECT 1 FROM certidoes WHERE entidade_id=? AND tipo_id=? AND estado='nao_se_aplica' "
                "ORDER BY id DESC LIMIT 1", (e["id"], t["id"])).fetchone()
            if v:
                dias = (datetime.date.fromisoformat(v["validade"]) - hoje).days
                sem = "verde" if dias > 15 else "ambar"
            elif nsa:
                sem = "cinza"
            else:
                sem = "vermelho"
            out.append({"entidade_id": e["id"], "entidade": e["nome"], "papel": e["papel"],
                        "tipo_id": t["id"], "tipo": t["nome"], "jurisdicao": t["jurisdicao"],
                        "semaforo": sem, "vigente": v})
    return out
```

`nao_se_aplica` é registrado como linha de certidão SEM arquivo real (arquivo='—', sha256 64 zeros, emissao=validade=data do registro, estado='nao_se_aplica') — mantém auditável QUEM decidiu. DV do CNPJ: algoritmo padrão dos 2 dígitos verificadores em `entidades._cnpj_valido`, ValueError "CNPJ inválido".

- [ ] **Step 4: `pytest -q` completo → verdes. Commit** — `feat: entidades e certidoes (historico, vigente na data, semaforo)`

---

### Task 4: API de entidades/certidões + upload de PDF

**Files:**
- Create: `backend/app/api_certidoes.py`; Modify: `backend/app/main.py` (include router)
- Test: `backend/tests/test_api_certidoes.py`

**Interfaces:**
- Consumes: T3; `exigir`, `conexao`; a permissão de admin da fase 1 (conferir o nome exato em `app/permissoes.py` — a matriz da fase 1 chama a permissão de administração de usuários; usar a MESMA para config de certidões, spec dec. 10).
- Produces (T8/T9 consomem):
  - `GET /api/certidoes` → painel (ver_paineis, sem CSRF)
  - `GET /api/certidoes/{id}/arquivo` → PDF (ver_paineis; FileResponse; 404)
  - `POST /api/certidoes/upload` (multipart: arquivo, entidade_id, tipo_id, emissao, validade, numero?; editar_cadastros) → 201 {id}
  - `POST /api/certidoes/{id}/estado` {estado, observacao?} (admin)
  - `GET /api/entidades` (ver_paineis) · `POST /api/entidades` · `POST /api/entidades/{id}/desativar` (admin)
  - `GET /api/certidoes/tipos` (ver_paineis) · `POST /api/certidoes/tipos` (admin)
- Upload endurecido (padrões dos gates da fase 2): content-type `application/pdf` E magic bytes `%PDF-` conferidos; teto 10 MB lido em stream; nome em disco = `dados/certidoes/{sha256}.pdf` (NUNCA o nome do cliente; dedupe por conteúdo); emissao/validade `datetime.date` no Pydantic; `numero` max_length=100; 404 antes do repositório; rollback antes de 422.

- [ ] **Step 1: Testes que falham** — fluxo feliz (upload → painel mostra vigente → download bate sha); 415 p/ magic bytes errados (txt renomeado); 413 p/ 11 MB; 403 (upload sem editar_cadastros; estado/entidades/tipos sem admin); 404s; dedupe (mesmo PDF 2x → 2 certidões, 1 arquivo em disco); validade < emissao → 422 pt-BR.
- [ ] **Step 2: Implementar o router** — seguir `api_medicoes.py` como referência de forma; upload com `UploadFile`, hash incremental (`hashlib.sha256` por chunks de 64 KB com teto), `Path("dados/certidoes")` criada com `mkdir(parents=True, exist_ok=True)`.
- [ ] **Step 3: `pytest -q` → verdes. Commit** — `feat: API de certidoes com upload endurecido e painel`

---

### Task 5: Robô das federais (worker semanal)

**Files:**
- Create: `backend/app/robo_certidoes.py`; Modify: `backend/app/main.py` (agendamento no padrão do backup da fase 1, sob `DASH_SEM_JOBS`), `backend/pyproject.toml` (dep `pypdf` pinada)
- Test: `backend/tests/test_robo_certidoes.py`

**Interfaces:**
- Consumes: `certidoes.registrar/vigente` (T3), `httpx` (já presente), `pypdf`.
- Produces: `robo_certidoes.rodar(conn, transport=None) -> dict` — para cada entidade ativa × tipo federal aplicável SEM vigente com folga (> 15 dias): tenta o adaptador; sucesso → salva PDF (gravação `.tmp`→rename, padrão do backup) + `certidoes.registrar(origem='robo')`; falha → acumula `{"entidade", "tipo", "erro"}` pt-BR SEM travar os demais. Retorna `{"emitidas": n, "avisos": [...]}` (T7 transforma avisos em alertas). `transport` injetável (`httpx.MockTransport`) — zero rede na suíte.
- Adaptadores (protocolo interno único `emitir(cnpj, http) -> tuple[bytes, str]` → (pdf, validade ISO)):
  1. **CNDT/TST** — emissão direta por CNPJ em `cndt-certidao.tst.jus.br` (historicamente sem captcha); validade por regex no texto do PDF (pypdf): `r"VALIDADE:?\s*(\d{2}/\d{2}/\d{4})"` normalizada p/ ISO.
  2. **CRF/FGTS (Caixa)** — `consulta-crf.caixa.gov.br` por CNPJ → PDF do CRF; validade idem.
  3. **CND RFB/PGFN** — tentativa pelo serviço público de emissão; é o mais sujeito a captcha/mudança — quando recusar, falha LIMPA com aviso "emissão manual necessária (RFB/PGFN)".
- ⚠️ Realidade externa (docstring obrigatória): os 3 serviços mudam sem aviso. O implementador faz UMA chamada real de verificação por serviço (CNPJ da Lotufo) FORA da suíte, via `python -m app.robo_certidoes --uma-vez`, ajusta o parsing ao observado e DOCUMENTA no relatório o que cada serviço devolveu. Serviço com captcha → adaptador vira fallback-only (sempre aviso). O contrato do sistema é: robô nunca é a única via — o upload manual (T4) sempre existe.

- [ ] **Step 1: Testes que falham (MockTransport)**

```python
# backend/tests/test_robo_certidoes.py (núcleo)
import httpx
from app import certidoes, robo_certidoes

def _pdf_com_texto(texto):
    # PDF mínimo de 1 página gerado à mão (template bytes com o texto embutido no
    # content stream) — helper no próprio teste, sem dependência nova.
    ...

def _transport(mapa):
    def handler(request):
        for chave, resposta in mapa.items():
            if chave in str(request.url):
                return resposta
        return httpx.Response(404)
    return httpx.MockTransport(handler)

def test_emite_e_registra(conn):
    pdf = _pdf_com_texto("CERTIDAO NEGATIVA ... VALIDADE: 28/02/2027")
    t = _transport({"tst.jus.br": httpx.Response(200, content=pdf,
                                                 headers={"content-type": "application/pdf"})})
    r = robo_certidoes.rodar(conn, transport=t)
    assert r["emitidas"] >= 1
    v = certidoes.vigente(conn, 1, 3)
    assert v and v["origem"] == "robo" and v["validade"] == "2027-02-28"

def test_falha_de_um_servico_nao_trava_os_demais(conn):
    t = _transport({"tst.jus.br": httpx.Response(500)})
    r = robo_certidoes.rodar(conn, transport=t)
    assert any("CNDT" in a["tipo"] for a in r["avisos"])
    assert "manual" in r["avisos"][0]["erro"]

def test_nao_reemite_com_folga(conn):
    # vigente com validade > 15 dias -> o par entidade x tipo nem chama o serviço
    ...

def test_pdf_invalido_vira_aviso(conn):
    t = _transport({"tst.jus.br": httpx.Response(200, content=b"<html>erro</html>")})
    r = robo_certidoes.rodar(conn, transport=t)
    assert r["emitidas"] == 0 and r["avisos"]
```

- [ ] **Step 2: Implementar** — laço entidade×tipo, adaptadores, `pypdf.PdfReader(BytesIO(pdf)).pages[*].extract_text()`, magic bytes `%PDF-` antes de tudo, `tempo` para datas, `--uma-vez` como `__main__` p/ a verificação manual.
- [ ] **Step 3: Agendar** — em `create_app`, seguir EXATAMENTE o mecanismo do backup horário da fase 1 (mesma primitiva de agendamento em `main.py`), período semanal, sob `DASH_SEM_JOBS`.
- [ ] **Step 4: Verificação real única por serviço (fora da suíte)** + ajuste do parsing + documentação no relatório.
- [ ] **Step 5: `pytest -q` → verdes. Commit** — `feat: robo semanal das certidoes federais com fallback manual`

---

### Task 6: Extração de metadados por IA no upload (admin-only)

Primeira chamada de IA do produto (§14). Regra do §14.1 na prática: IA aponta, código valida, humano confirma — a rota devolve SUGESTÃO de preenchimento, nunca grava.

**Files:**
- Create: `backend/app/ia_extracao.py`, migração `backend/migrations/007_ia_chamadas.sql`; Modify: `backend/app/api_certidoes.py` (rota extrair), `backend/pyproject.toml` (dep `anthropic` pinada)
- Test: `backend/tests/test_ia_extracao.py`

**Interfaces:**
- Consumes: pypdf (T5), `db.mutacao` (T1), `tempo` (T2).
- Produces:
  - `ia_extracao.extrair_certidao(conn, usuario_id, texto_pdf: str, cliente=None) -> dict` — chama a API do Claude (modelo `claude-haiku-4-5`, prompt fixo versionado no módulo) pedindo `{tipo, emissor, numero, emissao, validade, cnpj}` com evidência verbatim por campo; **validador determinístico** em seguida: datas parseáveis com validade > emissao; CNPJ (14 dígitos) presente LITERALMENTE no texto; validade re-localizada literal (dd/mm/aaaa OU aaaa-mm-dd no texto); campo reprovado → null + motivo. Registra a chamada em `ia_chamadas` (modelo, tokens in/out, custo estimado em centavos, usuario_id, finalidade='certidao_upload'). `cliente` injetável p/ teste (objeto com `.messages.create`).
  - Rota: `POST /api/certidoes/extrair` (multipart: arquivo PDF) — **`exigir` ADMIN** (regra do §14.5: ação com custo = só admin); sem `DASH_ANTHROPIC_KEY` no ambiente → 503 `{"detail": "Chave de IA não configurada — preencha manualmente ou configure DASH_ANTHROPIC_KEY"}`; resposta 200: `{"sugestao": {campos...}, "avisos": [motivos de campo reprovado], "custo_centavos": n}`.
  - `GET /api/ia/chamadas` (admin) — últimas 100, com totais do mês (a administração da T8 exibe).

```sql
-- backend/migrations/007_ia_chamadas.sql
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
```

- [ ] **Step 1: Testes que falham (cliente mockado — a suíte NUNCA chama a API real)**

```python
# backend/tests/test_ia_extracao.py (núcleo)
import pytest
from app import ia_extracao

class _ClienteFake:
    def __init__(self, resposta_json): self._r = resposta_json
    class _Msgs:
        def __init__(self, outer): self.outer = outer
        def create(self, **kw):
            class R:  # shape mínimo da resposta da SDK
                content = [type("B", (), {"text": None})()]
                usage = type("U", (), {"input_tokens": 800, "output_tokens": 120})()
            R.content[0].text = self.outer._r
            return R
    @property
    def messages(self): return self._Msgs(self)

TEXTO = "CERTIDAO NEGATIVA DE DEBITOS TRABALHISTAS ... CNPJ: 00.000.000/0001-00 ... Expedição: 01/09/2026 ... Validade: 28/02/2027 ..."

def test_extrai_e_valida(conn):
    fake = _ClienteFake('{"tipo":"CNDT","emissor":"TST","numero":"12345/2026","emissao":"2026-09-01","validade":"2027-02-28","cnpj":"00000000000100"}')
    r = ia_extracao.extrair_certidao(conn, 1, TEXTO, cliente=fake)
    assert r["sugestao"]["validade"] == "2027-02-28" and r["sugestao"]["cnpj"] == "00000000000100"
    assert conn.execute("SELECT COUNT(*) c FROM ia_chamadas").fetchone()["c"] == 1

def test_validador_derruba_data_nao_localizada(conn):
    fake = _ClienteFake('{"tipo":"CNDT","emissor":"TST","numero":null,"emissao":"2026-09-01","validade":"2027-06-30","cnpj":"00000000000100"}')
    r = ia_extracao.extrair_certidao(conn, 1, TEXTO, cliente=fake)   # 30/06/2027 NÃO está no texto
    assert r["sugestao"]["validade"] is None
    assert any("validade" in a for a in r["avisos"])

def test_validador_derruba_cnpj_ausente(conn):
    fake = _ClienteFake('{"tipo":"CNDT","emissor":"TST","numero":null,"emissao":"2026-09-01","validade":"2027-02-28","cnpj":"00000000000200"}')
    r = ia_extracao.extrair_certidao(conn, 1, TEXTO, cliente=fake)
    assert r["sugestao"]["cnpj"] is None

def test_rota_sem_chave_503(client_admin, monkeypatch):
    monkeypatch.delenv("DASH_ANTHROPIC_KEY", raising=False)
    r = client_admin.post("/api/certidoes/extrair", files={"arquivo": ("c.pdf", b"%PDF-...", "application/pdf")})
    assert r.status_code == 503 and "não configurada" in r.json()["detail"]

def test_rota_exige_admin(client_engenharia_ou_equivalente):
    # perfil engenharia -> 403 (regra: custo externo = admin-only)
    ...
```

- [ ] **Step 2: Implementar** — prompt fixo (pt-BR, instrução "só o literal, ausente = null, evidência verbatim por campo"); resposta com `response_format` textual JSON parseado com fallback de erro pt-BR; custo estimado por tabela de preço no módulo (constante comentada com data); `db.mutacao` no INSERT de `ia_chamadas`. A rota extrai o texto com pypdf (mesmos magic bytes/teto do upload da T4) e NÃO persiste o PDF (só o upload da T4 persiste).
- [ ] **Step 3: `pytest -q` → verdes. Commit** — `feat: extracao de metadados de certidao por IA (admin-only, validador literal)`

---

### Task 7: Alertas de certidão + checklist "pronto para protocolar"

**Files:**
- Modify: `backend/app/paineis.py` (tipos novos de alerta), `backend/app/api_paineis.py` (nada estrutural — alertas já fluem), `backend/migrations/008_contrato_entidade.sql`, `backend/app/contratos.py` (campo entidade_id), `backend/app/api_contratos.py` (aceitar entidade_id opcional)
- Create: `backend/app/checklist.py`, rota em `backend/app/api_certidoes.py`
- Test: `backend/tests/test_checklist.py`, ajustes em `backend/tests/test_paineis.py`

**Interfaces:**
- Consumes: `certidoes.vigente/painel` (T3), avisos do robô (T5 — persistidos? NÃO: o robô roda e devolve; os avisos viram alertas DERIVADOS: certidão ausente/vencida já aparece pelo estado do banco; aviso de serviço fora só aparece no log/admin. Decisão registrada: alerta = estado do banco, não memória do robô).
- Produces:
  - Migração 008: `ALTER TABLE contratos ADD COLUMN entidade_id INTEGER REFERENCES entidades(id) DEFAULT 1` (guarded: checar coluna antes via PRAGMA no runner — convenção de idempotência da fase 1). Default 1 = Lotufo; obras de consórcio apontam para a entidade do consórcio.
  - `paineis.alertas` ganha: `certidao_vencendo` (validade da vigente <= 15 dias, por entidade COM contrato ativo) e `certidao_vencida_ou_ausente` (tipo aplicável sem vigente hoje, idem) — mensagens pt-BR com entidade + tipo.
  - `checklist.pronto_para_protocolar(conn, contrato_id) -> dict` — para a entidade do contrato: cada tipo aplicável com `{tipo, situacao: 'ok'|'vencendo'|'pendente', validade?}` + `pronto: bool` (todos ok/vencendo — vencendo conta como ok mas aparece com aviso). Rota: `GET /api/contratos/{id}/checklist-protocolo` (ver_paineis; 404).

- [ ] **Step 1: Testes que falham** — checklist com 3 federais vigentes → pronto true; uma vencida → pronto false com o tipo apontado; entidade de consórcio usa as certidões DELA; alertas novos aparecem em `paineis.alertas` só para entidades com contrato ativo (entidade sem contrato não polui o painel); teste de idempotência da migração 008 (rodar migrate 2x).
- [ ] **Step 2: Implementar** — `checklist.py` pequeno e puro; alertas seguindo o padrão de mensagens acentuadas (fase 2 T11).
- [ ] **Step 3: `pytest -q` → verdes. Commit** — `feat: alertas de certidao e checklist pronto-para-protocolar`

---

### Task 8: Frontend — tela de Certidões (+ custo de IA na Administração)

**Files:**
- Create: `frontend/src/Certidoes.tsx`; Modify: `frontend/src/App.tsx` (nav item), `frontend/src/Admin.tsx` (bloco "Uso de IA": total do mês + últimas chamadas), `frontend/src/tokens.css` (apenas o que faltar — reusar)
- Test: `npx tsc --noEmit; npm run build` + verificação em navegador com banco descartável

**Interfaces:**
- Consumes: rotas T4/T6; padrões incumbentes (agir/gravou, foco, role=alert, guarda de geração, DESIGN.md).
- Produces: `Certidoes({usuario})` — matriz entidade × tipo com semáforo (verde/âmbar/vermelho/cinza — SEMPRE ponto + rótulo, nunca só cor, regra do DESIGN.md), origem (robô/upload), download, e:
  - formulário de upload (entidade, tipo, número, emissão, validade, arquivo) p/ editar_cadastros;
  - botão "Preencher com IA a partir do PDF" — visível SÓ para admin; desabilitado com explicação quando 503 (chave ausente); ao responder, PREENCHE os campos do formulário com a sugestão + mostra avisos de campo reprovado; o usuário revisa e submete o upload normal;
  - ações admin: revogar / não se aplica (com observação), gestão de entidades (nome, CNPJ, papel) e de tipos (nome, jurisdição, emissor).
- Sem prompt()/alert(); formulários inline; semáforo âmbar = chip claro (regra da fase 2: âmbar sólido é proibido).

- [ ] **Step 1: Implementar a tela** (referência de forma: Sugestoes.tsx p/ tabela+formulário; PainelGeral p/ chips).
- [ ] **Step 2: Admin.tsx — bloco Uso de IA** (GET /api/ia/chamadas): total do mês em R$, tabela das últimas chamadas (quando, quem, finalidade, modelo, custo).
- [ ] **Step 3: Verificar** — tsc/build limpos; navegador em banco descartável: upload manual, botão IA (com e sem chave — mockar 503 parando o backend var), semáforos, downloads, telas por perfil (diretoria só lê; engenharia sem botão IA; admin completo). NÃO derrubar servidores 8080/5173 do controller.
- [ ] **Step 4: Commit** — `feat: tela de certidoes com semaforo, upload assistido por IA e custo na administracao`

---

### Task 9: Frontend — checklist na página do contrato + alertas no painel

**Files:**
- Modify: `frontend/src/ContratoPagina.tsx` (aba/bloco "Protocolo"), `frontend/src/PainelGeral.tsx` (só se os tipos novos precisarem de rótulo/nível próprios na tabela ALERTAS — são aditivos)

**Interfaces:**
- Consumes: `GET /api/contratos/{id}/checklist-protocolo` (T7); alertas novos já fluem pela rota existente.
- Produces: bloco "Pronto para protocolar?" na página do contrato: lista tipo a tipo com situação (ok/vencendo/pendente, ponto+rótulo) e o veredito no topo ("Pronto" verde / "Pendências" vermelho); link "ver certidões" navega à tela da T8.

- [ ] **Step 1: Implementar** (guarda de geração por contratoId como nas demais abas).
- [ ] **Step 2: Registrar os 2 tipos novos na tabela ALERTAS do PainelGeral** (vencida_ou_ausente = nível ação; vencendo = atenção).
- [ ] **Step 3: tsc/build + navegador; Commit** — `feat: checklist de protocolo no contrato e alertas de certidao no painel`

---

### Task 10: Lote de polimento de UI da fase 2 + passe visual + finish review

O lote que a revisão final da fase 2 triou como "fase 3". Trabalho mecânico primeiro, auditoria visual depois.

**Files:**
- Modify: `frontend/src/ContratoPagina.tsx` (tabs com setas ←→, padrão ARIA), `frontend/src/App.tsx` (aria-disabled + describedby no lugar de title em botão desabilitado — se algum restou), `frontend/src/tokens.css` (ellipsis real no .selo: envolver o texto num span interno com overflow — ajuste estrutural pequeno no componente que o usa; sombra literal do botão → var(--sombra)), `frontend/src/Medicoes.tsx` (form de protocolo ganha campo opcional numero_processo — minor da revisão final; th scope já foi), `frontend/src/PainelGeral.tsx` (o que o passe visual apontar)
- Test: tsc/build + detect.mjs COMPLETO (a wave do gate 3 rodou degradado)

- [ ] **Step 1: Aplicar os itens mecânicos listados** (cada um é 1-10 linhas; TDD não se aplica — verificação por tsc/build/leitura).
- [ ] **Step 2: `node <skill impeccable>/scripts/detect.mjs --json` nos arquivos alterados** — resolver o que for mecânico.
- [ ] **Step 3: PASSE VISUAL (controller, painel do navegador visível)**: capturas desktop+mobile das 5 telas (painel, sugestões, contrato/medições, cronograma, certidões) em `.impeccable/review/`; fumaça manual completa (importar → aceitar → valor → protocolo → atestar → curva → certidão → checklist → CSVs).
- [ ] **Step 4: Finish reviewer da impeccable** (subagente novo com o pacote: pedido original, contrato de direção design-direction.md, DESIGN.md, capturas, craft-floor) → disposition; fix round se material; re-run do documenter se a superfície mudar.
- [ ] **Step 5: Commit** — `fix: lote de polimento de UI da fase 2 + achados do passe visual`

---

### Task 11: Varredura final da fase 3

**Files:**
- Modify: `README.md` (tela de Certidões + robô + variável DASH_ANTHROPIC_KEY documentada; fase 3 entregue)

- [ ] **Step 1: Suíte completa** — `cd backend; .venv\Scripts\python -m pytest -q` → verde.
- [ ] **Step 2: Frontend** — `npx tsc --noEmit; npm run build` limpos.
- [ ] **Step 3: Fumaça manual** — coberta no Step 3 da T10 (não repetir; se a T10 rodou antes de T11 por mais de 2 dias, repetir só o fluxo de certidões).
- [ ] **Step 4: README + commit** — `docs: fase 3 entregue (certidoes, robo, checklist, dividas estruturais)`

---

## Self-Review (executado na escrita do plano)

1. **Cobertura da spec**: §1.6/§3-8/§4-robô ✓ (T3-T5); §5 Certidão (histórico, estados, "qual valia na data") ✓ (T3); §7 tela 6 (tabela semáforo/origem/download) ✓ (T8); §7 tela 2 (avisos urgentes de certidões) ✓ (T7/T9); §12 fase 3 (cadastro extensível + robô + alertas + checklist) ✓ (T3/T5/T7); §14.4 fase 3 (IA nos metadados como sugestão no formulário) ✓ (T6/T8); §14.5 (admin-only + log de custo + degradação sem chave) ✓ (T6/T8); dívidas com prazo da revisão final da fase 2 ✓ (T1/T2/T10). "Montagem do pacote" de protocolo fica para a fase 7 (pacote de protocolo, §12) — fase 3 entrega o checklist, conforme §12.
2. **Placeholders**: os `...` que restam são SÓ em corpos de teste cuja mecânica está descrita ao lado (helper de PDF fake, teste de não-reemissão, 403 por perfil) — o implementador tem o contrato exato; nenhum "TBD"/"depois".
3. **Consistência de tipos**: `db.mutacao`/`registrar` (T1) usados em T3-T7; `tempo.hoje_local` (T2) em T3/T7; `certidoes.registrar(..., origem)` idêntico em T4 (upload) e T5 (robô); `painel()` shape idêntico no consumo da T8; checklist shape T7→T9. ✓

## Workflow de Execução Multi-Modelo (mantido da fase 2)

Orquestrador: sessão principal. Implementadores: Opus (1 subagente novo por task). Revisores de conformidade + revisão final: **Fable 5**. Re-reviews scoped: Opus. Gates adversariais (GPT-5.6 Sol via codex exec, diff no stdin): **após T1** (o rework transacional é o código mais sensível da fase), **após T6** (robô + IA = superfície externa nova) e **após T10** (frontend completo), sempre `--base` no commit do gate anterior. Achados triados pelo controller contra o código antes de qualquer fix.
