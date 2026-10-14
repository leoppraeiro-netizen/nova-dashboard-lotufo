# Bloco 6 (Tela inicial e avisos): registro único de avisos, tela inicial da operação, lista de medições, página da obra. Plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. **Leia antes `00-indice.md`.** Branch `bloco6-inicio`, criada de `bloco5-protocolo`.

**Goal:** a operação abre o sistema e vê, numa tela, os avisos do catálogo da spec (§11) com obra, dias e valor, quantas obras ativas já protocolaram no mês e o valor protocolado no mês e no anterior. Pela lista de medições em andamento retoma de onde parou. A página da obra ganha o cabeçalho da spec §10.3 e as abas Medições, Notas, Documentos, Reajuste, Prazos e Contrato.

**Architecture:**
- `app/avisos.py` é o registro único: uma lista `FONTES` de funções `(conn, hoje) -> list[aviso]`, cada aviso no formato do índice. Neste bloco entram três fontes:
  - documentos (do bloco 4);
  - notas (do bloco 3);
  - prazo do contrato (versão simples). O bloco 7 troca essa fonte pela de `prazos` e `reajuste`; o bloco 8 acrescenta a de pagamento.
- `paineis.alertas` passa a devolver `avisos.listar`.
- `app/api_inicio.py` serve a tela inicial e a lista de medições.
- A página da obra reorganiza as abas sem mudar as rotas de dados que já existem.
- Nenhuma migração.

**Tech Stack:** o do índice.

**Spec:** §10.1 (tela inicial), §10.2 (medições), §10.3 (página da obra), §11 (catálogo: nesta etapa "Documentos da empresa", "Regularidade do mês", "Nota divergente do espelho", "Nota ausente do RM", "Execução vencendo", "Vigência vencendo").

**Status:** APROVADO pelo Leonardo em 2026-09-24 (ver `00-indice.md`).

## Decisões deste bloco (para aprovação)

1. **Formato único de aviso** (índice): tipo, nível (`critico`, `acao`, `atencao`), público (`operacao`, `diretoria`), contrato e obra, dias, valor, mensagem de uma linha e destino do clique. Ordem na tela: nível, depois o campo `dias` em ordem crescente (prazo que vence antes, ou que já venceu, vem primeiro), depois obra.
2. **Saem da tela** os alertas antigos:
   - `reajuste_sem_par`: a spec manda tirar;
   - `data_base`: vira "pleito não enviado" no bloco 7;
   - `medicao_sem_protocolo`: a spec tira "pendências";
   - `vigencia_vencida` e `execucao_vencida`: viram níveis do aviso de prazo.

   A função `paineis._alertas_*` que os gerava sai do caminho da tela. O código antigo que só eles usam sai no bloco 9.
3. **Aviso de prazo, versão do bloco 6**:
   - **Execução:** aparece a 60 dias do fim, como `atencao`. Vira `critico` a 30 dias e depois de vencida.
   - **Vigência:** aparece só em órgão com `vigencia_automatica: false`, a 60 dias.
   - **Quando não aparece:** para contrato em encerramento e para contrato suspenso.

   O bloco 7 substitui esta versão pela completa: pedido enviado, instrumento pendente, paralisação, folga, endosso.
4. **"Medições protocoladas no mês: X de N"**:
   - N = contratos `ativo` sem `encerramento_iniciado_em`;
   - X = desses, os que têm ao menos uma medição cuja **primeira** data de protocolo (`medicao_protocolos.data`) cai no mês.

   **Valor protocolado** = soma do `valor_protocolado_centavos` (cheio) das medições cuja primeira data de protocolo cai no mês. O mês anterior segue a mesma regra. Reprotocolo não conta duas vezes.
5. **Medições em andamento**:
   - **Estados listados:** `espelho_gerado`, `espelho_enviado`, `nota_emitida`, `protocolada` e `nf_emitida`. Recebida, cancelada, desistida e prevista ficam de fora.
   - **Próximo passo, em texto fixo por estado:**
     - espelho gerado: "enviar ao faturamento";
     - espelho enviado: "anexar as notas";
     - nota emitida: "protocolar";
     - protocolada: "aguardando pagamento".
   - **Filtros:** obra e estado.
