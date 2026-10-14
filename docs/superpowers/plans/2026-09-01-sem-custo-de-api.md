# Sem Custo de API (emenda §15) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tirar do produto tudo que gera custo de API ou finge automação que não existe: a extração por IA vira leitura determinística do PDF, o robô das federais sai, e os documentos passam a dizer a verdade.

**Architecture:** Mesmo desenho das fases 1–3 (FastAPI + SQLite com SQL explícito, repositórios com auditoria, routers finos, React sem libs novas). Um módulo puro novo, `app/leitura_pdf.py`, herda o leitor de PDF e o validador determinístico de `ia_extracao.py` e ganha a localização por expressões regulares; `ia_extracao.py` e `robo_certidoes.py` são apagados; uma migração remove a tabela de custo; o frontend troca um botão e apaga um cartão.

**Tech Stack:** Python 3.12, FastAPI, sqlite3, pypdf (já pinado), pytest; React 18 + Vite + TS. Dependência removida: `anthropic`. Nenhuma dependência nova.

**Spec:** `docs/superpowers/specs/2026-08-28-dashboard-contratos-medicoes-design.md` — §15 (emenda de 2026-09-01), em especial §15.2 (certidões), §15.4 (decisões incorporadas) e §15.5 (pendências). A §14 está revogada e serve só de histórico.

## Global Constraints

- **Nenhum serviço pago por uso** (§15.1). Nada de SDK de IA, nada de API de certidão, nada de OCR em nuvem. Se uma tarefa parecer precisar disso, ela está errada.
- Toda mutação = UMA transação via `db.mutacao(conn)` com `auditoria.registrar(...)` dentro (contrato da fase 3, T1). Este plano não cria mutação nova; a leitura do PDF **nunca grava**.
- Datas: banco em UTC; decisão e exibição em America/Cuiaba via `app/tempo.py` e `frontend/src/tempo.ts`. Datas puras de certidão (emissão, validade) em `AAAA-MM-DD`, exibidas com `fmtDataPura`.
- Mensagens ao usuário em pt-BR, sem jargão de SDK; erro do arquivo → 422/415/413; nunca 5xx por culpa do arquivo.
- Permissões: leitura de PDF = `exigir("editar_cadastros")` (quem faz upload usa); nada de `administrar` para ela. Rotas removidas devem responder 404 (não existir), não 403.
- Migrações idempotentes (`IF NOT EXISTS` / `IF EXISTS`); runner em `app/db.py` já trata `ALTER TABLE ... ADD COLUMN`; `DROP TABLE IF EXISTS` é idempotente por construção.
- Frontend segue `DESIGN.md` (desde 2026-09-25 em `docs/sistema-visual-fase3-2026-09-02.md`; tokens e componentes já existentes em `tokens.css`); nada de cor ou tamanho fora da rampa.
- TDD por tarefa; commits `feat:/fix:/docs:/chore:` com rodapé `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`. Sem merge em `master`, sem push.
- Rodar: `cd backend; .venv\Scripts\python -m pytest -q` (baseline **439** verdes antes deste plano; a contagem cai com a remoção de `test_ia_extracao.py` e `test_robo_certidoes.py` e sobe com os testes novos). Frontend: `cd frontend; npx tsc --noEmit -p tsconfig.app.json; npm run build`.
- **Nunca** apontar servidor, seed ou teste para `backend/dados/dashboard.db` (é o caminho da produção). Testes usam `DASH_DB_PATH` em `tmp_path` via `conftest.py`.
- Não abrir sub-agentes dentro de uma tarefa. Não tocar em arquivos fora dos listados na tarefa.

---

### Task 1: Módulo `leitura_pdf` — localização por regex + validador herdado

**Files:**
- Create: `backend/app/leitura_pdf.py`
- Create: `backend/tests/test_leitura_pdf.py`
- Read only (fonte a herdar, NÃO apagar nesta task): `backend/app/ia_extracao.py:195-435`

**Interfaces:**
- Consumes: `entidades.cnpj_valido(digitos: str) -> bool` (`backend/app/entidades.py`).
- Produces (T2 consome):
  - `leitura_pdf.leitor_de_pdf(pdf: bytes) -> pypdf.PdfReader`
  - `leitura_pdf.texto_de_pdf(pdf: bytes) -> str`
  - `leitura_pdf.ler_certidao(texto: str, tipos: list[dict], entidade: dict | None = None) -> dict` com o shape `{"sugestao": {"tipo": str|None, "tipo_id": int|None, "numero": str|None, "emissao": "AAAA-MM-DD"|None, "validade": "AAAA-MM-DD"|None, "cnpj": "14 dígitos"|None}, "avisos": list[str], "evidencia": {campo: trecho_literal}}`
  - `leitura_pdf.TextoInadequado(ValueError)` — PDF sem texto legível ou texto acima de `TETO_CARACTERES`.
  - `leitura_pdf.CAMPOS = ("tipo", "numero", "emissao", "validade", "cnpj")`, `leitura_pdf.MANUAL = "preencha manualmente"`, `leitura_pdf.TETO_CARACTERES = 60_000`.

- [ ] **Step 1: Escrever os testes que falham**

