# Fase 2 — Medições + Cronograma + Painéis: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Medições com os 4 estados e origem por dado, cronograma versionado, fila única de sugestões alimentada por importação manual, painéis previsto×realizado com alertas de calendário e export CSV — sobre a fundação da fase 1.

**Architecture:** Mesmo desenho da fase 1: FastAPI + SQLite (SQL explícito, sem ORM), repositórios por entidade (`app/medicoes.py` etc.) com auditoria em toda escrita, routers finos (`app/api_*.py`) com pydantic na borda e permissões via `exigir()`, frontend React/TS sem libs novas (gráfico em SVG puro). Migrações SQL numeradas e idempotentes.

**Tech Stack:** Python 3.12, FastAPI, sqlite3 stdlib, pytest/httpx; React 18 + Vite + TypeScript (sem dependências novas).

**Spec:** `docs/superpowers/specs/2026-08-28-dashboard-contratos-medicoes-design.md` (v3, **modelo congelado 2026-08-31** — §5 Medição/Cronograma/Sugestão, §6 KPIs, §7 telas 1/2/3/4, §12 fase 2)

## Global Constraints

- Dinheiro SEMPRE em centavos inteiros (`app/dinheiro.py`: `parse_brl`/`format_brl`); float nunca exposto.
- SQL explícito; migrações idempotentes (`IF NOT EXISTS`) em `backend/migrations/NNN_*.sql` (convenção documentada em `app/db.py`).
- Toda escrita registra auditoria via `auditoria.registrar(conn, usuario_id, acao, entidade, entidade_id, antes, depois)`.
- Permissões no servidor: leituras `exigir("ver_paineis", com_csrf=False)`, escritas `exigir("editar_cadastros")` (matriz em `app/permissoes.py`).
- Mensagens de erro em pt-BR; datas ISO `AAAA-MM-DD`; competência `AAAA-MM`.
- Origem por dado: `detectado|aceito|manual` (spec §5) — na fase 2 só `aceito` (via sugestão) e `manual` ocorrem; `detectado` chega na fase 6.
- TDD: teste falhando antes de cada implementação; commits frequentes `feat:/fix:/test:/docs:` + rodapé `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.
- Executor multi-modelo (workflow aprovado em 2026-08-28, mantido): implementadores Opus (1 subagente novo por task), revisor de conformidade Opus por task; orquestrador triaja.
- Rodar testes: `cd backend; .venv\Scripts\python -m pytest -q` (Windows). Frontend: `cd frontend; npx tsc --noEmit; npm run build`.

---

### Task 1: Migração e repositório de medições

**Files:**
- Create: `backend/migrations/003_medicoes.sql`
- Create: `backend/app/medicoes.py`
- Test: `backend/tests/test_medicoes.py`

**Interfaces:**
- Consumes: `db.get_conn/migrate`, `auditoria.registrar`, tabela `contratos` (002).
- Produces (usado pelas Tasks 2, 4, 5):
  - `criar(conn, usuario_id, dados: dict) -> int` — dados: contrato_id, numero, tipo, competencia, opcionais valor_previsto? não — valores entram depois; origem_* junto do valor.
  - `listar(conn, contrato_id: int) -> list[dict]` (com protocolos embutidos em `protocolos: list`)
  - `detalhe(conn, medicao_id: int) -> dict | None`
  - `definir_valor(conn, usuario_id, medicao_id, campo: 'protocolado'|'atestado', centavos: int, origem: str) -> None` (ValueError se protocolado e medição congelada)
  - `registrar_protocolo(conn, usuario_id, medicao_id, data: str, numero_oficio, numero_processo, origem: str) -> int` (congela e move estado prevista→protocolada; reapresentação = nova linha)
  - `mudar_estado(conn, usuario_id, medicao_id, novo: str, motivo: str | None) -> None` (transições válidas; cancelada/desistida de qualquer estado não-final)

- [ ] **Step 1: Escrever a migração**

```sql
-- backend/migrations/003_medicoes.sql
CREATE TABLE IF NOT EXISTS medicoes (
    id INTEGER PRIMARY KEY,
    contrato_id INTEGER NOT NULL REFERENCES contratos(id),
    numero INTEGER NOT NULL CHECK (numero >= 1),
    tipo TEXT NOT NULL CHECK (tipo IN ('execucao','projeto','reajuste')),
    competencia TEXT NOT NULL CHECK (competencia GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]'),
    estado TEXT NOT NULL DEFAULT 'prevista'
        CHECK (estado IN ('prevista','protocolada','nf_emitida','recebida','cancelada','desistida')),
    valor_protocolado_centavos INTEGER CHECK (valor_protocolado_centavos >= 0),
    valor_protocolado_origem TEXT CHECK (valor_protocolado_origem IN ('detectado','aceito','manual')),
    valor_atestado_centavos INTEGER CHECK (valor_atestado_centavos >= 0),
    valor_atestado_origem TEXT CHECK (valor_atestado_origem IN ('detectado','aceito','manual')),
    motivo_represamento TEXT,
    congelada INTEGER NOT NULL DEFAULT 0,
    criado_em TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (contrato_id, numero, tipo)
);

CREATE TABLE IF NOT EXISTS medicao_protocolos (
    id INTEGER PRIMARY KEY,
    medicao_id INTEGER NOT NULL REFERENCES medicoes(id),
    data TEXT NOT NULL,
    numero_oficio TEXT,
    numero_processo TEXT,
    origem TEXT NOT NULL CHECK (origem IN ('detectado','aceito','manual')),
    criado_em TEXT NOT NULL DEFAULT (datetime('now'))
);
```

- [ ] **Step 2: Escrever os testes que falham**

```python
# backend/tests/test_medicoes.py
import pytest
from app import auth, contratos, db, medicoes

@pytest.fixture
def conn(tmp_path, monkeypatch):
    monkeypatch.setenv("DASH_DB_PATH", str(tmp_path / "t.db"))
    c = db.get_conn()
    db.migrate(c)
    auth.criar_usuario(c, "U", "u@lotufo.com", "senha-forte-123", "engenharia")
    yield c
    c.close()

@pytest.fixture
def contrato_id(conn):
    return contratos.criar(conn, 1, {"orgao": "SINFRA", "numero_instrumento": "IC 1/2026",
                                     "objeto": "Obra X", "valor_original_centavos": 100_000_00})

def test_criar_e_listar(conn, contrato_id):
    mid = medicoes.criar(conn, 1, {"contrato_id": contrato_id, "numero": 12,
                                   "tipo": "execucao", "competencia": "2026-07"})
    itens = medicoes.listar(conn, contrato_id)
    assert [ (i["numero"], i["tipo"], i["estado"]) for i in itens ] == [(12, "execucao", "prevista")]
    assert itens[0]["protocolos"] == []
    assert medicoes.detalhe(conn, mid)["competencia"] == "2026-07"

def test_numero_duplicado_no_mesmo_tipo_rejeita(conn, contrato_id):
    medicoes.criar(conn, 1, {"contrato_id": contrato_id, "numero": 1, "tipo": "execucao", "competencia": "2026-07"})
    with pytest.raises(ValueError, match="já existe"):
        medicoes.criar(conn, 1, {"contrato_id": contrato_id, "numero": 1, "tipo": "execucao", "competencia": "2026-08"})
    # mesmo numero em tipo diferente e valido (execucao 1 + reajuste 1)
    medicoes.criar(conn, 1, {"contrato_id": contrato_id, "numero": 1, "tipo": "reajuste", "competencia": "2026-07"})

def test_protocolo_congela_e_muda_estado(conn, contrato_id):
    mid = medicoes.criar(conn, 1, {"contrato_id": contrato_id, "numero": 1, "tipo": "execucao", "competencia": "2026-07"})
    medicoes.definir_valor(conn, 1, mid, "protocolado", 50_000_00, "manual")
    medicoes.registrar_protocolo(conn, 1, mid, "2026-08-05", "CT-279-LT-2026", None, "manual")
    d = medicoes.detalhe(conn, mid)
    assert d["estado"] == "protocolada" and d["congelada"] == 1
    with pytest.raises(ValueError, match="congelada"):
        medicoes.definir_valor(conn, 1, mid, "protocolado", 60_000_00, "manual")
    # atestado continua editavel (glosa sem cerimonia, spec §5)
    medicoes.definir_valor(conn, 1, mid, "atestado", 48_000_00, "manual")
    # reapresentacao = novo evento, sem apagar o anterior
    medicoes.registrar_protocolo(conn, 1, mid, "2026-08-20", "CT-301-LT-2026", None, "manual")
    assert len(medicoes.detalhe(conn, mid)["protocolos"]) == 2

def test_transicoes_de_estado(conn, contrato_id):
    mid = medicoes.criar(conn, 1, {"contrato_id": contrato_id, "numero": 1, "tipo": "execucao", "competencia": "2026-07"})
    with pytest.raises(ValueError, match="Transição inválida"):
        medicoes.mudar_estado(conn, 1, mid, "recebida", None)   # pular etapas nao pode
    medicoes.registrar_protocolo(conn, 1, mid, "2026-08-05", None, None, "manual")
    medicoes.mudar_estado(conn, 1, mid, "nf_emitida", None)
    medicoes.mudar_estado(conn, 1, mid, "recebida", None)
    with pytest.raises(ValueError, match="Transição inválida"):
        medicoes.mudar_estado(conn, 1, mid, "cancelada", None)  # recebida e final

def test_cancelar_com_motivo(conn, contrato_id):
    mid = medicoes.criar(conn, 1, {"contrato_id": contrato_id, "numero": 1, "tipo": "execucao", "competencia": "2026-07"})
    medicoes.mudar_estado(conn, 1, mid, "cancelada", "órgão desistiu")
    assert medicoes.detalhe(conn, mid)["estado"] == "cancelada"

def test_auditoria_registrada(conn, contrato_id):
    medicoes.criar(conn, 1, {"contrato_id": contrato_id, "numero": 1, "tipo": "execucao", "competencia": "2026-07"})
    acoes = [r["acao"] for r in conn.execute("SELECT acao FROM audit_log")]
    assert "medicao.criar" in acoes
```

- [ ] **Step 3: Rodar e ver falhar**

Run: `cd backend; .venv\Scripts\python -m pytest tests/test_medicoes.py -q`
Expected: FAIL (`ModuleNotFoundError: app.medicoes` ou tabela ausente)

- [ ] **Step 4: Implementar o repositório**

```python
# backend/app/medicoes.py
"""Medicoes: 4 estados visiveis + excecoes, origem por dado, congelamento no protocolo.

Fase 2: transicoes manuais (importacao); fases 5-6 passam a mover nf_emitida/recebida
por deteccao. Regra de congelamento (spec §5): apos o 1o protocolo (marco externo),
o valor PROTOCOLADO nao muda mais; o ATESTADO segue editavel (glosa).
"""
import sqlite3

from app import auditoria

# Estado -> estados alcancaveis. cancelada/desistida so de estados nao-finais.
TRANSICOES = {
    "prevista": {"protocolada", "cancelada", "desistida"},
    "protocolada": {"nf_emitida", "cancelada", "desistida"},
    "nf_emitida": {"recebida", "cancelada", "desistida"},
    "recebida": set(),
    "cancelada": set(),
    "desistida": set(),
}

