# Bloco 5 (Protocolo): carta, pacote, assinatura manual com conferência, envio. Plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. **Leia antes `00-indice.md`** (Global Constraints, decisões e interfaces compartilhadas valem aqui).

**Goal:** com as notas anexadas (bloco 3) e as certidões em dia (bloco 4), a pessoa escolhe a(s) medição(ões), digita o número do ofício, arrasta as peças técnicas que o órgão exige, confere a carta (texto editável), baixa o pacote montado na ordem do órgão, assina no DocuSign, arrasta o assinado de volta (o sistema confere página a página e o carimbo do envelope), vê a prévia do e-mail (destinatários, cópias, assunto, anexos com tamanho, o que falta) e envia. O envio aceito marca a medição como protocolada (na SINFRA, na etapa da nota) e grava tudo.

**Architecture:** peças puras e testáveis em módulos novos: `oficios.py` (número CT), `carta.py` (carta, capa e divisória em PDF com fpdf2), `pdfs.py` (juntar), `assinatura.py` (conferência por texto de página). `protocolo.py` orquestra por família (`FAMILIAS`, `Etapa`) com as regras do órgão vindas do cadastro. `api_protocolos.py` expõe; `Protocolo.tsx` é o fluxo na tela. Migração 025 aditiva.

**Tech Stack:** o do índice; dependência nova `fpdf2==2.8.8` (traz Pillow, fontTools e defusedxml).

**Spec:** §2 (estados, protocolo sem nota), §3 passos 4 a 7, §4.4 (nome de arquivo), §5.1 a §5.4, §6, §9 (cobrança na prévia), §12 (`envios`, `medicao_documentos`), §15.

**Status:** APROVADO pelo Leonardo em 2026-09-24 (ver `00-indice.md`).

## Decisões deste bloco (para aprovação)

1. **Carta em PDF gerada pelo sistema (fpdf2).** Não há modelo Word de carta de protocolo no repositório, nos projetos antigos nem nas pastas de trabalho: a carta é copiada da anterior hoje, e foi assim que o CT/297 (Espaço Show) saiu descrevendo o "Complexo da Orla" e o CT-301 saiu com o fiscal antigo no A/C. A conversão Word→PDF não existe no servidor (nem Word COM nem LibreOffice) e é frágil (Word trava com impressora de rede fora do ar, instrução global do Leonardo, item 6). O texto fixo mora em `cadastro/cartas.yaml`, por família; número da medição, período, notas e valores vêm dos dados. Fonte Arial do Windows (`C:\Windows\Fonts\arial.ttf`, `arialbd.ttf`); sem ela, Helvetica com os caracteres fora do latin-1 trocados (– vira -). **Timbre**: imagem recortada da primeira página de uma carta real (CT-301, MTPAR), em `cadastro/modelos/carta/timbre-lotufo.png`; entidade sem timbre recebe cabeçalho de texto (razão social, endereço, CNPJ). **O corpo é editável na prévia** (texto com três marcas: linha em branco separa parágrafos; `# ` abre título de seção; `i. `/`1. ` é item de lista); o texto final fica gravado no protocolo.
2. **Um protocolo = um documento a assinar = um ofício.** Tabela `protocolos` (etapa, natureza, número do ofício, corpo da carta, PDF montado, PDF assinado, conferência, envio, justificativa, número do órgão, comprovante, situação), `protocolo_medicoes` (N:N: a SES soma execução e reequilíbrio numa carta só), `protocolo_pecas` (peças arrastadas; removida é marcada, não apagada). Um e-mail pode levar vários protocolos: a SINFRA manda execução e reajuste no mesmo e-mail, em PDFs separados (limite de 25 MB por documento, regra da SUEF I de 11/09).
3. **Famílias no código, detalhes no cadastro.** A estrutura (etapas, partes do PDF, anexos soltos, quem marca protocolada) é da família; destinatários, textos, peças exigidas e sua ordem, ordem das certidões, limite por documento são do órgão.

| Família | Etapas | PDF assinado (ordem) | Anexos soltos do e-mail | Um e-mail por |
|---|---|---|---|---|
| MTPAR | única | carta → notas → certidões (ordem do órgão: municipal, trabalhista, estadual, federal, FGTS) | nenhum | natureza (sempre separados, cada um com seu CT) |
| SES | única | capa ("42ª MEDIÇÃO / PERÍODO") → carta com lista numerada → divisória NOTA FISCAL → notas → divisória CERTIDÕES → certidões → para cada peça, divisória com o título e a peça (ART, diário, fotos, cronograma, boletim, memoriais, ensaios) | nenhum | natureza (dois ofícios, dois e-mails; o mesmo envelope DocuSign pode cobrir os dois) |
| SINFRA | 1ª **medição** | carta → peças (boletim/caderno assinado) | planilha editável | e-mail único para execução e reajuste |
| SINFRA | 2ª **nota** | — (sem carta, sem assinatura) | notas, ZIP de certidões por empresa, CNO da obra, regularidade | e-mail único |
| Prefeitura | única | carta → notas | ZIP de certidões, peças (relatório fotográfico) | natureza |

4. **SINFRA: `protocolada` na etapa da nota.** A medição assinada sai antes da nota existir (MT-388: medição e reajuste assinados em 09/09, NF e certidões em 16/09); a data que inicia o pagamento é a do envio da nota. A etapa da medição grava o envio (e liga a medição ao envio) sem mudar o estado; a etapa da nota chama `medicoes.registrar_protocolo` com o número do ofício da etapa da medição (o último enviado para aquela medição). Nas demais famílias, a etapa única marca protocolada.
5. **Pendência avisa e deixa seguir.** Sem nota (casos reais: Coxipó recebe a medição pronta; Região Oeste protocola por link), certidão/regularidade sem validade hoje, peça exigida faltando, CNO não cadastrado, pacote não assinado, conferência com aviso, documento acima do limite do órgão, ofício com número já usado, medição já protocolada: cada um vira uma linha na prévia; enviar com qualquer linha exige justificativa, gravada no protocolo e na auditoria (`ressalva` do `registrar_protocolo` quando for certidão). **Bloqueia** (erro, não regra): medição cancelada, desistida ou recebida; protocolo sem PDF montado quando a etapa tem carta; nenhum destinatário; anexos acima de 35 MB.
6. **Conferência do assinado** (spec §6), por texto de cada página, no subprocesso com limite (tetos do pacote: 40 MB, 400 páginas, 60 s): (1) as N primeiras páginas do assinado batem com as N do montado (texto normalizado, sem o carimbo, semelhança ≥ 0,90); página só de imagem no montado exige página só de imagem (ou só o carimbo) no assinado; (2) páginas a mais no fim só se começarem por "Certificado de Conclusão"/"Certificate of Completion"; (3) todas as N páginas com `Docusign Envelope ID: <GUID>`, o mesmo em todas. Gabaritos reais para a prova (tarefa 5.11): o par da Cavalaria (`...-PROTOCOLO.pdf` e `...-Assinado.pdf`, 92 páginas, carimbo sem certificado), o CT-073 da MT-388 (4 páginas + 4 de certificado) e o CT-286 da Orla (0 páginas carimbadas: o "não assinado" que a regra 3 pega).
7. **Comprovante do CNO**: `cno_pdf` no YAML do contrato (arquivo em `cadastro/anexos/<nome-curto>/`), copiado por `cadastro aplicar` para a pasta de dados (`contratos.cno_arquivo`). Entra onde a família pede (SINFRA, etapa da nota); falta vira pendência. Os 22 contratos estão sem CNO hoje (P2 do índice).
8. **Teto do e-mail**: `correio.MAX_TOTAL` sobe de 25 MB para 35 MB (limite padrão de envio do Exchange Online; a sessão de upload do Graph aceita até 150 MB). O limite por documento do órgão (25 MB na SINFRA) é aviso por PDF.
9. **`medicao_protocolos.protocolo_id`** liga o protocolo antigo (a linha que `registrar_protocolo` já grava) ao protocolo novo e, por ele, ao envio. `origem` continua `manual` (o CHECK antigo não aceita outro valor e reconstruir a tabela não compensa).
10. **O registro manual de protocolo continua** (rota `POST /api/medicoes/{id}/protocolo`), para o protocolo feito fora do sistema; na tela ele fica atrás de "registrar protocolo feito por fora".

## Estrutura de arquivos

| Arquivo | Responsabilidade |
|---|---|
| `backend/migrations/025_protocolo.sql` | `protocolos`, `protocolo_medicoes`, `protocolo_pecas`; `medicao_protocolos.protocolo_id`; `contratos.objeto_completo`, `contratos.cno_arquivo`; `contrato_fiscais.cargo/tratamento/portaria` |
| `backend/app/oficios.py` | número do ofício canônico, forma da carta, usos anteriores |
| `backend/app/carta.py` | `Carta`, `gerar`, `pagina_titulo`, `data_extenso`, `preencher`, `config`, `emitente`, `fiscal_vigente` |
| `backend/app/pdfs.py` | juntar PDFs, contar páginas, tetos do pacote |
| `backend/app/leitura_pdf.py` | modo `paginas_texto` e `textos_por_pagina_com_limite` |
| `backend/app/arquivos.py` | `blocos_validados(arquivo, teto_bytes=..., tipo="pdf"|"xlsx")` |
| `backend/app/assinatura.py` | conferência do PDF assinado |
| `backend/app/protocolo.py` | famílias, etapas, criar, peças, carta, montar, assinado, pendências, prévia, envio |
| `backend/app/medicoes.py` | `registrar_protocolo(..., protocolo_id=None)` |
| `backend/app/correio.py` | `MAX_TOTAL = 35 MB` |
| `backend/app/cadastro_arquivos.py`, `cadastro_aplicar.py` | `cartas.yaml`; chaves novas do órgão; `objeto_completo`, `cno_pdf`, cargo/tratamento/portaria do fiscal; cópia de timbre e CNO para a pasta de dados |
| `backend/app/api_protocolos.py`, `main.py` | rotas |
| `cadastro/cartas.yaml`, `cadastro/modelos/carta/timbre-lotufo.png`, `cadastro/orgaos.yaml` | textos, timbre, peças e ordem por órgão |
| `frontend/src/Protocolo.tsx` (+ `.test.tsx`), `ContratoPagina.tsx` | fluxo na tela |
| `docs/levantamento-protocolo-2026-09-24.md`, `docs/runbook.md`, `docs/backlog.md` | levantamento, operação, pendências |

---

### Task 5.0: Levantamento (check-list da SINFRA, carta SINFRA real, timbre, textos reais)

Sem código. Resultado: `docs/levantamento-protocolo-2026-09-24.md`, usado na tarefa 5.11. Autorizado pela aprovação do plano (DT2 do índice): só baixar para o scratchpad e ler.

**Files:**
- Create: `docs/levantamento-protocolo-2026-09-24.md`

- [ ] **Step 1: Carta e texto da MTPAR e da SES, dos PDFs já baixados.** Pasta: `C:\Users\<usuario>\AppData\Local\Temp\claude\C--Users-<usuario>-Nova-Dashboard-Lotufo\9f83d3e0-c73a-4317-b8c9-19b94210004e\scratchpad\protocolos\`. Extrair o texto da página 1 (e 2, na SES) do CT-301 (MTPAR) e do CT/232 (SES) com o venv do projeto:

```bash
cd backend && .venv\Scripts\python -c "import pypdf,sys; r=pypdf.PdfReader(sys.argv[1]); print('\n=====\n'.join((p.extract_text() or '') for p in r.pages[:3]))" "<caminho do PDF>"
```

Copiar para o documento, **literalmente**, entre aspas: o parágrafo de qualificação, o parágrafo de encaminhamento, a lista de itens, o fecho e o bloco de assinatura de cada família. Anotar as variações de A/C (cargo "Engenheira Fiscal", "Fiscal de Obras") e de vocativo.

- [ ] **Step 2: Timbre.** Da página 1 do CT-301, extrair as imagens (`pypdf` `page.images`), escolher a do cabeçalho (a mais larga no topo) e a do rodapé, salvar em `cadastro/modelos/carta/timbre-lotufo.png` (e `rodape-lotufo.png` se houver). Conferir abrindo o PNG. Registrar no documento a largura em mm da imagem na página (para `carta.py` posicionar igual).

- [ ] **Step 3: SINFRA pelo Chrome da empresa.** Selecionar o navegador "Browser 1" (`list_connected_browsers`, `select_browser`); o login da Microsoft já está feito nele. No site `DepartamentodeEngenharia`, pasta da MT-388 (`.../4.003.025 - ...MT-388/OPERAÇÃO/02_PROJETO/`), baixar `IN001.2024 com anexos.pdf` pela API do SharePoint no próprio navegador (`fetch` de `/_api/web/GetFileByServerRelativePath(decodedurl='...')/$value` e download em JSON base64, como na carga das certidões de 23/09), e o PDF do protocolo SINFRA de medição mais recente que estiver na pasta de medições da MT-388 ou da Cavalaria (carta + boletim). Salvar no scratchpad. Do anexo da IN: **o check-list de protocolo de medição, item a item, na ordem**. Da carta SINFRA: estrutura e texto (mesma regra do step 1).

- [ ] **Step 4: Conclusão.** Na pasta da Orla (MTPAR), a carta `CT/245/LT/2026` (comunicação de conclusão): estrutura e texto, para o bloco 7.

- [ ] **Step 5: Escrever `docs/levantamento-protocolo-2026-09-24.md`** com: textos por família (citados, com a origem), ordem do check-list SINFRA, peças que cada órgão pede, o que ficou sem documento. Commit:

```bash
git add docs/levantamento-protocolo-2026-09-24.md cadastro/modelos/carta/
git commit -m "docs: levantamento do protocolo (textos reais, check-list SINFRA, timbre)"
```

---

### Task 5.1: Migração 025

**Files:**
- Create: `backend/migrations/025_protocolo.sql`
- Test: `backend/tests/test_migracao_025.py`

**Interfaces:**
- Produces: tabelas `protocolos`, `protocolo_medicoes`, `protocolo_pecas`; colunas `medicao_protocolos.protocolo_id`, `contratos.objeto_completo`, `contratos.cno_arquivo`, `contrato_fiscais.cargo`, `.tratamento`, `.portaria`.

- [ ] **Step 1: Teste**

```python
"""Migracao 025: protocolo feito pelo sistema (bloco 5)."""
from app import db


def _colunas(c, tabela):
    return {r[1] for r in c.execute(f"PRAGMA table_info({tabela})")}


def test_025_cria_tabelas_e_colunas_e_e_idempotente(tmp_path, monkeypatch):
    monkeypatch.setenv("DASH_DB_PATH", str(tmp_path / "t.db"))
    c = db.get_conn()
    db.migrate(c)
    db.migrate(c)                       # reexecucao nao falha nem duplica
    assert {"etapa", "natureza", "numero_oficio", "corpo_carta", "montado_arquivo", "assinado_arquivo",
            "conferencia", "envio_id", "justificativa", "numero_orgao", "situacao"} <= _colunas(c, "protocolos")
    assert {"protocolo_id", "medicao_id"} <= _colunas(c, "protocolo_medicoes")
    assert {"tipo", "nome", "arquivo", "sha256", "tamanho", "ext", "removida_em"} <= _colunas(c, "protocolo_pecas")
    assert "protocolo_id" in _colunas(c, "medicao_protocolos")
    assert {"objeto_completo", "cno_arquivo"} <= _colunas(c, "contratos")
    assert {"cargo", "tratamento", "portaria"} <= _colunas(c, "contrato_fiscais")
    c.close()
