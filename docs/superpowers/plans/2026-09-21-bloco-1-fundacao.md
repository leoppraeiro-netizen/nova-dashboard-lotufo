# Bloco 1 (Fundação): cadastro versionado e envio de e-mail por usuário. Plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** dar ao sistema a sua fonte de verdade de contratos (arquivos YAML versionados, carregados por comando, sem tela) com as 22 obras do QDOP, e a capacidade de cada pessoa enviar e-mail com anexos pela própria conta Microsoft, com registro imutável do envio.

**Architecture:** dois módulos novos e independentes no padrão plano do backend (`app/<modulo>.py`). `cadastro_arquivos` lê e valida `cadastro/*.yaml` e devolve uma estrutura normalizada; `cadastro_aplicar` a grava no SQLite numa única transação, idempotente, com ensaio, auditoria e recusa de alteração de instrumento já aplicado. `correio` envia pelo Microsoft Graph com token delegado por usuário (rascunho, anexos por sessão de upload, envio) e grava o envio. Nada do que existe muda de comportamento, exceto as rotas de escrita de cadastro, que passam a responder 409 quando a produção declara o cadastro versionado.

**Tech Stack:** Python 3.12, FastAPI, SQLite (migrações SQL idempotentes em `backend/migrations`), pytest, PyYAML (dependência nova), `urllib` da biblioteca padrão para o Graph (como `app/graph.py`), React 18 + Vite + vitest no frontend.

**Spec:** `docs/superpowers/specs/2026-09-21-reestruturacao-design.md` (seções 1, 5.1, 7.2 a 7.4 no que é cadastro, 8, 12, 14.1, 17). Decisões e evidências: `docs/decisoes-reestruturacao-2026-09-16.md`.

**Status:** APROVADO pelo Leonardo em 2026-09-21, incluindo as decisões 1, 2 e 3 da seção "Decisões deste plano em relação à spec". **Modo de execução escolhido: nesta sessão (superpowers:executing-plans)**, sem subagente por tarefa. **Andamento em 2026-09-21 (branch `bloco1-fundacao`):** Tasks 1 a 6 e 8 a 10 feitas e commitadas; Task 11 feita (suíte verde, gate Sol com 3 correções, documentos), faltando só o pedido de merge. **Task 7 feita**: o Leonardo delegou a conferência ("resolva tudo você"); os instrumentos foram lidos no SharePoint e os destinatários nos e-mails de protocolo. `cadastro/` commitado (10 órgãos, 9 entidades, 22 contratos, 35 instrumentos), validado e ensaiado sobre cópia da produção. O que ficou em aberto está em linhas `# NOTA` no topo de cada YAML e em `docs/backlog.md`. **Mergeado em `master` (fb7d07e) e em produção (checkout pinado em 1902aa0) em 2026-09-21.** `cadastro aplicar --ensaio` rodou limpo em produção (0 contratos criados, 22 alterados, 21 instrumentos criados, 14 iguais). **`cadastro aplicar` REAL rodado em produção em 2026-09-21 16:59, com OK do Leonardo** (admin: o e-mail do Leonardo; backup `dashboard-PRE-CADASTRO-20260921-165811.db`; mesmos números do ensaio; reaplicação em ensaio deu tudo igual). **Bloco 1 concluído.** Desvios do texto do plano: botões usam `btn`/`btn--primario` (as classes `botao*` não existem), token por usuário fica em `segredos\usuarios` (não `segredos\graph\usuarios`), `MAX_TOTAL` é 25 MiB, o arquivo do contrato é o slug ASCII do `nome_curto`.

## Global Constraints

- Banco: `backend/dados/dashboard.db` é o caminho padrão de dev E de produção nesta máquina. Testes usam `tmp_path` com `DASH_DB_PATH`. **Nunca semear nem apagar o banco padrão nem o de produção (`C:\DashboardLotufo\dados\dashboard.db`).** Leitura do banco de produção só com `?mode=ro`. O ensaio da Task 7 roda sobre uma CÓPIA no scratchpad.
- Sem custo de API: nada de serviço pago por uso, OCR ou LLM. Microsoft 365 já é da empresa.
- Dinheiro em centavos inteiros (`app/dinheiro.py`), histórico não sobrescrito, sem exclusão física de registro financeiro, auditoria append-only (`auditoria.registrar` dentro de `db.mutacao`).
- Toda escrita de negócio acontece dentro de `with db.mutacao(conn):` e a linha de auditoria entra no mesmo commit.
- Migrações idempotentes: `CREATE TABLE IF NOT EXISTS`, `CREATE INDEX IF NOT EXISTS`, `INSERT OR IGNORE`; `ALTER TABLE ... ADD COLUMN` no começo de linha (o runner pula o que já existe).
- Textos de interface, mensagens de erro e commits em português. Commit no padrão `tipo: descricao` (feat/fix/docs/test/chore), sem acento no assunto, terminando com a linha `Co-Authored-By` do modelo em uso.
- Testes: `cd backend && .venv\Scripts\python -m pytest`. Teste novo em `backend/tests/test_<modulo>.py`, no tamanho dos vizinhos, um teste focado por comportamento. CNPJ em documento é sempre placeholder inválido (`00000000000100` é o da Lotufo, já semeado; `00000000000500` é uma consorciada); o CNPJ válido fictício fica só nas fixtures e em `cadastro-exemplo/`.
- Branch `bloco1-fundacao`. Merge em `master` só com OK explícito do Leonardo. Um gate Sol sobre o diff inteiro ao final (toca autenticação e arquivo externo).
- Subagentes de implementação e revisão em Opus; nunca Sonnet ou Haiku.

## Decisões deste plano em relação à spec

1. **A nova máquina de estados da medição sai do bloco 1 e vai para o bloco 2** (com o espelho, que é quem a usa), e o remapeamento do legado vai para o bloco 3 (com a nota, porque `sincronizacao_rm` e `paineis` dependem dos estados atuais). Trocar estados sem os fluxos novos quebraria RM e painéis em produção sem entregar nada. A spec §17 listava isso no bloco 1; o resto do bloco 1 não depende dela.
2. **"Em encerramento" é a coluna `contratos.encerramento_iniciado_em`**, não um valor novo do CHECK de `estado`. Evita reconstruir a tabela `contratos`, que todo o banco referencia. O estado exposto é derivado: `estado='ativo'` com a data preenchida.
3. **Aditivos de valor e de prazo continuam na tabela `aditivos`** (ganham `chave_cadastro` e `forma`), porque `contratos.vigente` e os testes de dinheiro já dependem dela. Os demais instrumentos (apostilamento de reajuste, paralisação, reinício, marco de encerramento, endosso de garantia) vão para a tabela nova `instrumentos`.
4. **`geral.yaml`, regra do espelho e modelos Word ficam para o bloco 2**, que é quem os consome.
5. **As telas de cadastro não são redesenhadas aqui**: as rotas de escrita passam a responder 409 em produção; a tela mostra o erro. O redesenho vem nos blocos de tela.
6. **Trocar a própria senha e sessão de 30 dias (spec §1)** não estão em nenhum bloco da §17; entram no bloco 6 (tela inicial), junto com a tela Minha conta criada aqui.
7. **O deploy não roda `cadastro aplicar` sozinho neste bloco**: é um passo manual documentado no runbook, até o comando ter rodado algumas vezes em produção.

## Estrutura de arquivos

| Arquivo | Responsabilidade |
|---|---|
| `cadastro/orgaos.yaml`, `cadastro/entidades.yaml`, `cadastro/contratos/*.yaml` | a fonte de verdade (Task 7) |
| `backend/app/cadastro_arquivos.py` | ler, validar e normalizar o cadastro; não toca banco |
| `backend/app/cadastro_aplicar.py` | gravar a estrutura normalizada no banco; não lê arquivo |
| `backend/migrations/018_cadastro_versionado.sql` | tabelas e colunas do cadastro |
| `backend/migrations/019_envios.sql` | registro de e-mails enviados |
| `backend/app/correio.py` | token por usuário, envio pelo Graph, simulador, registro |
| `backend/app/api_correio.py` | conectar conta, status, e-mail de teste |
| `backend/app/cli.py` | subcomandos `cadastro validar` e `cadastro aplicar` |
| `backend/app/permissoes.py` | guarda `exigir_cadastro_editavel` |
| `frontend/src/MinhaConta.tsx` | tela "Minha conta" |

---

### Task 1: Ler, validar e normalizar o cadastro

**Files:**
- Modify: `backend/pyproject.toml` (dependência), `backend/requirements.lock`
- Create: `backend/app/cadastro_arquivos.py`
- Test: `backend/tests/test_cadastro_arquivos.py`

**Interfaces:**
- Consumes: `dinheiro.parse_brl(texto) -> int`, `entidades.cnpj_valido(cnpj14) -> bool`.
- Produces: `cadastro_arquivos.preparar(raiz: Path) -> dict` e `cadastro_arquivos.CadastroInvalido` (atributo `erros: list[str]`). Estrutura devolvida:

```python
{
  "orgaos":    [{"chave", "nome", "familia", "regras": dict}],
  "entidades": [{"chave", "nome", "cnpj" (14 dígitos), "papel", "coligada_rm": int|None, "sigla_oficio": str|None}],
  "contratos": [{
      "nome_curto", "numero_instrumento", "orgao" (chave), "entidade" (chave), "objeto",
      "municipio", "lei", "cno", "art", "numero_processo", "centro_custo_rm",
      "valor_original_centavos": int, "percentual_direito_bp": int,
      "execucao_inicio", "execucao_fim", "vigencia_inicio", "vigencia_fim"  (ISO ou None),
      "status", "status_desde" (ISO ou None), "sem_reajuste": bool,
      "datas_base": [{"mes": "AAAA-MM", "indice": str}],
      "fiscais": [{"nome", "email", "desde": ISO}],
      "destinatarios_extras": [str],
      "instrumentos": [{"chave", "tipo", "data": ISO, "numero", "objeto", "corrige",
                        "delta_valor_centavos": int, "nova_execucao_fim", "nova_vigencia_fim",
                        "dados": dict, "pdf"}]}],
  "avisos": [str],
}
```

- [ ] **Step 1: Acrescentar a dependência**

Em `backend/pyproject.toml`, dentro de `dependencies`, depois do bloco do `pypdf`:

```toml
    # Leitura do cadastro versionado (cadastro/*.yaml, spec 2026-09-21 §8). So' safe_load:
    # o cadastro e' dado, nunca objeto Python serializado.
    "PyYAML>=6.0,<7.0",
```

Rodar:

```bash
cd backend && .venv/Scripts/python -m pip install "PyYAML>=6.0,<7.0" && .venv/Scripts/python -m pip freeze > requirements.lock
```

Conferir com `git diff requirements.lock` que a única linha nova é `PyYAML==6.x`.

- [ ] **Step 2: Escrever os testes que falham**

`backend/tests/test_cadastro_arquivos.py`:

```python
import pytest
import yaml

from app import cadastro_arquivos as ca

ORGAO = {"chave": "sinfra-suef1", "nome": "SINFRA - SUEF I", "familia": "sinfra",
         "protocolo_para": ["protocolo@exemplo.com.br"], "folga_vigencia_dias": 90,
         "vigencia_automatica": True, "documentos_medicao": ["federal", "fgts"]}
ENTIDADE = {"chave": "lotufo", "nome": "Lotufo Engenharia e Construções Ltda",
            "cnpj": "00.000.000/0001-00", "papel": "lotufo", "coligada_rm": 1, "sigla_oficio": "LT"}
CONTRATO = {"nome_curto": "MT-402", "numero_instrumento": "019/2024/00/00-SINFRA",
            "orgao": "sinfra-suef1", "entidade": "lotufo", "objeto": "Remanescente da MT-402",
            "lei": "14.133", "valor_original": "15.127.200,00", "percentual_lotufo": "100",
            "execucao_fim": "2026-08-28", "vigencia_fim": "2026-11-22", "status": "ativo",
            "datas_base": [{"mes": "2023-04", "indice": "setorial FGV/DNIT"}],
            "instrumentos": [{"chave": "carga-legado", "tipo": "aditivo_valor", "data": "2026-08-04",
                              "delta_valor": "3.236.067,18", "objeto": "Carga inicial"}]}


def _escrever(raiz, orgaos=None, entidades=None, contratos=None):
    (raiz / "contratos").mkdir(parents=True, exist_ok=True)
    (raiz / "orgaos.yaml").write_text(yaml.safe_dump(orgaos or [ORGAO], allow_unicode=True), "utf-8")
    (raiz / "entidades.yaml").write_text(yaml.safe_dump(entidades or [ENTIDADE], allow_unicode=True), "utf-8")
    for c in (contratos if contratos is not None else [CONTRATO]):
        nome = c.get("_arquivo") or c["nome_curto"].lower()
        corpo = {k: v for k, v in c.items() if k != "_arquivo"}
        (raiz / "contratos" / f"{nome}.yaml").write_text(yaml.safe_dump(corpo, allow_unicode=True), "utf-8")
    return raiz


def _erros(raiz):
    with pytest.raises(ca.CadastroInvalido) as e:
        ca.preparar(raiz)
    return e.value.erros


def test_cadastro_minimo_normaliza(tmp_path):
    cad = ca.preparar(_escrever(tmp_path))
    c = cad["contratos"][0]
    assert c["valor_original_centavos"] == 1512720000
    assert c["percentual_direito_bp"] == 10000
    assert c["execucao_fim"] == "2026-08-28"
    assert c["instrumentos"][0]["delta_valor_centavos"] == 323606718
    assert cad["entidades"][0]["cnpj"] == "00000000000100"
    assert cad["orgaos"][0]["regras"]["folga_vigencia_dias"] == 90
    assert cad["avisos"] == []


def test_cnpj_com_dv_errado_e_erro(tmp_path):
    erros = _erros(_escrever(tmp_path, entidades=[{**ENTIDADE, "cnpj": "00.000.000/0001-00"}]))
    assert any("cnpj" in e.lower() for e in erros)


def test_orgao_inexistente_e_erro(tmp_path):
    erros = _erros(_escrever(tmp_path, contratos=[{**CONTRATO, "orgao": "nao-existe"}]))
    assert any("nao-existe" in e for e in erros)


def test_nome_do_arquivo_tem_que_bater_com_nome_curto(tmp_path):
    erros = _erros(_escrever(tmp_path, contratos=[{**CONTRATO, "_arquivo": "outra-obra"}]))
    assert any("nome_curto" in e for e in erros)


def test_chave_de_instrumento_repetida_e_erro(tmp_path):
    dois = CONTRATO["instrumentos"] * 2
    erros = _erros(_escrever(tmp_path, contratos=[{**CONTRATO, "instrumentos": dois}]))
    assert any("carga-legado" in e for e in erros)


def test_valor_em_formato_americano_e_recusado(tmp_path):
    erros = _erros(_escrever(tmp_path, contratos=[{**CONTRATO, "valor_original": "15127200.00"}]))
    assert any("valor_original" in e for e in erros)


def test_vigencia_antes_da_execucao_e_aviso_nao_erro(tmp_path):
    cad = ca.preparar(_escrever(tmp_path, contratos=[{**CONTRATO, "vigencia_fim": "2026-08-01"}]))
    assert any("vigência" in a.lower() for a in cad["avisos"])


def test_em_encerramento_exige_status_desde(tmp_path):
    erros = _erros(_escrever(tmp_path, contratos=[{**CONTRATO, "status": "em_encerramento"}]))
    assert any("status_desde" in e for e in erros)
```

- [ ] **Step 3: Rodar e ver falhar**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_cadastro_arquivos.py -q`
Expected: FAIL na coleta com `ImportError: cannot import name 'cadastro_arquivos'`.

- [ ] **Step 4: Implementar**

`backend/app/cadastro_arquivos.py`:

```python
"""Leitura, validacao e normalizacao do cadastro versionado (spec 2026-09-21 §8).

O cadastro e' editado pelo Leonardo com o Claude, em YAML, no repositorio. Este modulo
NAO toca o banco: devolve a estrutura que `cadastro_aplicar` grava. Todos os erros sao
acumulados (um cadastro com tres problemas mostra os tres) e levantados de uma vez.
"""
import datetime
import re
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path

import yaml

from app import dinheiro, entidades

FAMILIAS = ("mtpar", "sinfra", "ses", "prefeitura")
LEIS = ("8.666", "14.133", "13.303")
STATUS = ("ativo", "suspenso", "em_encerramento", "encerrado")
PAPEIS = ("lotufo", "consorcio", "consorciada")
# tipo do cadastro -> tipo da tabela `aditivos` (o que altera valor e prazo)
TIPOS_ADITIVO = {"aditivo_valor": "valor", "aditivo_prazo": "prazo", "aditivo_misto": "misto",
                 "apostilamento_prazo": "prazo"}
TIPOS_OUTROS = ("apostilamento_reajuste", "paralisacao", "reinicio", "marco_encerramento",
                "endosso_garantia")
_MES = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
_CHAVE = re.compile(r"^[a-z0-9][a-z0-9-]{1,40}$")
_CAMPOS_INSTRUMENTO = {"chave", "tipo", "data", "numero", "objeto", "corrige", "delta_valor",
                       "nova_execucao_fim", "nova_vigencia_fim", "pdf"}


class CadastroInvalido(Exception):
    def __init__(self, erros: list[str]):
        self.erros = erros
        super().__init__("\n".join(erros))


def _ler(arquivo: Path):
    with arquivo.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def _data(v) -> str | None:
    """Aceita date (o YAML ja' converte 2026-08-28) ou texto ISO. Devolve ISO ou None."""
    if v is None or v == "":
        return None
    if isinstance(v, datetime.datetime):
        raise ValueError("use data sem hora (AAAA-MM-DD)")
    if isinstance(v, datetime.date):
        return v.isoformat()
    return datetime.date.fromisoformat(str(v)).isoformat()