def criar(conn: sqlite3.Connection, usuario_id: int, dados: dict) -> int:
    ja = conn.execute(
        "SELECT id FROM medicoes WHERE contrato_id=? AND numero=? AND tipo=?",
        (dados["contrato_id"], dados["numero"], dados["tipo"])).fetchone()
    if ja:
        raise ValueError(f"Medição {dados['numero']} ({dados['tipo']}) já existe neste contrato")
    cur = conn.execute(
        "INSERT INTO medicoes (contrato_id, numero, tipo, competencia) VALUES (?,?,?,?)",
        (dados["contrato_id"], dados["numero"], dados["tipo"], dados["competencia"]))
    mid = cur.lastrowid
    auditoria.registrar(conn, usuario_id, "medicao.criar", "medicao", mid, None, dados)
    return mid

def detalhe(conn: sqlite3.Connection, medicao_id: int) -> dict | None:
    r = conn.execute("SELECT * FROM medicoes WHERE id=?", (medicao_id,)).fetchone()
    if r is None:
        return None
    d = dict(r)
    d["protocolos"] = [dict(p) for p in conn.execute(
        "SELECT * FROM medicao_protocolos WHERE medicao_id=? ORDER BY id", (medicao_id,))]
    return d

def listar(conn: sqlite3.Connection, contrato_id: int) -> list[dict]:
    ids = [r["id"] for r in conn.execute(
        "SELECT id FROM medicoes WHERE contrato_id=? ORDER BY tipo, numero", (contrato_id,))]
    return [detalhe(conn, i) for i in ids]

def definir_valor(conn, usuario_id: int, medicao_id: int, campo: str, centavos: int, origem: str) -> None:
    assert campo in ("protocolado", "atestado")
    m = detalhe(conn, medicao_id)
    if campo == "protocolado" and m["congelada"]:
        raise ValueError("Medição congelada: valor protocolado não pode mais mudar (registre reapresentação)")
    col_v, col_o = f"valor_{campo}_centavos", f"valor_{campo}_origem"
    antes = {col_v: m[col_v], col_o: m[col_o]}
    conn.execute(f"UPDATE medicoes SET {col_v}=?, {col_o}=? WHERE id=?", (centavos, origem, medicao_id))
    auditoria.registrar(conn, usuario_id, f"medicao.valor_{campo}", "medicao", medicao_id,
                        antes, {col_v: centavos, col_o: origem})

def registrar_protocolo(conn, usuario_id: int, medicao_id: int, data: str,
                        numero_oficio, numero_processo, origem: str) -> int:
    m = detalhe(conn, medicao_id)
    if m["estado"] in ("cancelada", "desistida", "recebida"):
        raise ValueError(f"Medição em estado final ({m['estado']}) não recebe protocolo")
    cur = conn.execute(
        "INSERT INTO medicao_protocolos (medicao_id, data, numero_oficio, numero_processo, origem) "
        "VALUES (?,?,?,?,?)", (medicao_id, data, numero_oficio, numero_processo, origem))
    if m["estado"] == "prevista":
        conn.execute("UPDATE medicoes SET estado='protocolada', congelada=1 WHERE id=?", (medicao_id,))
    else:
        conn.execute("UPDATE medicoes SET congelada=1 WHERE id=?", (medicao_id,))
    auditoria.registrar(conn, usuario_id, "medicao.protocolo", "medicao", medicao_id, None,
                        {"data": data, "numero_oficio": numero_oficio,
                         "numero_processo": numero_processo, "origem": origem})
    return cur.lastrowid

def mudar_estado(conn, usuario_id: int, medicao_id: int, novo: str, motivo: str | None) -> None:
    m = detalhe(conn, medicao_id)
    if novo not in TRANSICOES.get(m["estado"], set()):
        raise ValueError(f"Transição inválida: {m['estado']} → {novo}")
    conn.execute("UPDATE medicoes SET estado=?, motivo_represamento=COALESCE(?, motivo_represamento) WHERE id=?",
                 (novo, motivo, medicao_id))
    auditoria.registrar(conn, usuario_id, "medicao.estado", "medicao", medicao_id,
                        {"estado": m["estado"]}, {"estado": novo, "motivo": motivo})
```

- [ ] **Step 5: Rodar e ver passar** — `pytest tests/test_medicoes.py -q` → PASS; depois a suíte inteira (`pytest -q`) para garantir que nada quebrou.

- [ ] **Step 6: Commit**

```bash
git add backend/migrations/003_medicoes.sql backend/app/medicoes.py backend/tests/test_medicoes.py
git commit -m "feat: medicoes com 4 estados, origem por dado e congelamento no protocolo"
```

---

### Task 2: API de medições

**Files:**
- Create: `backend/app/api_medicoes.py`
- Modify: `backend/app/main.py` (incluir router — seguir o `app.include_router(api_contratos.router)` existente)
- Test: `backend/tests/test_api_medicoes.py`

**Interfaces:**
- Consumes: `medicoes.*` (Task 1), `exigir`, `conexao` (`app.api_auth`), `parse_brl`.
- Produces (frontend Task 7 consome): `GET /api/contratos/{id}/medicoes`; `POST /api/contratos/{id}/medicoes` {numero, tipo, competencia} → 201 {id}; `GET /api/medicoes/{id}`; `PUT /api/medicoes/{id}/valor` {campo: "protocolado"|"atestado", valor: "50.000,00"}; `POST /api/medicoes/{id}/protocolo` {data, numero_oficio?, numero_processo?}; `POST /api/medicoes/{id}/estado` {estado, motivo?}. Origem gravada como `"manual"` em todas as rotas desta fase.

- [ ] **Step 1: Testes que falham**

```python
# backend/tests/test_api_medicoes.py
def _contrato(client_admin):
    r = client_admin.post("/api/contratos", json={
        "orgao": "SINFRA", "numero_instrumento": "IC 1/2026",
        "objeto": "Obra", "valor_original": "100.000,00"})
    return r.json()["id"]

def test_fluxo_completo(client_admin):
    cid = _contrato(client_admin)
    r = client_admin.post(f"/api/contratos/{cid}/medicoes",
                          json={"numero": 1, "tipo": "execucao", "competencia": "2026-07"})
    assert r.status_code == 201
    mid = r.json()["id"]
    assert client_admin.put(f"/api/medicoes/{mid}/valor",
                            json={"campo": "protocolado", "valor": "50.000,00"}).status_code == 200
    assert client_admin.post(f"/api/medicoes/{mid}/protocolo",
                             json={"data": "2026-08-05", "numero_oficio": "CT-279-LT-2026"}).status_code == 201
    d = client_admin.get(f"/api/medicoes/{mid}").json()
    assert d["estado"] == "protocolada" and d["valor_protocolado_centavos"] == 5_000_000
    assert d["valor_protocolado_origem"] == "manual" and len(d["protocolos"]) == 1
    # congelada: mudar protocolado agora e 422
    r = client_admin.put(f"/api/medicoes/{mid}/valor", json={"campo": "protocolado", "valor": "60.000,00"})
    assert r.status_code == 422

def test_validacoes(client_admin):
    cid = _contrato(client_admin)
    assert client_admin.post(f"/api/contratos/{cid}/medicoes",
        json={"numero": 1, "tipo": "outro", "competencia": "2026-07"}).status_code == 422
    assert client_admin.post(f"/api/contratos/{cid}/medicoes",
        json={"numero": 1, "tipo": "execucao", "competencia": "07/2026"}).status_code == 422
    assert client_admin.post("/api/contratos/99999/medicoes",
        json={"numero": 1, "tipo": "execucao", "competencia": "2026-07"}).status_code == 404
    assert client_admin.get("/api/medicoes/99999").status_code == 404

def test_leitura_exige_login(client):
    assert client.get("/api/medicoes/1").status_code in (401, 403)
```

- [ ] **Step 2: Rodar e ver falhar** — 404 nas rotas novas.

- [ ] **Step 3: Implementar o router**

```python
# backend/app/api_medicoes.py
import datetime
import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Literal

from app import medicoes
from app.api_auth import conexao
from app.dinheiro import parse_brl
from app.permissoes import exigir

router = APIRouter()

COMPETENCIA = r"^\d{4}-(0[1-9]|1[0-2])$"

class MedicaoIn(BaseModel):
    numero: int = Field(ge=1, le=999)
    tipo: Literal["execucao", "projeto", "reajuste"]
    competencia: str = Field(pattern=COMPETENCIA)

class ValorIn(BaseModel):
    campo: Literal["protocolado", "atestado"]
    valor: str  # BRL

class ProtocoloIn(BaseModel):
    data: datetime.date
    numero_oficio: str | None = None
    numero_processo: str | None = None

class EstadoIn(BaseModel):
    estado: Literal["protocolada", "nf_emitida", "recebida", "cancelada", "desistida"]
    motivo: str | None = None

def _medicao_existe(conn: sqlite3.Connection, medicao_id: int) -> None:
    if conn.execute("SELECT id FROM medicoes WHERE id=?", (medicao_id,)).fetchone() is None:
        raise HTTPException(404, "Medição não encontrada")

def _contrato_existe(conn: sqlite3.Connection, contrato_id: int) -> None:
    if conn.execute("SELECT id FROM contratos WHERE id=?", (contrato_id,)).fetchone() is None:
        raise HTTPException(404, "Contrato não encontrado")

@router.get("/api/contratos/{contrato_id}/medicoes")
def listar(contrato_id: int, usuario: dict = Depends(exigir("ver_paineis", com_csrf=False)),
           conn: sqlite3.Connection = Depends(conexao)):
    _contrato_existe(conn, contrato_id)
    return medicoes.listar(conn, contrato_id)

@router.post("/api/contratos/{contrato_id}/medicoes", status_code=201)
def criar(contrato_id: int, dados: MedicaoIn,
          usuario: dict = Depends(exigir("editar_cadastros")),
          conn: sqlite3.Connection = Depends(conexao)):
    _contrato_existe(conn, contrato_id)
    try:
        mid = medicoes.criar(conn, usuario["id"], {"contrato_id": contrato_id, **dados.model_dump()})
    except ValueError as e:
        raise HTTPException(422, str(e))
    return {"id": mid}

@router.get("/api/medicoes/{medicao_id}")
def detalhe(medicao_id: int, usuario: dict = Depends(exigir("ver_paineis", com_csrf=False)),
            conn: sqlite3.Connection = Depends(conexao)):
    d = medicoes.detalhe(conn, medicao_id)
    if d is None:
        raise HTTPException(404, "Medição não encontrada")
    return d

@router.put("/api/medicoes/{medicao_id}/valor")
def definir_valor(medicao_id: int, dados: ValorIn,
                  usuario: dict = Depends(exigir("editar_cadastros")),
                  conn: sqlite3.Connection = Depends(conexao)):
    _medicao_existe(conn, medicao_id)
    try:
        medicoes.definir_valor(conn, usuario["id"], medicao_id, dados.campo,
                               parse_brl(dados.valor), "manual")
    except ValueError as e:
        raise HTTPException(422, str(e))
    return {"ok": True}

@router.post("/api/medicoes/{medicao_id}/protocolo", status_code=201)
def protocolo(medicao_id: int, dados: ProtocoloIn,
              usuario: dict = Depends(exigir("editar_cadastros")),
              conn: sqlite3.Connection = Depends(conexao)):
    _medicao_existe(conn, medicao_id)
    try:
        pid = medicoes.registrar_protocolo(conn, usuario["id"], medicao_id, dados.data.isoformat(),
                                           dados.numero_oficio, dados.numero_processo, "manual")
    except ValueError as e:
        raise HTTPException(422, str(e))
    return {"id": pid}

