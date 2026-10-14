# Bloco 8 (Diretoria e QDOP): tela da diretoria na cota da Lotufo e exportação do QDOP no leiaute oficial. Plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. **Leia antes `00-indice.md`.** Branch `bloco8-diretoria`, criada de `bloco7-reajuste-prazos`.

**Goal:** a diretoria abre uma tela só, sempre na cota da Lotufo e com o vocabulário fixo (medido, faturado, protocolado, recebido), organizada em cinco seções:
1. **Onde está o dinheiro**, com o protocolado por idade e por órgão.
2. **O mês e o ano**, comparados com o previsto e com o ano anterior.
3. **Os próximos seis meses.**
4. **A carteira.**
5. **As obras**, com farol e motivo.

A tela mostra também os avisos da diretoria. Um botão exporta o **QDOP** no leiaute oficial GL.SGI.FRP.DE.250.

**Architecture:**
- `app/diretoria.py` calcula as seções a partir de medições, protocolos, recebimentos, cronograma e cadastro; também calcula o prazo normal de cada órgão e o aviso de pagamento atrasado, que entra como FONTE em `avisos`.
- `app/qdop.py` monta as linhas do QDOP e escreve o `.xlsx` sobre um modelo recortado do arquivo oficial, guardado no cadastro e copiado para a pasta de dados.
- `Diretoria.tsx` substitui o `PainelGeral.tsx`.
- Nenhuma migração.

**Tech Stack:** o do índice; openpyxl 3.1.5 (já dependência) para escrever o QDOP.

**Spec:** §10.5 (tela), §11 (avisos da diretoria: execução vencida sem instrumento, pagamento atrasado, obra paralisada, reajuste pendente há mais de 90 dias), §8 (cadastro), memória "base cheia × cota" (medições no cheio, diretoria na cota).

**Status:** APROVADO pelo Leonardo em 2026-09-24 (ver `00-indice.md`).

## Decisões deste bloco (para aprovação)

1. **Cota sempre.** Cada valor passa por `contratos.cota(centavos, percentual_direito_bp)` do seu contrato. As medições guardam o cheio; o cronograma também (memória "base cheia × cota"), e é convertido do mesmo jeito.
2. **Onde está o dinheiro.**

   | Grupo | Critério |
   |---|---|
   | Medido esperando nota | medições em `espelho_gerado` ou `espelho_enviado` |
   | Nota emitida esperando protocolo | medições em `nota_emitida` |
   | Protocolado esperando pagamento | medições em `protocolada` ou `nf_emitida`, por faixa de dias desde o **primeiro** protocolo (até 30, 31 a 60, mais de 60) e por órgão |
   | Recebido no mês | `recebida_em` no mês |

   À parte: reajustes esperando apostilamento, com quantidade e maior número de dias (de `reajuste.ciclos`). O "valor já medido" do reajuste fica fora: o sistema não sabe quanto do medido depende do apostilamento.
3. **Total a receber só depois de conciliado** (spec §10.5). Enquanto `geral.yaml` tiver `diretoria.total_a_receber_liberado: false`, o grupo "protocolado esperando pagamento" mostra quantidade e dias, **sem valor**, com a nota "valores a conciliar com a controladoria". O Leonardo troca para `true` quando a conciliação fechar.
4. **Prazo do órgão.**
   - Amostra: dias entre o primeiro protocolo e o `recebida_em` das medições recebidas nos últimos 12 meses em contratos do órgão.
   - **Prazo normal:** 3º quartil, pela posição mais próxima.
   - **Previsão de recebimento:** usa a mediana da mesma amostra.
   - **Amostra pequena:** com menos de 10 medições, os dois valem 30 dias.
5. **O mês e o ano.**
   - Medido no mês: medições da competência, execução, projeto e reajuste, fora as canceladas, desistidas e previstas.
   - Comparado com o previsto do mês (cronograma vigente) e com a mesma competência do ano anterior.
   - Mais o acumulado do ano e a série de 12 meses (medido e previsto).
6. **Os próximos meses.**
   - **Faturamento previsto:** 6 meses, do mês corrente aos cinco seguintes, pelo cronograma dos contratos ativos.
   - **Recebimento previsto:** para cada medição protocolada e não recebida, a data do primeiro protocolo mais a mediana do órgão. O que já passou da data cai no mês corrente.
7. **Carteira.**
   - **Saldo a executar:** soma, nos contratos ativos, de (valor vigente − medido acumulado de execução e projeto), na cota.
   - **Ritmo:** medido de execução e projeto nos últimos 6 meses, dividido por 6.
   - **Meses de produção:** saldo ÷ ritmo.
   - **Participação de cada órgão:** no saldo.
   - **Contratos que terminam em até 183 dias:** pela execução vigente.
8. **Obras.**
   - As linhas do QDOP, mais farol e motivo:
     - vermelho: algum aviso **crítico** da diretoria para a obra;
     - amarelo: outro aviso da diretoria;
     - verde: nenhum.
   - O motivo é a mensagem dos avisos.
   - O clique abre a página da obra.
