# Bloco 7 (Reajuste e prazos): pleito de reajuste, carta de prazo, comunicação de conclusão, instrumentos, paralisação, encerramento. Plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. **Leia antes `00-indice.md` e as interfaces do bloco 5** (`carta`, `oficios`, `assinatura`, `pdfs`), que este bloco reusa. Branch `bloco7-reajuste-prazos`, criada de `bloco6-inicio`.

**Goal:**
- **Reajuste.** O sistema sabe, por data-base, quando é o aniversário e em que ponto está o ciclo: pleito não enviado, apostilamento pendente ou apostilado. Avisa a partir de 30 dias antes e deixa a operação mandar o pleito (ofício gerado, planilha de cálculo e cronograma anexados, assinatura por fora, envio).
- **Prazo.** Acompanha a execução (60 e 30 dias), a paralisação, a folga entre execução e vigência e o endosso do seguro-garantia. Deixa mandar a carta de prorrogação com o histórico do contrato montado a partir dos instrumentos.
- **Encerramento.** A medição final põe o contrato em encerramento e cobra a comunicação de conclusão.

**Architecture:**
- `app/reajuste.py` e `app/prazos.py` são puros sobre o banco: situação e avisos.
- `app/pleitos.py` faz o ciclo do ofício (criar, anexos, carta, montar, assinado, prévia, envio) com as peças do bloco 5.
- `avisos.FONTES` troca o prazo simples do bloco 6 pelos avisos de `prazos` e `reajuste`.
- `medicoes.marcar_final` liga medição e contrato.
- Os pleitos enviados antes do sistema entram pelo cadastro (`pleitos_anteriores`), para o aviso não acusar "não enviado" o que já foi.
- Migração 026.

**Tech Stack:** o do índice.

**Spec:** §2 (medição final), §5.2 (pleito, carta de prazo, conclusão), §7.2, §7.3, §7.4, §11 (execução vencendo, instrumento pendente, vigência vencendo, folga quebrada, endosso, reajuste nos dois estágios, obra paralisada, conclusão não comunicada), §12 (`pleitos`, `instrumentos`).

**Status:** APROVADO pelo Leonardo em 2026-09-24 (ver `00-indice.md`).

## Decisões deste bloco (para aprovação)

1. **Pleito é o mesmo caminho do protocolo**, com um documento só: ofício gerado → anexos arrastados → baixar → assinar no DocuSign → arrastar o assinado (mesma conferência do bloco 5) → prévia → enviar. Tipos: `reajuste`, `prazo` e `conclusao`. **Destinatários**: `protocolo_para` do órgão, mais o fiscal vigente e os `destinatarios_extras` do contrato. **Cópias**: `protocolo_copia` (spec §5.2).
2. **O instrumento que atende o pleito é calculado, não gravado.**
   - Reajuste: um `apostilamento_reajuste` com `data_base` e `ciclo` iguais. Sem `data_base`, vale a única data-base do contrato. Sem `ciclo`, vale o ano da `eficacia`, ou da `data`.
   - Prazo: qualquer instrumento de prazo assinado em data igual ou posterior à do envio.
   - Conclusão: o próprio envio fecha o aviso.
3. **Ciclo do reajuste.**
   - O ciclo corrente é o maior ano Y em que "1º dia do mês de aniversário de Y, menos 30 dias" já chegou.
   - **Pleito não enviado**: aparece daí até o envio. O nível é `atencao` antes do aniversário e `acao` depois.
   - **Apostilamento pendente**: aparece do envio até o apostilamento; entra no painel da diretoria depois de 90 dias.
   - Só o ciclo corrente conta. Ciclo antigo sem apostilamento não gera aviso (os levantamentos de 17/09 mostram os ciclos anteriores resolvidos ou já em discussão fora do sistema).
   - `sem_reajuste: true` desliga tudo.
4. **Pleitos enviados antes do sistema** entram pelo YAML do contrato:

   ```yaml
   pleitos_anteriores:
     - {tipo: reajuste, data_base: 2023-03, ciclo: 2026, oficio: CT-122-LT-2026, data: 2026-04-23}
     - {tipo: prazo, oficio: CT-331-LT-2025, data: 2025-11-10, dias: 120}
   ```

   Vão para `pleitos` com `origem='cadastro'`, `situacao='enviado'` e sem envio. A tarefa 7.6 preenche esses pleitos a partir de `docs/reajuste-pleitos-2026-09-17.md` e `docs/prazos-vigencia-execucao-2026-09-17.md`.
5. **Prazo.**
   - O relógio é a execução vigente (`contratos.vigente`).
   - **Paralisação aberta**, isto é, a última `paralisacao` sem `reinicio` depois, suspende o aviso de execução. Vira aviso "obra paralisada" para a diretoria.
   - **Folga**: é quebrada quando `vigência − execução` fica menor que a folga do órgão, ou que a do contrato (`folga_vigencia_dias` no YAML do contrato, que vence a do órgão; na MTPAR varia por contrato).
   - **Instrumento retroativo** é o assinado depois do fim da execução que ele prorroga. É sinalizado na aba Prazos e nunca recusado.
   - **Endosso do seguro-garantia**: aviso para instrumento de prazo assinado **nos últimos 60 dias** sem `endosso_garantia` que o referencie (`referente: <chave>`) ou com data posterior. É `atencao` até 5 dias e `acao` depois. Instrumento mais antigo que 60 dias sem registro de endosso não gera aviso (a carga não traz o histórico de endossos).
6. **Carta de prazo.**
   - A seção "1. HISTÓRICO DO CONTRATO" sai pronta, com um parágrafo por instrumento de prazo, em ordem, e o ordinal contado por forma (termo aditivo × termo de apostilamento).
   - A seção "2. DO PEDIDO" leva a justificativa digitada e os dias pedidos, com o novo fim calculado.
   - Justificativa que fala em chuva sem paralisação cadastrada vira pendência ("o contrato veda alegar só chuva; cite a ordem de paralisação do órgão"), e não bloqueio.
7. **Medição final** (operação): grava `medicoes.final`/`final_em` e põe `contratos.encerramento_iniciado_em` (se ainda nulo), com auditoria nos dois.
   - **Desmarcar** exige motivo. Limpa o encerramento só se nenhuma outra medição do contrato for final.
   - `cadastro aplicar` **preserva** o encerramento quando o contrato tem medição final, mesmo com o YAML em `ativo`, e lista a divergência no relatório ("atualize o YAML para em_encerramento").
   - Em encerramento: os avisos de prazo param. Entra "conclusão não comunicada" (`acao`, dias desde a medição final) até a carta de conclusão sair.
   - Os marcos de recebimento provisório, definitivo e baixa da garantia vêm do cadastro (`marco_encerramento` com `marco:`) e aparecem na aba Prazos.

## Estrutura de arquivos

