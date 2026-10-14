# Bloco 2 (Espelho): gerador de espelho de NF, estados novos da medição e envio ao faturamento. Plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** a medição passa a nascer no sistema quando a pessoa gera o espelho de nota fiscal (número, competência, valores digitados), o sistema calcula uma linha por nota pela regra fiscal versionada da obra, preenche os modelos Word, guarda os arquivos e envia o e-mail ao faturamento pela conta de quem clicou, registrando o envio; obras entram por ondas, cada uma provada ao centavo contra gabaritos reais.

**Architecture:** motor puro em `app/espelho.py` (Decimal, sem banco, sem arquivo) provado contra as 14 notas de gabarito, o MT-402 23ª e os espelhos reais gravados nos modelos; `app/extenso.py` (valor por extenso); `app/espelho_docx.py` (preenche content controls de um `.docx` por `w:tag`, com lxml); a regra fiscal de cada obra mora em `cadastro/espelho/<slug>.yaml` e os modelos em `cadastro/modelos/espelho/<slug>/`, lidos por `cadastro_arquivos`, validados contra os controles reais dos modelos e gravados por `cadastro_aplicar` (regra em JSON no banco, modelos copiados por hash para a pasta de dados); `app/espelhos.py` orquestra (cria medições nos estados novos, versiona espelhos, grava arquivos, monta e envia o e-mail via `correio`); `app/api_espelhos.py` expõe; o frontend ganha `Espelho.tsx` dentro da aba Medições. A tabela `medicoes` é reconstruída uma vez (migração 020) para o CHECK aceitar os três estados novos.

**Tech Stack:** Python 3.12, FastAPI, SQLite (migrações SQL em `backend/migrations`), pytest, PyYAML, **lxml (dependência nova)** para o `.docx`, `urllib` para o Graph (já em `correio.py`), React 18 + Vite + vitest.

**Spec:** `docs/superpowers/specs/2026-09-21-reestruturacao-design.md` §2, §3 (passos 1 e 2), §4, §5.1, §5.2 (linha "Espelho ao faturamento"), §8 (`geral.yaml`, `espelho/`, `modelos/`), §12, §15, §17.2. Regras por obra: `docs/espelho-regras-por-obra-2026-09-16.md`. E-mail do espelho: `docs/mapeamento-emails-medicao-2026-09-16.md` §2. Levantamento complementar do motor antigo (fatores nas fórmulas, controles dos 61 modelos, extenso, espelhos reais): feito em 2026-09-22 e incorporado neste plano (tabelas da seção "Regra por obra").

**Status:** APROVADO pelo Leonardo em 2026-09-22 (decisões 1 a 9). **Modo de execução: nesta sessão (superpowers:executing-plans)**, sem subagente por tarefa. Branch `bloco2-espelho`. **Andamento em 2026-09-22:** Tasks 1 a 14 feitas e commitadas (verificação visual da Task 12 feita sobre cópia da produção: MT-402 24ª gerada, `.docx` baixáveis, e-mail simulado enviado, medições em `espelho_enviado`); Task 15 FEITA: suíte 706 verdes (1 falha intermitente em `test_leitura_pdf` por tempo de subprocesso sob carga, passou isolada; a branch não toca `leitura_pdf`), gate Sol 1 round (11 corrigidos, 2 refutados, 2 decisões do plano; ver backlog), **merge `--no-ff` em `master` (5d34f94) com OK do Leonardo, em PRODUÇÃO em 2026-09-22 11:53** (deploy.ps1 com frontend; backup `dashboard-PRE-BLOCO2-20260922-115227.db`; migração 020 aplicada: 629 medições, 178 documentos, FKs íntegras, sem resíduo `_nova`), **`cadastro aplicar` real às 12:00** (geral 1, espelho 7 criados, 33 modelos em `dados/modelos`, 3 regras ativas). **Bloco 2 concluído.** Desvios do texto do plano: são 33 modelos (não 27); Tasks 9 e 10 num só módulo (`espelhos.py`, dois commits); `arquivos.receber_pdf(arquivo, pasta)` recebe a pasta; nome curto da emissora no arquivo = chave do cadastro capitalizada; `geral.yaml` ganhou `{saudacao}` (Bom dia/Boa tarde pela hora de Cuiabá) e a cópia inclui as operadoras (quem envia sai da própria cópia pelo e-mail de login); `Espelho` é um cartão próprio acima de Medições em `ContratoPagina.tsx` (remonta a lista via `key`), não dentro de `Medicoes.tsx`; a evidência do órgão aparece na coluna Documentos da linha da medição com download local.

## Global Constraints

- Banco: `backend/dados/dashboard.db` é o caminho padrão de dev E de produção nesta máquina. Testes usam `tmp_path` com `DASH_DB_PATH`. **Nunca semear nem apagar o banco padrão nem o de produção (`C:\DashboardLotufo\dados\dashboard.db`).** Leitura do banco de produção só com `?mode=ro`.
- Sem custo de API: nada de serviço pago por uso, OCR ou LLM. Microsoft 365 já é da empresa.
- Dinheiro em centavos inteiros fora do motor; dentro de `espelho.py` a aritmética é `Decimal` exata com arredondamento declarado por tributo (`trunc` = `ROUND_DOWN`, `round` = `ROUND_HALF_UP`), nunca float. Histórico não sobrescrito (espelho novo = versão nova), sem exclusão física, auditoria append-only (`auditoria.registrar` dentro de `db.mutacao`).
- Toda escrita de negócio dentro de `with db.mutacao(conn):`, auditoria no mesmo commit. Falha de envio de e-mail não muda estado nenhum (padrão de `correio.enviar_e_registrar`).
- Migrações idempotentes; `ALTER TABLE ... ADD COLUMN` no começo de linha. A 020 reconstrói `medicoes` e `medicao_documentos` pela receita oficial do SQLite (criar nova, copiar, apagar, renomear) com `PRAGMA foreign_keys=OFF` no início do script e `=ON` no fim; reexecutar o script tem de dar o mesmo resultado.
- Arquivos gerados e recebidos: PDF validado por assinatura `%PDF-` e teto de 10 MB (guardas de `api_certidoes.py`), nome em disco pelo sha256, caminho gravado relativo à pasta do banco (`espelhos/<sha>.docx`, `modelos/<sha>.docx`, `evidencias/<sha>.pdf`), download só dentro da pasta (`is_relative_to`).
- O sistema NÃO lê caixa de e-mail; `correio.py` só cria rascunho, sobe anexo e envia.
- Textos de interface, erros e commits em português. Commit `tipo: descricao` sem acento no assunto, terminando com `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.
- Testes: `cd backend && .venv\Scripts\python -m pytest` (601 hoje). Teste novo em `backend/tests/test_<modulo>.py`, um teste focado por comportamento. Frontend: `cd frontend && npm test`.
- Branch `bloco2-espelho`. Merge em `master` só com OK explícito do Leonardo. Um gate Sol sobre o diff inteiro ao final (toca dinheiro, autenticação Graph e arquivo externo). Subagentes de implementação e revisão em Opus; nunca Sonnet ou Haiku.
- Regra do plano: a spec §4.3 manda que uma obra só seja gerada pelo sistema quando reproduz ao centavo os gabaritos E um espelho real recente da própria obra. Nenhuma regra fica `ativa` sem esses dois testes no repositório.

## Decisões deste plano em relação à spec

1. **Estados novos entram de verdade no CHECK de `medicoes.estado`** (`espelho_gerado`, `espelho_enviado`, `nota_emitida`), reconstruindo a tabela uma vez só na migração 020, com os estados antigos mantidos. `nota_emitida` entra no CHECK agora mas só ganha transição no bloco 3 (leitor de PDF e RM); assim o bloco 3 não reconstrói de novo. O remapeamento do legado continua no bloco 3.
2. **Valor da medição nascida do espelho** vai para `valor_protocolado_centavos` com `valor_protocolado_origem='espelho'` (valor novo no CHECK), sem congelar; o congelamento continua sendo o protocolo. Gerar de novo cria versão nova do espelho e atualiza esse valor. Painéis, CSV e casador do RM continuam lendo a mesma coluna. O valor da medição é a **soma das entradas digitadas daquela natureza** (Deciolândia digita o cheio e emite a cota: a medição guarda o cheio, como a memória `base-cheia-x-cota-consorcio` manda).
3. **Um espelho cobre a medição inteira** (execução + reajuste + projeto de um mesmo número): uma linha em `espelhos` com N saídas, ligada às medições por `espelho_medicoes`. Reajuste continua medição própria (`tipo='reajuste'`), criada junto quando a pessoa digita o valor do reajuste. O reajuste do projeto (Estações BRT) soma na medição de reajuste; a saída guarda a distinção.
4. **Protocolar continua manual neste bloco**: `registrar_protocolo` passa a aceitar `espelho_gerado` e `espelho_enviado` → `protocolada`, para a operação não ficar sem caminho entre o bloco 2 e o bloco 5. Cancelar continua possível nos dois estados novos.
5. **Gerar de novo depois de enviado não volta o estado** (estados só andam para a frente): a medição fica `espelho_enviado`, a versão nova nasce `vigente` sem `envio_id`, a tela mostra "versão N não enviada" e permite enviar de novo. Gerar de novo com medição já `protocolada` ou posterior é recusado (correção pós-protocolo é fora do escopo, spec §2).
6. **Onda 1 = MT-402, MT-401 e Cavalaria `ativa`** (gabaritos: MT-402 23ª; MT-401 32ª e Cavalaria 03ª pelos espelhos reais gravados nos modelos). **MT-388, Parque Atalaia, Integra BRT e Estações BRT entram como `prova`**: o motor as reproduz nas 14 notas de gabarito (é o teste do motor), mas a tela só oferece o espelho quando o Leonardo trocar `situacao: ativa` no YAML. As outras 12 obras são ondas seguintes, cada uma uma branch curta pela receita do runbook (Task 15). Maternidade VG e Deciolândia exigem regra nova sem gabarito confiável; ficam para o fim.
7. **IBS e CBS** são linhas informativas: o motor as calcula quando a regra da obra declara `ibs`/`cbs` (percentual, arredondamento, `vigente_desde`), a tela as mostra e o `.docx` as preenche se o modelo tiver os controles `ibs` e `cbs`; **não deduzem do líquido**. Na onda 1 os YAMLs trazem as duas chaves comentadas com `# NOTA: confirmar alíquota e redução com o faturamento` — as notas de 2026 destacam CBS 0,9% e IBS 0,1%, mas a redução aplicável à obra pública não foi conferida. Backlog.
8. **Modelos Word entram no repositório** (`cadastro/modelos/espelho/<slug>/<chave-da-saida>.docx`, copiados dos 61 do motor antigo com nome novo) e o `cadastro aplicar` copia cada um para `dados/modelos/<sha256>.docx`, gravando o hash em `espelho_regras`; a produção não lê o checkout em tempo de execução. Os textos fixos dos modelos (CNPJ, CNO, O.S., alíquota escrita) continuam responsabilidade do modelo; o sistema preenche só os controles.
9. **Rótulo do número no texto do espelho sem zero à esquerda** (`3ª`, como 58 dos 61 modelos); **no nome do arquivo com dois dígitos** (`03ª`, spec §4.4). Período sempre `01/MM/AAAA A DD/MM/AAAA` (último dia do mês); a janela fora do mês civil da SES e o "PERÍODO: MAIO/2026" fixo da Região Oeste são das ondas dessas obras (o modelo terá de ganhar o controle `periodo`).

## Estrutura de arquivos

| Arquivo | Responsabilidade |
|---|---|
| `backend/migrations/020_espelho.sql` | estados novos (rebuild de `medicoes`), `medicao_documentos` com arquivo local (rebuild), `espelhos`, `espelho_medicoes`, `envio_medicoes`, `cadastro_geral`, `espelho_regras`, `entidades.emails_faturamento` |
| `backend/app/medicoes.py` | `TRANSICOES` e `registrar_protocolo` com os estados novos; `criar_para_espelho`; `marcar_espelho_enviado` |
| `backend/app/extenso.py` | valor por extenso em reais (centavos → texto) |
| `backend/app/espelho.py` | motor: regra + entradas → saídas (valores, retenções, líquido, extenso, nome do arquivo); puro |
| `backend/app/espelho_docx.py` | `controles(docx_bytes) -> set[str]`, `preencher(docx_bytes, valores) -> bytes` |
| `backend/app/cadastro_arquivos.py` | lê e valida `geral.yaml`, `espelho/*.yaml`, `emails_faturamento`; confere modelos e controles |
| `backend/app/cadastro_aplicar.py` | grava `cadastro_geral`, `espelho_regras`, copia modelos, `entidades.emails_faturamento` |
| `backend/app/arquivos.py` | guardas de arquivo extraídas de `api_certidoes.py` (pasta, sha, PDF válido) + `gravar_bytes` |
| `backend/app/espelhos.py` | serviço: prévia, gerar (versões, medições, arquivos), prévia do e-mail, enviar |
| `backend/app/api_espelhos.py` | rotas `/api/contratos/{id}/espelho*`, `/api/espelhos/{id}*`, `/api/medicoes/{id}/documentos` |
| `backend/app/cli.py` | relatório do `cadastro aplicar` com `geral` e `espelho` |
| `cadastro/geral.yaml`, `cadastro/espelho/*.yaml`, `cadastro/modelos/espelho/**` | fonte de verdade (Task 8) |
| `frontend/src/Espelho.tsx` (+ `.test.tsx`) | gerar espelho, prévia por nota, versões, prévia e envio do e-mail |
| `frontend/src/Medicoes.tsx`, `tokens.css` | rótulos, cores e transições dos estados novos; monta `Espelho` |
| `docs/runbook.md`, `docs/backlog.md` | receita "espelho por onda", operação |

## Esquema da regra fiscal (`cadastro/espelho/<slug>.yaml`)

Uma obra, um arquivo; `slug` = `cadastro_arquivos.slug(nome_curto)` do contrato correspondente. Estrutura (todos os percentuais e fatores são TEXTO com vírgula decimal, lidos com `Decimal`):

```yaml
# MT-388 — 4 notas por medição: 2 municípios × (medição, reajuste). Fatores conferidos nas
# fórmulas da planilha-motor em 2026-09-22 (T3=TRUNC(36184/43444;4)=0,8328; Porto = resto).
contrato: MT-388                    # nome_curto do contrato
situacao: prova                     # prova | ativa  (só `ativa` aparece na tela)
entradas:                           # o que a pessoa digita, nesta ordem
  - {chave: medicao,  rotulo: Valor da medição, natureza: medicao}
  - {chave: reajuste, rotulo: Valor do reajuste, natureza: reajuste}
parcelas:                           # divisões nomeadas, calculadas na ordem
  - {chave: med-caceres,  de: medicao,  fator: '0,8328', arredondamento: round}
  - {chave: med-porto,    de: medicao,  resto_de: [med-caceres]}
  - {chave: reaj-caceres, de: reajuste, fator: '0,8328', arredondamento: round}
  - {chave: reaj-porto,   de: reajuste, resto_de: [reaj-caceres]}
retencoes:                          # padrão da obra; cada saída pode sobrescrever chave a chave
  mao_de_obra: {percentual: '40', arredondamento: trunc}
  material:    {modo: diferenca}    # ou {modo: produto, percentual: '60', arredondamento: trunc}
  inss:        {percentual: '11', base: mao_de_obra, arredondamento: trunc}
  iss:         {percentual: '5',  base: mao_de_obra, arredondamento: trunc, deduz_liquido: false}
  irrf:        {percentual: '1,2', base: total, arredondamento: trunc}
  # ibs:       {percentual: '0,1', base: total, arredondamento: round, vigente_desde: '2026-01-01'}
  # cbs:       {percentual: '0,9', base: total, arredondamento: round, vigente_desde: '2026-01-01'}
saidas:                             # uma por nota; valor zero não emite
  - chave: caceres-medicao
    natureza: medicao               # medicao | reajuste | projeto  (Natureza do nome do arquivo)
    valor: med-caceres              # chave de entrada ou parcela, ou lista (soma)
    emissor: lotufo                 # chave em entidades.yaml
    municipio: Cáceres
    retencoes: {iss: {base: material}}   # sobrescreve só o que declara
    modelo: caceres-medicao.docx    # em cadastro/modelos/espelho/mt-388/
  - {chave: porto-medicao,   natureza: medicao,  valor: med-porto,    emissor: lotufo, municipio: Porto Esperidião, modelo: porto-medicao.docx}
  - {chave: caceres-reajuste, natureza: reajuste, valor: reaj-caceres, emissor: lotufo, municipio: Cáceres, retencoes: {iss: {base: material}}, modelo: caceres-reajuste.docx}
  - {chave: porto-reajuste,  natureza: reajuste, valor: reaj-porto,   emissor: lotufo, municipio: Porto Esperidião, modelo: porto-reajuste.docx}
```

Regras do esquema (o validador as impõe):
- `chave` de entrada, parcela e saída: `^[a-z0-9][a-z0-9-]{1,40}$`, únicas no arquivo. `de` e `valor` referenciam entrada ou parcela já declarada (ordem importa). Parcela tem exatamente um de `fator`, `fracao: [numerador, denominador]` ou `resto_de` (lista de parcelas irmãs com o mesmo `de`).
- `retencoes`: `mao_de_obra` pode ser `null` (projeto: sem desdobramento; então `material` não existe e `base: mao_de_obra` é erro). `inss`/`irrf`/`ibs`/`cbs` podem ser `null` (não há). `iss.base` ∈ {`mao_de_obra`, `material`, `total`}. `arredondamento` ∈ {`trunc`, `round`}. `deduz_liquido` só em `iss` (padrão `true`).
- Saída opcional `rotulo` (ex.: `Reajuste do Projeto`) entra no nome do arquivo no lugar da Natureza quando duas saídas da mesma natureza e mesmo emissor/município colidiriam.
- `modelo` tem de existir em `cadastro/modelos/espelho/<slug>/` e seus controles (`w:tag`) têm de cobrir os campos que a saída produz entre `valor, mo, material, inss, iss, irrf, valor_extenso, medicao, periodo` (erro); `ibs`/`cbs` ausentes no modelo geram aviso.
- Cálculo (Task 4): `valor_saida = Σ valor` → `mo = arred(valor × p_mo)` → `material = valor − mo` (ou `arred(valor × p_mat)` em `produto`) → `inss = arred(base × p)` → `iss` → `irrf` → `ibs` → `cbs` → `liquido = valor − inss − irrf − (iss se deduz_liquido)`. Extenso sobre `valor`. Saída com `valor ≤ 0` não emite.

## Regra por obra (dados para os YAMLs da Task 8, conferidos nas fórmulas das planilhas-motor)

| Obra | Entradas | Parcelas | Retenções (MO / INSS / ISS / IRRF) | Saídas (emissor · município) | Gabarito |
|---|---|---|---|---|---|
| MT-402 | medicao, reajuste | — | 40 trunc / 11 trunc / 5 s/MO trunc / 1,2 **round** | 2: Lotufo · Cuiabá | 23ª: 278.509,92 → 111.403,96 · 167.105,96 · 12.254,43 · 5.570,19 · **3.342,12**; reaj 19.580,95 → 7.832,38 · 11.748,57 · 861,56 · 391,61 · 234,97 |
| MT-401 | idem | — | idem (IRRF round) | 2 | 32ª: 985.375,86 → 394.150,34 · 591.225,52 · 43.356,53 · 19.707,51 · 11.824,51; reaj 133.083,30 → 53.233,32 · 79.849,98 · 5.855,66 · 2.661,66 · 1.597,00 |
| Cavalaria | idem | — | 40 trunc / 11 trunc / 5 trunc / 1,2 trunc | 2 | 03ª: 584.463,68 → 233.785,47 · 350.678,21 · 25.716,40 · 11.689,27 · 7.013,56; reaj 103.099,39 → 41.239,75 · 61.859,64 · 4.536,37 · 2.061,98 · 1.237,19 |
| MT-388 | medicao, reajuste | fator 0,8328 round (Cáceres), resto (Porto) | 40 trunc / 11 trunc / 5 trunc (**Cáceres: base material**) / 1,2 trunc; `deduz_liquido: false` | 4: Lotufo · Cáceres, Porto Esperidião | 10ª (634.529,58; 38.655,83): as 4 linhas da tabela §6 do doc de regras |
| Parque Atalaia | medicao, reajuste (cheio) | `cba = trunc(× 0,5872)`, `vg = resto`; por município `lotufo = trunc(× 0,8)`, `rivoli = resto` | 40 trunc / 11 trunc / 5 trunc / 1,2 trunc | 8: Lotufo e Rivoli · Cuiabá, Várzea Grande | 43ª (780.224,80; 623.268,84): 4 linhas Lotufo do doc §6 + Rivoli CBA 91.629,60 → 36.651,84 · 54.977,76 · 4.031,70 · 1.832,59 · 1.099,55 |
| Integra BRT | medicao (execução), projeto | exec: `cba = trunc(× 6740/7820)`, `vg = resto`; por município `lotufo = round(× 0,49)`, `guaxe = round(× 0,49)`, `encomind = resto`; projeto: sem município, mesmas cotas sobre o total | exec: 40 trunc / 11 trunc / 5 trunc / 1,2 trunc; projeto: `mao_de_obra: null`, `inss: null`, ISS 5 s/total trunc, IRRF **4,8** trunc; projeto Guaxe (Tangará) `iss: null` | 9: 6 exec (3 emissores × CBA, VG) + 3 projeto (Lotufo · Cuiabá, Guaxe · Tangará da Serra, Encomind · Cuiabá) | 10ª exec 7.382.048,52 → Lotufo CBA 3.117.641,10 · 1.247.056,44 · 1.870.584,66 · 137.176,20 · 62.352,82 · 37.411,69; Lotufo VG 499.562,67 · 199.825,06 · 299.737,61 · 21.980,75 · 9.991,25 · 5.994,75; projeto 7.522,08 → ISS 376,10 · IRRF 361,05 |
| Estações BRT | medicao, projeto, reajuste, reajuste-projeto (natureza reajuste, rotulo `Reajuste do Projeto`) | `cba = trunc(× 61/81)`, `vg = resto` (medicao e reajuste); projeto sem rateio | exec: 40 trunc / 11 trunc / 5 trunc / 1,2 trunc; projeto: sem MO/INSS, ISS 5 s/total trunc, IRRF 4,8 trunc | 6: exec CBA, exec VG, reaj CBA, reaj VG, projeto CBA, reaj-projeto CBA (Lotufo) | 3ª (3.198.742,98; 202.800,30): 4 linhas do doc §6; projeto 937.803,58 → ISS 46.890,17 · IRRF 45.014,57 |
| Complexo Leblon (onda seguinte) | medicao, reajuste | `lotufo = round(× 0,5)`, `rivoli = resto` | 40 trunc / 11 **round** / 5 **round** / 1,2 **round** | 4 | reaj 476.449,03 → Lotufo 238.224,52, Rivoli 238.224,51 |
| MTPAR (5 obras, onda seguinte) | medicao, reajuste (Granito só medicao) | — | 40 trunc / 11 round / 5 round / **1,5** round | 2 (Granito 1) | Cultural 20ª 1.742.098,79 → 696.839,51 · 1.045.259,28 · 76.652,35 · 34.841,98 · 26.131,48 |
| 5 Bairros | medicao, reajuste | — | 40 trunc / 11 trunc / 5 trunc / 1,2 round | 2 | 30ª 395.291,44 → 158.116,57 · 237.174,87 · 17.392,82 · 7.905,82 · 4.743,50 |
| Região Oeste | idem | — | tudo trunc | 2 (modelo de medição sem `valor_extenso` nem `periodo`) | 50ª 184.360,14 → 73.744,05 · 110.616,09 · 8.111,84 · 3.687,20 · 2.212,32 |
| Alta Floresta (SES) | medicao, reequilibrio-iss (natureza medicao), reajuste, reequilibrio-iss-reajuste (natureza reajuste) | — | **60** trunc / `inss: null` / 5 s/MO trunc / 1,2 trunc | 2 (valor = soma das duas entradas) | 42ª 56.009,69 → 33.605,81 · 22.403,88 · — · 1.680,29 · 672,11 |
| Coxipó 2ª, Coxipó 3ª (SUDECO, FONTE 100, reajuste), Deciolândia (cota 0,3333 round; material `produto` 60; sem IRRF; ISS destacado, `deduz_liquido: false`), Maternidade VG (ISS 2% s/ total, regra nova) | ondas seguintes | | | | Coxipó 3ª FONTE 100 354.184,69 → 141.673,88 · 212.510,81 · 15.584,13 · 7.083,69 · 4.250,22 |