@router.post("/api/medicoes/{medicao_id}/estado")
def estado(medicao_id: int, dados: EstadoIn,
           usuario: dict = Depends(exigir("editar_cadastros")),
           conn: sqlite3.Connection = Depends(conexao)):
    _medicao_existe(conn, medicao_id)
    try:
        medicoes.mudar_estado(conn, usuario["id"], medicao_id, dados.estado, dados.motivo)
    except ValueError as e:
        raise HTTPException(422, str(e))
    return {"ok": True}
```

Em `backend/app/main.py`, junto dos includes existentes: `from app import api_medicoes` e `app.include_router(api_medicoes.router)`.

- [ ] **Step 4: Rodar e ver passar** — arquivo novo e depois `pytest -q` completo.

- [ ] **Step 5: Commit** — `feat: API de medicoes (criar, valores, protocolo, estados)`

---

### Task 3: Cronograma versionado (migração + repositório + API)

**Files:**
- Create: `backend/migrations/004_cronograma.sql`
- Create: `backend/app/cronograma.py`, `backend/app/api_cronograma.py`
- Modify: `backend/app/main.py` (include router)
- Test: `backend/tests/test_cronograma.py`, `backend/tests/test_api_cronograma.py`

**Interfaces:**
- Consumes: `db`, `auditoria`, `contratos` (fixture), `exigir`, `conexao`, `parse_brl`.
- Produces (Task 5 consome):
  - `nova_versao(conn, usuario_id, contrato_id, itens: list[tuple[str, int]], origem: str) -> int` — itens = [(competencia, centavos)]; versão = anterior + 1.
  - `vigente(conn, contrato_id) -> dict | None` — {"numero", "criado_em", "itens": [{"competencia", "valor_previsto_centavos"}]}
  - `previsto_efetivo(conn, contrato_id) -> dict[str, int]` — competência → centavos, honrando "passado congelado": para cada competência vale a versão MAIS RECENTE cujo mês de criação seja ≤ àquela competência; competências anteriores a todas as versões usam a primeira versão. (Regra da spec §5 "passado congelado, futuro pela versão vigente" operacionalizada: revisar cronograma não reescreve meses já decorridos.)

- [ ] **Step 1: Migração**

```sql
-- backend/migrations/004_cronograma.sql
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
    competencia TEXT NOT NULL CHECK (competencia GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]'),
    valor_previsto_centavos INTEGER NOT NULL CHECK (valor_previsto_centavos >= 0),
    UNIQUE (versao_id, competencia)
);
```

- [ ] **Step 2: Testes que falham (repositório)**

```python
# backend/tests/test_cronograma.py
import pytest
from app import auth, contratos, cronograma, db

@pytest.fixture
def conn(tmp_path, monkeypatch):
    monkeypatch.setenv("DASH_DB_PATH", str(tmp_path / "t.db"))
    c = db.get_conn(); db.migrate(c)
    auth.criar_usuario(c, "U", "u@lotufo.com", "senha-forte-123", "engenharia")
    yield c
    c.close()

@pytest.fixture
def cid(conn):
    return contratos.criar(conn, 1, {"orgao": "SINFRA", "numero_instrumento": "IC 1",
                                     "objeto": "X", "valor_original_centavos": 100_00})

def test_versao_e_vigente(conn, cid):
    v1 = cronograma.nova_versao(conn, 1, cid, [("2026-09", 10_00), ("2026-10", 20_00)], "manual")
    assert cronograma.vigente(conn, cid)["numero"] == 1
    cronograma.nova_versao(conn, 1, cid, [("2026-09", 15_00), ("2026-10", 25_00)], "manual")
    vig = cronograma.vigente(conn, cid)
    assert vig["numero"] == 2
    assert vig["itens"][0]["valor_previsto_centavos"] == 15_00
    assert v1 == 1 or v1 > 0  # id retornado

def test_competencia_duplicada_na_versao(conn, cid):
    with pytest.raises(ValueError, match="duplicada"):
        cronograma.nova_versao(conn, 1, cid, [("2026-09", 1), ("2026-09", 2)], "manual")

def test_previsto_efetivo_congela_passado(conn, cid):
    # v1 criada "agora"; efetivo de competencias futuras segue a versao vigente,
    # mas uma competencia ANTERIOR ao mes de criacao da v2 mantem o valor da v1.
    cronograma.nova_versao(conn, 1, cid, [("2020-01", 10_00), ("2099-01", 20_00)], "manual")
    cronograma.nova_versao(conn, 1, cid, [("2020-01", 99_00), ("2099-01", 30_00)], "manual")
    ef = cronograma.previsto_efetivo(conn, cid)
    assert ef["2020-01"] == 10_00   # passado congelado (2020-01 < mes de criacao da v2)
    assert ef["2099-01"] == 30_00   # futuro pela vigente

def test_sem_cronograma(conn, cid):
    assert cronograma.vigente(conn, cid) is None
    assert cronograma.previsto_efetivo(conn, cid) == {}
```

- [ ] **Step 3: Rodar e ver falhar**, depois **implementar**

```python
# backend/app/cronograma.py
"""Cronograma versionado: passado congelado, futuro pela versao vigente (spec §5).

Operacionalizacao do congelamento: cada versao vale a partir do MES em que foi
criada (criado_em). O previsto efetivo de uma competencia e o valor da versao
mais recente criada ate aquela competencia — revisar o cronograma nunca
reescreve meses ja decorridos.
"""
import sqlite3

from app import auditoria

def nova_versao(conn: sqlite3.Connection, usuario_id: int, contrato_id: int,
                itens: list[tuple[str, int]], origem: str) -> int:
    comps = [c for c, _ in itens]
    if len(comps) != len(set(comps)):
        raise ValueError("Competência duplicada na versão do cronograma")
    ultimo = conn.execute("SELECT MAX(numero) AS n FROM cronograma_versoes WHERE contrato_id=?",
                          (contrato_id,)).fetchone()["n"] or 0
    cur = conn.execute("INSERT INTO cronograma_versoes (contrato_id, numero, origem) VALUES (?,?,?)",
                       (contrato_id, ultimo + 1, origem))
    vid = cur.lastrowid
    conn.executemany("INSERT INTO cronograma_itens (versao_id, competencia, valor_previsto_centavos) VALUES (?,?,?)",
                     [(vid, c, v) for c, v in itens])
    auditoria.registrar(conn, usuario_id, "cronograma.nova_versao", "contrato", contrato_id,
                        None, {"versao": ultimo + 1, "itens": len(itens)})
    return ultimo + 1

def _versoes(conn, contrato_id: int) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT * FROM cronograma_versoes WHERE contrato_id=? ORDER BY numero", (contrato_id,))]

def _itens(conn, versao_id: int) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT competencia, valor_previsto_centavos FROM cronograma_itens "
        "WHERE versao_id=? ORDER BY competencia", (versao_id,))]

def vigente(conn: sqlite3.Connection, contrato_id: int) -> dict | None:
    vs = _versoes(conn, contrato_id)
    if not vs:
        return None
    v = vs[-1]
    return {"numero": v["numero"], "criado_em": v["criado_em"], "origem": v["origem"],
            "itens": _itens(conn, v["id"])}

def previsto_efetivo(conn: sqlite3.Connection, contrato_id: int) -> dict[str, int]:
    efetivo: dict[str, int] = {}
    for v in _versoes(conn, contrato_id):        # ordem crescente de numero
        mes_criacao = v["criado_em"][:7]         # 'AAAA-MM' do datetime('now')
        for item in _itens(conn, v["id"]):
            comp = item["competencia"]
            # a versao so pode reescrever competencias >= mes em que nasceu;
            # excecao: se a competencia nunca teve valor, qualquer versao semeia.
            if comp >= mes_criacao or comp not in efetivo:
                efetivo[comp] = item["valor_previsto_centavos"]
    return efetivo
```

- [ ] **Step 4: Testes da API que falham + implementação**

```python
# backend/tests/test_api_cronograma.py
def _contrato(client_admin):
    return client_admin.post("/api/contratos", json={
        "orgao": "S", "numero_instrumento": "IC 1", "objeto": "X",
        "valor_original": "1.000,00"}).json()["id"]

def test_cronograma_api(client_admin):
    cid = _contrato(client_admin)
    assert client_admin.get(f"/api/contratos/{cid}/cronograma").json() is None
    r = client_admin.post(f"/api/contratos/{cid}/cronograma", json={
        "itens": [{"competencia": "2026-09", "valor": "100,00"},
                  {"competencia": "2026-10", "valor": "200,00"}]})
    assert r.status_code == 201 and r.json()["versao"] == 1
    vig = client_admin.get(f"/api/contratos/{cid}/cronograma").json()
    assert vig["numero"] == 1 and vig["itens"][0]["valor_previsto_centavos"] == 100_00
    assert client_admin.post(f"/api/contratos/{cid}/cronograma", json={
        "itens": [{"competencia": "2026-09", "valor": "1,00"},
                  {"competencia": "2026-09", "valor": "2,00"}]}).status_code == 422
    assert client_admin.get("/api/contratos/9999/cronograma").status_code == 404
```

```python
# backend/app/api_cronograma.py
import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app import cronograma
from app.api_auth import conexao
from app.dinheiro import parse_brl
from app.permissoes import exigir

router = APIRouter(prefix="/api/contratos/{contrato_id}/cronograma")

class ItemIn(BaseModel):
    competencia: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    valor: str  # BRL

class VersaoIn(BaseModel):
    itens: list[ItemIn] = Field(min_length=1)

def _contrato_existe(conn, contrato_id: int) -> None:
    if conn.execute("SELECT id FROM contratos WHERE id=?", (contrato_id,)).fetchone() is None:
        raise HTTPException(404, "Contrato não encontrado")

@router.get("")
def obter(contrato_id: int, usuario: dict = Depends(exigir("ver_paineis", com_csrf=False)),
          conn: sqlite3.Connection = Depends(conexao)):
    _contrato_existe(conn, contrato_id)
    return cronograma.vigente(conn, contrato_id)

@router.post("", status_code=201)
def nova_versao(contrato_id: int, dados: VersaoIn,
                usuario: dict = Depends(exigir("editar_cadastros")),
                conn: sqlite3.Connection = Depends(conexao)):
    _contrato_existe(conn, contrato_id)
    try:
        itens = [(i.competencia, parse_brl(i.valor)) for i in dados.itens]
        versao = cronograma.nova_versao(conn, usuario["id"], contrato_id, itens, "manual")
    except ValueError as e:
        raise HTTPException(422, str(e))
    return {"versao": versao}