```

- [ ] **Step 2:** `.venv\Scripts\python -m pytest tests/test_migracao_025.py -q` → FAIL (tabela não existe).

- [ ] **Step 3: Migração**

```sql
-- 025: protocolo de medicao feito pelo sistema (bloco 5; spec 2026-09-21 §3 passos 4 a 7, §5.3, §5.4, §6).
-- Um protocolo = um documento a assinar = um oficio. Um envio (e-mail) pode levar varios protocolos
-- (SINFRA: execucao e reajuste no mesmo e-mail, em PDFs separados). Aditiva: nada reconstruido.
CREATE TABLE IF NOT EXISTS protocolos (
    id INTEGER PRIMARY KEY,
    contrato_id INTEGER NOT NULL REFERENCES contratos(id),
    etapa TEXT NOT NULL CHECK (etapa IN ('unico','medicao','nota')),
    natureza TEXT NOT NULL CHECK (natureza IN ('execucao','reajuste','projeto')),
    numero_oficio TEXT,
    corpo_carta TEXT,
    montado_arquivo TEXT,
    montado_sha256 TEXT,
    montado_paginas INTEGER,
    montado_em TEXT,
    assinado_arquivo TEXT,
    assinado_sha256 TEXT,
    assinado_em TEXT,
    conferencia TEXT,
    envio_id INTEGER REFERENCES envios(id),
    justificativa TEXT,
    numero_orgao TEXT,
    comprovante_arquivo TEXT,
    situacao TEXT NOT NULL DEFAULT 'rascunho'
        CHECK (situacao IN ('rascunho','montado','assinado','enviado','descartado')),
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id),
    criado_em TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS protocolos_contrato ON protocolos(contrato_id);

CREATE TABLE IF NOT EXISTS protocolo_medicoes (
    protocolo_id INTEGER NOT NULL REFERENCES protocolos(id),
    medicao_id INTEGER NOT NULL REFERENCES medicoes(id),
    PRIMARY KEY (protocolo_id, medicao_id)
);

-- Pecas tecnicas arrastadas (boletim, planilha editavel, diario, fotos...). Removida e' marcada.
CREATE TABLE IF NOT EXISTS protocolo_pecas (
    id INTEGER PRIMARY KEY,
    protocolo_id INTEGER NOT NULL REFERENCES protocolos(id),
    tipo TEXT NOT NULL,
    nome TEXT NOT NULL,
    arquivo TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    tamanho INTEGER NOT NULL,
    ext TEXT NOT NULL CHECK (ext IN ('pdf','xlsx')),
    removida_em TEXT,
    criado_em TEXT NOT NULL DEFAULT (datetime('now'))
);

ALTER TABLE medicao_protocolos ADD COLUMN protocolo_id INTEGER REFERENCES protocolos(id);
ALTER TABLE contratos ADD COLUMN objeto_completo TEXT;
ALTER TABLE contratos ADD COLUMN cno_arquivo TEXT;
ALTER TABLE contrato_fiscais ADD COLUMN cargo TEXT;
ALTER TABLE contrato_fiscais ADD COLUMN tratamento TEXT;
ALTER TABLE contrato_fiscais ADD COLUMN portaria TEXT;
```

- [ ] **Step 4:** rodar o teste → PASS.
- [ ] **Step 5: Commit** `git add backend/migrations/025_protocolo.sql backend/tests/test_migracao_025.py` + `git commit -m "feat: migracao 025 do protocolo"`.

---

### Task 5.2: Carta, capa e divisória em PDF (`carta.py`, fpdf2)

**Files:**
- Modify: `backend/pyproject.toml`, `backend/requirements.lock`
- Create: `backend/app/carta.py`
- Test: `backend/tests/test_carta.py`

**Interfaces:**
- Produces: `Carta(numero, local_data, destinatario, ac, referencia, assunto, vocativo, corpo, assinatura, emitente={})`; `gerar(c: Carta) -> bytes`; `pagina_titulo(linhas: list[str], emitente: dict | None = None) -> bytes`; `data_extenso(d: date) -> str`; `preencher(modelo: str, campos: dict) -> str`. As funções que leem o banco (`config`, `emitente`, `fiscal_vigente`) entram na tarefa 5.6.

- [ ] **Step 1: Dependência.** `.venv\Scripts\python -m pip install fpdf2==2.8.8`. Em `pyproject.toml`, depois do `pypdfium2`:

```toml
    # Carta, capa e divisoria do protocolo em PDF (app/carta.py, bloco 5): nao existe modelo Word
    # de carta nem conversao Word->PDF no servidor. PINADO EXATO: o desenho do PDF e' conferido por
    # texto na assinatura (app/assinatura.py).
    "fpdf2==2.8.8",
```

Em `requirements.lock`, acrescentar as linhas que o `pip install` trouxe, com a versão instalada de cada (`pip freeze | findstr /i "fpdf2 pillow fonttools defusedxml"`), em ordem alfabética.

- [ ] **Step 2: Testes**

```python
"""Carta, capa e divisoria em PDF (bloco 5)."""
import datetime
import io

import pypdf

from app import carta


def _texto(pdf: bytes) -> str:
    return "\n".join(p.extract_text() or "" for p in pypdf.PdfReader(io.BytesIO(pdf)).pages)


def _carta(**mudar):
    base = dict(numero="CT/301/LT/2026", local_data="Cuiabá/MT, 16 de setembro de 2026.",
                destinatario=["A MT PARTICIPAÇÕES E PROJETOS S.A – MT-PAR"],
                ac=["A/C: Fiscal Exemplo", "Engenheira Fiscal"],
                referencia="Ref.: Contrato n.º 099/2024/MTPAR – Complexo Cultural",
                assunto="Asst.: 23ª Medição contratual (01/08/2026 a 31/08/2026)",
                vocativo="Prezada Senhora,",
                corpo="A LOTUFO encaminha os arquivos da 23ª Medição:\n\ni. Nota fiscal – NF nº 2311\n"
                      "ii. Certidões de regularidade fiscal\n\n# 2. DO PEDIDO\n\nCertos de contar com a usual brevidade.",
                assinatura=["Diretor Exemplo", "Diretor"])
    base.update(mudar)
    return carta.Carta(**base)


def test_carta_leva_os_dados_e_as_marcas_do_corpo():
    t = _texto(carta.gerar(_carta()))
    for trecho in ("CT/301/LT/2026", "16 de setembro de 2026", "A/C: Fiscal Exemplo", "Contrato n.º 099/2024/MTPAR",
                   "23ª Medição contratual", "i. Nota fiscal", "ii. Certidões", "2. DO PEDIDO", "Diretor Exemplo"):
        assert trecho in t, trecho
    assert "# 2." not in t                        # a marca de titulo nao vai para o papel


def test_sem_arial_cai_na_helvetica_sem_quebrar(monkeypatch, tmp_path):
    monkeypatch.setattr(carta, "_ARIAL", tmp_path / "nao-existe.ttf")
    t = _texto(carta.gerar(_carta()))
    assert "MT-PAR" in t and "CT/301/LT/2026" in t


def test_pagina_titulo_e_data_extenso_e_preencher():
    assert "NOTA FISCAL" in _texto(carta.pagina_titulo(["NOTA FISCAL"]))
    assert carta.data_extenso(datetime.date(2026, 9, 16)) == "16 de setembro de 2026"
    assert carta.preencher("{medicao} de {obra} ({faltou})", {"medicao": "23ª Medição", "obra": "Cultural"}) \
        == "23ª Medição de Cultural ({faltou})"
```

- [ ] **Step 3:** `.venv\Scripts\python -m pytest tests/test_carta.py -q` → FAIL (módulo não existe).

- [ ] **Step 4: Implementação**

```python
"""Carta, capa e divisoria em PDF (bloco 5; reusado pelos oficios do bloco 7).

Nao existe modelo Word de carta de protocolo (levantamento de 2026-09-24) nem conversao Word->PDF no
servidor: a carta e' desenhada aqui (fpdf2). O texto fixo vem do cadastro (`cadastro/cartas.yaml`,
aplicado em `cadastro_geral['cartas']`); o timbre e' imagem recortada de carta real, copiada para a
pasta de dados pelo `cadastro aplicar`.

O CORPO e' texto simples com tres marcas, e e' o que a pessoa edita na previa: linha em branco separa
paragrafos; linha comecando por "# " e' titulo de secao (negrito); linha comecando por "i. ", "ii. ",
"1. " etc. e' item de lista (recuado).
"""
import datetime
import re
from dataclasses import dataclass, field
from pathlib import Path

from fpdf import FPDF

from app import arquivos

MESES = ("janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro",
         "outubro", "novembro", "dezembro")
_ARIAL = Path(r"C:\Windows\Fonts\arial.ttf")
_ARIAL_NEGRITO = Path(r"C:\Windows\Fonts\arialbd.ttf")
_ITEM = re.compile(r"^((?:[ivxlc]+|\d{1,2}))\.\s+(.*)$", re.IGNORECASE)
_TROCAS_LATIN1 = {"–": "-", "—": "-", "“": '"', "”": '"', "‘": "'", "’": "'", "…": "..."}
ALTURA = 5.5


def data_extenso(d: datetime.date) -> str:
    return f"{d.day} de {MESES[d.month - 1]} de {d.year}"


class _Campos(dict):
    def __missing__(self, chave):           # campo que o dado nao tem fica visivel, nao quebra
        return "{" + chave + "}"


def preencher(modelo: str, campos: dict) -> str:
    return modelo.format_map(_Campos(campos))


@dataclass
class Carta:
    numero: str
    local_data: str
    destinatario: list[str]
    ac: list[str]
    referencia: str
    assunto: str
    vocativo: str
    corpo: str
    assinatura: list[str]
    emitente: dict = field(default_factory=dict)   # razao_social, cnpj, endereco, timbre (rel. a pasta de dados)


class _Doc(FPDF):
    def __init__(self, emitente: dict | None):
        super().__init__(format="A4")
        self.emitente = emitente or {}
        self.set_margins(25, 20, 20)
        self.set_auto_page_break(True, margin=22)
        if _ARIAL.is_file() and _ARIAL_NEGRITO.is_file():
            self.add_font("Carta", "", str(_ARIAL))
            self.add_font("Carta", "B", str(_ARIAL_NEGRITO))
            self.fonte, self.unicode = "Carta", True
        else:
            self.fonte, self.unicode = "Helvetica", False

    def t(self, s: str) -> str:
        if self.unicode:
            return s
        for de, para in _TROCAS_LATIN1.items():
            s = s.replace(de, para)
        return s.encode("latin-1", "replace").decode("latin-1")

    def header(self):
        rel = self.emitente.get("timbre")
        if rel:
            try:
                p = arquivos.caminho_seguro(rel)
            except ValueError:
                p = None
            if p is not None and p.is_file():
                self.image(str(p), x=20, y=8, w=170)
                self.set_y(40)
                return
        if self.emitente.get("razao_social"):
            self.set_font(self.fonte, "B", 11)
            self.cell(0, 5, self.t(self.emitente["razao_social"]), new_x="LMARGIN", new_y="NEXT", align="C")
            partes = [self.emitente.get("endereco"),
                      f"CNPJ {self.emitente['cnpj']}" if self.emitente.get("cnpj") else None]
            linha = " | ".join(x for x in partes if x)
            if linha:
                self.set_font(self.fonte, "", 8)
                self.cell(0, 4, self.t(linha), new_x="LMARGIN", new_y="NEXT", align="C")
            self.ln(6)

    def linha(self, texto: str, estilo: str = "", align: str = "L"):
        self.set_font(self.fonte, estilo, 11)
        self.multi_cell(0, ALTURA, self.t(texto), align=align, new_x="LMARGIN", new_y="NEXT")


def _corpo(pdf: _Doc, corpo: str) -> None:
    for bloco in re.split(r"\n\s*\n", (corpo or "").strip()):
        for bruta in bloco.splitlines():
            linha = bruta.strip()
            if not linha:
                continue
            if linha.startswith("# "):
                pdf.ln(2)
                pdf.linha(linha[2:].strip(), "B")
            elif (m := _ITEM.match(linha)):
                pdf.set_x(pdf.l_margin + 8)
                pdf.set_font(pdf.fonte, "", 11)
                pdf.multi_cell(0, ALTURA, pdf.t(f"{m.group(1)}. {m.group(2)}"), new_x="LMARGIN", new_y="NEXT")
            else:
                pdf.linha(linha, align="J")
        pdf.ln(3)


def gerar(c: Carta) -> bytes:
    pdf = _Doc(c.emitente)
    pdf.add_page()
    pdf.linha(c.numero, "B")
    pdf.linha(c.local_data, align="R")
    pdf.ln(4)
    for l in c.destinatario:
        pdf.linha(l, "B")
    for l in c.ac:
        pdf.linha(l)
    pdf.ln(3)
    pdf.linha(c.referencia, "B")
    pdf.linha(c.assunto, "B")
    pdf.ln(4)
    pdf.linha(c.vocativo)
    pdf.ln(2)
    _corpo(pdf, c.corpo)
    pdf.ln(12)
    for i, l in enumerate(c.assinatura):
        pdf.set_font(pdf.fonte, "B" if i == 0 else "", 11)
        pdf.cell(0, ALTURA, pdf.t(l), new_x="LMARGIN", new_y="NEXT", align="C")
    return bytes(pdf.output())


def pagina_titulo(linhas: list[str], emitente: dict | None = None) -> bytes:
    """Capa ou divisoria (SES): linhas em negrito, centralizadas no meio da pagina."""
    pdf = _Doc(emitente)
    pdf.add_page()
    pdf.set_y(120)
    for l in linhas:
        pdf.set_font(pdf.fonte, "B", 20)
        pdf.multi_cell(0, 11, pdf.t(l), align="C", new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())
```

- [ ] **Step 5:** rodar `tests/test_carta.py` → PASS.
- [ ] **Step 6: Commit** `git add backend/pyproject.toml backend/requirements.lock backend/app/carta.py backend/tests/test_carta.py` + `git commit -m "feat: carta, capa e divisoria em PDF (fpdf2)"`.

---

### Task 5.3: Número do ofício (`oficios.py`)

**Files:**
- Create: `backend/app/oficios.py`
- Test: `backend/tests/test_oficios.py`

**Interfaces:**
- Produces: `canonico(digitado: str, sigla: str | None, ano: int) -> str` (`"CT-301-LT-2026"`; entidade sem sigla: `"CARTA-048-2026"`); `na_carta(canon: str) -> str` (`"CT/301/LT/2026"`, `"CARTA Nº 048/2026"`); `usos(conn, canon: str, ignorar: tuple[str, int] | None = None) -> list[str]` (descrições dos outros documentos com o mesmo número; o bloco 7 acrescenta os pleitos).

- [ ] **Step 1: Testes**

```python
"""Numero do oficio (spec §5.4): digitado, canonico, com aviso de repetido."""
import pytest

from app import auth, db, oficios


def test_canonico_aceita_as_formas_digitadas():
    for digitado in ("301", "CT 301", "CT-301-LT-2026", "CT/301/LT/2026", "ct nº 301"):
        assert oficios.canonico(digitado, "LT", 2026) == "CT-301-LT-2026"
    assert oficios.canonico("68", "LT", 2026) == "CT-068-LT-2026"
    assert oficios.canonico("CT/122/LT/2025", "LT", 2026) == "CT-122-LT-2025"   # ano digitado manda
    assert oficios.canonico("48", None, 2026) == "CARTA-048-2026"
    with pytest.raises(ValueError):
        oficios.canonico("sem numero", "LT", 2026)


def test_na_carta():
    assert oficios.na_carta("CT-301-LT-2026") == "CT/301/LT/2026"
    assert oficios.na_carta("CARTA-048-2026") == "CARTA Nº 048/2026"


def test_usos_acha_protocolo_com_o_mesmo_numero(tmp_path, monkeypatch):
    monkeypatch.setenv("DASH_DB_PATH", str(tmp_path / "t.db"))
    c = db.get_conn(); db.migrate(c)
    uid = auth.criar_usuario(c, "U", "u@lotufo.com", "senha-forte-123", "admin")
    c.execute("INSERT INTO contratos (id, numero, objeto, estado, nome_curto) VALUES (1,'X','Obra','ativo','Obra')")
    c.execute("INSERT INTO protocolos (contrato_id, etapa, natureza, numero_oficio, usuario_id) "
              "VALUES (1,'unico','execucao','CT-301-LT-2026',?)", (uid,))
    c.commit()
    assert oficios.usos(c, "CT-301-LT-2026") and not oficios.usos(c, "CT-302-LT-2026")
    assert oficios.usos(c, "CT-301-LT-2026", ignorar=("protocolo", 1)) == []