6. **Abas da obra.**
   - Medições traz o espelho, as medições e o protocolo do bloco 5.
   - Notas lista as notas da obra, por medição, com a situação da conferência.
   - Documentos mostra o que a obra exige de cada empresa, na medição e no reajuste, com a situação de hoje.
   - Reajuste e Prazos mostram, neste bloco, o que o cadastro tem (datas-base, apostilamentos, instrumentos de prazo, paralisações, fiscais); as ações entram no bloco 7.
   - Contrato mostra, só para leitura, o cadastro do contrato, o cronograma e os aditivos.
   - Links antigos continuam valendo: `/contratos/7/protocolo` abre Medições; `/cronograma` e `/aditivos` abrem Contrato.
7. **Menu e tela inicial.**
   - Menu: Início, Medições, Obras, Documentos, Painel (só diretoria e admin, até o bloco 8 trocar pela Diretoria) e Administração.
   - Sugestões e Engenharia saem do menu; as rotas continuam até o bloco 9.
   - A raiz abre Início para operação e admin, e Painel para diretoria.

## Estrutura de arquivos

| Arquivo | Responsabilidade |
|---|---|
| `backend/app/avisos.py` | registro, fontes do bloco 6, `listar`, `resumo_mes` |
| `backend/app/paineis.py` | `alertas` delega para `avisos.listar` |
| `backend/app/medicoes.py` | `em_andamento(conn, contrato_id=None, estado=None) -> list[dict]` |
| `backend/app/contratos.py` | `cabecalho(conn, contrato_id, hoje=None) -> dict`; `cadastro_da_obra(conn, contrato_id) -> dict` |
| `backend/app/notas.py` | `do_contrato(conn, contrato_id) -> list[dict]` |
| `backend/app/api_inicio.py`, `api_contratos.py`, `main.py` | rotas novas |
| `frontend/src/Inicio.tsx`, `MedicoesLista.tsx`, `Alertas.tsx` | tela inicial, lista, avisos no formato novo |
| `frontend/src/ContratoPagina.tsx`, `ObraAbas.tsx` | cabeçalho e abas (Notas, Documentos, Reajuste, Prazos, Contrato) |
| `frontend/src/rota.tsx`, `App.tsx` | telas `inicio` e `medicoes`, abas novas, menu |

---

### Task 6.1: Registro de avisos (`avisos.py`)

**Files:**
- Create: `backend/app/avisos.py`
- Modify: `backend/app/paineis.py` (`alertas`)
- Test: `backend/tests/test_avisos.py`; ajustar `backend/tests/test_paineis.py` (os testes dos tipos que saíram passam a afirmar que eles NÃO aparecem)

**Interfaces:**
- Consumes: `documentos.avisos(conn, hoje) -> [{tipo, nivel, entidade_id, contrato_id, mensagem}]`; `notas.avisos(conn, hoje) -> [{tipo, nota_id, numero, medicao_id, contrato_id, dias, mensagem}]`; `contratos.vigente(conn, contrato_id) -> {execucao_fim_vigente, vigencia_fim_vigente, ...}`.
- Produces:
  - `FONTES: list`;
  - `NIVEIS = ("critico", "acao", "atencao")`;
  - `listar(conn, hoje=None, publico="operacao") -> list[dict]`;
  - `resumo_mes(conn, hoje=None) -> dict`, com as chaves `mes`, `obras_protocoladas`, `obras_ativas`, `valor_mes_centavos` e `valor_mes_anterior_centavos`;
  - `obra(conn, contrato_id) -> str | None`;
  - `ativos(conn) -> list[dict]`, com os contratos `ativo` sem encerramento.

- [ ] **Step 1: Testes** (banco temporário com contrato de órgão, no padrão de `test_documentos.py`)