| Arquivo | Responsabilidade |
|---|---|
| `backend/migrations/026_pleitos.sql` | `pleitos`, `pleito_anexos`, `medicoes.final/final_em`, `contratos.folga_vigencia_dias` |
| `backend/app/reajuste.py` | ciclos por data-base, avisos de reajuste |
| `backend/app/prazos.py` | situação do prazo, histórico em texto, avisos de prazo, encerramento e paralisação |
| `backend/app/pleitos.py` | ciclo do ofício de reajuste, prazo e conclusão |
| `backend/app/oficios.py` | `usos` também em `pleitos` |
| `backend/app/avisos.py` | `FONTES` com `prazos.avisos` e `reajuste.avisos` no lugar de `_de_contrato` |
| `backend/app/medicoes.py` | `marcar_final`, `desmarcar_final` |
| `backend/app/cadastro_arquivos.py`, `cadastro_aplicar.py` | `pleitos_anteriores`, `folga_vigencia_dias` do contrato, `marco`/`referente`/`data_base`/`ciclo`/`percentual`/`eficacia` validados nos instrumentos, encerramento preservado |
| `backend/app/api_pleitos.py`, `api_medicoes.py`, `main.py` | rotas |
| `cadastro/cartas.yaml` | textos `pleito_reajuste`, `prazo`, `conclusao` |
| `frontend/src/FluxoOficio.tsx`, `Reajuste.tsx`, `Prazos.tsx` (+ testes), `ObraAbas.tsx`, `Medicoes.tsx` | telas |

---

### Task 7.1: Migração 026

**Files:**
- Create: `backend/migrations/026_pleitos.sql`
- Test: `backend/tests/test_migracao_026.py`

- [ ] **Step 1: Teste**, no padrão do `test_migracao_025.py`: as tabelas `pleitos` e `pleito_anexos` existem com as colunas abaixo; `medicoes.final` tem padrão 0; `contratos.folga_vigencia_dias` existe; reexecutar não falha.
- [ ] **Step 2:** FAIL. **Step 3: Migração**

```sql
-- 026: pleitos (reajuste, prazo, conclusao), medicao final, folga por contrato (bloco 7; spec §5.2, §7.2 a §7.4).
CREATE TABLE IF NOT EXISTS pleitos (
    id INTEGER PRIMARY KEY,
    contrato_id INTEGER NOT NULL REFERENCES contratos(id),
    tipo TEXT NOT NULL CHECK (tipo IN ('reajuste','prazo','conclusao')),
    origem TEXT NOT NULL DEFAULT 'sistema' CHECK (origem IN ('sistema','cadastro')),
    data_base_mes TEXT,
    ciclo INTEGER,
    dias INTEGER CHECK (dias IS NULL OR dias > 0),
    justificativa TEXT,
    numero_oficio TEXT,
    corpo_carta TEXT,
    montado_arquivo TEXT,
    montado_sha256 TEXT,
    montado_paginas INTEGER,
    assinado_arquivo TEXT,
    assinado_sha256 TEXT,
    conferencia TEXT,
    envio_id INTEGER REFERENCES envios(id),
    envio_justificativa TEXT,
    enviado_em TEXT,
    situacao TEXT NOT NULL DEFAULT 'rascunho'
        CHECK (situacao IN ('rascunho','montado','assinado','enviado','descartado')),
    usuario_id INTEGER REFERENCES usuarios(id),
    criado_em TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS pleitos_contrato ON pleitos(contrato_id, tipo);
CREATE UNIQUE INDEX IF NOT EXISTS pleitos_cadastro
    ON pleitos(contrato_id, tipo, numero_oficio) WHERE origem = 'cadastro';

CREATE TABLE IF NOT EXISTS pleito_anexos (
    id INTEGER PRIMARY KEY,
    pleito_id INTEGER NOT NULL REFERENCES pleitos(id),
    tipo TEXT NOT NULL CHECK (tipo IN ('planilha_calculo','cronograma','outro')),
    nome TEXT NOT NULL,
    arquivo TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    tamanho INTEGER NOT NULL,
    ext TEXT NOT NULL CHECK (ext IN ('pdf','xlsx')),
    removido_em TEXT,
    criado_em TEXT NOT NULL DEFAULT (datetime('now'))
);

ALTER TABLE medicoes ADD COLUMN final INTEGER NOT NULL DEFAULT 0;
ALTER TABLE medicoes ADD COLUMN final_em TEXT;
ALTER TABLE contratos ADD COLUMN folga_vigencia_dias INTEGER;
```

- [ ] **Step 4:** PASS. **Step 5: Commit** `feat: migracao 026 dos pleitos e da medicao final`.

---

### Task 7.2: Cadastro (pleitos anteriores, folga do contrato, campos dos instrumentos, encerramento preservado)

**Files:**
- Modify: `backend/app/cadastro_arquivos.py`, `backend/app/cadastro_aplicar.py`
- Test: `backend/tests/test_cadastro_arquivos.py`, `backend/tests/test_cadastro_aplicar.py`

**Interfaces:** o contrato aceita `folga_vigencia_dias` (inteiro ≥ 0) e `pleitos_anteriores`. Cada pleito anterior tem:
- `tipo` em `reajuste`, `prazo` ou `conclusao`;
- `oficio`, normalizado por `oficios.canonico` com a sigla da entidade;
- `data`;
- `data_base` e `ciclo`, obrigatórios no reajuste;
- `dias`, opcional no prazo.

Os instrumentos validam os campos de `dados` que os blocos 7 e 8 leem:
- `apostilamento_reajuste`: `data_base` no formato AAAA-MM e presente nas datas-base; `ciclo` inteiro; `percentual` e `eficacia` opcionais;
- `endosso_garantia`: `referente`, que precisa ser a chave de um instrumento de prazo do mesmo contrato;
- `marco_encerramento`: `marco` em `conclusao`, `provisorio`, `definitivo` ou `baixa_garantia`;
- `paralisacao` e `reinicio`: só a data.

- [ ] **Step 1: Testes.**
  - Em `test_cadastro_arquivos`:
    - `marco: outro` → erro;
    - `referente` apontando para chave inexistente → erro;
    - `pleitos_anteriores` de reajuste sem `ciclo` → erro;
    - `folga_vigencia_dias: -1` → erro.
  - Em `test_cadastro_aplicar`:
    - aplicar cria os `pleitos` de origem `cadastro` (situação `enviado`, `enviado_em` = `data`);
    - reaplicar não duplica;
    - com medição `final=1` no banco e o YAML em `ativo`, o `encerramento_iniciado_em` continua e o relatório traz o aviso `medição final marcada; atualize o YAML`.
- [ ] **Step 2:** FAIL. **Step 3: Implementar.**
  - Em `_contrato` do `cadastro_aplicar`, trocar o cálculo de `enc` por:

```python
    tem_final = ja is not None and conn.execute(
        "SELECT 1 FROM medicoes WHERE contrato_id=? AND final=1 LIMIT 1", (ja["id"],)).fetchone() is not None
    if c["status"] == "em_encerramento":
        enc = c["status_desde"]
    elif ja is not None and (c["status"] == "encerrado" or tem_final):
        enc = ja["encerramento_iniciado_em"]
        if tem_final and c["status"] == "ativo":
            rel["avisos"].append(f"{c['nome_curto']}: medição final marcada na operação; atualize o YAML "
                                 f"para status em_encerramento")
    else:
        enc = None
```

  (Se `rel` não tiver a chave `avisos`, acrescentar em `_rel()` e mostrar no relatório do CLI.)
  - `folga_vigencia_dias` entra em `_CAMPOS_CONTRATO`.
  - `_pleitos_anteriores(conn, usuario_id, contrato_id, lista, rel)` faz `INSERT OR IGNORE` por `(contrato_id, tipo, numero_oficio)` com `origem='cadastro'`, com auditoria `cadastro.pleito`.