```

(Se o `INSERT INTO contratos` do teste falhar por coluna obrigatória, usar o helper de contrato de `tests/test_documentos.py`, que monta contrato com órgão; o teste é sobre `usos`, não sobre contrato.)

- [ ] **Step 2:** rodar → FAIL.

- [ ] **Step 3: Implementação**

```python
"""Numero do oficio (spec §5.4): digitado a mao, porque o contador e' da empresa inteira e vive fora do
sistema. O sistema so' normaliza ("301" -> "CT-301-LT-2026") e AVISA quando o numero ja' foi usado,
sem travar."""
import re

_NUMERO = re.compile(r"(?<!\d)(\d{1,4})(?!\d)")
_ANO = re.compile(r"(?<!\d)(20\d{2})(?!\d)")


def canonico(digitado: str, sigla: str | None, ano: int) -> str:
    texto = str(digitado or "")
    anos = _ANO.findall(texto)
    sem_ano = _ANO.sub(" ", texto)
    m = _NUMERO.search(sem_ano)
    if m is None:
        raise ValueError("Informe o número do ofício (ex.: 301)")
    n, a = int(m.group(1)), int(anos[-1]) if anos else ano
    return f"CT-{n:03d}-{sigla}-{a}" if sigla else f"CARTA-{n:03d}-{a}"


def na_carta(canon: str) -> str:
    if canon.startswith("CARTA-"):
        _, n, a = canon.split("-")
        return f"CARTA Nº {n}/{a}"
    return canon.replace("-", "/")


def usos(conn, canon: str, ignorar: tuple[str, int] | None = None) -> list[str]:
    out = []
    for r in conn.execute(
            "SELECT p.id, c.nome_curto, c.numero FROM protocolos p JOIN contratos c ON c.id=p.contrato_id "
            "WHERE p.numero_oficio=? AND p.situacao<>'descartado' ORDER BY p.id", (canon,)):
        if ignorar == ("protocolo", r["id"]):
            continue
        out.append(f"protocolo {r['id']} ({r['nome_curto'] or r['numero']})")
    return out
```

- [ ] **Step 4:** rodar → PASS. **Step 5: Commit** `feat: numero do oficio canonico e aviso de repetido`.

---

### Task 5.4: Juntar PDF, texto por página e upload com teto por rota

**Files:**
- Create: `backend/app/pdfs.py`
- Modify: `backend/app/leitura_pdf.py` (modo `paginas_texto`), `backend/app/arquivos.py` (`blocos_validados` com `teto_bytes` e `tipo`)
- Test: `backend/tests/test_pdfs.py`, `backend/tests/test_arquivos.py` (acrescentar um teste)

**Interfaces:**
- Produces: `pdfs.juntar(partes: list[bytes]) -> bytes`; `pdfs.paginas(pdf: bytes) -> int`; `pdfs.TETO_BYTES_PACOTE = 40 MB`; `pdfs.TETO_PAGINAS_PACOTE = 400`; `leitura_pdf.textos_por_pagina_com_limite(pdf: bytes, teto_paginas: int = 400) -> list[str]`; `arquivos.blocos_validados(arquivo, teto_bytes: int = TETO_BYTES, tipo: str = "pdf")` (`tipo="xlsx"` aceita planilha: content-type do Excel ou `application/octet-stream`, assinatura `PK\x03\x04`).

- [ ] **Step 1: Testes**

```python
"""Juntar PDF e texto por pagina (bloco 5)."""
from app import carta, leitura_pdf, pdfs


def test_juntar_preserva_a_ordem_e_o_texto_por_pagina():
    a = carta.pagina_titulo(["PRIMEIRA"])
    b = carta.pagina_titulo(["SEGUNDA"])
    junto = pdfs.juntar([a, b, a])
    assert pdfs.paginas(junto) == 3
    textos = leitura_pdf.textos_por_pagina_com_limite(junto)
    assert ["PRIMEIRA" in textos[0], "SEGUNDA" in textos[1], "PRIMEIRA" in textos[2]] == [True, True, True]


def test_texto_por_pagina_respeita_o_teto_de_paginas():
    import pytest
    junto = pdfs.juntar([carta.pagina_titulo(["X"])] * 3)
    with pytest.raises(leitura_pdf.TextoInadequado):
        leitura_pdf.textos_por_pagina_com_limite(junto, teto_paginas=2)
```

Em `tests/test_arquivos.py` (se não existir, criar), um teste de `blocos_validados` com `tipo="xlsx"` usando `UploadFile` de `starlette.datastructures` sobre `io.BytesIO(b"PK\x03\x04" + b"x" * 10)` com header `content-type` do Excel: consome sem erro; e o mesmo conteúdo com `tipo="pdf"` levanta `HTTPException` 415.

- [ ] **Step 2:** rodar → FAIL.

- [ ] **Step 3: `pdfs.py`**

```python
"""Montagem de PDF do protocolo (bloco 5). Juntar e contar sao pypdf sobre PDF que o proprio sistema
gerou ou ja' validou (notas, certidoes, pecas passaram por `arquivos.blocos_validados` e pelo
subprocesso); ler PDF de fora continua so' em `leitura_pdf`, no subprocesso com limite."""
import io

import pypdf

TETO_BYTES_PACOTE = 40 * 1024 * 1024     # a 42ª de Alta Floresta (SES) tem 10,9 MB e 114 paginas
TETO_PAGINAS_PACOTE = 400


def juntar(partes: list[bytes]) -> bytes:
    w = pypdf.PdfWriter()
    for p in partes:
        w.append(io.BytesIO(p))
    buf = io.BytesIO()
    w.write(buf)
    return buf.getvalue()


def paginas(pdf: bytes) -> int:
    return len(pypdf.PdfReader(io.BytesIO(pdf)).pages)
```

- [ ] **Step 4: `leitura_pdf.py`** (junto das constantes do OCR):

```python
# Pacote de protocolo (bloco 5): conferencia do assinado le o texto de CADA pagina de um PDF grande.
TEMPO_PACOTE_S = 60.0
TETO_CARACTERES_PAGINA = 20_000
```

função (antes de `_trabalho`):

```python
def textos_por_pagina(pdf: bytes, teto_paginas: int) -> list[str]:
    """Texto de cada pagina (pagina so' de imagem vem vazia). Roda no filho de `com_limite`."""
    paginas = leitor_de_pdf(pdf).pages
    if len(paginas) > teto_paginas:
        raise TextoInadequado(f"O PDF tem {len(paginas)} páginas, acima do limite de {teto_paginas} "
                              f"— confira o arquivo.")
    return [(p.extract_text() or "")[:TETO_CARACTERES_PAGINA] for p in paginas]
```

em `_trabalho`, novo ramo:

```python
        elif modo == "paginas_texto":
            valor = textos_por_pagina(pdf, opcoes)
```

e no fim do arquivo:

```python
def textos_por_pagina_com_limite(pdf: bytes, teto_paginas: int = 400) -> list[str]:
    """`textos_por_pagina` em subprocesso, com o prazo do pacote (ver `com_limite`)."""
    return com_limite(pdf, "paginas_texto", TEMPO_PACOTE_S, teto_paginas)
```

- [ ] **Step 5: `arquivos.py`.** `blocos_validados(arquivo: UploadFile, teto_bytes: int = TETO_BYTES, tipo: str = "pdf")`: para `tipo == "xlsx"`, aceitar content-type `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` ou `application/octet-stream` e exigir que o primeiro bloco comece por `b"PK\x03\x04"` (mensagem 415: "O arquivo não é uma planilha .xlsx"); o contador usa `teto_bytes` e a mensagem 413 diz `teto_bytes // (1024 * 1024)` MB. O comportamento padrão (PDF, 10 MB) não muda.
- [ ] **Step 6:** rodar `tests/test_pdfs.py tests/test_arquivos.py tests/test_leitura_pdf.py` → PASS.
- [ ] **Step 7: Commit** `feat: juntar PDF, texto por pagina e upload com teto por rota`.

---

### Task 5.5: Conferência do PDF assinado (`assinatura.py`)

**Files:**
- Create: `backend/app/assinatura.py`
- Test: `backend/tests/test_assinatura.py`

**Interfaces:**
- Consumes: `leitura_pdf.textos_por_pagina_com_limite`.
- Produces: `conferir(montado: list[str], assinado: list[str]) -> dict` com `{"ok": bool, "avisos": [{"codigo", "mensagem"}], "envelope": str | None, "paginas_montado": int, "paginas_assinado": int, "certificado": int}`; `conferir_pdfs(montado_pdf: bytes, assinado_pdf: bytes) -> dict`. Códigos: `nao_assinado`, `sem_carimbo`, `envelopes_diferentes`, `paginas_a_menos`, `pagina_diferente`, `paginas_extras`.

- [ ] **Step 1: Testes** (páginas como texto; o PDF real entra na prova da tarefa 5.11)

```python
"""Conferencia do PDF assinado (spec §6): paginas batem, extras so' certificado, carimbo em todas."""
from app import assinatura

G1 = "7E965481-0A1B-4C2D-8E9F-0123456789AB"
G2 = "C923C2B0-1111-2222-3333-444455556666"
MONTADO = ["CT/301/LT/2026 Cuiabá 16 de setembro Ref.: Contrato 099/2024 23ª Medição", "NOTA FISCAL 2311 valor 1.234,56", ""]


def _carimbar(paginas, guid=G1):
    return [f"Docusign Envelope ID: {guid}\n{t}" for t in paginas]


def test_assinado_certo_passa():
    r = assinatura.conferir(MONTADO, _carimbar(MONTADO))
    assert r["ok"] and r["envelope"] == G1 and r["avisos"] == []


def test_pdf_nao_assinado_e_pego():
    r = assinatura.conferir(MONTADO, MONTADO)
    assert not r["ok"] and [a["codigo"] for a in r["avisos"]] == ["nao_assinado"]


def test_pagina_trocada_e_pega():
    trocado = _carimbar([MONTADO[0], "OUTRA COISA COMPLETAMENTE DIFERENTE", ""])
    r = assinatura.conferir(MONTADO, trocado)
    assert any(a["codigo"] == "pagina_diferente" and "2" in a["mensagem"] for a in r["avisos"])


def test_certificado_no_fim_e_aceito_e_pagina_extra_qualquer_nao():
    cert = "Certificado de Conclusão\nIdentificação de envelope: " + G1
    assert assinatura.conferir(MONTADO, _carimbar(MONTADO) + [cert])["ok"]
    r = assinatura.conferir(MONTADO, _carimbar(MONTADO) + ["pagina solta"])
    assert [a["codigo"] for a in r["avisos"]] == ["paginas_extras"]


def test_envelopes_diferentes_e_paginas_a_menos():
    misturado = _carimbar(MONTADO[:2]) + _carimbar(MONTADO[2:], G2)
    assert "envelopes_diferentes" in [a["codigo"] for a in assinatura.conferir(MONTADO, misturado)["avisos"]]
    assert "paginas_a_menos" in [a["codigo"] for a in assinatura.conferir(MONTADO, _carimbar(MONTADO[:2]))["avisos"]]
```

- [ ] **Step 2:** rodar → FAIL.

- [ ] **Step 3: Implementação**

```python
"""Conferencia do PDF assinado no DocuSign (spec 2026-09-21 §6), por AVISO.

Tres regras, sobre o texto de cada pagina (o carimbo do DocuSign sai como texto extraivel):
(1) as N primeiras paginas do assinado batem com as N do pacote montado, ignorando o carimbo;
(2) paginas a mais no fim so' se forem o "Certificado de Conclusao" do DocuSign;
(3) todas as N paginas tem o carimbo "Docusign Envelope ID: <GUID>", o mesmo em todas.
Pega pagina trocada e, sobretudo, PDF que ainda nao foi assinado (o CT-286 da Orla foi protocolado
sem nenhuma pagina carimbada). Comparacao por semelhanca e nao por igualdade: o DocuSign reescreve o
PDF e o extrator devolve espacos e quebras diferentes.
"""
import re
import unicodedata
from difflib import SequenceMatcher

from app import leitura_pdf, pdfs

LIMIAR = 0.90
_ENVELOPE = re.compile(r"DOCUSIGN\s+ENVELOPE\s+ID\s*:?\s*([0-9A-F]{8}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{12})",
                       re.IGNORECASE)
_CERTIFICADO = re.compile(r"CERTIFICADO\s+DE\s+CONCLUS|CERTIFICATE\s+OF\s+COMPLETION", re.IGNORECASE)


def _plano(texto: str) -> str:
    t = _ENVELOPE.sub(" ", texto or "")
    t = "".join(unicodedata.normalize("NFKD", c)[:1] for c in t)
    return re.sub(r"[^0-9A-Z]", "", t.upper())


def _lista(paginas: list[int]) -> str:
    return ", ".join(str(p) for p in paginas[:12]) + (" …" if len(paginas) > 12 else "")


def conferir(montado: list[str], assinado: list[str]) -> dict:
    n, a = len(montado), len(assinado)
    avisos = []
    comum = min(n, a)
    if a < n:
        avisos.append({"codigo": "paginas_a_menos",
                       "mensagem": f"O assinado tem {a} páginas; o pacote montado tem {n}."})
    diferentes = []
    for i in range(comum):
        m, s = _plano(montado[i]), _plano(assinado[i])
        if not m and not s:
            continue
        if not m or not s or SequenceMatcher(None, m, s, autojunk=False).ratio() < LIMIAR:
            diferentes.append(i + 1)
    if diferentes:
        avisos.append({"codigo": "pagina_diferente",
                       "mensagem": f"Página(s) {_lista(diferentes)} do assinado não batem com o pacote montado."})
    extras = [n + 1 + j for j, t in enumerate(assinado[n:]) if not _CERTIFICADO.search((t or "")[:400])]
    if extras:
        avisos.append({"codigo": "paginas_extras",
                       "mensagem": f"Página(s) {_lista(extras)} a mais no fim, que não são o certificado do DocuSign."})
    ids = [(_ENVELOPE.search(assinado[i] or "") or [None, None])[1] for i in range(comum)]
    sem = [i + 1 for i, g in enumerate(ids) if not g]
    if comum and len(sem) == comum:
        avisos.append({"codigo": "nao_assinado",
                       "mensagem": "Nenhuma página tem o carimbo do DocuSign: o PDF parece não assinado."})
    elif sem:
        avisos.append({"codigo": "sem_carimbo", "mensagem": f"Página(s) {_lista(sem)} sem o carimbo do DocuSign."})
    distintos = {g.upper() for g in ids if g}
    if len(distintos) > 1:
        avisos.append({"codigo": "envelopes_diferentes",
                       "mensagem": f"O carimbo traz {len(distintos)} envelopes diferentes."})
    return {"ok": not avisos, "avisos": avisos, "envelope": next(iter(distintos)) if len(distintos) == 1 else None,
            "paginas_montado": n, "paginas_assinado": a, "certificado": a - n - len(extras) if a > n else 0}


def conferir_pdfs(montado_pdf: bytes, assinado_pdf: bytes) -> dict:
    teto = pdfs.TETO_PAGINAS_PACOTE
    return conferir(leitura_pdf.textos_por_pagina_com_limite(montado_pdf, teto),
                    leitura_pdf.textos_por_pagina_com_limite(assinado_pdf, teto))
```

- [ ] **Step 4:** rodar → PASS. Se `test_pagina_trocada` passar mas `test_assinado_certo` falhar, o problema é o `_plano` (conferir que o carimbo sai inteiro); não baixar o `LIMIAR` por causa de teste sintético: ele é calibrado com os PDFs reais na tarefa 5.11.
- [ ] **Step 5: Commit** `feat: conferencia do PDF assinado no DocuSign`.

---

### Task 5.6: Cadastro (cartas, órgão, contrato, fiscal) e leitura para a carta