9. **QDOP.**
   - **Modelo:** `cadastro/modelos/qdop/qdop-modelo.xlsx`, recortado do oficial de 22/09 com cabeçalho (linhas 1 a 13), a linha 14 como estilo das linhas de dados e o rodapé de assinaturas.
   - **Valores, não fórmulas:** abre certo em visualizador sem recálculo; Excel não recalcula nada.
   - **Colunas:**
     - Contratante: `orgaos.nome_qdop`.
     - Tipo: `orgaos.tipo_contratante`, PÚBLICO ou PRIVADO.
     - Datas: início e término da execução vigente, e fim da vigência vigente.
     - Empreita: PRÓPRIA se a entidade do contrato é a Lotufo, senão CONSÓRCIO.
     - % de direito.
     - Valores na cota: PI = valor original; VA = vigente − original; PI+VA.
     - Reajuste (recebido): medições de reajuste recebidas.
     - Faturados (PI+VA): medições de execução e projeto recebidas. É o sentido do QDOP (diário T7: "faturados" no QDOP é recebido).
     - Saldo = PI+VA − faturados.
     - % recebido e % a receber: sobre PI+VA.
     - Status: EM ANDAMENTO, PARALISADA (paralisação aberta) ou CONCLUÍDA (em encerramento ou encerrado).
     - Localidade: município em maiúsculas + " - MT".
     - Descrição: `objeto_completo`.
   - **Totalizadores:** PRÓPRIA, CONSÓRCIO e TOTAL nas linhas 9 a 11, como no oficial.
   - **Data da atualização:** hoje, em S7.
   - **Ordem das linhas:** início da execução, como no oficial.
10. **Cadastro atualizado pelo QDOP de 22/09** (tarefa de dados 8.2), com a conferência que já existe (`carga_legado.conferir_com_qdop`) gerando a lista de diferenças:
    - `objeto_completo` de todas as obras, tirado da coluna DESCRIÇÃO;
    - `nome_qdop` e `tipo_contratante` de cada órgão;
    - datas e valores que o QDOP (3) corrigiu: BR-163, Estações BRT, Deciolândia, apostilamentos de Leblon e MT-402.

    A obra nova do QDOP, Rota do Oeste lote 2 (consórcio, 20%), entra só com a entidade consórcio confirmada pelo Leonardo (P2).
11. **Painel antigo.** `PainelGeral.tsx` sai do menu e da rota: `/painel` passa a abrir a Diretoria. As rotas de backend `consolidado` e `curva` ficam até o bloco 9 decidir; `curva` é usada pela aba Contrato.

## Estrutura de arquivos

| Arquivo | Responsabilidade |
|---|---|
| `backend/app/diretoria.py` | prazo do órgão, seções da tela, aviso de pagamento atrasado |
| `backend/app/qdop.py` | linhas do QDOP e escrita do `.xlsx` sobre o modelo |
| `backend/app/avisos.py` | `FONTES` com `diretoria.avisos_pagamento` |
| `backend/app/cadastro_arquivos.py`, `cadastro_aplicar.py` | `nome_qdop` e `tipo_contratante` do órgão; `geral.yaml`: `qdop.modelo` e `diretoria.total_a_receber_liberado`; cópia do modelo |
| `backend/app/api_diretoria.py`, `main.py` | rotas |
| `cadastro/modelos/qdop/qdop-modelo.xlsx`, `cadastro/geral.yaml`, `cadastro/orgaos.yaml`, `cadastro/contratos/*.yaml` | modelo e dados |
| `frontend/src/Diretoria.tsx` (+ `.test.tsx`), `rota.tsx`, `App.tsx` | tela; sai `PainelGeral.tsx` do menu |

---

### Task 8.1: Modelo do QDOP e cadastro da diretoria

**Files:**
- Create: `cadastro/modelos/qdop/qdop-modelo.xlsx` (gerado pelo script abaixo, a partir do oficial)
- Modify: `cadastro/geral.yaml`, `cadastro/orgaos.yaml`, `backend/app/cadastro_arquivos.py`, `backend/app/cadastro_aplicar.py`
- Test: `backend/tests/test_cadastro_arquivos.py`, `backend/tests/test_cadastro_aplicar.py`

- [ ] **Step 1: Recortar o modelo** (script no scratchpad; openpyxl só para **criar o modelo**, não para editar entrega do usuário):

```python
import copy, openpyxl
ORIG = r"C:\Users\<usuario>\Downloads\LICITAÇÕES 11.08.2026\GL.SGI.FRP.DE.250 - QDOP - QUADRO DEMONSTRATIVO DE OBRAS E PROJETOS (3).xlsx"
wb = openpyxl.load_workbook(ORIG)
ws = wb.active
rodape = [[(c.column, c.value, copy.copy(c._style)) for c in ws[r] if c.value] for r in (39, 40)]
alturas = {r: ws.row_dimensions[r].height for r in (14, 39, 40)}
ws.delete_rows(15, ws.max_row - 14)            # fica o cabecalho (1-13) e a linha 14 como estilo
for c in ws[14]:
    c.value = None
for i, linha in enumerate(rodape):
    for col, valor, estilo in linha:
        cel = ws.cell(16 + i, col, valor)
        cel._style = estilo
ws.print_area = "A1:S17"
wb.save(r"cadastro\modelos\qdop\qdop-modelo.xlsx")
```