```

Incluir em `main.py` como nas tasks anteriores.

- [ ] **Step 5: `pytest -q` completo → PASS. Commit** — `feat: cronograma versionado com passado congelado`

---

### Task 4: Fila de sugestões + importação manual

**Files:**
- Create: `backend/migrations/005_sugestoes.sql`
- Create: `backend/app/sugestoes.py`, `backend/app/api_sugestoes.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_sugestoes.py`, `backend/tests/test_api_sugestoes.py`

**Interfaces:**
- Consumes: `medicoes.criar/definir_valor` (Task 1), `auditoria`, `parse_brl`.
- Produces (frontend Task 9 consome):
  - Repo: `criar(conn, usuario_id, tipo: str, payload: dict, confianca: float | None, evidencia: str | None) -> int`; `pendentes(conn) -> list[dict]` (payload já desserializado); `decidir(conn, usuario_id, sugestao_id, decisao: 'aceita'|'corrigida'|'descartada', payload_corrigido: dict | None) -> dict` — aceitar/corrigir uma sugestão `medicao_importada` cria a medição (origem `aceito`) e devolve `{"medicao_id": ...}`; descartar devolve `{}`. Sugestão já decidida → ValueError.
  - API: `GET /api/sugestoes` (pendentes); `POST /api/sugestoes/{id}/decisao` {decisao, payload_corrigido?}; `POST /api/sugestoes/importar` {texto_csv} — linhas `contrato_id;numero;tipo;competencia;valor_brl` viram sugestões `medicao_importada` pendentes; devolve {criadas, erros: [{linha, erro}]}.
- Payload de `medicao_importada`: `{"contrato_id": int, "numero": int, "tipo": str, "competencia": "AAAA-MM", "valor_protocolado_centavos": int | null}`.
- `tipo` da sugestão é TEXT livre (sem CHECK no SQL): as fases 6+ acrescentam tipos novos sem migração de CHECK; a validação de tipos conhecidos fica na aplicação.

- [ ] **Step 1: Migração**

```sql
-- backend/migrations/005_sugestoes.sql
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
```

- [ ] **Step 2: Testes do repositório (falham) + implementação**

```python
# backend/tests/test_sugestoes.py
import pytest
from app import auth, contratos, db, medicoes, sugestoes

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

def _payload(cid, numero=1):
    return {"contrato_id": cid, "numero": numero, "tipo": "execucao",
            "competencia": "2026-07", "valor_protocolado_centavos": 50_00}

def test_aceitar_cria_medicao_com_origem_aceito(conn, cid):
    sid = sugestoes.criar(conn, 1, "medicao_importada", _payload(cid), None, "importacao manual")
    assert [s["id"] for s in sugestoes.pendentes(conn)] == [sid]
    r = sugestoes.decidir(conn, 1, sid, "aceita", None)
    m = medicoes.detalhe(conn, r["medicao_id"])
    assert m["valor_protocolado_origem"] == "aceito" and m["numero"] == 1
    assert sugestoes.pendentes(conn) == []

def test_corrigir_usa_payload_editado(conn, cid):
    sid = sugestoes.criar(conn, 1, "medicao_importada", _payload(cid), None, None)
    r = sugestoes.decidir(conn, 1, sid, "corrigida", _payload(cid, numero=7))
    assert medicoes.detalhe(conn, r["medicao_id"])["numero"] == 7

def test_descartar_nao_cria_nada(conn, cid):
    sid = sugestoes.criar(conn, 1, "medicao_importada", _payload(cid), None, None)
    assert sugestoes.decidir(conn, 1, sid, "descartada", None) == {}
    assert medicoes.listar(conn, cid) == []

def test_decidir_duas_vezes_rejeita(conn, cid):
    sid = sugestoes.criar(conn, 1, "medicao_importada", _payload(cid), None, None)
    sugestoes.decidir(conn, 1, sid, "descartada", None)
    with pytest.raises(ValueError, match="já decidida"):
        sugestoes.decidir(conn, 1, sid, "aceita", None)
```

```python
# backend/app/sugestoes.py
"""Fila unica de sugestoes (spec §5): payload proposto + evidencia + decisao.

Fase 2: unico tipo e' medicao_importada (importacao manual). Aceitar/corrigir
cria a medicao com origem 'aceito' — o rastro (quem decidiu, quando, com que
payload) fica na propria sugestao e na auditoria.
"""
import json
import sqlite3

from app import auditoria, medicoes

def criar(conn, usuario_id: int, tipo: str, payload: dict, confianca, evidencia) -> int:
    cur = conn.execute(
        "INSERT INTO sugestoes (tipo, payload, confianca, evidencia) VALUES (?,?,?,?)",
        (tipo, json.dumps(payload, ensure_ascii=False, sort_keys=True), confianca, evidencia))
    auditoria.registrar(conn, usuario_id, "sugestao.criar", "sugestao", cur.lastrowid, None,
                        {"tipo": tipo, "payload": payload})
    return cur.lastrowid

def pendentes(conn) -> list[dict]:
    out = []
    for r in conn.execute("SELECT * FROM sugestoes WHERE estado='pendente' ORDER BY id"):
        d = dict(r)
        d["payload"] = json.loads(d["payload"])
        out.append(d)
    return out

def decidir(conn, usuario_id: int, sugestao_id: int, decisao: str,
            payload_corrigido: dict | None) -> dict:
    r = conn.execute("SELECT * FROM sugestoes WHERE id=?", (sugestao_id,)).fetchone()
    if r is None:
        raise ValueError("Sugestão não encontrada")
    if r["estado"] != "pendente":
        raise ValueError(f"Sugestão já decidida ({r['estado']})")
    resultado: dict = {}
    if decisao in ("aceita", "corrigida"):
        payload = payload_corrigido if decisao == "corrigida" else json.loads(r["payload"])
        mid = medicoes.criar(conn, usuario_id, {
            "contrato_id": payload["contrato_id"], "numero": payload["numero"],
            "tipo": payload["tipo"], "competencia": payload["competencia"]})
        if payload.get("valor_protocolado_centavos") is not None:
            medicoes.definir_valor(conn, usuario_id, mid, "protocolado",
                                   payload["valor_protocolado_centavos"], "aceito")
        resultado = {"medicao_id": mid}
    conn.execute("UPDATE sugestoes SET estado=?, decisor_id=?, decidido_em=datetime('now') WHERE id=?",
                 (decisao, usuario_id, sugestao_id))
    auditoria.registrar(conn, usuario_id, "sugestao.decidir", "sugestao", sugestao_id,
                        {"estado": "pendente"}, {"estado": decisao, **resultado})
    return resultado
```

- [ ] **Step 3: Testes da API (falham) + implementação**

```python
# backend/tests/test_api_sugestoes.py
def _contrato(client_admin):
    return client_admin.post("/api/contratos", json={
        "orgao": "S", "numero_instrumento": "IC 1", "objeto": "X",
        "valor_original": "1.000,00"}).json()["id"]

def test_importar_e_aceitar(client_admin):
    cid = _contrato(client_admin)
    r = client_admin.post("/api/sugestoes/importar", json={
        "texto_csv": f"{cid};12;execucao;2026-07;50.000,00\n{cid};13;execucao;2026-08;60.000,00\nlinha;invalida"})
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["criadas"] == 2 and len(corpo["erros"]) == 1 and corpo["erros"][0]["linha"] == 3
    pend = client_admin.get("/api/sugestoes").json()
    assert len(pend) == 2 and pend[0]["payload"]["numero"] == 12
    r = client_admin.post(f"/api/sugestoes/{pend[0]['id']}/decisao", json={"decisao": "aceita"})
    assert r.status_code == 200 and "medicao_id" in r.json()
    assert len(client_admin.get("/api/sugestoes").json()) == 1

def test_decisao_repetida_422(client_admin):
    cid = _contrato(client_admin)
    client_admin.post("/api/sugestoes/importar", json={"texto_csv": f"{cid};1;execucao;2026-07;1,00"})
    sid = client_admin.get("/api/sugestoes").json()[0]["id"]
    client_admin.post(f"/api/sugestoes/{sid}/decisao", json={"decisao": "descartada"})
    assert client_admin.post(f"/api/sugestoes/{sid}/decisao",
                             json={"decisao": "aceita"}).status_code == 422
```

```python
# backend/app/api_sugestoes.py
import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Literal

from app import sugestoes
from app.api_auth import conexao
from app.dinheiro import parse_brl
from app.permissoes import exigir

router = APIRouter(prefix="/api/sugestoes")

TIPOS_MEDICAO = ("execucao", "projeto", "reajuste")

class DecisaoIn(BaseModel):
    decisao: Literal["aceita", "corrigida", "descartada"]
    payload_corrigido: dict | None = None

class ImportarIn(BaseModel):
    texto_csv: str

@router.get("")
def listar(usuario: dict = Depends(exigir("ver_paineis", com_csrf=False)),
           conn: sqlite3.Connection = Depends(conexao)):
    return sugestoes.pendentes(conn)

@router.post("/{sugestao_id}/decisao")
def decidir(sugestao_id: int, dados: DecisaoIn,
            usuario: dict = Depends(exigir("editar_cadastros")),
            conn: sqlite3.Connection = Depends(conexao)):
    if dados.decisao == "corrigida" and not dados.payload_corrigido:
        raise HTTPException(422, "Decisão 'corrigida' exige payload_corrigido")
    try:
        return sugestoes.decidir(conn, usuario["id"], sugestao_id, dados.decisao,
                                 dados.payload_corrigido)
    except ValueError as e:
        raise HTTPException(422, str(e))

@router.post("/importar")
def importar(dados: ImportarIn, usuario: dict = Depends(exigir("editar_cadastros")),
             conn: sqlite3.Connection = Depends(conexao)):
    criadas, erros = 0, []
    for n, linha in enumerate(dados.texto_csv.strip().splitlines(), start=1):
        if not linha.strip():
            continue
        try:
            campos = [c.strip() for c in linha.split(";")]
            if len(campos) != 5:
                raise ValueError("Esperado: contrato_id;numero;tipo;competencia;valor")
            contrato_id, numero, tipo, competencia, valor = campos
            if tipo not in TIPOS_MEDICAO:
                raise ValueError(f"Tipo inválido: {tipo}")
            if conn.execute("SELECT id FROM contratos WHERE id=?", (int(contrato_id),)).fetchone() is None:
                raise ValueError(f"Contrato {contrato_id} não existe")
            payload = {"contrato_id": int(contrato_id), "numero": int(numero), "tipo": tipo,
                       "competencia": competencia, "valor_protocolado_centavos": parse_brl(valor)}
            sugestoes.criar(conn, usuario["id"], "medicao_importada", payload, None,
                            f"importação manual linha {n}")
            criadas += 1
        except (ValueError, KeyError) as e:
            erros.append({"linha": n, "erro": str(e)})
    return {"criadas": criadas, "erros": erros}