**Files:**
- Create: `cadastro/cartas.yaml` (versão inicial, trocada pelos textos reais na 5.11)
- Modify: `backend/app/cadastro_arquivos.py`, `backend/app/cadastro_aplicar.py`, `backend/app/carta.py` (funções que leem o banco)
- Test: `backend/tests/test_cadastro_arquivos.py`, `backend/tests/test_cadastro_aplicar.py`, `backend/tests/test_carta.py`

**Interfaces:**
- Produces:
  - `cadastro_geral['cartas']` (JSON), com `signatario`, `emitentes` (por chave de entidade; `timbre` vira caminho relativo na pasta de dados) e `familias.<familia>.{email_assunto, email_corpo, carta_assunto, carta_corpo}` (e, no bloco 7, `pleito_reajuste`, `prazo`, `conclusao`).
  - Novas chaves do órgão, guardadas em `orgaos.regras` e validadas:
    - `carta_destinatario: [linhas]`;
    - `pecas: [{tipo, rotulo, exigida, solto}]`;
    - `ordem_certidoes: [chaves]`.
  - `contratos.objeto_completo`; `contratos.cno_arquivo`; `contrato_fiscais.cargo`, `.tratamento` (`Senhor`/`Senhora`) e `.portaria`.
  - `carta.config(conn) -> dict`.
  - `carta.emitente(conn, entidade_id) -> dict`.
  - `carta.fiscal_vigente(conn, contrato_id, na_data: str) -> dict | None`.

- [ ] **Step 1: `cadastro/cartas.yaml` inicial**

```yaml
# Textos das cartas geradas pelo sistema (bloco 5; spec §5.2, §6). Placeholders: {razao_social} {cnpj}
# {oficio} {medicao} {periodo} {competencia} {obra} {instrumento} {objeto} {orgao} {lista} {saudacao}.
# {lista} e' montada pelo sistema (notas com numero e valor, certidoes, pecas) no estilo da familia.
# Textos reais copiados das cartas de 2026 na tarefa 5.11 (levantamento em docs/levantamento-protocolo-2026-09-24.md).
signatario: [Diretor Exemplo, Diretor, CREA 0000000000]
emitentes:
  lotufo:
    razao_social: LOTUFO ENGENHARIA E CONSTRUÇÕES LTDA
    cnpj: 00.000.000/0001-00
    endereco: Cuiabá/MT
    timbre: modelos/carta/timbre-lotufo.png
familias:
  mtpar:
    email_assunto: '{oficio} - {medicao} - {obra}'
    email_corpo: |
      {saudacao}

      Encaminho arquivo para protocolo.

      Solicito, por favor, devolutiva com os dados (nº de protocolo) sob os quais o arquivo seja protocolado.

      Atenciosamente,
    carta_assunto: 'Asst.: {medicao} contratual ({periodo})'
    carta_corpo: |
      A {razao_social}, inscrita no CNPJ sob o nº {cnpj}, utiliza-se da presente para encaminhar os arquivos relativos à {medicao} contratual, período {periodo}, conforme abaixo elencado:

      {lista}

      Certos de contar com a usual brevidade no atendimento, colocamo-nos à disposição para eventuais esclarecimentos.

      Atenciosamente,
  ses:
    email_assunto: '{medicao} ({periodo}) - {instrumento} - {obra}'
    email_corpo: |
      {saudacao}

      Encaminho, em anexo, arquivo para protocolo.

      Atenciosamente,
    carta_assunto: 'Asst.: Encaminhamento da {medicao}'
    carta_corpo: |
      A {razao_social}, inscrita no CNPJ sob o nº {cnpj}, vem encaminhar os documentos referentes à {medicao}, período {periodo}:

      {lista}

      Sem mais para o momento, subscrevemo-nos.

      Atenciosamente,
  sinfra:
    email_assunto: '{oficio} - {medicao} ({competencia}) - {instrumento} - {obra}'
    email_corpo: |
      {saudacao}

      Encaminho arquivo para protocolo.

      Encaminho ainda arquivos editáveis para envio à supervisora e à fiscalização.

      Atenciosamente,
    carta_assunto: 'Asst.: {medicao} ({periodo})'
    carta_corpo: |
      A {razao_social}, inscrita no CNPJ sob o nº {cnpj}, vem respeitosamente encaminhar a {medicao}, referente ao período {periodo}, para análise e aprovação:

      {lista}

      Sem mais para o momento, subscrevemo-nos.

      Atenciosamente,
    nota_email_assunto: 'Nota fiscal - {medicao} ({competencia}) - {instrumento} - {obra}'
    nota_email_corpo: |
      {saudacao}

      Encaminho nota fiscal, certidões e documentos de regularidade para protocolo.

      Atenciosamente,
  prefeitura:
    email_assunto: '{oficio} - Encaminha Notas Fiscais - {medicao} ({competencia}) - {obra}'
    email_corpo: |
      {saudacao}

      Encaminho, em anexo, nota fiscal e documentos para protocolo.

      Atenciosamente,
    carta_assunto: 'Asst.: Encaminhamento de nota fiscal - {medicao}'
    carta_corpo: |
      A {razao_social}, inscrita no CNPJ sob o nº {cnpj}, encaminha os documentos da {medicao}, período {periodo}:

      {lista}

      Atenciosamente,
```

- [ ] **Step 2: Testes de cadastro** (em `test_cadastro_arquivos.py`, no padrão dos vizinhos, que montam uma raiz de cadastro em `tmp_path`):
  - `cartas.yaml` ausente → `preparar` continua passando (cadastros antigos e testes).
  - `cartas.yaml` com `familias.<x>` fora de `mtpar/ses/sinfra/prefeitura` → erro. Timbre apontando para arquivo inexistente → erro `arquivo não encontrado`.
  - Órgão com `pecas: [{tipo: boletim, rotulo: Boletim, exigida: true}]` passa; `tipo` fora de `protocolo.TIPOS_PECA` → erro; `ordem_certidoes` com chave desconhecida → erro; `carta_destinatario` que não é lista de texto → erro.
  - Contrato com `cno_pdf` inexistente → erro; fiscal com `tratamento: Dona` → erro (`Senhor` ou `Senhora`).

  Em `test_cadastro_aplicar.py`:
  - aplicar grava `objeto_completo`, `cno_arquivo` (caminho `anexos/<sha>.pdf` que existe na pasta de dados), `cargo`/`tratamento`/`portaria` do fiscal e `cadastro_geral['cartas']` com `emitentes.lotufo.timbre` = `modelos/<sha>.png` existente;
  - reaplicar é igual (`iguais`);
  - `--ensaio` não grava arquivo na pasta de dados.

  Em `test_carta.py`:
  - `fiscal_vigente` devolve o de maior `desde` até a data;
  - `emitente` cai para nome e CNPJ da entidade quando `cartas.emitentes` não tem a chave.

- [ ] **Step 3:** rodar os três arquivos → FAIL nos testes novos.

- [ ] **Step 4: `cadastro_arquivos.py`.**
  - `_cartas(raiz, erros) -> dict | None`: lê `cartas.yaml` se existir e valida:
    - `signatario` é lista de textos;
    - `emitentes.<chave>` tem `razao_social`;
    - o `timbre`, relativo à raiz, existe; guarda o caminho absoluto em `timbre_caminho`;
    - `familias` só tem chaves de `FAMILIAS_CARTA = ("mtpar", "ses", "sinfra", "prefeitura")`, cada campo texto.
  - `preparar` põe o resultado em `geral["cartas"]`; `geral` passa a ser dict mesmo sem `geral.yaml`, quando há `cartas.yaml`.
  - Na validação do órgão (hoje em `preparar`, `cadastro_arquivos.py:244-264`), valida as chaves novas. `TIPOS_PECA` fica em `cadastro_arquivos` e é reexportado por `protocolo`. Constante:

```python
TIPOS_PECA = ("boletim", "planilha", "diario", "fotos", "cronograma", "art", "ensaios", "memorial", "outro")
```

  - Em `_contrato`:
    - `objeto_completo` é texto opcional;
    - `cno_pdf` é caminho relativo à raiz, que precisa existir; vira `cno_caminho` absoluto;
    - os fiscais aceitam `cargo`, `tratamento` (`Senhor`/`Senhora`) e `portaria`, todos opcionais.
- [ ] **Step 5: `cadastro_aplicar.py`.**
  - Helper que calcula o caminho pelo hash e só grava fora do ensaio:

```python
def _no_disco(pasta: str, caminho: str, ext: str, ensaio: bool) -> str:
    """Copia um arquivo do cadastro para a pasta de dados pelo hash (a producao nao le o checkout)."""
    dados = Path(caminho).read_bytes()
    if ensaio:
        return f"{pasta}/{arquivos.sha_de(dados)}.{ext}"
    return arquivos.gravar_bytes(pasta, dados, ext)[0]
```

  - Antes de `_geral`, trocar `timbre_caminho` por `timbre = _no_disco("modelos", ..., "png", ensaio)` em cada emitente.
  - Em `_contrato`, `cno_caminho` vira `cno_arquivo = _no_disco("anexos", ..., "pdf", ensaio)`.
  - `objeto_completo` e `cno_arquivo` entram em `_CAMPOS_CONTRATO`.
  - Fiscais:
    - a chave continua (`email`, `desde`);
    - `cargo`, `tratamento` e `portaria` são atualizados na linha existente com auditoria `cadastro.fiscal`;
    - a lista continua só crescendo, sem remoção.
- [ ] **Step 6: `carta.py`**, funções de leitura:

```python
import json


def config(conn) -> dict:
    r = conn.execute("SELECT valor FROM cadastro_geral WHERE chave='cartas'").fetchone()
    if r is None:
        raise ValueError("Textos das cartas não carregados: rode `cadastro aplicar` com cadastro/cartas.yaml")
    return json.loads(r["valor"])


def _cnpj(c: str) -> str:
    return f"{c[:2]}.{c[2:5]}.{c[5:8]}/{c[8:12]}-{c[12:]}" if c and len(c) == 14 else (c or "")


def emitente(conn, entidade_id: int) -> dict:
    e = conn.execute("SELECT * FROM entidades WHERE id=?", (entidade_id,)).fetchone()
    try:
        cfg = config(conn).get("emitentes", {})
    except ValueError:
        cfg = {}
    base = {"razao_social": (e["nome"] or "").upper() if e else "", "cnpj": _cnpj(e["cnpj"] if e else ""),
            "endereco": None, "timbre": None, "sigla": e["sigla_oficio"] if e else None}
    return {**base, **(cfg.get(e["chave"]) or {})} if e else base


def fiscal_vigente(conn, contrato_id: int, na_data: str) -> dict | None:
    r = conn.execute("SELECT * FROM contrato_fiscais WHERE contrato_id=? AND desde<=? "
                     "ORDER BY desde DESC, id DESC LIMIT 1", (contrato_id, na_data)).fetchone()
    return dict(r) if r else None
```

- [ ] **Step 7:** rodar os três arquivos → PASS; `python -m app.cli cadastro validar` sobre o cadastro real → sem erro.
- [ ] **Step 8: Commit** `feat: cadastro das cartas, pecas por orgao, CNO e dados do fiscal`.

---

### Task 5.7: Protocolo, parte 1: famílias, criar, peças, carta e montagem

**Files:**
- Create: `backend/app/protocolo.py`
- Test: `backend/tests/test_protocolo.py`

**Interfaces:**
- Consumes: `oficios`, `carta` (5.2 e 5.6), `pdfs`, `documentos.exigidos(conn, contrato_id, natureza) -> {"entidades", "tipos", "regularidade"}` (a regularidade é o id da entidade dona ou `None`), `certidoes.vigente(conn, entidade_id, tipo_id, na_data) -> dict | None`, `checklist.pronto_para_protocolar(conn, contrato_id, natureza) -> {"itens": [{"entidade", "tipo", "chave", "situacao"}], ...}`, `notas.faltam(conn, medicao_id) -> int`.
- Produces: `Etapa`, `FAMILIAS`, `TIPOS_PECA`, `titulo(m) -> str`, `etapas_do_contrato(conn, contrato_id) -> list[Etapa]`, `criar(conn, usuario_id, contrato_id, etapa, medicao_ids, numero_oficio) -> int`, `detalhe(conn, protocolo_id, hoje=None) -> dict`, `listar(conn, contrato_id) -> dict`, `adicionar_peca(conn, usuario_id, protocolo_id, tipo, nome, dados, ext) -> int`, `remover_peca(conn, usuario_id, protocolo_id, peca_id) -> None`, `corpo_padrao(conn, protocolo_id, hoje=None) -> str`, `montar(conn, usuario_id, protocolo_id, corpo=None, hoje=None) -> dict`, `nome_arquivo(conn, p) -> str`, `pendencias(conn, p, hoje) -> list[dict]`.

- [ ] **Step 1: Fixture de teste.** Em `test_protocolo.py`, uma fixture `cenario(tmp_path, monkeypatch)` que:
  - aponta `DASH_DB_PATH` para o `tmp_path`, migra, cria usuário admin e fixa `tempo.hoje_local` em 2026-09-16;
  - aplica um cadastro mínimo com `cadastro_aplicar.aplicar`:
    - um órgão `mtpar` (família mtpar, `ordem_certidoes: [municipal, trabalhista, estadual, federal, fgts]`);
    - um órgão `sinfra-x` (família sinfra, `pecas: [{tipo: boletim, rotulo: Boletim de medição, exigida: true}, {tipo: planilha, rotulo: Planilha editável, exigida: true, solto: true}]`, `limite_mb_por_documento: 25`, documentos com `regularidade`);
    - a entidade `lotufo` (sigla LT);
    - um contrato de cada órgão, com fiscal `Fiscal Exemplo`, `tratamento: Senhora`, `cargo: Engenheira Fiscal`;
    - o `cartas.yaml` da tarefa 5.6;
  - cria, para cada contrato, a medição 23 de execução e de reajuste em `nota_emitida`, com um documento de nota (`medicao_documentos`, `tipo_doc='nfs'`, arquivo gravado por `arquivos.gravar_bytes` a partir de `carta.pagina_titulo(["NFS-e 2311"])`);
  - grava as cinco certidões vigentes da Lotufo (PDF de `carta.pagina_titulo([...])`) pelo `documentos.gravar_certidao` com dados manuais;
  - devolve `conn`, ids e `uid`.

  Reusar os helpers de `tests/test_documentos.py` e `tests/test_notas.py` (importar deles) em vez de reescrever.

- [ ] **Step 2: Testes** (um por comportamento)