```python
# backend/tests/test_leitura_pdf.py
"""Leitura deterministica de certidao (spec §15.2): regex acha, validador confere.

Nada aqui toca rede, banco ou disco: `ler_certidao` recebe TEXTO e devolve
sugestao + avisos. Os textos abaixo reproduzem a estrutura real dos tres layouts
federais (frases-chave e ordem dos campos), com dados ficticios.
"""
import pytest

from app import entidades, leitura_pdf

CNPJ = "00000000000100"          # placeholder invalido, so' ilustrativo
TIPOS = [
    {"id": 1, "nome": "CND Federal (RFB/PGFN)", "jurisdicao": "federal"},
    {"id": 2, "nome": "CRF/FGTS", "jurisdicao": "federal"},
    {"id": 3, "nome": "CNDT", "jurisdicao": "trabalhista"},
    {"id": 4, "nome": "Certidão Negativa Estadual (SEFAZ-MT)", "jurisdicao": "estadual"},
]

CND = """MINISTÉRIO DA FAZENDA
Secretaria da Receita Federal do Brasil
Procuradoria-Geral da Fazenda Nacional
CERTIDÃO NEGATIVA DE DÉBITOS RELATIVOS AOS TRIBUTOS FEDERAIS E À DÍVIDA ATIVA DA UNIÃO
Nome: EMPRESA EXEMPLO LTDA
CNPJ: 00.000.000/0001-00
Ressalvado o direito de a Fazenda Nacional cobrar e inscrever quaisquer dívidas ...
Emitida às 10:23:45 do dia 02/08/2026 <hora e data de Brasília>.
Válida até 29/01/2027.
Código de controle da certidão: F0E1.D2C3.B4A5.9687
Qualquer rasura ou emenda invalidará este documento.
"""

CRF = """CAIXA
Certificado de Regularidade do FGTS - CRF
Inscrição: 00.000.000/0001-00
Razão Social: EMPRESA EXEMPLO LTDA
Endereço: RUA EXEMPLO 100 / CENTRO / CUIABA / MT / 78000-000
A Caixa Econômica Federal, no uso da atribuição que lhe confere o Art. 7, da Lei 8.036 ...
Validade: 10/08/2026 a 08/09/2026
Certificação Número: 2026081012345678901234
Informação obtida em 01/09/2026 08:12:33
"""

CNDT = """PODER JUDICIÁRIO
JUSTIÇA DO TRABALHO
CERTIDÃO NEGATIVA DE DÉBITOS TRABALHISTAS
Nome: EMPRESA EXEMPLO LTDA (MATRIZ E FILIAIS)
CNPJ: 00.000.000/0001-00
Certidão nº: 12345678/2026
Expedição: 23/07/2026, às 14:05:12
Validade: 19/01/2027 - 180 (cento e oitenta) dias, contados da data de sua expedição.
Certifica-se que EMPRESA EXEMPLO LTDA ... NÃO CONSTA como inadimplente no Banco Nacional de Devedores Trabalhistas.
"""

ESTADUAL = """GOVERNO DO ESTADO DE MATO GROSSO
SECRETARIA DE ESTADO DE FAZENDA
CERTIDÃO NEGATIVA DE DÉBITOS ESTADUAIS
Nº da certidão: 2026.0001234
Contribuinte: EMPRESA EXEMPLO LTDA
CNPJ: 00.000.000/0001-00
Emitida em: 17/08/2026
Válida até: 15/11/2026
"""


def _ler(texto, entidade=None):
    return leitura_pdf.ler_certidao(texto, TIPOS, entidade)


def test_cnpj_de_teste_tem_dv_valido():
    # No codigo real o CNPJ de teste tem DV valido; neste documento o valor e' um placeholder invalido, so' ilustrativo.
    assert entidades.cnpj_valido(CNPJ)


def test_cnd_federal_completa():
    r = _ler(CND)
    s = r["sugestao"]
    assert s["tipo"] == "CND Federal (RFB/PGFN)" and s["tipo_id"] == 1
    assert s["emissao"] == "2026-08-02"
    assert s["validade"] == "2027-01-29"
    assert s["numero"] == "F0E1.D2C3.B4A5.9687"
    assert s["cnpj"] == CNPJ
    assert r["avisos"] == []
    assert "29/01/2027" in r["evidencia"]["validade"]


def test_crf_usa_inicio_da_faixa_como_emissao():
    s = _ler(CRF)["sugestao"]
    assert s["tipo_id"] == 2
    assert s["emissao"] == "2026-08-10"
    assert s["validade"] == "2026-09-08"
    assert s["numero"] == "2026081012345678901234"
    assert s["cnpj"] == CNPJ


def test_cndt_expedicao_e_validade():
    s = _ler(CNDT)["sugestao"]
    assert s["tipo_id"] == 3
    assert s["emissao"] == "2026-07-23"
    assert s["validade"] == "2027-01-19"
    assert s["numero"] == "12345678/2026"


def test_estadual_generica_acha_datas_e_deixa_tipo_em_branco():
    r = _ler(ESTADUAL)
    s = r["sugestao"]
    assert s["tipo"] is None and s["tipo_id"] is None
    assert s["emissao"] == "2026-08-17"
    assert s["validade"] == "2026-11-15"
    assert s["numero"] == "2026.0001234"
    assert any("tipo" in a.lower() for a in r["avisos"])


def test_texto_vazio_e_texto_gigante_sao_inadequados():
    with pytest.raises(leitura_pdf.TextoInadequado):
        _ler("   \n ")
    with pytest.raises(leitura_pdf.TextoInadequado):
        _ler("x" * (leitura_pdf.TETO_CARACTERES + 1))


def test_campo_nao_localizado_vira_aviso_nomeado():
    r = _ler(CND.replace("Válida até 29/01/2027.", ""))
    assert r["sugestao"]["validade"] is None
    assert any("validade" in a.lower() and "não localizei" in a.lower() for a in r["avisos"])


def test_validade_antes_da_emissao_derruba_as_duas():
    r = _ler(CND.replace("29/01/2027", "01/01/2026"))
    assert r["sugestao"]["emissao"] is None and r["sugestao"]["validade"] is None
    assert any("posterior" in a for a in r["avisos"])


def test_data_impossivel_cai_com_aviso():
    r = _ler(CND.replace("29/01/2027", "31/02/2027"))
    assert r["sugestao"]["validade"] is None
    assert any("calendário" in a for a in r["avisos"])


def test_cnpj_com_dv_errado_nao_e_sugerido():
    r = _ler(CND.replace("00.000.000/0001-00", "00.000.000/0002-00"))
    assert r["sugestao"]["cnpj"] is None
    assert any("CNPJ" in a for a in r["avisos"])


def test_cnpj_divergente_da_entidade_avisa_mas_sugere():
    r = _ler(CND, entidade={"id": 9, "nome": "Outra Ltda", "cnpj": "00000000000200"})
    assert r["sugestao"]["cnpj"] == CNPJ
    assert any("difere da entidade" in a for a in r["avisos"])


def test_tipo_nao_cadastrado_cai_com_aviso():
    r = leitura_pdf.ler_certidao(CND, [{"id": 7, "nome": "Outro tipo", "jurisdicao": "federal"}])
    assert r["sugestao"]["tipo"] is None and r["sugestao"]["tipo_id"] is None
    assert any("não corresponde a nenhum tipo" in a for a in r["avisos"])


def test_tipo_casa_sem_acento_e_sem_caixa():
    tipos = [{"id": 5, "nome": "cnd federal (rfb/pgfn)", "jurisdicao": "federal"}]
    assert leitura_pdf.ler_certidao(CND, tipos)["sugestao"]["tipo_id"] == 5


def test_texto_de_pdf_de_pagina_em_branco_e_vazio():
    import io
    from pypdf import PdfWriter
    w = PdfWriter(); w.add_blank_page(width=595, height=842)
    buf = io.BytesIO(); w.write(buf)
    assert leitura_pdf.texto_de_pdf(buf.getvalue()).strip() == ""
```