Controles dos modelos (`w:tag` = `w:alias`; os ids 5001–5010/5030 são `w:id`): `valor`, `mo`, `material`, `inss`, `iss`, `irrf`, `valor_extenso`, `medicao` (2 ou 3 ocorrências), `periodo`. Moeda no controle: `1.234,56` sem `R$` (o `R$` é texto fixo). Extenso em CAIXA ALTA. O líquido não é impresso em modelo nenhum.

---

### Task 1: Migração 020 — estados novos, espelhos, envios ligados a medições

**Files:**
- Create: `backend/migrations/020_espelho.sql`
- Test: `backend/tests/test_migracao_020.py`

**Interfaces:**
- Consumes: `db.migrate(conn)`, `db._sem_alters_ja_aplicados(conn, sql)`, `db.MIGRATIONS_DIR`.
- Produces: tabelas `espelhos`, `espelho_medicoes`, `envio_medicoes`, `cadastro_geral`, `espelho_regras`; `medicoes.estado` aceita `espelho_gerado|espelho_enviado|nota_emitida`; `medicoes.valor_protocolado_origem` aceita `espelho`; `medicao_documentos.tipo_doc` aceita `espelho|evidencia_orgao`, colunas `arquivo`, `sha256`, `tamanho`, `espelho_id`, `saida`; `entidades.emails_faturamento TEXT` (JSON).

- [ ] **Step 1: Escrever o teste da migração (falha porque a 020 não existe)**