```

Incluir router em `main.py`.

- [ ] **Step 4: `pytest -q` completo → PASS. Commit** — `feat: fila de sugestoes com importacao manual de medicoes`

---

### Task 5: KPIs e alertas (repositório `paineis.py`)

**Files:**
- Create: `backend/app/paineis.py`
- Test: `backend/tests/test_paineis.py`

**Interfaces:**
- Consumes: `cronograma.previsto_efetivo` (Task 3), tabelas `medicoes` (Task 1), `contratos.vigente(conn, id) -> dict` com `valor_vigente_centavos` (fase 1).
- Produces (Task 6 consome):
  - `curva(conn, contrato_id) -> list[dict]` — por competência ordenada: `{"competencia", "previsto_centavos", "medido_execucao_centavos", "medido_reajuste_centavos", "atestado_pendente": bool}`. Medido = valor_atestado se houver, senão valor_protocolado com `atestado_pendente=True` (§6). Medições canceladas/desistidas ficam de fora.
  - `saldo(conn, contrato_id) -> dict` — `{"vigente_centavos", "atestado_execucao_centavos", "saldo_centavos", "formula": "vigente − atestado (execução)"}` (fórmula visível, §6).
  - `consolidado(conn) -> dict` — `{"carteira": [{contrato resumido + saldo}], "por_mes": [{"competencia", "previsto_centavos", "medido_centavos"}]}` sobre contratos com estado `ativo`.
  - `alertas(conn, hoje: str) -> list[dict]` — `{"tipo": "vigencia_vencendo"|"execucao_vencendo"|"data_base"|"medicao_sem_protocolo", "contrato_id", "mensagem"}`: vigência/execução vigentes (com aditivos) a ≤60 dias de `hoje`; aniversário da data-base no mês de `hoje` (reajuste anual); competência ≤ mês de `hoje` prevista no cronograma sem medição de execução protocolada.

- [ ] **Step 1: Testes que falham**

```python
# backend/tests/test_paineis.py
import pytest
from app import auth, contratos, cronograma, db, medicoes, paineis

@pytest.fixture
def conn(tmp_path, monkeypatch):
    monkeypatch.setenv("DASH_DB_PATH", str(tmp_path / "t.db"))
    c = db.get_conn(); db.migrate(c)
    auth.criar_usuario(c, "U", "u@lotufo.com", "senha-forte-123", "engenharia")
    yield c
    c.close()

@pytest.fixture
def cid(conn):
    return contratos.criar(conn, 1, {"orgao": "S", "numero_instrumento": "IC 1", "objeto": "X",
                                     "valor_original_centavos": 1_000_00,
                                     "vigencia_fim": "2026-10-15", "data_base": "2025-08-01"})

def _medir(conn, cid, numero, tipo, comp, protocolado, atestado=None):
    mid = medicoes.criar(conn, 1, {"contrato_id": cid, "numero": numero, "tipo": tipo, "competencia": comp})
    medicoes.definir_valor(conn, 1, mid, "protocolado", protocolado, "manual")
    medicoes.registrar_protocolo(conn, 1, mid, f"{comp}-28", None, None, "manual")
    if atestado is not None:
        medicoes.definir_valor(conn, 1, mid, "atestado", atestado, "manual")
    return mid

def test_curva_previsto_e_medido(conn, cid):
    cronograma.nova_versao(conn, 1, cid, [("2026-07", 300_00), ("2026-08", 400_00)], "manual")
    _medir(conn, cid, 1, "execucao", "2026-07", 250_00, atestado=240_00)
    _medir(conn, cid, 1, "reajuste", "2026-07", 10_00)
    pontos = {p["competencia"]: p for p in paineis.curva(conn, cid)}
    assert pontos["2026-07"]["previsto_centavos"] == 300_00
    assert pontos["2026-07"]["medido_execucao_centavos"] == 240_00      # atestado vence
    assert pontos["2026-07"]["medido_reajuste_centavos"] == 10_00       # serie propria (§6)
    assert pontos["2026-07"]["atestado_pendente"] is False
    assert pontos["2026-08"]["previsto_centavos"] == 400_00 and pontos["2026-08"]["medido_execucao_centavos"] == 0

def test_medido_usa_protocolado_marcado_enquanto_nao_atesta(conn, cid):
    _medir(conn, cid, 1, "execucao", "2026-07", 250_00)  # sem atestado
    p = paineis.curva(conn, cid)[0]
    assert p["medido_execucao_centavos"] == 250_00 and p["atestado_pendente"] is True

def test_cancelada_fica_fora(conn, cid):
    mid = medicoes.criar(conn, 1, {"contrato_id": cid, "numero": 9, "tipo": "execucao", "competencia": "2026-09"})
    medicoes.mudar_estado(conn, 1, mid, "cancelada", "x")
    assert all(p["competencia"] != "2026-09" for p in paineis.curva(conn, cid))

def test_saldo_formula_visivel(conn, cid):
    _medir(conn, cid, 1, "execucao", "2026-07", 250_00, atestado=240_00)
    s = paineis.saldo(conn, cid)
    assert s["vigente_centavos"] == 1_000_00 and s["atestado_execucao_centavos"] == 240_00
    assert s["saldo_centavos"] == 760_00 and "vigente" in s["formula"]

def test_consolidado_soma_só_ativos(conn, cid):
    outro = contratos.criar(conn, 1, {"orgao": "S", "numero_instrumento": "IC 2", "objeto": "Y",
                                      "valor_original_centavos": 500_00})
    contratos.mudar_estado(conn, 1, outro, "encerrado", "2026-01-01", None)
    _medir(conn, cid, 1, "execucao", "2026-07", 250_00)
    c = paineis.consolidado(conn)
    assert [x["id"] for x in c["carteira"]] == [cid]
    assert c["por_mes"][0]["competencia"] == "2026-07" and c["por_mes"][0]["medido_centavos"] == 250_00

def test_alertas(conn, cid):
    cronograma.nova_versao(conn, 1, cid, [("2026-07", 300_00)], "manual")
    tipos = {a["tipo"] for a in paineis.alertas(conn, hoje="2026-08-31")}
    # vigencia 2026-10-15 esta a <=60 dias de 2026-08-31; data_base aniversaria em agosto;
    # 2026-07 prevista sem protocolo de execucao
    assert {"vigencia_vencendo", "data_base", "medicao_sem_protocolo"} <= tipos
    # protocolada a medicao, o alerta de medicao some
    _medir(conn, cid, 1, "execucao", "2026-07", 1_00)
    tipos2 = {a["tipo"] for a in paineis.alertas(conn, hoje="2026-08-31")}
    assert "medicao_sem_protocolo" not in tipos2
```

- [ ] **Step 2: Rodar e ver falhar, implementar**

```python
# backend/app/paineis.py
"""KPIs (spec §6): eixos temporais explicitos, reajuste como serie propria,
saldo com formula visivel. Alertas de calendario (spec §7 tela 2) derivados
dos cadastros — nada e inventado: sem dado, sem metrica (regra da casa)."""
import datetime
import sqlite3

from app import contratos, cronograma

ESTADOS_VALIDOS = ("protocolada", "nf_emitida", "recebida")  # medem; excecoes ficam fora

def _medido(conn, contrato_id: int) -> dict[str, dict]:
    """competencia -> {execucao, reajuste, atestado_pendente} em centavos."""
    out: dict[str, dict] = {}
    for m in conn.execute(
            "SELECT * FROM medicoes WHERE contrato_id=? AND estado IN (?,?,?)",
            (contrato_id, *ESTADOS_VALIDOS)):
        comp = m["competencia"]
        p = out.setdefault(comp, {"execucao": 0, "reajuste": 0, "projeto": 0, "atestado_pendente": False})
        if m["valor_atestado_centavos"] is not None:
            valor = m["valor_atestado_centavos"]
        else:
            valor = m["valor_protocolado_centavos"] or 0
            if valor:
                p["atestado_pendente"] = True   # §6: protocolado enquanto nao atestada — marcado
        p[m["tipo"]] += valor
    return out

def curva(conn: sqlite3.Connection, contrato_id: int) -> list[dict]:
    previsto = cronograma.previsto_efetivo(conn, contrato_id)
    medido = _medido(conn, contrato_id)
    comps = sorted(set(previsto) | set(medido))
    return [{"competencia": c,
             "previsto_centavos": previsto.get(c, 0),
             "medido_execucao_centavos": medido.get(c, {}).get("execucao", 0),
             "medido_reajuste_centavos": medido.get(c, {}).get("reajuste", 0),
             "medido_projeto_centavos": medido.get(c, {}).get("projeto", 0),
             "atestado_pendente": medido.get(c, {}).get("atestado_pendente", False)}
            for c in comps]

def saldo(conn: sqlite3.Connection, contrato_id: int) -> dict:
    vig = contratos.vigente(conn, contrato_id)
    atestado = conn.execute(
        "SELECT COALESCE(SUM(COALESCE(valor_atestado_centavos, valor_protocolado_centavos, 0)), 0) AS s "
        "FROM medicoes WHERE contrato_id=? AND tipo='execucao' AND estado IN (?,?,?)",
        (contrato_id, *ESTADOS_VALIDOS)).fetchone()["s"]
    return {"vigente_centavos": vig["valor_vigente_centavos"],
            "atestado_execucao_centavos": atestado,
            "saldo_centavos": vig["valor_vigente_centavos"] - atestado,
            "formula": "saldo = vigente − atestado (execução); reajustes em série própria"}

def consolidado(conn: sqlite3.Connection) -> dict:
    ativos = [r["id"] for r in conn.execute("SELECT id FROM contratos WHERE estado='ativo' ORDER BY id")]
    carteira = []
    por_mes: dict[str, dict] = {}
    for cid in ativos:
        vig = contratos.vigente(conn, cid)
        s = saldo(conn, cid)
        carteira.append({"id": cid, "orgao": vig["orgao"], "numero_instrumento": vig["numero_instrumento"],
                         "objeto": vig["objeto"], "estado": vig["estado"], **s})
        for p in curva(conn, cid):
            m = por_mes.setdefault(p["competencia"], {"previsto_centavos": 0, "medido_centavos": 0})
            m["previsto_centavos"] += p["previsto_centavos"]
            m["medido_centavos"] += (p["medido_execucao_centavos"] + p["medido_reajuste_centavos"]
                                     + p["medido_projeto_centavos"])
    return {"carteira": carteira,
            "por_mes": [{"competencia": c, **v} for c, v in sorted(por_mes.items())]}

def alertas(conn: sqlite3.Connection, hoje: str | None = None) -> list[dict]:
    hoje_d = datetime.date.fromisoformat(hoje) if hoje else datetime.date.today()
    limite = hoje_d + datetime.timedelta(days=60)
    out: list[dict] = []
    for r in conn.execute("SELECT id FROM contratos WHERE estado='ativo'"):
        cid = r["id"]
        vig = contratos.vigente(conn, cid)
        rotulo = f"{vig['numero_instrumento']} ({vig['orgao']})"
        for campo, tipo in (("vigencia_fim_vigente", "vigencia_vencendo"),
                            ("execucao_fim_vigente", "execucao_vencendo")):
            fim = vig.get(campo)
            if fim and hoje_d <= datetime.date.fromisoformat(fim) <= limite:
                out.append({"tipo": tipo, "contrato_id": cid,
                            "mensagem": f"{rotulo}: {tipo.replace('_', ' ')} em {fim}"})
        if vig.get("data_base") and vig["data_base"][5:7] == f"{hoje_d.month:02d}":
            out.append({"tipo": "data_base", "contrato_id": cid,
                        "mensagem": f"{rotulo}: aniversário da data-base ({vig['data_base']}) — reajuste anual"})
        previsto = cronograma.previsto_efetivo(conn, cid)
        protocoladas = {m["competencia"] for m in conn.execute(
            "SELECT competencia FROM medicoes WHERE contrato_id=? AND tipo='execucao' "
            "AND estado IN (?,?,?)", (cid, *ESTADOS_VALIDOS))}
        mes_atual = hoje_d.isoformat()[:7]
        for comp in sorted(previsto):
            if comp <= mes_atual and previsto[comp] > 0 and comp not in protocoladas:
                out.append({"tipo": "medicao_sem_protocolo", "contrato_id": cid,
                            "mensagem": f"{rotulo}: competência {comp} prevista no cronograma sem medição protocolada"})
    return out