- [ ] **Step 2: Rodar e ver falhar** — `cd backend; .venv\Scripts\python -m pytest tests/test_leitura_pdf.py -q` → FAIL com `ModuleNotFoundError: app.leitura_pdf`.

- [ ] **Step 3: Implementar `app/leitura_pdf.py`**

Herdar de `ia_extracao.py` (copiar, não importar — o módulo antigo será apagado na T2): `leitor_de_pdf`, `texto_de_pdf`, `_normalizar`, `_data_no_texto`, `_cnpj_no_texto` e o corpo de `validar` **sem** o bloco de `emissor` (o emissor é atributo do tipo cadastrado, não da certidão) e **sem** o bloco "valor cru em formato inesperado" (aqui o cru sempre vem de regex, como string ou None). Acrescentar a localização:

```python
"""Leitura deterministica de certidao a partir do texto do PDF (spec §15.2).

Substitui a extracao por IA da §14 (revogada). Duas etapas, ambas sem rede:

1. `localizar(texto)`: expressoes regulares para os tres layouts federais (fixos
   ha anos) e um padrao generico por palavras-chave para estadual/municipal.
   Cada campo achado carrega o TRECHO LITERAL de onde saiu (`evidencia`).
2. `validar(...)`: o mesmo validador da fase 3 -- CNPJ com DV, datas reais e
   escritas no documento, validade posterior a emissao, tipo so' se casar com o
   cadastro, divergencia com a entidade escolhida vira aviso.

O que a regex nao acha volta `None` com um aviso nomeado. Nada aqui grava:
o resultado preenche o formulario e a pessoa confirma.
"""
import datetime
import io
import re
import unicodedata

import pypdf

from app import entidades

CAMPOS = ("tipo", "numero", "emissao", "validade", "cnpj")
MANUAL = "preencha manualmente"
TETO_CARACTERES = 60_000
_ROTULO = {"tipo": "o tipo", "numero": "o número", "emissao": "a data de emissão",
           "validade": "a data de validade", "cnpj": "o CNPJ"}


class TextoInadequado(ValueError):
    """PDF sem texto legivel (digitalizado, imagem) ou texto acima do teto."""


# --- leitura do PDF (unica implementacao do projeto; o upload tambem usa) -------------

def leitor_de_pdf(pdf: bytes) -> pypdf.PdfReader:
    return pypdf.PdfReader(io.BytesIO(pdf))


def texto_de_pdf(pdf: bytes) -> str:
    """Texto de todas as paginas. PDF de imagem pura devolve string vazia (sem OCR)."""
    return "\n".join(p.extract_text() or "" for p in leitor_de_pdf(pdf).pages)


# --- localizacao por regex -----------------------------------------------------------

_D = r"(\d{2}/\d{2}/\d{4})"

# Emissao: do layout mais especifico para o generico. A primeira que casar vence.
_EMISSAO = (
    re.compile(rf"emitid[ao]\s+[àa]s\s+\d{{2}}:\d{{2}}(?::\d{{2}})?\s+do\s+dia\s+{_D}", re.I),  # CND RFB/PGFN
    re.compile(rf"expedi[çc][ãa]o\s*:?\s*{_D}", re.I),                                      # CNDT
    re.compile(rf"(?:data\s+de\s+)?emiss[ãa]o\s*:?\s*{_D}", re.I),
    re.compile(rf"emitid[ao]\s+em\s*:?\s*{_D}", re.I),
)
# Validade: "Válida até" (CND), faixa "Validade: ini a fim" (CRF), "Validade: data" (CNDT/genérico).
_VALIDADE_ATE = re.compile(rf"v[áa]lid[ao]\s+at[ée]\s*:?\s*{_D}", re.I)
_VALIDADE_FAIXA = re.compile(rf"validade\s*:?\s*{_D}\s*(?:a|at[ée]|-)\s*{_D}", re.I)
_VALIDADE = re.compile(rf"(?:validade|vencimento)\s*:?\s*{_D}", re.I)
# Numero: CND (codigo de controle), CRF (certificacao numero), CNDT (certidao nº), generico.
_NUMERO = (
    re.compile(r"c[óo]digo\s+de\s+controle\s+da\s+certid[ãa]o\s*:?\s*([0-9A-F]{4}\.[0-9A-F]{4}\.[0-9A-F]{4}\.[0-9A-F]{4})", re.I),
    re.compile(r"certifica[çc][ãa]o\s+n[úu]mero\s*:?\s*(\d{10,30})", re.I),
    re.compile(r"certid[ãa]o\s+n[ºo°]\s*:?\s*(\d{1,12}/\d{4})", re.I),
    re.compile(r"n[ºo°]\s+da\s+certid[ãa]o\s*:?\s*([A-Z0-9][A-Z0-9./-]{3,40})", re.I),
)
_CNPJ = re.compile(r"(?<!\d)(\d{2})[.\s]?(\d{3})[.\s]?(\d{3})[/\s]?(\d{4})[-\s]?(\d{2})(?!\d)")
# Assinatura textual de cada tipo federal -> nome canonico semeado na migracao 006.
_TIPOS = (
    ("CND Federal (RFB/PGFN)", re.compile(r"tributos\s+federais|d[íi]vida\s+ativa\s+da\s+uni[ãa]o", re.I)),
    ("CRF/FGTS", re.compile(r"regularidade\s+do\s+fgts", re.I)),
    ("CNDT", re.compile(r"d[ée]bitos\s+trabalhistas", re.I)),
)


def _iso(br: str) -> str:
    d, m, a = br.split("/")
    return f"{a}-{m}-{d}"


def _primeira(padroes, texto: str):
    for p in padroes:
        m = p.search(texto)
        if m:
            return m
    return None


def localizar(texto: str) -> tuple[dict, dict]:
    """(bruto, evidencia): valores crus (str ou None) e o trecho de onde cada um saiu."""
    bruto: dict = {c: None for c in CAMPOS}
    evidencia: dict = {}

    m = _primeira(_EMISSAO, texto)
    if m:
        bruto["emissao"], evidencia["emissao"] = _iso(m.group(1)), m.group(0)

    m = _VALIDADE_ATE.search(texto) or _VALIDADE_FAIXA.search(texto) or _VALIDADE.search(texto)
    if m:
        if m.re is _VALIDADE_FAIXA:
            # CRF: "Validade: 10/08/2026 a 08/09/2026" -- o inicio da faixa E' a emissao
            # quando nenhuma outra frase a deu.
            if bruto["emissao"] is None:
                bruto["emissao"], evidencia["emissao"] = _iso(m.group(1)), m.group(0)
            bruto["validade"] = _iso(m.group(2))
        else:
            bruto["validade"] = _iso(m.group(1))
        evidencia["validade"] = m.group(0)

    m = _primeira(_NUMERO, texto)
    if m:
        bruto["numero"], evidencia["numero"] = m.group(1), m.group(0)

    # CNPJ: o primeiro com DV valido. Certidao traz o do contribuinte; um numero de
    # protocolo com 14 digitos nao passa no DV e e' pulado.
    for m in _CNPJ.finditer(texto):
        digitos = "".join(m.groups())
        if entidades.cnpj_valido(digitos):
            bruto["cnpj"], evidencia["cnpj"] = digitos, m.group(0)
            break

    for nome, assinatura in _TIPOS:
        m = assinatura.search(texto)
        if m:
            bruto["tipo"], evidencia["tipo"] = nome, m.group(0)
            break
    return bruto, evidencia


# --- validador (herdado da fase 3, §14.1, sem a parte de emissor) --------------------

def _normalizar(s: str) -> str:
    sem_acento = "".join(c for c in unicodedata.normalize("NFKD", s)
                         if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", sem_acento).strip().casefold()


def _data_no_texto(d: datetime.date, texto: str) -> bool:
    formas = (d.strftime("%d/%m/%Y"), d.isoformat())
    return any(re.search(rf"(?<!\d){re.escape(f)}(?!\d)", texto) for f in formas)


def _cnpj_no_texto(digitos: str, texto: str) -> bool:
    g = [re.escape(c) for c in digitos]
    padrao = (r"(?<!\d)" + "".join(g[0:2]) + r"[.\s]?" + "".join(g[2:5]) +
              r"[.\s]?" + "".join(g[5:8]) + r"[/\s]?" + "".join(g[8:12]) +
              r"[-\s]?" + "".join(g[12:14]) + r"(?!\d)")
    return re.search(padrao, texto) is not None


def validar(bruto: dict, texto: str, tipos: list[dict], entidade: dict | None = None) -> tuple[dict, list[str]]:
    # Copiar de ia_extracao.validar (fase 3): blocos de tipo, numero, datas, par de
    # datas, cnpj (DV + presenca) e divergencia com a entidade. Remover o bloco de
    # `emissor` e o de "valor cru em formato inesperado". Mensagens pt-BR identicas,
    # trocando "a IA pode tê-la calculado" por "a leitura pode ter errado".
    ...


def ler_certidao(texto: str, tipos: list[dict], entidade: dict | None = None) -> dict:
    if not texto or not texto.strip():
        raise TextoInadequado("O PDF não tem texto legível (arquivo digitalizado como imagem?) "
                              f"— {MANUAL}")
    if len(texto) > TETO_CARACTERES:
        raise TextoInadequado(f"O PDF tem texto demais para uma certidão "
                              f"({len(texto)} caracteres) — confira o arquivo e {MANUAL}")
    bruto, evidencia = localizar(texto)
    sugestao, avisos = validar(bruto, texto, tipos, entidade)
    for campo in CAMPOS:
        if bruto[campo] is None:
            avisos.append(f"Não localizei {_ROTULO[campo]} no texto do PDF — {MANUAL}.")
    return {"sugestao": sugestao, "avisos": avisos, "evidencia": evidencia}
```