- [ ] **Step 4:** PASS. **Step 5: Commit** `feat: cadastro dos pleitos anteriores, folga por contrato e campos dos instrumentos`.

---

### Task 7.3: Reajuste (`reajuste.py`)

**Files:**
- Create: `backend/app/reajuste.py`
- Test: `backend/tests/test_reajuste.py`

**Interfaces:**
- Produces:
  - `aniversario(mes_base: str, ano: int) -> date`;
  - `ciclos(conn, contrato_id, hoje=None) -> list[dict]`. Cada linha traz `data_base_mes`, `indice`, `ciclo`, `aniversario` (ISO) e `situacao` (`futuro` | `pleito_pendente` | `apostilamento_pendente` | `apostilado`), além de `dias`, `pleito` e `apostilamento`, que podem vir nulos.
    - Em `pleito_pendente`, `dias` = dias até o aniversário (negativo depois dele).
    - Em `apostilamento_pendente`, `dias` = dias desde o envio.
  - `avisos(conn, hoje=None) -> list[dict]`.

- [ ] **Step 1: Testes**

```python
"""Ciclo do reajuste por data-base (spec §7.2)."""
import datetime

from app import reajuste

D = datetime.date


def test_ciclo_corrente_e_janela_de_30_dias(cenario):
    c, ids = cenario                      # contrato com data-base 2024-06 (INCC-DI), sem pleito
    assert reajuste.ciclos(c, ids["contrato"], D(2026, 4, 30))[0]["ciclo"] == 2025  # jun/2026 - 30 dias ainda nao
    r = reajuste.ciclos(c, ids["contrato"], D(2026, 5, 2))[0]
    assert (r["ciclo"], r["situacao"], r["dias"]) == (2026, "pleito_pendente", 30)


def test_pleito_enviado_vira_apostilamento_pendente_e_apostilamento_fecha(cenario):
    c, ids = cenario
    ids["pleito"](data_base="2024-06", ciclo=2026, enviado_em="2026-06-10")
    r = reajuste.ciclos(c, ids["contrato"], D(2026, 9, 10))[0]
    assert (r["situacao"], r["dias"]) == ("apostilamento_pendente", 92)
    ids["instrumento"]("apostilamento_reajuste", "2026-09-15", {"data_base": "2024-06", "ciclo": 2026, "percentual": "6,76"})
    assert reajuste.ciclos(c, ids["contrato"], D(2026, 9, 20))[0]["situacao"] == "apostilado"


def test_avisos_niveis_e_diretoria_depois_de_90_dias(cenario):
    c, ids = cenario
    a = {x["tipo"]: x for x in reajuste.avisos(c, D(2026, 6, 15))}
    assert a["reajuste_pleito"]["nivel"] == "acao"          # aniversario ja passou
    ids["pleito"](data_base="2024-06", ciclo=2026, enviado_em="2026-06-10")
    a = {x["tipo"]: x for x in reajuste.avisos(c, D(2026, 9, 10))}
    assert "diretoria" in a["reajuste_apostilamento"]["publico"]
    a = {x["tipo"]: x for x in reajuste.avisos(c, D(2026, 7, 10))}
    assert a["reajuste_apostilamento"]["publico"] == ["operacao"]


def test_sem_reajuste_desliga(cenario):
    c, ids = cenario
    c.execute("UPDATE contratos SET sem_reajuste=1 WHERE id=?", (ids["contrato"],)); c.commit()
    assert reajuste.ciclos(c, ids["contrato"], D(2026, 6, 15)) == []
```

A fixture `cenario` cria o contrato com uma data-base e oferece os helpers `ids["pleito"](...)`, que insere um pleito de reajuste enviado, e `ids["instrumento"](tipo, data, dados)`, que insere em `instrumentos`.

- [ ] **Step 2:** FAIL. **Step 3: Implementação**

```python
"""Ciclo do reajuste por data-base (spec 2026-09-21 §7.2), bloco 7.

O sistema nao calcula indice nem valor. Sabe so' o calendario: o reajuste vale a partir do MES do
aniversario (OT 028/2015/CGE item 3.2.1; clausula 11.45 SINFRA); o aviso comeca 30 dias antes do 1o dia
desse mes; o ciclo fecha com o APOSTILAMENTO, nao com o oficio (reenviado a cada aditivo).
"""
import datetime
import json

from app import avisos as _av, tempo

JANELA_DIAS, DIRETORIA_DIAS = 30, 90


def aniversario(mes_base: str, ano: int) -> datetime.date:
    return datetime.date(ano, int(mes_base[5:7]), 1)


def _ciclo_corrente(mes_base: str, hoje: datetime.date) -> int | None:
    base = int(mes_base[:4])
    anos = [y for y in range(base + 1, hoje.year + 2)
            if aniversario(mes_base, y) - datetime.timedelta(days=JANELA_DIAS) <= hoje]
    return max(anos) if anos else None


def _apostilamento(conn, contrato_id: int, mes_base: str, ciclo: int, unica: bool) -> dict | None:
    for r in conn.execute("SELECT * FROM instrumentos WHERE contrato_id=? AND tipo='apostilamento_reajuste' "
                          "ORDER BY data DESC, id DESC", (contrato_id,)):
        d = json.loads(r["dados"] or "{}")
        base = d.get("data_base") or (mes_base if unica else None)
        ano = d.get("ciclo") or int(str(d.get("eficacia") or r["data"])[:4])
        if base == mes_base and int(ano) == ciclo:
            return {**dict(r), "dados": d}
    return None


def _pleito(conn, contrato_id: int, mes_base: str, ciclo: int) -> dict | None:
    r = conn.execute("SELECT * FROM pleitos WHERE contrato_id=? AND tipo='reajuste' AND data_base_mes=? AND ciclo=? "
                     "AND situacao='enviado' ORDER BY enviado_em DESC, id DESC LIMIT 1",
                     (contrato_id, mes_base, ciclo)).fetchone()
    return dict(r) if r else None


def ciclos(conn, contrato_id: int, hoje: datetime.date | None = None) -> list[dict]:
    hoje = hoje or tempo.hoje_local()
    c = conn.execute("SELECT sem_reajuste FROM contratos WHERE id=?", (contrato_id,)).fetchone()
    if c is None or c["sem_reajuste"]:
        return []
    bases = [dict(r) for r in conn.execute("SELECT mes, indice FROM contrato_datas_base WHERE contrato_id=? "
                                           "ORDER BY mes", (contrato_id,))]
    out = []
    for b in bases:
        y = _ciclo_corrente(b["mes"], hoje)
        if y is None:
            y = int(b["mes"][:4]) + 1
            out.append({"data_base_mes": b["mes"], "indice": b["indice"], "ciclo": y,
                        "aniversario": aniversario(b["mes"], y).isoformat(), "situacao": "futuro",
                        "dias": (aniversario(b["mes"], y) - hoje).days, "pleito": None, "apostilamento": None})
            continue
        aniv = aniversario(b["mes"], y)
        ap = _apostilamento(conn, contrato_id, b["mes"], y, len(bases) == 1)
        pl = _pleito(conn, contrato_id, b["mes"], y)
        if ap:
            sit, dias = "apostilado", None
        elif pl:
            sit, dias = "apostilamento_pendente", (hoje - datetime.date.fromisoformat(pl["enviado_em"][:10])).days
        else:
            sit, dias = "pleito_pendente", (aniv - hoje).days
        out.append({"data_base_mes": b["mes"], "indice": b["indice"], "ciclo": y, "aniversario": aniv.isoformat(),
                    "situacao": sit, "dias": dias, "pleito": pl, "apostilamento": ap})
    return out


def avisos(conn, hoje: datetime.date | None = None) -> list[dict]:
    hoje = hoje or tempo.hoje_local()
    out = []
    for c in conn.execute("SELECT id, nome_curto, numero FROM contratos WHERE estado IN ('ativo','suspenso')"):
        nome = c["nome_curto"] or c["numero"]
        for k in ciclos(conn, c["id"], hoje):
            base = f"{k['data_base_mes'][5:7]}/{k['data_base_mes'][:4]}"
            aniv = datetime.date.fromisoformat(k["aniversario"])
            destino = {"tela": "contrato", "id": c["id"], "aba": "reajuste"}
            if k["situacao"] == "pleito_pendente":
                quando = (f"faz aniversário em {aniv:%d/%m/%Y} (em {k['dias']} dias)" if k["dias"] >= 0
                          else f"fez aniversário em {aniv:%d/%m/%Y} (há {-k['dias']} dias)")
                out.append(_av.aviso("reajuste_pleito", "atencao" if k["dias"] >= 0 else "acao",
                                     f"{nome}: data-base {base} {quando}; pleito de reajuste não enviado",
                                     c["id"], nome, dias=k["dias"], destino=destino))
            elif k["situacao"] == "apostilamento_pendente":
                publico = ("operacao", "diretoria") if k["dias"] > DIRETORIA_DIAS else ("operacao",)
                out.append(_av.aviso("reajuste_apostilamento", "atencao",
                                     f"{nome}: pleito da data-base {base} enviado há {k['dias']} dias; "
                                     f"apostilamento pendente", c["id"], nome, dias=k["dias"],
                                     publico=publico, destino=destino))
    return out
```