Abrir o modelo no Excel (COM invisível, instrução global do Leonardo) e exportar o PDF da página 1 para conferir:
- cabeçalho, logo (se houver) e colunas iguais ao oficial;
- a linha 14 vazia e formatada;
- rodapé nas linhas 16 e 17.

O aviso "Unknown extension is not supported" do openpyxl ao ler o oficial indica perda de extensões (formatação condicional estendida). Conferir no PDF se algo visível sumiu e anotar no backlog.
- [ ] **Step 2: Cadastro.** Em `geral.yaml`:

```yaml
# Diretoria (bloco 8; spec §10.5). O total a receber so' vai para a tela depois de conciliado com a controladoria.
diretoria:
  total_a_receber_liberado: false
# QDOP (GL.SGI.FRP.DE.250): modelo recortado do oficial de 22/09/2026 (cabecalho, estilo da linha 14, rodape).
qdop:
  modelo: modelos/qdop/qdop-modelo.xlsx
```

Em cada órgão de `orgaos.yaml`, `nome_qdop` e `tipo_contratante`, com os nomes exatos da coluna CONTRATANTE do QDOP (3). Exemplos: `SINFRA - SECRETARIA DE ESTADO DE INFRAESTRUTURA E LOGISTICA DE MATO GROSSO`, `MT PARTICIPAÇÕES E PROJETOS S.A – MT-PAR`, `SES - SECRETARIA DE ESTADO DE SAUDE DE MATO GROSSO`, `SECRETARIA DE OBRAS PÚBLICAS DE CUIABÁ - MT`, `SECRETARIA MUNICIPAL DE SAÚDE (SMS/VG)`, `CONCESSIONÁRIA ROTA DO OESTE S.A.` (PRIVADO).

- [ ] **Step 3: Testes e código.**
  - `cadastro_arquivos` passa a validar:
    - `tipo_contratante` em (`PÚBLICO`, `PRIVADO`);
    - `nome_qdop` como texto;
    - `geral.diretoria.total_a_receber_liberado` como booleano;
    - `geral.qdop.modelo` como arquivo existente relativo à raiz (vira `modelo_caminho`).
  - `cadastro_aplicar` copia o modelo para a pasta de dados, pelo mesmo `_no_disco` do bloco 5 (pasta `modelos`, extensão `xlsx`), e grava `cadastro_geral['qdop'] = {"modelo": rel}`.
  - Testes:
    - órgão com `tipo_contratante: MISTO` → erro;
    - aplicar grava `qdop.modelo`, que existe na pasta de dados;
    - reaplicar é igual.
- [ ] **Step 4:** PASS; `cadastro validar`. **Step 5: Commit** `feat: modelo do QDOP e cadastro da diretoria`.

---

### Task 8.2: Cadastro atualizado pelo QDOP de 22/09 (dados)

**Files:**
- Modify: `cadastro/contratos/*.yaml`, `cadastro/orgaos.yaml`
- Create: `docs/conferencia-qdop-2026-09-22.md`

- [ ] **Step 1: Conferência.** Rodar a conferência existente contra o (3), sobre cópia da produção:

```bash
cd backend && .venv\Scripts\python -c "from app import db, carga_legado; c=db.get_conn(); print(carga_legado.conferir_com_qdop(c, r'C:\Users\<usuario>\Downloads\LICITAÇÕES 11.08.2026\GL.SGI.FRP.DE.250 - QDOP - QUADRO DEMONSTRATIVO DE OBRAS E PROJETOS (3).xlsx'))"
```

Usar `DASH_DB_PATH` apontando para a cópia no scratchpad. Se a assinatura de `conferir_com_qdop` pedir outro formato, ler a função e adaptar a chamada. Não mudar a função sem necessidade.

- [ ] **Step 2: `docs/conferencia-qdop-2026-09-22.md`.** Uma linha por obra: campo, cadastro, QDOP (3) e o que fazer. Nas datas e valores, a regra da memória "hierarquia das fontes": instrumento assinado manda, e o QDOP confere mas não alimenta. **Só vira YAML** o que tem instrumento ou fato documentado:
  - datas de execução e vigência com aditivo ou apostilamento conhecido;
  - valor com aditivo.

  O resto fica como pendência do Leonardo na seção P2 do documento.