O `...` em `validar` é o único ponto a preencher, copiando literalmente de `ia_extracao.py:298-435` os blocos indicados — o implementador tem o código-fonte ao lado; não reescrever a lógica.

- [ ] **Step 4: Rodar até passar** — `pytest tests/test_leitura_pdf.py -q` → todos verdes. Se `test_cnpj_de_teste_tem_dv_valido` falhar, trocar `CNPJ` no teste por um gerado com `entidades.cnpj_valido` (não mexer no validador).

- [ ] **Step 5: Commit**

```bash
git add backend/app/leitura_pdf.py backend/tests/test_leitura_pdf.py
git commit -m "feat: leitura deterministica de certidao a partir do PDF (regex + validador)"
```

---

### Task 2: Rota `/api/certidoes/ler-pdf`, remoção da IA e migração 010

**Files:**
- Modify: `backend/app/api_certidoes.py` (import na linha 37; `_conferir_parseavel` em 199-218; bloco "extracao por IA" 398-503; constante `LIMITE_CHAMADAS_IA` onde estiver definida; cabeçalho do módulo se citar IA)
- Modify: `backend/app/entidades.py:19-24` (comentário cita `ia_extracao`)
- Create: `backend/migrations/010_remove_ia_chamadas.sql`
- Delete: `backend/app/ia_extracao.py`, `backend/tests/test_ia_extracao.py`
- Modify: `backend/tests/test_api_certidoes.py:540-` (`test_extrair_por_ia_exige_csrf`)
- Modify: `backend/tests/test_db.py` (teste da migração 010)
- Modify: `backend/pyproject.toml` (remover `anthropic`), `backend/requirements.lock`

**Interfaces:**
- Consumes: `leitura_pdf.texto_de_pdf`, `leitura_pdf.leitor_de_pdf`, `leitura_pdf.ler_certidao`, `leitura_pdf.TextoInadequado` (T1); `_blocos_validados(arquivo)` e `_entidade_utilizavel(conn, entidade_id)` já existentes em `api_certidoes.py`.
- Produces (T4 consome): `POST /api/certidoes/ler-pdf` — multipart `arquivo` (PDF) + `entidade_id` opcional (Form) → `200 {"sugestao": {...}, "avisos": [...], "evidencia": {...}}`; permissão `editar_cadastros` + CSRF; 415/413 como o upload; 422 para PDF ilegível ou sem texto. `POST /api/certidoes/extrair` e `GET /api/ia/chamadas` **deixam de existir** (404).

- [ ] **Step 1: Escrever os testes que falham** (acrescentar em `backend/tests/test_api_certidoes.py`; substituir `test_extrair_por_ia_exige_csrf`)