(`avisos` importa `app.avisos` com alias para não sombrear a função local. Se o import circular aparecer, porque `avisos.FONTES` importa `reajuste`, mover `aviso()` e `obra()` para `app/avisos_formato.py` e importar dos dois lados.)

- [ ] **Step 4:** PASS. **Step 5: Commit** `feat: ciclo do reajuste e avisos de pleito e apostilamento`.

---

### Task 7.4: Prazos (`prazos.py`)

**Files:**
- Create: `backend/app/prazos.py`
- Test: `backend/tests/test_prazos.py`

**Interfaces:**
- Produces: `situacao(conn, contrato_id, hoje=None) -> dict` com:
  - `execucao_fim`, `dias_execucao`, `vigencia_fim` e `dias_vigencia`;
  - `folga`: `{"exigida", "real", "quebrada"}`;
  - `paralisacao`: `{"desde", "numero"}` ou `None`;
  - `pedido`: pleito de prazo enviado e não atendido, ou `None`;
  - `instrumentos`: cada um com `retroativo: bool`;
  - `endosso`: `{"instrumento", "assinado_em", "dias", "entregue"}` ou `None`;
  - `encerramento`: `{"desde", "marcos": {marco: data}, "conclusao_comunicada": bool}` ou `None`.

  Também produz `historico_texto(conn, contrato_id) -> str` e `avisos(conn, hoje=None) -> list[dict]`.

- [ ] **Step 1: Testes** (um por regra)

```python
def test_execucao_60_30_e_vencida_sem_pedido_vai_para_a_diretoria(cenario): ...
    # execucao_fim 2026-10-20: 01/09 -> execucao_vencendo atencao; 01/10 -> critico;
    # 25/10 -> instrumento_pendente critico com publico operacao+diretoria e mensagem "sem pedido"
def test_pedido_enviado_troca_o_aviso_e_instrumento_posterior_fecha(cenario): ...
    # pleito prazo enviado 2026-09-05 -> instrumento_pendente atencao "pedida em 05/09";
    # aditivo prazo assinado 2026-09-20 (nova execucao 2027-01-20) -> nenhum aviso de prazo
def test_paralisacao_aberta_suspende_o_aviso_e_avisa_a_diretoria(cenario): ...
    # instrumento paralisacao 2026-02-01 sem reinicio -> sem execucao_vencendo; obra_paralisada publico ["diretoria"];
    # reinicio 2026-05-05 -> volta o aviso normal
def test_folga_quebrada_pelo_contrato_e_pelo_orgao(cenario): ...
    # orgao folga 90; execucao 2026-12-01, vigencia 2027-01-15 (45 dias) -> folga_quebrada acao;
    # contrato folga_vigencia_dias 30 -> sem aviso
def test_vigencia_so_sem_prorrogacao_automatica(cenario): ...
def test_endosso_ate_5_dias_atencao_depois_acao_e_endosso_fecha(cenario): ...
def test_endosso_nao_cobra_instrumento_antigo(cenario): ...   # assinado ha 90 dias, sem endosso -> sem aviso
def test_retroativo_sinalizado(cenario): ...                  # assinado 2026-03-10 prorrogando execucao que acabou 2026-02-28
def test_em_encerramento_so_conclusao_nao_comunicada(cenario): ...
    # encerramento_iniciado_em 2026-09-01, hoje 2026-09-15 -> so' conclusao_nao_comunicada (acao, 14 dias);
    # pleito conclusao enviado -> nenhum aviso
def test_historico_texto_ordinal_por_forma(cenario): ...
    # 1o TA (termo_aditivo) e 1o apostilamento: "O 1º termo aditivo n.º 001/2025 foi assinado em 10/03/2025, com término
    # da execução em 20/10/2025 e da vigência em 18/01/2026." e "O 1º termo de apostilamento n.º ..."
```

Escrever cada teste por inteiro no padrão dos esboços acima: a fixture cria contrato, órgão e as linhas em `aditivos`, `instrumentos` e `pleitos`, e cada teste afirma o tipo, o nível, o público e o trecho da mensagem.

- [ ] **Step 2:** FAIL. **Step 3: Implementação**