```python
def test_etapas_por_familia(cenario):
    c, ids = cenario
    assert [e.chave for e in protocolo.etapas_do_contrato(c, ids["mtpar"])] == ["unico"]
    assert [e.chave for e in protocolo.etapas_do_contrato(c, ids["sinfra"])] == ["medicao", "nota"]


def test_criar_normaliza_o_oficio_e_recusa_medicao_encerrada(cenario):
    c, ids = cenario
    pid = protocolo.criar(c, ids["uid"], ids["mtpar"], "unico", [ids["mtpar_exec"]], "301")
    assert protocolo.detalhe(c, pid)["numero_oficio"] == "CT-301-LT-2026"
    c.execute("UPDATE medicoes SET estado='cancelada' WHERE id=?", (ids["mtpar_reaj"],)); c.commit()
    with pytest.raises(ValueError, match="cancelada"):
        protocolo.criar(c, ids["uid"], ids["mtpar"], "unico", [ids["mtpar_reaj"]], "302")


def test_mtpar_nao_junta_execucao_e_reajuste(cenario):
    c, ids = cenario
    with pytest.raises(ValueError, match="separad"):
        protocolo.criar(c, ids["uid"], ids["mtpar"], "unico", [ids["mtpar_exec"], ids["mtpar_reaj"]], "301")


def test_montar_mtpar_carta_notas_e_certidoes_na_ordem_do_orgao(cenario):
    c, ids = cenario
    pid = protocolo.criar(c, ids["uid"], ids["mtpar"], "unico", [ids["mtpar_exec"]], "301")
    r = protocolo.montar(c, ids["uid"], pid)
    textos = leitura_pdf.textos_por_pagina_com_limite(arquivos.caminho_seguro(r["arquivo"]).read_bytes())
    assert "CT/301/LT/2026" in textos[0] and "A/C: Fiscal Exemplo" in textos[0] and "23ª Medição" in textos[0]
    assert "NFS-e 2311" in textos[1]
    assert "MUNICIPAL" in textos[2].upper()                # ordem_certidoes: municipal primeiro
    assert r["nome"] == "CT-301-LT-2026 - Obra MTPAR - 23ª Medição (09.2026).pdf"
    assert protocolo.detalhe(c, pid)["situacao"] == "montado"


def test_corpo_editado_vai_para_a_carta_e_fica_gravado(cenario):
    c, ids = cenario
    pid = protocolo.criar(c, ids["uid"], ids["mtpar"], "unico", [ids["mtpar_exec"]], "301")
    corpo = protocolo.corpo_padrao(c, pid) + "\n\nSegue também o link: https://exemplo"
    r = protocolo.montar(c, ids["uid"], pid, corpo=corpo)
    t = leitura_pdf.textos_por_pagina_com_limite(arquivos.caminho_seguro(r["arquivo"]).read_bytes())[0]
    assert "https://exemplo" in t and protocolo.detalhe(c, pid)["corpo_carta"] == corpo


def test_sinfra_medicao_leva_carta_e_boletim_e_pendencia_de_planilha(cenario):
    c, ids = cenario
    pid = protocolo.criar(c, ids["uid"], ids["sinfra"], "medicao", [ids["sinfra_exec"]], "310")
    protocolo.adicionar_peca(c, ids["uid"], pid, "boletim", "boletim.pdf", carta.pagina_titulo(["BOLETIM 23"]), "pdf")
    codigos = [x["codigo"] for x in protocolo.detalhe(c, pid)["pendencias"]]
    assert "peca" in codigos and "sem_nota" not in codigos       # etapa da medicao nao cobra nota
    r = protocolo.montar(c, ids["uid"], pid)
    textos = leitura_pdf.textos_por_pagina_com_limite(arquivos.caminho_seguro(r["arquivo"]).read_bytes())
    assert "BOLETIM 23" in textos[-1]


def test_pendencias_de_certidao_e_nota(cenario):
    c, ids = cenario
    c.execute("DELETE FROM medicao_documentos WHERE medicao_id=?", (ids["mtpar_exec"],))
    c.execute("DELETE FROM certidoes WHERE tipo_id=(SELECT id FROM certidao_tipos WHERE chave='fgts')")
    c.commit()
    pid = protocolo.criar(c, ids["uid"], ids["mtpar"], "unico", [ids["mtpar_exec"]], "301")
    codigos = [x["codigo"] for x in protocolo.detalhe(c, pid)["pendencias"]]
    assert "sem_nota" in codigos and "certidao" in codigos
```

(O `DELETE` em teste é só montagem de cenário no banco temporário.)

- [ ] **Step 3:** rodar → FAIL.

- [ ] **Step 4: Implementação** (`backend/app/protocolo.py`)

```python
"""Protocolo de medicao feito pelo sistema (bloco 5; spec 2026-09-21 §3 passos 4 a 7, §5.3, §5.4, §6).

Um PROTOCOLO e' um documento a assinar e um oficio. A FAMILIA do orgao decide as ETAPAS (SINFRA tem
duas: medicao assinada e nota), as PARTES do PDF e os anexos SOLTOS do e-mail; o CADASTRO do orgao
decide destinatarios, textos, pecas tecnicas e sua ordem, ordem das certidoes e limite por documento.

Ciclo: rascunho -> montado (PDF gerado para assinar) -> assinado (PDF do DocuSign conferido) ->
enviado (e-mail aceito). Descartado sai do ciclo. O que falta vira PENDENCIA (avisa e deixa seguir);
so' bloqueia o que e' erro (medicao encerrada, sem destinatario, anexos acima do teto do e-mail).
"""
import datetime
import json
from dataclasses import dataclass

from app import (arquivos, auditoria, carta, cadastro_arquivos, certidoes, checklist, db, documentos,
                 notas, oficios, pdfs, tempo)

TIPOS_PECA = cadastro_arquivos.TIPOS_PECA
ROTULO_NATUREZA = {"execucao": "Medição", "projeto": "Projeto", "reajuste": "Reajuste"}
ENCERRADAS = ("cancelada", "desistida", "recebida")


@dataclass(frozen=True)
class Etapa:
    chave: str                  # 'unico' | 'medicao' | 'nota'
    rotulo: str
    carta: bool                 # gera carta e passa pela assinatura
    capa: bool                  # SES: pagina "42ª MEDIÇÃO / PERÍODO"
    divisorias: bool            # SES: pagina de titulo antes de cada secao
    partes: tuple[str, ...]     # ordem do PDF: 'carta', 'notas', 'certidoes', 'pecas'
    soltos: tuple[str, ...]     # anexos do e-mail fora do PDF: 'planilha', 'notas', 'certidoes_zip', 'cno', 'regularidade', 'pecas_soltas'
    marca_protocolada: bool
    junta_naturezas: bool       # execucao e reajuste no mesmo e-mail (cada um no seu PDF)


FAMILIAS: dict[str, tuple[Etapa, ...]] = {
    "mtpar": (Etapa("unico", "Protocolo", True, False, False, ("carta", "notas", "certidoes"), (), True, False),),
    "ses": (Etapa("unico", "Protocolo", True, True, True, ("carta", "notas", "certidoes", "pecas"), (), True, False),),
    "sinfra": (Etapa("medicao", "Medição assinada", True, False, False, ("carta", "pecas"), ("planilha",), False, True),
               Etapa("nota", "Nota, certidões e regularidade", False, False, False, (),
                     ("notas", "certidoes_zip", "cno", "regularidade"), True, True)),
    "prefeitura": (Etapa("unico", "Protocolo", True, False, False, ("carta", "notas"),
                         ("certidoes_zip", "pecas_soltas"), True, False),),
}


# --- leitura ---------------------------------------------------------------------------------------

def _contrato(conn, contrato_id: int) -> dict:
    c = conn.execute("SELECT * FROM contratos WHERE id=?", (contrato_id,)).fetchone()
    if c is None:
        raise ValueError(f"Contrato {contrato_id} não encontrado")
    return dict(c)


def _orgao(conn, c: dict) -> tuple[str, dict, dict]:
    if not c.get("orgao_id"):
        raise ValueError("Contrato sem órgão no cadastro: não há família de protocolo")
    o = conn.execute("SELECT * FROM orgaos WHERE id=?", (c["orgao_id"],)).fetchone()
    return o["familia"], json.loads(o["regras"]), dict(o)


def etapas_do_contrato(conn, contrato_id: int) -> list[Etapa]:
    familia, _, _ = _orgao(conn, _contrato(conn, contrato_id))
    return list(FAMILIAS[familia])


def _etapa(familia: str, chave: str) -> Etapa:
    for e in FAMILIAS[familia]:
        if e.chave == chave:
            return e
    raise ValueError(f"A família {familia} não tem a etapa {chave!r}")


def titulo(m: dict) -> str:
    if m["tipo"] == "reajuste":
        return f"Reajuste da {m['numero']}ª Medição"
    return f"{m['numero']}ª Medição" + (" de Projeto" if m["tipo"] == "projeto" else "")


def _medicoes(conn, protocolo_id: int) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT m.* FROM protocolo_medicoes pm JOIN medicoes m ON m.id=pm.medicao_id "
        "WHERE pm.protocolo_id=? ORDER BY m.tipo='reajuste', m.id", (protocolo_id,))]


def _periodo(conn, m: dict) -> str:
    e = conn.execute(
        "SELECT e.periodo_inicio, e.periodo_fim FROM espelho_medicoes em JOIN espelhos e ON e.id=em.espelho_id "
        "WHERE em.medicao_id=? AND e.situacao='vigente' ORDER BY e.versao DESC LIMIT 1", (m["id"],)).fetchone()
    ano, mes = int(m["competencia"][:4]), int(m["competencia"][5:7])
    ini = datetime.date(ano, mes, 1)
    fim = (datetime.date(ano + (mes == 12), mes % 12 + 1, 1) - datetime.timedelta(days=1))
    if e and e["periodo_inicio"] and e["periodo_fim"]:
        ini, fim = datetime.date.fromisoformat(e["periodo_inicio"]), datetime.date.fromisoformat(e["periodo_fim"])
    return f"{ini:%d/%m/%Y} a {fim:%d/%m/%Y}"


def _docs_nota(conn, medicao_ids: list[int]) -> list[dict]:
    if not medicao_ids:
        return []
    marcas = ",".join("?" * len(medicao_ids))
    return [dict(r) for r in conn.execute(
        f"SELECT id, medicao_id, tipo_doc, nome, arquivo FROM medicao_documentos "
        f"WHERE medicao_id IN ({marcas}) AND tipo_doc IN ('nfs','nf','fatura') AND arquivo IS NOT NULL "
        f"ORDER BY tipo_doc='fatura', id", medicao_ids)]


def _pecas(conn, protocolo_id: int) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT * FROM protocolo_pecas WHERE protocolo_id=? AND removida_em IS NULL ORDER BY id", (protocolo_id,))]


def _bytes(rel: str) -> bytes:
    return arquivos.caminho_seguro(rel).read_bytes()


# --- criar e pecas ---------------------------------------------------------------------------------

def criar(conn, usuario_id: int, contrato_id: int, etapa: str, medicao_ids: list[int],
          numero_oficio: str | None) -> int:
    c = _contrato(conn, contrato_id)
    familia, _, _ = _orgao(conn, c)
    e = _etapa(familia, etapa)
    if not medicao_ids:
        raise ValueError("Escolha ao menos uma medição")
    ms = [dict(r) for r in conn.execute(
        f"SELECT * FROM medicoes WHERE id IN ({','.join('?' * len(medicao_ids))})", medicao_ids)]
    if len(ms) != len(set(medicao_ids)) or any(m["contrato_id"] != contrato_id for m in ms):
        raise ValueError("Medição de outro contrato")
    for m in ms:
        if m["estado"] in ENCERRADAS:
            raise ValueError(f"{titulo(m)} está {m['estado']}: não recebe protocolo")
    naturezas = {m["tipo"] for m in ms}
    if len(naturezas) > 1 and familia != "ses":
        raise ValueError("Execução e reajuste vão em protocolos separados (um ofício para cada)")
    natureza = "execucao" if "execucao" in naturezas else next(iter(naturezas))
    canon = None
    if e.carta:
        ent = conn.execute("SELECT sigla_oficio FROM entidades WHERE id=?",
                           (c["entidade_id"],)).fetchone() if c.get("entidade_id") else None
        canon = oficios.canonico(numero_oficio or "", ent["sigla_oficio"] if ent else "LT", tempo.hoje_local().year)
    with db.mutacao(conn):
        pid = conn.execute("INSERT INTO protocolos (contrato_id, etapa, natureza, numero_oficio, usuario_id) "
                           "VALUES (?,?,?,?,?)", (contrato_id, etapa, natureza, canon, usuario_id)).lastrowid
        for mid in sorted(set(medicao_ids)):
            conn.execute("INSERT INTO protocolo_medicoes (protocolo_id, medicao_id) VALUES (?,?)", (pid, mid))
        auditoria.registrar(conn, usuario_id, "protocolo.criar", "protocolo", pid, None,
                            {"etapa": etapa, "medicoes": sorted(set(medicao_ids)), "numero_oficio": canon})
    return pid


def _editavel(p: dict) -> None:
    if p["situacao"] in ("enviado", "descartado"):
        raise ValueError(f"Protocolo {p['situacao']}: não pode ser alterado")


def adicionar_peca(conn, usuario_id: int, protocolo_id: int, tipo: str, nome: str, dados: bytes, ext: str) -> int:
    if tipo not in TIPOS_PECA:
        raise ValueError(f"Tipo de peça inválido: {tipo!r}")
    p = _linha(conn, protocolo_id)
    _editavel(p)
    rel, sha = arquivos.gravar_bytes("protocolos", dados, ext)
    with db.mutacao(conn):
        pid = conn.execute("INSERT INTO protocolo_pecas (protocolo_id, tipo, nome, arquivo, sha256, tamanho, ext) "
                           "VALUES (?,?,?,?,?,?,?)", (protocolo_id, tipo, nome, rel, sha, len(dados), ext)).lastrowid
        _voltar_a_rascunho(conn, p)
        auditoria.registrar(conn, usuario_id, "protocolo.peca", "protocolo", protocolo_id, None,
                            {"peca_id": pid, "tipo": tipo, "nome": nome, "sha256": sha})
    return pid


def remover_peca(conn, usuario_id: int, protocolo_id: int, peca_id: int) -> None:
    p = _linha(conn, protocolo_id)
    _editavel(p)
    with db.mutacao(conn):
        n = conn.execute("UPDATE protocolo_pecas SET removida_em=datetime('now') "
                         "WHERE id=? AND protocolo_id=? AND removida_em IS NULL", (peca_id, protocolo_id)).rowcount
        if n != 1:
            raise ValueError("Peça não encontrada")
        _voltar_a_rascunho(conn, p)
        auditoria.registrar(conn, usuario_id, "protocolo.peca_removida", "protocolo", protocolo_id, None,
                            {"peca_id": peca_id})


def _voltar_a_rascunho(conn, p: dict) -> None:
    """Mudou o conteudo depois de montado: o PDF montado (e o assinado) deixam de valer."""
    if p["situacao"] in ("montado", "assinado"):
        conn.execute("UPDATE protocolos SET situacao='rascunho', assinado_arquivo=NULL, assinado_sha256=NULL, "
                     "conferencia=NULL WHERE id=?", (p["id"],))


def _linha(conn, protocolo_id: int) -> dict:
    r = conn.execute("SELECT * FROM protocolos WHERE id=?", (protocolo_id,)).fetchone()
    if r is None:
        raise ValueError(f"Protocolo {protocolo_id} não encontrado")
    return dict(r)


# --- carta -----------------------------------------------------------------------------------------

def _config_pecas(regras: dict) -> list[dict]:
    return [{"exigida": False, "solto": False, **x} for x in (regras.get("pecas") or [])]


def _lista(conn, p: dict, familia: str, regras: dict, ms: list[dict]) -> str:
    """Itens da carta: notas (numero e valor), certidoes, pecas. SES numera; as outras usam i., ii."""
    itens = []
    docs = _docs_nota(conn, [m["id"] for m in ms])
    nums = ", ".join(sorted({(d["nome"] or "").rsplit(".", 1)[0] for d in docs if d["tipo_doc"] in ("nfs", "nf")}))
    total = sum(m["valor_protocolado_centavos"] or 0 for m in ms)
    if familia == "ses":
        itens.append(f"Nota Fiscal – R$ {_brl(total)}")
        for m in ms:
            itens.append(f"   Sendo: {titulo(m)} – R$ {_brl(m['valor_protocolado_centavos'] or 0)}")
    elif "notas" in _etapa(familia, p["etapa"]).partes:
        itens.append(f"Nota fiscal de prestação de serviços – {nums or 'NF'}")
    if "certidoes" in _etapa(familia, p["etapa"]).partes or familia == "prefeitura":
        itens.append("Certidões de regularidade fiscal")
    for cfg in _config_pecas(regras):
        if not cfg["solto"] and (cfg["exigida"] or any(x["tipo"] == cfg["tipo"] for x in _pecas(conn, p["id"]))):
            itens.append(cfg["rotulo"])
    romanos = ["i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x", "xi", "xii"]
    return "\n".join(f"{(k + 1) if familia == 'ses' else romanos[k]}. {t}" if not t.startswith("   ") else t
                     for k, t in enumerate(itens))


def _brl(centavos: int) -> str:
    inteiro, cent = divmod(int(centavos), 100)
    return f"{inteiro:,}".replace(",", ".") + f",{cent:02d}"


def _campos(conn, p: dict, c: dict, familia: str, regras: dict, ms: list[dict], hoje: datetime.date) -> dict:
    em = carta.emitente(conn, c["entidade_id"]) if c.get("entidade_id") else {}
    m0 = ms[0]
    return {"razao_social": em.get("razao_social", ""), "cnpj": em.get("cnpj", ""),
            "oficio": p["numero_oficio"] or "", "medicao": " e ".join(titulo(m) for m in ms),
            "periodo": _periodo(conn, m0), "competencia": f"{m0['competencia'][5:7]}/{m0['competencia'][:4]}",
            "obra": c.get("nome_curto") or c.get("numero"), "instrumento": c.get("numero_instrumento") or c.get("numero"),
            "objeto": c.get("objeto_completo") or c.get("objeto") or "", "orgao": "",
            "lista": _lista(conn, p, familia, regras, ms), "saudacao": _saudacao()}


def _saudacao() -> str:
    return "Bom dia." if tempo.agora_local().hour < 12 else "Boa tarde."


def corpo_padrao(conn, protocolo_id: int, hoje: datetime.date | None = None) -> str:
    p = _linha(conn, protocolo_id)
    c = _contrato(conn, p["contrato_id"])
    familia, regras, _ = _orgao(conn, c)
    textos = carta.config(conn)["familias"][familia]
    return carta.preencher(textos["carta_corpo"], _campos(conn, p, c, familia, regras, _medicoes(conn, protocolo_id),
                                                          hoje or tempo.hoje_local())).strip()


def _carta(conn, p: dict, corpo: str, hoje: datetime.date) -> carta.Carta:
    c = _contrato(conn, p["contrato_id"])
    familia, regras, o = _orgao(conn, c)
    ms = _medicoes(conn, p["id"])
    cfg = carta.config(conn)
    campos = _campos(conn, p, c, familia, regras, ms, hoje)
    f = carta.fiscal_vigente(conn, c["id"], hoje.isoformat())
    ac = []
    if f:
        ac.append(f"A/C: {f['nome']}")
        ac += [x for x in (f.get("cargo"), f.get("portaria")) if x]
    vocativo = {"Senhor": "Prezado Senhor,", "Senhora": "Prezada Senhora,"}.get((f or {}).get("tratamento"),
                                                                              "Prezados Senhores,")
    ref = f"Ref.: Contrato n.º {campos['instrumento']} – {campos['objeto']}".rstrip(" –")
    local = f"Cuiabá/MT, {carta.data_extenso(hoje)}."
    return carta.Carta(numero=oficios.na_carta(p["numero_oficio"]), local_data=local,
                       destinatario=regras.get("carta_destinatario") or [o["nome"]], ac=ac, referencia=ref,
                       assunto=carta.preencher(cfg["familias"][familia]["carta_assunto"], campos),
                       vocativo=vocativo, corpo=corpo, assinatura=cfg.get("signatario") or [],
                       emitente=carta.emitente(conn, c["entidade_id"]) if c.get("entidade_id") else {})


# --- montar ----------------------------------------------------------------------------------------

def nome_arquivo(conn, p: dict) -> str:
    c = _contrato(conn, p["contrato_id"])
    ms = _medicoes(conn, p["id"])
    m = ms[0]
    obra = c.get("nome_curto") or c.get("numero")
    doc = p["numero_oficio"] or ("NOTA" if p["etapa"] == "nota" else "PROTOCOLO")
    comp = f"{m['competencia'][5:7]}.{m['competencia'][:4]}"
    return f"{doc} - {obra} - {m['numero']:02d}ª {ROTULO_NATUREZA[p['natureza']]} ({comp}).pdf"


def _certidoes_pdf(conn, p: dict, regras: dict, hoje: datetime.date) -> list[bytes]:
    ex = documentos.exigidos(conn, p["contrato_id"], p["natureza"])
    ordem = regras.get("ordem_certidoes") or sorted(t["chave"] for t in ex["tipos"])
    tipos = sorted(ex["tipos"], key=lambda t: ordem.index(t["chave"]) if t["chave"] in ordem else 99)
    out = []
    for eid in ex["entidades"]:
        for t in tipos:
            v = certidoes.vigente(conn, eid, t["id"], hoje.isoformat())
            if v and v.get("arquivo"):
                out.append(_bytes(v["arquivo"]))
    return out


def montar(conn, usuario_id: int, protocolo_id: int, corpo: str | None = None,
           hoje: datetime.date | None = None) -> dict:
    hoje = hoje or tempo.hoje_local()
    p = _linha(conn, protocolo_id)
    _editavel(p)
    c = _contrato(conn, p["contrato_id"])
    familia, regras, _ = _orgao(conn, c)
    e = _etapa(familia, p["etapa"])
    if not e.carta:
        raise ValueError("Esta etapa não tem pacote para assinar: os arquivos vão soltos no e-mail")
    corpo = (corpo if corpo is not None else (p["corpo_carta"] or corpo_padrao(conn, protocolo_id, hoje))).strip()
    ms = _medicoes(conn, protocolo_id)
    em = carta.emitente(conn, c["entidade_id"]) if c.get("entidade_id") else {}
    partes: list[bytes] = []
    if e.capa:
        partes.append(carta.pagina_titulo([" e ".join(titulo(m) for m in ms).upper(),
                                           f"PERÍODO: {_periodo(conn, ms[0])}"], em))
    pecas = _pecas(conn, protocolo_id)
    for parte in e.partes:
        if parte == "carta":
            partes.append(carta.gerar(_carta(conn, p, corpo, hoje)))
        elif parte == "notas":
            docs = _docs_nota(conn, [m["id"] for m in ms])
            if docs and e.divisorias:
                partes.append(carta.pagina_titulo(["NOTA FISCAL"], em))
            partes += [_bytes(d["arquivo"]) for d in docs]
        elif parte == "certidoes":
            certs = _certidoes_pdf(conn, p, regras, hoje)
            if certs and e.divisorias:
                partes.append(carta.pagina_titulo(["CERTIDÕES"], em))
            partes += certs
        elif parte == "pecas":
            for cfg in _config_pecas(regras):
                das = [x for x in pecas if x["tipo"] == cfg["tipo"] and x["ext"] == "pdf" and not cfg["solto"]]
                if das and e.divisorias:
                    partes.append(carta.pagina_titulo([cfg["rotulo"].upper()], em))
                partes += [_bytes(x["arquivo"]) for x in das]
            soltas = [x for x in pecas if x["ext"] == "pdf" and x["tipo"] not in
                      {cfg["tipo"] for cfg in _config_pecas(regras)}]
            partes += [_bytes(x["arquivo"]) for x in soltas]
    pdf = pdfs.juntar(partes)
    if len(pdf) > pdfs.TETO_BYTES_PACOTE:
        raise ValueError(f"Pacote de {len(pdf) // (1024 * 1024)} MB, acima do limite de "
                         f"{pdfs.TETO_BYTES_PACOTE // (1024 * 1024)} MB: separe as peças")
    rel, sha = arquivos.gravar_bytes("protocolos", pdf, "pdf")
    n = pdfs.paginas(pdf)
    with db.mutacao(conn):
        conn.execute("UPDATE protocolos SET corpo_carta=?, montado_arquivo=?, montado_sha256=?, montado_paginas=?, "
                     "montado_em=datetime('now'), assinado_arquivo=NULL, assinado_sha256=NULL, conferencia=NULL, "
                     "situacao='montado' WHERE id=?", (corpo, rel, sha, n, protocolo_id))
        auditoria.registrar(conn, usuario_id, "protocolo.montar", "protocolo", protocolo_id, None,
                            {"sha256": sha, "paginas": n, "tamanho": len(pdf)})
    return {"arquivo": rel, "sha256": sha, "paginas": n, "tamanho": len(pdf), "nome": nome_arquivo(conn, p)}


# --- pendencias, detalhe e lista -------------------------------------------------------------------

def pendencias(conn, p: dict, hoje: datetime.date) -> list[dict]:
    c = _contrato(conn, p["contrato_id"])
    familia, regras, _ = _orgao(conn, c)
    e = _etapa(familia, p["etapa"])
    ms = _medicoes(conn, p["id"])
    out = []
    if "notas" in e.partes or "notas" in e.soltos:
        for m in ms:
            if not _docs_nota(conn, [m["id"]]) or notas.faltam(conn, m["id"]):
                out.append({"codigo": "sem_nota", "mensagem": f"{titulo(m)}: nota fiscal não anexada"})
    if "certidoes" in e.partes or "certidoes_zip" in e.soltos or "regularidade" in e.soltos:
        ck = checklist.pronto_para_protocolar(conn, c["id"], p["natureza"])
        for i in ck["itens"]:
            if i["situacao"] == "pendente":
                out.append({"codigo": "certidao", "mensagem": f"{i['entidade']}: {i['tipo']} sem validade hoje"})
    presentes = {x["tipo"] for x in _pecas(conn, p["id"])}
    usa_pecas = "pecas" in e.partes or "planilha" in e.soltos or "pecas_soltas" in e.soltos
    for cfg in _config_pecas(regras):
        if usa_pecas and cfg["exigida"] and cfg["tipo"] not in presentes:
            out.append({"codigo": "peca", "mensagem": f"{cfg['rotulo']}: não anexada"})
    if "cno" in e.soltos and not c.get("cno_arquivo"):
        out.append({"codigo": "cno", "mensagem": "Comprovante do CNO da obra não está no cadastro"})
    if e.carta:
        if p["situacao"] == "rascunho":
            out.append({"codigo": "nao_montado", "mensagem": "Pacote ainda não montado"})
        elif not p["assinado_arquivo"]:
            out.append({"codigo": "nao_assinado", "mensagem": "Pacote ainda não assinado"})
        else:
            for a in (json.loads(p["conferencia"] or "{}").get("avisos") or []):
                out.append({"codigo": "conferencia", "mensagem": a["mensagem"]})
        repetido = oficios.usos(conn, p["numero_oficio"], ignorar=("protocolo", p["id"])) if p["numero_oficio"] else []
        if repetido:
            out.append({"codigo": "oficio_repetido",
                        "mensagem": f"Ofício {p['numero_oficio']} já usado em {', '.join(repetido)}"})
    limite = regras.get("limite_mb_por_documento")
    rel = p["assinado_arquivo"] or p["montado_arquivo"]
    if limite and rel and arquivos.caminho_seguro(rel).stat().st_size > limite * 1024 * 1024:
        out.append({"codigo": "limite", "mensagem": f"PDF acima de {limite} MB, o limite por documento do órgão"})
    for m in ms:
        if m["estado"] in ("protocolada", "nf_emitida"):
            out.append({"codigo": "ja_protocolada", "mensagem": f"{titulo(m)} já está protocolada"})
    return out


def detalhe(conn, protocolo_id: int, hoje: datetime.date | None = None) -> dict:
    hoje = hoje or tempo.hoje_local()
    p = _linha(conn, protocolo_id)
    c = _contrato(conn, p["contrato_id"])
    familia, _, _ = _orgao(conn, c)
    e = _etapa(familia, p["etapa"])
    return {**p, "familia": familia, "etapa_rotulo": e.rotulo, "tem_carta": e.carta,
            "medicoes": [{**m, "titulo": titulo(m)} for m in _medicoes(conn, protocolo_id)],
            "pecas": _pecas(conn, protocolo_id), "conferencia": json.loads(p["conferencia"] or "null"),
            "pendencias": pendencias(conn, p, hoje),
            "nome_arquivo": nome_arquivo(conn, p) if p["montado_arquivo"] else None}


def listar(conn, contrato_id: int) -> dict:
    c = _contrato(conn, contrato_id)
    familia, regras, _ = _orgao(conn, c)
    ms = [dict(r) for r in conn.execute(
        "SELECT * FROM medicoes WHERE contrato_id=? AND estado NOT IN ('cancelada','desistida','recebida','prevista') "
        "ORDER BY numero DESC, tipo", (contrato_id,))]
    ids = [r[0] for r in conn.execute("SELECT id FROM protocolos WHERE contrato_id=? AND situacao<>'descartado' "
                                      "ORDER BY id DESC", (contrato_id,))]
    return {"familia": familia,
            "etapas": [{"chave": e.chave, "rotulo": e.rotulo, "carta": e.carta} for e in FAMILIAS[familia]],
            "pecas": _config_pecas(regras), "medicoes": [{**m, "titulo": titulo(m)} for m in ms],
            "protocolos": [detalhe(conn, i) for i in ids]}
```