```

- [ ] **Step 3: `pytest -q` completo → PASS. Commit** — `feat: KPIs (curva, saldo, consolidado) e alertas de calendario`

---

### Task 6: API de painéis + export CSV

**Files:**
- Create: `backend/app/api_paineis.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_api_paineis.py`

**Interfaces:**
- Consumes: `paineis.*` (Task 5), `medicoes.listar` (Task 1), `format_brl`.
- Produces (frontend Tasks 8/10 consome):
  - `GET /api/paineis/consolidado` → `paineis.consolidado`
  - `GET /api/paineis/alertas` → `paineis.alertas` (hoje = data do servidor)
  - `GET /api/contratos/{id}/curva` → `{"curva": [...], "saldo": {...}}`
  - `GET /api/contratos/{id}/medicoes.csv` e `GET /api/paineis/consolidado.csv` → `text/csv; charset=utf-8` **com BOM** (Excel pt-BR abre acentos direito), separador `;`, valores em BRL (`format_brl`). Toda listagem exporta CSV (spec §7).

- [ ] **Step 1: Testes que falham**

```python
# backend/tests/test_api_paineis.py
def _cenario(client_admin):
    cid = client_admin.post("/api/contratos", json={
        "orgao": "SINFRA", "numero_instrumento": "IC 1/2026", "objeto": "Obra X",
        "valor_original": "1.000,00"}).json()["id"]
    client_admin.post(f"/api/contratos/{cid}/cronograma", json={
        "itens": [{"competencia": "2026-07", "valor": "300,00"}]})
    mid = client_admin.post(f"/api/contratos/{cid}/medicoes",
        json={"numero": 1, "tipo": "execucao", "competencia": "2026-07"}).json()["id"]
    client_admin.put(f"/api/medicoes/{mid}/valor", json={"campo": "protocolado", "valor": "250,00"})
    client_admin.post(f"/api/medicoes/{mid}/protocolo", json={"data": "2026-07-28"})
    return cid

def test_consolidado_e_curva(client_admin):
    cid = _cenario(client_admin)
    c = client_admin.get("/api/paineis/consolidado").json()
    assert c["carteira"][0]["saldo_centavos"] == 750_00
    r = client_admin.get(f"/api/contratos/{cid}/curva").json()
    assert r["curva"][0]["previsto_centavos"] == 300_00
    assert r["saldo"]["formula"].startswith("saldo")

def test_alertas_endpoint(client_admin):
    _cenario(client_admin)
    r = client_admin.get("/api/paineis/alertas")
    assert r.status_code == 200 and isinstance(r.json(), list)

def test_csv_medicoes(client_admin):
    cid = _cenario(client_admin)
    r = client_admin.get(f"/api/contratos/{cid}/medicoes.csv")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert "attachment" in r.headers["content-disposition"]
    corpo = r.content.decode("utf-8-sig")
    assert corpo.splitlines()[0] == "numero;tipo;competencia;estado;valor_protocolado;valor_atestado;origem_protocolado"
    assert "1;execucao;2026-07;protocolada;R$ 250,00;;manual" in corpo

def test_csv_consolidado(client_admin):
    _cenario(client_admin)
    corpo = client_admin.get("/api/paineis/consolidado.csv").content.decode("utf-8-sig")
    assert corpo.splitlines()[0] == "contrato;orgao;objeto;vigente;atestado_execucao;saldo"
```

- [ ] **Step 2: Implementar**

```python
# backend/app/api_paineis.py
import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from app import medicoes, paineis
from app.api_auth import conexao
from app.dinheiro import format_brl
from app.permissoes import exigir

router = APIRouter()