```python
"""Prazo do contrato (spec 2026-09-21 §7.3 e §7.4), bloco 7.

O relogio e' a EXECUCAO. Vigencia so' conta onde o orgao nao prorroga sozinho. Paralisacao aberta
suspende o relogio. Instrumento retroativo e' sinalizado, nunca recusado. Em encerramento os avisos de
prazo param e fica so' a comunicacao de conclusao.
"""
import datetime
import json

from app import avisos as _av, contratos, tempo

DIAS_EXECUCAO, DIAS_CRITICO, DIAS_VIGENCIA = 60, 30, 60
ENDOSSO_PRAZO, ENDOSSO_JANELA = 5, 60
ORDINAL = {1: "1º", 2: "2º", 3: "3º", 4: "4º", 5: "5º", 6: "6º", 7: "7º", 8: "8º", 9: "9º", 10: "10º"}


def _d(s: str | None) -> datetime.date | None:
    return datetime.date.fromisoformat(s[:10]) if s else None


def _br(s: str | None) -> str:
    return f"{s[8:10]}/{s[5:7]}/{s[:4]}" if s else ""


def _instrumentos_prazo(conn, contrato_id: int) -> list[dict]:
    c = conn.execute("SELECT execucao_fim FROM contratos WHERE id=?", (contrato_id,)).fetchone()
    exe_ant = c["execucao_fim"] if c else None
    out = []
    for a in conn.execute("SELECT * FROM aditivos WHERE contrato_id=? AND status='assinado' "
                          "AND (nova_execucao_fim IS NOT NULL OR nova_vigencia_fim IS NOT NULL) "
                          "ORDER BY data_assinatura, id", (contrato_id,)):
        a = dict(a)
        a["retroativo"] = bool(exe_ant and a["data_assinatura"] and a["data_assinatura"] > exe_ant)
        a["execucao_anterior"] = exe_ant
        exe_ant = a["nova_execucao_fim"] or exe_ant
        out.append(a)
    return out


def _outros(conn, contrato_id: int, tipo: str) -> list[dict]:
    return [{**dict(r), "dados": json.loads(r["dados"] or "{}")} for r in conn.execute(
        "SELECT * FROM instrumentos WHERE contrato_id=? AND tipo=? ORDER BY data, id", (contrato_id, tipo))]


def _paralisacao(conn, contrato_id: int) -> dict | None:
    eventos = sorted(_outros(conn, contrato_id, "paralisacao") + _outros(conn, contrato_id, "reinicio"),
                     key=lambda x: (x["data"], x["id"]))
    if eventos and eventos[-1]["tipo"] == "paralisacao":
        return {"desde": eventos[-1]["data"], "numero": eventos[-1]["numero"]}
    return None


def _regras(conn, c: dict) -> dict:
    if not c.get("orgao_id"):
        return {}
    r = conn.execute("SELECT regras FROM orgaos WHERE id=?", (c["orgao_id"],)).fetchone()
    return json.loads(r["regras"]) if r else {}


def _pleito(conn, contrato_id: int, tipo: str) -> dict | None:
    r = conn.execute("SELECT * FROM pleitos WHERE contrato_id=? AND tipo=? AND situacao='enviado' "
                     "ORDER BY enviado_em DESC, id DESC LIMIT 1", (contrato_id, tipo)).fetchone()
    return dict(r) if r else None


def situacao(conn, contrato_id: int, hoje: datetime.date | None = None) -> dict:
    hoje = hoje or tempo.hoje_local()
    v = contratos.vigente(conn, contrato_id)
    regras = _regras(conn, v)
    insts = _instrumentos_prazo(conn, contrato_id)
    pedido = _pleito(conn, contrato_id, "prazo")
    if pedido and any((a["data_assinatura"] or "") >= pedido["enviado_em"][:10] for a in insts):
        pedido = None
    exe, vig = v.get("execucao_fim_vigente"), v.get("vigencia_fim_vigente")
    exigida = v.get("folga_vigencia_dias") if v.get("folga_vigencia_dias") is not None \
        else regras.get("folga_vigencia_dias")
    real = (_d(vig) - _d(exe)).days if exe and vig else None
    endosso = None
    if insts:
        ult = insts[-1]
        endossos = _outros(conn, contrato_id, "endosso_garantia")
        entregue = any(e["dados"].get("referente") == ult.get("chave_cadastro") or
                       e["data"] >= (ult["data_assinatura"] or "") for e in endossos)
        dias = (hoje - _d(ult["data_assinatura"])).days if ult["data_assinatura"] else None
        endosso = {"instrumento": ult.get("numero") or ult.get("chave_cadastro"), "chave": ult.get("chave_cadastro"),
                   "assinado_em": ult["data_assinatura"], "dias": dias, "entregue": entregue}
    enc = None
    if v.get("encerramento_iniciado_em"):
        marcos = {m["dados"].get("marco"): m["data"] for m in _outros(conn, contrato_id, "marco_encerramento")}
        enc = {"desde": v["encerramento_iniciado_em"], "marcos": marcos,
               "conclusao_comunicada": _pleito(conn, contrato_id, "conclusao") is not None}
    return {"execucao_fim": exe, "dias_execucao": (_d(exe) - hoje).days if exe else None,
            "vigencia_fim": vig, "dias_vigencia": (_d(vig) - hoje).days if vig else None,
            "vigencia_automatica": bool(regras.get("vigencia_automatica")),
            "folga": {"exigida": exigida, "real": real,
                      "quebrada": exigida is not None and real is not None and real < exigida},
            "paralisacao": _paralisacao(conn, contrato_id), "pedido": pedido, "instrumentos": insts,
            "endosso": endosso, "encerramento": enc}


def historico_texto(conn, contrato_id: int) -> str:
    c = conn.execute("SELECT * FROM contratos WHERE id=?", (contrato_id,)).fetchone()
    linhas = [f"O Contrato n.º {c['numero_instrumento'] or c['numero']} tem execução original até "
              f"{_br(c['execucao_fim'])} e vigência original até {_br(c['vigencia_fim'])}."]
    conta = {"termo_aditivo": 0, "apostilamento": 0}
    for a in _instrumentos_prazo(conn, contrato_id):
        forma = a.get("forma") or "termo_aditivo"
        conta[forma] = conta.get(forma, 0) + 1
        nome = "termo aditivo" if forma == "termo_aditivo" else "termo de apostilamento"
        partes = []
        if a["nova_execucao_fim"]:
            partes.append(f"término da execução em {_br(a['nova_execucao_fim'])}")
        if a["nova_vigencia_fim"]:
            partes.append(f"da vigência em {_br(a['nova_vigencia_fim'])}")
        linhas.append(f"O {ORDINAL.get(conta[forma], str(conta[forma]) + 'º')} {nome} n.º {a['numero'] or 's/n'} foi "
                      f"assinado em {_br(a['data_assinatura'])}, com {' e '.join(partes)}.")
    return "\n\n".join(linhas)


def avisos(conn, hoje: datetime.date | None = None) -> list[dict]:
    hoje = hoje or tempo.hoje_local()
    out = []
    for c in conn.execute("SELECT id, nome_curto, numero FROM contratos WHERE estado='ativo'"):
        nome, cid = c["nome_curto"] or c["numero"], c["id"]
        s = situacao(conn, cid, hoje)
        destino = {"tela": "contrato", "id": cid, "aba": "prazos"}
        if s["encerramento"]:
            if not s["encerramento"]["conclusao_comunicada"]:
                dias = (hoje - _d(s["encerramento"]["desde"])).days
                out.append(_av.aviso("conclusao_nao_comunicada", "acao",
                                     f"{nome}: medição final há {dias} dias; conclusão não comunicada",
                                     cid, nome, dias=dias, destino=destino))
            continue
        if s["paralisacao"]:
            out.append(_av.aviso("obra_paralisada", "atencao",
                                 f"{nome}: paralisada desde {_br(s['paralisacao']['desde'])}", cid, nome,
                                 publico=("diretoria",), destino=destino))
        else:
            dias = s["dias_execucao"]
            if s["pedido"]:
                desde = (hoje - _d(s["pedido"]["enviado_em"])).days
                vencida = dias is not None and dias < 0
                msg = (f"{nome}: prorrogação pedida em {_br(s['pedido']['enviado_em'])} "
                       f"({s['pedido']['numero_oficio']}); instrumento pendente há {desde} dias")
                if vencida:
                    msg += f"; execução vencida há {-dias} dias"
                out.append(_av.aviso("instrumento_pendente", "critico" if vencida else "atencao", msg, cid, nome,
                                     dias=dias, publico=("operacao", "diretoria") if vencida else ("operacao",),
                                     destino=destino))
            elif dias is not None and dias < 0:
                out.append(_av.aviso("instrumento_pendente", "critico",
                                     f"{nome}: execução vencida há {-dias} dias, sem pedido de prorrogação",
                                     cid, nome, dias=dias, publico=("operacao", "diretoria"), destino=destino))
            elif dias is not None and dias <= DIAS_EXECUCAO:
                out.append(_av.aviso("execucao_vencendo", "critico" if dias <= DIAS_CRITICO else "atencao",
                                     f"{nome}: execução termina em {dias} dias ({_br(s['execucao_fim'])})",
                                     cid, nome, dias=dias, destino=destino))
        if not s["vigencia_automatica"] and s["dias_vigencia"] is not None and s["dias_vigencia"] <= DIAS_VIGENCIA:
            out.append(_av.aviso("vigencia_vencendo", "critico" if s["dias_vigencia"] <= DIAS_CRITICO else "atencao",
                                 f"{nome}: vigência termina em {s['dias_vigencia']} dias ({_br(s['vigencia_fim'])})",
                                 cid, nome, dias=s["dias_vigencia"], destino=destino))
        if s["folga"]["quebrada"]:
            out.append(_av.aviso("folga_quebrada", "acao",
                                 f"{nome}: execução até {_br(s['execucao_fim'])} e vigência até {_br(s['vigencia_fim'])}: "
                                 f"folga de {s['folga']['real']} dias, o órgão pede {s['folga']['exigida']}",
                                 cid, nome, destino=destino))
        e = s["endosso"]
        if e and not e["entregue"] and e["dias"] is not None and e["dias"] <= ENDOSSO_JANELA:
            falta = ENDOSSO_PRAZO - e["dias"]
            quando = f"vence em {falta} dias" if falta >= 0 else f"atrasado {-falta} dias"
            out.append(_av.aviso("endosso_garantia", "atencao" if falta >= 0 else "acao",
                                 f"{nome}: endosso do seguro-garantia do {e['instrumento']} "
                                 f"(assinado em {_br(e['assinado_em'])}) {quando}", cid, nome, dias=falta,
                                 destino=destino))
    return out
```