Observações de implementação:
- `tempo.agora_local()`: se o módulo `tempo` não tiver, usar o que `espelhos.previa_envio` usa para `{saudacao}`; não criar segunda regra de hora.
- `valor_protocolado_centavos` é o valor cheio da medição gravado pelo espelho. Se estiver nulo numa medição do espelho, usar a soma das saídas Lotufo de `notas.esperadas(conn, medicao_id)` (`valor`), e anotar a regra num comentário.
- O nome do documento de nota na lista da carta sai do `nome` do arquivo, por exemplo "NFS-e 2311". Se as notas lidas tiverem número (`notas_fiscais.numero` ligado por `documento_id`), preferir "NF nº 2311, 2312".

- [ ] **Step 5:** rodar → PASS.
- [ ] **Step 6: Commit** `feat: protocolo por familia - criar, pecas, carta e montagem do pacote`.

---

### Task 5.8: Protocolo, parte 2: assinado, prévia, envio e marcação de protocolada

**Files:**
- Modify: `backend/app/protocolo.py`, `backend/app/medicoes.py` (`registrar_protocolo(..., protocolo_id=None)`), `backend/app/correio.py` (`MAX_TOTAL`)
- Test: `backend/tests/test_protocolo.py` (acrescentar), `backend/tests/test_medicoes.py` (um teste do `protocolo_id`)

**Interfaces:**
- Produces:
  - `receber_assinado(conn, usuario_id, protocolo_id, pdf: bytes) -> dict` (detalhe com `conferencia`);
  - `previa_envio(conn, protocolo_ids: list[int], remetente: str | None = None, hoje=None) -> dict` com as chaves `para`, `copia`, `assunto`, `corpo`, `anexos` (`[{nome, tamanho}]`), `total`, `limite`, `pendencias` (`[{protocolo_id, codigo, mensagem}]`);
  - `enviar(conn, usuario, protocolo_ids, para, copia, assunto, corpo, justificativa=None, hoje=None) -> int`;
  - `registrar_numero_orgao(conn, usuario_id, protocolo_id, numero, comprovante: bytes | None) -> None`;
  - `descartar(conn, usuario_id, protocolo_id, motivo: str) -> None`.
  - Tipo de envio `"protocolo"`.

- [ ] **Step 1: Testes** (acrescentar em `test_protocolo.py`, com `DASH_GRAPH_SIMULADOR` e `DASH_GRAPH_TOKENS_DIR` no `tmp_path` e o token do usuário gravado como em `tests/test_espelhos.py`)