def _csv(nome: str, cabecalho: list[str], linhas: list[list[str]]) -> Response:
    corpo = "\r\n".join([";".join(cabecalho)] + [";".join(l) for l in linhas]) + "\r\n"
    # utf-8-sig: o BOM faz o Excel pt-BR abrir acentuacao correta com separador ;
    return Response(corpo.encode("utf-8-sig"), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{nome}"'})

def _contrato_existe(conn, contrato_id: int) -> None:
    if conn.execute("SELECT id FROM contratos WHERE id=?", (contrato_id,)).fetchone() is None:
        raise HTTPException(404, "Contrato não encontrado")

@router.get("/api/paineis/consolidado")
def consolidado(usuario: dict = Depends(exigir("ver_paineis", com_csrf=False)),
                conn: sqlite3.Connection = Depends(conexao)):
    return paineis.consolidado(conn)

@router.get("/api/paineis/alertas")
def alertas(usuario: dict = Depends(exigir("ver_paineis", com_csrf=False)),
            conn: sqlite3.Connection = Depends(conexao)):
    return paineis.alertas(conn)

@router.get("/api/contratos/{contrato_id}/curva")
def curva(contrato_id: int, usuario: dict = Depends(exigir("ver_paineis", com_csrf=False)),
          conn: sqlite3.Connection = Depends(conexao)):
    _contrato_existe(conn, contrato_id)
    return {"curva": paineis.curva(conn, contrato_id), "saldo": paineis.saldo(conn, contrato_id)}

@router.get("/api/contratos/{contrato_id}/medicoes.csv")
def medicoes_csv(contrato_id: int, usuario: dict = Depends(exigir("ver_paineis", com_csrf=False)),
                 conn: sqlite3.Connection = Depends(conexao)):
    _contrato_existe(conn, contrato_id)
    linhas = []
    for m in medicoes.listar(conn, contrato_id):
        linhas.append([str(m["numero"]), m["tipo"], m["competencia"], m["estado"],
                       format_brl(m["valor_protocolado_centavos"]) if m["valor_protocolado_centavos"] is not None else "",
                       format_brl(m["valor_atestado_centavos"]) if m["valor_atestado_centavos"] is not None else "",
                       m["valor_protocolado_origem"] or ""])
    return _csv(f"medicoes-contrato-{contrato_id}.csv",
                ["numero", "tipo", "competencia", "estado", "valor_protocolado",
                 "valor_atestado", "origem_protocolado"], linhas)

@router.get("/api/paineis/consolidado.csv")
def consolidado_csv(usuario: dict = Depends(exigir("ver_paineis", com_csrf=False)),
                    conn: sqlite3.Connection = Depends(conexao)):
    c = paineis.consolidado(conn)
    linhas = [[x["numero_instrumento"], x["orgao"], x["objeto"],
               format_brl(x["vigente_centavos"]), format_brl(x["atestado_execucao_centavos"]),
               format_brl(x["saldo_centavos"])] for x in c["carteira"]]
    return _csv("consolidado.csv",
                ["contrato", "orgao", "objeto", "vigente", "atestado_execucao", "saldo"], linhas)
```

Incluir router em `main.py`.

- [ ] **Step 3: `pytest -q` completo → PASS. Commit** — `feat: API de paineis, alertas e export CSV`

---

### Task 7: Frontend — página do contrato com medições

**Files:**
- Create: `frontend/src/ContratoPagina.tsx`, `frontend/src/Medicoes.tsx`
- Modify: `frontend/src/Contratos.tsx` (linha da lista vira link "abrir" que chama `aoAbrir(id)` — prop nova), `frontend/src/App.tsx`

**Interfaces:**
- Consumes: rotas das Tasks 2 e 6; `api()` e `ApiErro` de `api.ts`; padrão de tela da fase 1 (estado local + `useEffect`, sem router — navegação por `useState` no App, como as telas existentes).
- Produces: `ContratoPagina({ contratoId, usuario, aoVoltar })` com abas `medicoes | cronograma` (cronograma na Task 8); `Medicoes({ contratoId, podeEditar })`.
- `App.tsx` ganha o estado `contratoAberto: number | null`; quando setado, renderiza `<ContratoPagina/>` no lugar de `<Contratos/>`.

- [ ] **Step 1: Implementar `Medicoes.tsx`**

```tsx
// frontend/src/Medicoes.tsx
import { useEffect, useState } from "react";
import { api, ApiErro } from "./api";

type Protocolo = { id: number; data: string; numero_oficio: string | null; origem: string };
export type Medicao = {
  id: number; numero: number; tipo: string; competencia: string; estado: string;
  valor_protocolado_centavos: number | null; valor_protocolado_origem: string | null;
  valor_atestado_centavos: number | null; valor_atestado_origem: string | null;
  congelada: number; protocolos: Protocolo[];
};

export function brl(centavos: number | null): string {
  if (centavos === null) return "—";
  return (centavos / 100).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

const PROXIMOS: Record<string, string[]> = {
  protocolada: ["nf_emitida", "cancelada", "desistida"],
  nf_emitida: ["recebida", "cancelada", "desistida"],
  prevista: ["cancelada", "desistida"],
};

export default function Medicoes({ contratoId, podeEditar }: { contratoId: number; podeEditar: boolean }) {
  const [itens, setItens] = useState<Medicao[]>([]);
  const [erro, setErro] = useState("");
  const [novo, setNovo] = useState({ numero: "", tipo: "execucao", competencia: "" });

  const carregar = () => api<Medicao[]>(`/api/contratos/${contratoId}/medicoes`).then(setItens);
  useEffect(() => { carregar().catch(e => setErro(String(e))); }, [contratoId]);

  const agir = async (fn: () => Promise<unknown>) => {
    setErro("");
    try { await fn(); await carregar(); }
    catch (e) { setErro(e instanceof ApiErro ? e.message : String(e)); }
  };

  return (
    <div>
      {erro && <p style={{ color: "crimson" }}>{erro}</p>}
      <table cellPadding={6} style={{ borderCollapse: "collapse", width: "100%" }}>
        <thead><tr style={{ textAlign: "left", borderBottom: "2px solid #333" }}>
          <th>Nº</th><th>Tipo</th><th>Competência</th><th>Estado</th>
          <th>Protocolado</th><th>Atestado</th><th>Protocolos</th>{podeEditar && <th>Ações</th>}
        </tr></thead>
        <tbody>{itens.map(m => (
          <tr key={m.id} style={{ borderBottom: "1px solid #ddd" }}>
            <td>{m.numero}ª</td><td>{m.tipo}</td><td>{m.competencia}</td>
            <td>{m.estado}{m.congelada ? " 🔒" : ""}</td>
            <td title={`origem: ${m.valor_protocolado_origem ?? "—"}`}>{brl(m.valor_protocolado_centavos)}</td>
            <td title={`origem: ${m.valor_atestado_origem ?? "—"}`}>{brl(m.valor_atestado_centavos)}</td>
            <td>{m.protocolos.map(p => `${p.data}${p.numero_oficio ? ` (${p.numero_oficio})` : ""}`).join("; ") || "—"}</td>
            {podeEditar && <td style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
              {!m.congelada && <button onClick={() => {
                const v = prompt("Valor protocolado (R$):"); if (v) agir(() =>
                  api(`/api/medicoes/${m.id}/valor`, { method: "PUT", body: JSON.stringify({ campo: "protocolado", valor: v }) }));
              }}>valor</button>}
              <button onClick={() => {
                const v = prompt("Valor atestado (R$):"); if (v) agir(() =>
                  api(`/api/medicoes/${m.id}/valor`, { method: "PUT", body: JSON.stringify({ campo: "atestado", valor: v }) }));
              }}>atestar</button>
              {m.estado !== "recebida" && m.estado !== "cancelada" && m.estado !== "desistida" &&
                <button onClick={() => {
                  const d = prompt("Data do protocolo (AAAA-MM-DD):"); if (!d) return;
                  const of = prompt("Nº do ofício (opcional):") || null;
                  agir(() => api(`/api/medicoes/${m.id}/protocolo`, { method: "POST",
                    body: JSON.stringify({ data: d, numero_oficio: of }) }));
                }}>protocolar</button>}
              {(PROXIMOS[m.estado] ?? []).map(e => <button key={e} onClick={() =>
                agir(() => api(`/api/medicoes/${m.id}/estado`, { method: "POST", body: JSON.stringify({ estado: e }) }))
              }>{e.replace("_", " ")}</button>)}
            </td>}
          </tr>))}
        </tbody>
      </table>
      {podeEditar && <form style={{ marginTop: 12, display: "flex", gap: 8 }} onSubmit={ev => {
        ev.preventDefault();
        agir(() => api(`/api/contratos/${contratoId}/medicoes`, { method: "POST", body: JSON.stringify({
          numero: Number(novo.numero), tipo: novo.tipo, competencia: novo.competencia }) })
        ).then(() => setNovo({ numero: "", tipo: "execucao", competencia: "" }));
      }}>
        <input required placeholder="nº" size={3} value={novo.numero}
               onChange={e => setNovo({ ...novo, numero: e.target.value })} />
        <select value={novo.tipo} onChange={e => setNovo({ ...novo, tipo: e.target.value })}>
          <option value="execucao">execução</option><option value="projeto">projeto</option>
          <option value="reajuste">reajuste</option>
        </select>
        <input required placeholder="AAAA-MM" pattern="\d{4}-\d{2}" size={8} value={novo.competencia}
               onChange={e => setNovo({ ...novo, competencia: e.target.value })} />
        <button>Nova medição</button>
      </form>}
      <p><a href={`/api/contratos/${contratoId}/medicoes.csv`}>Exportar CSV</a></p>
    </div>
  );
}
```

- [ ] **Step 2: Implementar `ContratoPagina.tsx`**

```tsx
// frontend/src/ContratoPagina.tsx
import { useEffect, useState } from "react";
import { api } from "./api";
import Medicoes, { brl } from "./Medicoes";
import Cronograma from "./Cronograma";
import type { Usuario } from "./Login";

type Detalhe = { id: number; orgao: string; numero_instrumento: string; objeto: string;
                 estado: string; valor_vigente_centavos: number };

export default function ContratoPagina({ contratoId, usuario, aoVoltar }:
    { contratoId: number; usuario: Usuario; aoVoltar: () => void }) {
  const [c, setC] = useState<Detalhe | null>(null);
  const [aba, setAba] = useState<"medicoes" | "cronograma">("medicoes");
  const podeEditar = usuario.perfil === "engenharia" || usuario.perfil === "admin";

  useEffect(() => { api<Detalhe>(`/api/contratos/${contratoId}`).then(setC); }, [contratoId]);
  if (!c) return null;

  return (
    <div>
      <button onClick={aoVoltar}>← Contratos</button>
      <h2>{c.numero_instrumento} — {c.orgao}</h2>
      <p>{c.objeto} · estado: {c.estado} · vigente: {brl(c.valor_vigente_centavos)}</p>
      <nav style={{ display: "flex", gap: 8, borderBottom: "1px solid #ddd", marginBottom: 12 }}>
        <button onClick={() => setAba("medicoes")} disabled={aba === "medicoes"}>Medições</button>
        <button onClick={() => setAba("cronograma")} disabled={aba === "cronograma"}>Cronograma</button>
      </nav>
      {aba === "medicoes" && <Medicoes contratoId={contratoId} podeEditar={podeEditar} />}
      {aba === "cronograma" && <Cronograma contratoId={contratoId} podeEditar={podeEditar} />}
    </div>
  );
}
```

(Nota: `Cronograma.tsx` nasce na Task 8; para compilar esta task antes dela, criar na Task 7 um stub mínimo `export default function Cronograma(_: {contratoId: number; podeEditar: boolean}) { return <p>Cronograma na próxima task.</p>; }` — a Task 8 o substitui.)

- [ ] **Step 3: Ligar no App e na lista** — em `Contratos.tsx`, adicionar prop opcional `aoAbrir?: (id: number) => void` e um botão "abrir" por linha chamando-a; em `App.tsx`:

```tsx
// trechos a acrescentar em App.tsx
const [contratoAberto, setContratoAberto] = useState<number | null>(null);
// no <main>, substituindo a linha da tela contratos:
{tela === "contratos" && contratoAberto === null &&
  <Contratos usuario={usuario} aoAbrir={setContratoAberto} />}
{tela === "contratos" && contratoAberto !== null &&
  <ContratoPagina contratoId={contratoAberto} usuario={usuario}
                  aoVoltar={() => setContratoAberto(null)} />}
```

- [ ] **Step 4: Verificar** — `cd frontend; npx tsc --noEmit` limpo; `npm run build` ok; subir backend com frontend e conferir manualmente criar medição → valor → protocolo → estados.

- [ ] **Step 5: Commit** — `feat: pagina do contrato com aba de medicoes`

---

### Task 8: Frontend — cronograma + curva previsto×realizado (SVG)

**Files:**
- Create: `frontend/src/Cronograma.tsx` (substitui o stub da Task 7)

**Interfaces:**
- Consumes: `GET/POST /api/contratos/{id}/cronograma` (Task 3), `GET /api/contratos/{id}/curva` (Task 6), `brl` (Task 7).
- Produces: `Cronograma({ contratoId, podeEditar })` — tabela editável de competências (textarea "AAAA-MM;valor" uma por linha → nova versão) + gráfico SVG de barras (previsto cinza atrás, medido execução sólido na frente, reajuste hachurado, ponto "!" quando `atestado_pendente`) + saldo com fórmula visível.

- [ ] **Step 1: Implementar**

```tsx
// frontend/src/Cronograma.tsx
import { useEffect, useState } from "react";
import { api, ApiErro } from "./api";
import { brl } from "./Medicoes";

type Item = { competencia: string; valor_previsto_centavos: number };
type Versao = { numero: number; criado_em: string; itens: Item[] } | null;
type Ponto = { competencia: string; previsto_centavos: number; medido_execucao_centavos: number;
               medido_reajuste_centavos: number; medido_projeto_centavos: number; atestado_pendente: boolean };
type Curva = { curva: Ponto[]; saldo: { vigente_centavos: number; atestado_execucao_centavos: number;
               saldo_centavos: number; formula: string } };

export default function Cronograma({ contratoId, podeEditar }:
    { contratoId: number; podeEditar: boolean }) {
  const [versao, setVersao] = useState<Versao>(null);
  const [dados, setDados] = useState<Curva | null>(null);
  const [texto, setTexto] = useState("");
  const [erro, setErro] = useState("");

  const carregar = () => Promise.all([
    api<Versao>(`/api/contratos/${contratoId}/cronograma`).then(setVersao),
    api<Curva>(`/api/contratos/${contratoId}/curva`).then(setDados),
  ]);
  useEffect(() => { carregar().catch(e => setErro(String(e))); }, [contratoId]);

  const salvar = async () => {
    setErro("");
    const itens = texto.trim().split("\n").filter(Boolean).map(l => {
      const [competencia, valor] = l.split(";").map(s => s.trim());
      return { competencia, valor };
    });
    try { await api(`/api/contratos/${contratoId}/cronograma`,
                    { method: "POST", body: JSON.stringify({ itens }) });
          setTexto(""); await carregar(); }
    catch (e) { setErro(e instanceof ApiErro ? e.message : String(e)); }
  };

  const pontos = dados?.curva ?? [];
  const teto = Math.max(1, ...pontos.map(p =>
    Math.max(p.previsto_centavos, p.medido_execucao_centavos + p.medido_reajuste_centavos + p.medido_projeto_centavos)));
  const W = Math.max(320, pontos.length * 56), H = 180, base = H - 24;

  return (
    <div>
      {erro && <p style={{ color: "crimson" }}>{erro}</p>}
      {dados && <p><strong>{brl(dados.saldo.saldo_centavos)}</strong> de saldo
        · <small>{dados.saldo.formula} = {brl(dados.saldo.vigente_centavos)} − {brl(dados.saldo.atestado_execucao_centavos)}</small></p>}
      {pontos.length > 0 && (
        <svg width={W} height={H} role="img" aria-label="Previsto × realizado por competência">
          {pontos.map((p, i) => {
            const x = i * 56 + 8;
            const hPrev = Math.round((p.previsto_centavos / teto) * (base - 20));
            const medido = p.medido_execucao_centavos + p.medido_reajuste_centavos + p.medido_projeto_centavos;
            const hMed = Math.round((medido / teto) * (base - 20));
            return (<g key={p.competencia}>
              <rect x={x} y={base - hPrev} width={20} height={hPrev} fill="#ccc" />
              <rect x={x + 22} y={base - hMed} width={20} height={hMed} fill="#2a6" />
              {p.atestado_pendente && <text x={x + 26} y={base - hMed - 4} fontSize={12}>!</text>}
              <text x={x} y={H - 8} fontSize={10}>{p.competencia.slice(2)}</text>
            </g>);
          })}
        </svg>)}
      <p><small>cinza = previsto (cronograma vigente, passado congelado) · verde = medido
        (atestado; protocolado marcado com “!” enquanto não atestado) · reajuste somado como série própria no CSV/API</small></p>
      <h3>Cronograma vigente {versao ? `(versão ${versao.numero})` : "(nenhum)"}</h3>
      <ul>{versao?.itens.map(i =>
        <li key={i.competencia}>{i.competencia}: {brl(i.valor_previsto_centavos)}</li>)}</ul>
      {podeEditar && <div>
        <p>Nova versão — uma linha por competência, formato <code>AAAA-MM;1.000,00</code>:</p>
        <textarea rows={6} cols={30} value={texto} onChange={e => setTexto(e.target.value)} />
        <br /><button onClick={salvar} disabled={!texto.trim()}>Publicar nova versão</button>
      </div>}
    </div>
  );
}
```

- [ ] **Step 2: Verificar** — `npx tsc --noEmit`; `npm run build`; manual: publicar versão, ver curva e saldo.

- [ ] **Step 3: Commit** — `feat: cronograma versionado e curva previsto x realizado no frontend`

---

### Task 9: Frontend — fila de sugestões (home da Engenharia)

**Files:**
- Create: `frontend/src/Sugestoes.tsx`

**Interfaces:**
- Consumes: `GET /api/sugestoes`, `POST /api/sugestoes/{id}/decisao`, `POST /api/sugestoes/importar` (Task 4); `brl` (Task 7).
- Produces: `Sugestoes({ podeEditar })` — lista de pendentes com evidência e 3 botões (aceitar / corrigir / descartar; corrigir abre `prompt` por campo pré-preenchido) + textarea de importação manual CSV com relatório de erros por linha. Consumido pelo App na Task 10.

- [ ] **Step 1: Implementar**

```tsx
// frontend/src/Sugestoes.tsx
import { useEffect, useState } from "react";
import { api, ApiErro } from "./api";
import { brl } from "./Medicoes";

type Sugestao = { id: number; tipo: string; payload: any; evidencia: string | null; criado_em: string };
type ResultadoImportacao = { criadas: number; erros: { linha: number; erro: string }[] };

export default function Sugestoes({ podeEditar }: { podeEditar: boolean }) {
  const [itens, setItens] = useState<Sugestao[]>([]);
  const [csv, setCsv] = useState("");
  const [resultado, setResultado] = useState<ResultadoImportacao | null>(null);
  const [erro, setErro] = useState("");

  const carregar = () => api<Sugestao[]>("/api/sugestoes").then(setItens);
  useEffect(() => { carregar().catch(e => setErro(String(e))); }, []);

  const decidir = async (s: Sugestao, decisao: string, payload_corrigido: any = null) => {
    setErro("");
    try { await api(`/api/sugestoes/${s.id}/decisao`,
                    { method: "POST", body: JSON.stringify({ decisao, payload_corrigido }) });
          await carregar(); }
    catch (e) { setErro(e instanceof ApiErro ? e.message : String(e)); }
  };

  const corrigir = (s: Sugestao) => {
    const p = { ...s.payload };
    const numero = prompt("Número da medição:", String(p.numero)); if (numero === null) return;
    const competencia = prompt("Competência (AAAA-MM):", p.competencia); if (competencia === null) return;
    decidir(s, "corrigida", { ...p, numero: Number(numero), competencia });
  };

  return (
    <div>
      <h2>Fila de sugestões</h2>
      {erro && <p style={{ color: "crimson" }}>{erro}</p>}
      {itens.length === 0 && <p>Nenhuma sugestão pendente.</p>}
      <ul>{itens.map(s => (
        <li key={s.id} style={{ marginBottom: 8 }}>
          <strong>{s.tipo}</strong> — contrato {s.payload.contrato_id}, {s.payload.numero}ª {s.payload.tipo}
          {" "}({s.payload.competencia}) {brl(s.payload.valor_protocolado_centavos)}
          {s.evidencia && <em> · {s.evidencia}</em>}
          {podeEditar && <span style={{ marginLeft: 8, display: "inline-flex", gap: 4 }}>
            <button onClick={() => decidir(s, "aceita")}>aceitar</button>
            <button onClick={() => corrigir(s)}>corrigir</button>
            <button onClick={() => decidir(s, "descartada")}>descartar</button>
          </span>}
        </li>))}
      </ul>
      {podeEditar && <details>
        <summary>Importar medições (CSV)</summary>
        <p>Uma linha por medição: <code>contrato_id;numero;tipo;AAAA-MM;valor</code></p>
        <textarea rows={5} cols={50} value={csv} onChange={e => setCsv(e.target.value)} />
        <br /><button disabled={!csv.trim()} onClick={async () => {
          setResultado(null);
          const r = await api<ResultadoImportacao>("/api/sugestoes/importar",
            { method: "POST", body: JSON.stringify({ texto_csv: csv }) });
          setResultado(r); setCsv(""); await carregar();
        }}>Importar para a fila</button>
        {resultado && <p>{resultado.criadas} sugestão(ões) criada(s).
          {resultado.erros.map(e => <span key={e.linha}><br />linha {e.linha}: {e.erro}</span>)}</p>}
      </details>}
    </div>
  );
}
```

- [ ] **Step 2: Verificar** — `npx tsc --noEmit`; `npm run build`.

- [ ] **Step 3: Commit** — `feat: fila de sugestoes com importacao manual no frontend`

---

### Task 10: Frontend — painel geral, alertas e home por perfil

**Files:**
- Create: `frontend/src/PainelGeral.tsx`
- Modify: `frontend/src/App.tsx`

**Interfaces:**
- Consumes: `GET /api/paineis/consolidado`, `GET /api/paineis/alertas`, `/api/paineis/consolidado.csv` (Task 6); `Sugestoes` (Task 9); `brl` (Task 7).
- Produces: `PainelGeral({ aoAbrirContrato })` — alertas no topo, carteira (tabela com saldo por contrato, clique abre a página do contrato), consolidado mensal (barras SVG como na Task 8), link CSV. `App.tsx`: telas `"painel" | "sugestoes" | "contratos" | "admin"`; home = `painel` para perfil diretoria, `sugestoes` para engenharia/admin (spec §7 telas 1–2).

- [ ] **Step 1: Implementar `PainelGeral.tsx`**

```tsx
// frontend/src/PainelGeral.tsx
import { useEffect, useState } from "react";
import { api } from "./api";
import { brl } from "./Medicoes";

type Linha = { id: number; orgao: string; numero_instrumento: string; objeto: string;
               vigente_centavos: number; atestado_execucao_centavos: number; saldo_centavos: number };
type Mes = { competencia: string; previsto_centavos: number; medido_centavos: number };
type Consolidado = { carteira: Linha[]; por_mes: Mes[] };
type Alerta = { tipo: string; contrato_id: number; mensagem: string };

export default function PainelGeral({ aoAbrirContrato }: { aoAbrirContrato: (id: number) => void }) {
  const [dados, setDados] = useState<Consolidado | null>(null);
  const [alertas, setAlertas] = useState<Alerta[]>([]);

  useEffect(() => {
    api<Consolidado>("/api/paineis/consolidado").then(setDados);
    api<Alerta[]>("/api/paineis/alertas").then(setAlertas);
  }, []);
  if (!dados) return null;

  const teto = Math.max(1, ...dados.por_mes.map(m => Math.max(m.previsto_centavos, m.medido_centavos)));
  const base = 140;

  return (
    <div>
      {alertas.length > 0 && <div style={{ background: "#fff3cd", padding: 8, marginBottom: 12 }}>
        <strong>Alertas</strong>
        <ul style={{ margin: 4 }}>{alertas.map((a, i) =>
          <li key={i}><button style={{ all: "unset", cursor: "pointer", textDecoration: "underline" }}
            onClick={() => aoAbrirContrato(a.contrato_id)}>{a.mensagem}</button></li>)}</ul>
      </div>}
      <h2>Consolidado mensal</h2>
      <svg width={Math.max(320, dados.por_mes.length * 56)} height={170}
           role="img" aria-label="Consolidado previsto × medido">
        {dados.por_mes.map((m, i) => {
          const x = i * 56 + 8;
          const hP = Math.round((m.previsto_centavos / teto) * 120);
          const hM = Math.round((m.medido_centavos / teto) * 120);
          return (<g key={m.competencia}>
            <rect x={x} y={base - hP} width={20} height={hP} fill="#ccc" />
            <rect x={x + 22} y={base - hM} width={20} height={hM} fill="#26a" />
            <text x={x} y={162} fontSize={10}>{m.competencia.slice(2)}</text>
          </g>);
        })}
      </svg>
      <h2>Carteira</h2>
      <table cellPadding={6} style={{ borderCollapse: "collapse", width: "100%" }}>
        <thead><tr style={{ textAlign: "left", borderBottom: "2px solid #333" }}>
          <th>Contrato</th><th>Órgão</th><th>Vigente</th><th>Atestado (exec.)</th><th>Saldo</th></tr></thead>
        <tbody>{dados.carteira.map(l => (
          <tr key={l.id} style={{ borderBottom: "1px solid #ddd", cursor: "pointer" }}
              onClick={() => aoAbrirContrato(l.id)}>
            <td>{l.numero_instrumento}</td><td>{l.orgao}</td>
            <td>{brl(l.vigente_centavos)}</td><td>{brl(l.atestado_execucao_centavos)}</td>
            <td><strong>{brl(l.saldo_centavos)}</strong></td>
          </tr>))}</tbody>
      </table>
      <p><a href="/api/paineis/consolidado.csv">Exportar CSV</a></p>
    </div>
  );
}
```

- [ ] **Step 2: App.tsx** — trocar o tipo da tela e a home por perfil:

```tsx
// trechos de App.tsx (substituem os equivalentes da fase 1 + Task 7)
const [tela, setTela] = useState<"painel" | "sugestoes" | "contratos" | "admin">("painel");
// ao carregar o usuario (no .then de /api/auth/eu e no aoEntrar do Login):
//   setTela(eu.perfil === "diretoria" ? "painel" : "sugestoes")
// header:
<button onClick={() => setTela("painel")}>Painel</button>
<button onClick={() => setTela("sugestoes")}>Sugestões</button>
<button onClick={() => { setTela("contratos"); setContratoAberto(null); }}>Contratos</button>
// main:
{tela === "painel" && <PainelGeral aoAbrirContrato={id => { setTela("contratos"); setContratoAberto(id); }} />}
{tela === "sugestoes" && <Sugestoes podeEditar={usuario.perfil !== "diretoria"} />}
```

- [ ] **Step 3: Verificar** — `npx tsc --noEmit`; `npm run build`; manual: login engenharia cai em Sugestões; alerta clicável abre o contrato.

- [ ] **Step 4: Commit** — `feat: painel geral com alertas, carteira e home por perfil`

---

### Task 11: Varredura final da fase

**Files:**
- Modify: `README.md` (seção "Rodar em desenvolvimento" ganha 3 linhas descrevendo as telas novas; marcar fase 2 entregue na lista de fases)

- [ ] **Step 1: Suíte completa** — `cd backend; .venv\Scripts\python -m pytest -q` → tudo verde (fase 1 intacta + fase 2).
- [ ] **Step 2: Frontend** — `cd frontend; npx tsc --noEmit; npm run build` limpos.
- [ ] **Step 3: Fumaça manual** — subir o app real, percorrer: importar CSV → aceitar sugestão → valor → protocolo → atestar → curva/painel/alertas → 2 exports CSV abrem no Excel.
- [ ] **Step 4: Atualizar README e commitar** — `docs: fase 2 entregue (medicoes, cronograma, paineis)`

---

## Self-Review (executado na escrita do plano)

1. **Cobertura da spec (§12 fase 2)**: 4 estados ✓ (T1/T2, com exceções e congelamento); fila de sugestões por importação manual ✓ (T4/T9); previsto×realizado ✓ (T3/T5/T8); painéis ✓ (T5/T6/T10, §7 telas 1–3); alertas de calendário ✓ (T5/T6/T10); export CSV ✓ (T6, links em T7/T10); origem por dado ✓ (`manual`/`aceito` nesta fase); reajuste como série própria ✓ (§6, T5/T8); saldo com fórmula visível ✓ (T5/T8). Fora de escopo desta fase (fases 5–6): mover `nf_emitida`/`recebida` por detecção — aqui manual, documentado em T1.
2. **Placeholders**: nenhum TBD; todo step tem código/comando. Único stub deliberado (Cronograma na T7) tem conteúdo exato e substituição na T8.
3. **Consistência de tipos**: `medicoes.criar/definir_valor/registrar_protocolo/mudar_estado` (T1) usados idênticos em T2/T4; `previsto_efetivo` (T3) em T5; `curva/saldo/consolidado/alertas` (T5) em T6; rotas de T2/T3/T4/T6 idênticas nos fetches de T7–T10; `brl` exportado em T7 e importado em T8/T9/T10. ✓

## Workflow de Execução Multi-Modelo (mantido da fase 0/1)

- **Orquestrador/triagem:** sessão principal. **Implementadores:** 1 subagente Opus novo por task. **Revisor de conformidade:** subagente Opus por task (confere resultado × task × spec). Achados adversariais: verificar contra o código antes de implementar qualquer crítica.