- [ ] **Step 4:** PASS. **Step 5: `avisos.FONTES`**: trocar `_de_contrato` por `prazos.avisos` e `reajuste.avisos` e apagar `_de_contrato`. Os testes do bloco 6 sobre execução e vigência são reescritos contra `prazos` (mesmo comportamento na parte que coincide). **Step 6: Commit** `feat: prazos (execucao, vigencia, folga, paralisacao, endosso, encerramento) no registro de avisos`.

---

### Task 7.5: Pleitos (`pleitos.py`) e medição final

**Files:**
- Create: `backend/app/pleitos.py`
- Modify: `backend/app/oficios.py` (`usos` também em `pleitos`), `backend/app/medicoes.py` (`marcar_final`, `desmarcar_final`), `cadastro/cartas.yaml` (textos `pleito_reajuste`, `prazo`, `conclusao`)
- Test: `backend/tests/test_pleitos.py`, `backend/tests/test_medicoes.py`, `backend/tests/test_oficios.py`

**Interfaces:**
- Produces:
  - `criar(conn, usuario_id, contrato_id, tipo, numero_oficio, data_base_mes=None, dias=None, justificativa=None, hoje=None) -> int`;
  - `detalhe(conn, pleito_id, hoje=None) -> dict`, que traz `pendencias` e `anexos`;
  - `listar(conn, contrato_id, tipo=None) -> list[dict]`;
  - `adicionar_anexo(conn, usuario_id, pleito_id, tipo, nome, dados, ext) -> int`;
  - `remover_anexo(conn, usuario_id, pleito_id, anexo_id) -> None`;
  - `corpo_padrao(conn, pleito_id, hoje=None) -> str`;
  - `montar(conn, usuario_id, pleito_id, corpo=None, hoje=None) -> dict`;
  - `receber_assinado(conn, usuario_id, pleito_id, pdf) -> dict`;
  - `previa_envio(conn, pleito_id, remetente=None, hoje=None) -> dict`, no mesmo formato da prévia do protocolo;
  - `enviar(conn, usuario, pleito_id, para, copia, assunto, corpo, justificativa=None, hoje=None) -> int`;
  - `descartar(conn, usuario_id, pleito_id, motivo) -> None`;
  - `medicoes.marcar_final(conn, usuario_id, medicao_id, data: str) -> None`;
  - `medicoes.desmarcar_final(conn, usuario_id, medicao_id, motivo: str) -> None`.
- Tipos de envio: `pleito_reajuste`, `carta_prazo` e `conclusao`.
- Anexos exigidos: `planilha_calculo` e `cronograma` no reajuste (IN 001/2024, art. 21 §1º), `cronograma` no prazo e nenhum na conclusão.

- [ ] **Step 1: Textos em `cartas.yaml`** (chaves de topo, iguais para todas as famílias; a 7.6 troca pelos textos reais do levantamento):

```yaml
pleito_reajuste:
  carta_assunto: 'Asst.: Solicitação de reajustamento contratual – data-base {data_base}'
  carta_corpo: |
    A {razao_social}, inscrita no CNPJ sob o nº {cnpj}, vem respeitosamente à presença de Vossa Senhoria:

    Considerando o Contrato n.º {instrumento}, que tem por objeto {objeto};

    Considerando que o reajuste vale a partir do mês de aniversário da data-base (Orientação Técnica n.º 028/2015/CGE, item 3.2.1);

    Considerando que o mês de aniversário da data-base {data_base} ({indice}) é {mes_aniversario};

    solicitar o reajustamento dos preços contratuais a partir de {aniversario}, conforme planilha de cálculo e cronograma físico-financeiro anexos.

    Sem mais para o momento, subscrevemo-nos.

    Atenciosamente,
  email_assunto: '{oficio} - Pleito de reajuste (data-base {data_base}) - {obra}'
  email_corpo: |
    {saudacao}

    Encaminho, em anexo, arquivo para protocolo.

    Atenciosamente,
prazo:
  carta_assunto: 'Asst.: Solicitação de prorrogação do prazo de execução'
  carta_corpo: |
    # 1. HISTÓRICO DO CONTRATO

    {historico}

    # 2. DO PEDIDO

    {justificativa}

    Diante do exposto, solicitamos a dilação do prazo de execução – e, por consequência, do prazo de vigência contratual – por mais {dias} dias, passando o término da execução de {fim_execucao} para {novo_fim_execucao}, conforme cronograma anexo.

    Atenciosamente,
  email_assunto: '{oficio} - Pedido de prorrogação de prazo - {obra}'
  email_corpo: |
    {saudacao}

    Encaminho, em anexo, arquivo para protocolo.

    Atenciosamente,
conclusao:
  carta_assunto: 'Asst.: Comunicação de conclusão da obra e solicitação de vistoria'
  carta_corpo: |
    A {razao_social}, inscrita no CNPJ sob o nº {cnpj}, comunica a conclusão dos serviços do Contrato n.º {instrumento}, que tem por objeto {objeto}, com a {medicao_final} ({data_final}), e solicita a vistoria para o recebimento provisório do objeto.

    Sem mais para o momento, subscrevemo-nos.

    Atenciosamente,
  email_assunto: '{oficio} - Comunicação de conclusão - {obra}'
  email_corpo: |
    {saudacao}

    Encaminho, em anexo, arquivo para protocolo.

    Atenciosamente,
```