```python
"""Registro unico de avisos (spec §11) e resumo do mes da tela inicial (§10.1)."""
import datetime

from app import avisos, tempo

D = datetime.date


def test_aviso_de_execucao_nivel_por_dias(cenario):
    c, ids = cenario                          # contrato ativo, execucao termina em 2026-10-20
    tipos = {a["tipo"]: a for a in avisos.listar(c, D(2026, 9, 1))}
    assert tipos["execucao_vencendo"]["nivel"] == "atencao" and tipos["execucao_vencendo"]["dias"] == 49
    assert {a["tipo"]: a for a in avisos.listar(c, D(2026, 10, 1))}["execucao_vencendo"]["nivel"] == "critico"
    assert "execucao_vencendo" not in {a["tipo"] for a in avisos.listar(c, D(2026, 7, 1))}


def test_vigencia_so_em_orgao_sem_prorrogacao_automatica(cenario):
    c, ids = cenario                          # orgao SINFRA (vigencia_automatica: true), vigencia 2026-10-30
    assert "vigencia_vencendo" not in {a["tipo"] for a in avisos.listar(c, D(2026, 10, 1))}


def test_contrato_em_encerramento_nao_tem_aviso_de_prazo(cenario):
    c, ids = cenario
    c.execute("UPDATE contratos SET encerramento_iniciado_em='2026-09-01' WHERE id=?", (ids["contrato"],)); c.commit()
    assert not [a for a in avisos.listar(c, D(2026, 10, 1)) if a["tipo"].startswith("execucao")]


def test_formato_e_publico(cenario):
    c, ids = cenario
    for a in avisos.listar(c, D(2026, 10, 1)):
        assert set(a) >= {"tipo", "nivel", "publico", "contrato_id", "obra", "dias", "valor_centavos",
                          "mensagem", "destino"}
        assert a["nivel"] in avisos.NIVEIS and "operacao" in a["publico"]
    assert avisos.listar(c, D(2026, 10, 1), publico="diretoria") == [
        a for a in avisos.listar(c, D(2026, 10, 1), publico="todos") if "diretoria" in a["publico"]]


def test_avisos_antigos_sairam(cenario):
    c, ids = cenario
    tipos = {a["tipo"] for a in avisos.listar(c, D(2026, 10, 1))}
    assert not tipos & {"reajuste_sem_par", "data_base", "medicao_sem_protocolo", "vigencia_vencida", "execucao_vencida"}


def test_resumo_do_mes_conta_primeiro_protocolo(cenario):
    c, ids = cenario                          # duas medicoes do contrato; a 1a protocolada em 08/09 e reprotocolada em 15/09
    r = avisos.resumo_mes(c, D(2026, 9, 20))
    assert (r["obras_protocoladas"], r["obras_ativas"]) == (1, 1)
    assert r["valor_mes_centavos"] == 1_000_000 and r["valor_mes_anterior_centavos"] == 0
```

- [ ] **Step 2:** rodar → FAIL.

- [ ] **Step 3: Implementação**