- [ ] **Step 3: YAML.**
  - `objeto_completo` de todas as obras, a partir da DESCRIÇÃO do QDOP (texto do QDOP, em maiúsculas como está);
  - os instrumentos que o QDOP (3) reflete e que têm número e data (apostilamentos de Leblon e MT-402), com `# fonte: QDOP 22/09/2026, conferir o PDF` se o PDF não estiver no repositório;
  - Rota do Oeste lote 2: arquivo do contrato preparado e **comentado**, até a entidade consórcio ser confirmada.
- [ ] **Step 4:** `cadastro validar` e `cadastro aplicar --ensaio` sobre a cópia da produção. Anexar o relatório ao documento. **Step 5: Commit** `docs: conferencia do cadastro com o QDOP de 22/09 e objeto completo das obras`.

---

### Task 8.3: Diretoria (`diretoria.py`)

**Files:**
- Create: `backend/app/diretoria.py`
- Modify: `backend/app/avisos.py` (`FONTES` com `diretoria.avisos_pagamento`)
- Test: `backend/tests/test_diretoria.py`

**Interfaces:**
- Consumes: `contratos.vigente`, `contratos.cota`, `cronograma.previsto_efetivo(conn, contrato_id) -> {competencia: centavos}`, `reajuste.ciclos`, `avisos.listar`, `qdop.linhas` (8.4; nesta tarefa, `painel` chama `qdop.linhas`, criado na 8.4, então implementar 8.4 **antes** do teste de `obras`, ou marcar esse teste para a 8.4).
- Produces: `prazo_orgao(conn, orgao_id, hoje, quantil=0.75) -> int`; `painel(conn, hoje=None) -> dict` (chaves `hoje`, `total_a_receber_liberado`, `dinheiro`, `mes_ano`, `proximos`, `carteira`, `obras`, `avisos`); `avisos_pagamento(conn, hoje=None) -> list[dict]`.

- [ ] **Step 1: Testes** (fixture com dois contratos: um próprio de 100% e um consórcio de 50%; medições em vários estados com valores redondos; protocolos e recebimentos com datas conhecidas; cronograma com previsto)

```python
def test_prazo_do_orgao_quartil_e_minimo(cenario):
    c, ids = cenario                  # 12 medicoes recebidas da SINFRA com 5,5,5,6,6,7,8,9,10,12,20,40 dias
    assert diretoria.prazo_orgao(c, ids["sinfra"], D(2026, 9, 24)) == 10          # posicao ceil(0,75*12)=9 -> 10
    assert diretoria.prazo_orgao(c, ids["sinfra"], D(2026, 9, 24), quantil=0.5) == 7
    assert diretoria.prazo_orgao(c, ids["mtpar"], D(2026, 9, 24)) == 30           # menos de 10 amostras


def test_dinheiro_na_cota_e_por_faixa(cenario):
    c, ids = cenario
    d = diretoria.painel(c, D(2026, 9, 24))["dinheiro"]
    assert d["medido_esperando_nota"]["valor_centavos"] == 1_000_000 + 500_000     # 10 mil proprio + 50% de 10 mil
    assert d["protocolado"]["faixas"]["mais_60"]["quantidade"] == 1


def test_total_a_receber_escondido_ate_liberar(cenario):
    c, ids = cenario
    p = diretoria.painel(c, D(2026, 9, 24))
    assert p["total_a_receber_liberado"] is False
    assert p["dinheiro"]["protocolado"]["faixas"]["ate_30"]["valor_centavos"] is None
    ids["liberar"]()                                  # cadastro_geral diretoria.total_a_receber_liberado = true
    assert diretoria.painel(c, D(2026, 9, 24))["dinheiro"]["protocolado"]["faixas"]["ate_30"]["valor_centavos"] == 700_000


def test_mes_e_ano_contra_previsto_e_ano_anterior(cenario): ...
    # medido 09/2026 = 1.500.000 (cota), previsto 09/2026 = 2.000.000, 09/2025 = 800.000, serie com 12 meses
def test_recebimento_previsto_pela_mediana_do_orgao(cenario): ...
    # protocolada em 2026-09-20 na SINFRA (mediana 7) -> cai em 09/2026; em 2026-09-28 -> 10/2026
def test_carteira_saldo_ritmo_e_termino(cenario): ...
def test_pagamento_atrasado_so_para_a_diretoria(cenario): ...
    # protocolada ha 45 dias na SINFRA (Q3 = 10) -> aviso 'pagamento_atrasado' publico ['diretoria'], com a mensagem
    # "protocolada há 45 dias; o prazo normal do órgão é 10 dias"
```

(Escrever os quatro esboçados por inteiro, no padrão dos três completos.)

- [ ] **Step 2:** FAIL. **Step 3: Implementação.** Núcleo:

```python
"""Tela da diretoria (spec 2026-09-21 §10.5), bloco 8. Tudo na COTA da Lotufo; vocabulario fixo:
medido, faturado (nota emitida), protocolado, recebido. O total a receber so' aparece com o cadastro
liberando (conciliacao com a controladoria)."""
import datetime
import json
import math

from app import avisos as _av, contratos, cronograma, reajuste, tempo

QUARTIL, MEDIANA, MINIMO, PADRAO_DIAS = 0.75, 0.5, 10, 30
ESPERANDO_NOTA = ("espelho_gerado", "espelho_enviado")
ESPERANDO_PROTOCOLO = ("nota_emitida",)
PROTOCOLADAS = ("protocolada", "nf_emitida")
FORA = ("cancelada", "desistida", "prevista")


def _quantil(valores: list[int], q: float) -> int:
    v = sorted(valores)
    return v[max(0, math.ceil(q * len(v)) - 1)]


def _medicoes(conn) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT m.*, c.percentual_direito_bp AS pct, c.orgao_id, c.nome_curto AS obra, "
        "(SELECT MIN(mp.data) FROM medicao_protocolos mp WHERE mp.medicao_id=m.id) AS protocolo_em "
        "FROM medicoes m JOIN contratos c ON c.id=m.contrato_id")]


def _cota(m: dict) -> int:
    return contratos.cota(m["valor_protocolado_centavos"] or 0, m["pct"]) or 0


def prazo_orgao(conn, orgao_id: int, hoje: datetime.date, quantil: float = QUARTIL) -> int:
    desde = (hoje - datetime.timedelta(days=365)).isoformat()
    dias = [(datetime.date.fromisoformat(m["recebida_em"][:10]) - datetime.date.fromisoformat(m["protocolo_em"][:10])).days
            for m in _medicoes(conn)
            if m["orgao_id"] == orgao_id and m["estado"] == "recebida" and m["recebida_em"] and m["protocolo_em"]
            and m["recebida_em"][:10] >= desde]
    dias = [d for d in dias if d >= 0]
    return _quantil(dias, quantil) if len(dias) >= MINIMO else PADRAO_DIAS


def _liberado(conn) -> bool:
    r = conn.execute("SELECT valor FROM cadastro_geral WHERE chave='diretoria'").fetchone()
    return bool(json.loads(r["valor"]).get("total_a_receber_liberado")) if r else False


def _grupo(ms: list[dict], com_valor: bool = True) -> dict:
    return {"quantidade": len(ms), "valor_centavos": sum(_cota(m) for m in ms) if com_valor else None}


def _mes(d: datetime.date, soma: int = 0) -> str:
    total = d.year * 12 + d.month - 1 + soma
    return f"{total // 12:04d}-{total % 12 + 1:02d}"
```

As seções seguem a ordem das decisões 2 a 8, cada uma numa função privada (`_dinheiro`, `_mes_ano`, `_proximos`, `_carteira`, `_obras`) que recebe `(conn, ms, hoje, liberado)` e devolve o dict da seção. Regras de cada uma:
- **Faixas do protocolado:** usam `(hoje − protocolo_em).days`: até 30, 31 a 60, mais de 60.
- **Por órgão:** agrupa por `orgao_id` com o nome de `orgaos.nome`, a quantidade, o valor (ou `None`) e o maior número de dias.
- **Previsto do mês:** soma, nos contratos ativos, de `cotas(cronograma.previsto_efetivo(conn, cid).get(mes, 0))`.
- **Recebimento previsto:** `protocolo_em + prazo_orgao(conn, orgao_id, hoje, MEDIANA)`, com `max(data, hoje)` para o que já passou, agrupado por mês.

`avisos_pagamento`: para cada medição protocolada e não recebida, com `dias = (hoje − protocolo_em)` maior que `prazo_orgao(Q3)`, `_av.aviso("pagamento_atrasado", "acao", f"{obra}: {titulo} protocolada há {dias} dias; o prazo normal do órgão é {prazo} dias", ..., valor_centavos=_cota(m) if liberado else None, publico=("diretoria",))`. Registrar em `avisos.FONTES`. Para evitar import circular, `avisos` importa `diretoria` dentro de uma função que lista as fontes (o mesmo cuidado da 7.3).

`painel(...)["avisos"] = _av.listar(conn, hoje, publico="diretoria")`.

- [ ] **Step 4:** PASS. **Step 5: Commit** `feat: secoes da tela da diretoria e aviso de pagamento atrasado`.

---

### Task 8.4: QDOP (`qdop.py`)

**Files:**
- Create: `backend/app/qdop.py`
- Test: `backend/tests/test_qdop.py`

**Interfaces:**
- Produces: `linhas(conn, hoje=None) -> list[dict]`. Chaves de cada linha: `contrato_id`, `seq`, `contratante`, `tipo`, `inicio`, `termino`, `vigencia`, `empreita`, `direito` (fração), `pi`, `va`, `pi_va`, `reajuste_recebido`, `faturados`, `saldo` (centavos, na cota), `pct_recebido`, `pct_a_receber`, `status`, `localidade`, `descricao`, `obra`.
- Produces: `gerar_xlsx(conn, hoje=None) -> bytes`.

- [ ] **Step 1: Testes**