def _bp(v) -> int:
    try:
        d = Decimal(str(v).replace(",", "."))
    except InvalidOperation:
        raise ValueError(f"percentual inválido: {v!r}") from None
    bp = int((d * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    if not 0 < bp <= 10000:
        raise ValueError(f"percentual fora de 0–100: {v!r}")
    return bp


def _instrumento(bruto: dict, onde: str, erros: list[str]) -> dict | None:
    def falha(campo, msg):
        erros.append(f"{onde}: {campo}: {msg}")

    chave, tipo = bruto.get("chave"), bruto.get("tipo")
    if not isinstance(chave, str) or not _CHAVE.match(chave.lower()) or chave != chave.strip():
        falha("chave", f"chave inválida: {chave!r}")
        return None
    if tipo not in TIPOS_ADITIVO and tipo not in TIPOS_OUTROS:
        falha("tipo", f"tipo desconhecido: {tipo!r}")
        return None
    inst = {"chave": chave, "tipo": tipo, "numero": bruto.get("numero"), "objeto": bruto.get("objeto"),
            "corrige": bruto.get("corrige"), "pdf": bruto.get("pdf"), "delta_valor_centavos": 0,
            "nova_execucao_fim": None, "nova_vigencia_fim": None,
            "dados": {k: v for k, v in bruto.items() if k not in _CAMPOS_INSTRUMENTO}}
    try:
        inst["data"] = _data(bruto.get("data"))
        inst["nova_execucao_fim"] = _data(bruto.get("nova_execucao_fim"))
        inst["nova_vigencia_fim"] = _data(bruto.get("nova_vigencia_fim"))
    except ValueError as e:
        falha("data", str(e))
        return None
    if not inst["data"]:
        falha("data", "obrigatória")
    if bruto.get("delta_valor") not in (None, ""):
        texto = str(bruto["delta_valor"]).strip()
        sinal = -1 if texto.startswith("-") else 1
        try:
            inst["delta_valor_centavos"] = sinal * dinheiro.parse_brl(texto.lstrip("-").strip())
        except ValueError as e:
            falha("delta_valor", str(e))
    if tipo in ("aditivo_valor",) and inst["delta_valor_centavos"] == 0:
        falha("delta_valor", "aditivo de valor sem delta")
    if tipo in ("aditivo_prazo", "apostilamento_prazo") and not (
            inst["nova_execucao_fim"] or inst["nova_vigencia_fim"]):
        falha("nova_execucao_fim", "instrumento de prazo sem data nova")
    if tipo in TIPOS_OUTROS and (inst["delta_valor_centavos"] or inst["nova_execucao_fim"]
                                 or inst["nova_vigencia_fim"]):
        falha("tipo", f"{tipo} não altera valor nem prazo; use aditivo ou apostilamento de prazo")
    # `dados` de data viram ISO para o JSON canonico nao depender do parser
    for k, v in list(inst["dados"].items()):
        if isinstance(v, datetime.date):
            inst["dados"][k] = v.isoformat()
    return inst


def _contrato(bruto: dict, arquivo: Path, raiz: Path, orgaos: set, ents: set,
              erros: list[str], avisos: list[str]) -> dict | None:
    onde = f"contratos/{arquivo.name}"

    def falha(campo, msg):
        erros.append(f"{onde}: {campo}: {msg}")

    if not isinstance(bruto, dict):
        falha("arquivo", "conteúdo não é um mapa YAML")
        return None
    for campo in ("nome_curto", "numero_instrumento", "orgao", "entidade", "objeto",
                  "valor_original", "status"):
        if bruto.get(campo) in (None, ""):
            falha(campo, "obrigatório")
    nome = str(bruto.get("nome_curto") or "")
    if nome and arquivo.stem != nome.lower().replace(" ", "-"):
        falha("nome_curto", f"arquivo {arquivo.name} não corresponde a nome_curto {nome!r} "
                            f"(esperado {nome.lower().replace(' ', '-')}.yaml)")
    if bruto.get("orgao") and bruto["orgao"] not in orgaos:
        falha("orgao", f"órgão não cadastrado: {bruto['orgao']}")
    if bruto.get("entidade") and bruto["entidade"] not in ents:
        falha("entidade", f"entidade não cadastrada: {bruto['entidade']}")
    if bruto.get("lei") is not None and str(bruto["lei"]) not in LEIS:
        falha("lei", f"use uma de {LEIS}")
    if bruto.get("status") not in STATUS:
        falha("status", f"use um de {STATUS}")

    c = {"nome_curto": nome, "numero_instrumento": str(bruto.get("numero_instrumento") or ""),
         "orgao": bruto.get("orgao"), "entidade": bruto.get("entidade"),
         "objeto": bruto.get("objeto"), "municipio": bruto.get("municipio"),
         "lei": None if bruto.get("lei") is None else str(bruto["lei"]),
         "cno": bruto.get("cno"), "art": bruto.get("art"),
         "numero_processo": bruto.get("numero_processo"),
         "centro_custo_rm": bruto.get("centro_custo_rm"), "status": bruto.get("status"),
         "sem_reajuste": bool(bruto.get("sem_reajuste", False)),
         "destinatarios_extras": [str(e).strip().lower() for e in bruto.get("destinatarios_extras") or []],
         "valor_original_centavos": 0, "percentual_direito_bp": 10000}
    try:
        c["valor_original_centavos"] = dinheiro.parse_brl(str(bruto.get("valor_original") or ""))
    except ValueError as e:
        falha("valor_original", str(e))
    try:
        c["percentual_direito_bp"] = _bp(bruto.get("percentual_lotufo", "100"))
    except ValueError as e:
        falha("percentual_lotufo", str(e))
    for campo in ("execucao_inicio", "execucao_fim", "vigencia_inicio", "vigencia_fim", "status_desde"):
        try:
            c[campo] = _data(bruto.get(campo))
        except ValueError as e:
            c[campo] = None
            falha(campo, str(e))
    if c["status"] == "em_encerramento" and not c["status_desde"]:
        falha("status_desde", "obrigatório quando status é em_encerramento (data da medição final)")
    if c["execucao_fim"] and c["vigencia_fim"] and c["vigencia_fim"] < c["execucao_fim"]:
        avisos.append(f"{onde}: vigência ({c['vigencia_fim']}) termina antes da execução "
                      f"({c['execucao_fim']})")

    c["datas_base"] = []
    for i, db_ in enumerate(bruto.get("datas_base") or []):
        mes = str((db_ or {}).get("mes") or "")
        if not _MES.match(mes):
            falha(f"datas_base[{i}].mes", f"use AAAA-MM: {mes!r}")
            continue
        c["datas_base"].append({"mes": mes, "indice": str(db_.get("indice") or "")})
    if len({d["mes"] for d in c["datas_base"]}) != len(c["datas_base"]):
        falha("datas_base", "mês repetido")

    c["fiscais"] = []
    for i, f in enumerate(bruto.get("fiscais") or []):
        try:
            desde = _data((f or {}).get("desde"))
        except ValueError as e:
            falha(f"fiscais[{i}].desde", str(e))
            continue
        if not (f or {}).get("email") or not desde:
            falha(f"fiscais[{i}]", "email e desde são obrigatórios")
            continue
        c["fiscais"].append({"nome": str(f.get("nome") or ""), "email": str(f["email"]).strip().lower(),
                             "desde": desde})

    c["instrumentos"] = []
    vistos: set[str] = set()
    for i, bruto_i in enumerate(bruto.get("instrumentos") or []):
        inst = _instrumento(bruto_i or {}, f"{onde}: instrumentos[{i}]", erros)
        if inst is None:
            continue
        if inst["chave"] in vistos:
            falha("instrumentos", f"chave repetida: {inst['chave']}")
        vistos.add(inst["chave"])
        if inst["pdf"] and not (raiz / inst["pdf"]).is_file():
            falha(f"instrumentos[{i}].pdf", f"arquivo não encontrado: {inst['pdf']}")
        c["instrumentos"].append(inst)
    for inst in c["instrumentos"]:
        if inst["corrige"] and inst["corrige"] not in vistos:
            falha("instrumentos", f"{inst['chave']} corrige {inst['corrige']!r}, que não existe")
    return c


def preparar(raiz: Path) -> dict:
    raiz = Path(raiz)
    erros: list[str] = []
    avisos: list[str] = []
    for nome in ("orgaos.yaml", "entidades.yaml"):
        if not (raiz / nome).is_file():
            raise CadastroInvalido([f"{nome}: arquivo não encontrado em {raiz}"])

    orgaos = []
    for i, o in enumerate(_ler(raiz / "orgaos.yaml") or []):
        onde = f"orgaos.yaml[{i}]"
        if not isinstance(o, dict) or not _CHAVE.match(str(o.get("chave") or "")):
            erros.append(f"{onde}: chave: inválida ou ausente")
            continue
        if o.get("familia") not in FAMILIAS:
            erros.append(f"{onde}: familia: use uma de {FAMILIAS}")
        if not o.get("nome"):
            erros.append(f"{onde}: nome: obrigatório")
        orgaos.append({"chave": o["chave"], "nome": o.get("nome"), "familia": o.get("familia"),
                       "regras": {k: v for k, v in o.items() if k not in ("chave", "nome", "familia")}})
    if len({o["chave"] for o in orgaos}) != len(orgaos):
        erros.append("orgaos.yaml: chave repetida")

    ents = []
    for i, e in enumerate(_ler(raiz / "entidades.yaml") or []):
        onde = f"entidades.yaml[{i}]"
        if not isinstance(e, dict) or not _CHAVE.match(str(e.get("chave") or "")):
            erros.append(f"{onde}: chave: inválida ou ausente")
            continue
        cnpj = re.sub(r"\D", "", str(e.get("cnpj") or ""))
        if not entidades.cnpj_valido(cnpj):
            erros.append(f"{onde}: cnpj: CNPJ inválido: {e.get('cnpj')!r}")
        if e.get("papel") not in PAPEIS:
            erros.append(f"{onde}: papel: use um de {PAPEIS}")
        if not e.get("nome"):
            erros.append(f"{onde}: nome: obrigatório")
        ents.append({"chave": e["chave"], "nome": e.get("nome"), "cnpj": cnpj, "papel": e.get("papel"),
                     "coligada_rm": e.get("coligada_rm"), "sigla_oficio": e.get("sigla_oficio")})
    for campo in ("chave", "cnpj"):
        if len({x[campo] for x in ents}) != len(ents):
            erros.append(f"entidades.yaml: {campo} repetido")

    chaves_orgao = {o["chave"] for o in orgaos}
    chaves_ent = {e["chave"] for e in ents}
    contratos = []
    for arquivo in sorted((raiz / "contratos").glob("*.yaml")):
        c = _contrato(_ler(arquivo), arquivo, raiz, chaves_orgao, chaves_ent, erros, avisos)
        if c is not None:
            contratos.append(c)
    for campo in ("nome_curto", "numero_instrumento"):
        valores = [c[campo] for c in contratos if c[campo]]
        if len(set(valores)) != len(valores):
            erros.append(f"contratos: {campo} repetido")

    if erros:
        raise CadastroInvalido(erros)
    return {"orgaos": orgaos, "entidades": ents, "contratos": contratos, "avisos": avisos}
```

- [ ] **Step 5: Rodar e ver passar**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_cadastro_arquivos.py -q`
Expected: `8 passed`.

- [ ] **Step 6: Commit**

```bash
git add backend/pyproject.toml backend/requirements.lock backend/app/cadastro_arquivos.py backend/tests/test_cadastro_arquivos.py
git commit -m "feat: leitura e validacao do cadastro versionado em YAML"
```

---

### Task 2: Migração 018 (tabelas e colunas do cadastro)

**Files:**
- Create: `backend/migrations/018_cadastro_versionado.sql`
- Test: `backend/tests/test_migracao_018.py`

**Interfaces:**
- Produces: tabelas `orgaos(id, chave UNIQUE, nome, familia, regras JSON)`, `contrato_datas_base(contrato_id, mes, indice)`, `contrato_fiscais(contrato_id, nome, email, desde)`, `instrumentos(contrato_id, chave, tipo, numero, data, dados JSON, pdf)`, `cadastro_aplicacoes(commit_hash, usuario_id, aplicado_em, resumo JSON)`; colunas `entidades.chave`, `entidades.sigla_oficio`, `contratos.{nome_curto, orgao_id, lei, municipio, cno, art, sem_reajuste, encerramento_iniciado_em, destinatarios_extras}`, `aditivos.{chave_cadastro, forma}`.

- [ ] **Step 1: Escrever o teste que falha**

`backend/tests/test_migracao_018.py`:

```python
import pytest
from app import db


@pytest.fixture
def conn(tmp_path, monkeypatch):
    monkeypatch.setenv("DASH_DB_PATH", str(tmp_path / "t.db"))
    c = db.get_conn(); db.migrate(c)
    yield c
    c.close()


def _colunas(conn, tabela):
    return {r[1] for r in conn.execute(f"PRAGMA table_info({tabela})")}


def test_cria_tabelas_e_colunas(conn):
    assert {"chave", "familia", "regras"} <= _colunas(conn, "orgaos")
    assert {"nome_curto", "orgao_id", "lei", "cno", "encerramento_iniciado_em",
            "sem_reajuste", "destinatarios_extras"} <= _colunas(conn, "contratos")
    assert {"chave_cadastro", "forma"} <= _colunas(conn, "aditivos")
    assert {"chave", "sigla_oficio"} <= _colunas(conn, "entidades")
    assert {"contrato_id", "chave", "tipo", "dados"} <= _colunas(conn, "instrumentos")


def test_reaplicar_e_inofensivo_e_adota_o_aditivo_da_carga_legada(conn):
    conn.execute("INSERT INTO contratos (orgao, numero_instrumento, objeto, valor_original_centavos) "
                 "VALUES ('SINFRA','1/2024','obra',100)")
    conn.execute("INSERT INTO aditivos (contrato_id, tipo, delta_valor_centavos, status, data_assinatura, "
                 "objeto) VALUES (1,'valor',50,'assinado','2026-08-04','Carga inicial: soma dos aditivos')")
    conn.commit()
    sql = (db.MIGRATIONS_DIR / "018_cadastro_versionado.sql").read_text(encoding="utf-8")
    conn.executescript(db._sem_alters_ja_aplicados(conn, sql))
    linha = conn.execute("SELECT chave_cadastro, forma FROM aditivos").fetchone()
    assert (linha["chave_cadastro"], linha["forma"]) == ("carga-legado", "termo_aditivo")


def test_nome_curto_e_unico(conn):
    base = "INSERT INTO contratos (orgao, numero_instrumento, objeto, valor_original_centavos, nome_curto) "
    conn.execute(base + "VALUES ('A','1','o',1,'MT-402')")
    with pytest.raises(Exception):
        conn.execute(base + "VALUES ('A','2','o',1,'MT-402')")
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_migracao_018.py -q`
Expected: FAIL com `no such table: orgaos`.

- [ ] **Step 3: Escrever a migração**

`backend/migrations/018_cadastro_versionado.sql`:

```sql
-- Cadastro versionado (spec 2026-09-21 §8 e §12). O cadastro de obras deixa de ter tela:
-- vem de arquivos YAML no repositorio, aplicados por `python -m app.cli cadastro aplicar`.
-- Tudo aqui e' ADITIVO: nenhuma tabela existente e' reconstruida.
--
-- "Em encerramento" e' a coluna encerramento_iniciado_em (estado continua 'ativo'): trocar
-- o CHECK de contratos.estado exigiria reconstruir a tabela que o banco inteiro referencia.
-- Aditivos de valor e de prazo continuam em `aditivos` (contratos.vigente depende dela); os
-- demais instrumentos vao para `instrumentos`.

CREATE TABLE IF NOT EXISTS orgaos (
    id INTEGER PRIMARY KEY,
    chave TEXT NOT NULL UNIQUE,
    nome TEXT NOT NULL,
    familia TEXT NOT NULL CHECK (familia IN ('mtpar','sinfra','ses','prefeitura')),
    regras TEXT NOT NULL,
    criado_em TEXT NOT NULL DEFAULT (datetime('now'))
);

ALTER TABLE entidades ADD COLUMN chave TEXT;
ALTER TABLE entidades ADD COLUMN sigla_oficio TEXT;

ALTER TABLE contratos ADD COLUMN nome_curto TEXT;
ALTER TABLE contratos ADD COLUMN orgao_id INTEGER REFERENCES orgaos(id);
ALTER TABLE contratos ADD COLUMN lei TEXT;
ALTER TABLE contratos ADD COLUMN municipio TEXT;
ALTER TABLE contratos ADD COLUMN cno TEXT;
ALTER TABLE contratos ADD COLUMN art TEXT;
ALTER TABLE contratos ADD COLUMN sem_reajuste INTEGER NOT NULL DEFAULT 0;
ALTER TABLE contratos ADD COLUMN encerramento_iniciado_em TEXT;
ALTER TABLE contratos ADD COLUMN destinatarios_extras TEXT;
CREATE UNIQUE INDEX IF NOT EXISTS contratos_nome_curto
    ON contratos(nome_curto) WHERE nome_curto IS NOT NULL;

CREATE TABLE IF NOT EXISTS contrato_datas_base (
    id INTEGER PRIMARY KEY,
    contrato_id INTEGER NOT NULL REFERENCES contratos(id),
    mes TEXT NOT NULL CHECK (mes GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]'),
    indice TEXT NOT NULL DEFAULT '',
    UNIQUE (contrato_id, mes)
);

CREATE TABLE IF NOT EXISTS contrato_fiscais (
    id INTEGER PRIMARY KEY,
    contrato_id INTEGER NOT NULL REFERENCES contratos(id),
    nome TEXT NOT NULL DEFAULT '',
    email TEXT NOT NULL,
    desde TEXT NOT NULL,
    UNIQUE (contrato_id, email, desde)
);

ALTER TABLE aditivos ADD COLUMN chave_cadastro TEXT;
ALTER TABLE aditivos ADD COLUMN forma TEXT;
CREATE UNIQUE INDEX IF NOT EXISTS aditivos_chave_cadastro
    ON aditivos(contrato_id, chave_cadastro) WHERE chave_cadastro IS NOT NULL;
-- O aditivo agregado da carga do legado (carga_legado.py) passa a ter chave, para o
-- cadastro reconhece-lo em vez de duplica-lo.
UPDATE aditivos SET chave_cadastro = 'carga-legado', forma = 'termo_aditivo'
 WHERE chave_cadastro IS NULL AND status = 'assinado' AND objeto LIKE 'Carga inicial:%';

CREATE TABLE IF NOT EXISTS instrumentos (
    id INTEGER PRIMARY KEY,
    contrato_id INTEGER NOT NULL REFERENCES contratos(id),
    chave TEXT NOT NULL,
    tipo TEXT NOT NULL CHECK (tipo IN ('apostilamento_reajuste','paralisacao','reinicio',
                                       'marco_encerramento','endosso_garantia')),
    numero TEXT,
    data TEXT NOT NULL,
    dados TEXT NOT NULL,
    pdf TEXT,
    criado_em TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (contrato_id, chave)
);

CREATE TABLE IF NOT EXISTS cadastro_aplicacoes (
    id INTEGER PRIMARY KEY,
    commit_hash TEXT,
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id),
    aplicado_em TEXT NOT NULL DEFAULT (datetime('now')),
    resumo TEXT NOT NULL
);
```

- [ ] **Step 4: Rodar e ver passar, e a suíte inteira**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_migracao_018.py tests/test_db.py tests/test_aditivos.py tests/test_contratos.py -q`
Expected: tudo passa (a migração não muda comportamento existente).

- [ ] **Step 5: Commit**

```bash
git add backend/migrations/018_cadastro_versionado.sql backend/tests/test_migracao_018.py
git commit -m "feat: migracao 018 - tabelas e colunas do cadastro versionado"
```

---

### Task 3: Aplicar órgãos e entidades (com ensaio)

**Files:**
- Create: `backend/app/cadastro_aplicar.py`
- Test: `backend/tests/test_cadastro_aplicar.py`

**Interfaces:**
- Consumes: estrutura de `cadastro_arquivos.preparar` (Task 1); tabelas da Task 2.
- Produces: `cadastro_aplicar.aplicar(conn, usuario_id: int, cad: dict, ensaio: bool = False, commit_hash: str | None = None) -> dict`. Relatório: `{"orgaos": R, "entidades": R, "contratos": R, "instrumentos": R, "avisos": [...], "ensaio": bool}` com `R = {"criados": [str], "alterados": [str], "iguais": int}`. Erro de regra levanta `ValueError` e nada é gravado.

- [ ] **Step 1: Escrever os testes que falham**

`backend/tests/test_cadastro_aplicar.py`:

```python
import json

import pytest
from app import auth, cadastro_aplicar, db

CNPJ_LOTUFO = "00000000000100"
CNPJ_OK = "00000000000500"


@pytest.fixture
def conn(tmp_path, monkeypatch):
    monkeypatch.setenv("DASH_DB_PATH", str(tmp_path / "t.db"))
    c = db.get_conn(); db.migrate(c)
    auth.criar_usuario(c, "U", "u@lotufo.com", "senha-forte-123", "admin")
    yield c
    c.close()


def _cad(**troca):
    base = {"orgaos": [{"chave": "sinfra-suef1", "nome": "SINFRA - SUEF I", "familia": "sinfra",
                        "regras": {"folga_vigencia_dias": 90}}],
            "entidades": [{"chave": "lotufo", "nome": "Lotufo Engenharia e Construções Ltda",
                           "cnpj": CNPJ_LOTUFO, "papel": "lotufo", "coligada_rm": 1, "sigla_oficio": "LT"}],
            "contratos": [], "avisos": []}
    return {**base, **troca}


def test_orgao_criado_depois_igual_depois_alterado(conn):
    r1 = cadastro_aplicar.aplicar(conn, 1, _cad())
    assert r1["orgaos"]["criados"] == ["sinfra-suef1"]
    r2 = cadastro_aplicar.aplicar(conn, 1, _cad())
    assert r2["orgaos"] == {"criados": [], "alterados": [], "iguais": 1}
    novo = _cad()
    novo["orgaos"][0]["regras"] = {"folga_vigencia_dias": 60}
    r3 = cadastro_aplicar.aplicar(conn, 1, novo)
    assert r3["orgaos"]["alterados"] == ["sinfra-suef1"]
    assert json.loads(conn.execute("SELECT regras FROM orgaos").fetchone()[0]) == {"folga_vigencia_dias": 60}


def test_entidade_casa_por_cnpj_com_a_lotufo_semeada(conn):
    r = cadastro_aplicar.aplicar(conn, 1, _cad())
    assert r["entidades"]["alterados"] == ["lotufo"]      # ganhou chave e sigla, nao duplicou
    linhas = conn.execute("SELECT id, chave, sigla_oficio FROM entidades").fetchall()
    assert [(x["id"], x["chave"], x["sigla_oficio"]) for x in linhas] == [(1, "lotufo", "LT")]


def test_entidade_nova_e_criada(conn):
    cad = _cad()
    cad["entidades"].append({"chave": "rivoli", "nome": "Rivoli", "cnpj": CNPJ_OK,
                             "papel": "consorciada", "coligada_rm": None, "sigla_oficio": None})
    r = cadastro_aplicar.aplicar(conn, 1, cad)
    assert r["entidades"]["criados"] == ["rivoli"]


def test_ensaio_relata_e_nao_grava(conn):
    r = cadastro_aplicar.aplicar(conn, 1, _cad(), ensaio=True)
    assert r["ensaio"] is True and r["orgaos"]["criados"] == ["sinfra-suef1"]
    assert conn.execute("SELECT COUNT(*) FROM orgaos").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM cadastro_aplicacoes").fetchone()[0] == 0


def test_aplicacao_real_fica_registrada_com_o_commit(conn):
    cadastro_aplicar.aplicar(conn, 1, _cad(), commit_hash="abc123")
    linha = conn.execute("SELECT commit_hash, usuario_id FROM cadastro_aplicacoes").fetchone()
    assert (linha["commit_hash"], linha["usuario_id"]) == ("abc123", 1)
    assert conn.execute("SELECT COUNT(*) FROM audit_log WHERE acao='cadastro.aplicar'").fetchone()[0] == 1
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_cadastro_aplicar.py -q`
Expected: FAIL com `ImportError: cannot import name 'cadastro_aplicar'`.

- [ ] **Step 3: Implementar**

`backend/app/cadastro_aplicar.py`:

```python
"""Grava no banco a estrutura normalizada do cadastro (spec 2026-09-21 §8).

Uma transacao so' (db.mutacao): qualquer erro desfaz tudo. Idempotente: reaplicar o mesmo
cadastro nao muda nada. `ensaio=True` roda de verdade e desfaz no fim, para o relatorio
mostrar exatamente o que SERIA gravado.
"""
import json
import sqlite3

from app import auditoria, contratos, db, tempo


class _Ensaio(Exception):
    """Sinal interno: desfaz a transacao do ensaio."""


def _rel() -> dict:
    return {"criados": [], "alterados": [], "iguais": 0}


def _json(v) -> str:
    return json.dumps(v, ensure_ascii=False, sort_keys=True)


def _diferencas(antes: dict, depois: dict) -> tuple[dict, dict]:
    chaves = [k for k in depois if antes.get(k) != depois[k]]
    return {k: antes.get(k) for k in chaves}, {k: depois[k] for k in chaves}


def _orgaos(conn, usuario_id, orgaos, rel) -> dict[str, int]:
    ids = {}
    for o in orgaos:
        novo = {"nome": o["nome"], "familia": o["familia"], "regras": _json(o["regras"])}
        ja = conn.execute("SELECT * FROM orgaos WHERE chave=?", (o["chave"],)).fetchone()
        if ja is None:
            cur = conn.execute("INSERT INTO orgaos (chave, nome, familia, regras) VALUES (?,?,?,?)",
                               (o["chave"], novo["nome"], novo["familia"], novo["regras"]))
            ids[o["chave"]] = cur.lastrowid
            rel["criados"].append(o["chave"])
            auditoria.registrar(conn, usuario_id, "cadastro.orgao", "orgao", cur.lastrowid, None, novo)
            continue
        ids[o["chave"]] = ja["id"]
        antes, depois = _diferencas(dict(ja), novo)
        if not depois:
            rel["iguais"] += 1
            continue
        conn.execute("UPDATE orgaos SET nome=?, familia=?, regras=? WHERE id=?",
                     (novo["nome"], novo["familia"], novo["regras"], ja["id"]))
        rel["alterados"].append(o["chave"])
        auditoria.registrar(conn, usuario_id, "cadastro.orgao", "orgao", ja["id"], antes, depois)
    return ids


def _entidades(conn, usuario_id, ents, rel) -> dict[str, int]:
    ids = {}
    for e in ents:
        novo = {"nome": e["nome"], "papel": e["papel"], "chave": e["chave"],
                "coligada_rm": e["coligada_rm"], "sigla_oficio": e["sigla_oficio"]}
        ja = conn.execute("SELECT * FROM entidades WHERE cnpj=?", (e["cnpj"],)).fetchone()
        if ja is None:
            cur = conn.execute(
                "INSERT INTO entidades (nome, cnpj, papel, chave, coligada_rm, sigla_oficio) "
                "VALUES (?,?,?,?,?,?)",
                (e["nome"], e["cnpj"], e["papel"], e["chave"], e["coligada_rm"], e["sigla_oficio"]))
            ids[e["chave"]] = cur.lastrowid
            rel["criados"].append(e["chave"])
            auditoria.registrar(conn, usuario_id, "cadastro.entidade", "entidade", cur.lastrowid,
                                None, {**novo, "cnpj": e["cnpj"]})
            continue
        ids[e["chave"]] = ja["id"]
        antes, depois = _diferencas(dict(ja), novo)
        if not depois:
            rel["iguais"] += 1
            continue
        conn.execute("UPDATE entidades SET nome=?, papel=?, chave=?, coligada_rm=?, sigla_oficio=? "
                     "WHERE id=?", (e["nome"], e["papel"], e["chave"], e["coligada_rm"],
                                    e["sigla_oficio"], ja["id"]))
        rel["alterados"].append(e["chave"])
        auditoria.registrar(conn, usuario_id, "cadastro.entidade", "entidade", ja["id"], antes, depois)
    return ids


def aplicar(conn: sqlite3.Connection, usuario_id: int, cad: dict, ensaio: bool = False,
            commit_hash: str | None = None) -> dict:
    rel = {"orgaos": _rel(), "entidades": _rel(), "contratos": _rel(), "instrumentos": _rel(),
           "avisos": list(cad.get("avisos", [])), "ensaio": ensaio}
    try:
        with db.mutacao(conn):
            ids_orgao = _orgaos(conn, usuario_id, cad["orgaos"], rel["orgaos"])
            ids_ent = _entidades(conn, usuario_id, cad["entidades"], rel["entidades"])
            for c in cad["contratos"]:
                _contrato(conn, usuario_id, c, ids_orgao, ids_ent, rel)
            if ensaio:
                raise _Ensaio()
            resumo = {k: {"criados": len(v["criados"]), "alterados": len(v["alterados"]),
                          "iguais": v["iguais"]}
                      for k, v in rel.items() if isinstance(v, dict)}
            conn.execute("INSERT INTO cadastro_aplicacoes (commit_hash, usuario_id, resumo) VALUES (?,?,?)",
                         (commit_hash, usuario_id, _json(resumo)))
            auditoria.registrar(conn, usuario_id, "cadastro.aplicar", "cadastro", None, None,
                                {"commit": commit_hash, **resumo})
    except _Ensaio:
        pass
    return rel


def _contrato(conn, usuario_id, c, ids_orgao, ids_ent, rel) -> None:
    """Preenchido nas Tasks 4 e 5."""
    raise NotImplementedError("contratos entram na Task 4")
```

Nota para o implementador: `_contrato` fica como está até a Task 4; os testes desta task usam `contratos: []` e não a alcançam. `contratos` e `tempo` são importados aqui porque as Tasks 4 e 5 os usam; se o linter reclamar do import não usado, deixe o aviso até a Task 4.

- [ ] **Step 4: Rodar e ver passar**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_cadastro_aplicar.py -q`
Expected: `5 passed`.

- [ ] **Step 5: Commit**

```bash
git add backend/app/cadastro_aplicar.py backend/tests/test_cadastro_aplicar.py
git commit -m "feat: aplicar orgaos e entidades do cadastro, com ensaio e auditoria"
```

---

### Task 4: Aplicar contratos (campos, status, datas-base, fiscais)

**Files:**
- Modify: `backend/app/cadastro_aplicar.py` (substitui `_contrato`)
- Test: `backend/tests/test_cadastro_aplicar.py` (acrescenta)

**Interfaces:**
- Consumes: `ids_orgao`, `ids_ent` da Task 3; `tempo.hoje_local() -> date`.
- Produces: `_contrato(conn, usuario_id, c, ids_orgao, ids_ent, rel) -> int` (id do contrato), que ao final chama `_instrumentos(conn, usuario_id, contrato_id, c, rel["instrumentos"])` da Task 5. Nesta task `_instrumentos` é criada vazia (`return None`) para o fluxo fechar.

- [ ] **Step 1: Escrever os testes que falham**

Acrescentar a `backend/tests/test_cadastro_aplicar.py`:

```python
def _contrato(**troca):
    base = {"nome_curto": "MT-402", "numero_instrumento": "019/2024/00/00-SINFRA",
            "orgao": "sinfra-suef1", "entidade": "lotufo", "objeto": "Remanescente da MT-402",
            "municipio": "Cuiabá", "lei": "14.133", "cno": None, "art": None, "numero_processo": None,
            "centro_custo_rm": "4.003.016", "valor_original_centavos": 1512720000,
            "percentual_direito_bp": 10000, "execucao_inicio": "2024-03-11", "execucao_fim": "2026-08-28",
            "vigencia_inicio": None, "vigencia_fim": "2026-11-22", "status": "ativo", "status_desde": None,
            "sem_reajuste": False, "datas_base": [{"mes": "2023-04", "indice": "setorial"}],
            "fiscais": [{"nome": "Fulano", "email": "fulano@exemplo.com.br", "desde": "2026-01-01"}],
            "destinatarios_extras": ["supervisora@exemplo.com.br"], "instrumentos": []}
    return {**base, **troca}


def test_contrato_existente_e_atualizado_pelo_numero_do_instrumento(conn):
    conn.execute("INSERT INTO contratos (orgao, numero_instrumento, objeto, valor_original_centavos) "
                 "VALUES ('SINFRA','019/2024/00/00-SINFRA','MT-402',1512720000)")
    conn.commit()
    r = cadastro_aplicar.aplicar(conn, 1, _cad(contratos=[_contrato()]))
    assert r["contratos"]["alterados"] == ["MT-402"] and r["contratos"]["criados"] == []
    c = conn.execute("SELECT * FROM contratos").fetchall()
    assert len(c) == 1 and c[0]["nome_curto"] == "MT-402" and c[0]["lei"] == "14.133"
    assert c[0]["orgao_id"] == 1 and c[0]["entidade_id"] == 1
    assert json.loads(c[0]["destinatarios_extras"]) == ["supervisora@exemplo.com.br"]


def test_reaplicar_contrato_e_igual(conn):
    cadastro_aplicar.aplicar(conn, 1, _cad(contratos=[_contrato()]))
    r = cadastro_aplicar.aplicar(conn, 1, _cad(contratos=[_contrato()]))
    assert r["contratos"] == {"criados": [], "alterados": [], "iguais": 1}


def test_em_encerramento_mantem_ativo_e_grava_a_data(conn):
    cad = _cad(contratos=[_contrato(status="em_encerramento", status_desde="2026-07-17")])
    cadastro_aplicar.aplicar(conn, 1, cad)
    c = conn.execute("SELECT estado, encerramento_iniciado_em FROM contratos").fetchone()
    assert (c["estado"], c["encerramento_iniciado_em"]) == ("ativo", "2026-07-17")


def test_suspender_gera_evento_do_contrato(conn):
    cadastro_aplicar.aplicar(conn, 1, _cad(contratos=[_contrato()]))
    cadastro_aplicar.aplicar(conn, 1, _cad(contratos=[_contrato(status="suspenso", status_desde="2025-10-01")]))
    ev = conn.execute("SELECT tipo, data FROM contrato_eventos").fetchall()
    assert [(e["tipo"], e["data"]) for e in ev] == [("suspensao", "2025-10-01")]
    assert conn.execute("SELECT estado FROM contratos").fetchone()[0] == "suspenso"


def test_valor_original_nao_muda_com_medicao_congelada(conn):
    cadastro_aplicar.aplicar(conn, 1, _cad(contratos=[_contrato()]))
    conn.execute("INSERT INTO medicoes (contrato_id, numero, tipo, competencia, estado, congelada) "
                 "VALUES (1,1,'execucao','2026-08','protocolada',1)")
    conn.commit()
    with pytest.raises(ValueError, match="valor original"):
        cadastro_aplicar.aplicar(conn, 1, _cad(contratos=[_contrato(valor_original_centavos=1)]))
    assert conn.execute("SELECT valor_original_centavos FROM contratos").fetchone()[0] == 1512720000


def test_datas_base_sincronizam_e_fiscal_novo_nao_apaga_o_antigo(conn):
    cadastro_aplicar.aplicar(conn, 1, _cad(contratos=[_contrato()]))
    novo = _contrato(datas_base=[{"mes": "2022-01", "indice": "SINAPI"}, {"mes": "2022-03", "indice": "SICRO"}],
                     fiscais=[{"nome": "Fulano", "email": "fulano@exemplo.com.br", "desde": "2026-01-01"},
                              {"nome": "Ana", "email": "ana@exemplo.com.br", "desde": "2026-09-01"}])
    cadastro_aplicar.aplicar(conn, 1, _cad(contratos=[novo]))
    assert [r[0] for r in conn.execute("SELECT mes FROM contrato_datas_base ORDER BY mes")] == ["2022-01", "2022-03"]
    assert conn.execute("SELECT COUNT(*) FROM contrato_fiscais").fetchone()[0] == 2
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_cadastro_aplicar.py -q`
Expected: os 6 novos falham com `NotImplementedError: contratos entram na Task 4`.

- [ ] **Step 3: Implementar**

Em `backend/app/cadastro_aplicar.py`, substituir a função `_contrato` inteira por:

```python
# status do cadastro -> contratos.estado. "em_encerramento" nao e' estado do banco: e'
# 'ativo' com encerramento_iniciado_em preenchido (migracao 018).
_ESTADO = {"ativo": "ativo", "suspenso": "suspenso", "em_encerramento": "ativo", "encerrado": "encerrado"}
_EVENTO = {("ativo", "suspenso"): "suspensao", ("suspenso", "ativo"): "retomada",
           ("ativo", "encerrado"): "encerramento", ("suspenso", "encerrado"): "encerramento"}
_CAMPOS_CONTRATO = ("nome_curto", "orgao", "orgao_id", "entidade_id", "objeto", "municipio", "lei", "cno",
                    "art", "numero_processo", "centro_custo_rm", "valor_original_centavos",
                    "percentual_direito_bp", "execucao_inicio", "execucao_fim", "vigencia_inicio",
                    "vigencia_fim", "sem_reajuste", "encerramento_iniciado_em", "destinatarios_extras",
                    "estado")


def _contrato(conn, usuario_id, c, ids_orgao, ids_ent, rel) -> int:
    nome_orgao = conn.execute("SELECT nome FROM orgaos WHERE id=?", (ids_orgao[c["orgao"]],)).fetchone()[0]
    ja = conn.execute("SELECT * FROM contratos WHERE numero_instrumento=?",
                      (c["numero_instrumento"],)).fetchone()
    enc = c["status_desde"] if c["status"] == "em_encerramento" else (
        ja["encerramento_iniciado_em"] if ja is not None and c["status"] == "encerrado" else None)
    novo = {"nome_curto": c["nome_curto"], "orgao": nome_orgao, "orgao_id": ids_orgao[c["orgao"]],
            "entidade_id": ids_ent[c["entidade"]], "objeto": c["objeto"], "municipio": c["municipio"],
            "lei": c["lei"], "cno": c["cno"], "art": c["art"], "numero_processo": c["numero_processo"],
            "centro_custo_rm": c["centro_custo_rm"],
            "valor_original_centavos": c["valor_original_centavos"],
            "percentual_direito_bp": c["percentual_direito_bp"],
            "execucao_inicio": c["execucao_inicio"], "execucao_fim": c["execucao_fim"],
            "vigencia_inicio": c["vigencia_inicio"], "vigencia_fim": c["vigencia_fim"],
            "sem_reajuste": 1 if c["sem_reajuste"] else 0, "encerramento_iniciado_em": enc,
            "destinatarios_extras": _json(c["destinatarios_extras"]), "estado": _ESTADO[c["status"]]}
    mudou = False
    if ja is None:
        colunas = ["numero_instrumento", *_CAMPOS_CONTRATO]
        cur = conn.execute(
            f"INSERT INTO contratos ({','.join(colunas)}) VALUES ({','.join('?' * len(colunas))})",
            [c["numero_instrumento"], *[novo[k] for k in _CAMPOS_CONTRATO]])
        cid = cur.lastrowid
        mudou = True
        rel["contratos"]["criados"].append(c["nome_curto"])
        auditoria.registrar(conn, usuario_id, "cadastro.contrato", "contrato", cid, None,
                            {"numero_instrumento": c["numero_instrumento"], **novo})
    else:
        cid = ja["id"]
        antes, depois = _diferencas(dict(ja), novo)
        if "valor_original_centavos" in depois and conn.execute(
                "SELECT 1 FROM medicoes WHERE contrato_id=? AND congelada=1 LIMIT 1", (cid,)).fetchone():
            raise ValueError(f"{c['nome_curto']}: o valor original não muda com medição congelada; "
                             "a alteração de valor entra como instrumento")
        if depois:
            sets = ", ".join(f"{k}=?" for k in depois)
            conn.execute(f"UPDATE contratos SET {sets} WHERE id=?", [*depois.values(), cid])
            if "estado" in depois:
                tipo = _EVENTO.get((antes["estado"], depois["estado"]))
                if tipo is None:
                    raise ValueError(f"{c['nome_curto']}: mudança de estado não prevista: "
                                     f"{antes['estado']} → {depois['estado']}")
                conn.execute("INSERT INTO contrato_eventos (contrato_id, tipo, data, observacao) "
                             "VALUES (?,?,?,?)",
                             (cid, tipo, c["status_desde"] or tempo.hoje_local().isoformat(),
                              "Cadastro versionado"))
            mudou = True
            auditoria.registrar(conn, usuario_id, "cadastro.contrato", "contrato", cid, antes, depois)

    # Datas-base: o cadastro e' a verdade (configuracao, nao historico financeiro).
    atuais = {r["mes"]: r["indice"] for r in conn.execute(
        "SELECT mes, indice FROM contrato_datas_base WHERE contrato_id=?", (cid,))}
    desejadas = {d["mes"]: d["indice"] for d in c["datas_base"]}
    if atuais != desejadas:
        conn.execute("DELETE FROM contrato_datas_base WHERE contrato_id=?", (cid,))
        conn.executemany("INSERT INTO contrato_datas_base (contrato_id, mes, indice) VALUES (?,?,?)",
                         [(cid, m, i) for m, i in sorted(desejadas.items())])
        mudou = True
        auditoria.registrar(conn, usuario_id, "cadastro.datas_base", "contrato", cid, atuais, desejadas)

    # Fiscais: historico. So' acrescenta; o fiscal vigente e' o de `desde` mais recente.
    for f in c["fiscais"]:
        cur = conn.execute("INSERT OR IGNORE INTO contrato_fiscais (contrato_id, nome, email, desde) "
                           "VALUES (?,?,?,?)", (cid, f["nome"], f["email"], f["desde"]))
        if cur.rowcount:
            mudou = True
            auditoria.registrar(conn, usuario_id, "cadastro.fiscal", "contrato", cid, None, f)

    if ja is not None:
        if mudou:
            rel["contratos"]["alterados"].append(c["nome_curto"])
        else:
            rel["contratos"]["iguais"] += 1
    _instrumentos(conn, usuario_id, cid, c, rel["instrumentos"])
    return cid


def _instrumentos(conn, usuario_id, contrato_id, c, rel) -> None:
    """Preenchido na Task 5."""
    return None
```

- [ ] **Step 4: Rodar e ver passar**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_cadastro_aplicar.py -q`
Expected: `11 passed`.

- [ ] **Step 5: Commit**

```bash
git add backend/app/cadastro_aplicar.py backend/tests/test_cadastro_aplicar.py
git commit -m "feat: aplicar contratos do cadastro - campos, status, datas-base e fiscais"
```

---

### Task 5: Aplicar instrumentos (imutáveis depois de aplicados)

**Files:**
- Modify: `backend/app/cadastro_aplicar.py` (substitui `_instrumentos`)
- Test: `backend/tests/test_cadastro_aplicar.py` (acrescenta)

**Interfaces:**
- Consumes: `contratos.vigente(conn, contrato_id) -> dict` com `valor_vigente_centavos`, `execucao_fim_vigente`, `vigencia_fim_vigente`; `cadastro_arquivos.TIPOS_ADITIVO`.
- Produces: instrumentos que alteram valor ou prazo gravados em `aditivos` (status `assinado`, `chave_cadastro`, `forma`, retrato `valor_anterior_centavos`/`valor_novo_centavos`); os demais em `instrumentos`.

- [ ] **Step 1: Escrever os testes que falham**

Acrescentar a `backend/tests/test_cadastro_aplicar.py`:

```python
from app import contratos as contratos_mod

AD_VALOR = {"chave": "ta-01", "tipo": "aditivo_valor", "data": "2026-06-30", "numero": "019/2024/01/01",
            "objeto": "1ª revisão em fase de obra", "corrige": None, "pdf": None,
            "delta_valor_centavos": 323606718, "nova_execucao_fim": None, "nova_vigencia_fim": None, "dados": {}}
AP_PRAZO = {"chave": "ap-10", "tipo": "apostilamento_prazo", "data": "2026-08-26", "numero": "019/2024/02/10",
            "objeto": None, "corrige": None, "pdf": None, "delta_valor_centavos": 0,
            "nova_execucao_fim": "2027-02-24", "nova_vigencia_fim": "2027-05-25", "dados": {}}
AP_REAJ = {"chave": "ap-09", "tipo": "apostilamento_reajuste", "data": "2026-03-06", "numero": "019/2024/02/09",
           "objeto": None, "corrige": None, "pdf": None, "delta_valor_centavos": 0,
           "nova_execucao_fim": None, "nova_vigencia_fim": None, "dados": {"ciclo": "2025-04", "percentual": None}}


def test_instrumentos_de_valor_e_prazo_mudam_o_vigente(conn):
    cad = _cad(contratos=[_contrato(instrumentos=[AP_PRAZO, AD_VALOR])])   # fora de ordem de proposito
    r = cadastro_aplicar.aplicar(conn, 1, cad)
    assert sorted(r["instrumentos"]["criados"]) == ["MT-402/ap-10", "MT-402/ta-01"]
    v = contratos_mod.vigente(conn, 1)
    assert v["valor_vigente_centavos"] == 1512720000 + 323606718
    assert (v["execucao_fim_vigente"], v["vigencia_fim_vigente"]) == ("2027-02-24", "2027-05-25")
    ad = conn.execute("SELECT * FROM aditivos WHERE chave_cadastro='ta-01'").fetchone()
    assert (ad["status"], ad["forma"], ad["valor_anterior_centavos"]) == ("assinado", "termo_aditivo", 1512720000)
    assert conn.execute("SELECT forma FROM aditivos WHERE chave_cadastro='ap-10'").fetchone()[0] == "apostilamento"


def test_reaplicar_instrumentos_e_igual(conn):
    cad = _cad(contratos=[_contrato(instrumentos=[AD_VALOR, AP_REAJ])])
    cadastro_aplicar.aplicar(conn, 1, cad)
    r = cadastro_aplicar.aplicar(conn, 1, cad)
    assert r["instrumentos"] == {"criados": [], "alterados": [], "iguais": 2}
    assert conn.execute("SELECT COUNT(*) FROM aditivos").fetchone()[0] == 1


def test_alterar_instrumento_aplicado_e_recusado_e_nada_muda(conn):
    cadastro_aplicar.aplicar(conn, 1, _cad(contratos=[_contrato(instrumentos=[AD_VALOR])]))
    adulterado = {**AD_VALOR, "delta_valor_centavos": 1}
    with pytest.raises(ValueError, match="já aplicado"):
        cadastro_aplicar.aplicar(conn, 1, _cad(contratos=[_contrato(instrumentos=[adulterado])]))
    assert conn.execute("SELECT delta_valor_centavos FROM aditivos").fetchone()[0] == 323606718


def test_instrumento_aplicado_que_some_do_cadastro_e_recusado(conn):
    cadastro_aplicar.aplicar(conn, 1, _cad(contratos=[_contrato(instrumentos=[AD_VALOR])]))
    with pytest.raises(ValueError, match="sumiu"):
        cadastro_aplicar.aplicar(conn, 1, _cad(contratos=[_contrato(instrumentos=[])]))


def test_apostilamento_de_reajuste_vai_para_instrumentos(conn):
    cadastro_aplicar.aplicar(conn, 1, _cad(contratos=[_contrato(instrumentos=[AP_REAJ])]))
    linha = conn.execute("SELECT tipo, numero, dados FROM instrumentos").fetchone()
    assert (linha["tipo"], linha["numero"]) == ("apostilamento_reajuste", "019/2024/02/09")
    assert json.loads(linha["dados"])["ciclo"] == "2025-04"
    assert conn.execute("SELECT COUNT(*) FROM aditivos").fetchone()[0] == 0


def test_texto_descritivo_do_aditivo_pode_ser_corrigido(conn):
    cadastro_aplicar.aplicar(conn, 1, _cad(contratos=[_contrato(instrumentos=[AD_VALOR])]))
    r = cadastro_aplicar.aplicar(conn, 1, _cad(contratos=[_contrato(instrumentos=[{**AD_VALOR, "objeto": "1ª RPFO"}])]))
    assert r["instrumentos"]["alterados"] == ["MT-402/ta-01"]
    assert conn.execute("SELECT objeto FROM aditivos").fetchone()[0] == "1ª RPFO"
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_cadastro_aplicar.py -q`
Expected: os 6 novos falham (nada é gravado em `aditivos` nem em `instrumentos`).

- [ ] **Step 3: Implementar**

Em `backend/app/cadastro_aplicar.py`, acrescentar ao topo `from app.cadastro_arquivos import TIPOS_ADITIVO` e substituir a função `_instrumentos` por:

```python
# O que torna um aditivo o que ele e': nao muda depois de aplicado (correcao e' instrumento
# novo). Numero, objeto e forma sao descricao e podem ser corrigidos.
_IMUTAVEL_ADITIVO = ("tipo", "delta_valor_centavos", "nova_execucao_fim", "nova_vigencia_fim",
                     "data_assinatura")


def _instrumentos(conn, usuario_id, contrato_id, c, rel) -> None:
    nome = c["nome_curto"]
    do_cadastro = {i["chave"] for i in c["instrumentos"]}
    aplicadas = [r["chave_cadastro"] for r in conn.execute(
        "SELECT chave_cadastro FROM aditivos WHERE contrato_id=? AND chave_cadastro IS NOT NULL",
        (contrato_id,))] + [r["chave"] for r in conn.execute(
            "SELECT chave FROM instrumentos WHERE contrato_id=?", (contrato_id,))]
    for chave in aplicadas:
        if chave not in do_cadastro:
            raise ValueError(f"{nome}: o instrumento {chave} já foi aplicado e sumiu do cadastro; "
                             "instrumento aplicado não se apaga (correção é instrumento novo)")

    # Ordem cronologica (empate: ordem do arquivo): o retrato valor_anterior/valor_novo de
    # cada aditivo depende dos que vieram antes.
    ordenados = sorted(enumerate(c["instrumentos"]), key=lambda par: (par[1]["data"], par[0]))
    for _, inst in ordenados:
        rotulo = f"{nome}/{inst['chave']}"
        if inst["tipo"] in TIPOS_ADITIVO:
            _aditivo(conn, usuario_id, contrato_id, inst, rotulo, rel)
        else:
            _outro(conn, usuario_id, contrato_id, inst, rotulo, rel)


def _aditivo(conn, usuario_id, contrato_id, inst, rotulo, rel) -> None:
    novo = {"tipo": TIPOS_ADITIVO[inst["tipo"]], "delta_valor_centavos": inst["delta_valor_centavos"],
            "nova_execucao_fim": inst["nova_execucao_fim"], "nova_vigencia_fim": inst["nova_vigencia_fim"],
            "data_assinatura": inst["data"], "numero": inst["numero"], "objeto": inst["objeto"],
            "forma": "apostilamento" if inst["tipo"].startswith("apostilamento") else "termo_aditivo"}
    ja = conn.execute("SELECT * FROM aditivos WHERE contrato_id=? AND chave_cadastro=?",
                      (contrato_id, inst["chave"])).fetchone()
    if ja is None:
        anterior = contratos.vigente(conn, contrato_id)["valor_vigente_centavos"]
        cur = conn.execute(
            """INSERT INTO aditivos (contrato_id, tipo, delta_valor_centavos, nova_vigencia_fim,
                   nova_execucao_fim, status, data_assinatura, numero, objeto, forma, chave_cadastro,
                   valor_anterior_centavos, valor_novo_centavos, assinado_por, observacao)
               VALUES (?,?,?,?,?,'assinado',?,?,?,?,?,?,?,?,?)""",
            (contrato_id, novo["tipo"], novo["delta_valor_centavos"], novo["nova_vigencia_fim"],
             novo["nova_execucao_fim"], novo["data_assinatura"], novo["numero"], novo["objeto"],
             novo["forma"], inst["chave"], anterior, anterior + novo["delta_valor_centavos"], usuario_id,
             f"Corrige {inst['corrige']}" if inst["corrige"] else None))
        rel["criados"].append(rotulo)
        auditoria.registrar(conn, usuario_id, "cadastro.instrumento", "aditivo", cur.lastrowid, None,
                            {"chave": inst["chave"], **novo})
        return
    for campo in _IMUTAVEL_ADITIVO:
        # A carga legada gravou o agregado como tipo 'valor' sem datas: comparar so' o que o
        # cadastro declara de diferente do que esta' gravado.
        if ja[campo] != novo[campo]:
            raise ValueError(f"{rotulo}: instrumento já aplicado não pode ser alterado "
                             f"({campo}: {ja[campo]!r} → {novo[campo]!r}); registre um instrumento novo "
                             "com `corrige`")
    antes, depois = _diferencas(dict(ja), {k: novo[k] for k in ("numero", "objeto", "forma")})
    if not depois:
        rel["iguais"] += 1
        return
    sets = ", ".join(f"{k}=?" for k in depois)
    conn.execute(f"UPDATE aditivos SET {sets} WHERE id=?", [*depois.values(), ja["id"]])
    rel["alterados"].append(rotulo)
    auditoria.registrar(conn, usuario_id, "cadastro.instrumento", "aditivo", ja["id"], antes, depois)


def _outro(conn, usuario_id, contrato_id, inst, rotulo, rel) -> None:
    novo = {"tipo": inst["tipo"], "numero": inst["numero"], "data": inst["data"],
            "dados": _json({**inst["dados"], "objeto": inst["objeto"], "corrige": inst["corrige"]})}
    ja = conn.execute("SELECT * FROM instrumentos WHERE contrato_id=? AND chave=?",
                      (contrato_id, inst["chave"])).fetchone()
    if ja is None:
        cur = conn.execute("INSERT INTO instrumentos (contrato_id, chave, tipo, numero, data, dados, pdf) "
                           "VALUES (?,?,?,?,?,?,?)", (contrato_id, inst["chave"], novo["tipo"],
                                                      novo["numero"], novo["data"], novo["dados"], inst["pdf"]))
        rel["criados"].append(rotulo)
        auditoria.registrar(conn, usuario_id, "cadastro.instrumento", "instrumento", cur.lastrowid, None,
                            {"chave": inst["chave"], **novo})
        return
    for campo in ("tipo", "numero", "data", "dados"):
        if ja[campo] != novo[campo]:
            raise ValueError(f"{rotulo}: instrumento já aplicado não pode ser alterado ({campo}); "
                             "registre um instrumento novo com `corrige`")
    if ja["pdf"] != inst["pdf"]:
        conn.execute("UPDATE instrumentos SET pdf=? WHERE id=?", (inst["pdf"], ja["id"]))
        rel["alterados"].append(rotulo)
        auditoria.registrar(conn, usuario_id, "cadastro.instrumento", "instrumento", ja["id"],
                            {"pdf": ja["pdf"]}, {"pdf": inst["pdf"]})
        return
    rel["iguais"] += 1
```

- [ ] **Step 4: Rodar e ver passar, e a vizinhança**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_cadastro_aplicar.py tests/test_aditivos.py tests/test_contratos.py tests/test_auditoria.py -q`
Expected: tudo passa (`test_cadastro_aplicar.py`: 17).

- [ ] **Step 5: Commit**

```bash
git add backend/app/cadastro_aplicar.py backend/tests/test_cadastro_aplicar.py
git commit -m "feat: aplicar instrumentos do cadastro - aditivos, apostilamentos e imutabilidade"
```

---

### Task 6: Comando `cadastro`, guarda das rotas de escrita e runbook

**Files:**
- Modify: `backend/app/cli.py`, `backend/app/permissoes.py`, `backend/app/api_contratos.py` (3 rotas), `backend/app/api_aditivos.py` (4 rotas), `backend/app/api_certidoes.py` (4 rotas), `scripts/rodar_producao.ps1`, `docs/runbook.md`
- Test: `backend/tests/test_cli_cadastro.py`, `backend/tests/test_permissoes.py` (acrescenta)

**Interfaces:**
- Consumes: `cadastro_arquivos.preparar`, `cadastro_aplicar.aplicar`.
- Produces: `python -m app.cli cadastro validar [--raiz cadastro]` (sai 0 ou 1) e `python -m app.cli cadastro aplicar --usuario <email> [--raiz cadastro] [--ensaio]`; `cli.main(argv: list[str] | None = None) -> int`; `permissoes.exigir_cadastro_editavel()`.

- [ ] **Step 1: Escrever os testes que falham**

`backend/tests/test_cli_cadastro.py`:

```python
import yaml
from app import auth, cli, db

ORGAOS = [{"chave": "sinfra-suef1", "nome": "SINFRA - SUEF I", "familia": "sinfra"}]
ENTS = [{"chave": "lotufo", "nome": "Lotufo", "cnpj": "00.000.000/0001-00", "papel": "lotufo",
         "coligada_rm": 1, "sigla_oficio": "LT"}]
CONTRATO = {"nome_curto": "MT-402", "numero_instrumento": "019/2024/00/00-SINFRA", "orgao": "sinfra-suef1",
            "entidade": "lotufo", "objeto": "MT-402", "valor_original": "15.127.200,00", "status": "ativo"}


def _cadastro(raiz, contrato=CONTRATO):
    (raiz / "contratos").mkdir(parents=True)
    (raiz / "orgaos.yaml").write_text(yaml.safe_dump(ORGAOS), "utf-8")
    (raiz / "entidades.yaml").write_text(yaml.safe_dump(ENTS), "utf-8")
    (raiz / "contratos" / "mt-402.yaml").write_text(yaml.safe_dump(contrato, allow_unicode=True), "utf-8")
    return raiz


def _banco(tmp_path, monkeypatch):
    monkeypatch.setenv("DASH_DB_PATH", str(tmp_path / "t.db"))
    c = db.get_conn(); db.migrate(c)
    auth.criar_usuario(c, "Leo", "leo@lotufo.com", "senha-forte-123", "admin")
    return c


def test_validar_ok_sai_zero(tmp_path, capsys):
    assert cli.main(["cadastro", "validar", "--raiz", str(_cadastro(tmp_path / "cad"))]) == 0
    assert "1 contrato" in capsys.readouterr().out


def test_validar_com_erro_sai_um_e_lista_os_erros(tmp_path, capsys):
    raiz = _cadastro(tmp_path / "cad", {**CONTRATO, "orgao": "nao-existe"})
    assert cli.main(["cadastro", "validar", "--raiz", str(raiz)]) == 1
    assert "nao-existe" in capsys.readouterr().out


def test_aplicar_grava_e_ensaio_nao(tmp_path, monkeypatch, capsys):
    conn = _banco(tmp_path, monkeypatch)
    raiz = str(_cadastro(tmp_path / "cad"))
    assert cli.main(["cadastro", "aplicar", "--raiz", raiz, "--usuario", "leo@lotufo.com", "--ensaio"]) == 0
    assert conn.execute("SELECT COUNT(*) FROM contratos").fetchone()[0] == 0
    assert cli.main(["cadastro", "aplicar", "--raiz", raiz, "--usuario", "leo@lotufo.com"]) == 0
    assert conn.execute("SELECT nome_curto FROM contratos").fetchone()[0] == "MT-402"
    assert "ENSAIO" in capsys.readouterr().out


def test_aplicar_com_usuario_inexistente_sai_um(tmp_path, monkeypatch):
    _banco(tmp_path, monkeypatch)
    raiz = str(_cadastro(tmp_path / "cad"))
    assert cli.main(["cadastro", "aplicar", "--raiz", raiz, "--usuario", "ninguem@lotufo.com"]) == 1
```

Acrescentar a `backend/tests/test_permissoes.py`:

```python
def test_cadastro_versionado_fecha_as_rotas_de_escrita(client_admin, monkeypatch):
    monkeypatch.setenv("DASH_CADASTRO_VERSIONADO", "1")
    corpo = {"orgao": "X", "numero_instrumento": "1/2026", "objeto": "o", "valor_original": "1,00"}
    assert client_admin.post("/api/contratos", json=corpo).status_code == 409
    assert client_admin.post("/api/contratos/1/aditivos", json={"tipo": "valor"}).status_code == 409
    assert client_admin.post("/api/entidades", json={"nome": "E", "cnpj": "00000000000600",
                                                     "papel": "consorcio"}).status_code == 409
    assert client_admin.get("/api/contratos").status_code == 200      # leitura continua
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_cli_cadastro.py tests/test_permissoes.py -q`
Expected: FAIL (`main()` não aceita argumentos; as rotas respondem 201 ou 422 em vez de 409).

- [ ] **Step 3: Implementar o comando**

Substituir `backend/app/cli.py` inteiro por:

```python
import argparse
import getpass
import subprocess
import sys
from pathlib import Path

from app import auth, cadastro_aplicar, cadastro_arquivos, db

RAIZ_PADRAO = Path(__file__).resolve().parent.parent.parent / "cadastro"


def _commit(raiz: Path) -> str | None:
    try:
        r = subprocess.run(["git", "rev-parse", "HEAD"], cwd=raiz, capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout.strip() or None if r.returncode == 0 else None


def _relatorio(rel: dict) -> None:
    print("ENSAIO (nada foi gravado)" if rel["ensaio"] else "APLICADO")
    for nome in ("orgaos", "entidades", "contratos", "instrumentos"):
        r = rel[nome]
        print(f"  {nome}: {len(r['criados'])} criados, {len(r['alterados'])} alterados, {r['iguais']} iguais")
        for rotulo in r["criados"]:
            print(f"    + {rotulo}")
        for rotulo in r["alterados"]:
            print(f"    ~ {rotulo}")
    for aviso in rel["avisos"]:
        print(f"  AVISO: {aviso}")


def _cadastro(args) -> int:
    raiz = Path(args.raiz)
    try:
        cad = cadastro_arquivos.preparar(raiz)
    except cadastro_arquivos.CadastroInvalido as e:
        print(f"Cadastro inválido ({len(e.erros)} erro(s)):")
        for erro in e.erros:
            print(f"  - {erro}")
        return 1
    n = len(cad["contratos"])
    if args.acao == "validar":
        print(f"Cadastro válido: {len(cad['orgaos'])} órgão(s), {len(cad['entidades'])} entidade(s), "
              f"{n} contrato{'s' if n != 1 else ''}.")
        for aviso in cad["avisos"]:
            print(f"  AVISO: {aviso}")
        return 0
    conn = db.get_conn()
    try:
        db.migrate(conn)
        u = conn.execute("SELECT id FROM usuarios WHERE email=? AND ativo=1", (args.usuario,)).fetchone()
        if u is None:
            print(f"Usuário não encontrado ou inativo: {args.usuario}")
            return 1
        try:
            rel = cadastro_aplicar.aplicar(conn, u["id"], cad, ensaio=args.ensaio, commit_hash=_commit(raiz))
        except ValueError as e:
            print(f"Cadastro recusado, nada foi gravado: {e}")
            return 1
    finally:
        conn.close()
    _relatorio(rel)
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="app.cli")
    sub = p.add_subparsers(dest="cmd", required=True)
    ca = sub.add_parser("criar-admin")
    ca.add_argument("--nome", required=True)
    ca.add_argument("--email", required=True)
    cad = sub.add_parser("cadastro")
    cad.add_argument("acao", choices=["validar", "aplicar"])
    cad.add_argument("--raiz", default=str(RAIZ_PADRAO))
    cad.add_argument("--usuario", help="e-mail de quem aplica (obrigatório em `aplicar`)")
    cad.add_argument("--ensaio", action="store_true", help="mostra o que mudaria e não grava")
    args = p.parse_args(argv)
    if args.cmd == "cadastro":
        if args.acao == "aplicar" and not args.usuario:
            p.error("`cadastro aplicar` exige --usuario <e-mail>")
        return _cadastro(args)
    senha = getpass.getpass("Senha do administrador: ")
    conn = db.get_conn()
    try:
        db.migrate(conn)
        uid = auth.criar_usuario(conn, args.nome, args.email, senha, "admin")
    finally:
        conn.close()
    print(f"Administrador criado (id={uid}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Implementar a guarda**

Em `backend/app/permissoes.py`, acrescentar `import os` no topo e, ao final do arquivo:

```python
def exigir_cadastro_editavel() -> None:
    """Fecha as rotas de escrita de cadastro quando o cadastro e' versionado (spec 2026-09-21 §8).

    Em producao (`DASH_CADASTRO_VERSIONADO=1`) contrato, aditivo, entidade e tipo de documento
    so' mudam pelos arquivos de `cadastro/`; editar pela tela criaria uma segunda verdade que o
    proximo `cadastro aplicar` desfaria. 409, e nao 403: a pessoa TEM permissao, o recurso e' que
    nao se edita por aqui.
    """
    if os.environ.get("DASH_CADASTRO_VERSIONADO") == "1":
        raise HTTPException(409, "O cadastro é versionado: contratos, aditivos e entidades são "
                                 "alterados pelos arquivos de cadastro, não pela tela.")
```

Em cada rota de escrita abaixo, acrescentar `dependencies=[Depends(exigir_cadastro_editavel)]` ao decorador e importar `exigir_cadastro_editavel` de `app.permissoes` (o `Depends` já está importado nos três arquivos):

- `backend/app/api_contratos.py`: `@router.post("", status_code=201)`, `@router.put("/{contrato_id}")`, `@router.post("/{contrato_id}/estado")`.
- `backend/app/api_aditivos.py`: `@router.post("/api/contratos/{contrato_id}/aditivos", status_code=201)`, `@router.put("/api/aditivos/{aditivo_id}")`, `@router.post("/api/aditivos/{aditivo_id}/assinar")`, `@router.post("/api/aditivos/{aditivo_id}/cancelar")`. A rota `ler-pdf` fica aberta (não grava).
- `backend/app/api_certidoes.py`: `@router.post("/api/entidades", status_code=201)`, `@router.put("/api/entidades/{entidade_id}/coligada-rm")`, `@router.post("/api/entidades/{entidade_id}/desativar")`, `@router.post("/api/certidoes/tipos", status_code=201)`.

Exemplo do resultado em `api_contratos.py`:

```python
@router.post("", status_code=201, dependencies=[Depends(exigir_cadastro_editavel)])
```

- [ ] **Step 5: Rodar e ver passar**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_cli_cadastro.py tests/test_permissoes.py tests/test_api_contratos.py tests/test_api_aditivos.py tests/test_api_certidoes.py -q`
Expected: tudo passa (sem a variável de ambiente as rotas continuam como eram).

- [ ] **Step 6: Produção e runbook**

Em `scripts/rodar_producao.ps1`, junto das outras atribuições de `$env:DASH_...`, acrescentar:

```powershell
# Cadastro versionado (spec 2026-09-21): as rotas de escrita de contrato, aditivo e entidade
# respondem 409; o cadastro entra por `python -m app.cli cadastro aplicar`.
$env:DASH_CADASTRO_VERSIONADO = "1"
```

Em `docs/runbook.md`, acrescentar a seção:

```markdown
## Cadastro versionado

O cadastro de obras mora em `cadastro/` (YAML), é editado pelo Leonardo com o Claude e entra no banco por comando. Não há tela.

1. Editar os arquivos, rodar `cd backend && .venv\Scripts\python -m app.cli cadastro validar`.
2. Commit e merge em `master`; `scripts\deploy.ps1` atualiza o checkout de produção.
3. No checkout de produção (`C:\DashboardLotufo\app\backend`), com `DASH_DB_PATH` apontando para o banco de produção:
   `.venv\Scripts\python -m app.cli cadastro aplicar --usuario <e-mail do admin> --ensaio` e conferir o relatório;
   repetir sem `--ensaio`. O snapshot horário do backup cobre o antes.
4. Instrumento assinado já aplicado não se altera: correção é instrumento novo com `corrige: <chave>`.
```

- [ ] **Step 7: Commit**

```bash
git add backend/app/cli.py backend/app/permissoes.py backend/app/api_contratos.py backend/app/api_aditivos.py backend/app/api_certidoes.py backend/tests/test_cli_cadastro.py backend/tests/test_permissoes.py scripts/rodar_producao.ps1 docs/runbook.md
git commit -m "feat: comando cadastro validar/aplicar e rotas de escrita fechadas em producao"
```

---

### Task 7: O cadastro inicial das 22 obras

**Files:**
- Create: `cadastro/orgaos.yaml`, `cadastro/entidades.yaml`, `cadastro/contratos/<nome-curto>.yaml` (22 arquivos)
- Scratchpad (não versionar): `gerar_cadastro_inicial.py`, `conferir_ensaio.py`

**Interfaces:**
- Consumes: banco de produção SOMENTE LEITURA; `docs/mapeamento-emails-medicao-2026-09-16.md` (órgãos, destinatários, fiscais), `docs/reajuste-pleitos-2026-09-17.md` §7, §9 e §10 (datas-base e índices), `docs/prazos-vigencia-execucao-2026-09-17.md` §4 e §8 (lei, instrumentos e prazos), QDOP de 27/08/2026 (status), `docs/decisoes-reestruturacao-2026-09-16.md` (T5).
- Produces: cadastro que passa em `cadastro validar` e cujo ensaio sobre a cópia de produção dá 22 contratos casados, nenhum criado, e o mesmo valor vigente de antes.

Esta task é de DADOS. O "teste" é a validação, o ensaio e a conferência humana.

- [ ] **Step 1: Gerar o esqueleto a partir da produção**

No scratchpad, `gerar_cadastro_inicial.py`:

```python
"""Esqueleto do cadastro a partir do banco de producao (SOMENTE LEITURA). Roda uma vez."""
import re
import sqlite3
import sys
from pathlib import Path

import yaml

ORIGEM = "file:C:/DashboardLotufo/dados/dashboard.db?mode=ro"
DESTINO = Path(sys.argv[1])          # pasta `cadastro/` do repositorio
con = sqlite3.connect(ORIGEM, uri=True)
con.row_factory = sqlite3.Row


def brl(centavos: int) -> str:
    inteiro, cent = divmod(abs(centavos), 100)
    return ("-" if centavos < 0 else "") + f"{inteiro:,}".replace(",", ".") + f",{cent:02d}"


def chave(texto: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", texto.lower()).strip("-")[:40]


(DESTINO / "contratos").mkdir(parents=True, exist_ok=True)
ents = [{"chave": chave(e["nome"].replace("Consórcio ", "")), "nome": e["nome"], "cnpj": e["cnpj"],
         "papel": e["papel"], "coligada_rm": e["coligada_rm"], "sigla_oficio": None}
        for e in con.execute("SELECT * FROM entidades WHERE ativo=1 ORDER BY id")]
(DESTINO / "entidades.yaml").write_text(yaml.safe_dump(ents, allow_unicode=True, sort_keys=False), "utf-8")
chave_ent = {e["id"]: chave(e["nome"].replace("Consórcio ", ""))
             for e in con.execute("SELECT id, nome FROM entidades")}

for c in con.execute("SELECT * FROM contratos ORDER BY id"):
    nome = c["objeto"]                               # a carga legada pos o apelido da obra em `objeto`
    doc = {"nome_curto": nome, "numero_instrumento": c["numero_instrumento"],
           "orgao": "PREENCHER", "entidade": chave_ent[c["entidade_id"] or 1], "objeto": nome,
           "municipio": None, "lei": None, "cno": None, "art": None,
           "numero_processo": c["numero_processo"], "centro_custo_rm": c["centro_custo_rm"],
           "valor_original": brl(c["valor_original_centavos"]),
           "percentual_lotufo": str(c["percentual_direito_bp"] / 100).replace(".", ","),
           "execucao_inicio": c["execucao_inicio"], "execucao_fim": c["execucao_fim"],
           "vigencia_inicio": c["vigencia_inicio"], "vigencia_fim": c["vigencia_fim"],
           "status": {"ativo": "ativo", "suspenso": "suspenso"}.get(c["estado"], c["estado"]),
           "status_desde": None, "sem_reajuste": False,
           "datas_base": ([{"mes": c["data_base"][:7], "indice": c["indice_reajuste"] or ""}]
                          if c["data_base"] else []),
           "fiscais": [], "destinatarios_extras": [], "instrumentos": []}
    for a in con.execute("SELECT * FROM aditivos WHERE contrato_id=? AND status='assinado' "
                         "ORDER BY data_assinatura, id", (c["id"],)):
        legado = (a["objeto"] or "").startswith("Carga inicial:")
        doc["instrumentos"].append({
            "chave": "carga-legado" if legado else f"ad-{a['id']}",
            "tipo": {"valor": "aditivo_valor", "prazo": "aditivo_prazo"}.get(a["tipo"], "aditivo_misto"),
            "data": a["data_assinatura"], "numero": a["numero"], "objeto": a["objeto"],
            "delta_valor": brl(a["delta_valor_centavos"]),
            "nova_execucao_fim": a["nova_execucao_fim"], "nova_vigencia_fim": a["nova_vigencia_fim"]})
    arquivo = DESTINO / "contratos" / f"{nome.lower().replace(' ', '-')}.yaml"
    arquivo.write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False), "utf-8")
    print(arquivo.name)
```

Run: `backend/.venv/Scripts/python <scratchpad>/gerar_cadastro_inicial.py cadastro`
Expected: 22 nomes de arquivo impressos.

- [ ] **Step 2: Escrever `cadastro/orgaos.yaml`**

Um item por órgão ou superintendência, com os dados do mapeamento de e-mails (§1) e dos prazos (§3). Conteúdo inicial:

```yaml
- chave: mtpar
  nome: MT Participações e Projetos S.A. - MTPAR
  familia: mtpar
  protocolo_para: [protocolo@exemplo.com.br]
  protocolo_copia: [copia@exemplo.com.br]
  pede_devolutiva: true
  separa_reajuste: true
  exige_planilha: false
  folga_vigencia_dias: null        # varia por contrato (78 e 55 dias observados)
  vigencia_automatica: false
  documentos_medicao: [federal, fgts, trabalhista, estadual, municipal]
  documentos_reajuste: [federal, fgts, trabalhista, estadual, municipal]
- chave: sinfra-sagpm
  nome: SINFRA - SAGPM / SUOESP
  familia: sinfra
  protocolo_para: [protocolo@exemplo.com.br]
  protocolo_copia: [copia@exemplo.com.br]
  pede_devolutiva: false
  separa_reajuste: false
  exige_planilha: true
  limite_mb_por_documento: 25
  folga_vigencia_dias: 90
  vigencia_automatica: true
  documentos_medicao: [federal, fgts, trabalhista, estadual, municipal]
  documentos_reajuste: [estadual]
- chave: sinfra-suef1
  nome: SINFRA - SUEF I
  familia: sinfra
  protocolo_para: [protocolo@exemplo.com.br]
  protocolo_assinados_para: [assinados@exemplo.com.br]
  protocolo_copia: [copia@exemplo.com.br]
  pede_devolutiva: false
  separa_reajuste: false
  exige_planilha: true
  limite_mb_por_documento: 25
  folga_vigencia_dias: 90
  vigencia_automatica: true
  documentos_medicao: [federal, fgts, trabalhista, estadual, municipal]
  documentos_reajuste: [estadual]
- chave: sinfra-suef2
  nome: SINFRA - SUEF II
  familia: sinfra
  protocolo_para: [protocolo@exemplo.com.br]
  protocolo_copia: [copia@exemplo.com.br]
  pede_devolutiva: false
  separa_reajuste: false
  exige_planilha: true
  limite_mb_por_documento: 25
  folga_vigencia_dias: 90
  vigencia_automatica: true
  documentos_medicao: [federal, fgts, trabalhista, estadual, municipal]
  documentos_reajuste: [estadual]
- chave: sinfra-supu
  nome: SINFRA - SUPU (Pavimentação Urbana)
  familia: sinfra
  protocolo_para: [protocolo@exemplo.com.br]
  protocolo_copia: [copia@exemplo.com.br]
  pede_devolutiva: false
  separa_reajuste: false
  exige_planilha: true
  limite_mb_por_documento: 25
  folga_vigencia_dias: 90
  vigencia_automatica: true
  documentos_medicao: [federal, fgts, trabalhista, estadual, municipal]
  documentos_reajuste: [estadual]
- chave: sinfra-sacid
  nome: SINFRA - SACID
  familia: sinfra
  protocolo_para: [protocolo@exemplo.com.br]
  protocolo_copia: [copia@exemplo.com.br]
  pede_devolutiva: false
  separa_reajuste: false
  exige_planilha: true
  limite_mb_por_documento: 25
  folga_vigencia_dias: 90
  vigencia_automatica: true
  documentos_medicao: [federal, fgts, trabalhista, estadual, municipal]
  documentos_reajuste: [estadual]
- chave: ses-mt
  nome: SES-MT - Superintendência de Obras, Reformas e Manutenções
  familia: ses
  protocolo_para: [protocolo@exemplo.com.br]
  protocolo_copia: [copia@exemplo.com.br]
  pede_devolutiva: false
  separa_reajuste: true
  exige_planilha: false
  folga_vigencia_dias: 99
  vigencia_automatica: false
  documentos_medicao: [federal, fgts, trabalhista, estadual, municipal]
  documentos_reajuste: [federal, fgts, trabalhista, estadual, municipal]
- chave: pref-cuiaba
  nome: Prefeitura de Cuiabá - Secretaria de Obras Públicas
  familia: prefeitura
  protocolo_para: [protocolo@exemplo.com.br]
  protocolo_copia: [copia@exemplo.com.br]
  pede_devolutiva: false
  separa_reajuste: true
  exige_planilha: false
  folga_vigencia_dias: null        # prazo único: a Prefeitura não separa execução de vigência
  vigencia_automatica: false
  documentos_medicao: [federal, fgts, trabalhista, estadual, municipal]
  documentos_reajuste: [federal, fgts, trabalhista, estadual, municipal]
- chave: pref-vg
  nome: Prefeitura de Várzea Grande - Secretaria Municipal de Saúde
  familia: prefeitura
  protocolo_para: [protocolo@exemplo.com.br]
  protocolo_copia: [copia@exemplo.com.br]
  pede_devolutiva: false
  separa_reajuste: true
  exige_planilha: false
  folga_vigencia_dias: null
  vigencia_automatica: false
  documentos_medicao: [federal, fgts, trabalhista, estadual, municipal]
  documentos_reajuste: [federal, fgts, trabalhista, estadual, municipal]
- chave: rota-do-oeste
  nome: Concessionária Rota do Oeste S.A. (privado)
  familia: prefeitura               # família provisória: contrato privado, protocolo fora da caixa mapeada
  protocolo_para: []
  protocolo_copia: []
  pede_devolutiva: false
  separa_reajuste: true
  exige_planilha: false
  folga_vigencia_dias: null
  vigencia_automatica: false
  documentos_medicao: []
  documentos_reajuste: []
```

- [ ] **Step 3: Completar `entidades.yaml`**

Preencher `sigla_oficio` (`LT` na Lotufo, `CCL` no Complexo Leblon, `CO` no Oriundi; as demais ficam `null` até aparecer um ofício real) e acrescentar as consorciadas com certidão em uso (Rivoli, Guaxe, Encomind) com `papel: consorciada`, `coligada_rm: null` e o CNPJ copiado de `~/dev/lotufo-dashboard/js/data/certidoes-empresas.js`. Conferir cada CNPJ com `cadastro validar` (o DV é checado).

- [ ] **Step 4: Completar os 22 contratos**

Para cada `cadastro/contratos/*.yaml`, preencher a partir dos levantamentos, sem inventar: campo sem evidência fica `null`.

| Campo | De onde vem |
|---|---|
| `orgao` | tabela de superintendências do mapeamento de e-mails §1.B; MTPAR, SES, prefeituras |
| `nome_curto` e nome do arquivo | nome curto aprovado na padronização de nomes (T2.1): `MT-402`, `MT-388`, `Integra BRT`, `Leblon`, `Complexo Cultural`... O arquivo é o nome em minúsculas com hífens |
| `lei` | prazos §4: 8.666 em 074/2021, 161/2022, 014/2023, 102/2022, 128/2022; 14.133 nos de 2024 em diante; 13.303 na MTPAR |
| `municipio`, `objeto` | QDOP, colunas Localidade e Descrição da Obra |
| `status` e `status_desde` | QDOP: EM ANDAMENTO → `ativo`; PARALISADA → `suspenso` (Coxipó 2ª, `status_desde: 2025-10-01`); CONCLUÍDA → `em_encerramento` (Alta Floresta `status_desde: 2026-07-17`, data do CT/232; Orla `status_desde: 2026-07-31`, data do CT/245) |
| `datas_base` | reajuste §7, §9 e §10. 5 Bairros tem duas: `2022-01` (SINAPI) e `2022-03` (SICRO) |
| `fiscais` | mapeamento de e-mails §1 (fiscal nominal por obra), com `desde` = data do primeiro e-mail em que aparece |
| `destinatarios_extras` | supervisoras: Tokio Marine e o engenheiro da supervisão na MT-388; Ecoplan na MT-402 e no Oriundi; a supervisora na Região Oeste |
| `instrumentos` | manter a entrada `carga-legado` gerada; acrescentar, com chave `ta-NN` ou `ap-NN`, os instrumentos posteriores a 04/08/2026 lidos em prazos §5 e §8 e em reajuste §10 (ex.: 5 Bairros já tem o 8º TA de 07/07/2026 dentro da base; MT-402 ganha `ap-10` de 26/08/2026 só quando as datas do apostilamento forem lidas no Diário Oficial) |

As datas de execução e vigência do arquivo são as que estão no banco; só mudam por instrumento.

- [ ] **Step 5: Validar**

Run: `cd backend && .venv/Scripts/python -m app.cli cadastro validar`
Expected: `Cadastro válido: 10 órgão(s), 9 entidade(s), 22 contratos.` Os avisos esperados são os do QDOP já conhecidos (Estações BRT e Terminais BRT com vigência antes da execução).

- [ ] **Step 6: Ensaio sobre uma cópia da produção**

No scratchpad, `conferir_ensaio.py`:

```python
"""Copia o banco de producao, aplica o cadastro na COPIA e compara o vigente antes e depois."""
import os
import shutil
import sqlite3
import sys
from pathlib import Path

copia = Path(sys.argv[1]) / "ensaio.db"
origem = sqlite3.connect("file:C:/DashboardLotufo/dados/dashboard.db?mode=ro", uri=True)
destino = sqlite3.connect(copia)
origem.backup(destino); destino.close(); origem.close()
os.environ["DASH_DB_PATH"] = str(copia)

from app import cadastro_aplicar, cadastro_arquivos, contratos, db   # noqa: E402

conn = db.get_conn(); db.migrate(conn)
antes = {r["numero_instrumento"]: contratos.vigente(conn, r["id"]) for r in conn.execute("SELECT id, numero_instrumento FROM contratos")}
cad = cadastro_arquivos.preparar(Path(sys.argv[2]))
admin = conn.execute("SELECT id FROM usuarios WHERE perfil='admin' AND ativo=1 ORDER BY id").fetchone()["id"]
rel = cadastro_aplicar.aplicar(conn, admin, cad)
print("criados:", rel["contratos"]["criados"])
for r in conn.execute("SELECT id, numero_instrumento, nome_curto FROM contratos"):
    d, a = contratos.vigente(conn, r["id"]), antes.get(r["numero_instrumento"])
    for campo in ("valor_vigente_centavos", "execucao_fim_vigente", "vigencia_fim_vigente"):
        if a is None or a[campo] != d[campo]:
            print(f"DIFERENTE {r['nome_curto']}: {campo}: {a and a[campo]} -> {d[campo]}")
print("total de contratos:", conn.execute("SELECT COUNT(*) FROM contratos").fetchone()[0])
```

Run: `cd backend && .venv/Scripts/python <scratchpad>/conferir_ensaio.py <scratchpad> ../cadastro`
Expected: `criados: []`, `total de contratos: 22`, e só aparecem linhas `DIFERENTE` para os contratos em que um instrumento novo foi acrescentado de propósito no Step 4. Qualquer outra diferença é erro do cadastro: corrigir o YAML e repetir.

- [ ] **Step 7: Conferência do Leonardo**

Gerar para ele uma tabela (obra, órgão, lei, valor vigente, execução, vigência, status, datas-base, fiscal) a partir do ensaio e pedir OK obra a obra. Registrar as correções pedidas nos YAML e repetir os Steps 5 e 6.

- [ ] **Step 8: Commit**

```bash
git add cadastro/
git commit -m "feat: cadastro inicial versionado das 22 obras do QDOP"
```

---

### Task 8: Conta Microsoft por usuário e registro de envio

**Files:**
- Create: `backend/migrations/019_envios.sql`, `backend/app/correio.py`
- Modify: `backend/app/graph.py` (escopos parametrizáveis)
- Test: `backend/tests/test_correio.py`

**Interfaces:**
- Consumes: `graph.Token`, `graph.iniciar_device_code`, `graph.concluir_device_code`, `graph.ErroGraph`, `graph._post_form`.
- Produces:
  - `correio.ESCOPOS = "offline_access User.Read Mail.Send Mail.ReadWrite"`
  - `correio.configuracao() -> dict` com `tenant`, `client_id`, `tokens_dir`, `simulador`
  - `correio.arquivo_token(usuario_id: int) -> Path`
  - `correio.conectado(usuario_id: int) -> bool`
  - `correio.registrar_envio(conn, usuario_id, tipo, remetente, para, copia, assunto, mensagem_id, anexos) -> int`, com `anexos: list[tuple[str, bytes]]`
  - `graph.iniciar_device_code(tenant, client_id, escopos=ESCOPOS)` e `graph.Token(tenant, client_id, arquivo, escopos=ESCOPOS)`

- [ ] **Step 1: Escrever os testes que falham**

`backend/tests/test_correio.py`:

```python
import hashlib
import json

import pytest
from app import auth, correio, db, graph


@pytest.fixture
def conn(tmp_path, monkeypatch):
    monkeypatch.setenv("DASH_DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setenv("DASH_GRAPH_TOKENS_DIR", str(tmp_path / "tokens"))
    monkeypatch.setenv("DASH_GRAPH_CLIENT_ID", "cliente-teste")
    c = db.get_conn(); db.migrate(c)
    auth.criar_usuario(c, "Ana", "ana@lotufo.com", "senha-forte-123", "engenharia")
    yield c
    c.close()


def test_token_e_um_arquivo_por_usuario(conn, tmp_path):
    assert correio.arquivo_token(1) == tmp_path / "tokens" / "usuario-1.txt"
    assert correio.conectado(1) is False
    graph.gravar_token(correio.arquivo_token(1), "refresh-da-ana")
    assert correio.conectado(1) is True and correio.conectado(2) is False


def test_escopos_de_envio_nao_pedem_leitura_de_caixa_alheia():
    assert "Mail.Send" in correio.ESCOPOS and "Mail.ReadWrite" in correio.ESCOPOS
    assert "Mail.Read.Shared" not in correio.ESCOPOS and "Sites.Read.All" not in correio.ESCOPOS


def test_device_code_usa_os_escopos_pedidos(monkeypatch):
    visto = {}
    monkeypatch.setattr(graph, "_post_form", lambda url, campos, timeout=60: visto.update(campos) or {
        "device_code": "d", "user_code": "ABCD", "verification_uri": "https://microsoft.com/devicelogin"})
    graph.iniciar_device_code("organizations", "cliente", escopos=correio.ESCOPOS)
    assert visto["scope"] == correio.ESCOPOS


def test_registrar_envio_grava_anexos_com_hash_e_audita(conn):
    eid = correio.registrar_envio(conn, 1, "teste", "ana@lotufo.com", ["fab@lotufo.com"], ["leo@lotufo.com"],
                                  "Emissão NF - 27ª Medição", "<id@outlook>", [("espelho.docx", b"abc")])
    e = conn.execute("SELECT * FROM envios WHERE id=?", (eid,)).fetchone()
    assert (e["tipo"], e["remetente"], json.loads(e["para"]), json.loads(e["copia"])) == (
        "teste", "ana@lotufo.com", ["fab@lotufo.com"], ["leo@lotufo.com"])
    a = conn.execute("SELECT nome, tamanho, sha256 FROM envio_anexos WHERE envio_id=?", (eid,)).fetchone()
    assert (a["nome"], a["tamanho"], a["sha256"]) == ("espelho.docx", 3, hashlib.sha256(b"abc").hexdigest())
    assert conn.execute("SELECT COUNT(*) FROM audit_log WHERE acao='correio.envio'").fetchone()[0] == 1
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_correio.py -q`
Expected: FAIL com `ImportError: cannot import name 'correio'`.

- [ ] **Step 3: Migração 019**

`backend/migrations/019_envios.sql`:

```sql
-- E-mails enviados pelo sistema (spec 2026-09-21 §5.1). So' entra aqui o que o Graph ACEITOU:
-- falha de envio nao deixa linha nem muda estado de nada. Append-only.
CREATE TABLE IF NOT EXISTS envios (
    id INTEGER PRIMARY KEY,
    tipo TEXT NOT NULL,
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id),
    remetente TEXT NOT NULL,
    para TEXT NOT NULL,
    copia TEXT NOT NULL,
    assunto TEXT NOT NULL,
    mensagem_id TEXT,
    enviado_em TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS envio_anexos (
    id INTEGER PRIMARY KEY,
    envio_id INTEGER NOT NULL REFERENCES envios(id),
    nome TEXT NOT NULL,
    tamanho INTEGER NOT NULL,
    sha256 TEXT NOT NULL
);
```

- [ ] **Step 4: Escopos parametrizáveis em `graph.py`**

Em `backend/app/graph.py`:

```python
def iniciar_device_code(tenant: str, client_id: str, escopos: str = ESCOPOS) -> dict:
```

e dentro dela trocar `"scope": ESCOPOS` por `"scope": escopos`. Na classe `Token`:

```python
    def __init__(self, tenant: str, client_id: str, arquivo: Path, escopos: str = ESCOPOS):
        self.tenant, self.client_id, self.arquivo, self.escopos = tenant, client_id, arquivo, escopos
```

e em `acesso()` trocar `"scope": ESCOPOS` por `"scope": self.escopos`. Nenhum chamador existente muda.

- [ ] **Step 5: Implementar a base do correio**

`backend/app/correio.py`:

```python
"""Envio de e-mail pelo Microsoft Graph, pela conta de QUEM ENVIA (spec 2026-09-21 §5.1).

Cada pessoa conecta a propria conta uma vez (codigo de dispositivo). O refresh token fica num
arquivo por usuario na pasta de segredos (`DASH_GRAPH_TOKENS_DIR`), fora do repositorio e do
banco. O sistema NAO le caixa de e-mail: `Mail.ReadWrite` e' o que o Graph exige para criar o
rascunho e subir anexo acima de 3 MB; nenhuma funcao deste modulo lista ou le mensagem.
"""
import hashlib
import json
import os
from pathlib import Path

from app import auditoria, db

ESCOPOS = "offline_access User.Read Mail.Send Mail.ReadWrite"


def configuracao() -> dict:
    return {"tenant": os.environ.get("DASH_GRAPH_TENANT") or "organizations",
            "client_id": os.environ.get("DASH_GRAPH_CLIENT_ID"),
            "tokens_dir": os.environ.get("DASH_GRAPH_TOKENS_DIR"),
            "simulador": os.environ.get("DASH_GRAPH_SIMULADOR")}


def arquivo_token(usuario_id: int) -> Path:
    pasta = configuracao()["tokens_dir"]
    if not pasta:
        raise RuntimeError("DASH_GRAPH_TOKENS_DIR não definida: sem pasta para as contas Microsoft")
    return Path(pasta) / f"usuario-{int(usuario_id)}.txt"


def conectado(usuario_id: int) -> bool:
    try:
        return bool(arquivo_token(usuario_id).read_text(encoding="utf-8").strip())
    except (OSError, RuntimeError):
        return False


def registrar_envio(conn, usuario_id: int, tipo: str, remetente: str, para: list[str],
                    copia: list[str], assunto: str, mensagem_id: str | None,
                    anexos: list[tuple[str, bytes]]) -> int:
    with db.mutacao(conn):
        cur = conn.execute(
            "INSERT INTO envios (tipo, usuario_id, remetente, para, copia, assunto, mensagem_id) "
            "VALUES (?,?,?,?,?,?,?)",
            (tipo, usuario_id, remetente, json.dumps(para), json.dumps(copia), assunto, mensagem_id))
        eid = cur.lastrowid
        resumo = []
        for nome, dados in anexos:
            h = hashlib.sha256(dados).hexdigest()
            conn.execute("INSERT INTO envio_anexos (envio_id, nome, tamanho, sha256) VALUES (?,?,?,?)",
                         (eid, nome, len(dados), h))
            resumo.append({"nome": nome, "tamanho": len(dados), "sha256": h})
        auditoria.registrar(conn, usuario_id, "correio.envio", "envio", eid, None,
                            {"tipo": tipo, "remetente": remetente, "para": para, "copia": copia,
                             "assunto": assunto, "mensagem_id": mensagem_id, "anexos": resumo})
    return eid
```

- [ ] **Step 6: Rodar e ver passar**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_correio.py tests/test_graph.py -q`
Expected: tudo passa.

- [ ] **Step 7: Commit**

```bash
git add backend/migrations/019_envios.sql backend/app/correio.py backend/app/graph.py backend/tests/test_correio.py
git commit -m "feat: conta Microsoft por usuario e registro imutavel de envio"
```

---

### Task 9: Enviar com anexos (rascunho, sessão de upload, envio) e simulador

**Files:**
- Modify: `backend/app/correio.py`
- Test: `backend/tests/test_correio.py` (acrescenta)

**Interfaces:**
- Consumes: Task 8.
- Produces:
  - `correio.MAX_TOTAL = 34 * 1024 * 1024`, `correio.LIMITE_SIMPLES = 3 * 1024 * 1024`, `correio.BLOCO = 3_276_800`
  - `correio.cliente(usuario_id: int)` devolve objeto com `remetente() -> str` e `enviar(para, copia, assunto, corpo_html, anexos) -> str | None` (identificador da mensagem). Com `DASH_GRAPH_SIMULADOR` definido devolve o simulador, que grava `enviados/<n>.json` na pasta.
  - `correio.enviar_e_registrar(conn, usuario: dict, tipo, para, copia, assunto, corpo_html, anexos) -> int` (id do envio). Levanta `graph.ErroGraph` e não grava nada se o envio falhar.

- [ ] **Step 1: Escrever os testes que falham**

Acrescentar a `backend/tests/test_correio.py`:

```python
class _Falso:
    """Fica no lugar de correio._http e grava as chamadas na ordem."""
    def __init__(self, falhar_em=None):
        self.chamadas, self.falhar_em = [], falhar_em

    def __call__(self, metodo, url, corpo=None, headers=None, bearer=None):
        self.chamadas.append((metodo, url.replace(graph.GRAPH, ""), len(corpo or b""), bool(bearer),
                              (headers or {}).get("Content-Range")))
        if self.falhar_em and self.falhar_em in url:
            raise graph.ErroGraph("Graph respondeu HTTP 500")
        if url.endswith("/me"):
            return {"mail": "ana@lotufo.com"}
        if url.endswith("/me/messages"):
            return {"id": "RASCUNHO", "internetMessageId": "<abc@outlook>"}
        if url.endswith("/createUploadSession"):
            return {"uploadUrl": "https://outlook.office.com/upload/sessao"}
        return {}


@pytest.fixture
def rede(conn, monkeypatch):
    graph.gravar_token(correio.arquivo_token(1), "refresh")
    monkeypatch.setattr(graph.Token, "acesso", lambda self: "TOKEN")
    falso = _Falso()
    monkeypatch.setattr(correio, "_http", falso)
    return falso


def test_anexo_pequeno_vai_direto_e_grande_vai_por_sessao_em_blocos(conn, rede):
    grande = b"x" * (correio.BLOCO * 2 + 10)
    mid = correio.cliente(1).enviar(["fab@lotufo.com"], ["leo@lotufo.com"], "Assunto", "<p>oi</p>",
                                    [("pequeno.docx", b"abc"), ("pacote.pdf", grande)])
    assert mid == "<abc@outlook>"
    caminhos = [(m, u) for m, u, *_ in rede.chamadas]
    assert caminhos == [("POST", "/me/messages"), ("POST", "/me/messages/RASCUNHO/attachments"),
                        ("POST", "/me/messages/RASCUNHO/attachments/createUploadSession"),
                        ("PUT", "https://outlook.office.com/upload/sessao"),
                        ("PUT", "https://outlook.office.com/upload/sessao"),
                        ("PUT", "https://outlook.office.com/upload/sessao"),
                        ("POST", "/me/messages/RASCUNHO/send")]
    blocos = [c for c in rede.chamadas if c[0] == "PUT"]
    assert [b[4] for b in blocos] == [f"bytes 0-{correio.BLOCO - 1}/{len(grande)}",
                                      f"bytes {correio.BLOCO}-{correio.BLOCO * 2 - 1}/{len(grande)}",
                                      f"bytes {correio.BLOCO * 2}-{len(grande) - 1}/{len(grande)}"]
    assert all(b[3] is False for b in blocos)        # a URL de upload ja' e' autenticada: sem bearer


def test_pacote_acima_do_teto_e_recusado_antes_de_tocar_a_rede(conn, rede):
    with pytest.raises(graph.ErroGraph, match="MB"):
        correio.cliente(1).enviar(["a@lotufo.com"], [], "A", "<p/>", [("g.pdf", b"x" * (correio.MAX_TOTAL + 1))])
    assert rede.chamadas == []


def test_falha_no_envio_apaga_o_rascunho_e_nao_registra(conn, monkeypatch):
    graph.gravar_token(correio.arquivo_token(1), "refresh")
    monkeypatch.setattr(graph.Token, "acesso", lambda self: "TOKEN")
    falso = _Falso(falhar_em="/send")
    monkeypatch.setattr(correio, "_http", falso)
    with pytest.raises(graph.ErroGraph):
        correio.enviar_e_registrar(conn, {"id": 1}, "teste", ["a@lotufo.com"], [], "A", "<p/>", [])
    assert ("DELETE", "/me/messages/RASCUNHO") in [(m, u) for m, u, *_ in falso.chamadas]
    assert conn.execute("SELECT COUNT(*) FROM envios").fetchone()[0] == 0


def test_enviar_e_registrar_grava_remetente_e_mensagem(conn, rede):
    eid = correio.enviar_e_registrar(conn, {"id": 1}, "teste", ["a@lotufo.com"], [], "Assunto", "<p/>",
                                     [("a.txt", b"oi")])
    e = conn.execute("SELECT remetente, mensagem_id FROM envios WHERE id=?", (eid,)).fetchone()
    assert (e["remetente"], e["mensagem_id"]) == ("ana@lotufo.com", "<abc@outlook>")


def test_simulador_grava_em_pasta_e_nao_usa_rede(conn, tmp_path, monkeypatch):
    monkeypatch.setenv("DASH_GRAPH_SIMULADOR", str(tmp_path / "sim"))
    monkeypatch.setattr(correio, "_http", lambda *a, **k: pytest.fail("rede usada no simulador"))
    correio.enviar_e_registrar(conn, {"id": 1, "email": "ana@lotufo.com"}, "teste", ["a@lotufo.com"], [], "Assunto",
                               "<p/>", [("a.txt", b"oi")])
    gravado = json.loads((tmp_path / "sim" / "enviados" / "1.json").read_text("utf-8"))
    assert gravado["assunto"] == "Assunto" and gravado["anexos"][0]["nome"] == "a.txt"
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_correio.py -q`
Expected: os 5 novos falham com `AttributeError: module 'app.correio' has no attribute 'cliente'`.

- [ ] **Step 3: Implementar**

Acrescentar a `backend/app/correio.py` os imports `base64`, `logging`, `urllib.error`, `urllib.request` e `from app import graph`, e o código:

```python
log = logging.getLogger("app.correio")

LIMITE_SIMPLES = 3 * 1024 * 1024       # acima disto o Graph exige sessao de upload
BLOCO = 3_276_800                      # multiplo de 320 KiB, como o Graph pede
MAX_TOTAL = 34 * 1024 * 1024           # o Exchange Online recusa mensagem acima de ~35 MB
_UPLOAD_HOSTS = ("https://outlook.office.com/", "https://outlook.office365.com/")


def _http(metodo: str, url: str, corpo: bytes | None = None, headers: dict | None = None,
          bearer: str | None = None) -> dict:
    """Uma requisicao. O bearer so' vai ao host do Graph; a URL de upload ja' e' autenticada."""
    if bearer is not None and not url.startswith(graph.GRAPH + "/"):
        raise graph.ErroGraph("URL fora do Microsoft Graph recusada")
    if bearer is None and not url.startswith(_UPLOAD_HOSTS):
        raise graph.ErroGraph("URL de upload fora do Outlook recusada")
    h = {"Accept": "application/json", **(headers or {})}
    if bearer is not None:
        h["Authorization"] = "Bearer " + bearer
    req = urllib.request.Request(url, data=corpo, headers=h, method=metodo)
    try:
        with urllib.request.urlopen(req, timeout=graph.TIMEOUT) as r:
            bruto = r.read()
    except urllib.error.HTTPError as e:
        raise graph.ErroGraph(f"Graph respondeu HTTP {e.code} ao enviar o e-mail") from None
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise graph.ErroGraph(f"Graph inacessível ({e.__class__.__name__})") from None
    return json.loads(bruto.decode("utf-8")) if bruto.strip() else {}


def _enderecos(lista: list[str]) -> list[dict]:
    return [{"emailAddress": {"address": e}} for e in lista]


def _conferir_tamanho(anexos: list[tuple[str, bytes]]) -> None:
    total = sum(len(d) for _, d in anexos)
    if total > MAX_TOTAL:
        raise graph.ErroGraph(f"Anexos somam {total // 1024 // 1024} MB; o limite do e-mail é "
                              f"{MAX_TOTAL // 1024 // 1024} MB. Divida o envio.")


class ClienteCorreio:
    def __init__(self, token: graph.Token):
        self.token = token

    def _json(self, metodo: str, caminho: str, corpo: dict | None = None) -> dict:
        dados = None if corpo is None else json.dumps(corpo).encode("utf-8")
        return _http(metodo, graph.GRAPH + caminho, dados, {"Content-Type": "application/json"},
                     bearer=self.token.acesso())

    def remetente(self) -> str:
        eu = self._json("GET", "/me")
        return (eu.get("mail") or eu.get("userPrincipalName") or "").lower()

    def enviar(self, para, copia, assunto, corpo_html, anexos) -> str | None:
        _conferir_tamanho(anexos)
        rascunho = self._json("POST", "/me/messages", {
            "subject": assunto, "body": {"contentType": "HTML", "content": corpo_html},
            "toRecipients": _enderecos(para), "ccRecipients": _enderecos(copia)})
        mid = rascunho["id"]
        try:
            for nome, dados in anexos:
                if len(dados) <= LIMITE_SIMPLES:
                    self._json("POST", f"/me/messages/{mid}/attachments", {
                        "@odata.type": "#microsoft.graph.fileAttachment", "name": nome,
                        "contentBytes": base64.b64encode(dados).decode("ascii")})
                    continue
                sessao = self._json("POST", f"/me/messages/{mid}/attachments/createUploadSession", {
                    "AttachmentItem": {"attachmentType": "file", "name": nome, "size": len(dados)}})
                for inicio in range(0, len(dados), BLOCO):
                    bloco = dados[inicio:inicio + BLOCO]
                    _http("PUT", sessao["uploadUrl"], bloco, {
                        "Content-Type": "application/octet-stream",
                        "Content-Range": f"bytes {inicio}-{inicio + len(bloco) - 1}/{len(dados)}"})
            self._json("POST", f"/me/messages/{mid}/send")
        except graph.ErroGraph:
            try:
                self._json("DELETE", f"/me/messages/{mid}")
            except graph.ErroGraph:
                log.warning("rascunho %s ficou na caixa apos falha de envio", mid)
            raise
        return rascunho.get("internetMessageId")


class CorreioSimulado:
    """`DASH_GRAPH_SIMULADOR=<pasta>`: grava o que seria enviado, para dev e testes de API."""

    def __init__(self, pasta: Path, remetente: str):
        self.pasta, self._remetente = pasta / "enviados", remetente

    def remetente(self) -> str:
        return self._remetente

    def enviar(self, para, copia, assunto, corpo_html, anexos) -> str:
        _conferir_tamanho(anexos)
        self.pasta.mkdir(parents=True, exist_ok=True)
        n = len(list(self.pasta.glob("*.json"))) + 1
        (self.pasta / f"{n}.json").write_text(json.dumps({
            "remetente": self._remetente, "para": para, "copia": copia, "assunto": assunto,
            "corpo": corpo_html,
            "anexos": [{"nome": nome, "tamanho": len(d), "sha256": hashlib.sha256(d).hexdigest()}
                       for nome, d in anexos]}, ensure_ascii=False, indent=1), encoding="utf-8")
        return f"<simulado-{n}@dashboard>"


def cliente(usuario_id: int, email_usuario: str = ""):
    cfg = configuracao()
    if cfg["simulador"]:
        return CorreioSimulado(Path(cfg["simulador"]), email_usuario or f"usuario-{usuario_id}@simulador")
    if not cfg["client_id"]:
        raise graph.ErroGraph("Microsoft 365 não configurado neste servidor (DASH_GRAPH_CLIENT_ID)")
    if not conectado(usuario_id):
        raise graph.ErroGraph("Sua conta Microsoft não está conectada: conecte em Minha conta")
    return ClienteCorreio(graph.Token(cfg["tenant"], cfg["client_id"], arquivo_token(usuario_id), ESCOPOS))


def enviar_e_registrar(conn, usuario: dict, tipo: str, para: list[str], copia: list[str], assunto: str,
                       corpo_html: str, anexos: list[tuple[str, bytes]]) -> int:
    """Envia e SO' ENTAO registra: falha de envio nao deixa rastro de envio."""
    c = cliente(usuario["id"], usuario.get("email", ""))
    remetente = c.remetente()
    mensagem_id = c.enviar(para, copia, assunto, corpo_html, anexos)
    try:
        return registrar_envio(conn, usuario["id"], tipo, remetente, para, copia, assunto, mensagem_id, anexos)
    except Exception:
        log.critical("E-mail ENVIADO e nao registrado: %s para %s (%s)", assunto, para, mensagem_id)
        raise
```

- [ ] **Step 4: Rodar e ver passar**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_correio.py -q`
Expected: `9 passed`.

- [ ] **Step 5: Commit**

```bash
git add backend/app/correio.py backend/tests/test_correio.py
git commit -m "feat: envio de e-mail com anexos pelo Graph - rascunho, sessao de upload e simulador"
```

---

### Task 10: "Minha conta": conectar a conta Microsoft e mandar um e-mail de teste

**Files:**
- Create: `backend/app/api_correio.py`, `frontend/src/MinhaConta.tsx`, `frontend/src/MinhaConta.test.tsx`
- Modify: `backend/app/main.py`, `frontend/src/rota.tsx`, `frontend/src/App.tsx`, `scripts/rodar_producao.ps1`, `docs/runbook.md`
- Test: `backend/tests/test_api_correio.py`

**Interfaces:**
- Consumes: `correio.*` (Tasks 8 e 9), `permissoes.exigir("editar_cadastros")` (o perfil de operação).
- Produces: `GET /api/correio/status` → `{configurado, conectado, login: {estado, user_code, verification_uri}}`; `POST /api/correio/conectar` → o mesmo objeto com o código; `POST /api/correio/teste` → `{envio_id, remetente}`. Rota de tela `/conta`.

- [ ] **Step 1: Escrever os testes que falham (backend)**

`backend/tests/test_api_correio.py`:

```python
import pytest
from app import api_correio, correio, graph


class _ThreadParada:
    """No lugar de threading.Thread: o acompanhamento do login nao roda no teste (ele dormiria
    5 s e acordaria DEPOIS do teste, ja' sem o monkeypatch, batendo na rede de verdade)."""
    def __init__(self, **_):
        pass

    def start(self):
        pass


@pytest.fixture(autouse=True)
def _ambiente(tmp_path, monkeypatch):
    monkeypatch.setenv("DASH_GRAPH_TOKENS_DIR", str(tmp_path / "tokens"))
    monkeypatch.setenv("DASH_GRAPH_CLIENT_ID", "cliente-teste")
    monkeypatch.setattr(api_correio.threading, "Thread", _ThreadParada)
    api_correio._LOGINS.clear()          # estado de login e' global do processo: zera entre testes
    yield
    api_correio._LOGINS.clear()


def test_status_de_quem_nunca_conectou(client_admin):
    r = client_admin.get("/api/correio/status").json()
    assert r["configurado"] is True and r["conectado"] is False and r["login"]["estado"] == "nenhum"


def test_conectar_devolve_o_codigo_so_para_quem_pediu(client_admin, monkeypatch):
    monkeypatch.setattr(graph, "iniciar_device_code", lambda tenant, cid, escopos: {
        "device_code": "d", "user_code": "ABCD-1234", "verification_uri": "https://microsoft.com/devicelogin",
        "expires_in": 900, "interval": 5, "message": ""})
    r = client_admin.post("/api/correio/conectar").json()
    assert r["login"]["user_code"] == "ABCD-1234" and r["login"]["estado"] == "aguardando"


def test_teste_envia_para_a_propria_pessoa_e_registra(client_admin, tmp_path, monkeypatch):
    monkeypatch.setenv("DASH_GRAPH_SIMULADOR", str(tmp_path / "sim"))
    r = client_admin.post("/api/correio/teste")
    assert r.status_code == 200, r.text
    assert r.json()["remetente"] == "admin@lotufo.com"
    assert (tmp_path / "sim" / "enviados" / "1.json").exists()


def test_teste_sem_conta_conectada_explica_o_que_fazer(client_admin):
    r = client_admin.post("/api/correio/teste")
    assert r.status_code == 422 and "Minha conta" in r.json()["detail"]
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_api_correio.py -q`
Expected: FAIL com 404 nas três rotas.

- [ ] **Step 3: Implementar a API**

`backend/app/api_correio.py`:

```python
"""Conta Microsoft de cada usuario: conectar, ver o estado e mandar um e-mail de teste."""
import sqlite3
import threading
import time

from fastapi import APIRouter, Depends, HTTPException

from app import correio, graph
from app.api_auth import conexao
from app.permissoes import exigir

router = APIRouter(prefix="/api/correio")

# Estado do login por codigo de dispositivo, POR USUARIO, em memoria do processo (reiniciar o
# servidor no meio cancela o login; a pessoa pede outro codigo).
_LOGINS: dict[int, dict] = {}
_LOCK = threading.Lock()
_NENHUM = {"estado": "nenhum", "user_code": None, "verification_uri": None}


def _status(usuario_id: int) -> dict:
    cfg = correio.configuracao()
    with _LOCK:
        login = dict(_LOGINS.get(usuario_id, _NENHUM))
    return {"configurado": bool(cfg["client_id"] and cfg["tokens_dir"]) or bool(cfg["simulador"]),
            "conectado": correio.conectado(usuario_id), "login": login}


@router.get("/status")
def status(usuario: dict = Depends(exigir("editar_cadastros", com_csrf=False))):
    return _status(usuario["id"])


def _acompanhar(usuario_id: int, cfg: dict, device_code: str, intervalo: int, expira: float) -> None:
    while time.time() < expira:
        time.sleep(intervalo)
        try:
            r = graph.concluir_device_code(cfg["tenant"], cfg["client_id"], device_code,
                                           correio.arquivo_token(usuario_id))
        except graph.ErroGraph as e:
            with _LOCK:
                _LOGINS[usuario_id] = {"estado": "erro", "erro": str(e), "user_code": None,
                                       "verification_uri": None}
            return
        if r != "pendente":
            with _LOCK:
                _LOGINS[usuario_id] = {"estado": r, "user_code": None, "verification_uri": None}
            return
    with _LOCK:
        _LOGINS[usuario_id] = {"estado": "expirado", "user_code": None, "verification_uri": None}


@router.post("/conectar")
def conectar(usuario: dict = Depends(exigir("editar_cadastros"))):
    cfg = correio.configuracao()
    if not (cfg["client_id"] and cfg["tokens_dir"]):
        raise HTTPException(422, "Microsoft 365 não configurado neste servidor "
                                 "(DASH_GRAPH_CLIENT_ID / DASH_GRAPH_TOKENS_DIR) — ver docs/runbook.md")
    uid = usuario["id"]
    with _LOCK:
        if _LOGINS.get(uid, {}).get("estado") == "aguardando":
            return _status(uid)
    try:
        d = graph.iniciar_device_code(cfg["tenant"], cfg["client_id"], correio.ESCOPOS)
    except graph.ErroGraph as e:
        raise HTTPException(502, str(e)) from None
    with _LOCK:
        _LOGINS[uid] = {"estado": "aguardando", "user_code": d["user_code"],
                        "verification_uri": d["verification_uri"]}
    threading.Thread(target=_acompanhar, daemon=True,
                     args=(uid, cfg, d["device_code"], d["interval"], time.time() + d["expires_in"])).start()
    return _status(uid)


@router.post("/teste")
def teste(usuario: dict = Depends(exigir("editar_cadastros")),
          conn: sqlite3.Connection = Depends(conexao)):
    c_usuario = {"id": usuario["id"], "email": usuario["email"]}
    try:
        destino = correio.cliente(usuario["id"], usuario["email"]).remetente()
        eid = correio.enviar_e_registrar(
            conn, c_usuario, "teste", [destino], [], "Dashboard Lotufo — teste de envio",
            "<p>Este e-mail confirma que a Dashboard Lotufo consegue enviar pela sua conta.</p>",
            [("teste.txt", "Anexo de teste da Dashboard Lotufo.\n".encode("utf-8"))])
    except graph.ErroGraph as e:
        raise HTTPException(422, str(e)) from None
    return {"envio_id": eid, "remetente": destino}
```

Em `backend/app/main.py`, junto dos outros routers:

```python
    from app.api_correio import router as correio_router
    app.include_router(correio_router)
```

- [ ] **Step 4: Rodar e ver passar (backend)**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_api_correio.py -q`
Expected: `4 passed`.

- [ ] **Step 5: Escrever o teste que falha (frontend)**

`frontend/src/MinhaConta.test.tsx`:

```tsx
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import MinhaConta from "./MinhaConta";

// vi.mock e' icado para o topo do arquivo: a funcao falsa precisa nascer em vi.hoisted para
// existir quando a fabrica do mock rodar.
const { api } = vi.hoisted(() => ({ api: vi.fn() }));
vi.mock("./api", () => ({ api }));

const NENHUM = { estado: "nenhum", user_code: null, verification_uri: null };

describe("MinhaConta", () => {
  afterEach(() => { cleanup(); api.mockReset(); });

  it("mostra que a conta não está conectada e, ao conectar, o código para digitar", async () => {
    api.mockResolvedValueOnce({ configurado: true, conectado: false, login: NENHUM });
    api.mockResolvedValueOnce({ configurado: true, conectado: false, login: {
      estado: "aguardando", user_code: "ABCD-1234", verification_uri: "https://microsoft.com/devicelogin" } });
    render(<MinhaConta />);
    expect(await screen.findByText("Conta Microsoft não conectada")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Conectar minha conta Microsoft" }));
    expect(await screen.findByText("ABCD-1234")).toBeTruthy();
  });

  it("conectada, permite mandar o e-mail de teste e mostra para onde foi", async () => {
    api.mockResolvedValueOnce({ configurado: true, conectado: true, login: NENHUM });
    api.mockResolvedValueOnce({ envio_id: 7, remetente: "ana@lotufo.com" });
    render(<MinhaConta />);
    fireEvent.click(await screen.findByRole("button", { name: "Enviar e-mail de teste" }));
    await waitFor(() => expect(screen.getByText(/ana@lotufo\.com/)).toBeTruthy());
  });
});
```

Run: `cd frontend && npx vitest run src/MinhaConta.test.tsx`
Expected: FAIL (`Cannot find module './MinhaConta'`).

- [ ] **Step 6: Implementar a tela**

`frontend/src/MinhaConta.tsx`:

```tsx
import { useEffect, useRef, useState } from "react";
import { api } from "./api";

type Login = { estado: string; user_code: string | null; verification_uri: string | null; erro?: string };
type Status = { configurado: boolean; conectado: boolean; login: Login };

export default function MinhaConta() {
  const [st, setSt] = useState<Status | null>(null);
  const [erro, setErro] = useState("");
  const [teste, setTeste] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const timer = useRef<number | undefined>(undefined);

  const carregar = () => api<Status>("/api/correio/status").then(setSt).catch(e => setErro(String(e.message ?? e)));
  useEffect(() => { carregar(); return () => window.clearInterval(timer.current); }, []);

  // Enquanto a Microsoft espera a pessoa digitar o codigo, consultar o estado a cada 5 s.
  useEffect(() => {
    window.clearInterval(timer.current);
    if (st?.login.estado === "aguardando") timer.current = window.setInterval(carregar, 5000);
  }, [st?.login.estado]);

  async function conectar() {
    setErro(""); setOcupado(true);
    try { setSt(await api<Status>("/api/correio/conectar", { method: "POST" })); }
    catch (e) { setErro(String((e as Error).message ?? e)); }
    finally { setOcupado(false); }
  }

  async function enviarTeste() {
    setErro(""); setTeste(""); setOcupado(true);
    try {
      const r = await api<{ remetente: string }>("/api/correio/teste", { method: "POST" });
      setTeste(`E-mail de teste enviado para ${r.remetente}. Confira a caixa de entrada e os itens enviados.`);
    } catch (e) { setErro(String((e as Error).message ?? e)); }
    finally { setOcupado(false); }
  }

  if (!st) return <p className="vazio">{erro || "Carregando…"}</p>;
  return (
    <section className="cartao">
      <header className="cartao__cabeca"><h2 className="cartao__titulo">Conta Microsoft</h2></header>
      <div className="cartao__corpo">
        <p>Os e-mails que você manda pela dashboard saem da sua própria caixa e aparecem nos seus itens enviados.</p>
        {!st.configurado && <p role="alert">O Microsoft 365 ainda não foi configurado neste servidor.</p>}
        <p><strong>{st.conectado ? "Conta Microsoft conectada" : "Conta Microsoft não conectada"}</strong></p>
        {st.login.estado === "aguardando" && st.login.user_code && (
          <p>
            Abra <a href={st.login.verification_uri ?? "#"} target="_blank" rel="noreferrer">{st.login.verification_uri}</a>,
            digite o código <strong>{st.login.user_code}</strong> e entre com a sua conta da Lotufo.
          </p>
        )}
        {st.login.estado === "expirado" && <p role="alert">O código expirou. Peça outro.</p>}
        {st.login.estado === "recusado" && <p role="alert">A Microsoft recusou o acesso. Tente de novo.</p>}
        {st.login.estado === "erro" && <p role="alert">{st.login.erro}</p>}
        {erro && <p role="alert">{erro}</p>}
        {teste && <p role="status">{teste}</p>}
        <div className="acoes">
          <button type="button" className="botao" disabled={ocupado || !st.configurado} onClick={conectar}>
            {st.conectado ? "Conectar de novo" : "Conectar minha conta Microsoft"}
          </button>
          <button type="button" className="botao botao--secundario" disabled={ocupado || !st.conectado}
                  onClick={enviarTeste}>Enviar e-mail de teste</button>
        </div>
      </div>
    </section>
  );
}
```

Nota: as classes `cartao`, `cartao__cabeca`, `cartao__titulo`, `cartao__corpo`, `botao`, `botao--secundario`, `acoes` e `vazio` já existem em `frontend/src/tokens.css` e nos CSS das telas atuais; conferir com `grep -n "\.cartao\b\|\.botao\b\|\.acoes\b" frontend/src/*.css` e usar o nome existente se algum diferir.

- [ ] **Step 7: Ligar a rota e a navegação**

Em `frontend/src/rota.tsx`: acrescentar `| { tela: "conta" }` à união `Rota` e `"conta"` à lista `SIMPLES`:

```ts
const SIMPLES = ["painel", "engenharia", "sugestoes", "contratos", "certidoes", "admin", "conta"] as const;
```

Em `frontend/src/App.tsx`:
1. `import MinhaConta from "./MinhaConta";`
2. Em `TITULOS`, acrescentar `conta: "Minha conta"`.
3. Envolver o bloco `<div className="usuario">…</div>` do rodapé da barra lateral num `<Link className="usuario__link" para={{ tela: "conta" }} ir={ir} aria-current={naPagina("conta")}>…</Link>`, para o nome da pessoa levar à tela.
4. Antes do bloco `{rota.tela === "admin" && …}`, acrescentar:

```tsx
        {rota.tela === "conta" && (
          <>
            <header className="topbar"><h1 className="topbar__titulo">Minha conta</h1></header>
            <div className="pagina"><MinhaConta /></div>
          </>
        )}
```

Em `frontend/src/rota.test.ts`, acrescentar o caso `"/conta"` → `{ tela: "conta" }` no mesmo formato dos testes de rota simples existentes.

- [ ] **Step 8: Rodar e ver passar (frontend)**

Run: `cd frontend && npx vitest run && npx tsc --noEmit`
Expected: todos os testes passam e o TypeScript não acusa erro.

- [ ] **Step 9: Produção e runbook**

Em `scripts/rodar_producao.ps1`, logo depois da linha que define `$env:DASH_GRAPH_TOKEN_ARQUIVO`:

```powershell
    # Uma conta Microsoft por usuario (envio de e-mail pela propria caixa, spec 2026-09-21 §5.1).
    $env:DASH_GRAPH_TOKENS_DIR = Join-Path $segredosGraph "usuarios"
```

Em `docs/runbook.md`, acrescentar:

```markdown
## Envio de e-mail pela conta de cada pessoa

1. No portal do Entra ID, no aplicativo já registrado, em Permissões de API → Microsoft Graph → delegadas,
   acrescentar `Mail.Send` e `Mail.ReadWrite` (as duas sem consentimento de administrador). `User.Read` e
   `offline_access` já existem.
2. Cada pessoa de operação abre Minha conta (clique no próprio nome), clica em "Conectar minha conta
   Microsoft", digita o código em microsoft.com/devicelogin com a conta da Lotufo e depois usa "Enviar e-mail
   de teste". O e-mail tem que aparecer na caixa de entrada E nos itens enviados dela.
3. O token fica em `C:\DashboardLotufo\segredos\graph\usuarios\usuario-<id>.txt`. Apagar o arquivo desconecta
   a pessoa. Token sem uso por 90 dias expira: basta conectar de novo.
4. O sistema não lê caixa de e-mail. `Mail.ReadWrite` é exigida pelo Graph para criar o rascunho e subir
   anexo acima de 3 MB.
```

- [ ] **Step 10: Commit**

```bash
git add backend/app/api_correio.py backend/app/main.py backend/tests/test_api_correio.py frontend/src/MinhaConta.tsx frontend/src/MinhaConta.test.tsx frontend/src/rota.tsx frontend/src/rota.test.ts frontend/src/App.tsx scripts/rodar_producao.ps1 docs/runbook.md
git commit -m "feat: tela Minha conta - conectar a conta Microsoft e enviar e-mail de teste"
```

---

### Task 11: Fechamento do bloco

**Files:**
- Modify: `CLAUDE.md`, `PRODUCT.md`, `docs/backlog.md`

- [ ] **Step 1: Suíte inteira**

Run: `cd backend && .venv/Scripts/python -m pytest -q` e `cd frontend && npx vitest run && npx tsc --noEmit`
Expected: tudo verde. Se algum teste antigo falhar, a causa é deste bloco: corrigir antes de seguir.

- [ ] **Step 2: Apontar a nova autoridade de produto**

Em `CLAUDE.md`, trocar a frase "Autoridade de produto: `docs/superpowers/specs/2026-08-28-dashboard-contratos-medicoes-design.md`" por:

```markdown
Autoridade de produto: `docs/superpowers/specs/2026-09-21-reestruturacao-design.md` (substitui a de 2026-08-28; o que ela não contradiz continua valendo). Decisões e evidências: `docs/decisoes-reestruturacao-2026-09-16.md`.
```

e acrescentar em "Regras que o código não conta":

```markdown
- **Cadastro versionado.** Obras, órgãos, entidades e instrumentos moram em `cadastro/*.yaml`, editados pelo Leonardo com o Claude e carregados por `python -m app.cli cadastro aplicar`. Não existe tela de cadastro; instrumento aplicado não se altera (correção é instrumento novo).
```

Em `PRODUCT.md`, substituir o parágrafo de "Positioning" pela primeira frase da seção 0 da spec nova e ajustar a linha de "Autoridade de produto".

- [ ] **Step 3: Backlog**

Em `docs/backlog.md`, acrescentar no topo:

```markdown
## Reestruturação: bloco 1, fundação (branch `bloco1-fundacao`)

- 2026-09-21 Entregue: cadastro versionado (`cadastro/*.yaml`, `cadastro validar` e `aplicar` com ensaio, auditoria e recusa de alteração de instrumento aplicado), migrações 018 e 019, as 22 obras do QDOP, rotas de escrita de cadastro fechadas em produção (`DASH_CADASTRO_VERSIONADO=1`), envio de e-mail pela conta de cada pessoa (rascunho, sessão de upload, registro em `envios`) e a tela Minha conta.
- 2026-09-21 Decisões do plano: máquina de estados da medição foi para o bloco 2 e o remapeamento do legado para o bloco 3; "em encerramento" é a coluna `encerramento_iniciado_em`; aditivos de valor e prazo seguem em `aditivos`, o resto em `instrumentos`.
- 2026-09-21 Pendências externas: `Mail.Send` e `Mail.ReadWrite` no aplicativo do Entra; as operadoras com usuário e conta conectada; datas do apostilamento de prazo de Leblon (24/08) e MT-402 (26/08) a ler no Diário Oficial; datas de Estações e Terminais BRT no QDOP.
```

- [ ] **Step 4: Gate Sol (uma rodada)**

```bash
git diff master...bloco1-fundacao | codex exec -m gpt-5.6-sol "Revise este diff procurando bugs. Foco: (1) cadastro_aplicar - idempotencia, transacao unica, recusa de alteracao de instrumento aplicado, ordem do retrato de valor; (2) correio - o bearer nunca sai do host do Graph, falha de envio nao registra envio, teto de tamanho, token por usuario sem vazar entre usuarios; (3) migracoes 018/019 idempotentes. Liste achados com arquivo e linha."
```

Corrigir o que for bug real, com teste, num commit `fix:`. Achado que for dívida vira uma linha no backlog.

- [ ] **Step 5: Commit e pedido de merge**

```bash
git add CLAUDE.md PRODUCT.md docs/backlog.md
git commit -m "docs: bloco 1 da reestruturacao - autoridade de produto, regra do cadastro e backlog"
```

Apresentar ao Leonardo: o que foi entregue, o relatório do ensaio da Task 7, o resultado do gate Sol e o pedido de OK para o merge em `master`. Depois do merge: deploy, `cadastro aplicar --ensaio` e `cadastro aplicar` em produção (runbook), e o teste de envio com a conta dele.