```python
"""Registro unico dos avisos da operacao e da diretoria (spec 2026-09-21 §11), bloco 6.

Cada FONTE e' uma funcao (conn, hoje) -> [aviso]. O bloco 6 registra documentos, notas e o prazo do
contrato; o bloco 7 troca o prazo simples pelos avisos de `prazos` e `reajuste`; o bloco 8 acrescenta
o pagamento atrasado. A tela nao sabe de onde o aviso vem: so' le o formato.

Formato: {tipo, nivel: critico|acao|atencao, publico: [operacao|diretoria], contrato_id, obra, dias,
valor_centavos, mensagem, destino}. Aviso some por ato real (documento gravado, carta enviada,
instrumento carregado), nunca por "dispensar".
"""
import datetime
import json

from app import contratos, documentos, notas, tempo

NIVEIS = ("critico", "acao", "atencao")
_ORDEM = {n: i for i, n in enumerate(NIVEIS)}
DIAS_EXECUCAO, DIAS_CRITICO, DIAS_VIGENCIA = 60, 30, 60


def aviso(tipo, nivel, mensagem, contrato_id=None, obra=None, dias=None, valor_centavos=None,
          publico=("operacao",), destino=None) -> dict:
    return {"tipo": tipo, "nivel": nivel, "publico": list(publico), "contrato_id": contrato_id, "obra": obra,
            "dias": dias, "valor_centavos": valor_centavos, "mensagem": mensagem,
            "destino": destino or ({"tela": "contrato", "id": contrato_id, "aba": "medicoes"} if contrato_id else None)}


def obra(conn, contrato_id: int | None) -> str | None:
    if not contrato_id:
        return None
    r = conn.execute("SELECT nome_curto, numero FROM contratos WHERE id=?", (contrato_id,)).fetchone()
    return (r["nome_curto"] or r["numero"]) if r else None


def ativos(conn) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT * FROM contratos WHERE estado='ativo' AND encerramento_iniciado_em IS NULL ORDER BY nome_curto, id")]


def _de_documentos(conn, hoje: datetime.date) -> list[dict]:
    return [aviso(a["tipo"], a["nivel"], a["mensagem"], a.get("contrato_id"), obra(conn, a.get("contrato_id")),
                  destino={"tela": "documentos"}) for a in documentos.avisos(conn, hoje)]


_NIVEL_NOTA = {"nota_divergente": "acao", "nota_ausente_rm": "atencao", "nota_cancelada_rm": "acao"}


def _de_notas(conn, hoje: datetime.date) -> list[dict]:
    out = []
    for a in notas.avisos(conn, hoje):
        cid = a.get("contrato_id")
        out.append(aviso(a["tipo"], _NIVEL_NOTA.get(a["tipo"], "atencao"), a["mensagem"], cid, obra(conn, cid),
                         dias=a.get("dias"),
                         destino={"tela": "contrato", "id": cid, "aba": "notas"} if cid else None))
    return out


def _regras_orgao(conn, c: dict) -> dict:
    if not c.get("orgao_id"):
        return {}
    r = conn.execute("SELECT regras FROM orgaos WHERE id=?", (c["orgao_id"],)).fetchone()
    return json.loads(r["regras"]) if r else {}


def _de_contrato(conn, hoje: datetime.date) -> list[dict]:
    """Prazo simples do bloco 6 (o bloco 7 troca por `prazos.avisos`)."""
    out = []
    for c in ativos(conn):
        v = contratos.vigente(conn, c["id"])
        nome = c.get("nome_curto") or c.get("numero")
        fim = v.get("execucao_fim_vigente")
        if fim:
            dias = (datetime.date.fromisoformat(fim) - hoje).days
            if dias <= DIAS_EXECUCAO:
                nivel = "critico" if dias <= DIAS_CRITICO else "atencao"
                msg = (f"{nome}: execução vencida há {-dias} dias ({fim[8:10]}/{fim[5:7]}/{fim[:4]})" if dias < 0
                       else f"{nome}: execução termina em {dias} dias ({fim[8:10]}/{fim[5:7]}/{fim[:4]})")
                out.append(aviso("execucao_vencendo", nivel, msg, c["id"], nome, dias=dias,
                                 destino={"tela": "contrato", "id": c["id"], "aba": "prazos"}))
        vig = v.get("vigencia_fim_vigente")
        if vig and _regras_orgao(conn, c).get("vigencia_automatica") is False:
            dias = (datetime.date.fromisoformat(vig) - hoje).days
            if dias <= DIAS_VIGENCIA:
                out.append(aviso("vigencia_vencendo", "critico" if dias <= DIAS_CRITICO else "atencao",
                                 f"{nome}: vigência termina em {dias} dias" if dias >= 0
                                 else f"{nome}: vigência vencida há {-dias} dias", c["id"], nome, dias=dias,
                                 destino={"tela": "contrato", "id": c["id"], "aba": "prazos"}))
    return out


FONTES = [_de_documentos, _de_notas, _de_contrato]


def listar(conn, hoje: datetime.date | None = None, publico: str = "operacao") -> list[dict]:
    hoje = hoje or tempo.hoje_local()
    todos = [a for fonte in FONTES for a in fonte(conn, hoje)]
    if publico != "todos":
        todos = [a for a in todos if publico in a["publico"]]
    # nivel; depois dias crescente (vencido ha mais tempo tem dias mais negativo e vem antes); sem dias, no fim
    return sorted(todos, key=lambda a: (_ORDEM[a["nivel"]], a["dias"] if a["dias"] is not None else 9999,
                                        a["obra"] or ""))


def _mes(d: datetime.date) -> str:
    return d.strftime("%Y-%m")


def resumo_mes(conn, hoje: datetime.date | None = None) -> dict:
    hoje = hoje or tempo.hoje_local()
    mes, ant = _mes(hoje), _mes(hoje.replace(day=1) - datetime.timedelta(days=1))
    ids_ativos = {c["id"] for c in ativos(conn)}
    linhas = conn.execute(
        "SELECT m.id, m.contrato_id, COALESCE(m.valor_protocolado_centavos, 0) AS valor, MIN(mp.data) AS data "
        "FROM medicoes m JOIN medicao_protocolos mp ON mp.medicao_id=m.id "
        "WHERE m.estado NOT IN ('cancelada','desistida') GROUP BY m.id").fetchall()
    no_mes = [l for l in linhas if (l["data"] or "")[:7] == mes]
    return {"mes": mes, "obras_ativas": len(ids_ativos),
            "obras_protocoladas": len({l["contrato_id"] for l in no_mes} & ids_ativos),
            "valor_mes_centavos": sum(l["valor"] for l in no_mes),
            "valor_mes_anterior_centavos": sum(l["valor"] for l in linhas if (l["data"] or "")[:7] == ant)}
```