```python
"""QDOP (GL.SGI.FRP.DE.250) exportado no leiaute oficial (bloco 8)."""
import datetime
import io

import openpyxl

from app import qdop

D = datetime.date


def test_linha_na_cota_com_faturados_recebidos(cenario):
    c, ids = cenario          # consorcio 50%: original 10.000.000,00; aditivo 2.000.000,00; recebido exec 4.000.000,00; reaj 100.000,00
    l = next(x for x in qdop.linhas(c, D(2026, 9, 24)) if x["contrato_id"] == ids["consorcio"])
    assert (l["empreita"], l["direito"]) == ("CONSÓRCIO", 0.5)
    assert (l["pi"], l["va"], l["pi_va"]) == (500_000_000, 100_000_000, 600_000_000)
    assert (l["faturados"], l["reajuste_recebido"], l["saldo"]) == (200_000_000, 5_000_000, 400_000_000)


def test_status_paralisada_e_concluida(cenario): ...
    # paralisacao aberta -> PARALISADA; encerramento_iniciado_em -> CONCLUÍDA; senao EM ANDAMENTO


def test_xlsx_no_leiaute_oficial(cenario):
    c, ids = cenario
    wb = openpyxl.load_workbook(io.BytesIO(qdop.gerar_xlsx(c, D(2026, 9, 24))))
    ws = wb.active
    assert ws["S1"].value == "GL.SGI.FRP.DE.250"
    assert ws["A13"].value == "SEQ." and ws["S13"].value == "DESCRIÇÃO DA OBRA"
    assert ws["A14"].value == 1 and ws["I14"].value == 100_000.00          # PI do primeiro contrato em reais
    ultima = 13 + len(qdop.linhas(c, D(2026, 9, 24)))
    assert ws.cell(ultima + 2, 1).value == "DEPARTAMENTO DE ENGENHARIA"
    assert ws["K11"].value == sum(l["pi_va"] for l in qdop.linhas(c, D(2026, 9, 24))) / 100
    assert ws.print_area.endswith(f"$S${ultima + 3}")
```

(A fixture aplica um cadastro mínimo com `geral.qdop.modelo` apontando para uma cópia do modelo real `cadastro/modelos/qdop/qdop-modelo.xlsx`.)

- [ ] **Step 2:** FAIL. **Step 3: Implementação**