```python
CND_TEXTO = """CERTIDÃO NEGATIVA DE DÉBITOS RELATIVOS AOS TRIBUTOS FEDERAIS E À DÍVIDA ATIVA DA UNIÃO
CNPJ: 00.000.000/0001-00
Emitida às 10:23:45 do dia 02/08/2026 <hora e data de Brasília>.
Válida até 29/01/2027.
Código de controle da certidão: F0E1.D2C3.B4A5.9687
"""


def _ler_pdf(client, monkeypatch, texto=CND_TEXTO, **form):
    # O leitor de texto e' trocado por um que devolve o texto de laboratorio: a regex
    # e' testada em test_leitura_pdf.py; aqui o alvo e' a FIACAO da rota.
    from app import leitura_pdf
    monkeypatch.setattr(leitura_pdf, "texto_de_pdf", lambda pdf: texto)
    return client.post("/api/certidoes/ler-pdf", data=form,
                       files={"arquivo": ("cnd.pdf", _pdf_valido(), "application/pdf")})


def test_ler_pdf_preenche_e_nao_persiste_nada(client_admin, monkeypatch, tmp_path):
    r = _ler_pdf(client_admin, monkeypatch)
    assert r.status_code == 200, r.text
    s = r.json()["sugestao"]
    assert s["validade"] == "2027-01-29" and s["emissao"] == "2026-08-02"
    assert s["tipo_id"] == 1 and s["cnpj"] == "00000000000100"
    assert r.json()["avisos"] == []
    from app.api_certidoes import pasta_certidoes
    assert not any(pasta_certidoes().glob("*")), "a leitura nunca grava arquivo"
    conn = _conn()
    assert conn.execute("SELECT COUNT(*) FROM certidoes").fetchone()[0] == 0


def test_ler_pdf_engenharia_pode_e_diretoria_nao(client, monkeypatch):
    eng = _logar(client, "engenharia")
    assert _ler_pdf(eng, monkeypatch).status_code == 200
    dire = _logar(client, "diretoria")
    assert _ler_pdf(dire, monkeypatch).status_code == 403


def test_ler_pdf_exige_sessao_e_csrf(client, client_admin, monkeypatch):
    assert _ler_pdf(client, monkeypatch).status_code == 401
    client_admin.headers.pop("X-CSRF-Token")
    assert _ler_pdf(client_admin, monkeypatch).status_code == 403


def test_ler_pdf_avisa_cnpj_divergente_da_entidade(client_admin, monkeypatch):
    # entidade 1 (Lotufo, semeada) tem outro CNPJ
    r = _ler_pdf(client_admin, monkeypatch, entidade_id=1)
    assert r.status_code == 200
    assert any("difere da entidade" in a for a in r.json()["avisos"])


def test_ler_pdf_sem_texto_da_422(client_admin, monkeypatch):
    r = _ler_pdf(client_admin, monkeypatch, texto="")
    assert r.status_code == 422 and "texto legível" in r.json()["detail"]


def test_ler_pdf_ilegivel_da_422(client_admin, monkeypatch):
    from app import leitura_pdf
    def quebra(pdf): raise ValueError("EOF marker not found")
    monkeypatch.setattr(leitura_pdf, "texto_de_pdf", quebra)
    r = client_admin.post("/api/certidoes/ler-pdf",
                          files={"arquivo": ("x.pdf", _pdf_valido(), "application/pdf")})
    assert r.status_code == 422 and "Não foi possível ler o PDF" in r.json()["detail"]


def test_ler_pdf_recusa_o_que_nao_e_pdf(client_admin):
    r = client_admin.post("/api/certidoes/ler-pdf",
                          files={"arquivo": ("x.pdf", b"nao e pdf", "application/pdf")})
    assert r.status_code == 415


def test_rotas_de_ia_nao_existem_mais(client_admin):
    assert client_admin.post("/api/certidoes/extrair",
                             files={"arquivo": ("x.pdf", _pdf_valido(), "application/pdf")}).status_code == 404
    assert client_admin.get("/api/ia/chamadas").status_code == 404
```

Usar os helpers que o arquivo já tem para PDF válido, conexão e login por perfil (nomes reais: conferir no topo de `test_api_certidoes.py` e em `test_permissoes.py`; se não houver `_logar(client, perfil)`, criar um local que cria o usuário via `auth.criar_usuario` e faz o login como o `client_admin` do `conftest.py`).

Em `backend/tests/test_db.py`, acrescentar:

```python
def test_migracao_010_remove_ia_chamadas_e_e_idempotente(tmp_path, monkeypatch):
    monkeypatch.setenv("DASH_DB_PATH", str(tmp_path / "m.db"))
    conn = db.get_conn()
    db.migrate(conn)
    tabelas = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "ia_chamadas" not in tabelas
    db.migrate(conn)          # segunda passada: nada a fazer, nada quebra
    conn.close()
```

- [ ] **Step 2: Rodar e ver falhar** — `pytest tests/test_api_certidoes.py tests/test_db.py -q` → os novos FAIL (404 na rota nova; tabela ainda existe).

- [ ] **Step 3: Migração 010**

```sql
-- backend/migrations/010_remove_ia_chamadas.sql
-- Spec §15 (2026-09-01): o produto nao chama servico pago por uso. A tabela de custo
-- de IA (§14.5, migracao 007) perdeu objeto -- nenhuma linha dela e' dado de negocio
-- (era log operacional, fora da cadeia de auditoria), entao remover e' seguro.
-- DROP IF EXISTS e' idempotente: reaplicar a migracao inteira (executescript nao e'
-- transacional) nao quebra.
DROP TABLE IF EXISTS ia_chamadas;
```

- [ ] **Step 4: Rota nova, rotas velhas fora, import trocado**

Em `api_certidoes.py`:
1. Linha 37: `from app import certidoes, checklist, db, entidades, leitura_pdf, tempo`.
2. `_conferir_parseavel`: trocar `ia_extracao.leitor_de_pdf` por `leitura_pdf.leitor_de_pdf` e ajustar o comentário (não há mais robô nem IA; o leitor único é o de `leitura_pdf`).
3. Apagar o bloco inteiro "extracao por IA (§14)" (`_frase`, `extrair`, `chamadas_de_ia`) e a constante `LIMITE_CHAMADAS_IA`. Se `_frase` for usada por outra rota, mantê-la.
4. Acrescentar, no lugar:

```python
# --- leitura deterministica do PDF (§15.2) --------------------------------------------

@router.post("/api/certidoes/ler-pdf")
def ler_pdf(arquivo: UploadFile = File(...),
            entidade_id: int | None = Form(default=None, ge=1, le=MAX_INT64),
            usuario: dict = Depends(exigir("editar_cadastros")),
            conn: sqlite3.Connection = Depends(conexao)):
    """PDF -> sugestao de preenchimento por regex. NAO grava certidao, NAO guarda o PDF.

    Mesma permissao do upload: quem anexa a certidao e' quem se beneficia de nao
    digitar seis campos. Nao ha custo externo (§15.1), entao nao ha por que restringir.
    Erro do ARQUIVO (nao e' PDF, nao abre, nao tem texto) e' 415/422 -- culpa de quem
    enviou, nunca 5xx.
    """
    pdf = b"".join(_blocos_validados(arquivo))
    try:
        # Atributo do modulo, nao nome importado: e' o que deixa os testes trocarem o leitor.
        texto = leitura_pdf.texto_de_pdf(pdf)
    except Exception as e:      # pypdf: corrompido, cifrado, truncado
        raise HTTPException(422, f"Não foi possível ler o PDF enviado ({type(e).__name__}) "
                                 f"— envie o arquivo original ou {leitura_pdf.MANUAL}")
    entidade = entidades.detalhe(conn, entidade_id) if entidade_id is not None else None
    try:
        return leitura_pdf.ler_certidao(texto, certidoes.tipos(conn), entidade)
    except leitura_pdf.TextoInadequado as e:
        raise HTTPException(422, str(e))
```

5. Em `entidades.py:19-24`, trocar a menção a `app/ia_extracao.py` por `app/leitura_pdf.py`.
6. Apagar `backend/app/ia_extracao.py` e `backend/tests/test_ia_extracao.py` (`git rm`).
7. `grep -rn "ia_extracao\|ia_chamadas\|DASH_ANTHROPIC\|anthropic" backend/app backend/tests` → deve devolver **só** a migração 007 (histórico) e a 010.

- [ ] **Step 5: Dependências**

Em `backend/pyproject.toml`: remover a entrada `"anthropic==1.3.0"` e o comentário dela; no comentário do `httpx`, dizer que ele fica por ser exigido pelo `TestClient` do Starlette (sem seção de extras neste projeto). Depois:

```powershell
cd backend
.venv\Scripts\python -m pip uninstall -y anthropic
.venv\Scripts\python -m pip check
.venv\Scripts\python -m pip freeze > requirements.lock
git diff --stat requirements.lock
```

Se `openpyxl`/`et_xmlfile` aparecerem no lock (drift já anotado no ledger da fase 3), desinstalá-los também (`pip uninstall -y openpyxl et_xmlfile`; nada em `backend/app` os importa — conferir com grep) e refazer o freeze. Se o freeze trouxer outras diferenças além dessas, PARAR e relatar antes de gravar.

- [ ] **Step 6: Suíte completa** — `pytest -q` → verde (baseline esperada: 439 − 51 de `test_ia_extracao.py` − 1 substituído + 8 novos + 1 de migração ≈ 396; a contagem exata fica no relatório). `python -c "import app.main"` sem `anthropic` instalado → ok.

- [ ] **Step 7: Commit**

```bash
git add -A backend
git commit -m "feat: rota ler-pdf deterministica substitui extracao por IA; remove anthropic e ia_chamadas (spec §15)"
```

---

### Task 3: Aposentar o robô das certidões federais

**Files:**
- Modify: `backend/app/main.py:9-11, 65-71` (import e `agendar_semanal`)
- Delete: `backend/app/robo_certidoes.py`, `backend/tests/test_robo_certidoes.py`
- Modify: `backend/app/certidoes.py:113-118` (docstring de `registrar` cita o robô), `backend/app/paineis.py:196-215` (docstring de `_alertas_de_certidao` cita o robô)
- Modify: `backend/tests/test_health.py` ou `backend/tests/test_frontend_mount.py` (teste de que `create_app` não sobe thread do robô)

**Interfaces:**
- Consumes: nada novo.
- Produces: `create_app()` sem worker de certidões; `certidoes.ORIGENS` continua `("robo", "upload")` (histórico; nada grava `robo` mais).

- [ ] **Step 1: Teste que falha**

```python
# acrescentar em backend/tests/test_health.py
def test_app_sobe_sem_modulo_de_robo(tmp_path, monkeypatch):
    """Spec §15.2: o robo das federais saiu. Nenhum atributo dele pode sobrar no app."""
    import importlib
    monkeypatch.setenv("DASH_DB_PATH", str(tmp_path / "r.db"))
    monkeypatch.setenv("DASH_SEM_JOBS", "1")
    monkeypatch.setenv("DASH_SEM_FRONTEND", "1")
    import app.main as m
    importlib.reload(m)
    assert not hasattr(m, "robo_mod")
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("app.robo_certidoes")
```

- [ ] **Step 2: Rodar e ver falhar** — `pytest tests/test_health.py -q` → FAIL (`robo_mod` existe).

- [ ] **Step 3: Remover**

Em `main.py`: apagar `from app import robo_certidoes as robo_mod` e o bloco `robo_mod.agendar_semanal()` com seu comentário; manter o `agendar_backup_horario` como está (o backup é assunto de outro plano). `git rm backend/app/robo_certidoes.py backend/tests/test_robo_certidoes.py`.

Em `certidoes.py`, docstring de `registrar`: trocar a frase sobre o robô semanal por: `usuario_id=None` fica aceito para importações sem humano (nenhuma existe hoje; o robô da fase 3 foi descartado pela spec §15.2).

Em `paineis.py`, docstring de `_alertas_de_certidao`: reescrever o primeiro parágrafo — o alerta deriva do estado do banco; não há robô; a mensagem do ausente manda anexar pelo upload porque esse é o único caminho.

`grep -rn "robo_certidoes\|robô\|robo\b" backend/app` → só `certidoes.ORIGENS` e a migração 006 (histórico) podem sobrar.

- [ ] **Step 4: Suíte completa** — `pytest -q` → verde; contagem cai em 431 linhas de teste do robô (informar a contagem).

- [ ] **Step 5: Commit**

```bash
git add -A backend
git commit -m "chore: aposenta o robo das certidoes federais (portais com captcha; spec §15.2)"
```

---

### Task 4: Frontend — "Preencher a partir do PDF" e fim do cartão "Uso de IA"

