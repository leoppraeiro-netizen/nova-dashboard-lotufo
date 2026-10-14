# Fase 0 (Inventário e Provas) + Fase 1 (Fundação) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Provar os três condutos externos (RM, detecção Outlook, regras do Power Automate) e construir a fundação da dashboard: backend FastAPI + SQLite endurecido, login com perfis/permissões, log de auditoria com hash encadeado, cadastro de obras/contratos com estados e aditivos-delta, frontend React com login e telas de contrato/administração, HTTPS interno e snapshot horário de backup.

**Architecture:** Um produto: backend Python (FastAPI) servindo API + frontend React buildado, banco SQLite (WAL, FK, busy_timeout, escrita serializada), sem ORM (SQL explícito + repositórios), migrações por arquivos SQL numerados. Auth por sessão server-side (cookie HttpOnly/Secure/SameSite=Strict + CSRF token), senhas argon2, permissões verificadas no servidor. Auditoria append-only com hash encadeado. Dinheiro em centavos inteiros.

**Tech Stack:** Python 3.12+, FastAPI, uvicorn, argon2-cffi, pytest, httpx; React 18 + Vite + TypeScript; SQLite 3 (stdlib `sqlite3`); PowerShell para spikes RM.

**Spec:** `docs/superpowers/specs/2026-08-28-dashboard-contratos-medicoes-design.md` (v3)

## Global Constraints

- Python 3.12+; dependências backend limitadas a: fastapi, uvicorn, argon2-cffi, httpx (dev), pytest (dev).
- SQLite sempre aberto com `journal_mode=WAL`, `busy_timeout=5000`, `foreign_keys=ON` (spec §4).
- Dinheiro SEMPRE em **centavos inteiros** (`int`); nunca float (spec dec. 15).
- Senhas com **argon2**; sessões server-side; cookies `HttpOnly; Secure; SameSite=Strict`; CSRF token em toda mutação (spec §10).
- Toda autorização verificada **no servidor** por permissão, nunca só na UI (spec §10).
- Log de auditoria é **append-only com hash encadeado** — nenhum UPDATE/DELETE na tabela (spec §5).
- Sem exclusão física de registros financeiros/contratuais — estados, não DELETE (spec §5).
- Valor vigente do contrato = original + **deltas** de aditivos assinados, em ordem de assinatura — sempre calculado, nunca gravado por cima (spec §5).
- Scripts `.ps1` com acentos: gravar em **UTF-8 com BOM** (instrução global do usuário).
- Textos da interface em **português brasileiro**.
- Commits frequentes; mensagens `feat:/fix:/test:/docs:/chore:` + rodapé `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.
- Working dir do projeto: `C:\Users\<usuario>\Nova Dashboard Lotufo` (repo git já iniciado).

**Nota de execução:** Tarefas 2, 3 e 4 (spikes da Fase 0) exigem recursos da sessão principal (MCP do Outlook, participação do Leonardo). Devem ser executadas **inline na sessão principal**, não por subagente. Tarefas 5+ são código puro e funcionam em qualquer modo.

---

### Task 1: Estrutura do repositório

**Files:**
- Create: `.gitignore`, `README.md`, `backend/` e `docs/superpowers/research/` (diretórios)

**Interfaces:**
- Produces: layout de pastas usado por todas as tarefas seguintes: `backend/app/`, `backend/tests/`, `backend/migrations/`, `frontend/`, `docs/superpowers/research/`.

- [ ] **Step 1: Criar .gitignore**

```gitignore
# Python
__pycache__/
*.pyc
.venv/
.pytest_cache/
# Node
node_modules/
frontend/dist/
# Dados locais (nunca commitar banco/segredos/backups)
dados/
*.db
*.db-wal
*.db-shm
backups/
certs/
.env
```

- [ ] **Step 2: Criar README.md**

```markdown
# Dashboard de Contratos e Medições — Lotufo

Sistema interno de gestão de contratos de obras públicas e ciclos de medição.

- Spec: `docs/superpowers/specs/2026-08-28-dashboard-contratos-medicoes-design.md`
- Planos: `docs/superpowers/plans/`
- Pesquisas (spikes): `docs/superpowers/research/`

## Rodar em desenvolvimento

```
cd backend
.venv\Scripts\python -m uvicorn app.main:app --reload --port 8080
```

Testes: `cd backend && .venv\Scripts\python -m pytest`
```

- [ ] **Step 3: Criar diretórios vazios com .gitkeep**

Criar: `backend/app/.gitkeep`, `backend/tests/.gitkeep`, `backend/migrations/.gitkeep`, `docs/superpowers/research/.gitkeep`.

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "chore: estrutura inicial do repositorio"
```

---

### Task 2: Spike de detecção — padrões de assunto contra o histórico real do Outlook

**⚠ Executar inline na sessão principal (usa MCP do Outlook).**

**Files:**
- Create: `docs/superpowers/research/2026-08-spike-deteccao-outlook.md`

**Interfaces:**
- Produces: documento com (a) as regex de assunto validadas, (b) precisão medida por categoria, (c) recomendação auto-aplicar × sugerir por categoria. A fase 6 implementará exatamente essas regex.

- [ ] **Step 1: Definir as regex candidatas (base: e-mails já observados na caixa)**

```python
# Padrões candidatos (case-insensitive), a validar contra o histórico:
PROTOCOLO_MEDICAO = r"(?P<oficio>CT[-/ ]?\d+[-/ ]?(?:LT|CO)[-/ ]?\d{4}).{0,10}?(?P<num>\d+)ª[_ ]?Medi[çc][ãa]o[_ ]?\((?P<comp>\d{2}[_/]\d{4})\).*?(?P<ic>IC\s*n?[º°]?\s*\d+[_/]\d{4}|CT\s*\d+[_/]\d{4})"
EMISSAO_NF       = r"Emiss[ãa]o NF.*?(?P<num>\d+)ª\s*Medi[çc][ãa]o.*?\((?P<comp>\d{2}/\d{4})\)"
FRC_RECEBIDA     = r"FRC\s*(?:N[º°]\s*)?(?P<nums>[\dE ]+)[-–]\s*CONS[ÓO]RCIO\s+(?P<consorcio>.+?)\s*\("
```

- [ ] **Step 2: Buscar o histórico por categoria no Outlook (MCP `outlook_email_search`)**

Para cada categoria, buscar amostra ampla (mínimo 30 e-mails ou tudo que existir): query `"Medição"` em enviados (protocolos), `"Emissão NF"` (espelhos), `"FRC"` (consórcio). Paginar com `nextOffset` até esgotar ou atingir 50 por categoria.

- [ ] **Step 3: Medir precisão**

Para cada e-mail da amostra, aplicar a regex da categoria ao assunto e classificar: extraiu todos os campos / extraiu parcial / não casou / casou mas era falso positivo. Montar tabela por categoria: total, casados, precisão de extração por campo (nº medição, competência, contrato, ofício).

- [ ] **Step 4: Escrever o documento de pesquisa**

Estrutura obrigatória do `2026-08-spike-deteccao-outlook.md`: (1) amostra usada (períodos, quantidades); (2) regex finais ajustadas com exemplos reais casados; (3) tabela de precisão; (4) falsos positivos/negativos encontrados e por quê; (5) recomendação por categoria: `auto-aplicar` (precisão ≥ 98% e campo completo) ou `sugerir com clique` (abaixo disso); (6) recomendações de disciplina de assunto para a equipe.

- [ ] **Step 5: Commit**

```bash
git add docs/superpowers/research/ && git commit -m "docs: spike de deteccao de e-mails - padroes e precisao"
```

---

### Task 3: Spike RM — provar o conduto API + Consulta SQL fim a fim

**⚠ Executar inline na sessão principal, COM o Leonardo (login RM dele; cadastro de consulta na interface do RM).**

**Files:**
- Create: `docs/superpowers/research/2026-08-spike-rm.md`
- Create: `scripts/spike_rm.ps1` (UTF-8 com BOM)

**Interfaces:**
- Produces: documento respondendo as 5 perguntas do spike (spec §12 fase 0); formato de autenticação da API validado. A fase 5 será desenhada sobre essas respostas.

- [ ] **Step 1: Leonardo cadastra a consulta de teste no RM**

Na interface do RM (Gestão > Consultas SQL), cadastrar consulta com código `DASH01`, coligada 0 (global), sistema `G` (Global), sentença:

```sql
SELECT CODCOLIGADA, NOMEFANTASIA FROM GCOLIGADA ORDER BY CODCOLIGADA
```

Anotar: código exato, coligada e sistema usados no cadastro (a URL da API usa os três).

- [ ] **Step 2: Executar a consulta pela API**

Criar `scripts/spike_rm.ps1` (UTF-8 com BOM). Credenciais pedidas em tempo de execução — nunca gravadas:

```powershell
$cred = Get-Credential -Message "Usuário RM"
$pair = "$($cred.UserName):$($cred.GetNetworkCredential().Password)"
$auth = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($pair))
$r = Invoke-RestMethod -Uri "http://<servidor-rm>:<porta-da-api>/api/framework/v1/consultaSQLServer/RealizaConsulta/DASH01/0/G" -Headers @{Authorization = "Basic $auth"}
$r | ConvertTo-Json -Depth 5
```

Expected: JSON com as 23 coligadas. Se 401: revisar usuário; se 404: revisar código/coligada/sistema na URL.

- [ ] **Step 3: Cadastrar e executar as consultas de investigação**

Com o conduto provado, cadastrar no RM (mesmo procedimento) e executar uma a uma:

```sql
-- DASH02: NFs recentes existem? Campos disponíveis? (TMOV = movimentos)
SELECT TOP 50 IDMOV, CODCOLIGADA, NUMEROMOV, SERIE, DATAEMISSAO, VALORBRUTO,
       CODTMV, STATUS, CAMPOLIVRE1, CAMPOLIVRE2, CAMPOLIVRE3, HISTORICOLONGO = ''
FROM TMOV WHERE CODTMV LIKE '2.%' ORDER BY DATAEMISSAO DESC

-- DASH03: financeiro dá baixa? parciais/estornos?
SELECT TOP 50 F.IDLAN, F.CODCOLIGADA, F.NUMERODOCUMENTO, F.VALORORIGINAL,
       F.STATUSLAN, F.DATABAIXA, F.VALORBAIXADO
FROM FLAN F WHERE F.PAGREC = 1 ORDER BY F.DATAVENCIMENTO DESC

-- DASH04: NFs das coligadas-consórcio existem?
SELECT CODCOLIGADA, COUNT(*) AS QTDE, MAX(DATAEMISSAO) AS ULTIMA
FROM TMOV WHERE CODTMV LIKE '2.%' GROUP BY CODCOLIGADA
```