```python
"""QDOP - Quadro Demonstrativo de Obras e Projetos (GL.SGI.FRP.DE.250), bloco 8.

Escrito sobre um MODELO recortado do arquivo oficial (cabecalho 1-13, linha 14 como estilo, rodape 16-17),
com VALORES e nao formulas: abre certo em qualquer visualizador. Tudo na cota. "Faturados" no QDOP e'
RECEBIDO (diario T7); reajuste recebido fica na coluna propria.
"""
import copy
import datetime
import io
import json

import openpyxl

from app import arquivos, contratos, prazos, tempo

COLUNAS = ("seq", "contratante", "tipo", "inicio", "termino", "vigencia", "empreita", "direito", "pi", "va",
           "pi_va", "reajuste_recebido", "faturados", "saldo", "pct_recebido", "pct_a_receber", "status",
           "localidade", "descricao")
EM_REAIS = {"pi", "va", "pi_va", "reajuste_recebido", "faturados", "saldo"}
DATAS = {"inicio", "termino", "vigencia"}


def _recebido(conn, contrato_id: int, pct, reajuste: bool) -> int:
    cond = "m.tipo='reajuste'" if reajuste else "m.tipo IN ('execucao','projeto')"
    total = conn.execute(f"SELECT COALESCE(SUM(m.valor_protocolado_centavos),0) FROM medicoes m "
                         f"WHERE m.contrato_id=? AND m.estado='recebida' AND {cond}", (contrato_id,)).fetchone()[0]
    return contratos.cota(total, pct) or 0


def linhas(conn, hoje: datetime.date | None = None) -> list[dict]:
    hoje = hoje or tempo.hoje_local()
    out = []
    for c in conn.execute("SELECT c.id, o.regras, o.nome AS orgao_nome, e.papel FROM contratos c "
                          "JOIN orgaos o ON o.id=c.orgao_id LEFT JOIN entidades e ON e.id=c.entidade_id "
                          "WHERE c.estado<>'rescindido' ORDER BY c.execucao_inicio, c.id").fetchall():
        v = contratos.vigente(conn, c["id"])
        regras = json.loads(c["regras"] or "{}")
        pct = v["percentual_direito_bp"]
        pi = contratos.cota(v["valor_original_centavos"], pct) or 0
        pi_va = contratos.cota(v["valor_vigente_centavos"], pct) or 0
        faturados = _recebido(conn, c["id"], pct, False)
        s = prazos.situacao(conn, c["id"], hoje)
        status = ("CONCLUÍDA" if v.get("encerramento_iniciado_em") or v["estado"] == "encerrado"
                  else "PARALISADA" if s["paralisacao"] else "EM ANDAMENTO")
        out.append({"contrato_id": c["id"], "obra": v.get("nome_curto"),
                    "contratante": regras.get("nome_qdop") or c["orgao_nome"],
                    "tipo": regras.get("tipo_contratante") or "PÚBLICO",
                    "inicio": v.get("execucao_inicio"), "termino": v.get("execucao_fim_vigente"),
                    "vigencia": v.get("vigencia_fim_vigente"),
                    "empreita": "PRÓPRIA" if c["papel"] == "lotufo" else "CONSÓRCIO",
                    "direito": (pct or 10000) / 10000, "pi": pi, "va": pi_va - pi, "pi_va": pi_va,
                    "reajuste_recebido": _recebido(conn, c["id"], pct, True), "faturados": faturados,
                    "saldo": pi_va - faturados, "pct_recebido": faturados / pi_va if pi_va else 0,
                    "pct_a_receber": (pi_va - faturados) / pi_va if pi_va else 0, "status": status,
                    "localidade": f"{(v.get('municipio') or '').upper()} - MT" if v.get("municipio") else "",
                    "descricao": v.get("objeto_completo") or v.get("objeto") or ""})
    for i, l in enumerate(out, 1):
        l["seq"] = i
    return out


def _modelo(conn):
    r = conn.execute("SELECT valor FROM cadastro_geral WHERE chave='qdop'").fetchone()
    if r is None:
        raise ValueError("Modelo do QDOP não carregado: rode `cadastro aplicar` com geral.yaml (qdop.modelo)")
    return arquivos.caminho_seguro(json.loads(r["valor"])["modelo"])


def gerar_xlsx(conn, hoje: datetime.date | None = None) -> bytes:
    hoje = hoje or tempo.hoje_local()
    ls = linhas(conn, hoje)
    wb = openpyxl.load_workbook(_modelo(conn))
    ws = wb.active
    estilo = {col: copy.copy(ws.cell(14, col)._style) for col in range(1, 20)}
    rodape = [[(cel.column, cel.value, copy.copy(cel._style)) for cel in ws[r] if cel.value] for r in (16, 17)]
    ws.delete_rows(14, ws.max_row - 13)
    for i, l in enumerate(ls):
        r = 14 + i
        for col, chave in enumerate(COLUNAS, 1):
            v = l[chave]
            if chave in EM_REAIS:
                v = v / 100
            elif chave in DATAS and v:
                v = datetime.date.fromisoformat(v)
            cel = ws.cell(r, col, v)
            cel._style = copy.copy(estilo[col])
    ultima = 13 + len(ls)
    for linha_tot, grupo in ((9, "PRÓPRIA"), (10, "CONSÓRCIO"), (11, None)):
        sel = [l for l in ls if grupo is None or l["empreita"] == grupo]
        for col, chave in zip("IJKLMN", ("pi", "va", "pi_va", "reajuste_recebido", "faturados", "saldo")):
            ws[f"{col}{linha_tot}"] = sum(l[chave] for l in sel) / 100
    ws["A9"] = len(ls)
    prop = [l for l in ls if l["empreita"] == "PRÓPRIA"]
    base = sum(l["pi_va"] for l in prop)
    ws["O9"] = sum(l["faturados"] for l in prop) / base if base else 0
    ws["P9"] = sum(l["saldo"] for l in prop) / base if base else 0
    ws["S7"] = hoje
    for k, linha in enumerate(rodape):
        for col, valor, est in linha:
            cel = ws.cell(ultima + 2 + k, col, valor)
            cel._style = est
    ws.print_area = f"A1:S{ultima + 3}"
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
```

(As fórmulas das linhas 9 e 10 do oficial, O9/P9 e os `SUMIF`, viram valores. Se o modelo trouxer fórmula em alguma célula de cabeçalho que dependa das linhas de dados, trocá-la pelo valor calculado da mesma forma.)

- [ ] **Step 4:** PASS. Abrir o arquivo gerado a partir da cópia da produção no Excel (COM invisível), exportar o PDF da página 1 e comparar com o oficial:
  - cabeçalho, larguras e formatos de número e data;
  - 22 ou 23 linhas;
  - rodapé.
- [ ] **Step 5: Commit** `feat: QDOP no leiaute oficial GL.SGI.FRP.DE.250`.

---

### Task 8.5: Rotas e tela da diretoria

**Files:**
- Create: `backend/app/api_diretoria.py`, `frontend/src/Diretoria.tsx`, `frontend/src/Diretoria.test.tsx`
- Modify: `backend/app/main.py`, `frontend/src/rota.tsx`, `frontend/src/rota.test.ts`, `frontend/src/App.tsx`
- Test: `backend/tests/test_api_diretoria.py`

**Rotas:** `GET /api/diretoria` → `diretoria.painel`; `GET /api/diretoria/qdop.xlsx` → `gerar_xlsx`, com `Content-Disposition` `GL.SGI.FRP.DE.250 - QDOP - <AAAA-MM-DD>.xlsx` e o media type do Excel. Os dois com `exigir("ver_paineis", com_csrf=False)`; a operação também vê, porque a spec não restringe a leitura.