`cadastro_arquivos._cartas` valida essas três chaves quando presentes, com `carta_assunto`, `carta_corpo`, `email_assunto` e `email_corpo` como texto.

- [ ] **Step 2: Testes** (`test_pleitos.py`; fixture com contrato SINFRA, data-base 2024-06, fiscal e o simulador do Graph, como no bloco 5)
  - `test_reajuste_so_para_data_base_do_contrato_e_ciclo_corrente`: `criar(..., "reajuste", "122", data_base_mes="2023-01")` → `ValueError`; com `2024-06` em 15/06/2026 → `ciclo == 2026`.
  - `test_prazo_exige_dias_e_justificativa_e_chuva_vira_pendencia`: sem `dias` → `ValueError`; com a justificativa "chuvas acima da média" e sem paralisação, as pendências trazem o código `chuva`.
  - `test_conclusao_so_em_encerramento`: contrato ativo → `ValueError`; depois de `medicoes.marcar_final`, passa.
  - `test_carta_de_prazo_traz_historico_e_novo_fim`: `montar` → o texto da página 1 traz "HISTÓRICO DO CONTRATO", "O 1º termo aditivo" e o novo fim (execução vigente mais `dias`).
  - `test_enviar_reajuste_fecha_o_aviso_de_pleito`:
    - com os anexos exigidos e o assinado (helper `_assinar` do bloco 5), `enviar` faz o envio do tipo `pleito_reajuste` com 3 anexos;
    - `reajuste.ciclos` fica em `apostilamento_pendente`;
    - o aviso `reajuste_pleito` some.
  - `test_falha_do_graph_nao_muda_o_pleito`: igual ao do bloco 5.
  - Em `test_medicoes.py`:
    - `marcar_final` põe `final=1` e o encerramento no contrato;
    - `desmarcar_final` sem motivo dá `ValueError`;
    - com motivo, limpa os dois quando não há outra medição final.
  - Em `test_oficios.py`: `usos` acha um pleito com o mesmo número.
- [ ] **Step 3:** FAIL.
- [ ] **Step 4: Implementação.**
  - **Estrutura:** `pleitos.py` segue o molde de `protocolo.py`: `_linha`, `_editavel`, anexos com remoção marcada, montar com um documento só (a carta), conferência pelo `assinatura.conferir_pdfs`, e o envio que registra só depois do envio aceito.
  - **Campos da carta**, além dos do protocolo:
    - reajuste: `{data_base}` (MM/AAAA), `{indice}`, `{mes_aniversario}` (nome do mês), `{aniversario}` (DD/MM/AAAA);
    - prazo: `{historico}` (`prazos.historico_texto`), `{justificativa}`, `{dias}`, `{fim_execucao}` e `{novo_fim_execucao}` (execução vigente mais `dias`, calculada em `corpo_padrao` com a execução vigente no dia em que a carta é montada);
    - conclusão: `{medicao_final}` (título da medição com `final=1`) e `{data_final}`.
  - **Pendências:**
    - `nao_montado`, `nao_assinado`, `conferencia`, `oficio_repetido`;
    - `anexo`, uma por anexo exigido que falta;
    - `chuva`: justificativa que casa `r"\bchuv"`, ignorando maiúsculas, num contrato sem nenhuma `paralisacao`.
  - **Envio:**
    - para e cópia como na decisão 1;
    - anexos: o PDF assinado (ou o montado), com nome `{CT} - {obra} - {Pleito de reajuste|Pedido de prorrogação|Comunicação de conclusão}.pdf`, e os anexos arrastados com o nome original;
    - depois do envio aceito, numa transação: `situacao='enviado'`, `enviado_em=hoje`, `envio_id` e `envio_justificativa`, com a auditoria `pleito.enviar`.
  - **Medição final:**

```python
def marcar_final(conn, usuario_id: int, medicao_id: int, data: str) -> None:
    with db.mutacao(conn):
        m = detalhe(conn, medicao_id)
        if m["estado"] in ("cancelada", "desistida"):
            raise ValueError(f"Medição {m['estado']} não pode ser a final")
        conn.execute("UPDATE medicoes SET final=1, final_em=? WHERE id=?", (data, medicao_id))
        conn.execute("UPDATE contratos SET encerramento_iniciado_em=COALESCE(encerramento_iniciado_em, ?) WHERE id=?",
                     (data, m["contrato_id"]))
        auditoria.registrar(conn, usuario_id, "medicao.final", "medicao", medicao_id, {"final": m.get("final")},
                            {"final": 1, "final_em": data})
        auditoria.registrar(conn, usuario_id, "contrato.encerramento", "contrato", m["contrato_id"], None,
                            {"encerramento_iniciado_em": data, "por": "medicao_final", "medicao_id": medicao_id})
```

  `desmarcar_final(conn, usuario_id, medicao_id, motivo)` é simétrico: exige motivo, zera `final` e limpa `encerramento_iniciado_em` só se nenhuma outra medição do contrato tiver `final=1`, com auditoria nos dois.
- [ ] **Step 5:** PASS. **Step 6: Commit** `feat: pleitos de reajuste, prazo e conclusao; medicao final`.

---

### Task 7.6: Rotas, telas e dados reais

**Files:**
- Create: `backend/app/api_pleitos.py`, `frontend/src/FluxoOficio.tsx`, `frontend/src/Reajuste.tsx`, `frontend/src/Prazos.tsx`, `frontend/src/Reajuste.test.tsx`
- Modify: `backend/app/api_medicoes.py`, `backend/app/main.py`, `frontend/src/ObraAbas.tsx`, `frontend/src/Medicoes.tsx`, `cadastro/contratos/*.yaml`, `cadastro/cartas.yaml`
- Test: `backend/tests/test_api_pleitos.py`

**Rotas:**