(Nomes de colunas podem variar por versão do RM — ajustar conforme erro retornado e registrar os nomes reais no documento.)

- [ ] **Step 4: Escrever o documento de pesquisa**

`2026-08-spike-rm.md` responde obrigatoriamente: (1) formato de auth e URL que funcionaram; (2) o financeiro dá baixa no RM? há baixa parcial (`VALORBAIXADO < VALORORIGINAL`) e estorno?; (3) que campo da NF pode carregar o nº da medição (campo livre? histórico?) — existe hoje algum preenchido?; (4) as coligadas-consórcio emitem NF (DASH04)?; (5) esquema real (nomes de tabelas/colunas confirmados) para as consultas definitivas da fase 5; (6) tipos de movimento (CODTMV) que representam NF de serviço na Lotufo.

- [ ] **Step 5: Commit**

```bash
git add docs/superpowers/research/ scripts/ && git commit -m "docs: spike RM - conduto API provado e esquema real mapeado"
```

---

### Task 4: Inventário das regras do Power Automate

**⚠ Executar inline na sessão principal, com acesso do Leonardo ao Power Automate (navegador).**

**Files:**
- Create: `docs/superpowers/research/2026-08-inventario-power-automate.md`

**Interfaces:**
- Produces: tabela de decisão completa das regras fiscais (por obra) e de rateio (por consórcio). As fases 7–8 implementam exatamente estas regras; a migration de regras fiscais (fase 7) valida que o modelo do §5 da spec cobre 100% desta tabela.

- [ ] **Step 1: Abrir make.powerautomate.com com a conta do Leonardo e listar todos os fluxos**

Registrar nome, estado (ativo/falhando) e função aparente de cada fluxo relacionado a espelho/FRC/medição.

- [ ] **Step 2: Para cada fluxo, abrir a definição e extrair as regras**

Para cada obra/consórcio coberto: percentuais de split MO×materiais, alíquotas (INSS/ISSQN/IRRF e quaisquer outras), bases de cálculo, deduções, condicionais ("se obra X então..."), arredondamentos, numeração de FRC, participações das consorciadas. Capturar screenshot/print do branch de origem de cada regra.

- [ ] **Step 3: Escrever a tabela de decisão**