Em `paineis.py`, `alertas(conn, hoje=None)` passa a ser `return avisos.listar(conn, hoje)`. Os testes de `test_paineis.py` que conferiam os tipos antigos são reescritos para o formato novo, e os tipos que saíram passam a ser conferidos como ausentes. As funções privadas antigas só ficam se outro código as usar (`grep`); as que ninguém usa saem agora.

- [ ] **Step 4:** rodar `tests/test_avisos.py tests/test_paineis.py tests/test_api_paineis.py` → PASS.
- [ ] **Step 5: Commit** `feat: registro unico de avisos e resumo do mes`.

---

### Task 6.2: Medições em andamento, cabeçalho e dados da obra

**Files:**
- Modify: `backend/app/medicoes.py`, `backend/app/contratos.py`, `backend/app/notas.py`
- Test: `backend/tests/test_medicoes.py`, `backend/tests/test_contratos.py`, `backend/tests/test_notas.py` (um teste por função nova)

**Interfaces:**
- Produces:
  - `medicoes.em_andamento(conn, contrato_id: int | None = None, estado: str | None = None) -> list[dict]`. Cada linha tem `id`, `contrato_id`, `obra`, `numero`, `tipo`, `titulo`, `competencia`, `estado`, `valor_centavos`, `proximo_passo` e `desde`; `desde` é a data do último marco conhecido, ou a de criação.
  - `contratos.cabecalho(conn, contrato_id, hoje=None) -> dict`, com:
    - órgão e instrumento;
    - `valor_vigente_centavos`, `cota_vigente_centavos` e `percentual_lotufo_bp`;
    - `execucao_fim`, `dias_execucao`, `vigencia_fim` e `dias_vigencia`;
    - `status` (`ativo` | `suspenso` | `em_encerramento` | `encerrado` | `rescindido`).
  - `contratos.cadastro_da_obra(conn, contrato_id) -> dict`, com `datas_base`, `fiscais`, `aditivos` (os de valor e de prazo) e `instrumentos` (apostilamento de reajuste, paralisação, reinício, marcos, endosso), cada um com `dados` já decodificado.
  - `notas.do_contrato(conn, contrato_id) -> list[dict]`: uma linha por medição do contrato, com as saídas esperadas e a nota que atende cada uma (`notas.esperadas`), mais os documentos de nota anexados.

- [ ] **Step 1: Testes.**
  - `em_andamento` não lista medições recebidas nem canceladas; `proximo_passo` de `nota_emitida` é "protocolar"; o filtro por estado funciona.
  - `cabecalho` de contrato com `encerramento_iniciado_em` devolve `status == "em_encerramento"`, e `dias_execucao` é a diferença até `execucao_fim_vigente`.
  - `cadastro_da_obra` devolve o apostilamento de reajuste com `dados["percentual"]`.
  - `notas.do_contrato` devolve as medições com as saídas.
- [ ] **Step 2:** rodar → FAIL.
- [ ] **Step 3: Implementação.**
  - `em_andamento`: um SELECT com JOIN em `contratos` e `WHERE estado IN (...)`, mais filtros opcionais, ordenado por `nome_curto` e depois por número decrescente.
  - `titulo`: mover a função `titulo(m)` de `protocolo.py` (bloco 5) para `medicoes.py`, porque `protocolo` importa `medicoes` e o contrário daria import circular; `protocolo.titulo = medicoes.titulo` mantém o nome antigo.
  - O mapa fixo:

```python
PROXIMO_PASSO = {"espelho_gerado": "enviar ao faturamento", "espelho_enviado": "anexar as notas",
                 "nota_emitida": "protocolar", "protocolada": "aguardando pagamento",
                 "nf_emitida": "aguardando pagamento"}
```

  - `desde`: o máximo entre `espelho_em`, `nota_emitida_em` e a última data de `medicao_protocolos`.
  - `cabecalho`: usa `contratos.vigente` e `contratos.cota`; o nome do órgão vem da tabela `orgaos`; o status é `em_encerramento` quando `estado == 'ativo'` e há `encerramento_iniciado_em`.
  - `cadastro_da_obra`: SELECTs em `contrato_datas_base`, `contrato_fiscais`, `aditivos` (com `chave_cadastro`, `forma`, `tipo`, `data_assinatura`, `delta_valor_centavos`, `nova_execucao_fim`, `nova_vigencia_fim`, `status`) e `instrumentos` (com `json.loads(dados)`).