**Files:**
- Modify: `frontend/src/Certidoes.tsx` (tipos `SugestaoIa`/`RespostaIa` ~41-49; estado `ia`, `iaOcupada`, `iaIndisponivel`, `geracaoIa` ~164-187; `preencherComIA` ~301-338; botão e avisos ~690-720; comentários que citam IA)
- Modify: `frontend/src/Admin.tsx` (remover `ChamadaIa`, `UsoIa`, `competenciaBR`, estado `uso`/`erroIa`, a chamada a `/api/ia/chamadas` e a `<section>` "Uso de IA"; remover imports `brl`, `fmtDataHora`, `IconeAlerta` se ficarem sem uso)
- Modify: `frontend/src/api.ts:74-85` (docstring de `apiForm` cita IA e 503)

**Interfaces:**
- Consumes: `POST /api/certidoes/ler-pdf` (T2) → `{ sugestao: { tipo: string|null; tipo_id: number|null; numero: string|null; emissao: string|null; validade: string|null; cnpj: string|null }; avisos: string[]; evidencia: Record<string,string> }`.
- Produces: nada para outras tarefas.

- [ ] **Step 1: Certidoes.tsx**

1. Tipos:
```ts
type SugestaoLida = {
  tipo: string | null; tipo_id: number | null; numero: string | null;
  emissao: string | null; validade: string | null; cnpj: string | null;
};
type RespostaLeitura = { sugestao: SugestaoLida; avisos: string[]; evidencia: Record<string, string> };
```
2. Estado: `const [leitura, setLeitura] = useState<{ avisos: string[] } | null>(null);` e `const [lendo, setLendo] = useState(false);` no lugar de `ia`, `iaOcupada`, `iaIndisponivel`. Manter o contador de geração (renomear `geracaoIa` → `geracaoLeitura`) — a corrida "trocou o PDF antes da resposta" continua real.
3. Handler:
```ts
async function preencherDoPdf() {
  if (!arquivo) { setErro("Escolha o PDF antes de pedir o preenchimento — a leitura é do arquivo, não da tela."); return; }
  const g = ++geracaoLeitura.current;
  setErro(""); setLeitura(null); setLendo(true);
  try {
    const dados = new FormData();
    dados.append("arquivo", arquivo);
    if (form.entidade_id) dados.append("entidade_id", form.entidade_id);
    const r = await apiForm<RespostaLeitura>("/api/certidoes/ler-pdf", dados);
    if (g !== geracaoLeitura.current) return;
    const s = r.sugestao;
    setForm(f => ({
      ...f,
      tipo_id: s.tipo_id !== null ? String(s.tipo_id) : f.tipo_id,
      numero: s.numero ?? f.numero,
      emissao: s.emissao ?? f.emissao,
      validade: s.validade ?? f.validade,
      // Entidade so' e' sugerida se ainda nao houver uma escolhida e o CNPJ lido
      // casar com um cadastro: trocar a escolha da pessoa seria decidir por ela.
      entidade_id: f.entidade_id || String(entidades.find(e => e.cnpj === s.cnpj)?.id ?? ""),
    }));
    setLeitura({ avisos: r.avisos });
  } catch (e) {
    if (g !== geracaoLeitura.current) return;
    setErro(e instanceof ApiErro ? e.message : "Não foi possível ler o PDF.");
  } finally {
    if (g === geracaoLeitura.current) setLendo(false);
  }
}
```
Adaptar os nomes `arquivo`, `form`, `entidades`, `setForm` aos que o componente já usa (conferir no arquivo; não introduzir estado paralelo).
4. Botão: substituir o bloco admin-only por um botão secundário visível a `podeEditar`, com o ícone já usado, rótulo **"Preencher a partir do PDF"**, `disabled={!arquivo || lendo}`, texto "Lendo…" enquanto `lendo`. Apagar todo tratamento de 503 e de `custo_centavos`. Manter a lista de avisos (`role="status"`), com o título "Conferir antes de arquivar" quando houver avisos e "Campos preenchidos a partir do PDF — confira e arquive" quando `avisos.length === 0`.
5. Ajustar a nota de ajuda do formulário: a frase sobre IA vira "O preenchimento a partir do PDF lê o texto do arquivo; certidão digitalizada como imagem precisa ser digitada."
6. `grep -n -i "\bia\b\|IA\b\|anthropic\|503\|custo" frontend/src/Certidoes.tsx` → zero ocorrências restantes.

- [ ] **Step 2: Admin.tsx** — apagar a `<section className="cartao" aria-labelledby="titulo-uso-ia">` inteira, os tipos `ChamadaIa`/`UsoIa`, `competenciaBR`, os estados `uso`/`erroIa`, a chamada `api<UsoIa>("/api/ia/chamadas")` dentro de `carregar`, e `nomePorId` se ficar sem uso. Remover os imports que sobrarem sem uso (`brl`, `fmtDataHora`, `IconeAlerta`) e o comentário sobre `ia_chamadas` no topo.

- [ ] **Step 3: api.ts** — na docstring de `apiForm`, trocar "(upload de PDF e extracao por IA)" por "(upload de PDF e leitura do PDF)" e apagar a frase sobre separar 503 "sem chave de IA".

- [ ] **Step 4: Verificar** — `cd frontend; npx tsc --noEmit -p tsconfig.app.json; npm run build; npx oxlint` → sem erros (os 7 avisos pré-existentes do oxlint podem permanecer; nenhum novo).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/Certidoes.tsx frontend/src/Admin.tsx frontend/src/api.ts
git commit -m "feat: 'Preencher a partir do PDF' sem IA e sem restricao de admin; remove painel de custo"
```

---

### Task 5: Documentos — README, runbook e ledger

**Files:**
- Modify: `README.md` (linhas 9-11 estado das fases; seção "Telas da fase 2" ganha a tela de Certidões)
- Create: `docs/runbook.md`
- Modify: `.superpowers/sdd/2026-09-01-fase3-certidoes-e-dividas/progress.md` (nota de encerramento deste plano e o que resta da fase 3)

- [ ] **Step 1: README**

Trocar o parágrafo das fases por: fases 0–2 entregues; fase 3 (certidões) implementada neste branch com upload manual, "Preencher a partir do PDF" determinístico, semáforo, alertas e checklist "pronto para protocolar"; robô de emissão descartado (spec §15.2); produto sem custo de API (spec §15). Acrescentar à lista de telas:

```
- **Certidões** — matriz entidade × tipo com semáforo (em dia / a vencer / sem cobertura / não se aplica), upload do PDF com "Preencher a partir do PDF" (lê o texto do arquivo; certidão digitalizada precisa ser digitada), download da vigente, cadastro de entidades e tipos (admin). A página do contrato ganha a aba **Protocolo** com o checklist "pronto para protocolar" da entidade do contrato.
```

- [ ] **Step 2: Runbook** — criar `docs/runbook.md` com exatamente estas seções, cada uma em poucas linhas e sem prometer o que não existe:

```markdown
# Runbook — Dashboard Lotufo