Formato por linha: `escopo (obra/consórcio) | regra | parâmetros | origem (fluxo/branch) | observações`. Seção final obrigatória: **"Regras que NÃO cabem no modelo da spec §5"** (vazia ou não — é o teste de cobertura do modelo antes da primeira migration de regras fiscais).

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/research/ && git commit -m "docs: inventario das regras do Power Automate"
```

---

### Task 5: Backend scaffold — FastAPI + pytest funcionando

**Files:**
- Create: `backend/pyproject.toml`, `backend/app/__init__.py`, `backend/app/main.py`, `backend/tests/__init__.py`, `backend/tests/conftest.py`, `backend/tests/test_health.py`

**Interfaces:**
- Produces: `create_app() -> FastAPI` em `app.main`; fixture pytest `client` (httpx TestClient); endpoint `GET /api/health` → `{"status": "ok"}`.

- [ ] **Step 1: Criar ambiente e instalar dependências**

```powershell
cd backend
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install fastapi uvicorn argon2-cffi httpx pytest
```

- [ ] **Step 2: Criar pyproject.toml**

```toml
[project]
name = "dashboard-lotufo"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = ["fastapi", "uvicorn", "argon2-cffi"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 3: Escrever o teste que falha**

`backend/tests/conftest.py`:

```python
import pytest
from fastapi.testclient import TestClient
from app.main import create_app

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DASH_DB_PATH", str(tmp_path / "test.db"))
    app = create_app()
    with TestClient(app) as c:
        yield c
```

`backend/tests/test_health.py`:

```python
def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
```

- [ ] **Step 4: Rodar e ver falhar**

Run: `.venv\Scripts\python -m pytest tests/test_health.py -v` — Expected: FAIL (`ModuleNotFoundError: app`).

- [ ] **Step 5: Implementar o mínimo**

`backend/app/__init__.py`: vazio. `backend/app/main.py`:

```python
from fastapi import FastAPI

def create_app() -> FastAPI:
    app = FastAPI(title="Dashboard Lotufo")

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    return app

app = create_app()
```

- [ ] **Step 6: Rodar e ver passar**

Run: `.venv\Scripts\python -m pytest -v` — Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/ && git commit -m "feat: scaffold FastAPI com pytest"
```

---

### Task 6: Banco SQLite endurecido + runner de migrações

**Files:**
- Create: `backend/app/db.py`, `backend/migrations/001_usuarios_sessoes_audit.sql`, `backend/tests/test_db.py`

**Interfaces:**
- Produces: `db.get_conn() -> sqlite3.Connection` (WAL, FK ON, busy_timeout 5000, row_factory=Row, caminho de `DASH_DB_PATH` ou `dados/dashboard.db`); `db.migrate(conn)` aplica `backend/migrations/*.sql` em ordem, registrando em `schema_migrations(nome)`; `create_app()` chama `migrate` na inicialização.

- [ ] **Step 1: Escrever os testes que falham**

`backend/tests/test_db.py`:

```python
import sqlite3
from app import db

def test_conn_endurecida(tmp_path, monkeypatch):
    monkeypatch.setenv("DASH_DB_PATH", str(tmp_path / "t.db"))
    conn = db.get_conn()
    assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    assert conn.execute("PRAGMA busy_timeout").fetchone()[0] == 5000
    conn.close()

def test_migrate_aplica_uma_vez(tmp_path, monkeypatch):
    monkeypatch.setenv("DASH_DB_PATH", str(tmp_path / "t.db"))
    conn = db.get_conn()
    db.migrate(conn)
    db.migrate(conn)  # idempotente
    tabelas = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"usuarios", "sessoes", "audit_log", "schema_migrations"} <= tabelas
    conn.close()
```

- [ ] **Step 2: Rodar e ver falhar** — Run: `.venv\Scripts\python -m pytest tests/test_db.py -v` — Expected: FAIL.

- [ ] **Step 3: Implementar `app/db.py`**

```python
import os
import sqlite3
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"

def db_path() -> Path:
    p = Path(os.environ.get("DASH_DB_PATH", "dados/dashboard.db"))
    p.parent.mkdir(parents=True, exist_ok=True)
    return p

def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(db_path(), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn

def migrate(conn: sqlite3.Connection) -> None:
    conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations (nome TEXT PRIMARY KEY)")
    aplicadas = {r[0] for r in conn.execute("SELECT nome FROM schema_migrations")}
    for sql_file in sorted(MIGRATIONS_DIR.glob("*.sql")):
        if sql_file.name not in aplicadas:
            conn.executescript(sql_file.read_text(encoding="utf-8"))
            conn.execute("INSERT INTO schema_migrations (nome) VALUES (?)", (sql_file.name,))
    conn.commit()
```

- [ ] **Step 4: Criar `migrations/001_usuarios_sessoes_audit.sql`**

```sql
CREATE TABLE usuarios (
    id INTEGER PRIMARY KEY,
    nome TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    senha_hash TEXT NOT NULL,
    perfil TEXT NOT NULL CHECK (perfil IN ('engenharia','diretoria','admin')),
    ativo INTEGER NOT NULL DEFAULT 1,
    tentativas_falhas INTEGER NOT NULL DEFAULT 0,
    bloqueado_ate TEXT,
    criado_em TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE sessoes (
    token_hash TEXT PRIMARY KEY,
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id),
    csrf_token TEXT NOT NULL,
    criado_em TEXT NOT NULL DEFAULT (datetime('now')),
    expira_em TEXT NOT NULL
);

CREATE TABLE audit_log (
    id INTEGER PRIMARY KEY,
    usuario_id INTEGER REFERENCES usuarios(id),
    acao TEXT NOT NULL,
    entidade TEXT,
    entidade_id TEXT,
    antes TEXT,
    depois TEXT,
    criado_em TEXT NOT NULL DEFAULT (datetime('now')),
    hash_prev TEXT NOT NULL,
    hash TEXT NOT NULL
);
```

- [ ] **Step 5: Ligar `migrate` no `create_app()`** — em `app/main.py`, no início de `create_app()`:

```python
from app import db
conn = db.get_conn()
db.migrate(conn)
conn.close()
```

- [ ] **Step 6: Rodar e ver passar** — Run: `.venv\Scripts\python -m pytest -v` — Expected: PASS (todos).

- [ ] **Step 7: Commit**

```bash
git add backend/ && git commit -m "feat: SQLite endurecido (WAL/FK/busy_timeout) e runner de migracoes"
```

---

### Task 7: Módulo de dinheiro (centavos, formatação, rateio com resíduo)

**Files:**
- Create: `backend/app/dinheiro.py`, `backend/tests/test_dinheiro.py`

**Interfaces:**
- Produces: `parse_brl(texto: str) -> int` (centavos; aceita "4.075.275,90", "R$ 1.000,00"); `format_brl(centavos: int) -> str` ("R$ 4.075.275,90"); `ratear(total_centavos: int, percentuais: list[tuple[str, float]]) -> dict[str, int]` — soma das partes SEMPRE igual ao total; resíduo de centavos distribuído por ordem decrescente de fração truncada (maior resto primeiro).

- [ ] **Step 1: Escrever os testes que falham**

`backend/tests/test_dinheiro.py`:

```python
import pytest
from app.dinheiro import parse_brl, format_brl, ratear

def test_parse_brl():
    assert parse_brl("4.075.275,90") == 407527590
    assert parse_brl("R$ 1.000,00") == 100000
    assert parse_brl("0,01") == 1

def test_parse_brl_invalido():
    with pytest.raises(ValueError):
        parse_brl("abc")

def test_format_brl():
    assert format_brl(407527590) == "R$ 4.075.275,90"
    assert format_brl(1) == "R$ 0,01"

def test_ratear_soma_sempre_igual_ao_total():
    partes = ratear(100000001, [("A", 60.0), ("B", 40.0)])  # 1.000.000,01
    assert sum(partes.values()) == 100000001

def test_ratear_residuo_para_maior_resto():
    # 100 centavos em 3 partes iguais: 33+33+34, centavo extra p/ maior resto
    partes = ratear(100, [("A", 33.33), ("B", 33.33), ("C", 33.34)])
    assert sum(partes.values()) == 100
    assert partes["C"] == 34
```

- [ ] **Step 2: Rodar e ver falhar** — Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implementar `app/dinheiro.py`**

```python
import re

def parse_brl(texto: str) -> int:
    limpo = texto.replace("R$", "").strip().replace(".", "").replace(",", ".")
    if not re.fullmatch(r"-?\d+(\.\d{1,2})?", limpo):
        raise ValueError(f"Valor monetário inválido: {texto!r}")
    inteiro, _, dec = limpo.partition(".")
    return int(inteiro) * 100 + (int(dec.ljust(2, "0")) if dec else 0) * (-1 if inteiro.startswith("-") and dec else 1)

def format_brl(centavos: int) -> str:
    sinal = "-" if centavos < 0 else ""
    c = abs(centavos)
    inteiro, dec = divmod(c, 100)
    milhares = f"{inteiro:,}".replace(",", ".")
    return f"{sinal}R$ {milhares},{dec:02d}"

def ratear(total_centavos: int, percentuais: list[tuple[str, float]]) -> dict[str, int]:
    brutos = {nome: total_centavos * pct / 100.0 for nome, pct in percentuais}
    partes = {nome: int(v) for nome, v in brutos.items()}   # trunca
    residuo = total_centavos - sum(partes.values())
    por_resto = sorted(brutos, key=lambda n: brutos[n] - partes[n], reverse=True)
    for nome in por_resto[:residuo]:
        partes[nome] += 1
    return partes
```

- [ ] **Step 4: Rodar e ver passar** — Run: `.venv\Scripts\python -m pytest tests/test_dinheiro.py -v` — Expected: PASS. (Se `test_parse_brl` falhar em negativo, simplificar: valores negativos não são aceitos por `parse_brl` na v1 — remover o caso e o multiplicador.)

- [ ] **Step 5: Commit**

```bash
git add backend/ && git commit -m "feat: modulo de dinheiro em centavos com rateio de residuo"
```

---

### Task 8: Autenticação — senhas argon2, login/logout, sessões, lockout

**Files:**
- Create: `backend/app/auth.py`, `backend/app/api_auth.py`, `backend/tests/test_auth.py`
- Modify: `backend/app/main.py` (incluir router)

**Interfaces:**
- Consumes: `db.get_conn()` (Task 6).
- Produces: `auth.criar_usuario(conn, nome, email, senha, perfil) -> int`; `auth.autenticar(conn, email, senha) -> dict | None` (None se senha errada/bloqueado; incrementa `tentativas_falhas`, bloqueia 15 min após 5 falhas); `auth.criar_sessao(conn, usuario_id) -> tuple[str, str]` (token, csrf) com expiração 12h; `auth.sessao_valida(conn, token) -> dict | None` (usuário + csrf); dependency FastAPI `usuario_atual` (lê cookie `sessao`, 401 se inválida); endpoints `POST /api/auth/login` (JSON email/senha → set-cookie HttpOnly/SameSite=Strict + retorna `{nome, perfil, csrf}`), `POST /api/auth/logout`, `GET /api/auth/eu`.

- [ ] **Step 1: Escrever os testes que falham**

`backend/tests/test_auth.py`:

```python
from app import db, auth

def _conn(tmp_path, monkeypatch):
    monkeypatch.setenv("DASH_DB_PATH", str(tmp_path / "t.db"))
    conn = db.get_conn(); db.migrate(conn); return conn

def test_criar_e_autenticar(tmp_path, monkeypatch):
    conn = _conn(tmp_path, monkeypatch)
    auth.criar_usuario(conn, "Leo", "leo@lotufo.com", "senha-forte-123", "admin")
    assert auth.autenticar(conn, "leo@lotufo.com", "senha-forte-123")["nome"] == "Leo"
    assert auth.autenticar(conn, "leo@lotufo.com", "errada") is None

def test_lockout_apos_5_falhas(tmp_path, monkeypatch):
    conn = _conn(tmp_path, monkeypatch)
    auth.criar_usuario(conn, "Leo", "leo@lotufo.com", "senha-forte-123", "admin")
    for _ in range(5):
        auth.autenticar(conn, "leo@lotufo.com", "errada")
    # mesmo com senha certa, bloqueado
    assert auth.autenticar(conn, "leo@lotufo.com", "senha-forte-123") is None

def test_sessao(tmp_path, monkeypatch):
    conn = _conn(tmp_path, monkeypatch)
    uid = auth.criar_usuario(conn, "Leo", "leo@lotufo.com", "senha-forte-123", "admin")
    token, csrf = auth.criar_sessao(conn, uid)
    s = auth.sessao_valida(conn, token)
    assert s["usuario_id"] == uid and s["csrf_token"] == csrf
    assert auth.sessao_valida(conn, "token-invalido") is None

def test_login_endpoint(client):
    # seed via app (usa o mesmo banco do client)
    r = client.post("/api/auth/login", json={"email": "x@lotufo.com", "senha": "y"})
    assert r.status_code == 401
```

- [ ] **Step 2: Rodar e ver falhar** — Expected: FAIL.

- [ ] **Step 3: Implementar `app/auth.py`**

```python
import hashlib
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

_ph = PasswordHasher()
MAX_FALHAS = 5
BLOQUEIO_MIN = 15
SESSAO_HORAS = 12

def _agora() -> datetime:
    return datetime.now(timezone.utc)

def criar_usuario(conn: sqlite3.Connection, nome: str, email: str, senha: str, perfil: str) -> int:
    cur = conn.execute(
        "INSERT INTO usuarios (nome, email, senha_hash, perfil) VALUES (?,?,?,?)",
        (nome, email.lower(), _ph.hash(senha), perfil))
    conn.commit()
    return cur.lastrowid

def autenticar(conn: sqlite3.Connection, email: str, senha: str) -> dict | None:
    row = conn.execute("SELECT * FROM usuarios WHERE email=? AND ativo=1",
                       (email.lower(),)).fetchone()
    if row is None:
        return None
    if row["bloqueado_ate"] and datetime.fromisoformat(row["bloqueado_ate"]) > _agora():
        return None
    try:
        _ph.verify(row["senha_hash"], senha)
    except VerifyMismatchError:
        falhas = row["tentativas_falhas"] + 1
        bloqueio = (_agora() + timedelta(minutes=BLOQUEIO_MIN)).isoformat() if falhas >= MAX_FALHAS else None
        conn.execute("UPDATE usuarios SET tentativas_falhas=?, bloqueado_ate=? WHERE id=?",
                     (falhas % MAX_FALHAS if bloqueio else falhas, bloqueio, row["id"]))
        conn.commit()
        return None
    conn.execute("UPDATE usuarios SET tentativas_falhas=0, bloqueado_ate=NULL WHERE id=?", (row["id"],))
    conn.commit()
    return dict(row)

def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()

def criar_sessao(conn: sqlite3.Connection, usuario_id: int) -> tuple[str, str]:
    token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    expira = (_agora() + timedelta(hours=SESSAO_HORAS)).isoformat()
    conn.execute("INSERT INTO sessoes (token_hash, usuario_id, csrf_token, expira_em) VALUES (?,?,?,?)",
                 (_hash_token(token), usuario_id, csrf, expira))
    conn.commit()
    return token, csrf

def sessao_valida(conn: sqlite3.Connection, token: str) -> dict | None:
    row = conn.execute("SELECT * FROM sessoes WHERE token_hash=?", (_hash_token(token),)).fetchone()
    if row is None or datetime.fromisoformat(row["expira_em"]) < _agora():
        return None
    return dict(row)

def encerrar_sessao(conn: sqlite3.Connection, token: str) -> None:
    conn.execute("DELETE FROM sessoes WHERE token_hash=?", (_hash_token(token),))
    conn.commit()
```

- [ ] **Step 4: Implementar `app/api_auth.py`**

```python
import sqlite3
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from app import auth, db

router = APIRouter(prefix="/api/auth")

def conexao():
    conn = db.get_conn()
    try:
        yield conn
    finally:
        conn.close()

def usuario_atual(request: Request, conn: sqlite3.Connection = Depends(conexao)) -> dict:
    token = request.cookies.get("sessao")
    s = auth.sessao_valida(conn, token) if token else None
    if s is None:
        raise HTTPException(401, "Sessão inválida ou expirada")
    u = conn.execute("SELECT id, nome, email, perfil FROM usuarios WHERE id=?",
                     (s["usuario_id"],)).fetchone()
    return {**dict(u), "csrf_token": s["csrf_token"]}

def exigir_csrf(request: Request, usuario: dict = Depends(usuario_atual)) -> dict:
    if request.headers.get("X-CSRF-Token") != usuario["csrf_token"]:
        raise HTTPException(403, "CSRF token ausente ou inválido")
    return usuario

class LoginIn(BaseModel):
    email: str
    senha: str

@router.post("/login")
def login(dados: LoginIn, response: Response, conn: sqlite3.Connection = Depends(conexao)):
    u = auth.autenticar(conn, dados.email, dados.senha)
    if u is None:
        raise HTTPException(401, "E-mail ou senha inválidos, ou usuário bloqueado")
    token, csrf = auth.criar_sessao(conn, u["id"])
    response.set_cookie("sessao", token, httponly=True, samesite="strict",
                        secure=True, max_age=12 * 3600)
    return {"nome": u["nome"], "perfil": u["perfil"], "csrf": csrf}

@router.post("/logout")
def logout(request: Request, response: Response, conn: sqlite3.Connection = Depends(conexao)):
    token = request.cookies.get("sessao")
    if token:
        auth.encerrar_sessao(conn, token)
    response.delete_cookie("sessao")
    return {"ok": True}

@router.get("/eu")
def eu(usuario: dict = Depends(usuario_atual)):
    return {k: usuario[k] for k in ("id", "nome", "email", "perfil")}
```

Em `app/main.py`, dentro de `create_app()`: `from app.api_auth import router as auth_router; app.include_router(auth_router)`.

**Nota (testes):** `secure=True` exige HTTPS; o TestClient do FastAPI aceita cookies secure normalmente. Se algum teste de endpoint falhar por cookie, usar `client.cookies` diretamente.

- [ ] **Step 5: Rodar e ver passar** — Run: `.venv\Scripts\python -m pytest -v` — Expected: PASS (todos).

- [ ] **Step 6: Commit**

```bash
git add backend/ && git commit -m "feat: autenticacao argon2 com sessoes, lockout e CSRF"
```

---

### Task 9: Permissões por perfil + seed do administrador

**Files:**
- Create: `backend/app/permissoes.py`, `backend/app/cli.py`, `backend/tests/test_permissoes.py`

**Interfaces:**
- Consumes: `usuario_atual`, `exigir_csrf` (Task 8).
- Produces: `PERFIS: dict[str, set[str]]` — permissões: `ver_paineis`, `editar_cadastros`, `editar_config_fiscal`, `administrar`; `permissoes.tem(perfil, permissao) -> bool`; factory de dependency `exigir(permissao)` (403 se o perfil não tem); CLI `python -m app.cli criar-admin --nome X --email Y` (senha pedida no prompt) para o primeiro usuário.

- [ ] **Step 1: Escrever os testes que falham**

`backend/tests/test_permissoes.py`:

```python
from app.permissoes import PERFIS, tem

def test_perfis():
    assert tem("admin", "administrar")
    assert tem("admin", "editar_config_fiscal")
    assert tem("engenharia", "editar_cadastros")
    assert not tem("engenharia", "editar_config_fiscal")
    assert not tem("engenharia", "administrar")
    assert tem("diretoria", "ver_paineis")
    assert not tem("diretoria", "editar_cadastros")
```

- [ ] **Step 2: Rodar e ver falhar** — Expected: FAIL.

- [ ] **Step 3: Implementar `app/permissoes.py`**

```python
from fastapi import Depends, HTTPException
from app.api_auth import exigir_csrf, usuario_atual

PERFIS: dict[str, set[str]] = {
    "diretoria": {"ver_paineis"},
    "engenharia": {"ver_paineis", "editar_cadastros"},
    "admin": {"ver_paineis", "editar_cadastros", "editar_config_fiscal", "administrar"},
}

def tem(perfil: str, permissao: str) -> bool:
    return permissao in PERFIS.get(perfil, set())

def exigir(permissao: str, com_csrf: bool = True):
    base = exigir_csrf if com_csrf else usuario_atual
    def dep(usuario: dict = Depends(base)) -> dict:
        if not tem(usuario["perfil"], permissao):
            raise HTTPException(403, f"Permissão necessária: {permissao}")
        return usuario
    return dep
```

- [ ] **Step 4: Implementar `app/cli.py`**

```python
import argparse
import getpass
from app import auth, db

def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    ca = sub.add_parser("criar-admin")
    ca.add_argument("--nome", required=True)
    ca.add_argument("--email", required=True)
    args = p.parse_args()
    if args.cmd == "criar-admin":
        senha = getpass.getpass("Senha do administrador: ")
        conn = db.get_conn()
        db.migrate(conn)
        uid = auth.criar_usuario(conn, args.nome, args.email, senha, "admin")
        print(f"Administrador criado (id={uid}).")

if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Rodar e ver passar** — Run: `.venv\Scripts\python -m pytest -v` — Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/ && git commit -m "feat: permissoes por perfil e CLI de seed do admin"
```

---

### Task 10: Log de auditoria com hash encadeado

**Files:**
- Create: `backend/app/auditoria.py`, `backend/app/api_admin.py`, `backend/tests/test_auditoria.py`
- Modify: `backend/app/main.py` (incluir router), `backend/app/api_auth.py` (auditar login/logout)

**Interfaces:**
- Consumes: tabela `audit_log` (Task 6), `exigir` (Task 9).
- Produces: `auditoria.registrar(conn, usuario_id, acao, entidade=None, entidade_id=None, antes=None, depois=None)` — calcula `hash = sha256(hash_prev + payload_json)`, `hash_prev` = hash da última linha (ou "genesis"); `auditoria.verificar_cadeia(conn) -> bool`; endpoint `GET /api/admin/auditoria?limite=100` (permissão `administrar`). Convenção de ação: `"entidade.verbo"` (ex.: `auth.login`, `contrato.criar`). Tasks 11–12 chamam `registrar` em toda mutação.

- [ ] **Step 1: Escrever os testes que falham**

`backend/tests/test_auditoria.py`:

```python
import json
from app import db, auditoria

def _conn(tmp_path, monkeypatch):
    monkeypatch.setenv("DASH_DB_PATH", str(tmp_path / "t.db"))
    conn = db.get_conn(); db.migrate(conn); return conn

def test_registro_encadeado(tmp_path, monkeypatch):
    conn = _conn(tmp_path, monkeypatch)
    auditoria.registrar(conn, None, "auth.login", depois={"email": "a@b.c"})
    auditoria.registrar(conn, None, "contrato.criar", "contrato", "1", depois={"objeto": "obra X"})
    linhas = conn.execute("SELECT * FROM audit_log ORDER BY id").fetchall()
    assert linhas[0]["hash_prev"] == "genesis"
    assert linhas[1]["hash_prev"] == linhas[0]["hash"]
    assert auditoria.verificar_cadeia(conn) is True

def test_adulteracao_detectada(tmp_path, monkeypatch):
    conn = _conn(tmp_path, monkeypatch)
    auditoria.registrar(conn, None, "auth.login")
    auditoria.registrar(conn, None, "auth.logout")
    conn.execute("UPDATE audit_log SET acao='hackeado' WHERE id=1")
    conn.commit()
    assert auditoria.verificar_cadeia(conn) is False
```

- [ ] **Step 2: Rodar e ver falhar** — Expected: FAIL.

- [ ] **Step 3: Implementar `app/auditoria.py`**

```python
import hashlib
import json
import sqlite3

def _payload(usuario_id, acao, entidade, entidade_id, antes, depois, criado_em) -> str:
    return json.dumps([usuario_id, acao, entidade, entidade_id, antes, depois, criado_em],
                      ensure_ascii=False, sort_keys=True)

def registrar(conn: sqlite3.Connection, usuario_id, acao: str, entidade=None,
              entidade_id=None, antes: dict | None = None, depois: dict | None = None) -> None:
    ultimo = conn.execute("SELECT hash FROM audit_log ORDER BY id DESC LIMIT 1").fetchone()
    hash_prev = ultimo["hash"] if ultimo else "genesis"
    criado_em = conn.execute("SELECT datetime('now')").fetchone()[0]
    antes_j = json.dumps(antes, ensure_ascii=False, sort_keys=True) if antes else None
    depois_j = json.dumps(depois, ensure_ascii=False, sort_keys=True) if depois else None
    corpo = _payload(usuario_id, acao, entidade, entidade_id, antes_j, depois_j, criado_em)
    h = hashlib.sha256((hash_prev + corpo).encode()).hexdigest()
    conn.execute(
        """INSERT INTO audit_log (usuario_id, acao, entidade, entidade_id, antes, depois,
           criado_em, hash_prev, hash) VALUES (?,?,?,?,?,?,?,?,?)""",
        (usuario_id, acao, entidade, entidade_id, antes_j, depois_j, criado_em, hash_prev, h))
    conn.commit()

def verificar_cadeia(conn: sqlite3.Connection) -> bool:
    esperado = "genesis"
    for r in conn.execute("SELECT * FROM audit_log ORDER BY id"):
        if r["hash_prev"] != esperado:
            return False
        corpo = _payload(r["usuario_id"], r["acao"], r["entidade"], r["entidade_id"],
                         r["antes"], r["depois"], r["criado_em"])
        if hashlib.sha256((r["hash_prev"] + corpo).encode()).hexdigest() != r["hash"]:
            return False
        esperado = r["hash"]
    return True
```

- [ ] **Step 4: Implementar `app/api_admin.py` e auditar o login**

`app/api_admin.py`:

```python
import sqlite3
from fastapi import APIRouter, Depends
from app import auditoria, db
from app.api_auth import conexao
from app.permissoes import exigir

router = APIRouter(prefix="/api/admin")

@router.get("/auditoria")
def listar_auditoria(limite: int = 100,
                     usuario: dict = Depends(exigir("administrar", com_csrf=False)),
                     conn: sqlite3.Connection = Depends(conexao)):
    linhas = conn.execute(
        "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (min(limite, 500),)).fetchall()
    return {"cadeia_integra": auditoria.verificar_cadeia(conn),
            "eventos": [dict(l) for l in linhas]}
```

Em `api_auth.py`: após login bem-sucedido, `auditoria.registrar(conn, u["id"], "auth.login")`; no logout, `auditoria.registrar(conn, s_usuario_id_se_disponivel, "auth.logout")` (obter `usuario_id` da sessão antes de encerrá-la). Em `main.py`: incluir `api_admin.router`.

- [ ] **Step 5: Rodar e ver passar** — Run: `.venv\Scripts\python -m pytest -v` — Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/ && git commit -m "feat: auditoria append-only com hash encadeado e endpoint admin"
```

---

### Task 11: Schema e regra de negócio de contratos (vigente por deltas)

**Files:**
- Create: `backend/migrations/002_contratos.sql`, `backend/app/contratos.py`, `backend/tests/test_contratos.py`

**Interfaces:**
- Consumes: `db` (Task 6), `dinheiro` (Task 7), `auditoria` (Task 10).
- Produces: tabelas `obras`, `contratos`, `contrato_eventos`, `aditivos`; `contratos.criar(conn, usuario_id, dados: dict) -> int`; `contratos.atualizar(conn, usuario_id, contrato_id, dados) -> None`; `contratos.mudar_estado(conn, usuario_id, contrato_id, novo_estado, data, observacao) -> None` (transições válidas: ativo↔suspenso, ativo→encerrado, ativo→rescindido; grava evento); `contratos.vigente(conn, contrato_id) -> dict` com `valor_vigente_centavos`, `vigencia_fim_vigente`, `execucao_fim_vigente` = original + deltas/datas dos aditivos com `status='assinado'` em ordem de `data_assinatura`; `contratos.listar(conn) -> list[dict]` (cada um com o vigente calculado).

- [ ] **Step 1: Criar `migrations/002_contratos.sql`**

```sql
CREATE TABLE obras (
    id INTEGER PRIMARY KEY,
    nome TEXT NOT NULL
);

CREATE TABLE contratos (
    id INTEGER PRIMARY KEY,
    obra_id INTEGER REFERENCES obras(id),
    orgao TEXT NOT NULL,
    numero_instrumento TEXT NOT NULL,
    objeto TEXT NOT NULL,
    valor_original_centavos INTEGER NOT NULL CHECK (valor_original_centavos >= 0),
    data_base TEXT,
    indice_reajuste TEXT,
    vigencia_inicio TEXT,
    vigencia_fim TEXT,
    execucao_inicio TEXT,
    execucao_fim TEXT,
    numero_processo TEXT,
    pasta_sharepoint TEXT,
    estado TEXT NOT NULL DEFAULT 'ativo'
        CHECK (estado IN ('ativo','suspenso','encerrado','rescindido')),
    criado_em TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE contrato_eventos (
    id INTEGER PRIMARY KEY,
    contrato_id INTEGER NOT NULL REFERENCES contratos(id),
    tipo TEXT NOT NULL CHECK (tipo IN ('suspensao','retomada','encerramento','rescisao')),
    data TEXT NOT NULL,
    observacao TEXT,
    criado_em TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE aditivos (
    id INTEGER PRIMARY KEY,
    contrato_id INTEGER NOT NULL REFERENCES contratos(id),
    tipo TEXT NOT NULL CHECK (tipo IN ('prazo','valor','escopo','misto')),
    delta_valor_centavos INTEGER NOT NULL DEFAULT 0,
    nova_vigencia_fim TEXT,
    nova_execucao_fim TEXT,
    status TEXT NOT NULL DEFAULT 'em_andamento'
        CHECK (status IN ('em_andamento','assinado')),
    data_assinatura TEXT,
    criado_em TEXT NOT NULL DEFAULT (datetime('now'))
);
```

- [ ] **Step 2: Escrever os testes que falham**

`backend/tests/test_contratos.py`:

```python
import pytest
from app import contratos, db

BASE = {"orgao": "SINFRA-MT", "numero_instrumento": "IC 082/2025",
        "objeto": "MT-388 Porto Esperidião", "valor_original_centavos": 1_000_000_00,
        "vigencia_fim": "2027-12-31", "execucao_fim": "2027-06-30"}

def _conn(tmp_path, monkeypatch):
    monkeypatch.setenv("DASH_DB_PATH", str(tmp_path / "t.db"))
    conn = db.get_conn(); db.migrate(conn); return conn

def test_criar_e_vigente_sem_aditivos(tmp_path, monkeypatch):
    conn = _conn(tmp_path, monkeypatch)
    cid = contratos.criar(conn, 1, BASE)
    v = contratos.vigente(conn, cid)
    assert v["valor_vigente_centavos"] == 1_000_000_00
    assert v["vigencia_fim_vigente"] == "2027-12-31"

def test_vigente_soma_deltas_assinados_em_ordem(tmp_path, monkeypatch):
    conn = _conn(tmp_path, monkeypatch)
    cid = contratos.criar(conn, 1, BASE)
    conn.execute("""INSERT INTO aditivos (contrato_id, tipo, delta_valor_centavos,
        status, data_assinatura) VALUES (?, 'valor', 300_000_00, 'assinado', '2026-03-01')""", (cid,))
    conn.execute("""INSERT INTO aditivos (contrato_id, tipo, delta_valor_centavos,
        nova_execucao_fim, status, data_assinatura)
        VALUES (?, 'misto', -120_000_00, '2027-09-30', 'assinado', '2026-06-01')""", (cid,))
    conn.execute("""INSERT INTO aditivos (contrato_id, tipo, delta_valor_centavos, status)
        VALUES (?, 'valor', 999_999_99, 'em_andamento')""", (cid,))  # nao conta
    conn.commit()
    v = contratos.vigente(conn, cid)
    assert v["valor_vigente_centavos"] == 1_000_000_00 + 300_000_00 - 120_000_00
    assert v["execucao_fim_vigente"] == "2027-09-30"

def test_estado_transicoes(tmp_path, monkeypatch):
    conn = _conn(tmp_path, monkeypatch)
    cid = contratos.criar(conn, 1, BASE)
    contratos.mudar_estado(conn, 1, cid, "suspenso", "2026-08-01", "paralisação")
    contratos.mudar_estado(conn, 1, cid, "ativo", "2026-09-01", "retomada")
    with pytest.raises(ValueError):
        contratos.mudar_estado(conn, 1, cid, "rescindido", "2026-09-02", None)  # ok na verdade
```

Ajuste do último teste (transição ativo→rescindido é VÁLIDA): trocar por transição inválida real:

```python
def test_estado_transicao_invalida(tmp_path, monkeypatch):
    conn = _conn(tmp_path, monkeypatch)
    cid = contratos.criar(conn, 1, BASE)
    contratos.mudar_estado(conn, 1, cid, "encerrado", "2026-08-01", None)
    with pytest.raises(ValueError):
        contratos.mudar_estado(conn, 1, cid, "suspenso", "2026-09-01", None)  # encerrado é terminal
```

- [ ] **Step 3: Rodar e ver falhar** — Expected: FAIL.

- [ ] **Step 4: Implementar `app/contratos.py`**

```python
import sqlite3
from app import auditoria

CAMPOS = ["obra_id", "orgao", "numero_instrumento", "objeto", "valor_original_centavos",
          "data_base", "indice_reajuste", "vigencia_inicio", "vigencia_fim",
          "execucao_inicio", "execucao_fim", "numero_processo", "pasta_sharepoint"]

TRANSICOES = {"ativo": {"suspenso", "encerrado", "rescindido"},
              "suspenso": {"ativo"}, "encerrado": set(), "rescindido": set()}
EVENTO_POR_ESTADO = {"suspenso": "suspensao", "ativo": "retomada",
                     "encerrado": "encerramento", "rescindido": "rescisao"}

def criar(conn: sqlite3.Connection, usuario_id: int, dados: dict) -> int:
    presentes = [c for c in CAMPOS if c in dados]
    cur = conn.execute(
        f"INSERT INTO contratos ({','.join(presentes)}) VALUES ({','.join('?' * len(presentes))})",
        [dados[c] for c in presentes])
    conn.commit()
    auditoria.registrar(conn, usuario_id, "contrato.criar", "contrato", str(cur.lastrowid),
                        depois={c: dados.get(c) for c in presentes})
    return cur.lastrowid

def atualizar(conn: sqlite3.Connection, usuario_id: int, contrato_id: int, dados: dict) -> None:
    antes = dict(conn.execute("SELECT * FROM contratos WHERE id=?", (contrato_id,)).fetchone())
    presentes = [c for c in CAMPOS if c in dados]
    if not presentes:
        return
    conn.execute(f"UPDATE contratos SET {','.join(f'{c}=?' for c in presentes)} WHERE id=?",
                 [dados[c] for c in presentes] + [contrato_id])
    conn.commit()
    auditoria.registrar(conn, usuario_id, "contrato.atualizar", "contrato", str(contrato_id),
                        antes={c: antes[c] for c in presentes},
                        depois={c: dados[c] for c in presentes})

def mudar_estado(conn, usuario_id: int, contrato_id: int, novo: str, data: str, observacao) -> None:
    atual = conn.execute("SELECT estado FROM contratos WHERE id=?", (contrato_id,)).fetchone()["estado"]
    if novo not in TRANSICOES.get(atual, set()):
        raise ValueError(f"Transição inválida: {atual} → {novo}")
    conn.execute("UPDATE contratos SET estado=? WHERE id=?", (novo, contrato_id))
    conn.execute("INSERT INTO contrato_eventos (contrato_id, tipo, data, observacao) VALUES (?,?,?,?)",
                 (contrato_id, EVENTO_POR_ESTADO[novo], data, observacao))
    conn.commit()
    auditoria.registrar(conn, usuario_id, "contrato.mudar_estado", "contrato", str(contrato_id),
                        antes={"estado": atual}, depois={"estado": novo, "data": data})

def vigente(conn: sqlite3.Connection, contrato_id: int) -> dict:
    c = dict(conn.execute("SELECT * FROM contratos WHERE id=?", (contrato_id,)).fetchone())
    valor = c["valor_original_centavos"]
    vig_fim, exe_fim = c["vigencia_fim"], c["execucao_fim"]
    for a in conn.execute("""SELECT * FROM aditivos WHERE contrato_id=? AND status='assinado'
                             ORDER BY data_assinatura, id""", (contrato_id,)):
        valor += a["delta_valor_centavos"]
        vig_fim = a["nova_vigencia_fim"] or vig_fim
        exe_fim = a["nova_execucao_fim"] or exe_fim
    return {**c, "valor_vigente_centavos": valor,
            "vigencia_fim_vigente": vig_fim, "execucao_fim_vigente": exe_fim}

def listar(conn: sqlite3.Connection) -> list[dict]:
    ids = [r["id"] for r in conn.execute("SELECT id FROM contratos ORDER BY numero_instrumento")]
    return [vigente(conn, i) for i in ids]
```

- [ ] **Step 5: Rodar e ver passar** — Run: `.venv\Scripts\python -m pytest tests/test_contratos.py -v` — Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/ && git commit -m "feat: contratos com estados, eventos e vigente por deltas de aditivos"
```

---

### Task 12: API de contratos

**Files:**
- Create: `backend/app/api_contratos.py`, `backend/tests/test_api_contratos.py`
- Modify: `backend/app/main.py` (incluir router), `backend/tests/conftest.py` (fixture de client logado)

**Interfaces:**
- Consumes: `contratos` (Task 11), `exigir` (Task 9).
- Produces: `GET /api/contratos` (permissão `ver_paineis`) → lista com vigente; `POST /api/contratos` (permissão `editar_cadastros` + CSRF) → cria, aceita valores monetários como string BRL (`"valor_original": "1.000.000,00"`) convertidos por `parse_brl`; `GET /api/contratos/{id}`; `PUT /api/contratos/{id}`; `POST /api/contratos/{id}/estado` (`{"estado": "suspenso", "data": "2026-08-01", "observacao": "..."}`).

- [ ] **Step 1: Ampliar `conftest.py` com client logado**

```python
@pytest.fixture
def client_admin(client):
    from app import auth, db
    conn = db.get_conn()
    auth.criar_usuario(conn, "Admin", "admin@lotufo.com", "senha-forte-123", "admin")
    conn.close()
    r = client.post("/api/auth/login", json={"email": "admin@lotufo.com", "senha": "senha-forte-123"})
    client.headers["X-CSRF-Token"] = r.json()["csrf"]
    return client
```

- [ ] **Step 2: Escrever os testes que falham**

`backend/tests/test_api_contratos.py`:

```python
NOVO = {"orgao": "SINFRA-MT", "numero_instrumento": "IC 082/2025",
        "objeto": "MT-388", "valor_original": "1.000.000,00",
        "vigencia_fim": "2027-12-31", "execucao_fim": "2027-06-30"}

def test_criar_e_listar(client_admin):
    r = client_admin.post("/api/contratos", json=NOVO)
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    lista = client_admin.get("/api/contratos").json()
    assert any(c["id"] == cid and c["valor_vigente_centavos"] == 100_000_000 for c in lista)

def test_sem_login_nega(client):
    assert client.get("/api/contratos").status_code == 401

def test_sem_csrf_nega(client_admin):
    del client_admin.headers["X-CSRF-Token"]
    assert client_admin.post("/api/contratos", json=NOVO).status_code == 403

def test_mudar_estado(client_admin):
    cid = client_admin.post("/api/contratos", json=NOVO).json()["id"]
    r = client_admin.post(f"/api/contratos/{cid}/estado",
                          json={"estado": "suspenso", "data": "2026-08-01", "observacao": "OS de paralisação"})
    assert r.status_code == 200
    assert client_admin.get(f"/api/contratos/{cid}").json()["estado"] == "suspenso"
```

- [ ] **Step 3: Rodar e ver falhar** — Expected: FAIL (404 nas rotas).

- [ ] **Step 4: Implementar `app/api_contratos.py`**

```python
import sqlite3
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app import contratos
from app.api_auth import conexao
from app.dinheiro import parse_brl
from app.permissoes import exigir

router = APIRouter(prefix="/api/contratos")

class ContratoIn(BaseModel):
    obra_id: int | None = None
    orgao: str
    numero_instrumento: str
    objeto: str
    valor_original: str  # BRL "1.000.000,00"
    data_base: str | None = None
    indice_reajuste: str | None = None
    vigencia_inicio: str | None = None
    vigencia_fim: str | None = None
    execucao_inicio: str | None = None
    execucao_fim: str | None = None
    numero_processo: str | None = None
    pasta_sharepoint: str | None = None

    def como_dados(self) -> dict:
        d = self.model_dump(exclude={"valor_original"}, exclude_none=True)
        d["valor_original_centavos"] = parse_brl(self.valor_original)
        return d

class EstadoIn(BaseModel):
    estado: str
    data: str
    observacao: str | None = None

@router.get("")
def listar(usuario: dict = Depends(exigir("ver_paineis", com_csrf=False)),
           conn: sqlite3.Connection = Depends(conexao)):
    return contratos.listar(conn)

@router.post("", status_code=201)
def criar(dados: ContratoIn, usuario: dict = Depends(exigir("editar_cadastros")),
          conn: sqlite3.Connection = Depends(conexao)):
    return {"id": contratos.criar(conn, usuario["id"], dados.como_dados())}

@router.get("/{contrato_id}")
def detalhe(contrato_id: int, usuario: dict = Depends(exigir("ver_paineis", com_csrf=False)),
            conn: sqlite3.Connection = Depends(conexao)):
    row = conn.execute("SELECT id FROM contratos WHERE id=?", (contrato_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "Contrato não encontrado")
    return contratos.vigente(conn, contrato_id)

@router.put("/{contrato_id}")
def atualizar(contrato_id: int, dados: ContratoIn,
              usuario: dict = Depends(exigir("editar_cadastros")),
              conn: sqlite3.Connection = Depends(conexao)):
    contratos.atualizar(conn, usuario["id"], contrato_id, dados.como_dados())
    return {"ok": True}

@router.post("/{contrato_id}/estado")
def mudar_estado(contrato_id: int, dados: EstadoIn,
                 usuario: dict = Depends(exigir("editar_cadastros")),
                 conn: sqlite3.Connection = Depends(conexao)):
    try:
        contratos.mudar_estado(conn, usuario["id"], contrato_id, dados.estado,
                               dados.data, dados.observacao)
    except ValueError as e:
        raise HTTPException(422, str(e))
    return {"ok": True}
```

Em `main.py`: incluir `api_contratos.router`.

- [ ] **Step 5: Rodar e ver passar** — Run: `.venv\Scripts\python -m pytest -v` — Expected: PASS (todos).

- [ ] **Step 6: Commit**

```bash
git add backend/ && git commit -m "feat: API de contratos com permissoes, CSRF e valores BRL"
```

---

### Task 13: Frontend scaffold + tela de login

**Files:**
- Create: `frontend/` (Vite React TS), `frontend/src/api.ts`, `frontend/src/Login.tsx`, `frontend/src/App.tsx`, `frontend/src/main.tsx`

**Interfaces:**
- Consumes: `POST /api/auth/login`, `GET /api/auth/eu` (Task 8).
- Produces: `api.ts` com `api(caminho, opts)` — fetch com `credentials: "include"`, header `X-CSRF-Token` automático (csrf guardado em memória após login) e erro tipado `ApiErro(status, mensagem)`; contexto de usuário `{id, nome, perfil}`; roteamento mínimo por estado (sem lib de rotas): sem sessão → Login; com sessão → layout com menu (Contratos, Administração se perfil admin) e conteúdo.

- [ ] **Step 1: Criar o projeto Vite**

```powershell
cd "C:\Users\<usuario>\Nova Dashboard Lotufo"
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install
```

Em `frontend/vite.config.ts`, adicionar proxy do dev server:

```ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: { proxy: { "/api": "http://localhost:8080" } },
});
```

- [ ] **Step 2: Implementar `src/api.ts`**

```ts
let csrf: string | null = null;

export class ApiErro extends Error {
  constructor(public status: number, mensagem: string) { super(mensagem); }
}

export function setCsrf(token: string | null) { csrf = token; }

export async function api<T = unknown>(caminho: string, opts: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json", ...(opts.headers as any) };
  if (csrf) headers["X-CSRF-Token"] = csrf;
  const r = await fetch(caminho, { credentials: "include", ...opts, headers });
  if (!r.ok) {
    const corpo = await r.json().catch(() => ({}));
    throw new ApiErro(r.status, (corpo as any).detail ?? r.statusText);
  }
  return r.json();
}
```

- [ ] **Step 3: Implementar `src/Login.tsx`**

```tsx
import { useState } from "react";
import { api, setCsrf } from "./api";

export interface Usuario { id: number; nome: string; perfil: string; }

export default function Login({ aoEntrar }: { aoEntrar: (u: Usuario) => void }) {
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [erro, setErro] = useState("");

  async function entrar(e: React.FormEvent) {
    e.preventDefault();
    try {
      const r = await api<{ nome: string; perfil: string; csrf: string }>(
        "/api/auth/login", { method: "POST", body: JSON.stringify({ email, senha }) });
      setCsrf(r.csrf);
      const eu = await api<Usuario>("/api/auth/eu");
      aoEntrar(eu);
    } catch {
      setErro("E-mail ou senha inválidos, ou usuário bloqueado.");
    }
  }

  return (
    <form onSubmit={entrar} style={{ maxWidth: 320, margin: "10vh auto", display: "grid", gap: 12 }}>
      <h1>Dashboard Lotufo</h1>
      <input placeholder="E-mail" value={email} onChange={e => setEmail(e.target.value)} />
      <input placeholder="Senha" type="password" value={senha} onChange={e => setSenha(e.target.value)} />
      <button type="submit">Entrar</button>
      {erro && <p style={{ color: "crimson" }}>{erro}</p>}
    </form>
  );
}
```

- [ ] **Step 4: Implementar `src/App.tsx`** (roteamento por estado; placeholders para Contratos/Admin preenchidos nas Tasks 14–15)

```tsx
import { useEffect, useState } from "react";
import { api } from "./api";
import Login, { Usuario } from "./Login";

export default function App() {
  const [usuario, setUsuario] = useState<Usuario | null>(null);
  const [tela, setTela] = useState<"contratos" | "admin">("contratos");
  const [carregando, setCarregando] = useState(true);

  useEffect(() => {
    api<Usuario>("/api/auth/eu").then(setUsuario).catch(() => {}).finally(() => setCarregando(false));
  }, []);

  if (carregando) return null;
  if (!usuario) return <Login aoEntrar={setUsuario} />;

  return (
    <div style={{ fontFamily: "system-ui", padding: 16 }}>
      <header style={{ display: "flex", gap: 16, borderBottom: "1px solid #ddd", paddingBottom: 8 }}>
        <strong>Dashboard Lotufo</strong>
        <button onClick={() => setTela("contratos")}>Contratos</button>
        {usuario.perfil === "admin" && <button onClick={() => setTela("admin")}>Administração</button>}
        <span style={{ marginLeft: "auto" }}>{usuario.nome}</span>
        <button onClick={async () => { await api("/api/auth/logout", { method: "POST" }); location.reload(); }}>
          Sair
        </button>
      </header>
      <main style={{ marginTop: 16 }}>
        {tela === "contratos" && <p>Contratos (Task 14)</p>}
        {tela === "admin" && <p>Administração (Task 15)</p>}
      </main>
    </div>
  );
}
```

`src/main.tsx`: renderizar `<App />` (padrão do template Vite; remover CSS de exemplo).

- [ ] **Step 5: Verificar no navegador**

Backend rodando (`uvicorn app.main:app --port 8080`), admin criado via `python -m app.cli criar-admin --nome Leonardo --email leo@lotufo.com`. Rodar `npm run dev` e abrir http://localhost:5173 — login funciona, menu aparece, Sair funciona. **Nota:** em dev via proxy HTTP o cookie `secure` pode ser rejeitado pelo navegador; se o login não persistir, temporariamente aceitar `secure=False` quando `DASH_DEV=1` (env var) em `api_auth.py` — nunca em produção.

- [ ] **Step 6: Commit**

```bash
git add frontend/ backend/ && git commit -m "feat: frontend React com login e layout base"
```

---

### Task 14: Tela de contratos (lista + formulário + estado)

**Files:**
- Create: `frontend/src/Contratos.tsx`
- Modify: `frontend/src/App.tsx` (usar o componente)

**Interfaces:**
- Consumes: API de contratos (Task 12); `api()` (Task 13).
- Produces: componente `<Contratos usuario={usuario} />`: tabela (instrumento, órgão, objeto, valor vigente formatado, estado, fim de execução vigente), botão "Novo contrato" (form com os campos do `ContratoIn`), clique na linha abre detalhe com edição e mudança de estado (select + data + observação). Botões de edição só aparecem se `usuario.perfil !== "diretoria"` (o servidor já bloqueia de verdade).

- [ ] **Step 1: Implementar `src/Contratos.tsx`**

```tsx
import { useEffect, useState } from "react";
import { api } from "./api";
import { Usuario } from "./Login";

interface Contrato {
  id: number; orgao: string; numero_instrumento: string; objeto: string;
  valor_vigente_centavos: number; estado: string;
  execucao_fim_vigente: string | null;
  [k: string]: unknown;
}

function brl(centavos: number): string {
  return (centavos / 100).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

const CAMPOS_FORM = [
  ["orgao", "Órgão/Cliente"], ["numero_instrumento", "Nº do instrumento"],
  ["objeto", "Objeto"], ["valor_original", "Valor original (ex.: 1.000.000,00)"],
  ["data_base", "Data-base (AAAA-MM-DD)"], ["vigencia_inicio", "Vigência início"],
  ["vigencia_fim", "Vigência fim"], ["execucao_inicio", "Execução início"],
  ["execucao_fim", "Execução fim"], ["numero_processo", "Nº processo no órgão"],
  ["pasta_sharepoint", "Pasta SharePoint (URL)"],
] as const;

export default function Contratos({ usuario }: { usuario: Usuario }) {
  const [lista, setLista] = useState<Contrato[]>([]);
  const [novo, setNovo] = useState<Record<string, string> | null>(null);
  const [erro, setErro] = useState("");
  const podeEditar = usuario.perfil !== "diretoria";

  const carregar = () => api<Contrato[]>("/api/contratos").then(setLista);
  useEffect(() => { carregar(); }, []);

  async function salvar(e: React.FormEvent) {
    e.preventDefault();
    try {
      const corpo = Object.fromEntries(Object.entries(novo!).filter(([, v]) => v !== ""));
      await api("/api/contratos", { method: "POST", body: JSON.stringify(corpo) });
      setNovo(null); setErro(""); carregar();
    } catch (err: any) { setErro(String(err.message)); }
  }

  return (
    <div>
      {podeEditar && <button onClick={() => setNovo({})}>Novo contrato</button>}
      {novo && (
        <form onSubmit={salvar} style={{ display: "grid", gap: 8, maxWidth: 480, margin: "12px 0" }}>
          {CAMPOS_FORM.map(([campo, rotulo]) => (
            <input key={campo} placeholder={rotulo} value={novo[campo] ?? ""}
              onChange={e => setNovo({ ...novo, [campo]: e.target.value })} />
          ))}
          <button type="submit">Salvar</button>
          {erro && <p style={{ color: "crimson" }}>{erro}</p>}
        </form>
      )}
      <table cellPadding={6} style={{ borderCollapse: "collapse", marginTop: 12 }}>
        <thead><tr style={{ textAlign: "left", borderBottom: "2px solid #333" }}>
          <th>Instrumento</th><th>Órgão</th><th>Objeto</th><th>Valor vigente</th><th>Estado</th><th>Fim execução</th>
        </tr></thead>
        <tbody>
          {lista.map(c => (
            <tr key={c.id} style={{ borderBottom: "1px solid #ddd" }}>
              <td>{c.numero_instrumento}</td><td>{c.orgao}</td><td>{c.objeto}</td>
              <td>{brl(c.valor_vigente_centavos)}</td><td>{c.estado}</td>
              <td>{c.execucao_fim_vigente ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

- [ ] **Step 2: Usar em `App.tsx`** — substituir o placeholder: `{tela === "contratos" && <Contratos usuario={usuario} />}` (com import).

- [ ] **Step 3: Verificar no navegador** — criar um contrato real (ex.: IC 082/2025, MT-388), ver na tabela com valor formatado; logar como perfil diretoria (criar usuário de teste) e confirmar que o botão "Novo contrato" some e o POST direto é negado pelo servidor.

- [ ] **Step 4: Commit**

```bash
git add frontend/ && git commit -m "feat: tela de contratos com lista e cadastro"
```

---

### Task 15: Tela de administração (usuários + auditoria)

**Files:**
- Create: `backend/app/api_usuarios.py`, `backend/tests/test_api_usuarios.py`, `frontend/src/Admin.tsx`
- Modify: `backend/app/main.py`, `frontend/src/App.tsx`

**Interfaces:**
- Consumes: `exigir("administrar")` (Task 9), `auth.criar_usuario` (Task 8), `GET /api/admin/auditoria` (Task 10).
- Produces: `GET /api/admin/usuarios` (lista sem hash); `POST /api/admin/usuarios` (`{nome, email, senha, perfil}`); `PUT /api/admin/usuarios/{id}` (`{ativo}` e/ou `{perfil}`) — tudo permissão `administrar` + CSRF, tudo auditado (`usuario.criar`, `usuario.atualizar` — sem senha no log); componente `<Admin />` com duas seções: usuários (tabela + form) e auditoria (últimos 100 eventos + selo "cadeia íntegra: sim/não").

- [ ] **Step 1: Escrever os testes que falham**

`backend/tests/test_api_usuarios.py`:

```python
def test_criar_usuario_e_listar(client_admin):
    r = client_admin.post("/api/admin/usuarios", json={
        "nome": "Ana", "email": "ana@lotufo.com",
        "senha": "outra-senha-123", "perfil": "engenharia"})
    assert r.status_code == 201
    lista = client_admin.get("/api/admin/usuarios").json()
    assert any(u["email"] == "ana@lotufo.com" for u in lista)
    assert all("senha_hash" not in u for u in lista)

def test_nao_admin_negado(client_admin, client):
    client_admin.post("/api/admin/usuarios", json={
        "nome": "Eng", "email": "eng@lotufo.com", "senha": "senha-eng-123", "perfil": "engenharia"})
    r = client.post("/api/auth/login", json={"email": "eng@lotufo.com", "senha": "senha-eng-123"})
    client.headers["X-CSRF-Token"] = r.json()["csrf"]
    assert client.get("/api/admin/usuarios").status_code == 403
```

- [ ] **Step 2: Rodar e ver falhar** — Expected: FAIL.

- [ ] **Step 3: Implementar `app/api_usuarios.py`**

```python
import sqlite3
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app import auditoria, auth
from app.api_auth import conexao
from app.permissoes import exigir

router = APIRouter(prefix="/api/admin/usuarios")

class UsuarioIn(BaseModel):
    nome: str
    email: str
    senha: str
    perfil: str

class UsuarioPatch(BaseModel):
    ativo: bool | None = None
    perfil: str | None = None

@router.get("")
def listar(usuario: dict = Depends(exigir("administrar", com_csrf=False)),
           conn: sqlite3.Connection = Depends(conexao)):
    return [dict(r) for r in conn.execute(
        "SELECT id, nome, email, perfil, ativo, criado_em FROM usuarios ORDER BY nome")]

@router.post("", status_code=201)
def criar(dados: UsuarioIn, usuario: dict = Depends(exigir("administrar")),
          conn: sqlite3.Connection = Depends(conexao)):
    if dados.perfil not in ("engenharia", "diretoria", "admin"):
        raise HTTPException(422, "Perfil inválido")
    if len(dados.senha) < 10:
        raise HTTPException(422, "Senha deve ter no mínimo 10 caracteres")
    uid = auth.criar_usuario(conn, dados.nome, dados.email, dados.senha, dados.perfil)
    auditoria.registrar(conn, usuario["id"], "usuario.criar", "usuario", str(uid),
                        depois={"nome": dados.nome, "email": dados.email, "perfil": dados.perfil})
    return {"id": uid}

@router.put("/{alvo_id}")
def atualizar(alvo_id: int, dados: UsuarioPatch,
              usuario: dict = Depends(exigir("administrar")),
              conn: sqlite3.Connection = Depends(conexao)):
    antes = conn.execute("SELECT perfil, ativo FROM usuarios WHERE id=?", (alvo_id,)).fetchone()
    if antes is None:
        raise HTTPException(404, "Usuário não encontrado")
    novos = {k: v for k, v in dados.model_dump().items() if v is not None}
    for campo, valor in novos.items():
        conn.execute(f"UPDATE usuarios SET {campo}=? WHERE id=?", (int(valor) if campo == "ativo" else valor, alvo_id))
    conn.commit()
    auditoria.registrar(conn, usuario["id"], "usuario.atualizar", "usuario", str(alvo_id),
                        antes=dict(antes), depois=novos)
    return {"ok": True}
```

Incluir router em `main.py`.

- [ ] **Step 4: Rodar e ver passar** — Run: `.venv\Scripts\python -m pytest -v` — Expected: PASS (todos).

- [ ] **Step 5: Implementar `frontend/src/Admin.tsx`**

```tsx
import { useEffect, useState } from "react";
import { api } from "./api";

interface Usr { id: number; nome: string; email: string; perfil: string; ativo: number; }
interface Evento { id: number; acao: string; entidade: string | null; criado_em: string; usuario_id: number | null; }

export default function Admin() {
  const [usuarios, setUsuarios] = useState<Usr[]>([]);
  const [audit, setAudit] = useState<{ cadeia_integra: boolean; eventos: Evento[] } | null>(null);
  const [novo, setNovo] = useState({ nome: "", email: "", senha: "", perfil: "engenharia" });

  const carregar = () => {
    api<Usr[]>("/api/admin/usuarios").then(setUsuarios);
    api<typeof audit>("/api/admin/auditoria").then(setAudit as any);
  };
  useEffect(carregar, []);

  async function criar(e: React.FormEvent) {
    e.preventDefault();
    await api("/api/admin/usuarios", { method: "POST", body: JSON.stringify(novo) });
    setNovo({ nome: "", email: "", senha: "", perfil: "engenharia" });
    carregar();
  }

  return (
    <div style={{ display: "grid", gap: 24 }}>
      <section>
        <h2>Usuários</h2>
        <form onSubmit={criar} style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <input placeholder="Nome" value={novo.nome} onChange={e => setNovo({ ...novo, nome: e.target.value })} />
          <input placeholder="E-mail" value={novo.email} onChange={e => setNovo({ ...novo, email: e.target.value })} />
          <input placeholder="Senha (mín. 10)" type="password" value={novo.senha} onChange={e => setNovo({ ...novo, senha: e.target.value })} />
          <select value={novo.perfil} onChange={e => setNovo({ ...novo, perfil: e.target.value })}>
            <option value="engenharia">Engenharia</option>
            <option value="diretoria">Diretoria</option>
            <option value="admin">Administrador</option>
          </select>
          <button type="submit">Criar</button>
        </form>
        <ul>
          {usuarios.map(u => (
            <li key={u.id}>
              {u.nome} — {u.email} — {u.perfil} {u.ativo ? "" : "(inativo)"}
              <button style={{ marginLeft: 8 }} onClick={async () => {
                await api(`/api/admin/usuarios/${u.id}`, { method: "PUT", body: JSON.stringify({ ativo: !u.ativo }) });
                carregar();
              }}>{u.ativo ? "Desativar" : "Reativar"}</button>
            </li>
          ))}
        </ul>
      </section>
      <section>
        <h2>Auditoria {audit && (audit.cadeia_integra ? "✓ cadeia íntegra" : "⚠ CADEIA VIOLADA")}</h2>
        <table cellPadding={4}>
          <tbody>
            {audit?.eventos.map(ev => (
              <tr key={ev.id}><td>{ev.criado_em}</td><td>{ev.acao}</td><td>{ev.entidade ?? ""}</td></tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
```

Em `App.tsx`: `{tela === "admin" && <Admin />}` (com import).

- [ ] **Step 6: Verificar no navegador** — criar usuária Ana (engenharia), ver na lista, ver eventos de auditoria com selo "cadeia íntegra".

- [ ] **Step 7: Commit**

```bash
git add backend/ frontend/ && git commit -m "feat: administracao de usuarios e visor de auditoria"
```

---

### Task 16: Produção mínima — build servido pelo FastAPI, HTTPS, backup horário, autostart

**Files:**
- Create: `backend/app/backup.py`, `backend/tests/test_backup.py`, `scripts/gerar_certificado.ps1` (UTF-8 com BOM), `scripts/instalar_autostart.ps1` (UTF-8 com BOM), `scripts/rodar_producao.ps1` (UTF-8 com BOM)
- Modify: `backend/app/main.py` (servir `frontend/dist`, agendar backup)

**Interfaces:**
- Consumes: `db` (Task 6).
- Produces: `backup.criar_snapshot(origem_db: Path, pasta_destino: Path) -> Path` — usa `VACUUM INTO` para arquivo `dashboard-AAAAMMDD-HHMMSS.db`, mantém os últimos 48; thread de agendamento no `create_app()` (1x/hora, desligada quando `DASH_SEM_JOBS=1` — os testes usam essa env var); app serve o build React em `/` (SPA fallback); scripts de produção.

- [ ] **Step 1: Escrever o teste que falha**

`backend/tests/test_backup.py`:

```python
import sqlite3
from pathlib import Path
from app import backup

def test_snapshot_e_rotacao(tmp_path):
    origem = tmp_path / "app.db"
    conn = sqlite3.connect(origem)
    conn.execute("CREATE TABLE t (x)"); conn.execute("INSERT INTO t VALUES (42)")
    conn.commit(); conn.close()
    destino = tmp_path / "backups"
    arq = backup.criar_snapshot(origem, destino)
    assert arq.exists()
    check = sqlite3.connect(arq)
    assert check.execute("SELECT x FROM t").fetchone()[0] == 42  # backup abre e tem os dados
    check.close()

def test_rotacao_mantem_48(tmp_path, monkeypatch):
    origem = tmp_path / "app.db"
    sqlite3.connect(origem).execute("CREATE TABLE t (x)")
    destino = tmp_path / "backups"; destino.mkdir()
    for i in range(50):
        (destino / f"dashboard-20260101-{i:06d}.db").write_bytes(b"velho")
    backup.criar_snapshot(origem, destino)
    assert len(list(destino.glob("dashboard-*.db"))) == 48
```

- [ ] **Step 2: Rodar e ver falhar** — Expected: FAIL.

- [ ] **Step 3: Implementar `app/backup.py`**

```python
import sqlite3
import threading
import time
from datetime import datetime
from pathlib import Path

MANTER = 48  # ~2 dias de snapshots horários

def criar_snapshot(origem_db: Path, pasta_destino: Path) -> Path:
    pasta_destino.mkdir(parents=True, exist_ok=True)
    nome = f"dashboard-{datetime.now():%Y%m%d-%H%M%S}.db"
    destino = pasta_destino / nome
    conn = sqlite3.connect(origem_db)
    try:
        conn.execute("VACUUM INTO ?", (str(destino),))
    finally:
        conn.close()
    antigos = sorted(pasta_destino.glob("dashboard-*.db"))
    for velho in antigos[:-MANTER] if len(antigos) > MANTER else []:
        velho.unlink()
    return destino

def agendar_backup_horario(origem_db: Path, pasta_destino: Path) -> threading.Thread:
    def loop():
        while True:
            time.sleep(3600)
            try:
                criar_snapshot(origem_db, pasta_destino)
            except Exception:
                pass  # falha de backup vai para o log na fase de observabilidade
    t = threading.Thread(target=loop, daemon=True)
    t.start()
    return t
```

Em `create_app()` (após migrate), respeitando testes:

```python
import os
from pathlib import Path
from app import backup as backup_mod
if os.environ.get("DASH_SEM_JOBS") != "1":
    backup_mod.agendar_backup_horario(db.db_path(), Path("backups"))
```

E em `conftest.py`, na fixture `client`: `monkeypatch.setenv("DASH_SEM_JOBS", "1")`.

- [ ] **Step 4: Servir o build do frontend**

Em `create_app()`, após os routers:

```python
from fastapi.staticfiles import StaticFiles
dist = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
if dist.exists():
    app.mount("/", StaticFiles(directory=dist, html=True), name="frontend")
```

Rodar `npm run build` em `frontend/` e conferir que http://localhost:8080 serve o app.

- [ ] **Step 5: Scripts de produção (UTF-8 com BOM)**

`scripts/gerar_certificado.ps1` — certificado autoassinado para HTTPS interno:

```powershell
$cert = New-SelfSignedCertificate -DnsName $env:DASH_SERVIDOR, "localhost" -CertStoreLocation "Cert:\LocalMachine\My" -NotAfter (Get-Date).AddYears(5)
$pasta = Join-Path $PSScriptRoot "..\certs"; New-Item -ItemType Directory -Force $pasta | Out-Null
$senha = ConvertTo-SecureString "dashboard-local" -AsPlainText -Force
Export-PfxCertificate -Cert $cert -FilePath (Join-Path $pasta "dashboard.pfx") -Password $senha
# converter para PEM (uvicorn precisa de .pem): requer openssl OU usar python:
& "$PSScriptRoot\..\backend\.venv\Scripts\python.exe" -c @"
import subprocess, sys
# extrai chave/cert do pfx com cryptography
from cryptography.hazmat.primitives.serialization import pkcs12, Encoding, PrivateFormat, NoEncryption
data = open(r'$pasta\dashboard.pfx','rb').read()
key, cert, _ = pkcs12.load_key_and_certificates(data, b'dashboard-local')
open(r'$pasta\chave.pem','wb').write(key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()))
open(r'$pasta\cert.pem','wb').write(cert.public_bytes(Encoding.PEM))
"@
```

(Instalar `cryptography` no venv: `.venv\Scripts\python -m pip install cryptography`.)

`scripts/rodar_producao.ps1`:

```powershell
Set-Location (Join-Path $PSScriptRoot "..\backend")
& .venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8443 `
    --ssl-keyfile ..\certs\chave.pem --ssl-certfile ..\certs\cert.pem
```

`scripts/instalar_autostart.ps1` — tarefa agendada que sobe o serviço no boot:

```powershell
$acao = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-ExecutionPolicy Bypass -File `"$PSScriptRoot\rodar_producao.ps1`""
$gatilho = New-ScheduledTaskTrigger -AtStartup
Register-ScheduledTask -TaskName "<tarefa>" -Action $acao -Trigger $gatilho -RunLevel Highest -Force
Write-Host "Tarefa '<tarefa>' instalada. Inicie com: Start-ScheduledTask -TaskName <tarefa>"
```

- [ ] **Step 6: Rodar todos os testes** — Run: `.venv\Scripts\python -m pytest -v` — Expected: PASS (todos).

- [ ] **Step 7: Verificação de produção** — rodar `scripts\gerar_certificado.ps1` e `scripts\rodar_producao.ps1`; abrir `https://<servidor>:8443` de outra máquina da rede; aceitar o certificado autoassinado; logar e criar um contrato. Confirmar que após 1h existe snapshot em `backups\` (ou chamar `backup.criar_snapshot` manualmente para validar).

- [ ] **Step 8: Commit final da fase**

```bash
git add backend/ frontend/ scripts/ && git commit -m "feat: producao minima - build servido, HTTPS interno, backup horario, autostart"
```

---

## Self-Review (executado na escrita do plano)

1. **Cobertura da spec (fases 0–1):** Fase 0 — inventário PA (Task 4), spike RM (Task 3), spike detecção (Task 2) ✓. Fase 1 — projeto (T1, T5), banco endurecido (T6), login/perfis/permissões (T8, T9), auditoria hash-encadeada (T10), cadastro de contratos com estados e aditivos-delta (T11, T12, T14), dinheiro em centavos (T7), HTTPS + backup horário local + autostart (T16), admin de usuários (T15) ✓. Fora da fase (correto): SharePoint/Outlook/RM sync, medições, certidões, geração de documentos.
2. **Placeholders:** nenhum "TBD/TODO"; todos os passos têm código ou comando concreto. Ajustes onde a realidade pode divergir (nomes de colunas do RM, cookie secure em dev) estão sinalizados com a correção esperada.
3. **Consistência de tipos:** `get_conn/migrate` (T6) usados em T8–T12; `exigir` (T9) consumido em T10, T12, T15; `parse_brl` (T7) em T12; nomes de tabelas idênticos entre migrations e repositórios; `client_admin` definido em T12 e usado em T15. ✓

## Workflow de Execução Multi-Modelo (aprovado em 2026-08-28)

**Papéis:**
- **Orquestrador/triagem:** Fable 5 (sessão principal). Despacha subagentes, revisa vereditos, roda os spikes com Leonardo, triaja achados adversariais (verificar contra o código antes de implementar qualquer crítica).
- **Implementadores (1 subagente novo por tarefa):** Opus para Tasks 6–12 e 16 (lógica, dinheiro, auth, auditoria, contratos); Sonnet para Tasks 1, 5, 13, 14, 15 (scaffold/frontend mecânico).
- **Revisor de conformidade (1 subagente novo por tarefa):** Opus — confere o resultado contra a tarefa do plano e a spec.
- **Adversário:** GPT-5.6 Sol via plugin oficial do Codex (`/codex:adversarial-review`), somente leitura. Review gate automático do plugin DESLIGADO — gates manuais abaixo. Loop curto: 1 re-revisão; só continua se sobrar problema material.

**Gates adversariais (GPT-5.6 Sol):**
- **Gate A — após Tasks 7–9.** Brief: "Assuma que o código está quebrado. Ataque: parse/format/rateio monetário (arredondamento, negativo, resíduo), bypass de autenticação (sessão, CSRF, lockout, enumeração de usuários), escalada de permissão. Para cada achado: severidade, arquivo, evidência, reprodução, menor correção segura. Só defeitos que mudam comportamento/segurança/integridade."
- **Gate B — após Tasks 10–12.** Brief: "Ataque: quebrar a cadeia de hash da auditoria sem detecção, corromper o cálculo do vigente (ordem de aditivos, deltas negativos, datas nulas), burlar permissões/CSRF da API de contratos, injeção SQL nos repositórios. Mesmo formato de achado."
- **Gate C — fim da Fase 1.** Diff completo da fase, brief geral de segurança + integridade antes de expor na rede interna.
- **Gate D — permanente.** Toda spec/plano de fase futura passa por `/codex:adversarial-review` antes da execução.

**Regras:** achados do Sol são verificados pelo orquestrador contra o código (rigor antes de concordância); correções via subagente implementador; 1 re-revisão do Sol; Leonardo é o portão final de cada fase. Setup do Codex: `npm i -g @openai/codex`, `codex login` (conta ChatGPT do Leonardo), plugin `codex@openai-codex`, `model = "gpt-5.6-sol"` no config.

## Observações para o executor

- Tasks 2–4 são spikes com participação do Leonardo — executá-las inline na sessão principal, na ordem que a disponibilidade dele permitir; elas não bloqueiam as Tasks 5–16 (código), mas **bloqueiam o início da Fase 2** (congelamento do modelo, conforme spec §12).
- A senha real do admin e credenciais RM nunca entram em arquivos ou no git.
- Se `VACUUM INTO` falhar por versão antiga do SQLite embutido no Python, atualizar Python ≥3.12 resolve (SQLite ≥3.27).