- [ ] **Step 4:** rodar → PASS. **Step 5: Commit** `feat: medicoes em andamento, cabecalho e cadastro da obra`.

---

### Task 6.3: Rotas

**Files:**
- Create: `backend/app/api_inicio.py`
- Modify: `backend/app/api_contratos.py`, `backend/app/main.py`
- Test: `backend/tests/test_api_inicio.py`

| Método e caminho | Permissão | Resposta |
|---|---|---|
| `GET /api/inicio` | `ver_paineis` | `{"avisos": avisos.listar(conn), "resumo": avisos.resumo_mes(conn)}` |
| `GET /api/medicoes/andamento?contrato_id=&estado=` | `ver_paineis` | `medicoes.em_andamento` |
| `GET /api/contratos/{id}/cabecalho` | `ver_paineis` | `contratos.cabecalho` |
| `GET /api/contratos/{id}/cadastro` | `ver_paineis` | `contratos.cadastro_da_obra` |
| `GET /api/contratos/{id}/notas` | `ver_paineis` | `notas.do_contrato` |

Diretoria recebe `GET /api/inicio` com `publico="diretoria"` (o perfil vem do usuário da sessão). Contrato inexistente dá 404.

- [ ] **Step 1: Testes.**
  - `/api/inicio` responde 200 com `avisos` e `resumo`.
  - `/api/medicoes/andamento?estado=nota_emitida` aplica o filtro.
  - `/api/contratos/999/cabecalho` responde 404.
- [ ] **Step 2:** FAIL. **Step 3:** implementar. **Step 4:** PASS. **Step 5: Commit** `feat: rotas da tela inicial, medicoes em andamento e dados da obra`.

---

### Task 6.4: Frontend (Início, Medições, página da obra, menu)

**Files:**
- Create: `frontend/src/Inicio.tsx`, `frontend/src/Inicio.test.tsx`, `frontend/src/MedicoesLista.tsx`, `frontend/src/ObraAbas.tsx`
- Modify: `frontend/src/Alertas.tsx`, `frontend/src/rota.tsx`, `frontend/src/rota.test.ts`, `frontend/src/App.tsx`, `frontend/src/ContratoPagina.tsx`

**Rotas** (`rota.tsx`):

```ts
export type AbaContrato = "medicoes" | "notas" | "documentos" | "reajuste" | "prazos" | "contrato";
// Telas simples: acrescentar "inicio" e "medicoes" a SIMPLES e ao tipo Rota.
// Links antigos: /contratos/7/protocolo -> medicoes; /contratos/7/cronograma e /aditivos -> contrato.
const ABA_ANTIGA: Record<string, AbaContrato> = { protocolo: "medicoes", cronograma: "contrato", aditivos: "contrato" };
```

`parseRota` resolve `ABA_ANTIGA[c]` antes de `ehAba(c)`. Em `rota.test.ts`:
- `/inicio` e `/medicoes` são telas;
- `/contratos/7/protocolo` vira `{tela: "contrato", id: 7, aba: "medicoes"}`;
- `caminhoDe` de cada aba nova volta ao caminho.

**Alertas.tsx**:
- Recebe `Aviso[]` no formato do índice.
- Cada linha mostra o selo do nível (`selo--acao` para crítico e ação, `selo--atencao` para atenção), a mensagem, o valor quando houver (`fmtBRL`) e um `Link` para o destino:
  - contrato: `{tela: "contrato", id, aba}`;
  - documentos: `{tela: "documentos"}`.
- Some o mapa local de tipo para rótulo: a mensagem vem pronta do servidor.

**Inicio.tsx**:
- Três KPIs (classes `kpis`/`kpi`):
  - "Medições protocoladas no mês", no formato `X de N obras ativas`;
  - "Valor protocolado no mês";
  - "Protocolado no mês anterior".
- Abaixo, o cartão "Avisos" com `<Alertas avisos=... />`.
- Sem avisos: "Nenhum aviso. Tudo em dia." (classe `vazio`).