```python
# backend/tests/test_migracao_020.py
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


def _semear_filhas(conn):
    """Contrato + medicao legada + uma linha em cada tabela filha de medicoes."""
    conn.execute("INSERT INTO contratos (orgao, numero_instrumento, objeto, valor_original_centavos) "
                 "VALUES ('SINFRA','X/2026','obra',100)")
    conn.execute("INSERT INTO medicoes (contrato_id, numero, tipo, competencia, estado) "
                 "VALUES (1, 1, 'execucao', '2026-05', 'protocolada')")
    conn.execute("INSERT INTO medicao_protocolos (medicao_id, data, origem) VALUES (1,'2026-06-01','manual')")
    conn.execute("INSERT INTO medicao_documentos (medicao_id, fonte, tipo_doc, nome, item_id) "
                 "VALUES (1,'controladoria_sp','nf','NF 1.pdf','item-1')")
    conn.commit()


def test_estados_novos_e_origem_espelho_sao_aceitos(conn):
    conn.execute("INSERT INTO contratos (orgao, numero_instrumento, objeto, valor_original_centavos) "
                 "VALUES ('SINFRA','X/2026','obra',100)")
    for estado in ("espelho_gerado", "espelho_enviado", "nota_emitida", "prevista"):
        conn.execute("INSERT INTO medicoes (contrato_id, numero, tipo, competencia, estado, "
                     "valor_protocolado_centavos, valor_protocolado_origem) VALUES (1,?, 'execucao','2026-05',?,100,'espelho')",
                     (len(estado), estado))
    assert conn.execute("SELECT COUNT(*) FROM medicoes").fetchone()[0] == 4


def test_filhas_de_medicoes_sobrevivem_a_reexecucao_do_script(conn):
    _semear_filhas(conn)
    sql = (db.MIGRATIONS_DIR / "020_espelho.sql").read_text(encoding="utf-8")
    conn.executescript(db._sem_alters_ja_aplicados(conn, sql))
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    assert conn.execute("SELECT estado FROM medicoes WHERE id=1").fetchone()[0] == "protocolada"
    assert conn.execute("SELECT COUNT(*) FROM medicao_protocolos WHERE medicao_id=1").fetchone()[0] == 1
    assert conn.execute("SELECT tipo_doc FROM medicao_documentos WHERE medicao_id=1").fetchone()[0] == "nf"
    # a FK das filhas continua apontando para `medicoes`, nao para a tabela temporaria
    ddl = conn.execute("SELECT sql FROM sqlite_master WHERE name='medicao_protocolos'").fetchone()[0]
    assert "REFERENCES medicoes(id)" in ddl and "medicoes_nova" not in ddl


def test_tabelas_e_colunas_novas(conn):
    assert {"arquivo", "sha256", "tamanho", "espelho_id", "saida"} <= _colunas(conn, "medicao_documentos")
    assert {"contrato_id", "numero", "competencia", "versao", "situacao", "entradas", "saidas",
            "regra_sha256", "criado_por", "envio_id", "motivo"} <= _colunas(conn, "espelhos")
    assert {"espelho_id", "medicao_id"} <= _colunas(conn, "espelho_medicoes")
    assert {"envio_id", "medicao_id"} <= _colunas(conn, "envio_medicoes")
    assert {"chave", "valor"} <= _colunas(conn, "cadastro_geral")
    assert {"contrato_id", "situacao", "regra", "modelos", "sha256"} <= _colunas(conn, "espelho_regras")
    assert "emails_faturamento" in _colunas(conn, "entidades")
    conn.execute("INSERT INTO medicao_documentos (medicao_id, fonte, tipo_doc, nome, item_id) "
                 "SELECT 1,'sistema','espelho','x.docx','abc' WHERE 0")  # so' valida o CHECK no parse
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `cd backend && .venv\Scripts\python -m pytest tests/test_migracao_020.py -v`
Expected: FAIL (`no such file` na leitura da 020 e CHECK recusando `espelho_gerado`).

- [ ] **Step 3: Escrever a migração**

```sql
-- 020: espelho de NF (bloco 2). Reconstroi `medicoes` UMA vez para o CHECK de estado aceitar
-- espelho_gerado/espelho_enviado (este bloco) e nota_emitida (bloco 3), e `valor_protocolado_origem`
-- aceitar 'espelho'. Receita oficial do SQLite (lang_altertable, "Making Other Kinds Of Table Schema
-- Changes"): criar nova, copiar, apagar a antiga, renomear. foreign_keys OFF so' durante o script:
-- as 4 filhas (medicao_protocolos, nf_alocacoes, mensagens_observadas, medicao_documentos)
-- referenciam `medicoes` pelo NOME e voltam a valer quando a nova assume o nome.
-- Reexecutar este script produz o mesmo resultado (a nova e' recriada e recopiada).
PRAGMA foreign_keys=OFF;

CREATE TABLE IF NOT EXISTS medicoes_nova (
    id INTEGER PRIMARY KEY,
    contrato_id INTEGER NOT NULL REFERENCES contratos(id),
    numero INTEGER NOT NULL CHECK (numero >= 1),
    tipo TEXT NOT NULL CHECK (tipo IN ('execucao','projeto','reajuste')),
    competencia TEXT NOT NULL CHECK (competencia GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]'),
    estado TEXT NOT NULL DEFAULT 'prevista'
        CHECK (estado IN ('prevista','espelho_gerado','espelho_enviado','nota_emitida',
                          'protocolada','nf_emitida','recebida','cancelada','desistida')),
    valor_protocolado_centavos INTEGER CHECK (valor_protocolado_centavos >= 0),
    valor_protocolado_origem TEXT CHECK (valor_protocolado_origem IN ('detectado','aceito','manual','espelho')),
    valor_atestado_centavos INTEGER CHECK (valor_atestado_centavos >= 0),
    valor_atestado_origem TEXT CHECK (valor_atestado_origem IN ('detectado','aceito','manual')),
    motivo_represamento TEXT,
    congelada INTEGER NOT NULL DEFAULT 0,
    criado_em TEXT NOT NULL DEFAULT (datetime('now')),
    atestado_em TEXT,
    nf_emitida_em TEXT,
    recebida_em TEXT,
    espelho_em TEXT,
    espelho_origem TEXT CHECK (espelho_origem IN ('detectado','aceito','manual')),
    UNIQUE (contrato_id, numero, tipo)
);
INSERT INTO medicoes_nova (id, contrato_id, numero, tipo, competencia, estado, valor_protocolado_centavos,
    valor_protocolado_origem, valor_atestado_centavos, valor_atestado_origem, motivo_represamento,
    congelada, criado_em, atestado_em, nf_emitida_em, recebida_em, espelho_em, espelho_origem)
  SELECT id, contrato_id, numero, tipo, competencia, estado, valor_protocolado_centavos,
    valor_protocolado_origem, valor_atestado_centavos, valor_atestado_origem, motivo_represamento,
    congelada, criado_em, atestado_em, nf_emitida_em, recebida_em, espelho_em, espelho_origem
  FROM medicoes;
DROP TABLE medicoes;
ALTER TABLE medicoes_nova RENAME TO medicoes;

-- Espelho: uma linha por (contrato, numero, competencia, versao). Cobre execucao + reajuste +
-- projeto do mesmo numero; as saidas (uma por nota) ficam em JSON, os arquivos em medicao_documentos.
CREATE TABLE IF NOT EXISTS espelhos (
    id INTEGER PRIMARY KEY,
    contrato_id INTEGER NOT NULL REFERENCES contratos(id),
    numero INTEGER NOT NULL,
    competencia TEXT NOT NULL,
    versao INTEGER NOT NULL,
    situacao TEXT NOT NULL CHECK (situacao IN ('vigente','substituido')),
    entradas TEXT NOT NULL,            -- JSON {chave: centavos}
    saidas TEXT NOT NULL,              -- JSON [espelho.Saida]
    regra_sha256 TEXT NOT NULL,
    criado_por INTEGER NOT NULL REFERENCES usuarios(id),
    criado_em TEXT NOT NULL DEFAULT (datetime('now')),
    substituido_em TEXT,
    motivo TEXT,
    envio_id INTEGER REFERENCES envios(id),
    UNIQUE (contrato_id, numero, competencia, versao)
);
CREATE TABLE IF NOT EXISTS espelho_medicoes (
    espelho_id INTEGER NOT NULL REFERENCES espelhos(id),
    medicao_id INTEGER NOT NULL REFERENCES medicoes(id),
    PRIMARY KEY (espelho_id, medicao_id)
);
CREATE TABLE IF NOT EXISTS envio_medicoes (
    envio_id INTEGER NOT NULL REFERENCES envios(id),
    medicao_id INTEGER NOT NULL REFERENCES medicoes(id),
    PRIMARY KEY (envio_id, medicao_id)
);

-- medicao_documentos passa a aceitar arquivo LOCAL (espelho gerado, evidencia do orgao), com hash.
-- Reconstruida pelo mesmo motivo (CHECK de tipo_doc). item_id continua NOT NULL: para arquivo local
-- e' o proprio sha256 (UNIQUE medicao_id+item_id = dedup natural).
CREATE TABLE IF NOT EXISTS medicao_documentos_nova (
    id INTEGER PRIMARY KEY,
    medicao_id INTEGER NOT NULL REFERENCES medicoes(id),
    fonte TEXT NOT NULL,               -- 'engenharia_sp' | 'controladoria_sp' | 'sistema' | 'operacao'
    tipo_doc TEXT NOT NULL CHECK (tipo_doc IN ('nf','nfs','fatura','espelho','evidencia_orgao')),
    nome TEXT NOT NULL,
    numero_nf TEXT,
    consorciada TEXT,
    municipio TEXT,
    item_id TEXT NOT NULL,
    weblink TEXT,
    arquivo TEXT,                      -- relativo a pasta do banco: 'espelhos/<sha>.docx'
    sha256 TEXT,
    tamanho INTEGER,
    espelho_id INTEGER REFERENCES espelhos(id),
    saida TEXT,                        -- chave da saida da regra
    criado_em TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (medicao_id, item_id)
);
INSERT INTO medicao_documentos_nova (id, medicao_id, fonte, tipo_doc, nome, numero_nf, consorciada,
    municipio, item_id, weblink, criado_em)
  SELECT id, medicao_id, fonte, tipo_doc, nome, numero_nf, consorciada, municipio, item_id, weblink, criado_em
  FROM medicao_documentos;
DROP TABLE medicao_documentos;
ALTER TABLE medicao_documentos_nova RENAME TO medicao_documentos;
CREATE INDEX IF NOT EXISTS idx_medicao_documentos_medicao ON medicao_documentos (medicao_id);

-- Cadastro geral (geral.yaml) e regra fiscal por obra (espelho/<slug>.yaml), gravados por
-- `cadastro aplicar`. `modelos` = JSON {chave_saida: {arquivo: 'modelos/<sha>.docx', sha256}}.
CREATE TABLE IF NOT EXISTS cadastro_geral (
    chave TEXT PRIMARY KEY,
    valor TEXT NOT NULL,
    atualizado_em TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS espelho_regras (
    contrato_id INTEGER PRIMARY KEY REFERENCES contratos(id),
    situacao TEXT NOT NULL CHECK (situacao IN ('prova','ativa')),
    regra TEXT NOT NULL,
    modelos TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    atualizado_em TEXT NOT NULL DEFAULT (datetime('now'))
);
ALTER TABLE entidades ADD COLUMN emails_faturamento TEXT;

PRAGMA foreign_keys=ON;
```

- [ ] **Step 4: Rodar o teste e a suíte inteira**

Run: `cd backend && .venv\Scripts\python -m pytest tests/test_migracao_020.py -v` → PASS (3). Depois `.venv\Scripts\python -m pytest -q` → 604 passed. Se a reexecução falhar em `foreign_key_check`, o `PRAGMA foreign_keys=OFF` não teve efeito por transação aberta: garantir que `db.migrate` chama `executescript` com a conexão sem transação (ele chama; `executescript` faz COMMIT antes).

- [ ] **Step 5: Commit**

```bash
git add backend/migrations/020_espelho.sql backend/tests/test_migracao_020.py
git commit -m "feat: migracao 020 - estados do espelho, espelhos, envio_medicoes e regras fiscais"
```

---

### Task 2: Estados novos em `medicoes.py` e o que enumera estados

**Files:**
- Modify: `backend/app/medicoes.py:18-25` (`TRANSICOES`), `:131-185` (`registrar_protocolo`), fim do arquivo (funções novas)
- Modify: `backend/app/paineis.py:214` e `:222-239`
- Modify: `frontend/src/Medicoes.tsx:69-105`, `frontend/src/tokens.css:545-548`
- Test: `backend/tests/test_medicoes.py` (acrescentar), `backend/tests/test_paineis.py` (acrescentar)

**Interfaces:**
- Produces: `medicoes.criar_para_espelho(conn, usuario_id, contrato_id, numero, tipo, competencia, valor_centavos) -> int` (cria em `espelho_gerado` com `valor_protocolado_origem='espelho'`, ou atualiza o valor se já existe em `espelho_gerado`/`espelho_enviado`; recusa outros estados); `medicoes.marcar_espelho_enviado(conn, usuario_id, medicao_id) -> None` (só `espelho_gerado` → `espelho_enviado`; já enviado é no-op). `registrar_protocolo` aceita `espelho_gerado`/`espelho_enviado` → `protocolada`.

- [ ] **Step 1: Testes que falham**

Acrescentar em `backend/tests/test_medicoes.py` (usar as fixtures do arquivo; conferir o nome do helper que cria contrato+medição — o arquivo já tem um; se criar contrato direto, usar `INSERT INTO contratos (orgao, numero_instrumento, objeto, valor_original_centavos)`):

```python
def test_criar_para_espelho_nasce_em_espelho_gerado_com_valor(conn_medicao):
    conn, usuario_id, contrato_id = conn_medicao
    mid = medicoes.criar_para_espelho(conn, usuario_id, contrato_id, 7, "execucao", "2026-05", 27850992)
    m = medicoes.detalhe(conn, mid)
    assert (m["estado"], m["valor_protocolado_centavos"], m["valor_protocolado_origem"], m["congelada"]) == \
        ("espelho_gerado", 27850992, "espelho", 0)


def test_criar_para_espelho_de_novo_atualiza_o_valor_e_recusa_protocolada(conn_medicao):
    conn, usuario_id, contrato_id = conn_medicao
    mid = medicoes.criar_para_espelho(conn, usuario_id, contrato_id, 7, "execucao", "2026-05", 100)
    assert medicoes.criar_para_espelho(conn, usuario_id, contrato_id, 7, "execucao", "2026-05", 200) == mid
    assert medicoes.detalhe(conn, mid)["valor_protocolado_centavos"] == 200
    medicoes.registrar_protocolo(conn, usuario_id, mid, "2026-06-10", "CT-1", None, "manual")
    with pytest.raises(ValueError, match="protocolada"):
        medicoes.criar_para_espelho(conn, usuario_id, contrato_id, 7, "execucao", "2026-05", 300)


def test_protocolo_a_partir_de_espelho_enviado_congela(conn_medicao):
    conn, usuario_id, contrato_id = conn_medicao
    mid = medicoes.criar_para_espelho(conn, usuario_id, contrato_id, 8, "execucao", "2026-05", 100)
    medicoes.marcar_espelho_enviado(conn, usuario_id, mid)
    medicoes.marcar_espelho_enviado(conn, usuario_id, mid)          # idempotente
    assert medicoes.detalhe(conn, mid)["estado"] == "espelho_enviado"
    medicoes.registrar_protocolo(conn, usuario_id, mid, "2026-06-10", "CT-2", None, "manual")
    m = medicoes.detalhe(conn, mid)
    assert (m["estado"], m["congelada"]) == ("protocolada", 1)
    with pytest.raises(ValueError):
        medicoes.mudar_estado(conn, usuario_id, mid, "espelho_enviado", None)   # nao volta
```

Fixture `conn_medicao`: se não existir no arquivo, criar no topo dele:

```python
@pytest.fixture
def conn_medicao(tmp_path, monkeypatch):
    monkeypatch.setenv("DASH_DB_PATH", str(tmp_path / "t.db"))
    conn = db.get_conn(); db.migrate(conn)
    uid = auth.criar_usuario(conn, "U", "u@lotufo.com", "senha-forte-123", "admin")
    conn.execute("UPDATE certidao_tipos SET aplicavel_por_padrao=0"); conn.commit()
    cur = conn.execute("INSERT INTO contratos (orgao, numero_instrumento, objeto, valor_original_centavos) "
                       "VALUES ('SINFRA','019/2024','MT-402',100)")
    conn.commit()
    yield conn, uid, cur.lastrowid
    conn.close()
```

Em `backend/tests/test_paineis.py`, acrescentar:

```python
def test_medicao_em_espelho_aparece_como_pendencia_de_protocolo(conn_painel):
    conn, uid, cid = conn_painel
    medicoes.criar_para_espelho(conn, uid, cid, 9, "execucao", "2026-05", 100)
    p = paineis.painel_engenharia(conn)           # usar o nome real da funcao que monta `pendencias`
    tipos = {x["tipo_pendencia"] for x in p["pendencias"]}
    assert "espelho_sem_protocolo" in tipos
```

(Conferir em `paineis.py:200-244` o nome da função e a fixture existente do arquivo; adaptar a fixture, não a asserção.)

- [ ] **Step 2: Rodar e ver falhar** — `pytest tests/test_medicoes.py tests/test_paineis.py -q` → 4 falhas (`AttributeError: criar_para_espelho`).

- [ ] **Step 3: Implementar em `medicoes.py`**

Trocar `TRANSICOES`:

```python
TRANSICOES = {
    "prevista": {"cancelada", "desistida"},
    # Estados do espelho (spec 2026-09-21 §2). espelho_gerado -> espelho_enviado e' do SISTEMA
    # (marcar_espelho_enviado, no ato do envio); -> protocolada e' registrar_protocolo.
    "espelho_gerado": {"cancelada"},
    "espelho_enviado": {"cancelada"},
    "nota_emitida": {"cancelada"},          # transicoes para ca' entram no bloco 3
    "protocolada": {"nf_emitida", "cancelada", "desistida"},
    "nf_emitida": {"recebida", "cancelada", "desistida"},
    "recebida": set(), "cancelada": set(), "desistida": set(),
}
ESTADOS_ESPELHO = ("espelho_gerado", "espelho_enviado")
```

Em `registrar_protocolo`, trocar o bloco `if atual == "prevista": ... else: ...` por:

```python
        if atual in ("prevista", *ESTADOS_ESPELHO, "nota_emitida"):
            upd = conn.execute(
                "UPDATE medicoes SET estado='protocolada', congelada=1 WHERE id=? AND estado=?",
                (medicao_id, atual))
        else:
            upd = conn.execute("UPDATE medicoes SET congelada=1 WHERE id=? AND estado=?",
                               (medicao_id, atual))
```

Acrescentar ao fim do arquivo:

```python
def criar_para_espelho(conn, usuario_id: int, contrato_id: int, numero: int, tipo: str,
                       competencia: str, valor_centavos: int) -> int:
    """A medicao nasce ao gerar o espelho (spec §2). Gerar de novo atualiza o valor enquanto a
    medicao nao foi protocolada; depois disso correcao e' fora do escopo (nao ha' glosa pos-protocolo)."""
    with db.mutacao(conn):
        ja = conn.execute("SELECT id, estado, valor_protocolado_centavos FROM medicoes "
                          "WHERE contrato_id=? AND numero=? AND tipo=?", (contrato_id, numero, tipo)).fetchone()
        if ja is None:
            cur = conn.execute(
                "INSERT INTO medicoes (contrato_id, numero, tipo, competencia, estado, "
                "valor_protocolado_centavos, valor_protocolado_origem) VALUES (?,?,?,?,'espelho_gerado',?,'espelho')",
                (contrato_id, numero, tipo, competencia, valor_centavos))
            auditoria.registrar(conn, usuario_id, "medicao.criar", "medicao", cur.lastrowid, None,
                                {"numero": numero, "tipo": tipo, "competencia": competencia,
                                 "estado": "espelho_gerado", "valor_protocolado_centavos": valor_centavos})
            return cur.lastrowid
        if ja["estado"] not in ESTADOS_ESPELHO:
            raise ValueError(f"Medição {numero} ({tipo}) já está {ja['estado']}: o espelho não pode ser "
                             "gerado de novo depois de protocolada")
        cur = conn.execute("UPDATE medicoes SET valor_protocolado_centavos=?, competencia=? "
                           "WHERE id=? AND estado IN ('espelho_gerado','espelho_enviado')",
                           (valor_centavos, competencia, ja["id"]))
        if cur.rowcount != 1:
            raise ValueError("Estado da medição mudou concorrentemente; tente novamente")
        auditoria.registrar(conn, usuario_id, "medicao.valor_protocolado", "medicao", ja["id"],
                            {"valor_protocolado_centavos": ja["valor_protocolado_centavos"]},
                            {"valor_protocolado_centavos": valor_centavos, "valor_protocolado_origem": "espelho"})
        return ja["id"]


def marcar_espelho_enviado(conn, usuario_id: int, medicao_id: int) -> None:
    """Transicao do SISTEMA no ato do envio ao faturamento. Ja' enviado: nada a fazer."""
    with db.mutacao(conn):
        cur = conn.execute("UPDATE medicoes SET estado='espelho_enviado' WHERE id=? AND estado='espelho_gerado'",
                           (medicao_id,))
        if cur.rowcount == 1:
            auditoria.registrar(conn, usuario_id, "medicao.estado", "medicao", medicao_id,
                                {"estado": "espelho_gerado"}, {"estado": "espelho_enviado"})
```

- [ ] **Step 4: `paineis.py`** — na linha 214 trocar a lista por `m.estado IN ('prevista','espelho_gerado','espelho_enviado','protocolada','nf_emitida')`; antes do `else:  # nf_emitida` (linha 235) inserir:

```python
        elif m["estado"] in ("espelho_gerado", "espelho_enviado"):
            pendencias.append({**base, "tipo_pendencia": "espelho_sem_protocolo",
                               "mensagem": ("espelho gerado, aguardando nota e protocolo" if m["estado"] == "espelho_gerado"
                                            else "espelho enviado ao faturamento, aguardando nota e protocolo")})
```

- [ ] **Step 5: Frontend** — em `Medicoes.tsx`: `ROTULO_ESTADO` ganha `espelho_gerado: "Espelho gerado", espelho_enviado: "Espelho enviado", nota_emitida: "Nota emitida"`; `PROXIMOS` ganha `espelho_gerado: ["cancelada"], espelho_enviado: ["cancelada"]`; na regra de edição de valor (`:360-362`) o valor protocolado NÃO é editável à mão em `espelho_gerado`/`espelho_enviado` (vem do espelho). Em `tokens.css:545-548` acrescentar `.estado--espelho_gerado .estado__ponto` e `.estado--espelho_enviado .estado__ponto` com a mesma cor de `prevista` e de `protocolada`, respectivamente.

- [ ] **Step 6: Rodar** — `pytest -q` → verde (607); `cd frontend && npm test` → verde; `npx tsc --noEmit` sem erro.

- [ ] **Step 7: Commit** — `git commit -m "feat: medicao nasce em espelho_gerado e protocola a partir dos estados do espelho"`

---

### Task 3: Valor por extenso

**Files:**
- Create: `backend/app/extenso.py`
- Test: `backend/tests/test_extenso.py`

**Interfaces:**
- Produces: `extenso.reais(centavos: int) -> str` (minúsculas, com acento; quem imprime aplica `.upper()`).

- [ ] **Step 1: Teste (falha)**

```python
# backend/tests/test_extenso.py
import pytest
from app import extenso

GABARITO = [
    (357854, "três mil, quinhentos e setenta e oito reais e cinquenta e quatro centavos"),
    (27850992, "duzentos e setenta e oito mil, quinhentos e nove reais e noventa e dois centavos"),
    (240892989, "dois milhões, quatrocentos e oito mil, novecentos e vinte e nove reais e oitenta e nove centavos"),
    (100000000, "um milhão de reais"),
    (1313, "treze reais e treze centavos"),
    # espelhos reais: " e " antes do ultimo grupo quando < 100 ou multiplo de 100; "," senao
    (5007415, "cinquenta mil e setenta e quatro reais e quinze centavos"),
    (86920018, "oitocentos e sessenta e nove mil e duzentos reais e dezoito centavos"),
    (3219258, "trinta e dois mil, cento e noventa e dois reais e cinquenta e oito centavos"),
    (174209879, "um milhão, setecentos e quarenta e dois mil e noventa e oito reais e setenta e nove centavos"),
    (30702, "trezentos e sete reais e dois centavos"),
    # bordas
    (10000, "cem reais"), (10100, "cento e um reais"), (100, "um real"), (1, "um centavo"),
    (45, "quarenta e cinco centavos"), (0, "zero reais"), (100000, "mil reais"), (100100, "mil e um reais"),
]


@pytest.mark.parametrize("centavos,texto", GABARITO)
def test_extenso(centavos, texto):
    assert extenso.reais(centavos) == texto
```

- [ ] **Step 2: Rodar** → `ModuleNotFoundError`.

- [ ] **Step 3: Implementar**

```python
"""Valor por extenso em reais, regra do motor antigo do espelho (levantamento 2026-09-22 §3).

Entrada em CENTAVOS inteiros (nada de float). Saida em minusculas com acento; o espelho
imprime em caixa alta. Diferencas de grafia ("três", "quatorze", "cinquenta", "milhão") sao
exatamente o que o gabarito pega.
"""
_UNIDADES = ["", "um", "dois", "três", "quatro", "cinco", "seis", "sete", "oito", "nove", "dez", "onze",
             "doze", "treze", "quatorze", "quinze", "dezesseis", "dezessete", "dezoito", "dezenove"]
_DEZENAS = ["", "", "vinte", "trinta", "quarenta", "cinquenta", "sessenta", "setenta", "oitenta", "noventa"]
_CENTENAS = ["", "cento", "duzentos", "trezentos", "quatrocentos", "quinhentos", "seiscentos", "setecentos",
             "oitocentos", "novecentos"]


def _tres(n: int) -> str:
    if n == 0:
        return ""
    if n == 100:
        return "cem"
    partes = []
    if n >= 100:
        partes.append(_CENTENAS[n // 100])
    resto = n % 100
    if 0 < resto < 20:
        partes.append(_UNIDADES[resto])
    elif resto >= 20:
        d, u = divmod(resto, 10)
        partes.append(_DEZENAS[d] + (f" e {_UNIDADES[u]}" if u else ""))
    return " e ".join(partes)


def inteiro(n: int) -> str:
    if n == 0:
        return "zero"
    if n >= 1_000_000_000:
        raise ValueError("valor acima de 999 milhões não tem extenso definido")
    mi, resto = divmod(n, 1_000_000)
    mil, uni = divmod(resto, 1000)
    grupos = []   # (texto, valor bruto do grupo)
    if mi:
        grupos.append((_tres(mi) + (" milhão" if mi == 1 else " milhões"), mi))
    if mil:
        grupos.append(("mil" if mil == 1 else _tres(mil) + " mil", mil))
    if uni:
        grupos.append((_tres(uni), uni))
    texto = grupos[0][0]
    for i, (t, bruto) in enumerate(grupos[1:], start=1):
        ultimo = i == len(grupos) - 1
        sep = " e " if ultimo and (bruto < 100 or bruto % 100 == 0) else ", "
        texto += sep + t
    return texto


def reais(centavos: int) -> str:
    if centavos < 0:
        raise ValueError("valor negativo não tem extenso")
    r, c = divmod(int(centavos), 100)
    partes = []
    if r:
        de = " de" if r % 1_000_000 == 0 else ""
        partes.append(inteiro(r) + de + (" real" if r == 1 else " reais"))
    if c:
        partes.append(inteiro(c) + (" centavo" if c == 1 else " centavos"))
    return " e ".join(partes) if partes else "zero reais"
```

- [ ] **Step 4: Rodar** → 18 passed. **Step 5: Commit** — `git commit -m "feat: valor por extenso em reais para o espelho"`

---

### Task 4: Motor do espelho (`espelho.py`) provado contra os gabaritos

**Files:**
- Create: `backend/app/espelho.py`
- Test: `backend/tests/test_espelho.py`

**Interfaces:**
- Consumes: `extenso.reais(centavos) -> str`.
- Produces:
  - `espelho.normalizar(regra_bruta: dict) -> dict` — valida o esquema da seção "Esquema da regra fiscal" (sem olhar arquivo nem banco) e devolve a regra normalizada (percentuais como `str` Decimal com ponto, `fracao` como lista, `retencoes` de cada saída já mescladas com o padrão da obra). Levanta `RegraInvalida(erros: list[str])`.
  - `espelho.calcular(regra: dict, entradas: dict[str, int]) -> list[dict]` — uma saída emitida por nota, na ordem de `regra["saidas"]`, cada uma:
    `{"chave", "natureza", "rotulo", "emissor", "municipio", "modelo", "valor", "mo", "material", "inss", "iss", "irrf", "ibs", "cbs", "liquido"}` em centavos (`None` onde a regra diz `null`), mais `"extenso"` (minúsculas). Saída com valor ≤ 0 não entra.
  - `espelho.valor_por_natureza(regra, entradas) -> dict[str, int]` — soma das entradas por natureza (`medicao`→`execucao`, `reajuste`, `projeto`), só as > 0.
  - `espelho.nome_arquivo(regra, saida, obra: str, numero: int, competencia: str, nome_emissor: str, ext="docx") -> str` — padrão §4.4.
  - `espelho.CAMPOS_MODELO = ("valor", "mo", "material", "inss", "iss", "irrf", "valor_extenso", "medicao", "periodo")`, `espelho.CAMPOS_OPCIONAIS = ("ibs", "cbs")`, `espelho.campos_da_saida(saida_normalizada) -> set[str]` (quais controles a saída preenche).
  - `espelho.formatar_controles(saida_calculada, numero: int, competencia: str) -> dict[str, str]` — `{"valor": "278.509,92", "mo": ..., "valor_extenso": "DUZENTOS ...", "medicao": "23ª", "periodo": "01/01/2026 A 31/01/2026", ...}` só com os campos não-`None`.

- [ ] **Step 1: Testes (falham)**

```python
# backend/tests/test_espelho.py
import pytest
from app import espelho

def brl(t: str) -> int:
    return int(t.replace(".", "").replace(",", ""))

BASE = {"mao_de_obra": {"percentual": "40", "arredondamento": "trunc"}, "material": {"modo": "diferenca"},
        "inss": {"percentual": "11", "base": "mao_de_obra", "arredondamento": "trunc"},
        "iss": {"percentual": "5", "base": "mao_de_obra", "arredondamento": "trunc"},
        "irrf": {"percentual": "1,2", "base": "total", "arredondamento": "trunc"}}

def regra_simples(irrf_arred="trunc"):
    return espelho.normalizar({
        "contrato": "MT-402", "situacao": "ativa",
        "entradas": [{"chave": "medicao", "rotulo": "Valor da medição", "natureza": "medicao"},
                     {"chave": "reajuste", "rotulo": "Valor do reajuste", "natureza": "reajuste"}],
        "retencoes": {**BASE, "irrf": {**BASE["irrf"], "arredondamento": irrf_arred}},
        "saidas": [{"chave": "medicao", "natureza": "medicao", "valor": "medicao", "emissor": "lotufo",
                    "municipio": "Cuiabá", "modelo": "medicao.docx"},
                   {"chave": "reajuste", "natureza": "reajuste", "valor": "reajuste", "emissor": "lotufo",
                    "municipio": "Cuiabá", "modelo": "reajuste.docx"}]})

MT388 = {"contrato": "MT-388", "situacao": "prova",
    "entradas": [{"chave": "medicao", "rotulo": "Valor da medição", "natureza": "medicao"},
                 {"chave": "reajuste", "rotulo": "Valor do reajuste", "natureza": "reajuste"}],
    "parcelas": [{"chave": "med-caceres", "de": "medicao", "fator": "0,8328", "arredondamento": "round"},
                 {"chave": "med-porto", "de": "medicao", "resto_de": ["med-caceres"]},
                 {"chave": "reaj-caceres", "de": "reajuste", "fator": "0,8328", "arredondamento": "round"},
                 {"chave": "reaj-porto", "de": "reajuste", "resto_de": ["reaj-caceres"]}],
    "retencoes": {**BASE, "iss": {**BASE["iss"], "deduz_liquido": False}},
    "saidas": [
        {"chave": "caceres-medicao", "natureza": "medicao", "valor": "med-caceres", "emissor": "lotufo",
         "municipio": "Cáceres", "retencoes": {"iss": {"base": "material"}}, "modelo": "a.docx"},
        {"chave": "porto-medicao", "natureza": "medicao", "valor": "med-porto", "emissor": "lotufo",
         "municipio": "Porto Esperidião", "modelo": "b.docx"},
        {"chave": "caceres-reajuste", "natureza": "reajuste", "valor": "reaj-caceres", "emissor": "lotufo",
         "municipio": "Cáceres", "retencoes": {"iss": {"base": "material"}}, "modelo": "c.docx"},
        {"chave": "porto-reajuste", "natureza": "reajuste", "valor": "reaj-porto", "emissor": "lotufo",
         "municipio": "Porto Esperidião", "modelo": "d.docx"}]}

def linha(s):
    return tuple(s[k] for k in ("valor", "mo", "material", "inss", "iss", "irrf"))

def test_mt402_23a_irrf_arredondado():
    r = regra_simples("round")
    s = espelho.calcular(r, {"medicao": brl("278.509,92"), "reajuste": brl("19.580,95")})
    assert linha(s[0]) == (27850992, 11140396, 16710596, 1225443, 557019, 334212)
    assert linha(s[1]) == (1958095, 783238, 1174857, 86156, 39161, 23497)
    assert s[0]["liquido"] == 27850992 - 1225443 - 557019 - 334212
    assert s[0]["extenso"].startswith("duzentos e setenta e oito mil")

def test_cavalaria_03a_tudo_truncado():
    s = espelho.calcular(regra_simples("trunc"), {"medicao": brl("584.463,68"), "reajuste": brl("103.099,39")})
    assert linha(s[0]) == (58446368, 23378547, 35067821, 2571640, 1168927, 701356)
    assert linha(s[1]) == (10309939, 4123975, 6185964, 453637, 206198, 123719)

def test_mt401_32a():
    s = espelho.calcular(regra_simples("round"), {"medicao": brl("985.375,86"), "reajuste": brl("133.083,30")})
    assert linha(s[0]) == (98537586, 39415034, 59122552, 4335653, 1970751, 1182451)
    assert linha(s[1]) == (13308330, 5323332, 7984998, 585566, 266166, 159700)

def test_reajuste_zero_nao_emite_e_valor_por_natureza():
    r = regra_simples()
    s = espelho.calcular(r, {"medicao": 100000, "reajuste": 0})
    assert [x["chave"] for x in s] == ["medicao"]
    assert espelho.valor_por_natureza(r, {"medicao": 100000, "reajuste": 0}) == {"execucao": 100000}

def test_mt388_10a_quatro_notas_iss_sobre_material_em_caceres():
    s = espelho.calcular(espelho.normalizar(MT388), {"medicao": brl("634.529,58"), "reajuste": brl("38.655,83")})
    assert [linha(x) for x in s] == [
        (52843623, 21137449, 31706174, 2325119, 1585308, 634123),
        (10609335, 4243734, 6365601, 466810, 212186, 127312),
        (3219258, 1287703, 1931555, 141647, 96577, 38631),
        (646325, 258530, 387795, 28438, 12926, 7755)]
    assert s[0]["liquido"] == 52843623 - 2325119 - 634123          # ISS nao deduz

def test_atalaia_43a_rateio_em_dois_niveis_com_resto():
    r = espelho.normalizar({"contrato": "Parque Atalaia", "situacao": "prova",
        "entradas": [{"chave": "medicao", "rotulo": "m", "natureza": "medicao"}],
        "parcelas": [{"chave": "cba", "de": "medicao", "fator": "0,5872", "arredondamento": "trunc"},
                     {"chave": "vg", "de": "medicao", "resto_de": ["cba"]},
                     {"chave": "cba-lotufo", "de": "cba", "fator": "0,8", "arredondamento": "trunc"},
                     {"chave": "cba-rivoli", "de": "cba", "resto_de": ["cba-lotufo"]},
                     {"chave": "vg-lotufo", "de": "vg", "fator": "0,8", "arredondamento": "trunc"},
                     {"chave": "vg-rivoli", "de": "vg", "resto_de": ["vg-lotufo"]}],
        "retencoes": BASE,
        "saidas": [{"chave": k, "natureza": "medicao", "valor": k, "emissor": e, "municipio": m, "modelo": f"{k}.docx"}
                   for k, e, m in [("cba-lotufo", "lotufo", "Cuiabá"), ("cba-rivoli", "rivoli", "Cuiabá"),
                                   ("vg-lotufo", "lotufo", "Várzea Grande"), ("vg-rivoli", "rivoli", "Várzea Grande")]]})
    s = espelho.calcular(r, {"medicao": brl("780.224,80")})
    assert linha(s[0]) == (36651840, 14660736, 21991104, 1612680, 733036, 439822)
    assert linha(s[1]) == (9162960, 3665184, 5497776, 403170, 183259, 109955)
    assert linha(s[2]) == (25766144, 10306457, 15459687, 1133710, 515322, 309193)
    assert s[0]["valor"] + s[1]["valor"] + s[2]["valor"] + s[3]["valor"] == brl("780.224,80")

def test_brt_10a_fracao_exata_round_por_empresa_e_projeto_sem_split():
    r = espelho.normalizar({"contrato": "Integra BRT", "situacao": "prova",
        "entradas": [{"chave": "medicao", "rotulo": "m", "natureza": "medicao"},
                     {"chave": "projeto", "rotulo": "p", "natureza": "projeto"}],
        "parcelas": [{"chave": "cba", "de": "medicao", "fracao": [6740, 7820], "arredondamento": "trunc"},
                     {"chave": "vg", "de": "medicao", "resto_de": ["cba"]},
                     {"chave": "cba-lotufo", "de": "cba", "fator": "0,49", "arredondamento": "round"},
                     {"chave": "vg-lotufo", "de": "vg", "fator": "0,49", "arredondamento": "round"},
                     {"chave": "proj-lotufo", "de": "projeto", "fator": "0,49", "arredondamento": "round"}],
        "retencoes": BASE,
        "saidas": [{"chave": "exec-cba-lotufo", "natureza": "medicao", "valor": "cba-lotufo", "emissor": "lotufo", "municipio": "Cuiabá", "modelo": "a.docx"},
                   {"chave": "exec-vg-lotufo", "natureza": "medicao", "valor": "vg-lotufo", "emissor": "lotufo", "municipio": "Várzea Grande", "modelo": "b.docx"},
                   {"chave": "proj-cba-lotufo", "natureza": "projeto", "valor": "proj-lotufo", "emissor": "lotufo", "municipio": "Cuiabá", "modelo": "c.docx",
                    "retencoes": {"mao_de_obra": None, "material": None, "inss": None,
                                  "iss": {"percentual": "5", "base": "total", "arredondamento": "trunc"},
                                  "irrf": {"percentual": "4,8", "base": "total", "arredondamento": "trunc"}}}]})
    s = espelho.calcular(r, {"medicao": brl("7.382.048,52"), "projeto": 0})
    assert linha(s[0]) == (311764110, 124705644, 187058466, 13717620, 6235282, 3741169)
    assert linha(s[1]) == (49956267, 19982506, 29973761, 2198075, 999125, 599475)
    assert len(s) == 2
    p = espelho.calcular(r, {"medicao": 0, "projeto": brl("15.351,18")})   # 7.522,08 / 0,49 -> Lotufo 7.522,08
    assert (p[0]["valor"], p[0]["mo"], p[0]["inss"], p[0]["iss"], p[0]["irrf"]) == (752208, None, None, 37610, 36105)

def test_estacoes_3a_fracao_61_81_truncada():
    r = espelho.normalizar({"contrato": "Estações BRT", "situacao": "prova",
        "entradas": [{"chave": "medicao", "rotulo": "m", "natureza": "medicao"},
                     {"chave": "reajuste", "rotulo": "r", "natureza": "reajuste"}],
        "parcelas": [{"chave": "med-cba", "de": "medicao", "fracao": [61, 81], "arredondamento": "trunc"},
                     {"chave": "med-vg", "de": "medicao", "resto_de": ["med-cba"]},
                     {"chave": "reaj-cba", "de": "reajuste", "fracao": [61, 81], "arredondamento": "trunc"},
                     {"chave": "reaj-vg", "de": "reajuste", "resto_de": ["reaj-cba"]}],
        "retencoes": BASE,
        "saidas": [{"chave": k, "natureza": n, "valor": k, "emissor": "lotufo", "municipio": m, "modelo": f"{k}.docx"}
                   for k, n, m in [("med-cba", "medicao", "Cuiabá"), ("med-vg", "medicao", "Várzea Grande"),
                                   ("reaj-cba", "reajuste", "Cuiabá"), ("reaj-vg", "reajuste", "Várzea Grande")]]})
    s = espelho.calcular(r, {"medicao": brl("3.198.742,98"), "reajuste": brl("202.800,30")})
    assert [linha(x) for x in s] == [
        (240892989, 96357195, 144535794, 10599291, 4817859, 2890715),
        (78981309, 31592523, 47388786, 3475177, 1579626, 947775),
        (15272615, 6109046, 9163569, 671995, 305452, 183271),
        (5007415, 2002966, 3004449, 220326, 100148, 60088)]

def test_leblon_resto_fica_um_centavo_menor_e_tributos_arredondados():
    r = espelho.normalizar({"contrato": "Leblon", "situacao": "prova",
        "entradas": [{"chave": "reajuste", "rotulo": "r", "natureza": "reajuste"}],
        "parcelas": [{"chave": "lotufo", "de": "reajuste", "fator": "0,5", "arredondamento": "round"},
                     {"chave": "rivoli", "de": "reajuste", "resto_de": ["lotufo"]}],
        "retencoes": {**BASE, "inss": {**BASE["inss"], "arredondamento": "round"},
                      "iss": {**BASE["iss"], "arredondamento": "round"}, "irrf": {**BASE["irrf"], "arredondamento": "round"}},
        "saidas": [{"chave": "lotufo", "natureza": "reajuste", "valor": "lotufo", "emissor": "lotufo", "municipio": "Cuiabá", "modelo": "a.docx"},
                   {"chave": "rivoli", "natureza": "reajuste", "valor": "rivoli", "emissor": "rivoli", "municipio": "Cuiabá", "modelo": "b.docx"}]})
    s = espelho.calcular(r, {"reajuste": brl("476.449,03")})
    assert (s[0]["valor"], s[1]["valor"]) == (23822452, 23822451)
    assert (s[0]["inss"], s[0]["iss"], s[0]["irrf"]) == (1048188, 476449, 285869)

def test_ibs_cbs_informativos_nao_deduzem_do_liquido():
    bruto = {**regra_simples(), }
    r = espelho.normalizar({**MT388, "retencoes": {**BASE, "ibs": {"percentual": "0,1", "base": "total", "arredondamento": "round", "vigente_desde": "2026-01-01"},
                                                   "cbs": {"percentual": "0,9", "base": "total", "arredondamento": "round", "vigente_desde": "2026-01-01"}}})
    s = espelho.calcular(r, {"medicao": 100000, "reajuste": 0})
    assert (s[0]["ibs"], s[0]["cbs"]) == (round(s[0]["valor"] * 0.001), round(s[0]["valor"] * 0.009))
    assert s[0]["liquido"] == s[0]["valor"] - s[0]["inss"] - s[0]["iss"] - s[0]["irrf"]

def test_nome_do_arquivo_e_controles():
    r = espelho.normalizar(MT388)
    s = espelho.calcular(r, {"medicao": brl("634.529,58"), "reajuste": 0})
    assert espelho.nome_arquivo(r, r["saidas"][0], "MT-388", 10, "2026-05", "Lotufo") == \
        "ESPELHO - MT-388 - 10ª Medição (05.2026) - Cáceres.docx"     # 1 emissor: sem consorciada
    assert espelho.nome_arquivo(regra_simples(), regra_simples()["saidas"][1], "MT-402", 3, "2026-05", "Lotufo") == \
        "ESPELHO - MT-402 - 03ª Reajuste (05.2026).docx"
    c = espelho.formatar_controles(s[0], 10, "2026-05")
    assert c["valor"] == "528.436,23" and c["medicao"] == "10ª" and c["periodo"] == "01/05/2026 A 31/05/2026"
    assert c["valor_extenso"].startswith("QUINHENTOS E VINTE E OITO MIL, QUATROCENTOS")
    assert espelho.campos_da_saida(r["saidas"][0]) == {"valor", "mo", "material", "inss", "iss", "irrf", "valor_extenso", "medicao", "periodo"}

@pytest.mark.parametrize("quebra,trecho", [
    ({"saidas": [{"chave": "x", "natureza": "medicao", "valor": "nao-existe", "emissor": "lotufo", "municipio": "C", "modelo": "a.docx"}]}, "nao-existe"),
    ({"parcelas": [{"chave": "p", "de": "medicao", "fator": "0,5", "arredondamento": "round", "resto_de": ["q"]}]}, "exatamente um"),
    ({"retencoes": {**BASE, "iss": {**BASE["iss"], "base": "lucro"}}}, "base"),
    ({"situacao": "ligada"}, "situacao"),
])
def test_normalizar_acumula_erros(quebra, trecho):
    with pytest.raises(espelho.RegraInvalida) as e:
        espelho.normalizar({**MT388, **quebra})
    assert any(trecho in x for x in e.value.erros)
```

- [ ] **Step 2: Rodar** → `ModuleNotFoundError: app.espelho`.

- [ ] **Step 3: Implementar `backend/app/espelho.py`**

```python
"""Motor do espelho de NF (spec 2026-09-21 §4): regra fiscal da obra + valores digitados -> uma
saida por nota. Puro: sem banco, sem arquivo. Aritmetica Decimal exata; cada parcela e cada
tributo declara `trunc` (ROUND_DOWN) ou `round` (ROUND_HALF_UP), porque as planilhas-motor das
obras diferem nisso e o espelho real e' a prova (docs/espelho-regras-por-obra-2026-09-16.md §3,
levantamento de 2026-09-22). Nao se replica o epsilon de float do motor antigo.
"""
import calendar
import copy
import re
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal, InvalidOperation

from app import extenso

NATUREZAS = ("medicao", "reajuste", "projeto")
TIPO_POR_NATUREZA = {"medicao": "execucao", "reajuste": "reajuste", "projeto": "projeto"}
ROTULO_NATUREZA = {"medicao": "Medição", "reajuste": "Reajuste", "projeto": "Projeto"}
SITUACOES = ("prova", "ativa")
ARREDONDAMENTOS = {"trunc": ROUND_DOWN, "round": ROUND_HALF_UP}
BASES = ("mao_de_obra", "material", "total")
TRIBUTOS = ("inss", "iss", "irrf", "ibs", "cbs")
CAMPOS_MODELO = ("valor", "mo", "material", "inss", "iss", "irrf", "valor_extenso", "medicao", "periodo")
CAMPOS_OPCIONAIS = ("ibs", "cbs")
_CHAVE = re.compile(r"^[a-z0-9][a-z0-9-]{1,40}$")
_CENT = Decimal("0.01")


class RegraInvalida(Exception):
    def __init__(self, erros: list[str]):
        self.erros = erros
        super().__init__("\n".join(erros))


def _dec(v, onde, erros) -> str | None:
    try:
        d = Decimal(str(v).strip().replace(".", "").replace(",", ".")) if "," in str(v) else Decimal(str(v).strip())
    except InvalidOperation:
        erros.append(f"{onde}: número inválido: {v!r}")
        return None
    return str(d)


def _arred(v: Decimal, modo: str) -> Decimal:
    return v.quantize(_CENT, rounding=ARREDONDAMENTOS[modo])


def _retencao(bruto, onde, erros, obrigatorio_base=True):
    if bruto is None:
        return None
    if not isinstance(bruto, dict):
        erros.append(f"{onde}: esperado mapa ou null"); return None
    r = {"percentual": _dec(bruto.get("percentual"), f"{onde}.percentual", erros),
         "arredondamento": bruto.get("arredondamento")}
    if r["arredondamento"] not in ARREDONDAMENTOS:
        erros.append(f"{onde}.arredondamento: use trunc ou round")
    if obrigatorio_base:
        r["base"] = bruto.get("base")
        if r["base"] not in BASES:
            erros.append(f"{onde}.base: use uma de {BASES}")
    if "deduz_liquido" in bruto:
        r["deduz_liquido"] = bool(bruto["deduz_liquido"])
    if "vigente_desde" in bruto:
        r["vigente_desde"] = str(bruto["vigente_desde"])
    return r


def _retencoes(bruto: dict, onde: str, erros: list[str]) -> dict:
    """Bloco completo (padrao da obra) ou parcial (sobrescrita da saida): so' normaliza o que veio."""
    if not isinstance(bruto, dict):
        erros.append(f"{onde}: esperado mapa"); return {}
    out = {}
    for k, v in bruto.items():
        if k == "mao_de_obra":
            out[k] = _retencao(v, f"{onde}.{k}", erros, obrigatorio_base=False)
        elif k == "material":
            if v is None:
                out[k] = None
            elif not isinstance(v, dict) or v.get("modo") not in ("diferenca", "produto"):
                erros.append(f"{onde}.material.modo: use diferenca ou produto")
            elif v["modo"] == "produto":
                out[k] = {"modo": "produto", **(_retencao(v, f"{onde}.material", erros, False) or {})}
            else:
                out[k] = {"modo": "diferenca"}
        elif k in TRIBUTOS:
            out[k] = _retencao(v, f"{onde}.{k}", erros)
        else:
            erros.append(f"{onde}.{k}: retenção desconhecida")
    return out


def _mesclar(padrao: dict, sobre: dict) -> dict:
    out = copy.deepcopy(padrao)
    for k, v in sobre.items():
        if v is None or k not in out or out[k] is None or not isinstance(v, dict):
            out[k] = copy.deepcopy(v)
        else:
            out[k] = {**out[k], **v}
    return out


def normalizar(bruto: dict) -> dict:
    erros: list[str] = []
    if not isinstance(bruto, dict):
        raise RegraInvalida(["regra não é um mapa YAML"])
    r = {"contrato": str(bruto.get("contrato") or ""), "situacao": bruto.get("situacao")}
    if not r["contrato"]:
        erros.append("contrato: obrigatório")
    if r["situacao"] not in SITUACOES:
        erros.append(f"situacao: use uma de {SITUACOES}")
    conhecidas: dict[str, str] = {}      # chave -> 'entrada' | 'parcela'
    r["entradas"] = []
    for i, e in enumerate(bruto.get("entradas") or []):
        onde = f"entradas[{i}]"
        e = e or {}
        if not _CHAVE.match(str(e.get("chave") or "")) or e["chave"] in conhecidas:
            erros.append(f"{onde}.chave: inválida ou repetida: {e.get('chave')!r}"); continue
        if e.get("natureza") not in NATUREZAS:
            erros.append(f"{onde}.natureza: use uma de {NATUREZAS}")
        conhecidas[e["chave"]] = "entrada"
        r["entradas"].append({"chave": e["chave"], "rotulo": str(e.get("rotulo") or e["chave"]),
                              "natureza": e.get("natureza")})
    if not r["entradas"]:
        erros.append("entradas: ao menos uma")
    r["parcelas"] = []
    for i, p in enumerate(bruto.get("parcelas") or []):
        onde = f"parcelas[{i}]"
        p = p or {}
        if not _CHAVE.match(str(p.get("chave") or "")) or p["chave"] in conhecidas:
            erros.append(f"{onde}.chave: inválida ou repetida: {p.get('chave')!r}"); continue
        if p.get("de") not in conhecidas:
            erros.append(f"{onde}.de: referencia {p.get('de')!r}, que não foi declarada antes"); continue
        modos = [k for k in ("fator", "fracao", "resto_de") if k in p]
        if len(modos) != 1:
            erros.append(f"{onde}: declare exatamente um de fator, fracao ou resto_de"); continue
        n = {"chave": p["chave"], "de": p["de"]}
        if "fator" in p:
            n["fator"] = _dec(p["fator"], f"{onde}.fator", erros)
        elif "fracao" in p:
            f = p["fracao"]
            if not (isinstance(f, list) and len(f) == 2 and all(isinstance(x, int) and x > 0 for x in f)):
                erros.append(f"{onde}.fracao: use [numerador, denominador] inteiros positivos")
            n["fracao"] = list(f) if isinstance(f, list) else None
        else:
            irmas = p["resto_de"] if isinstance(p["resto_de"], list) else []
            for q in irmas:
                par = next((x for x in r["parcelas"] if x["chave"] == q), None)
                if par is None or par["de"] != p["de"]:
                    erros.append(f"{onde}.resto_de: {q!r} não é parcela irmã (mesmo `de`) já declarada")
            n["resto_de"] = irmas
        if "resto_de" not in n:
            if p.get("arredondamento") not in ARREDONDAMENTOS:
                erros.append(f"{onde}.arredondamento: use trunc ou round")
            n["arredondamento"] = p.get("arredondamento")
        conhecidas[p["chave"]] = "parcela"
        r["parcelas"].append(n)
    padrao = _retencoes(bruto.get("retencoes") or {}, "retencoes", erros)
    for k in ("mao_de_obra", "material", "inss", "iss", "irrf"):
        padrao.setdefault(k, None)
    r["saidas"] = []
    chaves_saida = set()
    for i, s in enumerate(bruto.get("saidas") or []):
        onde = f"saidas[{i}]"
        s = s or {}
        if not _CHAVE.match(str(s.get("chave") or "")) or s["chave"] in chaves_saida:
            erros.append(f"{onde}.chave: inválida ou repetida: {s.get('chave')!r}"); continue
        chaves_saida.add(s["chave"])
        if s.get("natureza") not in NATUREZAS:
            erros.append(f"{onde}.natureza: use uma de {NATUREZAS}")
        valor = s.get("valor") if isinstance(s.get("valor"), list) else [s.get("valor")]
        for v in valor:
            if v not in conhecidas:
                erros.append(f"{onde}.valor: referencia {v!r}, que não existe")
        for campo in ("emissor", "municipio", "modelo"):
            if not s.get(campo):
                erros.append(f"{onde}.{campo}: obrigatório")
        ret = _mesclar(padrao, _retencoes(s.get("retencoes") or {}, f"{onde}.retencoes", erros))
        if ret.get("mao_de_obra") is None:
            if ret.get("material") is not None:
                erros.append(f"{onde}: sem mão de obra não há material (declare material: null)")
            for t in TRIBUTOS:
                if ret.get(t) and ret[t].get("base") in ("mao_de_obra", "material"):
                    erros.append(f"{onde}.retencoes.{t}.base: {ret[t]['base']} exige mão de obra")
        elif ret.get("material") is None:
            erros.append(f"{onde}: com mão de obra o material é obrigatório (diferenca ou produto)")
        if ret.get("iss") is not None:
            ret["iss"].setdefault("deduz_liquido", True)
        r["saidas"].append({"chave": s["chave"], "natureza": s.get("natureza"), "rotulo": s.get("rotulo"),
                            "valor": valor, "emissor": str(s.get("emissor") or ""), "municipio": str(s.get("municipio") or ""),
                            "modelo": str(s.get("modelo") or ""), "retencoes": ret})
    if not r["saidas"]:
        erros.append("saidas: ao menos uma")
    if erros:
        raise RegraInvalida(erros)
    return r


def _valores(regra: dict, entradas: dict[str, int]) -> dict[str, Decimal]:
    v = {e["chave"]: Decimal(int(entradas.get(e["chave"]) or 0)) / 100 for e in regra["entradas"]}
    for p in regra["parcelas"]:
        base = v[p["de"]]
        if "resto_de" in p:
            v[p["chave"]] = base - sum(v[q] for q in p["resto_de"])
        elif "fator" in p:
            v[p["chave"]] = _arred(base * Decimal(p["fator"]), p["arredondamento"])
        else:
            n, d = p["fracao"]
            v[p["chave"]] = _arred(base * Decimal(n) / Decimal(d), p["arredondamento"])
    return v


def _cent(v: Decimal | None) -> int | None:
    return None if v is None else int(v.quantize(_CENT, rounding=ROUND_DOWN) * 100)


def calcular(regra: dict, entradas: dict[str, int]) -> list[dict]:
    v = _valores(regra, entradas)
    saidas = []
    for s in regra["saidas"]:
        valor = sum(v[k] for k in s["valor"])
        if valor <= 0:
            continue
        ret = s["retencoes"]
        mo = mat = None
        if ret["mao_de_obra"]:
            mo = _arred(valor * Decimal(ret["mao_de_obra"]["percentual"]) / 100, ret["mao_de_obra"]["arredondamento"])
            m = ret["material"]
            mat = valor - mo if m["modo"] == "diferenca" else _arred(valor * Decimal(m["percentual"]) / 100, m["arredondamento"])
        bases = {"mao_de_obra": mo, "material": mat, "total": valor}
        trib = {}
        for t in TRIBUTOS:
            cfg = ret.get(t)
            trib[t] = None if not cfg else _arred(bases[cfg["base"]] * Decimal(cfg["percentual"]) / 100, cfg["arredondamento"])
        liquido = valor - (trib["inss"] or 0) - (trib["irrf"] or 0)
        if trib["iss"] is not None and ret["iss"].get("deduz_liquido", True):
            liquido -= trib["iss"]
        saidas.append({"chave": s["chave"], "natureza": s["natureza"], "rotulo": s["rotulo"] or ROTULO_NATUREZA[s["natureza"]],
                       "emissor": s["emissor"], "municipio": s["municipio"], "modelo": s["modelo"],
                       "valor": _cent(valor), "mo": _cent(mo), "material": _cent(mat),
                       **{t: _cent(trib[t]) for t in TRIBUTOS}, "liquido": _cent(liquido),
                       "extenso": extenso.reais(_cent(valor))})
    return saidas


def valor_por_natureza(regra: dict, entradas: dict[str, int]) -> dict[str, int]:
    soma: dict[str, int] = {}
    for e in regra["entradas"]:
        c = int(entradas.get(e["chave"]) or 0)
        if c > 0:
            t = TIPO_POR_NATUREZA[e["natureza"]]
            soma[t] = soma.get(t, 0) + c
    return soma


def _fmt(centavos: int) -> str:
    inteiro, cent = divmod(abs(centavos), 100)
    return ("-" if centavos < 0 else "") + f"{inteiro:,}".replace(",", ".") + f",{cent:02d}"


def periodo(competencia: str) -> str:
    ano, mes = int(competencia[:4]), int(competencia[5:7])
    ultimo = calendar.monthrange(ano, mes)[1]
    return f"01/{mes:02d}/{ano} A {ultimo:02d}/{mes:02d}/{ano}"


def formatar_controles(saida: dict, numero: int, competencia: str) -> dict[str, str]:
    c = {"medicao": f"{numero}ª", "periodo": periodo(competencia), "valor": _fmt(saida["valor"]),
         "valor_extenso": saida["extenso"].upper()}
    for k in ("mo", "material", "inss", "iss", "irrf", "ibs", "cbs"):
        if saida.get(k) is not None:
            c[k] = _fmt(saida[k])
    return c


def campos_da_saida(saida_normalizada: dict) -> set[str]:
    ret = saida_normalizada["retencoes"]
    campos = {"valor", "valor_extenso", "medicao", "periodo"}
    if ret["mao_de_obra"]:
        campos |= {"mo", "material"}
    campos |= {t for t in ("inss", "iss", "irrf") if ret.get(t)}
    return campos


def nome_arquivo(regra: dict, saida: dict, obra: str, numero: int, competencia: str,
                 nome_emissor: str, ext: str = "docx") -> str:
    emissores = {s["emissor"] for s in regra["saidas"]}
    municipios = {s["municipio"] for s in regra["saidas"]}
    nome = f"ESPELHO - {obra} - {numero:02d}ª {saida.get('rotulo') or ROTULO_NATUREZA[saida['natureza']]} " \
           f"({competencia[5:7]}.{competencia[:4]})"
    if len(emissores) > 1:
        nome += f" - {nome_emissor}"
    if len(municipios) > 1:
        nome += f" - {saida['municipio']}"
    return f"{nome}.{ext}"
```

Observação para o executor: em `test_ibs_cbs_informativos...` a variável `bruto` sobra; apagar a linha. Se `test_brt_10a...` falhar por 1 centavo na parcela `cba`, conferir se a `fracao` está sendo aplicada como `base * n / d` (uma divisão só, precisão 28) e não como `base * (n/d)` pré-arredondado.

- [ ] **Step 4: Rodar** → 16 passed. Se algum gabarito falhar por 1 centavo, NÃO ajustar o gabarito: conferir a política de arredondamento da obra na tabela "Regra por obra" (é a fórmula da planilha) e o `deduz_liquido`.

- [ ] **Step 5: Commit** — `git commit -m "feat: motor do espelho de NF provado contra os gabaritos das 7 obras"`

---

### Task 5: Preencher os controles do modelo Word (`espelho_docx.py`)

**Files:**
- Modify: `backend/pyproject.toml` (dependência `lxml>=5.0,<7.0`), `backend/requirements.lock` (`pip freeze` após instalar)
- Create: `backend/app/espelho_docx.py`
- Test: `backend/tests/test_espelho_docx.py`

**Interfaces:**
- Produces: `espelho_docx.controles(docx: bytes) -> set[str]` (tags dos `w:sdt` de `word/document.xml`), `espelho_docx.preencher(docx: bytes, valores: dict[str, str]) -> bytes` (troca o texto de cada controle cuja tag está em `valores`; controle repetido recebe o mesmo texto; tag ausente é ignorada; o resto do pacote é copiado byte a byte), `espelho_docx.DocxInvalido`.

- [ ] **Step 1: Instalar a dependência** — `cd backend && .venv\Scripts\python -m pip install "lxml>=5.0,<7.0"` e acrescentar `"lxml>=5.0,<7.0",` em `[project].dependencies` do `pyproject.toml` com o comentário `# so' para preencher content controls do .docx (espelho_docx.py); python-docx nao le w:sdt`. Regravar `requirements.lock` com `.venv\Scripts\python -m pip freeze > requirements.lock` (conferir no diff que só entrou `lxml`).

- [ ] **Step 2: Teste (falha)** — o teste monta um `.docx` mínimo em memória, com dois controles `valor` (repetido) e um `medicao`, e um parágrafo fixo:

```python
# backend/tests/test_espelho_docx.py
import io
import zipfile

import pytest
from app import espelho_docx

W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
def sdt(tag, texto):
    return (f'<w:sdt><w:sdtPr><w:alias w:val="{tag}"/><w:tag w:val="{tag}"/><w:id w:val="5001"/></w:sdtPr>'
            f'<w:sdtContent><w:r><w:rPr><w:b/></w:rPr><w:t>{texto[:3]}</w:t></w:r><w:r><w:t>{texto[3:]}</w:t></w:r></w:sdtContent></w:sdt>')

def docx_minimo() -> bytes:
    doc = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document {W} '
           'xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" mc:Ignorable="w14">'
           f'<w:body><w:p><w:r><w:t>VALOR DA MEDIÇÃO: R$ </w:t></w:r>{sdt("valor", "1.000,00")}</w:p>'
           f'<w:p>{sdt("medicao", "9ª")}<w:r><w:t> fixo </w:t></w:r>{sdt("valor", "1.000,00")}</w:p></w:body></w:document>')
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>')
        z.writestr("word/document.xml", doc)
        z.writestr("word/styles.xml", "<a/>")
    return buf.getvalue()

def texto_de(docx: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(docx)) as z:
        return z.read("word/document.xml").decode("utf-8")

def test_controles_lista_as_tags():
    assert espelho_docx.controles(docx_minimo()) == {"valor", "medicao"}

def test_preencher_troca_todas_as_ocorrencias_e_preserva_o_resto():
    saida = espelho_docx.preencher(docx_minimo(), {"valor": "278.509,92", "medicao": "23ª", "inexistente": "x"})
    xml = texto_de(saida)
    assert xml.count("278.509,92") == 2 and "23ª" in xml and "1.000,00" not in xml and "9ª" not in xml
    assert "VALOR DA MEDIÇÃO: R$ " in xml and "<w:b/>" in xml and 'mc:Ignorable="w14"' in xml
    with zipfile.ZipFile(io.BytesIO(saida)) as z:
        assert z.read("word/styles.xml") == b"<a/>"

def test_preencher_e_deterministico_para_o_hash():
    a = espelho_docx.preencher(docx_minimo(), {"valor": "1,00"})
    b = espelho_docx.preencher(docx_minimo(), {"valor": "1,00"})
    assert a == b

def test_docx_sem_document_xml_e_recusado():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("x.txt", "nada")
    with pytest.raises(espelho_docx.DocxInvalido):
        espelho_docx.controles(buf.getvalue())
```

- [ ] **Step 3: Implementar**

```python
"""Preenche content controls (w:sdt) de um modelo .docx pelo `w:tag` (spec §4.2, modelos Word).

O .docx e' um zip; so' `word/document.xml` muda. lxml preserva prefixos de namespace (o
`mc:Ignorable` do Word referencia prefixos pelo nome; ElementTree os renomearia). O zip de saida
e' regravado com data fixa e ordem estavel para o mesmo conteudo dar o mesmo sha256.
"""
import io
import zipfile

from lxml import etree

NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
W = "{%s}" % NS["w"]
_DATA_FIXA = (1980, 1, 1, 0, 0, 0)


class DocxInvalido(Exception):
    pass


def _document(docx: bytes) -> tuple[zipfile.ZipFile, etree._Element]:
    try:
        z = zipfile.ZipFile(io.BytesIO(docx))
        xml = z.read("word/document.xml")
    except (zipfile.BadZipFile, KeyError) as e:
        raise DocxInvalido("arquivo não é um .docx com word/document.xml") from e
    try:
        return z, etree.fromstring(xml)
    except etree.XMLSyntaxError as e:
        raise DocxInvalido(f"document.xml malformado: {e}") from e


def _tag(sdt) -> str | None:
    t = sdt.find(f"{W}sdtPr/{W}tag")
    return None if t is None else t.get(f"{W}val")


def controles(docx: bytes) -> set[str]:
    _, raiz = _document(docx)
    return {t for t in (_tag(s) for s in raiz.iter(f"{W}sdt")) if t}


def preencher(docx: bytes, valores: dict[str, str]) -> bytes:
    z, raiz = _document(docx)
    for sdt in raiz.iter(f"{W}sdt"):
        tag = _tag(sdt)
        if tag not in valores:
            continue
        conteudo = sdt.find(f"{W}sdtContent")
        if conteudo is None:
            continue
        ts = list(conteudo.iter(f"{W}t"))
        if not ts:
            continue
        ts[0].text = valores[tag]
        ts[0].set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
        for t in ts[1:]:
            t.text = ""
        # placeholder do Word ("Clique para digitar") deixaria o texto cinza
        ph = sdt.find(f"{W}sdtPr/{W}showingPlcHdr")
        if ph is not None:
            ph.getparent().remove(ph)
    novo_xml = etree.tostring(raiz, xml_declaration=True, encoding="UTF-8", standalone=True)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as saida:
        for info in sorted(z.infolist(), key=lambda i: i.filename):
            dados = novo_xml if info.filename == "word/document.xml" else z.read(info.filename)
            zi = zipfile.ZipInfo(info.filename, date_time=_DATA_FIXA)
            zi.compress_type = zipfile.ZIP_DEFLATED
            saida.writestr(zi, dados)
    return buf.getvalue()
```

- [ ] **Step 4: Rodar** → 4 passed. Abrir um modelo real depois da Task 8 e conferir no Word que o texto entrou com a formatação do controle (passo manual da Task 8).

- [ ] **Step 5: Commit** — `git add backend/pyproject.toml backend/requirements.lock backend/app/espelho_docx.py backend/tests/test_espelho_docx.py && git commit -m "feat: preenchimento dos content controls do modelo Word do espelho (lxml)"`

---

### Task 6: Cadastro — ler e validar `geral.yaml`, `espelho/*.yaml` e `emails_faturamento`

**Files:**
- Modify: `backend/app/cadastro_arquivos.py` (`preparar`, seção de entidades, funções novas `_geral`, `_espelho`)
- Test: `backend/tests/test_cadastro_arquivos.py` (acrescentar)

**Interfaces:**
- Consumes: `espelho.normalizar`, `espelho.RegraInvalida`, `espelho.campos_da_saida`, `espelho.CAMPOS_MODELO`, `espelho.CAMPOS_OPCIONAIS`, `espelho_docx.controles`, `espelho_docx.DocxInvalido`.
- Produces: `preparar(raiz)` passa a devolver também:
  - `"geral": {"faturamento": {"para": [str], "copia": [str], "assunto": str, "corpo": str}}` (ou `None` quando `geral.yaml` não existe — compatibilidade com os testes atuais);
  - `"espelho": [{"contrato": nome_curto, "slug": str, "situacao", "regra": <normalizada>, "sha256": str (da regra canônica JSON), "modelos": {chave_saida: {"caminho": Path absoluto, "sha256": str}}}]`;
  - entidades ganham `"emails_faturamento": [str]` (lista, vazia se ausente).

- [ ] **Step 1: Testes (falham)** — acrescentar em `test_cadastro_arquivos.py`, usando o helper que o arquivo já tem para montar uma raiz mínima em `tmp_path` (conferir o nome; se não houver, criar `_raiz(tmp_path)` que grava `orgaos.yaml`, `entidades.yaml` e um `contratos/mt-402.yaml` válidos). Para o modelo, reutilizar `docx_minimo()` de `test_espelho_docx.py` (importar) trocando as tags para as nove de `CAMPOS_MODELO`:

```python
from tests.test_espelho_docx import docx_minimo  # se o import falhar, copiar a funcao para um conftest helper
from app import espelho_docx

REGRA_MT402 = """
contrato: MT-402
situacao: ativa
entradas:
  - {chave: medicao, rotulo: Valor da medição, natureza: medicao}
retencoes:
  mao_de_obra: {percentual: '40', arredondamento: trunc}
  material: {modo: diferenca}
  inss: {percentual: '11', base: mao_de_obra, arredondamento: trunc}
  iss: {percentual: '5', base: mao_de_obra, arredondamento: trunc}
  irrf: {percentual: '1,2', base: total, arredondamento: round}
saidas:
  - {chave: medicao, natureza: medicao, valor: medicao, emissor: lotufo, municipio: Cuiabá, modelo: medicao.docx}
"""

def _modelo_completo() -> bytes:
    # um controle por campo obrigatorio; o helper de test_espelho_docx so' tem valor/medicao
    from tests.test_espelho_docx import W, sdt
    import io, zipfile
    corpo = "".join(sdt(t, "x") for t in espelho.CAMPOS_MODELO)
    doc = f'<?xml version="1.0"?><w:document {W}><w:body><w:p>{corpo}</w:p></w:body></w:document>'
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/document.xml", doc)
    return buf.getvalue()

def _com_espelho(raiz, regra=REGRA_MT402, modelo=None):
    (raiz / "espelho").mkdir(exist_ok=True)
    (raiz / "espelho" / "mt-402.yaml").write_text(regra, encoding="utf-8")
    pasta = raiz / "modelos" / "espelho" / "mt-402"; pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "medicao.docx").write_bytes(modelo or _modelo_completo())
    (raiz / "geral.yaml").write_text(
        "faturamento:\n  para: [faturamento@lotufo.com]\n  copia: [leo@lotufo.com]\n"
        "  assunto: 'Emissão NF - {medicao} ({competencia}) - {obra} - {instrumento}'\n"
        "  corpo: |\n    Bom dia.\n    Seguem espelhos.\n", encoding="utf-8")

def test_espelho_valido_entra_normalizado_com_hash_dos_modelos(tmp_path):
    raiz = _raiz(tmp_path); _com_espelho(raiz)
    cad = cadastro_arquivos.preparar(raiz)
    e = cad["espelho"][0]
    assert (e["contrato"], e["slug"], e["situacao"]) == ("MT-402", "mt-402", "ativa")
    assert e["regra"]["saidas"][0]["retencoes"]["iss"]["deduz_liquido"] is True
    assert e["modelos"]["medicao"]["sha256"] == hashlib.sha256(_modelo_completo()).hexdigest()
    assert cad["geral"]["faturamento"]["para"] == ["faturamento@lotufo.com"]

def test_espelho_de_contrato_inexistente_e_modelo_sem_controle_sao_erros(tmp_path):
    raiz = _raiz(tmp_path)
    _com_espelho(raiz, regra=REGRA_MT402.replace("contrato: MT-402", "contrato: MT-999"), modelo=docx_minimo())
    with pytest.raises(cadastro_arquivos.CadastroInvalido) as ex:
        cadastro_arquivos.preparar(raiz)
    erros = "\n".join(ex.value.erros)
    assert "MT-999" in erros and "mt-402.yaml" in erros
    assert "medicao.docx" in erros and "material" in erros          # controle faltando

def test_emissor_desconhecido_e_arquivo_com_slug_errado_sao_erros(tmp_path):
    raiz = _raiz(tmp_path); _com_espelho(raiz, regra=REGRA_MT402.replace("emissor: lotufo", "emissor: acme"))
    (raiz / "espelho" / "mt-402.yaml").rename(raiz / "espelho" / "mt402.yaml")
    with pytest.raises(cadastro_arquivos.CadastroInvalido) as ex:
        cadastro_arquivos.preparar(raiz)
    erros = "\n".join(ex.value.erros)
    assert "acme" in erros and "mt402.yaml" in erros

def test_ibs_sem_controle_no_modelo_e_aviso_nao_erro(tmp_path):
    raiz = _raiz(tmp_path)
    _com_espelho(raiz, regra=REGRA_MT402.replace("  irrf:", "  ibs: {percentual: '0,1', base: total, arredondamento: round}\n  irrf:"))
    cad = cadastro_arquivos.preparar(raiz)
    assert any("ibs" in a and "medicao.docx" in a for a in cad["avisos"])

def test_geral_faturamento_exige_para_e_assunto(tmp_path):
    raiz = _raiz(tmp_path); _com_espelho(raiz)
    (raiz / "geral.yaml").write_text("faturamento:\n  copia: []\n", encoding="utf-8")
    with pytest.raises(cadastro_arquivos.CadastroInvalido, match="geral.yaml"):
        cadastro_arquivos.preparar(raiz)

def test_emails_faturamento_da_entidade_normalizados(tmp_path):
    raiz = _raiz(tmp_path)
    ents = (raiz / "entidades.yaml").read_text(encoding="utf-8") + \
        "- chave: rivoli\n  nome: Rivoli\n  cnpj: '00000000000100'\n  papel: consorciada\n  emails_faturamento: [' Adm@Consorciada.com ']\n"
    (raiz / "entidades.yaml").write_text(ents, encoding="utf-8")
    cad = cadastro_arquivos.preparar(raiz)
    assert next(e for e in cad["entidades"] if e["chave"] == "rivoli")["emails_faturamento"] == ["adm@consorciada.com"]
```

- [ ] **Step 2: Rodar** → falhas (`KeyError: 'espelho'`, etc.).

- [ ] **Step 3: Implementar em `cadastro_arquivos.py`**

Imports: `import hashlib, json` e `from app import dinheiro, entidades, espelho, espelho_docx`. Na leitura de entidades (linha ~251) acrescentar `"emails_faturamento": [str(x).strip().lower() for x in (e.get("emails_faturamento") or [])]`. Funções novas:

```python
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _geral(raiz: Path, erros: list[str]) -> dict | None:
    arq = raiz / "geral.yaml"
    if not arq.is_file():
        return None
    g = _ler(arq) or {}
    f = g.get("faturamento") if isinstance(g, dict) else None
    if not isinstance(f, dict):
        erros.append("geral.yaml: faturamento: obrigatório"); return None
    para = [str(x).strip().lower() for x in (f.get("para") or [])]
    copia = [str(x).strip().lower() for x in (f.get("copia") or [])]
    if not para:
        erros.append("geral.yaml: faturamento.para: ao menos um destinatário")
    for e in para + copia:
        if not _EMAIL.match(e):
            erros.append(f"geral.yaml: e-mail inválido: {e!r}")
    for campo in ("assunto", "corpo"):
        if not str(f.get(campo) or "").strip():
            erros.append(f"geral.yaml: faturamento.{campo}: obrigatório")
    for ph in ("{medicao}", "{obra}"):
        if ph not in str(f.get("assunto") or ""):
            erros.append(f"geral.yaml: faturamento.assunto: precisa conter {ph}")
    return {"faturamento": {"para": para, "copia": copia, "assunto": str(f.get("assunto") or "").strip(),
                            "corpo": str(f.get("corpo") or "").strip()}}


def _espelhos(raiz: Path, contratos: list[dict], ents: set[str], erros: list[str], avisos: list[str]) -> list[dict]:
    pasta = raiz / "espelho"
    if not pasta.is_dir():
        return []
    por_nome = {c["nome_curto"]: c for c in contratos}
    out = []
    for arq in sorted(pasta.glob("*.yaml")):
        onde = f"espelho/{arq.name}"
        try:
            regra = espelho.normalizar(_ler(arq))
        except espelho.RegraInvalida as e:
            erros.extend(f"{onde}: {x}" for x in e.erros); continue
        nome = regra["contrato"]
        if nome not in por_nome:
            erros.append(f"{onde}: contrato: {nome!r} não existe em contratos/"); continue
        if arq.stem != slug(nome):
            erros.append(f"{onde}: arquivo deveria chamar-se {slug(nome)}.yaml")
        modelos = {}
        for s in regra["saidas"]:
            if s["emissor"] not in ents:
                erros.append(f"{onde}: saidas/{s['chave']}: emissor não cadastrado: {s['emissor']}")
            caminho = raiz / "modelos" / "espelho" / slug(nome) / s["modelo"]
            if not caminho.is_file():
                erros.append(f"{onde}: saidas/{s['chave']}: modelo não encontrado: {s['modelo']}"); continue
            dados = caminho.read_bytes()
            try:
                tags = espelho_docx.controles(dados)
            except espelho_docx.DocxInvalido as e:
                erros.append(f"{onde}: {s['modelo']}: {e}"); continue
            faltam = espelho.campos_da_saida(s) - tags
            if faltam:
                erros.append(f"{onde}: {s['modelo']}: sem os controles {sorted(faltam)}")
            for opc in espelho.CAMPOS_OPCIONAIS:
                if s["retencoes"].get(opc) and opc not in tags:
                    avisos.append(f"{onde}: {s['modelo']}: sem o controle {opc} (linha não sairá no espelho)")
            modelos[s["chave"]] = {"caminho": caminho, "sha256": hashlib.sha256(dados).hexdigest()}
        canonico = json.dumps(regra, ensure_ascii=False, sort_keys=True)
        out.append({"contrato": nome, "slug": slug(nome), "situacao": regra["situacao"], "regra": regra,
                    "sha256": hashlib.sha256(canonico.encode("utf-8")).hexdigest(), "modelos": modelos})
    return out
```

Em `preparar`, depois do laço de contratos e antes do `if erros:` acrescentar `geral = _geral(raiz, erros)` e `esp = _espelhos(raiz, contratos, chaves_ent, erros, avisos)`; no `return` acrescentar `"geral": geral, "espelho": esp`. Também: nomes de arquivo repetidos entre saídas de uma mesma regra são erro — calcular `espelho.nome_arquivo(regra, s, nome, 1, "2026-01", s["emissor"])` para cada saída e acusar duplicata (`f"{onde}: duas saídas gerariam o mesmo arquivo: {n}"`).

- [ ] **Step 4: Rodar** `pytest tests/test_cadastro_arquivos.py tests/test_cli_cadastro.py -q` → verde (os testes antigos continuam passando porque `geral`/`espelho` são opcionais na raiz).

- [ ] **Step 5: Commit** — `git commit -m "feat: cadastro le e valida geral.yaml, regras do espelho e modelos Word"`

---

### Task 7: Cadastro — gravar regra, geral e modelos; relatório do CLI

**Files:**
- Modify: `backend/app/cadastro_aplicar.py` (`aplicar`, `_entidades`, funções novas `_geral`, `_espelhos`), `backend/app/cli.py:22` (tupla do relatório)
- Test: `backend/tests/test_cadastro_aplicar.py` (acrescentar), `backend/tests/test_cli_cadastro.py` (acrescentar 1)

**Interfaces:**
- Consumes: `cad["geral"]`, `cad["espelho"]`, `cad["entidades"][i]["emails_faturamento"]`.
- Produces: `cadastro_geral` (chave `faturamento`, valor JSON), `espelho_regras` por contrato (`regra` JSON normalizada, `modelos` JSON `{chave: {"arquivo": "modelos/<sha>.docx", "sha256"}}`, `sha256`, `situacao`), arquivos em `db.db_path().parent / "modelos" / f"{sha}.docx"`, `entidades.emails_faturamento` JSON; relatório com seções `geral` e `espelho`; `cadastro_aplicar.pasta_modelos() -> Path`.

- [ ] **Step 1: Testes (falham)**

```python
# em test_cadastro_aplicar.py
def _cad_com_espelho(tmp_path):
    modelo = tmp_path / "m.docx"; modelo.write_bytes(b"PK-fake-docx")
    regra = {"contrato": "MT-402", "situacao": "prova", "entradas": [{"chave": "medicao", "rotulo": "m", "natureza": "medicao"}],
             "parcelas": [], "saidas": [{"chave": "medicao", "natureza": "medicao", "rotulo": None, "valor": ["medicao"],
                                        "emissor": "lotufo", "municipio": "Cuiabá", "modelo": "medicao.docx",
                                        "retencoes": {"mao_de_obra": {"percentual": "40", "arredondamento": "trunc"},
                                                      "material": {"modo": "diferenca"}, "inss": None, "iss": None, "irrf": None}}]}
    contrato = {"nome_curto": "MT-402", "numero_instrumento": "019/2024", "orgao": "sinfra-suef1", "entidade": "lotufo",
                "objeto": "MT-402", "municipio": None, "lei": None, "cno": None, "art": None, "numero_processo": None,
                "centro_custo_rm": None, "status": "ativo", "status_desde": None, "sem_reajuste": False,
                "destinatarios_extras": [], "valor_original_centavos": 100, "percentual_direito_bp": 10000,
                "execucao_inicio": None, "execucao_fim": None, "vigencia_inicio": None, "vigencia_fim": None,
                "datas_base": [], "fiscais": [], "instrumentos": []}
    return _cad(contratos=[contrato],
                geral={"faturamento": {"para": ["f@lotufo.com"], "copia": [], "assunto": "Emissão NF - {medicao} - {obra}", "corpo": "Bom dia."}},
                espelho=[{"contrato": "MT-402", "slug": "mt-402", "situacao": "prova", "regra": regra, "sha256": "abc",
                          "modelos": {"medicao": {"caminho": modelo, "sha256": hashlib.sha256(b"PK-fake-docx").hexdigest()}}}])

def test_espelho_grava_regra_copia_modelo_e_e_idempotente(conn, tmp_path):
    cad = _cad_com_espelho(tmp_path)
    r1 = cadastro_aplicar.aplicar(conn, 1, cad)
    assert r1["espelho"]["criados"] == ["MT-402"] and r1["geral"]["criados"] == ["faturamento"]
    linha = conn.execute("SELECT situacao, modelos FROM espelho_regras").fetchone()
    m = json.loads(linha["modelos"])["medicao"]
    assert linha["situacao"] == "prova" and m["arquivo"].startswith("modelos/") and m["arquivo"].endswith(".docx")
    assert (cadastro_aplicar.pasta_modelos() / Path(m["arquivo"]).name).read_bytes() == b"PK-fake-docx"
    r2 = cadastro_aplicar.aplicar(conn, 1, cad)
    assert r2["espelho"]["iguais"] == 1 and r2["geral"]["iguais"] == 1

def test_trocar_situacao_para_ativa_e_alteracao_auditada(conn, tmp_path):
    cad = _cad_com_espelho(tmp_path); cadastro_aplicar.aplicar(conn, 1, cad)
    cad["espelho"][0]["situacao"] = "ativa"; cad["espelho"][0]["regra"]["situacao"] = "ativa"
    r = cadastro_aplicar.aplicar(conn, 1, cad)
    assert r["espelho"]["alterados"] == ["MT-402"]
    assert conn.execute("SELECT COUNT(*) FROM audit_log WHERE acao='cadastro.espelho'").fetchone()[0] == 2

def test_ensaio_do_espelho_nao_copia_modelo(conn, tmp_path):
    cad = _cad_com_espelho(tmp_path)
    cadastro_aplicar.aplicar(conn, 1, cad, ensaio=True)
    assert conn.execute("SELECT COUNT(*) FROM espelho_regras").fetchone()[0] == 0
    assert not list(cadastro_aplicar.pasta_modelos().glob("*.docx"))

def test_emails_faturamento_da_entidade_sao_gravados(conn):
    cad = _cad(); cad["entidades"][0]["emails_faturamento"] = ["a@lotufo.com"]
    cadastro_aplicar.aplicar(conn, 1, cad)
    assert json.loads(conn.execute("SELECT emails_faturamento FROM entidades WHERE cnpj=?", (CNPJ_LOTUFO,)).fetchone()[0]) == ["a@lotufo.com"]
```

(`from pathlib import Path` e `import hashlib` no topo. `_cad()` atual não tem `emails_faturamento`: `_entidades` deve tratar ausência como `[]`.)

Em `test_cli_cadastro.py`: um teste que roda `validar` numa raiz com `espelho/` válido e confere que a saída imprime `espelho: 1` (adaptar ao formato de `_relatorio`).

- [ ] **Step 2: Rodar** → falhas.

- [ ] **Step 3: Implementar**

Em `_entidades`: incluir `"emails_faturamento": _json(e.get("emails_faturamento") or [])` no `novo`, no INSERT e no UPDATE. Em `aplicar`: `rel` ganha `"geral": _rel(), "espelho": _rel()`; depois dos contratos chamar `_geral(conn, usuario_id, cad.get("geral"), rel["geral"])` e `_espelhos(conn, usuario_id, cad.get("espelho") or [], rel["espelho"], ensaio)`. Funções:

```python
def pasta_modelos():
    p = db.db_path().parent / "modelos"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _geral(conn, usuario_id, geral, rel) -> None:
    if not geral:
        return
    for chave, valor in geral.items():
        novo = _json(valor)
        ja = conn.execute("SELECT valor FROM cadastro_geral WHERE chave=?", (chave,)).fetchone()
        if ja is None:
            conn.execute("INSERT INTO cadastro_geral (chave, valor) VALUES (?,?)", (chave, novo))
            rel["criados"].append(chave)
            auditoria.registrar(conn, usuario_id, "cadastro.geral", "cadastro_geral", chave, None, valor)
        elif ja["valor"] != novo:
            conn.execute("UPDATE cadastro_geral SET valor=?, atualizado_em=datetime('now') WHERE chave=?", (novo, chave))
            rel["alterados"].append(chave)
            auditoria.registrar(conn, usuario_id, "cadastro.geral", "cadastro_geral", chave, json.loads(ja["valor"]), valor)
        else:
            rel["iguais"] += 1


def _espelhos(conn, usuario_id, lista, rel, ensaio) -> None:
    for e in lista:
        cid = conn.execute("SELECT id FROM contratos WHERE nome_curto=?", (e["contrato"],)).fetchone()
        if cid is None:
            raise ValueError(f"espelho/{e['slug']}.yaml: contrato {e['contrato']!r} não está no banco")
        cid = cid[0]
        modelos = {k: {"arquivo": f"modelos/{m['sha256']}.docx", "sha256": m["sha256"]} for k, m in e["modelos"].items()}
        novo = {"situacao": e["situacao"], "regra": _json(e["regra"]), "modelos": _json(modelos), "sha256": e["sha256"]}
        ja = conn.execute("SELECT * FROM espelho_regras WHERE contrato_id=?", (cid,)).fetchone()
        if ja is not None:
            antes, depois = _diferencas(dict(ja), novo)
            if not depois:
                rel["iguais"] += 1
                continue
        if not ensaio:
            # copia o modelo pelo hash: a producao nao le o checkout em tempo de execucao
            for m in e["modelos"].values():
                destino = pasta_modelos() / f"{m['sha256']}.docx"
                if not destino.exists():
                    destino.write_bytes(Path(m["caminho"]).read_bytes())
        if ja is None:
            conn.execute("INSERT INTO espelho_regras (contrato_id, situacao, regra, modelos, sha256) VALUES (?,?,?,?,?)",
                         (cid, novo["situacao"], novo["regra"], novo["modelos"], novo["sha256"]))
            rel["criados"].append(e["contrato"])
            auditoria.registrar(conn, usuario_id, "cadastro.espelho", "contrato", cid, None,
                                {"situacao": e["situacao"], "sha256": e["sha256"], "modelos": modelos})
        else:
            conn.execute("UPDATE espelho_regras SET situacao=?, regra=?, modelos=?, sha256=?, atualizado_em=datetime('now') "
                         "WHERE contrato_id=?", (novo["situacao"], novo["regra"], novo["modelos"], novo["sha256"], cid))
            rel["alterados"].append(e["contrato"])
            auditoria.registrar(conn, usuario_id, "cadastro.espelho", "contrato", cid,
                                {k: antes[k] for k in depois if k != "regra"} | ({"regra": "alterada"} if "regra" in depois else {}),
                                {k: depois[k] for k in depois if k != "regra"} | ({"sha256_novo": e["sha256"]} if "regra" in depois else {}))
```

(`from pathlib import Path` no topo.) Em `cli.py:22` a tupla vira `("orgaos", "entidades", "contratos", "instrumentos", "geral", "espelho")`. Em `cli.py` o `validar` imprime também `espelho: N regras (M ativas)`.

- [ ] **Step 4: Rodar** → verde. **Step 5: Commit** — `git commit -m "feat: cadastro aplicar grava regra do espelho, geral e copia modelos por hash"`

---

### Task 8: Conteúdo do cadastro — `geral.yaml`, e-mails das consorciadas, regras e modelos das 7 obras, prova pelos YAMLs reais

**Files:**
- Create: `cadastro/geral.yaml`; `cadastro/espelho/{mt-402,mt-401,cavalaria,mt-388,parque-atalaia,integra-brt,estacoes-brt}.yaml`; `cadastro/modelos/espelho/<slug>/*.docx` (copiados de `~/dev/lotufo-automacao-medicao/modelos/<OBRA-ID>/`, renomeados para a chave da saída)
- Modify: `cadastro/entidades.yaml` (`emails_faturamento` de rivoli e guaxe)
- Test: `backend/tests/test_espelho_cadastro_real.py`

**Interfaces:**
- Consumes: Task 6 e 7; tabela "Regra por obra" deste plano; leitura autorizada do motor antigo (memória `automacao-medicao-autorizada`).
- Produces: `cadastro validar` passa; os YAMLs reais reproduzem os gabaritos.

- [ ] **Step 1: Confirmar os endereços do e-mail do espelho** — abrir na caixa do Leonardo (conector Microsoft 365 já autorizado) um thread real "Emissão NF" de 2026 de obra própria e um de consórcio (Leblon ou Integra BRT); copiar Para/CC literais. O mapeamento de 16/09 traz: Para os dois endereços do faturamento; CC a equipe interna, a controladoria e mais uma pessoa da cópia interna (domínio a confirmar); as consorciadas Rivoli (dois contatos) e Guaxe (um contato). Gravar os endereços confirmados; o que não se confirmar fica fora, com `# NOTA`.

- [ ] **Step 2: `cadastro/geral.yaml`**

```yaml
# Destinatarios e texto fixo do e-mail do espelho ao faturamento (mapeamento de e-mails 2026-09-16 §2,
# enderecos conferidos em thread real em 2026-09-22). Consorciada da obra entra automaticamente
# (entidades.yaml: emails_faturamento). Placeholders do assunto: {medicao} = "10ª Medição e Reajuste",
# {competencia} = "05/2026", {obra} = nome curto, {instrumento} = numero_instrumento do contrato.
faturamento:
  para: [faturamento@exemplo.com.br]
  copia: [copia@exemplo.com.br]
  assunto: 'Emissão NF - {medicao} ({competencia}) - {obra} - IC nº {instrumento}'
  corpo: |
    Bom dia.

    Seguem espelhos para emissão de Notas Fiscais.

    Favor conferir se os impostos, base de cálculo e deduções discriminadas no espelho estão corretos.

    Atenciosamente,
```

- [ ] **Step 3: Copiar os modelos** — script no scratchpad (PowerShell) que copia e renomeia, por obra, conforme as tabelas 1.11–1.19 do levantamento: `SINFRA-MT402/MODELO - Espelho NF - Lotufo MT-402 - 23ª Medição.docx` → `cadastro/modelos/espelho/mt-402/medicao.docx`; `... - Reajuste 32ª Medição.docx` → `reajuste.docx`; idem MT-401 e Cavalaria (`MODELO - NF - Lotufo Cavalaria - 03ª Medição.docx` → `medicao.docx`, `Reaj.` → `reajuste.docx`); MT-388 (`caceres-medicao`, `porto-medicao`, `caceres-reajuste`, `porto-reajuste`); Atalaia (8: `{med,reaj}-{cba,vg}-{lotufo,rivoli}`); BRT (9: `exec-{cba,vg}-{lotufo,guaxe,encomind}`, `proj-cba-lotufo`, `proj-tangara-guaxe`, `proj-cba-encomind`); Estações (6: `exec-cba`, `exec-vg`, `reaj-cba`, `reaj-vg`, `proj-cba`, `reaj-proj-cba`). Não copiar o modelo órfão do Espaço Show nem a pasta `_backup-pre-extenso`. Conferir com `git status` que entraram 27 `.docx`.

- [ ] **Step 4: Escrever os 7 YAMLs** pela tabela "Regra por obra" (o de MT-388 é o exemplo da seção "Esquema"; MT-402/MT-401 como `regra_simples("round")` da Task 4 com `situacao: ativa`; Cavalaria com IRRF `trunc`, `ativa`; Atalaia, BRT, Estações como os testes da Task 4, `situacao: prova`). Em BRT, a saída `proj-tangara-guaxe` tem `retencoes: {iss: null}` além do bloco de projeto; `municipio: Tangará da Serra`. Em Estações a 4ª entrada é `{chave: reajuste-projeto, rotulo: Valor do reajuste do projeto, natureza: reajuste}` e a saída `reaj-proj-cba` tem `rotulo: Reajuste do Projeto`. Topo de cada arquivo: comentário com a fonte da regra (fórmulas da planilha-motor, data) e `# NOTA` do que ficou por confirmar (IBS/CBS). Em `entidades.yaml`: `emails_faturamento` em rivoli e guaxe (Step 1); `encomind: []`.

- [ ] **Step 5: `cadastro validar`** — `cd backend && .venv\Scripts\python -m app.cli cadastro validar` → sem erro; avisos só os já conhecidos (Maternidade VG). Se um modelo acusar controle faltando, é o modelo real (ex.: Guaxe Tangará sem `iss` — a regra tem `iss: null`, então não deve acusar); NÃO editar o `.docx` aqui: registrar no backlog.

- [ ] **Step 6: Teste que prova os YAMLs reais** (`backend/tests/test_espelho_cadastro_real.py`) — carrega `cadastro/` do repositório (`cli.RAIZ_PADRAO`) com `cadastro_arquivos.preparar` e confere: (a) as 7 regras existem, MT-402/MT-401/Cavalaria `ativa`, as outras `prova`; (b) `calcular` com a regra real de cada obra reproduz as linhas da tabela "Regra por obra" (MT-402 23ª, MT-401 32ª, Cavalaria 03ª, as 4 de MT-388, Atalaia Lotufo CBA/VG e Rivoli CBA, BRT Lotufo CBA/VG e projeto, Estações 4 linhas + projeto 937.803,58); (c) `espelho_docx.preencher` de cada modelo com `formatar_controles` da saída correspondente produz um `.docx` cujo `document.xml` contém o valor formatado (prova de que os controles reais casam). Um `@pytest.mark.parametrize` por obra.

- [ ] **Step 7: Conferência visual** (manual, uma vez): gerar em scratchpad o `.docx` de MT-402 23ª com a regra real e abrir no Word (COM ou duplo clique): texto entrou nos controles, negrito preservado, extenso em caixa alta. Anotar o resultado no commit.

- [ ] **Step 8: Rodar tudo e commitar** — `pytest -q` verde. `git add cadastro/ backend/tests/test_espelho_cadastro_real.py && git commit -m "feat: cadastro do espelho - geral, regras e modelos de 7 obras (3 ativas), provados pelos gabaritos"`

---

### Task 9: Serviço `espelhos.py` — prévia, gerar (versões, medições, arquivos) e `arquivos.py`

**Files:**
- Create: `backend/app/arquivos.py` (guardas de arquivo extraídas de `api_certidoes.py`), `backend/app/espelhos.py`
- Modify: `backend/app/api_certidoes.py` (importa de `arquivos` em vez de definir: `pasta_certidoes`, `_blocos_validados`, `_sha_do_arquivo`, `_receber_pdf`, `_conferir_parseavel` viram aliases de `arquivos.*`; comportamento idêntico)
- Test: `backend/tests/test_espelhos.py`; `tests/test_api_certidoes.py` continua verde sem mudança

**Interfaces:**
- Consumes: `espelho.*`, `espelho_docx.preencher`, `medicoes.criar_para_espelho`, `contratos.vigente`, `cadastro_aplicar.pasta_modelos`.
- Produces (`arquivos.py`): `pasta(nome: str) -> Path` (`db.db_path().parent / nome`, criada), `gravar_bytes(nome_pasta: str, dados: bytes, ext: str) -> tuple[str, str]` (grava `<pasta>/<sha>.<ext>` se não existe; devolve `("<pasta>/<sha>.<ext>", sha)`), `caminho_seguro(relativo: str) -> Path` (resolve sob a pasta do banco; `ValueError` se sair dela), mais as funções movidas de `api_certidoes` com os nomes `blocos_validados`, `sha_do_arquivo`, `receber_pdf`, `conferir_parseavel`, `pasta_certidoes`.
- Produces (`espelhos.py`):
  - `regra_do_contrato(conn, contrato_id) -> dict | None` — `{"situacao", "regra", "modelos"}` de `espelho_regras` (JSON já carregado).
  - `previa(conn, contrato_id, numero, competencia, entradas: dict[str,int]) -> dict` — `{"saidas": [calculadas + "nome_arquivo"], "medicoes": [{"tipo", "valor_centavos", "existente": estado|None}], "avisos": [str]}`; `ValueError` se a obra não tem regra `ativa` ou se alguma medição já está protocolada.
  - `gerar(conn, usuario: dict, contrato_id, numero, competencia, entradas, motivo=None) -> int` — cria/atualiza as medições (`criar_para_espelho`), preenche os `.docx`, grava em `espelhos/`, insere `espelhos` (versão = max+1; a anterior vira `substituido` com `substituido_em` e `motivo`), `espelho_medicoes`, `medicao_documentos` (`fonte='sistema'`, `tipo_doc='espelho'`, `item_id=sha`, `espelho_id`, `saida`); auditoria `espelho.gerar`. Uma transação.
  - `detalhe(conn, espelho_id) -> dict` — linha + `saidas` + `medicoes` + `arquivos` (`[{documento_id, saida, nome, tamanho, sha256}]`) + `envio` (`envios` se `envio_id`).
  - `listar(conn, contrato_id) -> list[dict]` — todos os espelhos do contrato, `vigente` primeiro, com `arquivos`.

- [ ] **Step 1: Extrair `arquivos.py`** — mover as funções de `api_certidoes.py:43-47,94-103,150-260` para `backend/app/arquivos.py` com nomes públicos; em `api_certidoes.py` deixar `from app.arquivos import (MAGIC, MIME, TETO_MB, TETO_BYTES, BLOCO, pasta_certidoes, blocos_validados as _blocos_validados, sha_do_arquivo as _sha_do_arquivo, receber_pdf as _receber_pdf, conferir_parseavel as _conferir_parseavel)`. Acrescentar em `arquivos.py`:

```python
def pasta(nome: str) -> Path:
    p = db.db_path().parent / nome
    p.mkdir(parents=True, exist_ok=True)
    return p


def gravar_bytes(nome_pasta: str, dados: bytes, ext: str) -> tuple[str, str]:
    """Grava pelo hash (dedup natural) e devolve (caminho relativo a pasta do banco, sha256)."""
    sha = hashlib.sha256(dados).hexdigest()
    destino = pasta(nome_pasta) / f"{sha}.{ext}"
    if not destino.exists():
        tmp = destino.with_suffix(f".{os.getpid()}.tmp")
        tmp.write_bytes(dados)
        os.replace(tmp, destino)
    return f"{nome_pasta}/{sha}.{ext}", sha


def caminho_seguro(relativo: str) -> Path:
    base = db.db_path().parent.resolve()
    alvo = (base / relativo).resolve()
    if not alvo.is_relative_to(base):
        raise ValueError("caminho fora da pasta de dados")
    return alvo
```

Rodar `pytest tests/test_api_certidoes.py -q` → verde. Commit: `git commit -m "refactor: guardas de arquivo de api_certidoes movidas para app/arquivos.py"`.

- [ ] **Step 2: Testes de `espelhos.py` (falham)**

```python
# backend/tests/test_espelhos.py
import io, json, zipfile
import pytest
from app import auth, cadastro_aplicar, db, espelhos, medicoes
from tests.test_cadastro_aplicar import _cad_com_espelho, _cad

@pytest.fixture
def ambiente(tmp_path, monkeypatch):
    monkeypatch.setenv("DASH_DB_PATH", str(tmp_path / "t.db"))
    conn = db.get_conn(); db.migrate(conn)
    uid = auth.criar_usuario(conn, "Ana", "ana@lotufo.com", "senha-forte-123", "engenharia")
    conn.execute("UPDATE certidao_tipos SET aplicavel_por_padrao=0"); conn.commit()
    cad = _cad_com_espelho(tmp_path)
    # modelo de verdade (minimo) no lugar do fake, com os controles que a regra exige
    from tests.test_cadastro_arquivos import _modelo_completo
    m = tmp_path / "m.docx"; m.write_bytes(_modelo_completo())
    import hashlib
    cad["espelho"][0]["modelos"]["medicao"] = {"caminho": m, "sha256": hashlib.sha256(m.read_bytes()).hexdigest()}
    cad["espelho"][0]["situacao"] = cad["espelho"][0]["regra"]["situacao"] = "ativa"
    cadastro_aplicar.aplicar(conn, uid, cad)
    cid = conn.execute("SELECT id FROM contratos").fetchone()[0]
    yield conn, {"id": uid, "email": "ana@lotufo.com"}, cid
    conn.close()

def test_previa_uma_linha_por_nota_e_medicoes_a_criar(ambiente):
    conn, u, cid = ambiente
    p = espelhos.previa(conn, cid, 23, "2026-01", {"medicao": 27850992})
    assert [s["chave"] for s in p["saidas"]] == ["medicao"]
    assert p["saidas"][0]["nome_arquivo"] == "ESPELHO - MT-402 - 23ª Medição (01.2026).docx"
    assert p["medicoes"] == [{"tipo": "execucao", "valor_centavos": 27850992, "existente": None}]

def test_gerar_cria_medicao_espelho_arquivo_e_documento(ambiente):
    conn, u, cid = ambiente
    eid = espelhos.gerar(conn, u, cid, 23, "2026-01", {"medicao": 27850992})
    d = espelhos.detalhe(conn, eid)
    assert d["versao"] == 1 and d["situacao"] == "vigente" and len(d["arquivos"]) == 1
    mid = d["medicoes"][0]["id"]
    assert medicoes.detalhe(conn, mid)["estado"] == "espelho_gerado"
    doc = conn.execute("SELECT * FROM medicao_documentos WHERE medicao_id=?", (mid,)).fetchone()
    assert doc["tipo_doc"] == "espelho" and doc["arquivo"].startswith("espelhos/") and doc["espelho_id"] == eid
    from app import arquivos
    with zipfile.ZipFile(arquivos.caminho_seguro(doc["arquivo"])) as z:
        assert "278.509,92" in z.read("word/document.xml").decode("utf-8")

def test_gerar_de_novo_versiona_e_atualiza_o_valor(ambiente):
    conn, u, cid = ambiente
    e1 = espelhos.gerar(conn, u, cid, 23, "2026-01", {"medicao": 100})
    e2 = espelhos.gerar(conn, u, cid, 23, "2026-01", {"medicao": 200}, motivo="órgão corrigiu")
    d1, d2 = espelhos.detalhe(conn, e1), espelhos.detalhe(conn, e2)
    assert (d1["situacao"], d1["motivo"], d2["versao"], d2["situacao"]) == ("substituido", "órgão corrigiu", 2, "vigente")
    assert d1["medicoes"][0]["id"] == d2["medicoes"][0]["id"]
    assert medicoes.detalhe(conn, d2["medicoes"][0]["id"])["valor_protocolado_centavos"] == 200
    assert [x["versao"] for x in espelhos.listar(conn, cid)] == [2, 1]

def test_regra_em_prova_ou_ausente_recusa(ambiente):
    conn, u, cid = ambiente
    conn.execute("UPDATE espelho_regras SET situacao='prova'"); conn.commit()
    with pytest.raises(ValueError, match="fluxo antigo"):
        espelhos.previa(conn, cid, 1, "2026-01", {"medicao": 1})

def test_entrada_desconhecida_e_tudo_zero_recusam(ambiente):
    conn, u, cid = ambiente
    with pytest.raises(ValueError, match="entrada"):
        espelhos.previa(conn, cid, 1, "2026-01", {"reajuste": 1})
    with pytest.raises(ValueError, match="nenhuma nota"):
        espelhos.previa(conn, cid, 1, "2026-01", {"medicao": 0})
```

(A regra de `_cad_com_espelho` tem `inss/iss/irrf: None`; ajustar `_modelo_completo` ou a regra para que `campos_da_saida ⊆ controles`; o mais simples é o modelo completo ter todos os nove controles, o que já cobre.)

- [ ] **Step 3: Implementar `espelhos.py`**

```python
"""Espelho de NF como ato de operacao (spec §3 passos 1-2, §4): a medicao nasce aqui.

Uma linha em `espelhos` por (contrato, numero, competencia, versao) cobre execucao, reajuste e
projeto do mesmo numero. Gerar de novo = versao nova (a anterior vira `substituido`, com motivo);
nada e' sobrescrito. Arquivos .docx gravados pelo sha256 em <dados>/espelhos.
"""
import json

from app import arquivos, auditoria, contratos, db, espelho, espelho_docx, medicoes


def regra_do_contrato(conn, contrato_id: int) -> dict | None:
    r = conn.execute("SELECT situacao, regra, modelos FROM espelho_regras WHERE contrato_id=?", (contrato_id,)).fetchone()
    if r is None:
        return None
    return {"situacao": r["situacao"], "regra": json.loads(r["regra"]), "modelos": json.loads(r["modelos"])}


def _exigir_ativa(conn, contrato_id) -> dict:
    r = regra_do_contrato(conn, contrato_id)
    if r is None or r["situacao"] != "ativa":
        raise ValueError("Esta obra ainda não gera espelho pelo sistema (fluxo antigo): regra ausente ou em prova")
    return r


def _nomes_entidades(conn) -> dict[str, str]:
    return {e["chave"]: e["nome"] for e in conn.execute("SELECT chave, nome FROM entidades WHERE chave IS NOT NULL")}


def _calcular(conn, contrato_id, numero, competencia, entradas) -> tuple[dict, dict, list[dict], dict[str, int]]:
    r = _exigir_ativa(conn, contrato_id)
    regra = r["regra"]
    chaves = {e["chave"] for e in regra["entradas"]}
    estranhas = set(entradas) - chaves
    if estranhas:
        raise ValueError(f"entrada desconhecida para esta obra: {sorted(estranhas)}")
    saidas = espelho.calcular(regra, entradas)
    if not saidas:
        raise ValueError("nenhuma nota a emitir: todos os valores estão zerados")
    c = contratos.vigente(conn, contrato_id)
    nomes = _nomes_entidades(conn)
    por_chave = {s["chave"]: s for s in regra["saidas"]}
    for s in saidas:
        s["nome_arquivo"] = espelho.nome_arquivo(regra, por_chave[s["chave"]], c["nome_curto"] or c["objeto"],
                                                 numero, competencia, nomes.get(s["emissor"], s["emissor"]))
    return r, c, saidas, espelho.valor_por_natureza(regra, entradas)


def _medicoes_existentes(conn, contrato_id, numero, tipos) -> dict[str, dict]:
    return {m["tipo"]: dict(m) for m in conn.execute(
        "SELECT id, tipo, estado FROM medicoes WHERE contrato_id=? AND numero=? AND tipo IN (%s)"
        % ",".join("?" * len(tipos)), (contrato_id, numero, *tipos))}


def previa(conn, contrato_id: int, numero: int, competencia: str, entradas: dict[str, int]) -> dict:
    _, _, saidas, por_tipo = _calcular(conn, contrato_id, numero, competencia, entradas)
    existentes = _medicoes_existentes(conn, contrato_id, numero, list(por_tipo))
    avisos = []
    meds = []
    for tipo, valor in por_tipo.items():
        ex = existentes.get(tipo)
        if ex and ex["estado"] not in medicoes.ESTADOS_ESPELHO:
            raise ValueError(f"Medição {numero} ({tipo}) já está {ex['estado']}: não pode gerar espelho de novo")
        if ex:
            avisos.append(f"Medição {numero} ({tipo}) já tem espelho: será gerada uma versão nova")
        meds.append({"tipo": tipo, "valor_centavos": valor, "existente": ex["estado"] if ex else None})
    return {"saidas": saidas, "medicoes": meds, "avisos": avisos}


def gerar(conn, usuario: dict, contrato_id: int, numero: int, competencia: str,
          entradas: dict[str, int], motivo: str | None = None) -> int:
    r, c, saidas, por_tipo = _calcular(conn, contrato_id, numero, competencia, entradas)
    modelos = {k: arquivos.caminho_seguro(m["arquivo"]).read_bytes() for k, m in r["modelos"].items()}
    gerados = []                      # (saida, nome, bytes) -- fora da transacao: so' calculo
    for s in saidas:
        docx = espelho_docx.preencher(modelos[s["chave"]], espelho.formatar_controles(s, numero, competencia))
        gerados.append((s, docx))
    with db.mutacao(conn):
        ids = {tipo: medicoes.criar_para_espelho(conn, usuario["id"], contrato_id, numero, tipo, competencia, valor)
               for tipo, valor in por_tipo.items()}
        anterior = conn.execute("SELECT id, versao FROM espelhos WHERE contrato_id=? AND numero=? AND competencia=? "
                                "AND situacao='vigente'", (contrato_id, numero, competencia)).fetchone()
        versao = 1
        if anterior is not None:
            versao = anterior["versao"] + 1
            conn.execute("UPDATE espelhos SET situacao='substituido', substituido_em=datetime('now'), motivo=? WHERE id=?",
                         (motivo, anterior["id"]))
        cur = conn.execute(
            "INSERT INTO espelhos (contrato_id, numero, competencia, versao, situacao, entradas, saidas, regra_sha256, criado_por) "
            "VALUES (?,?,?,?,'vigente',?,?,?,?)",
            (contrato_id, numero, competencia, versao, json.dumps(entradas), json.dumps(saidas, ensure_ascii=False),
             conn.execute("SELECT sha256 FROM espelho_regras WHERE contrato_id=?", (contrato_id,)).fetchone()[0], usuario["id"]))
        eid = cur.lastrowid
        for mid in set(ids.values()):
            conn.execute("INSERT INTO espelho_medicoes (espelho_id, medicao_id) VALUES (?,?)", (eid, mid))
        for s, docx in gerados:
            caminho, sha = arquivos.gravar_bytes("espelhos", docx, "docx")
            mid = ids[espelho.TIPO_POR_NATUREZA[s["natureza"]]]
            conn.execute(
                "INSERT OR IGNORE INTO medicao_documentos (medicao_id, fonte, tipo_doc, nome, item_id, arquivo, sha256, tamanho, "
                "espelho_id, saida, consorciada, municipio) VALUES (?,'sistema','espelho',?,?,?,?,?,?,?,?,?)",
                (mid, s["nome_arquivo"], f"{eid}:{sha}", caminho, sha, len(docx), eid, s["chave"], s["emissor"], s["municipio"]))
        auditoria.registrar(conn, usuario["id"], "espelho.gerar", "espelho", eid, None,
                            {"contrato_id": contrato_id, "numero": numero, "competencia": competencia, "versao": versao,
                             "entradas": entradas, "substitui": anterior["id"] if anterior else None, "motivo": motivo,
                             "arquivos": [{"nome": s["nome_arquivo"], "sha256": arquivos.sha_de(d)} for s, d in gerados]})
    return eid
```

(`arquivos.sha_de(bytes) -> str` = `hashlib.sha256(d).hexdigest()`, acrescentar. `item_id = f"{eid}:{sha}"` para a mesma saída em versões diferentes não colidir na UNIQUE.)

```python
def _arquivos(conn, espelho_id) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT id AS documento_id, medicao_id, saida, nome, tamanho, sha256 FROM medicao_documentos "
        "WHERE espelho_id=? ORDER BY id", (espelho_id,))]


def detalhe(conn, espelho_id: int) -> dict | None:
    r = conn.execute("SELECT * FROM espelhos WHERE id=?", (espelho_id,)).fetchone()
    if r is None:
        return None
    d = dict(r)
    d["entradas"], d["saidas"] = json.loads(d["entradas"]), json.loads(d["saidas"])
    d["medicoes"] = [dict(m) for m in conn.execute(
        "SELECT m.id, m.tipo, m.estado, m.valor_protocolado_centavos FROM espelho_medicoes em "
        "JOIN medicoes m ON m.id=em.medicao_id WHERE em.espelho_id=? ORDER BY m.tipo", (espelho_id,))]
    d["arquivos"] = _arquivos(conn, espelho_id)
    d["envio"] = None
    if d["envio_id"]:
        e = conn.execute("SELECT id, remetente, para, copia, assunto, enviado_em FROM envios WHERE id=?", (d["envio_id"],)).fetchone()
        d["envio"] = {**dict(e), "para": json.loads(e["para"]), "copia": json.loads(e["copia"])}
    return d


def listar(conn, contrato_id: int) -> list[dict]:
    ids = [r[0] for r in conn.execute("SELECT id FROM espelhos WHERE contrato_id=? ORDER BY numero DESC, versao DESC",
                                      (contrato_id,))]
    return [detalhe(conn, i) for i in ids]
```

- [ ] **Step 4: Rodar** `pytest tests/test_espelhos.py -q` → 5 passed; suíte verde.

- [ ] **Step 5: Commit** — `git commit -m "feat: servico do espelho - previa, geracao versionada, arquivos e medicoes"`

---

### Task 10: Envio do espelho ao faturamento

**Files:**
- Modify: `backend/app/espelhos.py` (funções `previa_envio`, `enviar`)
- Test: `backend/tests/test_espelhos.py` (acrescentar)

**Interfaces:**
- Consumes: `correio.enviar_e_registrar(conn, usuario, tipo, para, copia, assunto, corpo_html, anexos) -> int`, `correio.MAX_TOTAL`, `medicoes.marcar_espelho_enviado`, `cadastro_geral.faturamento`, `entidades.emails_faturamento`.
- Produces: `espelhos.previa_envio(conn, espelho_id) -> dict` (`{"para", "copia", "assunto", "corpo", "anexos": [{"nome", "tamanho"}], "total", "limite", "avisos"}`); `espelhos.enviar(conn, usuario, espelho_id, para, copia, assunto, corpo) -> int` (envio_id). Regras: destinatários = `geral.faturamento.para` + `emails_faturamento` das entidades emissoras com papel `consorciada` que aparecem nas saídas; cópia = `geral.faturamento.copia`; assunto pelo template com `{medicao}` = `"{n}ª Medição[, Projeto][ e Reajuste]"` conforme as naturezas presentes; corpo em texto → HTML por parágrafos (`<p>`); anexos = os `.docx` do espelho; total acima de `correio.MAX_TOTAL` → aviso na prévia e `ValueError` no envio. Enviar: `enviar_e_registrar` (tipo `espelho`) → dentro de `db.mutacao`: `envio_medicoes` para cada medição, `espelhos.envio_id`, `marcar_espelho_enviado`. Espelho `substituido` não se envia.

- [ ] **Step 1: Testes (falham)** — com `monkeypatch.setenv("DASH_GRAPH_SIMULADOR", str(tmp_path / "sim"))`:

```python
def test_previa_do_envio_monta_destinatarios_assunto_e_anexos(ambiente):
    conn, u, cid = ambiente
    eid = espelhos.gerar(conn, u, cid, 23, "2026-01", {"medicao": 27850992})
    p = espelhos.previa_envio(conn, eid)
    assert p["para"] == ["f@lotufo.com"] and p["assunto"] == "Emissão NF - 23ª Medição - MT-402"
    assert [a["nome"] for a in p["anexos"]] == ["ESPELHO - MT-402 - 23ª Medição (01.2026).docx"]
    assert p["corpo"].startswith("Bom dia.")

def test_enviar_registra_liga_medicoes_e_avanca_o_estado(ambiente, tmp_path, monkeypatch):
    monkeypatch.setenv("DASH_GRAPH_SIMULADOR", str(tmp_path / "sim"))
    conn, u, cid = ambiente
    eid = espelhos.gerar(conn, u, cid, 23, "2026-01", {"medicao": 27850992})
    p = espelhos.previa_envio(conn, eid)
    envio_id = espelhos.enviar(conn, u, eid, p["para"], p["copia"], p["assunto"], p["corpo"] + "\nLink: x")
    d = espelhos.detalhe(conn, eid)
    assert d["envio_id"] == envio_id and d["envio"]["para"] == ["f@lotufo.com"]
    assert medicoes.detalhe(conn, d["medicoes"][0]["id"])["estado"] == "espelho_enviado"
    assert conn.execute("SELECT COUNT(*) FROM envio_medicoes WHERE envio_id=?", (envio_id,)).fetchone()[0] == 1
    gravado = json.loads((tmp_path / "sim" / "enviados" / "1.json").read_text(encoding="utf-8"))
    assert gravado["anexos"][0]["nome"].endswith(".docx") and "<p>Link: x</p>" in gravado["corpo"]

def test_falha_no_envio_nao_muda_nada(ambiente, monkeypatch):
    conn, u, cid = ambiente
    eid = espelhos.gerar(conn, u, cid, 23, "2026-01", {"medicao": 100})
    from app import correio, graph
    def quebra(*a, **k): raise graph.ErroGraph("Graph fora")
    monkeypatch.setattr(correio, "enviar_e_registrar", quebra)
    p = espelhos.previa_envio(conn, eid)
    with pytest.raises(graph.ErroGraph):
        espelhos.enviar(conn, u, eid, p["para"], p["copia"], p["assunto"], p["corpo"])
    d = espelhos.detalhe(conn, eid)
    assert d["envio_id"] is None and medicoes.detalhe(conn, d["medicoes"][0]["id"])["estado"] == "espelho_gerado"
    assert conn.execute("SELECT COUNT(*) FROM envios").fetchone()[0] == 0

def test_versao_substituida_nao_se_envia_e_reenvio_mantem_estado(ambiente, tmp_path, monkeypatch):
    monkeypatch.setenv("DASH_GRAPH_SIMULADOR", str(tmp_path / "sim"))
    conn, u, cid = ambiente
    e1 = espelhos.gerar(conn, u, cid, 23, "2026-01", {"medicao": 100})
    p = espelhos.previa_envio(conn, e1); espelhos.enviar(conn, u, e1, p["para"], p["copia"], p["assunto"], p["corpo"])
    e2 = espelhos.gerar(conn, u, cid, 23, "2026-01", {"medicao": 200}, motivo="corrigido")
    with pytest.raises(ValueError, match="substitu"):
        espelhos.previa_envio(conn, e1)
    p2 = espelhos.previa_envio(conn, e2)
    assert any("versão 1" in a for a in p2["avisos"])          # avisa que ja houve envio
    espelhos.enviar(conn, u, e2, p2["para"], p2["copia"], p2["assunto"], p2["corpo"])
    assert medicoes.detalhe(conn, espelhos.detalhe(conn, e2)["medicoes"][0]["id"])["estado"] == "espelho_enviado"
```

- [ ] **Step 2: Implementar** (em `espelhos.py`; `import html` e `from app import correio`):

```python
def _geral(conn) -> dict:
    r = conn.execute("SELECT valor FROM cadastro_geral WHERE chave='faturamento'").fetchone()
    if r is None:
        raise ValueError("cadastro geral sem `faturamento`: rode `cadastro aplicar` com geral.yaml")
    return json.loads(r["valor"])


def _rotulo_medicao(numero: int, saidas: list[dict]) -> str:
    nat = {s["natureza"] for s in saidas}
    partes = [f"{numero}ª Medição"] if "medicao" in nat else []
    if "projeto" in nat:
        partes.append(f"{numero}ª Projeto" if not partes else "Projeto")
    texto = ", ".join(partes)
    if "reajuste" in nat:
        texto = f"{texto} e Reajuste" if texto else f"{numero}ª Reajuste"
    return texto


def previa_envio(conn, espelho_id: int) -> dict:
    d = detalhe(conn, espelho_id)
    if d is None:
        raise ValueError("espelho não encontrado")
    if d["situacao"] != "vigente":
        raise ValueError("esta versão do espelho foi substituída; envie a versão vigente")
    g = _geral(conn)
    c = contratos.vigente(conn, d["contrato_id"])
    emissores = {s["emissor"] for s in d["saidas"]}
    extras = []
    for e in conn.execute("SELECT chave, emails_faturamento FROM entidades WHERE papel='consorciada' AND chave IS NOT NULL"):
        if e["chave"] in emissores and e["emails_faturamento"]:
            extras += json.loads(e["emails_faturamento"])
    para = list(dict.fromkeys(g["para"] + extras))
    obra = c["nome_curto"] or c["objeto"]
    assunto = g["assunto"].format(medicao=_rotulo_medicao(d["numero"], d["saidas"]),
                                  competencia=f"{d['competencia'][5:7]}/{d['competencia'][:4]}",
                                  obra=obra, instrumento=c["numero_instrumento"])
    anexos = [{"nome": a["nome"], "tamanho": a["tamanho"]} for a in d["arquivos"]]
    total = sum(a["tamanho"] for a in anexos)
    avisos = []
    if total > correio.MAX_TOTAL:
        avisos.append(f"anexos somam {total // 1024 // 1024} MB; o limite do e-mail é {correio.MAX_TOTAL // 1024 // 1024} MB")
    ja = conn.execute("SELECT versao FROM espelhos WHERE contrato_id=? AND numero=? AND competencia=? AND envio_id IS NOT NULL "
                      "ORDER BY versao DESC LIMIT 1", (d["contrato_id"], d["numero"], d["competencia"])).fetchone()
    if ja is not None:
        avisos.append(f"a versão {ja['versao']} deste espelho já foi enviada ao faturamento; este envio substitui")
    return {"para": para, "copia": list(g["copia"]), "assunto": assunto, "corpo": g["corpo"],
            "anexos": anexos, "total": total, "limite": correio.MAX_TOTAL, "avisos": avisos}


def _html(texto: str) -> str:
    return "".join(f"<p>{html.escape(l) or '&nbsp;'}</p>" for l in texto.strip().splitlines())


def enviar(conn, usuario: dict, espelho_id: int, para: list[str], copia: list[str], assunto: str, corpo: str) -> int:
    d = detalhe(conn, espelho_id)
    if d is None or d["situacao"] != "vigente":
        raise ValueError("esta versão do espelho foi substituída; envie a versão vigente")
    if not para:
        raise ValueError("informe ao menos um destinatário")
    anexos = [(a["nome"], arquivos.caminho_seguro(
        conn.execute("SELECT arquivo FROM medicao_documentos WHERE id=?", (a["documento_id"],)).fetchone()[0]).read_bytes())
              for a in d["arquivos"]]
    if sum(len(b) for _, b in anexos) > correio.MAX_TOTAL:
        raise ValueError("anexos acima do limite do e-mail; divida o envio")
    envio_id = correio.enviar_e_registrar(conn, usuario, "espelho", para, copia, assunto, _html(corpo), anexos)
    with db.mutacao(conn):
        for m in d["medicoes"]:
            conn.execute("INSERT OR IGNORE INTO envio_medicoes (envio_id, medicao_id) VALUES (?,?)", (envio_id, m["id"]))
            medicoes.marcar_espelho_enviado(conn, usuario["id"], m["id"])
        conn.execute("UPDATE espelhos SET envio_id=? WHERE id=?", (envio_id, espelho_id))
        auditoria.registrar(conn, usuario["id"], "espelho.enviar", "espelho", espelho_id, None,
                            {"envio_id": envio_id, "medicoes": [m["id"] for m in d["medicoes"]]})
    return envio_id
```

- [ ] **Step 3: Rodar** → verde. Se `_html` e `enviar_e_registrar` falharem por o simulador não estar configurado no `ambiente`, o fixture `ambiente` não define o simulador de propósito: só os testes de envio o definem.

- [ ] **Step 4: Commit** — `git commit -m "feat: envio do espelho ao faturamento pela conta da pessoa, ligado as medicoes"`

---

### Task 11: Rotas `api_espelhos.py`

**Files:**
- Create: `backend/app/api_espelhos.py`
- Modify: `backend/app/main.py:89-114` (registrar o router)
- Test: `backend/tests/test_api_espelhos.py`

**Interfaces:**
- Consumes: `espelhos.*`, `permissoes.exigir`, `api_auth.conexao`, `dinheiro.parse_brl`, `arquivos.caminho_seguro`, `api_medicoes.COMPETENCIA` (regex).
- Produces (todas com `exigir("editar_cadastros")`, GET sem CSRF; `diretoria` só GET):
  - `GET /api/contratos/{id}/espelho` → `{"regra": {"situacao", "entradas": [{chave, rotulo, natureza}], "saidas": N} | null, "espelhos": espelhos.listar}`
  - `POST /api/contratos/{id}/espelho/previa` `{numero, competencia, entradas: {chave: "BRL"}}` → `espelhos.previa` (422 em `ValueError`)
  - `POST /api/contratos/{id}/espelho` (201) `{numero, competencia, entradas, motivo?}` → `{"espelho_id"}`
  - `GET /api/espelhos/{id}` → `espelhos.detalhe` (404)
  - `GET /api/espelhos/{id}/arquivos/{documento_id}` → `FileResponse` do `.docx` com `filename` = nome do documento; 404 se não for do espelho
  - `GET /api/espelhos/{id}/envio` → `espelhos.previa_envio`
  - `POST /api/espelhos/{id}/enviar` `{para: [..], copia: [..], assunto, corpo}` → `{"envio_id"}` (422 em `ValueError`/`ErroGraph`)

- [ ] **Step 1: Testes (falham)** — `test_api_espelhos.py` com `client_admin` (conftest) + fixture que aplica `_cad_com_espelho` ativa no banco do `client_admin` (obter a conexão via `db.get_conn()` no mesmo `DASH_DB_PATH`) e define `DASH_GRAPH_SIMULADOR`:

```python
def test_fluxo_previa_gerar_baixar_enviar(client_admin, ambiente_api):
    cid = ambiente_api
    r = client_admin.get(f"/api/contratos/{cid}/espelho"); assert r.status_code == 200
    assert r.json()["regra"]["situacao"] == "ativa" and r.json()["espelhos"] == []
    corpo = {"numero": 23, "competencia": "2026-01", "entradas": {"medicao": "278.509,92"}}
    p = client_admin.post(f"/api/contratos/{cid}/espelho/previa", json=corpo)
    assert p.status_code == 200 and p.json()["saidas"][0]["valor"] == 27850992
    g = client_admin.post(f"/api/contratos/{cid}/espelho", json=corpo)
    assert g.status_code == 201
    eid = g.json()["espelho_id"]
    d = client_admin.get(f"/api/espelhos/{eid}").json()
    a = client_admin.get(f"/api/espelhos/{eid}/arquivos/{d['arquivos'][0]['documento_id']}")
    assert a.status_code == 200 and a.headers["content-type"].startswith("application/vnd.openxmlformats")
    assert "ESPELHO - MT-402" in a.headers["content-disposition"]
    pe = client_admin.get(f"/api/espelhos/{eid}/envio").json()
    e = client_admin.post(f"/api/espelhos/{eid}/enviar", json={k: pe[k] for k in ("para", "copia", "assunto", "corpo")})
    assert e.status_code == 200 and e.json()["envio_id"] == 1
    assert client_admin.get(f"/api/espelhos/{eid}").json()["medicoes"][0]["estado"] == "espelho_enviado"

def test_valor_invalido_e_obra_sem_regra_dao_422(client_admin, ambiente_api):
    cid = ambiente_api
    r = client_admin.post(f"/api/contratos/{cid}/espelho/previa", json={"numero": 1, "competencia": "2026-01", "entradas": {"medicao": "12.34"}})
    assert r.status_code == 422
    r = client_admin.post("/api/contratos/999/espelho/previa", json={"numero": 1, "competencia": "2026-01", "entradas": {}})
    assert r.status_code == 404

def test_arquivo_de_outro_espelho_da_404(client_admin, ambiente_api):
    cid = ambiente_api
    corpo = {"numero": 1, "competencia": "2026-01", "entradas": {"medicao": "1,00"}}
    e1 = client_admin.post(f"/api/contratos/{cid}/espelho", json=corpo).json()["espelho_id"]
    e2 = client_admin.post(f"/api/contratos/{cid}/espelho", json={**corpo, "numero": 2}).json()["espelho_id"]
    doc2 = client_admin.get(f"/api/espelhos/{e2}").json()["arquivos"][0]["documento_id"]
    assert client_admin.get(f"/api/espelhos/{e1}/arquivos/{doc2}").status_code == 404

def test_diretoria_le_mas_nao_gera(client, ambiente_api):
    # criar usuario diretoria + login como em conftest.client_admin; POST -> 403, GET -> 200
    ...
```

(Escrever o último teste completo copiando o padrão de login de `conftest.client_admin` com perfil `diretoria`.)

- [ ] **Step 2: Implementar `api_espelhos.py`**

```python
"""Espelho de NF: previa, geracao, download dos .docx e envio ao faturamento (spec §3 passos 1-2)."""
import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, constr

from app import arquivos, dinheiro, espelhos, graph
from app.api_auth import conexao
from app.api_medicoes import COMPETENCIA, MAX_INT64, _contrato_existe
from app.permissoes import exigir

router = APIRouter()
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


class EspelhoIn(BaseModel):
    numero: int = Field(ge=1, le=999)
    competencia: constr(pattern=COMPETENCIA)
    entradas: dict[str, constr(max_length=40)]
    motivo: constr(max_length=500) | None = None


class EnvioIn(BaseModel):
    para: list[constr(max_length=200)] = Field(max_length=30)
    copia: list[constr(max_length=200)] = Field(max_length=30)
    assunto: constr(min_length=1, max_length=300)
    corpo: constr(max_length=20000)


def _centavos(entradas: dict[str, str]) -> dict[str, int]:
    out = {}
    for k, v in entradas.items():
        try:
            out[k] = dinheiro.parse_brl(v) if v.strip() else 0
        except ValueError as e:
            raise HTTPException(422, f"{k}: {e}") from None
        if out[k] > MAX_INT64:
            raise HTTPException(422, f"{k}: valor acima do limite")
    return out


@router.get("/api/contratos/{contrato_id}/espelho")
def regra_e_espelhos(contrato_id: int, _=Depends(exigir("ver_paineis", com_csrf=False)),
                     conn: sqlite3.Connection = Depends(conexao)):
    _contrato_existe(conn, contrato_id)
    r = espelhos.regra_do_contrato(conn, contrato_id)
    regra = None if r is None else {"situacao": r["situacao"], "entradas": r["regra"]["entradas"],
                                    "saidas": len(r["regra"]["saidas"])}
    return {"regra": regra, "espelhos": espelhos.listar(conn, contrato_id)}


@router.post("/api/contratos/{contrato_id}/espelho/previa")
def previa(contrato_id: int, dados: EspelhoIn, _=Depends(exigir("editar_cadastros")),
           conn: sqlite3.Connection = Depends(conexao)):
    _contrato_existe(conn, contrato_id)
    try:
        return espelhos.previa(conn, contrato_id, dados.numero, dados.competencia, _centavos(dados.entradas))
    except ValueError as e:
        raise HTTPException(422, str(e)) from None


@router.post("/api/contratos/{contrato_id}/espelho", status_code=201)
def gerar(contrato_id: int, dados: EspelhoIn, usuario: dict = Depends(exigir("editar_cadastros")),
          conn: sqlite3.Connection = Depends(conexao)):
    _contrato_existe(conn, contrato_id)
    try:
        eid = espelhos.gerar(conn, usuario, contrato_id, dados.numero, dados.competencia, _centavos(dados.entradas), dados.motivo)
    except ValueError as e:
        raise HTTPException(422, str(e)) from None
    return {"espelho_id": eid}


def _espelho(conn, espelho_id) -> dict:
    d = espelhos.detalhe(conn, espelho_id)
    if d is None:
        raise HTTPException(404, "Espelho não encontrado")
    return d


@router.get("/api/espelhos/{espelho_id}")
def detalhe(espelho_id: int, _=Depends(exigir("ver_paineis", com_csrf=False)), conn: sqlite3.Connection = Depends(conexao)):
    return _espelho(conn, espelho_id)


@router.get("/api/espelhos/{espelho_id}/arquivos/{documento_id}")
def baixar(espelho_id: int, documento_id: int, _=Depends(exigir("ver_paineis", com_csrf=False)),
           conn: sqlite3.Connection = Depends(conexao)):
    doc = conn.execute("SELECT nome, arquivo FROM medicao_documentos WHERE id=? AND espelho_id=?",
                       (documento_id, espelho_id)).fetchone()
    if doc is None or not doc["arquivo"]:
        raise HTTPException(404, "Arquivo não encontrado")
    try:
        caminho = arquivos.caminho_seguro(doc["arquivo"])
    except ValueError:
        raise HTTPException(404, "Arquivo não encontrado") from None
    if not caminho.is_file():
        raise HTTPException(404, "Arquivo não encontrado")
    return FileResponse(caminho, media_type=DOCX, filename=doc["nome"])


@router.get("/api/espelhos/{espelho_id}/envio")
def previa_envio(espelho_id: int, _=Depends(exigir("editar_cadastros", com_csrf=False)),
                 conn: sqlite3.Connection = Depends(conexao)):
    _espelho(conn, espelho_id)
    try:
        return espelhos.previa_envio(conn, espelho_id)
    except ValueError as e:
        raise HTTPException(422, str(e)) from None


@router.post("/api/espelhos/{espelho_id}/enviar")
def enviar(espelho_id: int, dados: EnvioIn, usuario: dict = Depends(exigir("editar_cadastros")),
           conn: sqlite3.Connection = Depends(conexao)):
    _espelho(conn, espelho_id)
    try:
        eid = espelhos.enviar(conn, {"id": usuario["id"], "email": usuario["email"]}, espelho_id,
                              [e.strip().lower() for e in dados.para if e.strip()],
                              [e.strip().lower() for e in dados.copia if e.strip()], dados.assunto, dados.corpo)
    except (ValueError, graph.ErroGraph) as e:
        raise HTTPException(422, str(e)) from None
    return {"envio_id": eid}
```

Registrar em `main.py` ao lado dos outros: `app.include_router(api_espelhos.router)`. Conferir se `_contrato_existe` em `api_medicoes.py:84` já levanta 404 (ou devolve bool — adaptar).

- [ ] **Step 3: Rodar** → verde; suíte inteira verde. **Step 4: Commit** — `git commit -m "feat: rotas do espelho - previa, gerar, baixar docx, previa e envio do e-mail"`

---

### Task 12: Frontend — `Espelho.tsx` na aba Medições

**Files:**
- Create: `frontend/src/Espelho.tsx`, `frontend/src/Espelho.test.tsx`
- Modify: `frontend/src/Medicoes.tsx` (monta `<Espelho>` acima da tabela quando a obra tem regra ativa; esconde o formulário "Nova medição" nesse caso), `frontend/src/tokens.css` (classes `.espelho-*` mínimas, reaproveitando `.tabela-wrap`, `.btn`, `.btn--primario`, `.btn--pequeno`)

**Interfaces:**
- Consumes: as 7 rotas da Task 11, `api<T>()` de `api.ts`, `brl()` exportado por `Medicoes.tsx`, `competenciaBR`.
- Produces: `export default function Espelho({ contratoId, podeEditar, aoMudar }: { contratoId: number; podeEditar: boolean; aoMudar: () => void })` — `aoMudar` recarrega a lista de medições do pai depois de gerar/enviar.

Comportamento (spec §3 passos 1 e 2, T2.2):
1. Ao montar: `GET /api/contratos/{id}/espelho`. `regra === null` ou `situacao !== "ativa"` → o componente mostra uma linha discreta "Esta obra ainda gera o espelho pelo fluxo antigo" e nada mais (o formulário "Nova medição" do `Medicoes.tsx` continua). Regra ativa → botão **Gerar espelho** (só `podeEditar`).
2. Formulário: número (1–999), competência `MM/AAAA` (convertida para `AAAA-MM`), um campo de moeda por `regra.entradas` na ordem do cadastro com o `rotulo`; campo vazio = 0. Botão **Conferir** → `POST .../espelho/previa`; erro 422 aparece como `role="alert"`.
3. Prévia: tabela com uma linha por nota — colunas Nota (rótulo + emissor + município), Valor, Mão de obra, Material, INSS, ISS, IRRF, IBS, CBS, Líquido (colunas de tributo `null` mostram "—"); abaixo, "Medições: 23ª execução R$ …, 23ª reajuste R$ …" e os `avisos`. Botões **Gerar** (→ `POST .../espelho`; se `avisos` incluir "versão nova", pede motivo opcional) e **Voltar**.
4. Lista de espelhos do contrato (do GET): um cartão por espelho vigente com número, competência, versão, data, quem gerou, links de download de cada `.docx` (`/api/espelhos/{id}/arquivos/{documento_id}`), estado do envio ("Enviado em DD/MM por remetente → para" ou "Não enviado") e botões **Enviar ao faturamento** (vigente e `podeEditar`) e **Gerar de novo** (preenche o formulário com número e competência). Versões substituídas ficam num `<details>` "versões anteriores" com motivo.
5. Enviar: `GET /api/espelhos/{id}/envio` → painel com Para e Cópia (textareas, um e-mail por linha), Assunto (input), Corpo (textarea) e a lista de anexos com tamanho e o total contra o limite; `avisos` em destaque. Botão **Enviar** → `POST /api/espelhos/{id}/enviar`; sucesso mostra "Enviado. A medição passou a Espelho enviado." e chama `aoMudar()`.
6. Guarda de geração (padrão `let vigente = true` de `ContratoPagina.tsx:104`) em todos os efeitos.

- [ ] **Step 1: Teste vitest (falha)** — `Espelho.test.tsx` com `fetch` simulado (padrão de `MinhaConta.test.tsx`): (a) regra `null` → texto "fluxo antigo" e nenhum botão; (b) regra ativa com 2 entradas → clicar "Gerar espelho", preencher, "Conferir" → o `fetch` do `previa` recebe `{"numero":10,"competencia":"2026-05","entradas":{"medicao":"634.529,58","reajuste":"38.655,83"}}` e a tabela renderiza 4 linhas com "528.436,23"; (c) espelho vigente na lista com `envio: null` mostra "Não enviado" e o botão "Enviar ao faturamento".

- [ ] **Step 2: Implementar** o componente (tipos `Regra`, `Saida`, `EspelhoDetalhe`, `PreviaEnvio` espelhando os JSONs das Tasks 9–11; estado `passo: "lista" | "form" | "previa" | "envio"`). Em `Medicoes.tsx:134`, dentro do componente, montar `<Espelho contratoId={contratoId} podeEditar={podeEditar} aoMudar={carregar} />` antes da tabela e esconder o formulário "Nova medição" quando o `Espelho` informar regra ativa (levantar um `useState<boolean>` `regraAtiva` via prop callback `aoSaberRegra`).

- [ ] **Step 3: Rodar** `cd frontend && npm test && npx tsc --noEmit && npm run build` → verde. Os hooks do impeccable rodam como lint nas edições de `.tsx`; atender o que apontarem sem redesenhar a página.

- [ ] **Step 4: Verificação visual** — `.claude/launch.json` com a entrada `backend-review` (porta 8090, `DASH_DEV=1`, `DASH_SEM_JOBS=1`, `DASH_DB_PATH` no scratchpad, `DASH_GRAPH_SIMULADOR` no scratchpad) sobre uma CÓPIA do banco de produção com `cadastro aplicar` rodado nela; abrir MT-402 → Medições → Gerar espelho com 24ª/09/2026 e valores de teste; conferir tabela, download do `.docx`, prévia do e-mail e envio simulado (JSON em `enviados/`). Screenshot para o resumo. Remover a entrada do `launch.json` ao terminar.

- [ ] **Step 5: Commit** — `git commit -m "feat: tela do espelho - gerar, conferir por nota, baixar e enviar ao faturamento"`

---

### Task 13: Evidência do órgão anexada à medição (opcional do passo 1)

**Files:**
- Modify: `backend/app/api_espelhos.py` (rota de upload e download de documento local), `frontend/src/Espelho.tsx` (área de arrastar no cartão do espelho vigente)
- Test: `backend/tests/test_api_espelhos.py` (acrescentar 2)

**Interfaces:**
- Consumes: `arquivos.receber_pdf(UploadFile) -> (Path, sha)` (a função movida na Task 9; ela grava em `pasta_certidoes()` — parametrizar a pasta: `receber_pdf(arquivo, pasta: Path)`; `api_certidoes` passa `pasta_certidoes()`), `arquivos.conferir_parseavel`.
- Produces: `POST /api/medicoes/{id}/documentos` (`UploadFile` PDF, `Form tipo_doc='evidencia_orgao'`) → grava em `evidencias/<sha>.pdf`, insere `medicao_documentos` (`fonte='operacao'`, `tipo_doc='evidencia_orgao'`, `item_id=sha`, `arquivo`, `sha256`, `tamanho`), auditoria `medicao.documento`; 415 fora de PDF, 413 acima de 10 MB (mesmos códigos de `api_certidoes.upload`); `GET /api/medicoes/{id}/documentos/{documento_id}` → `FileResponse` (PDF ou DOCX pelo sufixo). `medicoes.detalhe` já devolve `documentos`; acrescentar `arquivo`, `tamanho`, `tipo_doc` ao SELECT de `medicoes.py:69-71`.

- [ ] **Step 1: Testes** — upload de um PDF de `conftest._pdf_com_texto("medição 23")` numa medição em `espelho_gerado` → 201, `medicoes.detalhe` lista o documento com `tipo_doc='evidencia_orgao'`, download devolve `application/pdf`; upload de `b"nao e pdf"` → 415.
- [ ] **Step 2: Implementar** rota e área de arrastar (input `type=file` estilizado como em `Certidoes.tsx`; lista "Informado pelo órgão: nome.pdf").
- [ ] **Step 3: Rodar** suíte + vitest. **Step 4: Commit** — `git commit -m "feat: evidencia do orgao anexada a medicao do espelho"`

---

### Task 14: Documentação, backlog e receita "espelho por onda"

**Files:**
- Modify: `docs/runbook.md` (seção nova "Espelho de NF"), `docs/backlog.md` (seção "Reestruturação: bloco 2"), `PRODUCT.md` (uma linha: espelho gerado no sistema para as obras ativas), `docs/superpowers/plans/2026-09-22-bloco-2-espelho.md` (Status)

- [ ] **Step 1: Runbook — "Espelho de NF"**: (a) como a operação usa (obra → Medições → Gerar espelho → Conferir → Gerar → Enviar ao faturamento; gerar de novo cria versão; protocolar continua pelo botão atual até o bloco 5); (b) onde ficam os arquivos (`dados/espelhos`, `dados/modelos`, `dados/evidencias`) e que o backup horário os NÃO cobre hoje (backlog); (c) **receita de uma onda nova**, passo a passo: 1. copiar os modelos da obra do motor antigo para `cadastro/modelos/espelho/<slug>/` com o nome da chave da saída; 2. escrever `cadastro/espelho/<slug>.yaml` pela tabela "Regra por obra" do plano com `situacao: prova`; 3. `cadastro validar`; 4. acrescentar em `test_espelho_cadastro_real.py` o gabarito da obra (as linhas do espelho real mais recente: valor, MO, material, INSS, ISS, IRRF, copiadas do `.docx` enviado ao faturamento ou do modelo); 5. suíte verde; 6. abrir o `.docx` gerado no Word e conferir contra o espelho real; 7. trocar para `situacao: ativa`, commit, merge com OK, `deploy.ps1`, `cadastro aplicar --ensaio` e `aplicar` em produção; 8. avisar as operadoras e desligar o fluxo do Power Automate daquela obra só depois do primeiro espelho real sair pelo sistema.
- [ ] **Step 2: Backlog** — linhas: IBS/CBS a confirmar com o faturamento (alíquota, redução, se entram no espelho); modelos sem controle (`periodo` e `valor_extenso` na Região Oeste; `ibs`/`cbs` em todos) a editar no Word antes da onda; período fora do mês civil (SES) e "PERÍODO: MAIO/2026" fixo; Deciolândia sem gabarito real (modelos são cópia do MT-402); Maternidade VG sem motor; backup não cobre `dados/espelhos|modelos|evidencias`; casador do RM ainda só casa `protocolada` (bloco 3 deve considerar `espelho_enviado`); `paineis.py` trata os estados novos como pendência genérica até o bloco 6; e-mails não confirmados no Step 1 da Task 8, se houver.
- [ ] **Step 3: Commit** — `git commit -m "docs: runbook do espelho, receita de onda e backlog do bloco 2"`

---

### Task 15: Suíte, gate Sol, pedido de merge e produção

- [ ] **Step 1: Suíte inteira** — `cd backend && .venv\Scripts\python -m pytest -q` (esperado ≈ 660) e `cd frontend && npm test && npm run build`. Nada pula.
- [ ] **Step 2: Gate Sol** sobre o diff inteiro da branch (`git diff master...bloco2-espelho | codex exec -m gpt-5.6-sol ...`, como no bloco 1): um round de correção; achados refutados vão para o backlog com a refutação. Pontos que o Sol vai olhar: reconstrução de `medicoes` (FKs, idempotência), arredondamento por tributo, `caminho_seguro`, tamanho dos anexos, `Mail.ReadWrite` continua sem leitura, transação do `gerar` (arquivo gravado antes do commit: se o commit falhar fica um `.docx` órfão pelo hash — aceitável, documentar).
- [ ] **Step 3: Atualizar o Status deste plano** e pedir o OK de merge ao Leonardo, com o resumo: o que muda para a operação, o que fica igual, o que exige ação dele (faturamento/IBS, ondas).
- [ ] **Step 4: Produção (com OK)** — `git merge --no-ff bloco2-espelho` em `master`, push; **backup** do banco (`dashboard-PRE-BLOCO2-<ts>.db` pela API `backup` do sqlite3, como em 2026-09-21); `scripts\deploy.ps1` (com frontend) — a migração 020 roda no start e reconstrói `medicoes` (629 linhas); conferir `/api/health`, dono da porta 80 novo, `PRAGMA foreign_key_check` vazio e `SELECT COUNT(*) FROM medicoes` = 629 em `?mode=ro`; então `cadastro aplicar --ensaio` (espera: `geral: 1 criado`, `espelho: 7 criados`, resto igual) e `aplicar` real com OK explícito, conferindo que `dados/modelos` recebeu 27 `.docx`. Registrar na memória de retomada.

## Self-review (feito ao escrever, 2026-09-22)

- **Cobertura da spec:** §2 estados (Task 1–2; `nota_emitida` só CHECK, declarado), medição nasce no espelho (Task 9), reajuste medição própria (decisão 3), versão anterior substituída com motivo (Task 9), protocolar sem nota segue pelo fluxo atual (decisão 4); §3 passos 1–2 (Tasks 9–13); §4.2 saídas, rateio com resto, retenções tabeladas, arredondamento por tributo, IBS/CBS (decisão 7), extenso (Task 3), modelos com controles (Tasks 5, 8); §4.3 prova por gabaritos e espelho real (Tasks 4, 8; regra do plano); §4.4 nomes (Task 4 `nome_arquivo`); §5.1 mecânica já existente, envio grava tudo, falha não muda estado (Task 10); §5.2 espelho ao faturamento com consorciadas (Task 10); §8 `geral.yaml`, `espelho/`, `modelos/` (Tasks 6–8); §12 `espelhos`, `envio_medicoes`, `medicao_documentos` local (Task 1); §15 guardas de arquivo, auditoria, testes, gate (Tasks 9, 13, 15). **Fora deste bloco, de propósito:** leitura da NF e `nota_emitida` (bloco 3), pacote e protocolo pelo sistema (bloco 5), tela inicial (bloco 6), remapeamento do legado (bloco 3), ZIP de vários espelhos (o e-mail leva um `.docx` por nota; download é por arquivo).
- **Placeholders:** o teste `test_diretoria_le_mas_nao_gera` da Task 11 está com `...` de propósito com a instrução de copiar o padrão de `conftest.client_admin`; os demais passos têm código. A Task 12 descreve o componente por comportamento e testes, não por código integral, porque o padrão visual vem dos arquivos vizinhos e dos hooks do impeccable.
- **Consistência de nomes:** `espelho.normalizar/calcular/valor_por_natureza/nome_arquivo/formatar_controles/campos_da_saida/CAMPOS_MODELO/CAMPOS_OPCIONAIS/TIPO_POR_NATUREZA/RegraInvalida`; `espelho_docx.controles/preencher/DocxInvalido`; `espelhos.regra_do_contrato/previa/gerar/detalhe/listar/previa_envio/enviar`; `medicoes.criar_para_espelho/marcar_espelho_enviado/ESTADOS_ESPELHO`; `arquivos.pasta/gravar_bytes/caminho_seguro/sha_de/receber_pdf`; `cadastro_aplicar.pasta_modelos`. `medicao_documentos.item_id` = `f"{espelho_id}:{sha}"` para espelhos e `sha` para evidências. Tabelas e colunas iguais entre a 020 (Task 1) e os SELECT/INSERT das Tasks 9–11.