| Método e caminho | Resposta |
|---|---|
| `GET /api/contratos/{id}/reajuste` | `{"ciclos": reajuste.ciclos, "pleitos": pleitos.listar(tipo="reajuste")}` |
| `GET /api/contratos/{id}/prazos` | `{"situacao": prazos.situacao, "historico": prazos.historico_texto, "pleitos": pleitos.listar(tipo in prazo, conclusao)}` |
| `POST /api/contratos/{id}/pleitos` `{tipo, numero_oficio, data_base_mes?, dias?, justificativa?}` | detalhe (201) |
| `GET /api/pleitos/{id}` | detalhe + `corpo_padrao` |
| `POST /api/pleitos/{id}/anexos` (multipart `tipo`, `arquivo`) · `.../anexos/{aid}/remover` | detalhe |
| `POST /api/pleitos/{id}/montar` `{corpo?}` · `GET /api/pleitos/{id}/documento` · `POST /api/pleitos/{id}/assinado` | detalhe / PDF / detalhe |
| `POST /api/pleitos/{id}/previa` · `POST /api/pleitos/{id}/enviar` `{para, copia, assunto, corpo, justificativa?}` · `POST /api/pleitos/{id}/descartar` `{motivo}` | prévia / `{envio_id}` / ok |
| `POST /api/medicoes/{id}/final` `{data?}` · `POST /api/medicoes/{id}/final/desmarcar` `{motivo}` | medição |

Permissões e erros como em `api_protocolos.py`.

**Telas:**
- `FluxoOficio.tsx` (genérico, usado por Reajuste e Prazos), em passos:
  1. número do ofício e os campos do tipo (data-base; dias e justificativa);
  2. anexos exigidos com "Anexar";
  3. carta: textarea com o corpo e "Montar" → "Baixar";
  4. "Arrastar o assinado" → conferência;
  5. "Prévia" → para, cópia, assunto e corpo editáveis, anexos, pendências, justificativa;
  6. "Enviar".
- `Reajuste.tsx`: tabela dos ciclos com data-base, índice, aniversário, situação (selo) e dias. "Enviar pleito" abre o `FluxoOficio` do tipo reajuste com a data-base marcada. Embaixo, a lista dos pleitos enviados (data, ofício, origem "sistema" ou "carga") e os apostilamentos.
- `Prazos.tsx`:
  - situação: execução, vigência e folga com os dias, o selo de paralisação e o do endosso;
  - tabela dos instrumentos, com o selo "retroativo";
  - paralisações;
  - histórico em texto (o mesmo da carta);
  - "Pedir prorrogação" (`FluxoOficio` de prazo);
  - em encerramento: marcos (provisório, definitivo, baixa da garantia) e "Comunicar conclusão" (`FluxoOficio` de conclusão).
- `Medicoes.tsx`: na linha da medição, "Marcar como medição final". Confirma e mostra "o contrato entra em encerramento". Quando marcada, mostra o selo "final" e "desmarcar" (pede motivo).

**Dados reais (tarefa de dados; sem teste novo além do `cadastro validar`):**
- `pleitos_anteriores` de cada contrato, tirados de `docs/reajuste-pleitos-2026-09-17.md` e `docs/prazos-vigencia-execucao-2026-09-17.md`: para cada pleito de 2026 citado ali com ofício e data (exemplos: CT-122-LT-2026 Cavalaria, reajuste, 23/04/2026; os de apostilamento da Orla CT/068 e CT/245 e do Granito CT/135 e CT/248), uma linha com a fonte em comentário.
- `folga_vigencia_dias` nos contratos MTPAR com o valor do levantamento (78 ou 55 dias, por contrato).
- As paralisações conhecidas: MT-402, de 01/02 a 05/05/2026 (paralisação e reinício), e Coxipó 2ª, desde 01/10/2025 (paralisação). Cada uma com `# CONFERIR: Leonardo` no YAML (P2 do índice).
- Os textos reais de `cartas.yaml` (`pleito_reajuste`, `prazo`, `conclusao`), a partir do CT-122 (reajuste), do CT331 da Cavalaria (prazo) e do CT/245 da Orla (conclusão, levantamento 5.0).

- [ ] **Step 1: Testes.**
  - API: fluxo feliz do pleito de reajuste pelo simulador; `POST /api/medicoes/{id}/final` põe o contrato em encerramento, e `GET /prazos` mostra `encerramento`.
  - `Reajuste.test.tsx`: a tabela mostra "pleito não enviado", e "Enviar pleito" abre o fluxo com a data-base.
- [ ] **Step 2:** FAIL. **Step 3:** implementar. **Step 4:** PASS; `cadastro validar` e `cadastro aplicar --ensaio` sobre cópia da produção: diferença só nos campos e pleitos novos. Conferir na tela inicial da cópia que os avisos de reajuste batem com o levantamento de 17/09: só os ciclos sem pleito registrado.
- [ ] **Step 5: Verificação visual**:
  - aba Reajuste do Cultural;
  - aba Prazos da MT-402 (paralisação encerrada, instrumentos, retroativo se houver);
  - carta de prazo montada e aberta;
  - marcar e desmarcar a medição final numa obra da cópia.
- [ ] **Step 6: Commit** `feat: telas de reajuste e prazos, rotas dos pleitos e dados reais do cadastro`.

---

### Task 7.7: Documentação e suíte

- [ ] **Step 1:** Runbook, seção "Reajuste, prazos e encerramento (bloco 7)":
  - ciclo do reajuste;
  - regras de prazo (60/30, paralisação, folga, endosso de 60 dias);
  - medição final e o YAML;
  - como registrar pleito antigo, paralisação, endosso e marcos no cadastro.

  Backlog: paralisações e folgas a conferir (P2); pleitos antigos que o levantamento não cobriu.
- [ ] **Step 2:** suíte do backend; depois `npm test -- --run` e `npm run build`.
- [ ] **Step 3: Commit** `docs: runbook e backlog do bloco 7`. Seguir para o bloco 8.

## Self-review

- **§7.2:**
  - unidade (contrato, data-base): 7.3;
  - aniversário e janela de 30 dias: 7.3;
  - pleito pelo sistema com CT manual e anexos: 7.5;
  - "apostilamento pendente há N dias": 7.3;
  - apostilamento fecha: 7.3;
  - reemissão é novo pleito no mesmo ciclo: o último enviado vale;
  - `sem_reajuste`: 7.3;
  - "execução sem reajuste par" sai: bloco 6.
- **§7.3:**
  - relógio da execução e 60/30: 7.4;
  - vigência só sem prorrogação automática: 7.4;
  - folga por órgão (e por contrato): 7.2 e 7.4;
  - carta com histórico: 7.4 e 7.5;
  - pedido enviado com instrumento pendente: 7.4;
  - endosso em 5 dias: 7.4;
  - vencida sem instrumento é crítico: 7.4;
  - termo aditivo e apostilamento aceitos: `aditivos` de forma `termo_aditivo` ou `apostilamento`;
  - retroativo sinalizado: 7.4;
  - paralisação: 7.4;
  - "chuva": 7.5.
- **§7.4:** `em_encerramento` pela medição final, 7.5; avisos de prazo param, 7.4; quatro marcos, 7.4 e 7.6; conclusão não comunicada, 7.4.
- **§11:** execução vencendo, instrumento pendente, vigência vencendo, folga quebrada, endosso, os dois de reajuste, obra paralisada (diretoria) e conclusão não comunicada, todos em 7.3 e 7.4.