**Tela** (antes de escrever o gráfico, carregar a skill `dataviz`; cores dos tokens):
1. **"Onde está o dinheiro"**:
   - quatro KPIs: medido esperando nota, nota esperando protocolo, protocolado esperando pagamento, recebido no mês;
   - tabela por órgão com as faixas (até 30, 31 a 60, mais de 60);
   - "Reajustes esperando apostilamento: N (o mais antigo há D dias)";
   - sem liberação, o valor do protocolado vira "a conciliar".
2. **"O mês e o ano"**: KPIs do medido no mês × previsto × mesmo mês do ano anterior e acumulado do ano; gráfico de 12 meses com barras do medido e linha do previsto.
3. **"Próximos meses"**: tabela de 6 meses com faturamento previsto e recebimento previsto.
4. **"Carteira"**:
   - saldo a executar e meses de produção no ritmo atual;
   - participação por órgão (barra horizontal simples);
   - contratos que terminam em até 6 meses.
5. **"Obras"**:
   - a tabela do QDOP com o farol (selo verde, amarelo ou vermelho) e o motivo;
   - a linha abre a obra;
   - botão "Exportar QDOP (.xlsx)".
6. **Avisos da diretoria**: o `<Alertas>` do bloco 6.

**Rotas do front:** tela `diretoria`; `/painel` abre a Diretoria. Menu: "Diretoria" (diretoria e admin). A raiz da diretoria vai para `diretoria`. `PainelGeral.tsx` sai do menu e da rota; o arquivo é apagado no bloco 9 junto com o que ele usa.

- [ ] **Step 1: Testes.**
  - API: 200 com as sete chaves; o xlsx abre no openpyxl com a S1 certa; a diretoria acessa e o usuário anônimo recebe 401.
  - Front: sem liberação mostra "a conciliar"; o botão de exportar aponta para `/api/diretoria/qdop.xlsx`; `/painel` resolve para a tela `diretoria`.
- [ ] **Step 2:** FAIL. **Step 3:** implementar. **Step 4:** PASS; `npm run build` limpo.
- [ ] **Step 5: Verificação visual** sobre cópia da produção, logado como diretoria: as cinco seções com dados reais e o QDOP exportado aberto. Conferir três obras contra o QDOP (3) oficial, anotando as diferenças esperadas (o oficial é preenchido à mão e pode estar uma medição atrás, memória "Campo Reajuste" e CONFERENCIA.md da antiga).
- [ ] **Step 6: Commit** `feat: tela da diretoria e exportacao do QDOP`.

---

### Task 8.6: Documentação, suíte, gate Sol

- [ ] **Step 1:** Runbook, seção "Diretoria e QDOP (bloco 8)":
  - as regras de cada seção;
  - o que é "prazo normal do órgão";
  - como liberar o total a receber (`geral.yaml`);
  - como trocar o modelo do QDOP (recortar do oficial novo e aplicar).

  Backlog:
  - conciliação com a controladoria (P2);
  - Rota do Oeste lote 2;
  - as diferenças da conferência com o QDOP que ficaram com o Leonardo.
- [ ] **Step 2:** suíte do backend; depois o frontend.
- [ ] **Step 3: Gate Sol** (se mantido, DT1; toca dinheiro), um round:

```bash
git diff bloco7-reajuste-prazos...bloco8-diretoria | codex exec -m gpt-5.6-sol --skip-git-repo-check "Revise este diff (FastAPI + SQLite, tela da diretoria e exportação do QDOP). Procure bugs reais de dinheiro: valor que não passa pela cota, soma que conta a mesma medição duas vezes (reprotocolo), medição cancelada somada, faixa de dias errada, total a receber que vaza com o cadastro dizendo não liberado, divisão por zero, arredondamento que não é o único do projeto. Responda em português, com arquivo:linha e cenário concreto."
```

- [ ] **Step 4: Commit** `docs: runbook e backlog do bloco 8`. Seguir para o bloco 9.

## Self-review

- **§10.5, seção 1** (dinheiro): 8.3. As faixas de dias e o grupo por órgão estão lá, com os reajustes esperando apostilamento; o "valor já medido" do reajuste ficou fora (decisão 2).
- **§10.5, seções 2 a 4:** 8.3.
- **§10.5, seção 5** (tabela no estilo QDOP com farol e motivo, clique na obra, exportação oficial): 8.3, 8.4 e 8.5.
- **Avisos da diretoria:**
  - execução vencida sem instrumento: bloco 7, público diretoria;
  - pagamento atrasado: 8.3;
  - obra paralisada: bloco 7;
  - reajuste há mais de 90 dias: bloco 7.

  Certidão não aparece: `documentos` publica só para operação.
- **"Prazo normal do órgão":** Q3, com mínimo de 10 amostras (senão 30 dias), em 8.3.
- **Total a receber condicionado à conciliação:** decisão 3 e teste da 8.3.