```python
def _assinar(pdf_montado: bytes, guid="7E965481-0A1B-4C2D-8E9F-0123456789AB") -> bytes:
    """Assinado de mentira: as mesmas paginas, cada uma com o carimbo como texto a mais."""
    import pypdf, io
    from fpdf import FPDF
    r, w = pypdf.PdfReader(io.BytesIO(pdf_montado)), pypdf.PdfWriter()
    for pagina in r.pages:
        f = FPDF(format="A4"); f.add_page(); f.set_font("Helvetica", size=6)
        f.text(5, 5, f"Docusign Envelope ID: {guid}")
        carimbo = pypdf.PdfReader(io.BytesIO(bytes(f.output()))).pages[0]
        pagina.merge_page(carimbo)
        w.add_page(pagina)
    buf = io.BytesIO(); w.write(buf); return buf.getvalue()


def test_assinado_conferido_e_nao_assinado_vira_pendencia(cenario):
    c, ids = cenario
    pid = protocolo.criar(c, ids["uid"], ids["mtpar"], "unico", [ids["mtpar_exec"]], "301")
    r = protocolo.montar(c, ids["uid"], pid)
    montado = arquivos.caminho_seguro(r["arquivo"]).read_bytes()
    d = protocolo.receber_assinado(c, ids["uid"], pid, montado)          # o mesmo PDF, sem carimbo
    assert d["situacao"] == "assinado" and any(x["codigo"] == "conferencia" for x in d["pendencias"])
    d = protocolo.receber_assinado(c, ids["uid"], pid, _assinar(montado))
    assert d["conferencia"]["ok"] and not [x for x in d["pendencias"] if x["codigo"] == "conferencia"]


def test_enviar_mtpar_marca_protocolada_e_liga_o_envio(cenario):
    c, ids = cenario
    pid = protocolo.criar(c, ids["uid"], ids["mtpar"], "unico", [ids["mtpar_exec"]], "301")
    montado = arquivos.caminho_seguro(protocolo.montar(c, ids["uid"], pid)["arquivo"]).read_bytes()
    protocolo.receber_assinado(c, ids["uid"], pid, _assinar(montado))
    pv = protocolo.previa_envio(c, [pid])
    assert pv["assunto"].startswith("CT-301-LT-2026 - 23ª Medição") and pv["anexos"][0]["nome"].endswith(".pdf")
    envio = protocolo.enviar(c, ids["usuario"], [pid], pv["para"], pv["copia"], pv["assunto"], pv["corpo"])
    m = c.execute("SELECT estado FROM medicoes WHERE id=?", (ids["mtpar_exec"],)).fetchone()
    assert m["estado"] == "protocolada"
    mp = c.execute("SELECT protocolo_id, numero_oficio FROM medicao_protocolos WHERE medicao_id=?",
                   (ids["mtpar_exec"],)).fetchone()
    assert (mp["protocolo_id"], mp["numero_oficio"]) == (pid, "CT-301-LT-2026")
    assert protocolo.detalhe(c, pid)["envio_id"] == envio


def test_enviar_com_pendencia_exige_justificativa_e_nada_muda_antes(cenario):
    c, ids = cenario
    pid = protocolo.criar(c, ids["uid"], ids["mtpar"], "unico", [ids["mtpar_exec"]], "301")
    protocolo.montar(c, ids["uid"], pid)                                  # sem assinar: pendencia
    pv = protocolo.previa_envio(c, [pid])
    with pytest.raises(ValueError, match="justificativa"):
        protocolo.enviar(c, ids["usuario"], [pid], pv["para"], pv["copia"], pv["assunto"], pv["corpo"])
    assert c.execute("SELECT COUNT(*) FROM envios").fetchone()[0] == 0
    protocolo.enviar(c, ids["usuario"], [pid], pv["para"], pv["copia"], pv["assunto"], pv["corpo"],
                     justificativa="assinado fisicamente pelo diretor")
    assert json.loads(c.execute("SELECT depois FROM auditoria WHERE acao='protocolo.enviar'").fetchone()[0])[
        "justificativa"] == "assinado fisicamente pelo diretor"


def test_sinfra_medicao_nao_protocola_e_nota_protocola_com_o_oficio_da_medicao(cenario):
    c, ids = cenario
    p1 = protocolo.criar(c, ids["uid"], ids["sinfra"], "medicao", [ids["sinfra_exec"]], "310")
    protocolo.adicionar_peca(c, ids["uid"], p1, "boletim", "b.pdf", carta.pagina_titulo(["B"]), "pdf")
    protocolo.adicionar_peca(c, ids["uid"], p1, "planilha", "planilha.xlsx", b"PK\x03\x04planilha", "xlsx")
    montado = arquivos.caminho_seguro(protocolo.montar(c, ids["uid"], p1)["arquivo"]).read_bytes()
    protocolo.receber_assinado(c, ids["uid"], p1, _assinar(montado))
    pv = protocolo.previa_envio(c, [p1])
    assert {a["nome"] for a in pv["anexos"]} >= {"planilha.xlsx"}
    protocolo.enviar(c, ids["usuario"], [p1], pv["para"], pv["copia"], pv["assunto"], pv["corpo"])
    assert c.execute("SELECT estado FROM medicoes WHERE id=?", (ids["sinfra_exec"],)).fetchone()[0] == "nota_emitida"
    p2 = protocolo.criar(c, ids["uid"], ids["sinfra"], "nota", [ids["sinfra_exec"]], None)
    pv2 = protocolo.previa_envio(c, [p2])
    assert any(a["nome"].startswith("Certidoes - Lotufo") for a in pv2["anexos"])
    protocolo.enviar(c, ids["usuario"], [p2], pv2["para"], pv2["copia"], pv2["assunto"], pv2["corpo"],
                     justificativa="CNO ainda não cadastrado")
    mp = c.execute("SELECT numero_oficio, protocolo_id FROM medicao_protocolos WHERE medicao_id=?",
                   (ids["sinfra_exec"],)).fetchone()
    assert (mp["numero_oficio"], mp["protocolo_id"]) == ("CT-310-LT-2026", p2)


def test_falha_do_graph_nao_muda_estado(cenario, monkeypatch):
    c, ids = cenario
    pid = protocolo.criar(c, ids["uid"], ids["mtpar"], "unico", [ids["mtpar_exec"]], "301")
    montado = arquivos.caminho_seguro(protocolo.montar(c, ids["uid"], pid)["arquivo"]).read_bytes()
    protocolo.receber_assinado(c, ids["uid"], pid, _assinar(montado))
    pv = protocolo.previa_envio(c, [pid])

    def falha(*a, **k):
        raise correio.graph.ErroGraph("fora do ar")

    monkeypatch.setattr(correio, "enviar_e_registrar", falha)
    with pytest.raises(correio.graph.ErroGraph):
        protocolo.enviar(c, ids["usuario"], [pid], pv["para"], pv["copia"], pv["assunto"], pv["corpo"])
    assert protocolo.detalhe(c, pid)["situacao"] == "assinado"
    assert c.execute("SELECT estado FROM medicoes WHERE id=?", (ids["mtpar_exec"],)).fetchone()[0] == "nota_emitida"
```

(`ids["usuario"]` é o dict do usuário com `id` e `email`, como `espelhos.enviar` recebe.)

Em `test_medicoes.py`: `registrar_protocolo(..., protocolo_id=7)` grava a coluna; sem o parâmetro fica `NULL`.

- [ ] **Step 2:** rodar → FAIL.

- [ ] **Step 3: `medicoes.registrar_protocolo`** ganha `protocolo_id: int | None = None` (último parâmetro); o `INSERT INTO medicao_protocolos` inclui a coluna; `depois` da auditoria leva `protocolo_id` quando houver. `correio.MAX_TOTAL = 35 * 1024 * 1024` com o comentário: "35 MB: limite padrão de envio do Exchange Online; a sessão de upload do Graph aceita até 150 MB".

- [ ] **Step 4: `protocolo.py`**, acrescentar:

```python
import io
import zipfile

from app import assinatura, correio, medicoes


def receber_assinado(conn, usuario_id: int, protocolo_id: int, pdf: bytes) -> dict:
    p = _linha(conn, protocolo_id)
    _editavel(p)
    if not p["montado_arquivo"]:
        raise ValueError("Monte o pacote antes de anexar o assinado")
    conf = assinatura.conferir_pdfs(_bytes(p["montado_arquivo"]), pdf)
    rel, sha = arquivos.gravar_bytes("protocolos", pdf, "pdf")
    with db.mutacao(conn):
        conn.execute("UPDATE protocolos SET assinado_arquivo=?, assinado_sha256=?, assinado_em=datetime('now'), "
                     "conferencia=?, situacao='assinado' WHERE id=?", (rel, sha, json.dumps(conf), protocolo_id))
        auditoria.registrar(conn, usuario_id, "protocolo.assinado", "protocolo", protocolo_id, None,
                            {"sha256": sha, "conferencia": conf})
    return detalhe(conn, protocolo_id)


def _familia_e_etapa(conn, p: dict) -> tuple[str, dict, dict, Etapa, dict]:
    c = _contrato(conn, p["contrato_id"])
    familia, regras, o = _orgao(conn, c)
    return familia, regras, o, _etapa(familia, p["etapa"]), c


def _anexos(conn, p: dict, hoje: datetime.date) -> list[tuple[str, bytes]]:
    familia, regras, _, e, c = _familia_e_etapa(conn, p)
    out = []
    if e.carta and (p["assinado_arquivo"] or p["montado_arquivo"]):
        out.append((nome_arquivo(conn, p), _bytes(p["assinado_arquivo"] or p["montado_arquivo"])))
    pecas = _pecas(conn, p["id"])
    tipos_soltos = {x["tipo"] for x in _config_pecas(regras) if x["solto"]}
    for solto in e.soltos:
        if solto == "planilha":
            out += [(x["nome"], _bytes(x["arquivo"])) for x in pecas if x["tipo"] == "planilha"]
        elif solto == "pecas_soltas":
            out += [(x["nome"], _bytes(x["arquivo"])) for x in pecas if x["tipo"] in tipos_soltos]
        elif solto == "notas":
            out += [(d["nome"], _bytes(d["arquivo"])) for d in _docs_nota(conn, [m["id"] for m in _medicoes(conn, p["id"])])]
        elif solto == "certidoes_zip":
            for eid in documentos.exigidos(conn, p["contrato_id"], p["natureza"])["entidades"]:
                try:
                    out.append(documentos.zip_vigentes(conn, eid, hoje.isoformat()))
                except ValueError:
                    pass            # empresa sem nenhuma vigente: ja' e' pendencia 'certidao'
        elif solto == "cno" and c.get("cno_arquivo"):
            out.append((f"CNO - {c.get('nome_curto') or c.get('numero')}.pdf", _bytes(c["cno_arquivo"])))
        elif solto == "regularidade":
            dona = documentos.exigidos(conn, p["contrato_id"], p["natureza"])["regularidade"]
            r = documentos.regularidade_vigente(conn, dona) if dona else None
            if r:
                out.append((r.get("nome_original") or f"Regularidade {r['competencia']}.pdf", _bytes(r["arquivo"])))
    return out


def _destinatarios(conn, p: dict, regras: dict, e: Etapa, c: dict, hoje: datetime.date) -> tuple[list, list]:
    chave = "protocolo_assinados_para" if e.chave == "nota" and regras.get("protocolo_assinados_para") \
        else "protocolo_para"
    para = list(regras.get(chave) or [])
    f = carta.fiscal_vigente(conn, c["id"], hoje.isoformat())
    if f and f["email"] not in para:
        para.append(f["email"])
    para += [x for x in json.loads(c.get("destinatarios_extras") or "[]") if x not in para]
    return para, list(regras.get("protocolo_copia") or [])


def previa_envio(conn, protocolo_ids: list[int], remetente: str | None = None,
                 hoje: datetime.date | None = None) -> dict:
    hoje = hoje or tempo.hoje_local()
    ps = [_linha(conn, i) for i in protocolo_ids]
    if not ps:
        raise ValueError("Escolha ao menos um protocolo")
    familia, regras, _, e, c = _familia_e_etapa(conn, ps[0])
    if any((x["contrato_id"], x["etapa"]) != (ps[0]["contrato_id"], ps[0]["etapa"]) for x in ps):
        raise ValueError("Só protocolos do mesmo contrato e da mesma etapa vão no mesmo e-mail")
    if len(ps) > 1 and not e.junta_naturezas:
        raise ValueError("Nesta família cada protocolo vai no seu e-mail")
    textos = carta.config(conn)["familias"][familia]
    campos = _campos(conn, ps[0], c, familia, regras, [m for x in ps for m in _medicoes(conn, x["id"])], hoje)
    k_assunto, k_corpo = ("nota_email_assunto", "nota_email_corpo") if e.chave == "nota" else \
        ("email_assunto", "email_corpo")
    para, copia = _destinatarios(conn, ps[0], regras, e, c, hoje)
    if remetente:
        copia = [x for x in copia if x.lower() != remetente.lower()]
    anexos = [a for x in ps for a in _anexos(conn, x, hoje)]
    total = sum(len(b) for _, b in anexos)
    pend = [{"protocolo_id": x["id"], **q} for x in ps for q in pendencias(conn, x, hoje)]
    if total > correio.MAX_TOTAL:
        pend.append({"protocolo_id": None, "codigo": "tamanho",
                     "mensagem": f"Anexos somam {total // (1024 * 1024)} MB, acima do limite do e-mail"})
    return {"para": para, "copia": copia, "assunto": carta.preencher(textos[k_assunto], campos),
            "corpo": carta.preencher(textos[k_corpo], campos).strip(),
            "anexos": [{"nome": n, "tamanho": len(b)} for n, b in anexos], "total": total,
            "limite": correio.MAX_TOTAL, "pendencias": pend}


def _html(corpo: str) -> str:
    from html import escape
    return "".join(f"<p>{escape(par).replace(chr(10), '<br>')}</p>" for par in corpo.strip().split("\n\n"))


def _oficio_da_medicao(conn, medicao_id: int) -> str | None:
    r = conn.execute("SELECT p.numero_oficio FROM protocolo_medicoes pm JOIN protocolos p ON p.id=pm.protocolo_id "
                     "WHERE pm.medicao_id=? AND p.situacao='enviado' AND p.numero_oficio IS NOT NULL "
                     "ORDER BY p.id DESC LIMIT 1", (medicao_id,)).fetchone()
    return r[0] if r else None


def enviar(conn, usuario: dict, protocolo_ids: list[int], para: list[str], copia: list[str], assunto: str,
           corpo: str, justificativa: str | None = None, hoje: datetime.date | None = None) -> int:
    hoje = hoje or tempo.hoje_local()
    pv = previa_envio(conn, protocolo_ids, hoje=hoje)
    ps = [_linha(conn, i) for i in protocolo_ids]
    _, _, _, e, _ = _familia_e_etapa(conn, ps[0])
    # Tudo o que recusa vem ANTES do e-mail (que nao se desfaz).
    for x in ps:
        if x["situacao"] in ("enviado", "descartado"):
            raise ValueError(f"Protocolo {x['id']} já {x['situacao']}")
        if e.carta and not x["montado_arquivo"]:
            raise ValueError("Monte o pacote antes de enviar")
        for m in _medicoes(conn, x["id"]):
            if m["estado"] in ENCERRADAS:
                raise ValueError(f"{titulo(m)} está {m['estado']}")
    if not [x for x in para if x.strip()]:
        raise ValueError("Informe ao menos um destinatário")
    if pv["total"] > correio.MAX_TOTAL:
        raise ValueError("Anexos acima do limite do e-mail; divida o envio")
    if pv["pendencias"] and not (justificativa or "").strip():
        raise ValueError(f"{len(pv['pendencias'])} pendência(s) na prévia: informe a justificativa para enviar assim")
    anexos = [a for x in ps for a in _anexos(conn, x, hoje)]
    envio_id = correio.enviar_e_registrar(conn, usuario, "protocolo", para, copia, assunto, _html(corpo), anexos)
    certidao_pendente = any(q["codigo"] == "certidao" for q in pv["pendencias"])
    with db.mutacao(conn):
        for x in ps:
            conn.execute("UPDATE protocolos SET envio_id=?, situacao='enviado', justificativa=? WHERE id=?",
                         (envio_id, (justificativa or "").strip() or None, x["id"]))
            for m in _medicoes(conn, x["id"]):
                conn.execute("INSERT OR IGNORE INTO envio_medicoes (envio_id, medicao_id) VALUES (?,?)",
                             (envio_id, m["id"]))
                if e.marca_protocolada:
                    oficio = x["numero_oficio"] or _oficio_da_medicao(conn, m["id"])
                    medicoes.registrar_protocolo(conn, usuario["id"], m["id"], hoje.isoformat(), oficio, None,
                                                 "manual", apesar_das_pendencias=certidao_pendente,
                                                 justificativa=justificativa if certidao_pendente else None,
                                                 protocolo_id=x["id"])
            auditoria.registrar(conn, usuario["id"], "protocolo.enviar", "protocolo", x["id"], None,
                                {"envio_id": envio_id, "pendencias": pv["pendencias"],
                                 "justificativa": (justificativa or "").strip() or None})
    return envio_id


def registrar_numero_orgao(conn, usuario_id: int, protocolo_id: int, numero: str,
                           comprovante: bytes | None) -> None:
    p = _linha(conn, protocolo_id)
    if p["situacao"] != "enviado":
        raise ValueError("Só protocolo enviado recebe o número do órgão")
    rel = arquivos.gravar_bytes("protocolos", comprovante, "pdf")[0] if comprovante else p["comprovante_arquivo"]
    with db.mutacao(conn):
        conn.execute("UPDATE protocolos SET numero_orgao=?, comprovante_arquivo=? WHERE id=?",
                     (numero.strip() or None, rel, protocolo_id))
        auditoria.registrar(conn, usuario_id, "protocolo.numero_orgao", "protocolo", protocolo_id,
                            {"numero_orgao": p["numero_orgao"]}, {"numero_orgao": numero.strip(), "comprovante": rel})


def descartar(conn, usuario_id: int, protocolo_id: int, motivo: str) -> None:
    p = _linha(conn, protocolo_id)
    if p["situacao"] == "enviado":
        raise ValueError("Protocolo enviado não se descarta")
    if not (motivo or "").strip():
        raise ValueError("Informe o motivo")
    with db.mutacao(conn):
        conn.execute("UPDATE protocolos SET situacao='descartado' WHERE id=?", (protocolo_id,))
        auditoria.registrar(conn, usuario_id, "protocolo.descartar", "protocolo", protocolo_id,
                            {"situacao": p["situacao"]}, {"situacao": "descartado", "motivo": motivo.strip()})
```