## Onde as coisas ficam
- Código: este repositório (branch de produção = `master`).
- Banco: `backend\dados\dashboard.db` (+ `-wal`/`-shm`). **Mesmo caminho do servidor de dev** — ver "Riscos conhecidos".
- Snapshots: `backend\dados\backups\dashboard-AAAAMMDD-HHMMSS.db` (48 mais recentes, horários, gerados pelo processo do servidor).
- PDFs de certidão: `backend\dados\certidoes\<sha256>.pdf`.
- TLS: `certs\cert.pem` e `certs\chave.pem` (gerados por `scripts\gerar_certificado.ps1`, 5 anos).
- Logs: hoje o uvicorn escreve em stdout; na tarefa agendada isso não vai para arquivo. Dívida registrada.

## Subir e derrubar
- Dev: ver README ("Rodar em desenvolvimento").
- Produção: `scripts\rodar_producao.ps1` (elevado). Autostart: `scripts\instalar_autostart.ps1`; parar: `Stop-ScheduledTask -TaskName <tarefa>`.

## Restaurar o banco a partir de um snapshot
1. Parar o servidor (tarefa agendada e qualquer uvicorn em 8080/8443).
2. Copiar `dashboard.db`, `-wal` e `-shm` atuais para uma pasta de quarentena.
3. Copiar o snapshot escolhido para `backend\dados\dashboard.db`.
4. `backend\.venv\Scripts\python -c "import sqlite3; print(sqlite3.connect('backend/dados/dashboard.db').execute('PRAGMA integrity_check').fetchone())"` → `('ok',)`.
5. Subir o servidor; as migrações pendentes rodam sozinhas em `create_app()`.

## Contas
- Primeiro administrador: `cd backend; .venv\Scripts\python -m app.cli criar-admin --nome ... --email ...`.
- Demais usuários (inclusive o segundo administrador): tela Administração → Usuários.
- Senha esquecida: não há reset pela tela hoje; criar outro usuário e desativar o antigo. Dívida registrada.

## Variáveis de ambiente
`DASH_DB_PATH` (obrigatória fora de dev na prática), `DASH_DEV` (só dev), `DASH_SEM_JOBS`, `DASH_SEM_FRONTEND`, `DASH_DIST_PATH`. Nenhuma chave de serviço externo: o produto não chama API paga (spec §15).

## Riscos conhecidos (parecer de 2026-09-01)
- Dev e produção compartilham árvore e caminho de banco por padrão.
- Snapshots só locais; sem cópia externa; primeiro snapshot 1 h após o processo subir.
- Sem logs em arquivo; health não toca o banco; tarefa sem reinício automático.
```

- [ ] **Step 3: Ledger** — acrescentar ao fim de `.superpowers/sdd/2026-09-01-fase3-certidoes-e-dividas/progress.md`:

```
## Emenda §15 — sem custo de API (2026-09-01, plano docs/superpowers/plans/2026-09-01-sem-custo-de-api.md)
Decisões do Leonardo após o parecer crítico: nada pago por uso; robô descartado; itens de medição só na fase 6; custo/margem em backlog invisível; caixa compartilhada + 2º admin aprovados.
Tasks S1–S5 executadas neste branch (ver commits). T6/T8-IA da fase 3 ficam como histórico; `test_ia_extracao.py` e `test_robo_certidoes.py` removidos.
RESTA da fase 3: T10b (passe visual, agora com o botão "Preencher a partir do PDF"), gate 3 (Sol) sobre 237b152..HEAD, T11 (varredura), revisão final whole-branch, merge em master só com OK do Leonardo.
```

- [ ] **Step 4: Commit**

```bash
git add README.md docs/runbook.md .superpowers/sdd/2026-09-01-fase3-certidoes-e-dividas/progress.md
git commit -m "docs: README e runbook refletem o produto sem custo de API; ledger da fase 3 atualizado"
```

---

## Self-Review (executado na escrita do plano)

1. **Cobertura da spec §15**: §15.1 regra (T2 remove SDK e chave; T3 remove robô) ✓; §15.2 leitura determinística com layouts federais + genérico, evidência literal, validador mantido, nunca grava, `editar_cadastros` (T1/T2/T4) ✓; §15.2 removidos: módulo, rota `extrair`, rota `chamadas`, tabela (migração 010), dependência, variável, bloco "Uso de IA" (T2/T4) ✓; §15.4 runbook (T5) ✓; §15.3 (fases 4–7) e §15.5 (pendências externas) são texto de spec, sem código nesta rodada — nada a implementar ✓. Alerta de reajuste com antecedência (§15.4, "polimento da fase 3/4") fica **fora** deste plano de propósito: é funcionalidade nova, entra no plano de fechamento da fase 3.
2. **Placeholders**: o único `...` está em `validar` (T1, Step 3) com a instrução exata de copiar os blocos de `ia_extracao.py:298-435`; os helpers de teste em T2 têm instrução para localizar os nomes reais no arquivo. Sem "TBD".
3. **Consistência**: `leitura_pdf.ler_certidao(texto, tipos, entidade)` devolve `{"sugestao","avisos","evidencia"}` em T1, é o retorno direto da rota em T2 e o `RespostaLeitura` do T4; `texto_de_pdf` é chamado como atributo do módulo em T2 para o `monkeypatch` do teste funcionar; `TextoInadequado` levantado em T1 e capturado em T2. ✓

## Workflow de Execução

Orquestrador: sessão principal (Fable 5.1). Implementadores: Opus, um subagente novo por task, sem sub-agentes. Revisor de cada task e revisão final do lote: a sessão principal. Sem gate adversarial neste plano (não há superfície externa nova; a rota nova reaproveita as guardas de upload já auditadas no gate 2); o gate 3 da fase 3 cobrirá o diff completo `237b152..HEAD`, incluindo estas tasks.