**MedicoesLista.tsx**:
- Filtros de obra (select com as obras da lista) e de estado.
- Tabela com as colunas obra, medição, competência, estado, valor, próximo passo e desde.
- A linha abre `{tela: "contrato", id, aba: "medicoes"}`.

**ContratoPagina.tsx**:
- **Cabeçalho** (`GET /api/contratos/{id}/cabecalho`):
  - órgão · instrumento;
  - valor vigente e cota da Lotufo (percentual);
  - execução até DD/MM/AAAA (N dias);
  - vigência até DD/MM/AAAA (N dias);
  - selo do status.
- **Abas**: Medições, Notas, Documentos, Reajuste, Prazos, Contrato.
  - Medições: o que era medições e o protocolo (bloco 5), um abaixo do outro.
  - As outras cinco vêm de `ObraAbas.tsx`.

**ObraAbas.tsx**:
- `NotasObra`: por medição, as saídas esperadas com número e valor da nota e a situação da conferência, em tabela.
- `DocumentosObra`: dois quadros (medição e reajuste), montados de `GET /api/contratos/{id}/checklist?natureza=` (rota existente), com empresa × documento, situação e validade.
- `ReajusteObra`, versão deste bloco: datas-base (mês, índice) e apostilamentos de reajuste (número, data, percentual, eficácia).
- `PrazosObra`, versão deste bloco: aditivos e apostilamentos de prazo (número, data, nova execução, nova vigência), paralisações e reinícios, marcos de encerramento, fiscais com o histórico.
- `ContratoObra`: dados do cadastro, com `<Cronograma>` e `<Aditivos>` existentes em modo leitura (sem os formulários, que o bloco 9 remove do código).

**App.tsx**:
- Menu: Início, Medições, Obras, Documentos, Painel (`perfil` diretoria ou admin), Administração (admin).
- A raiz leva a `inicio`, ou a `painel` para a diretoria.
- Tiram-se do menu os itens Engenharia e Sugestões.

- [ ] **Step 1: Testes.**
  - `Inicio.test.tsx`: mostra "2 de 5 obras ativas" e o valor formatado; um aviso crítico aparece antes de um de atenção; o link do aviso aponta para `/contratos/7/prazos`.
  - `rota.test.ts`: os casos acima.
- [ ] **Step 2:** `npm test -- --run` → FAIL nos novos. **Step 3:** implementar. **Step 4:** PASS; `npm run build` limpo.
- [ ] **Step 5: Verificação visual** no `backend-review` sobre cópia da produção:
  - Início com os avisos reais: documentos da empresa, nota ausente do RM, execução vencendo;
  - lista de medições filtrada por "nota emitida";
  - página de uma obra SINFRA com as seis abas;
  - o link antigo `/contratos/<id>/protocolo`.

  Screenshot da tela inicial para o relatório.
- [ ] **Step 6: Commit** `feat: tela inicial, lista de medicoes e pagina da obra com as abas da spec`.

---

### Task 6.5: Documentação e suíte

- [ ] **Step 1:** runbook, seção "Tela inicial e avisos (bloco 6)":
  - o catálogo em vigor;
  - como um aviso some;
  - a regra do "X de N" e do valor do mês.

  Backlog: o fluxo "Certidão Alerta" do Power Automate continua ligado (decisão de 2026-09-24); os avisos da tela inicial não dependem dele.
- [ ] **Step 2:** suíte inteira do backend; depois `npm test -- --run` e `npm run build`.
- [ ] **Step 3: Commit** `docs: runbook e backlog do bloco 6`. Seguir para o bloco 7 (branch `bloco7-reajuste-prazos` a partir desta).

## Self-review

- Spec §10.1: avisos, "X de N" e valores do mês → 6.1 e 6.4. Não há sugestões nem pendências na tela (decisão 2).
- Spec §10.2: lista com filtro → 6.2 e 6.4.
- Spec §10.3: cabeçalho e as seis abas → 6.2 e 6.4. A linha do tempo da medição em painel lateral **não** entra: a aba Medições já mostra espelho, notas e protocolo por medição. Registrar no backlog como melhoria de tela, fora do escopo mínimo.
- Spec §11, parte deste bloco: 6.1. O resto do catálogo entra nos blocos 7 e 8.
- Nomes: `avisos.aviso(...)`, `avisos.obra(...)` e `avisos.ativos(...)` são usados pelos blocos 7 e 8 com essas assinaturas.