Nota: a medição que já é `protocolada` recebe só uma linha nova em `medicao_protocolos` (é o que `registrar_protocolo` faz hoje para estado posterior). A validação do checklist dentro de `registrar_protocolo` é a mesma da prévia: com `apesar_das_pendencias` e justificativa, passa. Na etapa da nota da SINFRA, o `numero_oficio` vem do protocolo da etapa da medição.

- [ ] **Step 5:** rodar `tests/test_protocolo.py tests/test_medicoes.py tests/test_correio.py` → PASS.
- [ ] **Step 6: Commit** `feat: protocolo - assinado conferido, previa e envio que marca protocolada`.

---

### Task 5.9: Rotas (`api_protocolos.py`)

**Files:**
- Create: `backend/app/api_protocolos.py`
- Modify: `backend/app/main.py` (incluir o router)
- Test: `backend/tests/test_api_protocolos.py`

**Interfaces (rotas):** leitura com `exigir("ver_paineis", com_csrf=False)`; escrita com `exigir("editar_cadastros")`.

| Método e caminho | Corpo | Resposta |
|---|---|---|
| `GET /api/contratos/{id}/protocolos` | — | `protocolo.listar` |
| `POST /api/contratos/{id}/protocolos` | `{etapa, medicao_ids, numero_oficio}` | detalhe (201) |
| `GET /api/protocolos/{pid}` | — | detalhe + `corpo_padrao` quando `corpo_carta` é nulo |
| `POST /api/protocolos/{pid}/pecas` | multipart `tipo`, `arquivo` (PDF até 40 MB ou `.xlsx` até 25 MB) | detalhe |
| `POST /api/protocolos/{pid}/pecas/{peca_id}/remover` | — | detalhe |
| `POST /api/protocolos/{pid}/montar` | `{corpo?}` | detalhe |
| `GET /api/protocolos/{pid}/pacote` | — | PDF montado (`FileResponse`, nome `nome_arquivo`) |
| `GET /api/protocolos/{pid}/assinado` | — | PDF assinado |
| `POST /api/protocolos/{pid}/assinado` | multipart `arquivo` (PDF até 40 MB) | detalhe |
| `POST /api/protocolos/envio/previa` | `{protocolo_ids}` | `previa_envio` (remetente = e-mail do usuário) |
| `POST /api/protocolos/envio` | `{protocolo_ids, para, copia, assunto, corpo, justificativa?}` | `{envio_id}` |
| `POST /api/protocolos/{pid}/numero-orgao` | multipart `numero`, `comprovante?` | detalhe |
| `POST /api/protocolos/{pid}/descartar` | `{motivo}` | `{ok: true}` |

Erros: `ValueError` → 422 com a mensagem; `ErroGraph` → 502 ("Falha ao enviar pelo Microsoft 365: …; nada foi registrado"); protocolo ou contrato inexistente → 404. Upload de peça: `tipo` em `protocolo.TIPOS_PECA` (`Literal`); PDF por `arquivos.blocos_validados(arquivo, teto_bytes=pdfs.TETO_BYTES_PACOTE)`, planilha por `blocos_validados(arquivo, teto_bytes=25 MB, tipo="xlsx")` (a escolha é pela extensão do nome: `.xlsx` → planilha). O assinado passa também pelo teto de páginas (a conferência já roda em subprocesso).

- [ ] **Step 1: Testes** (fluxo feliz pela API com `client_admin` e o simulador do Graph; peça com tipo inválido → 422; download do pacote → `application/pdf` e `Content-Disposition` com o nome do §4.4; envio sem destinatário → 422; usuário diretoria não cria protocolo → 403). Montar o cenário pelos helpers de `test_protocolo.py` (importar a fixture como função auxiliar).
- [ ] **Step 2:** rodar → FAIL. **Step 3:** implementar no padrão de `api_espelhos.py` e `api_documentos.py` (modelos Pydantic `CriarIn`, `MontarIn`, `PreviaIn`, `EnvioIn`, `DescartarIn`). **Step 4:** rodar → PASS.
- [ ] **Step 5: Commit** `feat: rotas do protocolo`.

---

### Task 5.10: Tela do protocolo (`Protocolo.tsx`)

**Files:**
- Create: `frontend/src/Protocolo.tsx`, `frontend/src/Protocolo.test.tsx`
- Modify: `frontend/src/ContratoPagina.tsx` (a aba `protocolo` mostra `<Protocolo contratoId=... usuario=... />` no lugar do checklist solto; o checklist aparece dentro da prévia como pendência)

**Comportamento da tela** (uma coluna, cartões em sequência; classes existentes):
1. **Novo protocolo**:
   - escolher a etapa (botões com os rótulos de `listar().etapas`);
   - marcar a(s) medição(ões) (checkbox; na SINFRA execução e reajuste podem ir juntas no e-mail, mas cada uma vira um protocolo: a tela cria um por medição quando marcadas duas);
   - digitar o número do ofício (só etapa com carta; placeholder "301");
   - "Criar".
2. **Protocolo aberto** (um cartão por protocolo não enviado):
   - cabeçalho com etapa, medições, ofício e situação;
   - **Peças**: para cada peça do órgão, rótulo, "(exigida)" quando for o caso, botão "Anexar" (PDF ou `.xlsx` na planilha), lista com remover;
   - **Carta**: textarea com o corpo (padrão vindo da API), com a nota "Linha em branco separa parágrafos; `# ` abre título; `i.`/`1.` é item";
   - "Montar pacote" → link "Baixar pacote (N páginas, X MB)";
   - **Assinado**: "Arrastar o PDF assinado" → resultado da conferência (ok em `notas__ok`; cada aviso em `notas__diverge`).
3. **Enviar** (um ou mais protocolos marcados da mesma etapa):
   - "Prévia" carrega para, cópia, assunto e corpo (editáveis, como no espelho), mais anexos com tamanho, total e limite;
   - pendências em lista `aviso`; se houver pendência, campo "Justificativa (obrigatória para enviar assim)";
   - "Enviar" → mensagem de sucesso com a data. Falha mostra a mensagem da API e não muda nada.
4. **Enviados**: lista com data, ofício e envio; "Número do protocolo do órgão" (campo mais comprovante opcional).
5. "Registrar protocolo feito por fora" continua como link discreto, abrindo o formulário antigo (`Medicoes.tsx`).

- [ ] **Step 1: Teste** (`Protocolo.test.tsx`, no padrão de `Espelho.test.tsx`, com `fetch` simulado):
  - (a) a tela lista as etapas e cria um protocolo com o número digitado;
  - (b) a prévia com pendência só habilita "Enviar" com justificativa preenchida;
  - (c) a conferência com aviso aparece em destaque.
- [ ] **Step 2:** `cd frontend && npm test -- --run src/Protocolo.test.tsx` → FAIL. **Step 3:** implementar. **Step 4:** PASS; `npm run build` limpo.
- [ ] **Step 5: Verificação visual** (servidor `backend-review` sobre cópia da produção, obra MTPAR Complexo Cultural): criar, montar, baixar e abrir o PDF, anexar o próprio PDF (conferência acusa "não assinado"), prévia com pendências. **Não enviar** nada da cópia: o simulador do Graph deve estar ligado no `backend-review` (`DASH_GRAPH_SIMULADOR`).
- [ ] **Step 6: Commit** `feat: tela do protocolo (pecas, carta, pacote, assinado, previa e envio)`.

---

### Task 5.11: Cadastro real e prova com os PDFs reais

**Files:**
- Modify: `cadastro/cartas.yaml` (textos reais do levantamento 5.0), `cadastro/orgaos.yaml` (`carta_destinatario`, `pecas`, `ordem_certidoes` de cada órgão), `cadastro/contratos/*.yaml` (`cargo`, `tratamento`, `portaria` dos fiscais onde as cartas reais mostram; `objeto_completo` onde já estiver em comentário)
- Create: `backend/tests/fixtures/assinatura/*.json` (textos por página dos três PDFs reais; sem PDF no repositório)
- Test: `backend/tests/test_assinatura.py` (acrescentar a prova com textos reais)

- [ ] **Step 1: Textos reais.** Trocar os textos de `cartas.yaml` pelos do levantamento, **literalmente**. Nos órgãos:
  - MTPAR: `carta_destinatario: ["A MT PARTICIPAÇÕES E PROJETOS S.A – MT-PAR"]`, `ordem_certidoes: [municipal, trabalhista, estadual, federal, fgts]`.
  - SES: `carta_destinatario: ["A SUPERINTENDÊNCIA DE OBRAS REFORMAS E MANUTENÇÕES"]`, `ordem_certidoes: [estadual, federal, fgts, municipal, trabalhista]` e peças na ordem do pacote real de Alta Floresta:

```yaml
    pecas:
      - {tipo: art, rotulo: "CÓPIA DAS ART'S", exigida: true}
      - {tipo: diario, rotulo: DIÁRIO DE OBRA, exigida: true}
      - {tipo: fotos, rotulo: RELATÓRIOS FOTOGRÁFICOS, exigida: true}
      - {tipo: cronograma, rotulo: CRONOGRAMA FÍSICO-FINANCEIRO, exigida: true}
      - {tipo: boletim, rotulo: BOLETIM DE MEDIÇÃO, exigida: true}
      - {tipo: memorial, rotulo: MEMORIAIS, exigida: false}
      - {tipo: ensaios, rotulo: ENSAIOS, exigida: false}
```

  - SINFRA: nas cinco superintendências, `pecas` na ordem do check-list da IN 001/2024 (levantamento 5.0); no mínimo, boletim assinado exigido e planilha editável exigida e solta. `carta_destinatario` com a linha da secretaria e a da superintendência.
  - Prefeituras: `pecas: [{tipo: fotos, rotulo: Relatório fotográfico, exigida: false, solto: true}]`.
- [ ] **Step 2: Prova da conferência com PDF real.** Script no scratchpad que extrai `textos_por_pagina_com_limite` de:
  - (a) `C:\Users\<usuario>\dev\aditivos-lotufo\cavalaria\Protocolo\21.08.2026-CT-291-LT-2026-1a_RPFO_-_IC_04-2026_-_Sede_Cavalaria-Assinado.pdf` e do `...-PROTOCOLO.pdf` ao lado;
  - (b) `...\mt-388\...\CT-073-LT-2026 - Revisão Estudos Hidrológicos\Complete_com_o_Docusign_CT073-LT-2026_-_CT_0.pdf`, comparado com as suas 4 primeiras páginas como "montado";
  - (c) o CT-286 da Orla, do scratchpad `protocolos/`.

  Rodar `assinatura.conferir` e registrar:
  - (a) ok (se falhar, anotar a razão de semelhança por página e ajustar `LIMIAR` entre 0,80 e 0,95 com a menor razão das páginas certas; a trocada tem de continuar abaixo);
  - (b) ok com `certificado == 4`;
  - (c) `nao_assinado`.

  Guardar os textos por página (só texto, sem imagem) como JSON em `backend/tests/fixtures/assinatura/` e escrever um teste que roda os três casos. Os textos da Cavalaria são de um aditivo da própria Lotufo (sem dado pessoal além do nome do diretor e do fiscal, que constam das cartas públicas); se houver CPF em alguma página, trocar por `000.000.000-00` no JSON.
- [ ] **Step 3: Ensaio do cadastro.** `python -m app.cli cadastro validar` e `cadastro aplicar --ensaio` sobre cópia da produção: diferença só nos campos novos.
- [ ] **Step 4: Commit** `feat: textos reais das cartas, pecas por orgao e prova da conferencia com PDFs reais`.

---

### Task 5.12: Documentação, suíte, gate Sol

- [ ] **Step 1: Runbook**, seção "Protocolo de medição (bloco 5)":
  - fluxo da operação;
  - famílias e etapas (a tabela da decisão 3);
  - onde mudar textos (`cartas.yaml`), peças e ordem (`orgaos.yaml`) e CNO (`cno_pdf`);
  - "a conferência do assinado é aviso".

  **Backlog**: CNO dos 22 contratos (P2); cargos, tratamentos e portarias que faltam; check-list SINFRA se o levantamento não fechou; `LIMIAR` calibrado.
- [ ] **Step 2:** suíte inteira do backend; depois `npm test -- --run` e `npm run build` (nunca em paralelo).
- [ ] **Step 3: Gate Sol** (se mantido, DT1), um round, sobre o diff da branch:

```bash
git diff master...bloco5-protocolo | codex exec -m gpt-5.6-sol --skip-git-repo-check "Revise este diff (FastAPI + SQLite, protocolo de medição com PDF montado, PDF assinado conferido e envio de e-mail pelo Graph). Procure bugs reais: envio que muda estado antes de o e-mail ser aceito, arquivo fora da pasta de dados, PDF hostil lido fora do subprocesso, justificativa contornável, medição encerrada protocolada, pendência que some sem ato. Responda em português, cada achado com arquivo:linha e cenário concreto."
```

  Corrigir o que for real, com teste. Registrar no backlog os achados recusados, cada um com a evidência.
- [ ] **Step 4: Commit** `docs: runbook e backlog do bloco 5`. Seguir para o bloco 6 (a branch `bloco6-inicio` nasce desta).

## Self-review (feito ao escrever)

- **Spec §3 passos 4 a 7:**
  - ofício digitado: 5.3 e 5.7;
  - peças: 5.7;
  - carta com dados: 5.2 e 5.7;
  - notas, certidões, regularidade e CNO na ordem do órgão: 5.7 e 5.8;
  - assinar por fora e arrastar de volta: 5.8;
  - prévia com destinatários, cópias, assunto, anexos com tamanho e o que falta: 5.8 e 5.10;
  - enviar marca protocolada: 5.8;
  - número do órgão e comprovante: 5.8.
- **Spec §5.3:**
  - MTPAR em PDF único, separado por natureza, pedindo devolutiva (no corpo do e-mail);
  - SINFRA com duas etapas e 25 MB;
  - SES com carta de lista numerada;
  - prefeitura com corpo editável para link.
- **Spec §6:**
  - as três regras da conferência: 5.5;
  - acima de 25 MB vira aviso: 5.7.
- **Spec §5.1:** falha de envio não muda estado (teste da 5.8); o registro de anexos com hash vem do `correio` existente.
- **Tipos e nomes:** `protocolo.enviar(conn, usuario: dict, ...)` recebe o dict do usuário, como `espelhos.enviar`; as demais funções recebem `usuario_id`.
