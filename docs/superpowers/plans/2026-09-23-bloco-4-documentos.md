# Bloco 4 (Documentos de protocolo): seis leitores de certidão, duas gavetas (certidões e regularidade mensal), exigência por órgão e migração das certidões. Plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** a pessoa arrasta o PDF de uma certidão; o sistema reconhece o tipo (federal, FGTS, trabalhista, estadual, municipal de Cuiabá, falência), a empresa (pelo CNPJ), a natureza (negativa ou positiva com efeito de negativa; positiva pura é recusada), a emissão e a validade (a da falência é calculada em 30 dias úteis com feriados nacionais), e grava; PDF sem texto vira digitação de poucos campos. Uma vez por mês a pessoa anexa o PDF de regularidade do DP (folha, SEFIP/eSocial, INSS) por competência. O sistema sabe o que cada órgão exige na medição e no reajuste (com as consorciadas nas obras de consórcio), mostra por empresa o que vale, o que vence e o que falta, avisa na tela de alertas, alimenta o checklist do protocolo, gera o ZIP "vigentes em DD/MM" por empresa, e carrega as certidões atuais por um comando com ensaio.

**Architecture:** leitor puro em `app/leitura_certidao.py` (texto → campos, seis perfis de regex portados da dashboard antiga e provados contra 47 certidões reais legíveis), contagem de dias úteis em `app/feriados.py`; serviço `app/documentos.py` (exigência por contrato e natureza, situação por empresa e tipo, regularidade, avisos, ZIP, gravação a partir da leitura ou da digitação, importação de pasta); `app/certidoes.py` continua a única fonte de "o que valia na data" e só ganha as colunas novas; `app/checklist.py` passa a responder pela exigência nova; `app/api_documentos.py` expõe; a tela `Documentos.tsx` substitui `Certidoes.tsx`. Migração 024 aditiva (nenhuma tabela reconstruída).

**Tech Stack:** Python 3.12, FastAPI, SQLite (migrações SQL em `backend/migrations`), pytest, pypdf (extração já existente em `leitura_pdf.py`, em subprocesso com limite de tempo), `zipfile` da biblioteca padrão, React 18 + Vite + vitest.

**Spec:** `docs/superpowers/specs/2026-09-21-reestruturacao-design.md` §3 passo 0, §9 (documentos de protocolo), §10.4 (tela), §11 (avisos "Documentos da empresa" e "Regularidade do mês"), §12 (`certidoes` seis tipos e natureza; `regularidade_mensal`), §14.3 (migração das certidões), §15, §17.4. Decisões: `docs/decisoes-reestruturacao-2026-09-16.md` seção T6 (2026-09-21). Regra de domínio levantada em 2026-09-23 na dashboard antiga (`js/features/certidoes.js`, `PERFIS`, `addDiasUteis`; `js/data/certidoes-empresas.js`, links e composição dos consórcios; `backup-sharepoint-2026-08-04/`, 63 PDFs e `Certidoes.json`).

**Status:** APROVADO pelo Leonardo em 2026-09-23 (decisões 1 a 17; a 16 ajustada para "manter o que a operadora envia"). Passou por revisão adversarial (Fable, 13 achados incorporados) e pelo levantamento das certidões enviadas por obra nos protocolos reais. Branch `bloco4-documentos`. **Andamento em 2026-09-23: Tasks 1 a 11 FEITAS e commitadas; gate Sol feito (15 achados, 9 corrigidos, 6 recusados com evidência, ver backlog); suíte 810 verdes no backend (1 falha = teste frágil antigo do hash do .docx, backlog) e 22 no frontend; verificação visual sobre cópia da produção feita (leitura, positiva recusada, repetida, digitação, regularidade, ZIP, checklist do Integra BRT com consorciadas, alertas). Desvios do texto do plano: `regularidade_propria` na entidade (Leblon manda a folha do próprio consórcio, achado ao fechar as lacunas); entidade desativada recusada também na digitação e na regularidade; conferências de repetida/regularidade antes de gravar o PDF (gate). Mergeado em `master` (921bfef) e EM PRODUÇÃO em 2026-09-23 15:25 (deploy com frontend, 024 aplicada, `cadastro aplicar` real). Falta: carga das certidões com OK próprio.**

## Global Constraints

- Banco: `backend/dados/dashboard.db` é o caminho padrão de dev E de produção nesta máquina. Testes usam `tmp_path` com `DASH_DB_PATH`. **Nunca semear nem apagar o banco padrão nem o de produção (`C:\DashboardLotufo\dados\dashboard.db`).** Leitura do banco de produção só com `?mode=ro`.
- Sem custo de API: nada de serviço pago por uso, OCR ou LLM. PDF sem texto: a pessoa digita (spec §9).
- Histórico não se apaga: certidão é linha nova a cada emissão (append-only, como hoje); regularidade também; vale a de maior validade (certidão) e a de maior competência (regularidade). Toda escrita dentro de `with db.mutacao(conn):`, com `auditoria.registrar` no mesmo commit.
- Migração 024 idempotente; `ALTER TABLE ... ADD COLUMN` no começo de linha (o runner pula a coluna que já existe).
- Arquivos recebidos: PDF validado por `arquivos.receber_pdf`/`blocos_validados` (tipo, `%PDF-`, 10 MB, abre no leitor), nome em disco pelo sha256 (`certidoes/<sha>.pdf`, `regularidades/<sha>.pdf`), caminho relativo à pasta do banco, download só dentro da pasta (`arquivos.caminho_seguro`). **Nenhum PDF de certidão entra no repositório**: os gabaritos são o TEXTO extraído.
- O sistema não lê caixa de e-mail nem SharePoint. A carga inicial lê uma PASTA LOCAL que o Leonardo baixou.
- "Hoje" é sempre `tempo.hoje_local()` (America/Cuiaba), nunca `date.today()`.
- Textos de interface, erros e commits em português. Commit `tipo: descricao` sem acento no assunto, terminando com `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Testes: `cd backend && .venv\Scripts\python -m pytest`. Teste novo em `backend/tests/test_<modulo>.py`, um teste focado por comportamento. Frontend: `cd frontend && npm test -- --run` e `npm run build` (tsc -b).
- Branch `bloco4-documentos`. Merge em `master` só com OK explícito do Leonardo. Subagentes, se houver, em Opus ou Fable; nunca Sonnet ou Haiku.

## Decisões deste plano em relação à spec (para aprovação)

1. **Seis tipos fixos, identificados por `chave`** (`federal`, `fgts`, `trabalhista`, `estadual`, `municipal`, `falencia`). A migração 024 dá chave e link de emissão aos três tipos já semeados (ids 1 a 3) e cria os outros três com `aplicavel_por_padrao = 0`. A partir deste bloco **quem diz o que é exigido é o cadastro do órgão** (decisão 6); `aplicavel_por_padrao` sobra só como regra de contrato SEM órgão (os criados pela tela antiga e os testes), para não mudar o comportamento deles.
2. **Um leitor novo substitui o genérico.** `app/leitura_certidao.py` com os seis perfis da antiga, em ordem (falência, FGTS, trabalhista, federal, estadual, municipal; o primeiro que casar vence), sobre o texto normalizado (NFKC, que desfaz a ligadura "ﬁ" e o espaço não quebrável da certidão federal; sem acento; maiúsculas; espaços colapsados). Saem `leitura_pdf.localizar/validar/ler_certidao` e as rotas `POST /api/certidoes/ler-pdf` e `POST /api/certidoes/upload`, para não haver duas leituras da mesma certidão. A extração do PDF (`leitura_pdf.texto_de_pdf_com_limite`, subprocesso, tetos) fica como está. **CNPJ**: o primeiro CNPJ com DV válido **que seja de uma empresa do cadastro**; senão o primeiro válido, e a leitura recusa com `empresa-desconhecida`. Isso resolve a municipal de Cuiabá, que cola a inscrição estadual no CNPJ (`12345678900.000.000/0001-00`).
3. **Natureza lida; positiva pura recusada, sem digitação que a contorne.** Federal, trabalhista e municipal pelo título ("negativa", "positiva ... com efeito(s) de negativa/negativo"); estadual pela sigla `CND`/`CPEND`/`CPD`; FGTS por "encontra-se em situação regular"; falência por "nada consta". **Consequência real**: as estaduais de Guaxe e Encomind de 22/08/2026 são CPD (a da Guaxe lista quatro certidões de dívida ativa na PGE) e seriam recusadas; a antiga as aceitava. No protocolo do Integra BRT essas consorciadas aparecem com "estadual faltando" e a pessoa segue com justificativa (spec: avisa e deixa seguir).
4. **Validade da falência = 30 dias úteis contados da emissão**, a emissão contando como 1º dia quando é dia útil, pulando sábado, domingo e feriados nacionais de lei (01/01, Paixão de Cristo, 21/04, 01/05, 07/09, 12/10, 02/11, 15/11, 20/11 a partir de 2024, 25/12). Carnaval e Corpus Christi são ponto facultativo e **contam como dia útil**, o que encurta a validade (lado seguro). A emissão é a data de "até a data de dd/mm/aaaa" (igual ao rodapé "dia dd/mm/aaaa"). Diverge da antiga (que não desconta feriado) em dois casos reais: Leblon e Rivoli emitidas em 03/08/2026 valem até 14/09 (a antiga gravou 11/09).
5. **A leitura automática manda; a pessoa confere, não edita.** Ao gravar, o servidor relê o PDF; os campos do formulário só valem quando o leitor não consegue (motivos `sem-texto`, `tipo-desconhecido`, `natureza-desconhecida`, `sem-cnpj`, `sem-emissao`, `sem-validade`, `datas-incoerentes`). Digitação: empresa, tipo, emissão, validade e natureza (padrão "negativa"); na falência a validade vazia é calculada. **Quando o PDF tem texto com CNPJ válido, a empresa digitada precisa ser uma delas** (evita gravar a CND da Guaxe na Lotufo; é a checagem que o validador antigo fazia). O PDF só vai para o disco depois de decidido gravar: recusa não deixa arquivo órfão. `positiva` e `empresa-desconhecida` não abrem digitação. Certidão já cadastrada (mesma empresa, tipo, emissão e validade) é recusada como repetida. **FGTS**: 9 dos 13 CRFs do backup não têm texto (salvos por driver de impressão); os 4 com texto são a página da Caixa salva pelo navegador ("Consulta Regularidade do Empregador.pdf"). O runbook orienta salvar assim.
6. **Exigência por contrato e natureza.** Medição e projeto usam `documentos_medicao` do órgão; reajuste usa `documentos_reajuste`. Exceção por contrato: `documentos_medicao`/`documentos_reajuste` no YAML do contrato, que substituem a lista do órgão. **Primeiro caso: Deciolândia** (contrato ativo do consórcio Via Parecis, SINFRA SUEF II), que ganha `documentos_medicao: []` e `documentos_reajuste: []`: não protocolamos por ela (pendência da spec §18, "quem protocola Deciolândia") e sem a exceção o sistema cobraria para sempre cinco certidões da Via Parecis que ninguém anexa. Entra no backlog para rever quando se souber quem protocola. Obra de consórcio exige as certidões **do consórcio e de cada consorciada**, cadastradas em `entidades.yaml` (`consorciadas:`). Composição conferida nos protocolos reais (levantamento de 2026-09-23, abaixo): Oriundi = Lotufo, Rivoli (ZIP de 03/08 com 15 certidões: Oriundi, Lotufo, Rivoli); **Complexo Leblon = Lotufo, Rivoli, Montante** (PDF de certidões da 25ª, 11/06: consórcio, Lotufo, Montante 00.000.000/0001-00 e Rivoli), o que faz **Montante entrar em `entidades.yaml` como consorciada**; Integra BRT = Lotufo, Guaxe, Encomind (pelos emissores do espelho; nenhum protocolo com certidão achado na caixa do Leonardo, a NF sai pela caixa do consórcio). Via Parecis e BR-163 ficam sem composição (não protocolamos por elas).

**Falência não é exigida em protocolo de medição nem de reajuste.** Nos 24 protocolos conferidos, todos levam as mesmas 5 (federal, FGTS, trabalhista, estadual, municipal); a única exceção é a NF da 6ª da Cavalaria (11/09), cujo ZIP levou também a falência, enquanto o ZIP de 14/09 usado em 5 Bairros, MT-388, MT-402 e Terminais BRT (mesma SINFRA) não levou. É incidente, não regra. A falência aparece de verdade no **apostilamento do reajuste anual** da Região Oeste (Prefeitura de Cuiabá pediu "certidão de falência e concordata", contrato social e balanço em 25/06): isso é o pleito de reajuste do bloco 7, não o protocolo. Neste bloco a falência é lida, guardada e vai no ZIP de licitação.
7. **Regularidade mensal**: gaveta própria (`regularidades`), um PDF por empresa e competência, append-only, vale a de maior competência. **Exigida da Lotufo, salvo consórcio com folha própria**: o pacote do Oriundi de 03/08 levou a da Lotufo (`052026 - LOTUFO ENGENHARIA.pdf`), mas o do Leblon na 25ª (11/06) é a folha do próprio consórcio (`042026 - CONSÓRCIO COMPLEXO LEBLON.pdf`: CNO, contrato 012/2024 e folha do CNPJ 00.000.000/0001-00). A entidade ganha `regularidade_propria` (migração 024), marcado no Complexo Leblon. **Em que órgãos**: `regularidade` entra em `documentos_medicao` das cinco superintendências da SINFRA (confirmado nos protocolos de 22/06, 06/07, 19/08 e 16/09); não entra no reajuste SINFRA (IN 001/2024 art. 12 §3º); a MTPAR não leva (o CT-301 de 16/09 é um PDF único de 797 KB, e a regularidade sozinha tem de 3,5 a 4,1 MB); SES e prefeituras ficam fora até aparecer evidência. **Competência esperada**: a do mês menos 2 a partir do dia 10; antes do dia 10 a do mês menos 3 ainda serve (22/06 levou 04/2026; 03/08 levou 05/2026; 16/09 levou 07/2026). O sistema não lê o PDF (é o pacote do DP, em parte escaneado): a competência é digitada, pré-preenchida pelo nome do arquivo (`042026 - LOTUFO ENGENHARIA.pdf` → 2026-04).
8. **Comprovante do CNO fica para o bloco 5.** Ele é da obra e o "sistema junta os dois" acontece na montagem do pacote. Aqui nada muda no cadastro do contrato (o campo `cno` já existe).
9. **Avisos neste bloco substituem os de certidão em `paineis.alertas`** (a tela de alertas atual, até a tela inicial do bloco 6): `documentos_empresa`, uma linha por empresa com contrato ativo, só tipos exigidos por algum contrato ativo, com o que venceu, o que falta e o que vence ("Lotufo: municipal vencida em 20/09; FGTS vence em 4 dias"); limiar de 7 dias quando a validade total da certidão é de até 31 dias (FGTS, municipal) e 15 para as demais, calculado pela própria certidão. `regularidade_mes` a partir do dia 10 ("Lotufo: regularidade de 07/2026 não anexada; a última é de 06/2026"). Saem `certidao_vencida_ou_ausente` e `certidao_vencendo`. Certidão não vai para a diretoria (spec §10.5).
10. **Checklist do protocolo pela exigência nova.** `checklist.pronto_para_protocolar(conn, contrato_id, natureza)` lista empresa × tipo exigido (com as consorciadas) e a regularidade; `registrar_protocolo` passa a natureza da medição. O comportamento fica igual: pendência trava o botão até a pessoa marcar "protocolar apesar das pendências" com justificativa auditada.
11. **Tela "Documentos de protocolo" substitui "Certidões".** Uma área de arrastar para a página inteira (a empresa vem do CNPJ); um cartão por empresa com os seis tipos (vigente até, vence em N dias, vencida em, falta, não exigida), link "Emitir" e botão "copiar CNPJ" (os portais não aceitam CNPJ na URL), a regularidade da empresa com a competência e o botão de anexar, e "Baixar ZIP das vigentes em [data]". Somem da tela o cadastro de entidade e de tipo (já respondem 409 em produção), "não se aplica" e "revogar"; as rotas antigas (`GET /api/certidoes`, entidade, tipo, não se aplica, estado) ficam no backend até o bloco 9, que remove o código da fase 3.
12. **`nome_curto` da entidade** (novo em `entidades.yaml`) nomeia os arquivos do ZIP no padrão que os órgãos já recebem da antiga: `Lotufo - FGTS - 2026-09-28.pdf` dentro de `Certidoes - Lotufo - 2026-09-23.zip`.
13. **Carga das certidões por comando**: `python -m app.cli documentos importar <pasta> --usuario <e-mail> [--ensaio]` percorre os PDFs da pasta (recursivo), lê com o leitor novo e grava só os **vigentes hoje**; relatório com gravadas, repetidas, vencidas, positivas, sem leitura (estas a operação digita pela tela). Fonte: a biblioteca `Certidoes` do site GestaoContratosFaturamento, baixada para uma pasta local no dia (o sistema não lê SharePoint). Rodar em produção é ato separado, com backup e OK.
14. **Fixtures textuais de 12 certidões reais** (do backup de 04/08/2026) em `backend/tests/fixtures/certidoes/*.txt`, como no bloco 3; o nome do servidor do TJMT que assina a falência é trocado por `SERVIDOR DO TJMT`. CNPJ, razão social e endereço das empresas do grupo ficam (constam da certidão pública). PDF não entra.
15. **"Vale a de maior validade" passa a ser literal.** `certidoes.vigente` hoje escolhe a de emissão mais recente (`ORDER BY emissao DESC, id DESC`); coincide com a de maior validade enquanto a validade de cada tipo é fixa, mas diverge se alguém anexar uma emissão antiga depois da nova. A ordem passa a `validade DESC, emissao DESC, id DESC` (spec §9), com teste.
16. **Reajuste da SINFRA segue o que a operadora envia (decisão do Leonardo, 2026-09-23).** A IN 001/2024 art. 12 §3º exige só a estadual no reajuste, mas na prática vão as mesmas 5 da medição (NF do reajuste da 46ª do Oriundi, 03/08: mesmo ZIP de 15 certidões; nas outras obras SINFRA medição e reajuste vão no mesmo e-mail). As cinco superintendências da SINFRA ficam com `documentos_reajuste: [federal, fgts, trabalhista, estadual, municipal]`, sem `regularidade` (o reajuste do Oriundi não levou o pacote do DP). Isto altera a spec §9 ("no reajuste da SINFRA, só a estadual").
17. **Gate Sol ao final**: a branch toca arquivo externo (leitores) e o CLAUDE.md pede o gate; no bloco 3 o Leonardo o dispensou. Proposta: fazer, com o diff inteiro.

## Pendências externas (não bloqueiam a implementação)

- Pasta atual da biblioteca `Certidoes` (SharePoint GestaoContratosFaturamento) baixada para rodar a carga (decisão 13). O backup de 04/08 serve para ensaio; em produção vale a pasta do dia.
- Orientar as operadoras a salvar o CRF do FGTS pela página da Caixa ("Imprimir → Salvar como PDF" do navegador), que sai com texto (decisão 5).
- SES e prefeituras: se algum protocolo delas levar a regularidade do DP, incluir `regularidade` na lista do órgão (uma linha no YAML).

## Estrutura de arquivos

| Arquivo | Responsabilidade |
|---|---|
| `backend/migrations/024_documentos.sql` | `certidao_tipos.chave`/`link_emissao` + três tipos novos; `certidoes.natureza`/`leitura`/`nome_original`; `regularidades`; `entidades.nome_curto`; `entidade_consorciadas`; `contratos.documentos` |
| `backend/app/feriados.py` | feriados nacionais e soma de dias úteis |
| `backend/app/leitura_certidao.py` | leitor puro: texto → tipo, natureza, CNPJ, emissão, validade, número, evidência; `Recusa(motivo)` |
| `backend/app/certidoes.py` | `registrar` aceita natureza, leitura e nome original |
| `backend/app/documentos.py` | exigência, situação, regularidade, painel, avisos, ZIP, gravar lida/digitada, importar pasta |
| `backend/app/checklist.py` | veredito pela exigência nova (natureza, consorciadas, regularidade) |
| `backend/app/medicoes.py` | `registrar_protocolo` passa a natureza |
| `backend/app/paineis.py` | alertas de documentos no lugar de `_alertas_de_certidao` |
| `backend/app/api_documentos.py` | rotas novas; `backend/app/main.py` inclui o router |
| `backend/app/api_certidoes.py` | sai `ler-pdf` e `upload`; checklist aceita `natureza` |
| `backend/app/leitura_pdf.py` | sai a seção "localização por regex" e o validador genérico |
| `backend/app/cadastro_arquivos.py`, `cadastro_aplicar.py` | `nome_curto`, `consorciadas`, listas de documentos validadas, exceção por contrato |
| `backend/app/cli.py` | subcomando `documentos importar` |
| `cadastro/entidades.yaml`, `cadastro/orgaos.yaml` | nomes curtos, composição dos consórcios, regularidade na SINFRA |
| `backend/tests/fixtures/certidoes/*.txt` | texto real de 12 certidões |
| `frontend/src/Documentos.tsx` (+ `.test.tsx`) | tela nova; sai `Certidoes.tsx` |
| `frontend/src/App.tsx`, `rota.tsx`, `Alertas.tsx`, `ContratoPagina.tsx`, `Medicoes.tsx` | navegação, alertas novos, checklist com empresa e natureza |
| `docs/runbook.md`, `docs/backlog.md` | operação, carga, pendências |

## Os seis perfis do leitor (texto normalizado: sem acento, maiúsculas, espaços colapsados, "Nº" vira "NO")

| Tipo | Reconhece por | Natureza | Emissão | Validade | Número |
|---|---|---|---|---|---|
| falencia | `FALENCIA E (RECUPERACAO JUDICIAL\|CONCORDATA)` | `NADA CONSTA` → negativa; outro `CONSTA` → positiva | `ATE A DA[TR]A DE dd/mm/aaaa` | 30 dias úteis (decisão 4) | `NO: 25958385` |
| fgts | `CERTIFICADO DE REGULARIDADE DO FGTS` | `ENCONTRA-SE EM SITUACAO REGULAR` → negativa | início de `VALIDADE: dd/mm/aaaa A dd/mm/aaaa` | fim da mesma faixa | `CERTIFICACAO NUMERO: \d{10,30}` |
| trabalhista | `DEBITOS TRABALHISTAS` | título (ver abaixo) | `EXPEDICAO: dd/mm/aaaa` | `VALIDADE: dd/mm/aaaa` | `CERTIDAO NO: 57104469/2026` |
| federal | `TRIBUTOS FEDERAIS E A DIVIDA ATIVA DA UNIAO` | título | `DO DIA dd/mm/aaaa` | `VALIDA ATE dd/mm/aaaa` | código de controle `DB05.42F6.A9AE.2CD8` |
| estadual | `GERIDOS PELA PROCURADORIA-GERAL DO ESTADO` | sigla `CND`/`CPEND`/`CPD NO` | `DATA DA EMISSAO: dd/mm/aaaa` | `VALIDA ATE: dd/mm/aaaa` | `NUMERO DE AUTENTICACAO: ...` |
| municipal | `PREFEITURA MUNICIPAL DE CUIABA` | título | `CUIABA/MT, QUARTA-FEIRA, 24 DE JUNHO DE 2026` | `VALIDA ATE 24 DE JULHO DE 2026` | primeiro `\d{4,10}/\d{4}` (`993266/2026`) |

Título (federal, trabalhista, municipal, e estadual sem sigla): `POSITIVA ... COM EFEITO(S) (DE) NEGATIV(O|A)` (até 60 caracteres entre as partes) → positiva com efeito de negativa; `CERTIDAO NEGATIVA DE DEBITOS` → negativa; `CERTIDAO POSITIVA` → positiva; nada disso → `natureza-desconhecida`.

**Prova feita ao escrever este plano (2026-09-23, protótipo no scratchpad):** sobre os 63 PDFs do backup de 04/08/2026, 49 têm texto; o leitor acertou tipo, CNPJ, emissão e validade de 45 contra o `Certidoes.json` que a antiga gravou, e o número de todas as 45; as outras 2 são as falências de 03/08 (decisão 4, diferença esperada); recusou as 2 CPD (Guaxe, Encomind) como `positiva` e os 14 sem texto como `sem-texto`.

---

### Task 1: Migração 024

**Files:**
- Create: `backend/migrations/024_documentos.sql`
- Test: `backend/tests/test_migracao_024.py`

**Interfaces:**
- Produces: `certidao_tipos.chave` (único quando não nulo: `federal`, `fgts`, `trabalhista`, `estadual`, `municipal`, `falencia`), `certidao_tipos.link_emissao`; `certidoes.natureza` (`negativa`|`positiva_efeito_negativa`|NULL), `certidoes.leitura` (`automatica`|`manual`|NULL), `certidoes.nome_original`; tabela `regularidades(id, entidade_id, competencia 'AAAA-MM', arquivo, sha256, tamanho, nome_original, usuario_id, criado_em)`; `entidades.nome_curto`; tabela `entidade_consorciadas(consorcio_id, consorciada_id)`; `contratos.documentos` (JSON `{"medicao": [...], "reajuste": [...]}` ou NULL).

- [ ] **Step 1: Escrever o teste**

```python
# backend/tests/test_migracao_024.py
"""Migracao 024: seis tipos com chave, natureza da certidao, regularidade mensal, consorciadas."""
import sqlite3

import pytest

from app import db


@pytest.fixture
def conn(tmp_path, monkeypatch):
    monkeypatch.setenv("DASH_DB_PATH", str(tmp_path / "t.db"))
    c = db.get_conn(); db.migrate(c)
    yield c
    c.close()


def test_seis_tipos_com_chave_e_link(conn):
    linhas = conn.execute("SELECT chave, link_emissao, aplicavel_por_padrao FROM certidao_tipos "
                          "WHERE chave IS NOT NULL ORDER BY id").fetchall()
    assert [r[0] for r in linhas] == ["federal", "fgts", "trabalhista", "estadual", "municipal", "falencia"]
    assert all(r[1].startswith("https://") for r in linhas)
    assert [r[2] for r in linhas] == [1, 1, 1, 0, 0, 0]


def test_natureza_e_regularidade_com_check(conn):
    conn.execute("INSERT INTO certidoes (entidade_id, tipo_id, emissao, validade, arquivo, sha256, origem, natureza, leitura) "
                 "VALUES (1, 1, '2026-06-24', '2026-12-21', 'certidoes/x.pdf', ?, 'upload', 'positiva_efeito_negativa', 'automatica')",
                 ("a" * 64,))
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO certidoes (entidade_id, tipo_id, emissao, validade, arquivo, sha256, origem, natureza) "
                     "VALUES (1, 1, '2026-06-24', '2026-12-21', 'certidoes/x.pdf', ?, 'upload', 'positiva')", ("a" * 64,))
    conn.execute("INSERT INTO regularidades (entidade_id, competencia, arquivo, sha256, tamanho) "
                 "VALUES (1, '2026-07', 'regularidades/x.pdf', ?, 10)", ("b" * 64,))
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO regularidades (entidade_id, competencia, arquivo, sha256, tamanho) "
                     "VALUES (1, '07/2026', 'regularidades/x.pdf', ?, 10)", ("b" * 64,))


def test_reexecucao_nao_duplica_tipos(conn):
    sql = (db.MIGRATIONS_DIR / "024_documentos.sql").read_text(encoding="utf-8")
    conn.executescript(db._sem_alters_ja_aplicados(conn, sql))
    assert conn.execute("SELECT COUNT(*) FROM certidao_tipos WHERE chave IS NOT NULL").fetchone()[0] == 6
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `cd backend && .venv\Scripts\python -m pytest tests/test_migracao_024.py -v`
Expected: FAIL (`no such column: chave`).

- [ ] **Step 3: Escrever a migração**

```sql
-- 024: documentos de protocolo (bloco 4, spec 2026-09-21 §9 e §12). ADITIVA: nenhuma tabela e'
-- reconstruida. Os tres tipos semeados na 006 ganham chave e link; os outros tres nascem com
-- aplicavel_por_padrao=0 porque, a partir deste bloco, quem diz o que e' exigido e' o cadastro do
-- orgao (documentos.exigidos); aplicavel_por_padrao so' vale para contrato sem orgao.
ALTER TABLE certidao_tipos ADD COLUMN chave TEXT;
ALTER TABLE certidao_tipos ADD COLUMN link_emissao TEXT;
UPDATE certidao_tipos SET chave='federal',
  link_emissao='https://servicos.receitafederal.gov.br/servico/certidoes/#/home/cnpj'
  WHERE id=1 AND nome='CND Federal (RFB/PGFN)';
UPDATE certidao_tipos SET chave='fgts',
  link_emissao='https://consulta-crf.caixa.gov.br/consultacrf/pages/consultaEmpregador.jsf'
  WHERE id=2 AND nome='CRF/FGTS';
UPDATE certidao_tipos SET chave='trabalhista',
  link_emissao='https://cndt-certidao.tst.jus.br/gerarCertidao.faces'
  WHERE id=3 AND nome='CNDT';
INSERT OR IGNORE INTO certidao_tipos (nome, jurisdicao, emissor, aplicavel_por_padrao, chave, link_emissao) VALUES
 ('Certidão Conjunta Estadual (SEFAZ/PGE-MT)', 'estadual', 'SEFAZ-MT / PGE-MT', 0, 'estadual',
  'https://www.sefaz.mt.gov.br/cnd/certidao/servlet/ServletRotdAberto?origem=60'),
 ('Certidão de Débitos Gerais (Prefeitura de Cuiabá)', 'municipal', 'Prefeitura de Cuiabá', 0, 'municipal',
  'https://portalfazenda.cuiaba.mt.gov.br/portalfazenda/PortalContribuinte/EmitirCertidao'),
 ('Certidão de Falência e Recuperação Judicial (TJMT)', 'estadual', 'TJMT', 0, 'falencia',
  'https://sec.tjmt.jus.br/');
CREATE UNIQUE INDEX IF NOT EXISTS certidao_tipos_chave ON certidao_tipos (chave) WHERE chave IS NOT NULL;

-- Natureza lida do documento; positiva pura nunca e' gravada (o leitor recusa). NULL = linha
-- anterior a este bloco. `leitura`: se os campos vieram do leitor ou da digitacao.
ALTER TABLE certidoes ADD COLUMN natureza TEXT CHECK (natureza IN ('negativa','positiva_efeito_negativa'));
ALTER TABLE certidoes ADD COLUMN leitura TEXT CHECK (leitura IN ('automatica','manual'));
ALTER TABLE certidoes ADD COLUMN nome_original TEXT;

-- Regularidade mensal do DP (folha, SEFIP/eSocial, INSS): um PDF por empresa e competencia,
-- append-only; vale a de maior competencia.
CREATE TABLE IF NOT EXISTS regularidades (
    id INTEGER PRIMARY KEY,
    entidade_id INTEGER NOT NULL REFERENCES entidades(id),
    competencia TEXT NOT NULL CHECK (competencia GLOB '[0-9][0-9][0-9][0-9]-[0-1][0-9]'),
    arquivo TEXT NOT NULL,
    sha256 TEXT NOT NULL CHECK (length(sha256) = 64),
    tamanho INTEGER NOT NULL,
    nome_original TEXT,
    usuario_id INTEGER REFERENCES usuarios(id),
    criado_em TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_regularidades_ent ON regularidades (entidade_id, competencia);

-- Nome curto para arquivos (ZIP) e telas; composicao dos consorcios (as certidoes da obra de
-- consorcio sao as do consorcio E as de cada consorciada).
ALTER TABLE entidades ADD COLUMN nome_curto TEXT;
CREATE TABLE IF NOT EXISTS entidade_consorciadas (
    consorcio_id INTEGER NOT NULL REFERENCES entidades(id),
    consorciada_id INTEGER NOT NULL REFERENCES entidades(id),
    PRIMARY KEY (consorcio_id, consorciada_id)
);

-- Excecao por contrato a lista de documentos do orgao (JSON {"medicao": [...], "reajuste": [...]}).
ALTER TABLE contratos ADD COLUMN documentos TEXT;
```

- [ ] **Step 4: Ajustar as contagens da matriz antiga**

`tests/test_certidoes.py:87`, `:95` e `:97` contam entidades × tipos em `certidoes.painel` com 3 tipos fixos (3, 6, 3). Com seis tipos: trocar o número fixo por `len(certidoes.tipos(conn))` vezes o número de entidades.

- [ ] **Step 5: Rodar e ver passar**

Run: `cd backend && .venv\Scripts\python -m pytest tests/test_migracao_024.py tests/test_certidoes.py tests/test_checklist.py -v`
Expected: PASS (o checklist da fase 3 não muda: os tipos novos nascem fora do padrão).

- [ ] **Step 6: Commit**

```bash
git add backend/migrations/024_documentos.sql backend/tests/test_migracao_024.py backend/tests/test_certidoes.py
git commit -m "feat: migracao 024 - seis tipos de certidao com chave, natureza, regularidade mensal, consorciadas"
```

---

### Task 2: Cadastro — nome curto, consorciadas, listas de documentos, exceção por contrato

**Files:**
- Modify: `backend/app/cadastro_arquivos.py` (constante `DOCUMENTOS`; validação das listas no órgão e no contrato; `nome_curto` e `consorciadas` na entidade)
- Modify: `backend/app/cadastro_aplicar.py` (`_entidades` grava `nome_curto`; `_consorciadas` novo; `documentos` em `_CAMPOS_CONTRATO`)
- Modify: `cadastro/entidades.yaml`, `cadastro/orgaos.yaml`
- Test: `backend/tests/test_cadastro_arquivos.py`, `backend/tests/test_cadastro_aplicar.py`

**Interfaces:**
- Produces: `cadastro_arquivos.DOCUMENTOS = ("federal", "fgts", "trabalhista", "estadual", "municipal", "falencia", "regularidade")`; entidade normalizada ganha `nome_curto: str` e `consorciadas: list[str]` (chaves); contrato normalizado ganha `documentos: dict | None` (`{"medicao": [...], "reajuste": [...]}` só com as chaves presentes no YAML).

- [ ] **Step 1: Testes do carregador**

```python
# acrescentar em backend/tests/test_cadastro_arquivos.py
def test_lista_de_documentos_do_orgao_so_aceita_chaves_conhecidas(tmp_path):
    erros = _erros(_escrever(tmp_path, orgaos=[{**ORGAO, "documentos_medicao": ["federal", "cnd-inventada"]}]))
    assert any("documentos_medicao" in e for e in erros)


def test_consorciadas_normalizadas_e_conferidas(tmp_path):
    rivoli = {"chave": "rivoli", "nome": "Rivoli", "cnpj": "00.000.000/0005-00", "papel": "consorciada"}
    leblon = {"chave": "complexo-leblon", "nome": "Consórcio Complexo Leblon", "nome_curto": "Complexo Leblon",
              "cnpj": "00.000.000/0004-00", "papel": "consorcio", "consorciadas": ["lotufo", "rivoli"]}
    cad = ca.preparar(_escrever(tmp_path, entidades=[ENTIDADE, rivoli, leblon]))
    e = {x["chave"]: x for x in cad["entidades"]}
    assert e["complexo-leblon"]["consorciadas"] == ["lotufo", "rivoli"]
    assert e["complexo-leblon"]["nome_curto"] == "Complexo Leblon"
    assert e["rivoli"]["nome_curto"] == "Rivoli"          # sem nome_curto, vale o nome
    erros = _erros(_escrever(tmp_path, entidades=[ENTIDADE, {**leblon, "consorciadas": ["lotufo", "nao-existe"]}]))
    assert any("consorciadas" in x for x in erros)
    erros = _erros(_escrever(tmp_path, entidades=[{**ENTIDADE, "consorciadas": ["lotufo"]}]))
    assert any("consorciadas" in x for x in erros)       # so' consorcio tem composicao


def test_excecao_de_documentos_no_contrato(tmp_path):
    cad = ca.preparar(_escrever(tmp_path, contratos=[{**CONTRATO, "documentos_reajuste": ["estadual"]}]))
    assert cad["contratos"][0]["documentos"] == {"reajuste": ["estadual"]}
    assert ca.preparar(_escrever(tmp_path))["contratos"][0]["documentos"] is None
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `cd backend && .venv\Scripts\python -m pytest tests/test_cadastro_arquivos.py -v`
Expected: FAIL nos três testes novos.

- [ ] **Step 3: Implementar no carregador**

Em `cadastro_arquivos.py`, junto das constantes:

```python
DOCUMENTOS = ("federal", "fgts", "trabalhista", "estadual", "municipal", "falencia", "regularidade")


def _lista_documentos(valor, onde: str, erros: list[str]) -> list[str] | None:
    """Lista de documentos exigidos (orgao ou excecao do contrato). None = campo ausente."""
    if valor is None:
        return None
    if not isinstance(valor, list) or any(v not in DOCUMENTOS for v in valor) or len(set(valor)) != len(valor):
        erros.append(f"{onde}: use uma lista, sem repetição, de {', '.join(DOCUMENTOS)}")
        return None
    return list(valor)
```

No laço dos órgãos, antes do `orgaos.append`:

```python
        for campo in ("documentos_medicao", "documentos_reajuste"):
            _lista_documentos(o.get(campo), f"{onde}: {campo}", erros)
```

No laço das entidades, o dicionário ganha:

```python
        consorciadas = [str(x) for x in (e.get("consorciadas") or [])]
        ents.append({..., "nome_curto": str(e.get("nome_curto") or e.get("nome") or "").strip(),
                     "consorciadas": consorciadas})
```

Depois do laço (antes de `chaves_orgao`), a conferência da composição:

```python
    por_chave = {x["chave"]: x for x in ents}
    for x in ents:
        if not x["consorciadas"]:
            continue
        onde = f"entidades.yaml[{x['chave']}]: consorciadas"
        if x["papel"] != "consorcio":
            erros.append(f"{onde}: só consórcio tem composição")
        for ch in x["consorciadas"]:
            alvo = por_chave.get(ch)
            if alvo is None or alvo["papel"] not in ("lotufo", "consorciada"):
                erros.append(f"{onde}: {ch!r} não é a Lotufo nem uma consorciada cadastrada")
        if len(set(x["consorciadas"])) != len(x["consorciadas"]):
            erros.append(f"{onde}: repetida")
```

Em `_contrato`, depois de montar `c`:

```python
    docs = {}
    for chave, campo in (("medicao", "documentos_medicao"), ("reajuste", "documentos_reajuste")):
        lista = _lista_documentos(bruto.get(campo), f"{onde}: {campo}", erros)
        if lista is not None:
            docs[chave] = lista
    c["documentos"] = docs or None
```

- [ ] **Step 4: Teste do aplicador**

```python
# acrescentar em backend/tests/test_cadastro_aplicar.py
def test_consorciadas_e_nome_curto_aplicados_e_idempotentes(conn):
    rivoli = {"chave": "rivoli", "nome": "Rivoli", "cnpj": "00000000000500", "papel": "consorciada",
              "coligada_rm": None, "sigla_oficio": None, "nome_curto": "Rivoli", "consorciadas": []}
    leblon = {"chave": "complexo-leblon", "nome": "Consórcio Complexo Leblon", "cnpj": "00000000000400",
              "papel": "consorcio", "coligada_rm": 17, "sigla_oficio": "CCL", "nome_curto": "Complexo Leblon",
              "consorciadas": ["lotufo", "rivoli"]}
    lotufo = {**_cad()["entidades"][0], "nome_curto": "Lotufo", "consorciadas": []}
    cad = _cad(entidades=[lotufo, rivoli, leblon])
    cadastro_aplicar.aplicar(conn, 1, cad)
    ids = {r["chave"]: r["id"] for r in conn.execute("SELECT id, chave FROM entidades")}
    pares = conn.execute("SELECT consorciada_id FROM entidade_consorciadas WHERE consorcio_id=? ORDER BY 1",
                         (ids["complexo-leblon"],)).fetchall()
    assert [p[0] for p in pares] == sorted([ids["lotufo"], ids["rivoli"]])
    assert conn.execute("SELECT nome_curto FROM entidades WHERE id=?", (ids["lotufo"],)).fetchone()[0] == "Lotufo"
    r2 = cadastro_aplicar.aplicar(conn, 1, cad)
    assert r2["entidades"]["alterados"] == []
    leblon2 = {**leblon, "consorciadas": ["lotufo"]}
    r3 = cadastro_aplicar.aplicar(conn, 1, _cad(entidades=[lotufo, rivoli, leblon2]))
    assert "complexo-leblon (consorciadas)" in r3["entidades"]["alterados"]
    assert conn.execute("SELECT COUNT(*) FROM entidade_consorciadas").fetchone()[0] == 1
```

- [ ] **Step 5: Implementar no aplicador**

Em `_entidades`: `novo` ganha `"nome_curto": e.get("nome_curto") or e["nome"]`; o `INSERT` e o `UPDATE` incluem a coluna `nome_curto`. Depois do laço, chamar `_consorciadas(conn, usuario_id, ents, ids, rel)`:

```python
def _consorciadas(conn, usuario_id, ents, ids, rel) -> None:
    """Composicao dos consorcios: o conjunto do YAML substitui o do banco (cadastro, nao historico
    financeiro); a mudanca vai para a auditoria com as chaves de antes e de depois."""
    chave_de = {v: k for k, v in ids.items()}
    for e in ents:
        if e.get("papel") != "consorcio":
            continue
        cid = ids[e["chave"]]
        antes = sorted(chave_de.get(r[0], str(r[0])) for r in conn.execute(
            "SELECT consorciada_id FROM entidade_consorciadas WHERE consorcio_id=?", (cid,)))
        depois = sorted(e.get("consorciadas") or [])
        if antes == depois:
            continue
        conn.execute("DELETE FROM entidade_consorciadas WHERE consorcio_id=?", (cid,))
        for ch in depois:
            conn.execute("INSERT INTO entidade_consorciadas (consorcio_id, consorciada_id) VALUES (?,?)",
                         (cid, ids[ch]))
        rel["alterados"].append(f"{e['chave']} (consorciadas)")
        auditoria.registrar(conn, usuario_id, "cadastro.consorciadas", "entidade", cid,
                            {"consorciadas": antes}, {"consorciadas": depois})
```

Em `_contrato`: `_CAMPOS_CONTRATO` ganha `"documentos"` no fim, e `novo` ganha `"documentos": _json(c["documentos"]) if c.get("documentos") else None`.

- [ ] **Step 6: Cadastro real**

`cadastro/entidades.yaml`: entidade nova `montante` (`nome: Montante`, `cnpj: '00.000.000/0006-00'`, `papel: consorciada`, `coligada_rm: null`, `sigla_oficio: null`, `emails_faturamento: []`), com o comentário "consorciada do Complexo Leblon: certidões no protocolo da 25ª (11/06/2026)"; `nome_curto` em todas (Lotufo, Oriundi, Via Parecis, Complexo Leblon, Integra BRT, BR-163, Rivoli, Guaxe, Encomind, Montante) e `consorciadas` em três, com comentário da fonte:

```yaml
- chave: oriundi
  ...
  nome_curto: Oriundi
  # FRC do Oriundi (03/08/2026): NFS-e 2242 e 2244 da Lotufo, 3003 e 3004 da Rivoli.
  consorciadas: [lotufo, rivoli]
- chave: complexo-leblon
  ...
  nome_curto: Complexo Leblon
  # PDF "CERTIDÕES DE REGULARIDADE - COMP. LEBLON" da 25ª (11/06/2026): consórcio, Lotufo, Montante, Rivoli.
  consorciadas: [lotufo, rivoli, montante]
  # Pacote do DP da 25ª é a folha do próprio consórcio.
  regularidade_propria: true
- chave: integra-brt
  ...
  nome_curto: Integra BRT
  consorciadas: [lotufo, guaxe, encomind]
```

`cadastro/orgaos.yaml`: nas cinco superintendências da SINFRA (`sinfra-sagpm`, `sinfra-suef1`, `sinfra-suef2`, `sinfra-supu`, `sinfra-sacid`), `documentos_medicao: [federal, fgts, trabalhista, estadual, municipal, regularidade]`, com o comentário "regularidade do DP confirmada nos protocolos de 22/06, 06/07, 19/08 e 16/09/2026; MTPAR não leva (PDF único de 797 KB no CT-301)". `documentos_reajuste` da SINFRA passa a `[federal, fgts, trabalhista, estadual, municipal]` (decisão 16), com o comentário "o que a operadora envia; a IN 001/2024 art. 12 §3º exigiria só a estadual".

`cadastro/contratos/deciolandia.yaml` (decisão 6): `documentos_medicao: []` e `documentos_reajuste: []`, com o comentário "não protocolamos pelo consórcio Via Parecis (spec §18); rever quando se souber quem protocola".

- [ ] **Step 7: Rodar**

Run: `cd backend && .venv\Scripts\python -m pytest tests/test_cadastro_arquivos.py tests/test_cadastro_aplicar.py tests/test_cli_cadastro.py tests/test_espelho_cadastro_real.py -v` e `.venv\Scripts\python -m app.cli cadastro validar` (sobre `cadastro/`).
Expected: PASS; validar sem erro.

- [ ] **Step 8: Commit**

```bash
git add backend/app/cadastro_arquivos.py backend/app/cadastro_aplicar.py cadastro/entidades.yaml cadastro/orgaos.yaml cadastro/contratos/deciolandia.yaml backend/tests/test_cadastro_arquivos.py backend/tests/test_cadastro_aplicar.py
git commit -m "feat: cadastro com nome curto, composicao dos consorcios, listas de documentos e regularidade na SINFRA"
```

---

### Task 3: Feriados nacionais e dias úteis

**Files:**
- Create: `backend/app/feriados.py`
- Test: `backend/tests/test_feriados.py`

**Interfaces:**
- Produces: `feriados.pascoa(ano: int) -> date`, `feriados.nacionais(ano: int) -> frozenset[date]`, `feriados.dia_util(d: date) -> bool`, `feriados.somar_dias_uteis(inicio: date, n: int) -> date`.

- [ ] **Step 1: Teste**

```python
# backend/tests/test_feriados.py
import datetime

from app import feriados

D = datetime.date


def test_pascoa_e_paixao():
    assert feriados.pascoa(2026) == D(2026, 4, 5)
    assert feriados.pascoa(2027) == D(2027, 3, 28)
    assert D(2026, 4, 3) in feriados.nacionais(2026)          # Paixao de Cristo


def test_consciencia_negra_so_a_partir_de_2024():
    assert D(2026, 11, 20) in feriados.nacionais(2026)
    assert D(2023, 11, 20) not in feriados.nacionais(2023)


def test_falencias_reais_do_backup():
    # emissao conta como 1o dia; sem feriado no meio, igual a antiga
    assert feriados.somar_dias_uteis(D(2026, 7, 13), 30) == D(2026, 8, 21)
    assert feriados.somar_dias_uteis(D(2026, 6, 17), 30) == D(2026, 7, 28)
    # Corpus Christi (04/06/2026) e' ponto facultativo: conta como dia util
    assert feriados.somar_dias_uteis(D(2026, 5, 14), 30) == D(2026, 6, 24)
    # 07/09 e' feriado: a antiga gravou 11/09, o certo e' 14/09
    assert feriados.somar_dias_uteis(D(2026, 8, 3), 30) == D(2026, 9, 14)


def test_emissao_no_fim_de_semana_comeca_na_segunda():
    assert feriados.somar_dias_uteis(D(2026, 8, 1), 1) == D(2026, 8, 3)
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `cd backend && .venv\Scripts\python -m pytest tests/test_feriados.py -v`
Expected: FAIL (`No module named 'app.feriados'`).

- [ ] **Step 3: Implementar**

```python
# backend/app/feriados.py
"""Feriados nacionais e contagem de dias uteis (spec §9: validade da certidao de falencia).

So' feriados NACIONAIS de lei: Lei 662/1949 com a 10.607/2002 (01/01, 21/04, 01/05, 07/09, 02/11,
15/11, 25/12), Lei 6.802/1980 (12/10), Lei 14.759/2023 (20/11, desde 2024) e a Paixao de Cristo.
Carnaval e Corpus Christi sao ponto facultativo e contam como dia util: contar menos feriados
encurta a validade calculada, que e' o lado seguro para quem protocola.
"""
import datetime
from functools import lru_cache

_FIXOS = ((1, 1), (4, 21), (5, 1), (9, 7), (10, 12), (11, 2), (11, 15), (11, 20), (12, 25))


def pascoa(ano: int) -> datetime.date:
    """Domingo de Pascoa (algoritmo de Meeus/Jones/Butcher, calendario gregoriano)."""
    a = ano % 19
    b, c = divmod(ano, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mes, dia = divmod(h + l - 7 * m + 114, 31)
    return datetime.date(ano, mes, dia + 1)


@lru_cache(maxsize=64)
def nacionais(ano: int) -> frozenset[datetime.date]:
    dias = {datetime.date(ano, m, d) for m, d in _FIXOS if (m, d) != (11, 20) or ano >= 2024}
    dias.add(pascoa(ano) - datetime.timedelta(days=2))
    return frozenset(dias)


def dia_util(d: datetime.date) -> bool:
    return d.weekday() < 5 and d not in nacionais(d.year)


def somar_dias_uteis(inicio: datetime.date, n: int) -> datetime.date:
    """O n-esimo dia util a partir de `inicio`, que conta como o 1o quando e' dia util."""
    if n < 1:
        raise ValueError("n precisa ser pelo menos 1")
    d, contados = inicio, 0
    while True:
        if dia_util(d):
            contados += 1
            if contados == n:
                return d
        d += datetime.timedelta(days=1)
```

- [ ] **Step 4: Rodar e ver passar**

Run: `cd backend && .venv\Scripts\python -m pytest tests/test_feriados.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/feriados.py backend/tests/test_feriados.py
git commit -m "feat: feriados nacionais e soma de dias uteis para a validade da certidao de falencia"
```

---

### Task 4: Fixtures reais e leitor `leitura_certidao.py`

**Files:**
- Create: `backend/tests/fixtures/certidoes/*.txt` (12 arquivos, gerados uma vez)
- Create: `backend/app/leitura_certidao.py`
- Test: `backend/tests/test_leitura_certidao.py`

**Interfaces:**
- Consumes: `feriados.somar_dias_uteis`, `entidades.cnpj_valido`.
- Produces: `leitura_certidao.TIPOS`, `NATUREZAS = ("negativa", "positiva_efeito_negativa")`, `DIGITAVEIS: frozenset[str]`, `class Recusa(ValueError)` com `.motivo: str`, `plano(texto: str) -> str`, `cnpjs_no_texto(texto: str) -> list[str]` (CNPJs com DV válido, na ordem), `ler(texto: str, cnpjs_cadastrados: frozenset[str] = frozenset()) -> dict` com as chaves `tipo, natureza, cnpj, emissao, validade, numero, validade_calculada: bool, evidencia: dict[str, str]`.

- [ ] **Step 1: Gerar as fixtures (uma vez; o script fica no scratchpad, não no repositório)**

```python
# <scratchpad>/gerar_fixtures_certidoes.py -- rodar com backend/.venv/Scripts/python
import pathlib, re, pypdf
BASE = pathlib.Path(r"C:\Users\<usuario>\dev\lotufo-dashboard\backup-sharepoint-2026-08-04\certidoes-pdfs")
DEST = pathlib.Path(r"C:\Users\<usuario>\Nova Dashboard Lotufo\backend\tests\fixtures\certidoes")
ESCOLHA = {
    "federal-lotufo": "cert__Lotufo__2026-12-21 - FEDERAL*",
    "federal-oriundi": "cert__Consórcio Oriundi__2027-01-30 - FEDERAL*",
    "fgts-lotufo": "cert__Lotufo__2026-08-09 - FGTS*",
    "fgts-integra": "cert__Consórcio Integra BRT__2026-08-26 - FGTS*",
    "trabalhista-lotufo": "cert__Lotufo__2026-12-21 - TRABALHISTA*",
    "estadual-lotufo": "cert__Lotufo__2026-08-22 - ESTADUAL*",
    "estadual-integra": "cert__Consórcio Integra BRT__2026-08-22 - ESTADUAL*",
    "estadual-guaxe-cpd": "cert__Guaxe__2026-08-22 - ESTADUAL*",
    "municipal-lotufo": "cert__Lotufo__2026-07-24 - MUNICIPAL*",
    "municipal-leblon": "cert__Consórcio Complexo Leblon__2026-10-05 - MUNICIPAL*",
    "falencia-lotufo": "cert__Lotufo__2026-08-21 - FALENCIA*",
    "falencia-leblon": "cert__Consórcio Complexo Leblon__2026-09-11 - FALENCIA*",
}
DEST.mkdir(parents=True, exist_ok=True)
for nome, padrao in ESCOLHA.items():
    (pdf,) = list(BASE.glob(padrao))
    texto = "\n".join((p.extract_text() or "") for p in pypdf.PdfReader(str(pdf)).pages)
    texto = re.sub(r"(emitida por )[^.\n]+", r"\1SERVIDOR DO TJMT", texto)   # decisao 14
    (DEST / f"{nome}.txt").write_text(texto, encoding="utf-8")
```

Conferir que nenhum `.txt` contém o nome de servidor (`grep -i "emitida por" backend/tests/fixtures/certidoes/*.txt` só mostra `SERVIDOR DO TJMT`).

- [ ] **Step 2: Testes do leitor**

```python
# backend/tests/test_leitura_certidao.py
import pathlib

import pytest

from app import leitura_certidao as lc

FIX = pathlib.Path(__file__).parent / "fixtures" / "certidoes"
CADASTRADOS = frozenset({"00000000000100", "00000000000200", "00000000000300", "00000000000400",
                         "00000000000500", "00000000000600", "00000000000700"})


def _ler(nome):
    return lc.ler((FIX / f"{nome}.txt").read_text(encoding="utf-8"), CADASTRADOS)


@pytest.mark.parametrize("nome, tipo, natureza, cnpj, emissao, validade, numero", [
    ("federal-lotufo", "federal", "positiva_efeito_negativa", "00000000000100", "2026-06-24", "2026-12-21", "DB05.42F6.A9AE.2CD8"),
    ("federal-oriundi", "federal", "negativa", "00000000000200", "2026-08-03", "2027-01-30", "FDF6.447C.AFC6.3B8A"),
    ("fgts-lotufo", "fgts", "negativa", "00000000000100", "2026-07-11", "2026-08-09", "2026071109560105220476"),
    ("fgts-integra", "fgts", "negativa", "00000000000300", "2026-07-28", "2026-08-26", "2026072807576425758063"),
    ("trabalhista-lotufo", "trabalhista", "negativa", "00000000000100", "2026-06-24", "2026-12-21", "57104469/2026"),
    ("estadual-lotufo", "estadual", "positiva_efeito_negativa", "00000000000100", "2026-06-24", "2026-08-22", "2AAA2LK2M77722T7"),
    ("estadual-integra", "estadual", "negativa", "00000000000300", "2026-06-24", "2026-08-22", "TBAB9LL2UA2BA22B"),
    ("municipal-lotufo", "municipal", "positiva_efeito_negativa", "00000000000100", "2026-06-24", "2026-07-24", "993266/2026"),
    ("municipal-leblon", "municipal", "negativa", "00000000000400", "2026-07-07", "2026-10-05", "997775/2026"),
    ("falencia-lotufo", "falencia", "negativa", "00000000000100", "2026-07-13", "2026-08-21", "25958385"),
    ("falencia-leblon", "falencia", "negativa", "00000000000400", "2026-08-03", "2026-09-14", "26387279"),
])
def test_certidoes_reais(nome, tipo, natureza, cnpj, emissao, validade, numero):
    r = _ler(nome)
    assert (r["tipo"], r["natureza"], r["cnpj"], r["emissao"], r["validade"], r["numero"]) == \
        (tipo, natureza, cnpj, emissao, validade, numero)
    assert r["validade_calculada"] is (tipo == "falencia")


def test_estadual_positiva_pura_e_recusada():
    with pytest.raises(lc.Recusa) as e:
        _ler("estadual-guaxe-cpd")
    assert e.value.motivo == "positiva" and "positiva" not in lc.DIGITAVEIS


def test_texto_curto_e_sem_texto():
    with pytest.raises(lc.Recusa) as e:
        lc.ler("   ")
    assert e.value.motivo == "sem-texto" and e.value.motivo in lc.DIGITAVEIS


def test_documento_que_nao_e_certidao():
    with pytest.raises(lc.Recusa) as e:
        lc.ler("NOTA FISCAL DE SERVICOS ELETRONICA " * 5)
    assert e.value.motivo == "tipo-desconhecido"


def test_cnpj_do_cadastro_vence_o_primeiro_do_texto():
    texto = (FIX / "municipal-lotufo.txt").read_text(encoding="utf-8")
    assert "12345678900.000.000/0001-00" in texto        # inscricao estadual colada no CNPJ
    assert lc.ler("CNPJ 00.000.000/0001-00 " + texto, CADASTRADOS)["cnpj"] == "00000000000100"


def test_normalizacao_desfaz_ligadura_e_espaco_nao_quebravel():
    assert lc.plano("Certi\ufb01cado\u00a0de  Regularidade") == "CERTIFICADO DE REGULARIDADE"
    assert lc.plano("Certi fi cado") == "CERTIFICADO"
```

- [ ] **Step 3: Rodar e ver falhar**

Run: `cd backend && .venv\Scripts\python -m pytest tests/test_leitura_certidao.py -v`
Expected: FAIL (`No module named 'app.leitura_certidao'`).

- [ ] **Step 4: Implementar**

```python
# backend/app/leitura_certidao.py
"""Leitor deterministico das seis certidoes de protocolo (spec §9, bloco 4).

Regra de dominio portada da dashboard antiga (js/features/certidoes.js, `PERFIS`), com tres
mudancas: (1) a NATUREZA e' lida e a positiva pura e' recusada; (2) a falencia soma 30 dias uteis
descontando feriados nacionais (app/feriados.py); (3) o CNPJ escolhido e' o de uma empresa do
cadastro que aparece no documento, nao o primeiro numero com cara de CNPJ (a municipal de Cuiaba
cola a inscricao estadual no CNPJ).

Puro: texto -> campos. Nao abre PDF (`leitura_pdf.texto_de_pdf_com_limite`, em subprocesso) e nao
toca banco (`documentos.py` decide gravar). Tudo e' casado sobre `plano(texto)`: NFKC (desfaz a
ligadura "fi" e o espaco nao quebravel da certidao federal), sem acento, maiusculas, espacos
colapsados. Os valores extraidos sao digitos, datas e codigos, que a normalizacao nao altera.
"""
import datetime
import re
import unicodedata

from app import entidades, feriados

TIPOS = ("federal", "fgts", "trabalhista", "estadual", "municipal", "falencia")
NATUREZAS = ("negativa", "positiva_efeito_negativa")
MIN_TEXTO = 80
DIAS_UTEIS_FALENCIA = 30
ROTULO = {"federal": "federal", "fgts": "do FGTS", "trabalhista": "trabalhista", "estadual": "estadual",
          "municipal": "municipal", "falencia": "de falência"}
# Motivos em que a pessoa ainda pode digitar os campos (decisao 5 do plano). `positiva` e
# `empresa-desconhecida` NAO: a primeira nao serve para protocolo, a segunda nao tem a quem pertencer.
DIGITAVEIS = frozenset({"sem-texto", "tipo-desconhecido", "natureza-desconhecida", "sem-cnpj",
                        "sem-emissao", "sem-validade", "datas-incoerentes"})
_MESES = {m: i for i, m in enumerate(("JANEIRO", "FEVEREIRO", "MARCO", "ABRIL", "MAIO", "JUNHO", "JULHO",
                                      "AGOSTO", "SETEMBRO", "OUTUBRO", "NOVEMBRO", "DEZEMBRO"), 1)}


class Recusa(ValueError):
    """Leitura que nao se aproveita. `motivo` e' estavel: a tela e o CLI decidem por ele."""

    def __init__(self, motivo: str, mensagem: str):
        super().__init__(mensagem)
        self.motivo = motivo


def plano(texto: str) -> str:
    t = unicodedata.normalize("NFKC", texto or "")
    t = re.sub(r"(?i)certi\s+fi\s+ca", "Certifica", t)             # ligadura que o extrator separa
    t = "".join(unicodedata.normalize("NFD", c)[:1] for c in t)    # 1 para 1: tira o acento
    return re.sub(r"\s+", " ", t).upper().strip()


_D = r"(\d{2}/\d{2}/\d{4})"
_EXT = r"(\d{1,2}) DE ([A-Z]+) DE (\d{4})"
# Ordem da antiga: o primeiro que casar vence.
_ASSINATURAS = (
    ("falencia", re.compile(r"FALENCIA E (?:RECUPERACAO JUDICIAL|CONCORDATA)")),
    ("fgts", re.compile(r"CERTIFICADO DE REGULARIDADE DO FGTS")),
    ("trabalhista", re.compile(r"DEBITOS TRABALHISTAS")),
    ("federal", re.compile(r"TRIBUTOS FEDERAIS E A DIVIDA ATIVA DA UNIAO")),
    ("estadual", re.compile(r"GERIDOS PELA PROCURADORIA-GERAL DO ESTADO")),
    ("municipal", re.compile(r"PREFEITURA MUNICIPAL DE CUIABA")),
)
_CAMPOS = {
    "federal": {"emissao": r"DO DIA " + _D, "validade": r"VALIDA ATE:? ?" + _D,
                "numero": r"CODIGO DE CONTROLE DA CERTIDAO:? ?([0-9A-F]{4}(?:\.[0-9A-F]{4}){3})"},
    "fgts": {"faixa": r"VALIDADE:? ?" + _D + r" ?A ?" + _D, "numero": r"CERTIFICACAO NUMERO:? ?(\d{10,30})"},
    "trabalhista": {"emissao": r"EXPEDICAO:? ?" + _D, "validade": r"VALIDADE:? ?" + _D,
                    "numero": r"CERTIDAO NO:? ?(\d{5,12}/\d{4})"},
    "estadual": {"emissao": r"DATA DA EMISSAO:? ?" + _D, "validade": r"VALIDA ATE:? ?" + _D,
                 "numero": r"NUMERO DE AUTENTICACAO:? ?([A-Z0-9]{10,30})"},
    "municipal": {"emissao": r"CUIABA/MT, ?[A-Z-]+, ?" + _EXT, "validade": r"VALIDA ATE " + _EXT,
                  "numero": r"(?<![\d.])(\d{4,10}/\d{4})(?!\d)"},
    "falencia": {"emissao": r"ATE A DA[TR]A DE " + _D, "numero": r"\bNO:? ?(\d{5,12})"},
}
_POS_EFEITO = re.compile(r"POSITIVA.{0,60}?COM EFEITOS? (?:DE )?NEGATIV[OA]")
_SIGLA = re.compile(r"\b(CND|CPEND|CPD) NO\b")
_CNPJ = re.compile(r"(\d{2})\.(\d{3})\.(\d{3})/(\d{4})-(\d{2})")


def _natureza(tipo: str, p: str) -> str | None:
    """'negativa', 'positiva_efeito_negativa', 'positiva' ou None (nao reconhecida)."""
    if tipo == "fgts":
        return "negativa" if "ENCONTRA-SE EM SITUACAO REGULAR" in p else None
    if tipo == "falencia":
        if "NADA CONSTA" in p:
            return "negativa"
        return "positiva" if re.search(r"\bCONSTA", p) else None
    if tipo == "estadual":
        m = _SIGLA.search(p)
        if m:
            return {"CND": "negativa", "CPEND": "positiva_efeito_negativa", "CPD": "positiva"}[m.group(1)]
    if _POS_EFEITO.search(p):
        return "positiva_efeito_negativa"
    if "CERTIDAO NEGATIVA DE DEBITOS" in p:
        return "negativa"
    if "CERTIDAO POSITIVA" in p:
        return "positiva"
    return None


def _data(grupos: tuple) -> datetime.date | None:
    try:
        if len(grupos) == 1:
            d, m, a = grupos[0].split("/")
            return datetime.date(int(a), int(m), int(d))
        return datetime.date(int(grupos[2]), _MESES[grupos[1]], int(grupos[0]))
    except (ValueError, KeyError):
        return None


def cnpjs_no_texto(texto: str) -> list[str]:
    """CNPJs com DV valido que aparecem no documento, na ordem (tambem confere a empresa digitada)."""
    return [c for c in ("".join(m.groups()) for m in _CNPJ.finditer(plano(texto))) if entidades.cnpj_valido(c)]


def ler(texto: str, cnpjs_cadastrados: frozenset[str] = frozenset()) -> dict:
    p = plano(texto)
    if len(p) < MIN_TEXTO:
        raise Recusa("sem-texto", "O PDF não tem texto legível (foi digitalizado ou salvo como imagem) — "
                                  "informe empresa, tipo, emissão e validade.")
    tipo = next((t for t, rx in _ASSINATURAS if rx.search(p)), None)
    if tipo is None:
        raise Recusa("tipo-desconhecido", "Não reconheci a certidão (federal, FGTS, trabalhista, estadual, "
                                          "municipal de Cuiabá ou falência) — informe os campos.")
    natureza = _natureza(tipo, p)
    if natureza == "positiva":
        raise Recusa("positiva", f"A certidão {ROTULO[tipo]} é POSITIVA (há débito ou processo): não serve "
                                 f"para protocolo. Regularize e emita de novo.")
    if natureza is None:
        raise Recusa("natureza-desconhecida", f"Não achei se a certidão {ROTULO[tipo]} é negativa ou positiva "
                                              f"com efeito de negativa — informe os campos.")
    validos = cnpjs_no_texto(texto)
    cnpj = next((c for c in validos if c in cnpjs_cadastrados), validos[0] if validos else None)
    if cnpj is None:
        raise Recusa("sem-cnpj", "Não achei o CNPJ no documento — informe os campos.")

    campos, evidencia = _CAMPOS[tipo], {}

    def achar(campo):
        m = re.search(campos[campo], p)
        if m:
            evidencia[campo] = m.group(0)
        return m

    if tipo == "fgts":
        m = achar("faixa")
        emissao = _data((m.group(1),)) if m else None
        validade = _data((m.group(2),)) if m else None
    else:
        m = achar("emissao")
        emissao = _data(m.groups()) if m else None
        if tipo == "falencia":
            validade = feriados.somar_dias_uteis(emissao, DIAS_UTEIS_FALENCIA) if emissao else None
        else:
            m = achar("validade")
            validade = _data(m.groups()) if m else None
    if emissao is None:
        raise Recusa("sem-emissao", "Não achei a data de emissão — informe os campos.")
    if validade is None:
        raise Recusa("sem-validade", "Não achei a validade — informe os campos.")
    if validade < emissao:
        raise Recusa("datas-incoerentes", "A validade lida é anterior à emissão — informe os campos.")
    m = achar("numero")
    numero = next((g for g in m.groups() if g), None) if m else None
    return {"tipo": tipo, "natureza": natureza, "cnpj": cnpj, "emissao": emissao.isoformat(),
            "validade": validade.isoformat(), "numero": numero,
            "validade_calculada": tipo == "falencia", "evidencia": evidencia}
```

- [ ] **Step 5: Rodar e ver passar**

Run: `cd backend && .venv\Scripts\python -m pytest tests/test_leitura_certidao.py -v`
Expected: PASS (13 casos).

- [ ] **Step 6: Prova sobre o backup inteiro (scratchpad, não vira teste)**

Rodar o leitor sobre os 63 PDFs de `backup-sharepoint-2026-08-04/certidoes-pdfs` contra `Certidoes.json`, casando os metadados pelo par (pasta da empresa, nome do arquivo) e não só pelo nome (há três "CND - TRABALHISTA 24-11-2026.pdf" em pastas diferentes). Esperado: 45 iguais em tipo, CNPJ, emissão, validade e número; 2 falências de 03/08 com 14/09 no lugar de 11/09; 2 `positiva`; 14 `sem-texto`. Qualquer outra diferença volta para o Step 4.

- [ ] **Step 7: Commit**

```bash
git add backend/app/leitura_certidao.py backend/tests/test_leitura_certidao.py backend/tests/fixtures/certidoes
git commit -m "feat: leitor das seis certidoes com natureza, CNPJ do cadastro e falencia em dias uteis"
```

---

### Task 5: Serviço `documentos.py` — exigência, situação, regularidade, gravar, painel, avisos, ZIP

**Files:**
- Create: `backend/app/documentos.py`
- Modify: `backend/app/certidoes.py` (`_inserir` e `registrar` aceitam `natureza`, `leitura`, `nome_original`)
- Test: `backend/tests/test_documentos.py`

**Interfaces:**
- Consumes: `certidoes.vigente/ultima_emissao/nao_se_aplica_vigora/registrar`, `contratos.entidade_de`, `entidades.listar/detalhe`, `leitura_certidao.ler/Recusa`, `feriados.somar_dias_uteis`, `arquivos.caminho_seguro`, `tempo.hoje_local`.
- Produces (usados nas Tasks 6 a 9):
  - `tipo_por_chave(conn, chave: str) -> dict`
  - `exigidos(conn, contrato_id: int, natureza: str) -> {"entidades": list[int], "tipos": list[dict], "regularidade": int | None}` (natureza = tipo da medição: `execucao`, `projeto`, `reajuste`)
  - `situacao(conn, entidade_id: int, tipo: dict, hoje: date) -> {"situacao": "ok"|"vencendo"|"vencida"|"faltando"|"nao_se_aplica", "dias": int|None, "certidao": dict|None}`
  - `competencia_esperada(hoje: date) -> str`; `regularidade_vigente(conn, entidade_id) -> dict|None`; `situacao_regularidade(conn, entidade_id, hoje) -> {"situacao": "ok"|"atrasada"|"faltando", "competencia", "esperada", "regularidade"}`
  - `ler(conn, texto: str) -> dict` (leitura + `entidade_id`, `entidade`, `tipo_id`, `tipo_nome`; `Recusa("empresa-desconhecida")`)
  - `dados_manuais(conn, entidade_id, tipo_chave, emissao, validade, natureza, numero, cnpjs_do_texto=()) -> dict`
  - `gravar_certidao(conn, usuario_id, dados: dict, arquivo: str, sha256: str, nome_original: str | None, leitura: str) -> int`
  - `registrar_regularidade(conn, usuario_id, entidade_id, competencia, arquivo, sha256, tamanho, nome_original) -> int`
  - `painel(conn, hoje: date | None = None) -> dict`; `avisos(conn, hoje: date | None = None) -> list[dict]`
  - `zip_vigentes(conn, entidade_id: int, na_data: str) -> tuple[str, bytes]`
  - `importar_pasta(conn, usuario_id, pasta: Path, ensaio: bool, hoje: date | None = None) -> dict`

- [ ] **Step 1: `certidoes.registrar` com os campos novos e `vigente` pela maior validade**

`_inserir(...)` ganha os parâmetros `natureza=None, leitura=None, nome_original=None`, gravados no `INSERT` e no dicionário da auditoria; `registrar(...)` ganha os mesmos três como keyword com padrão `None` e recusa natureza fora de `("negativa", "positiva_efeito_negativa", None)` com `ValueError("Natureza inválida: ...")`. Nenhum chamador existente muda.

`certidoes.vigente` (decisão 15): `ORDER BY emissao DESC, id DESC` vira `ORDER BY validade DESC, emissao DESC, id DESC`, com a docstring atualizada ("vale a de maior validade, spec §9") e um teste em `test_certidoes.py`:

```python
def test_vigente_e_a_de_maior_validade_mesmo_anexada_antes(conn, monkeypatch):
    monkeypatch.setattr(tempo, "hoje_local", lambda: datetime.date(2026, 9, 1))
    nova = _reg(conn, emissao="2026-08-20", validade="2026-12-01")
    _reg(conn, emissao="2026-08-25", validade="2026-09-20")      # emissao mais nova, validade menor
    assert certidoes.vigente(conn, 1, 1)["id"] == nova
```

- [ ] **Step 2: Testes do serviço**

```python
# backend/tests/test_documentos.py
import datetime
import json
import pathlib
import zipfile
import io

import pytest

from app import auth, certidoes, db, documentos, leitura_certidao, tempo

D = datetime.date
FIX = pathlib.Path(__file__).parent / "fixtures" / "certidoes"


@pytest.fixture
def conn(tmp_path, monkeypatch):
    monkeypatch.setenv("DASH_DB_PATH", str(tmp_path / "t.db"))
    c = db.get_conn(); db.migrate(c)
    auth.criar_usuario(c, "U", "u@lotufo.com", "senha-forte-123", "admin")
    monkeypatch.setattr(tempo, "hoje_local", lambda: D(2026, 9, 23))
    yield c
    c.close()


# DML cru SEMPRE com commit: `db.mutacao` recusa transacao aberta fora dele (db.py:94-97).
def _orgao(conn, medicao, reajuste):
    conn.execute("INSERT INTO orgaos (chave, nome, familia, regras) VALUES ('sinfra-x','SINFRA X','sinfra',?)",
                 (json.dumps({"documentos_medicao": medicao, "documentos_reajuste": reajuste}),))
    conn.commit()
    return conn.execute("SELECT id FROM orgaos WHERE chave='sinfra-x'").fetchone()[0]


def _consorcio(conn):
    conn.execute("UPDATE entidades SET nome_curto='Lotufo' WHERE id=1")
    conn.execute("INSERT INTO entidades (id, nome, cnpj, papel, nome_curto) VALUES "
                 "(2, 'Consórcio Complexo Leblon', '00000000000400', 'consorcio', 'Complexo Leblon'), "
                 "(3, 'Rivoli', '00000000000500', 'consorciada', 'Rivoli')")
    conn.execute("INSERT INTO entidade_consorciadas VALUES (2, 1), (2, 3)")
    conn.commit()


def _contrato(conn, orgao_id, entidade_id=1, documentos_json=None):
    conn.execute("INSERT INTO contratos (orgao, numero_instrumento, objeto, valor_original_centavos, orgao_id, "
                 "entidade_id, documentos) VALUES ('SINFRA', ?, 'obra', 100, ?, ?, ?)",
                 (f"C-{orgao_id}-{entidade_id}", orgao_id, entidade_id, documentos_json))
    conn.commit()
    return conn.execute("SELECT MAX(id) FROM contratos").fetchone()[0]


def _cert(conn, ent, chave, emissao, validade):
    t = documentos.tipo_por_chave(conn, chave)
    return certidoes.registrar(conn, 1, ent, t["id"], emissao, validade, f"certidoes/{ent}{chave}.pdf",
                               "a" * 64, "upload", natureza="negativa", leitura="automatica")


def test_exigidos_consorcio_natureza_e_excecao(conn):
    _consorcio(conn)
    oid = _orgao(conn, ["federal", "fgts", "regularidade"], ["estadual"])
    cid = _contrato(conn, oid, entidade_id=2)
    ex = documentos.exigidos(conn, cid, "execucao")
    assert ex["entidades"] == [2, 1, 3]
    assert [t["chave"] for t in ex["tipos"]] == ["federal", "fgts"]
    assert ex["regularidade"] == 1                        # so' da Lotufo
    reaj = documentos.exigidos(conn, cid, "reajuste")
    assert [t["chave"] for t in reaj["tipos"]] == ["estadual"] and reaj["regularidade"] is None
    cid2 = _contrato(conn, oid, documentos_json=json.dumps({"reajuste": ["estadual", "municipal"]}))
    assert [t["chave"] for t in documentos.exigidos(conn, cid2, "reajuste")["tipos"]] == ["estadual", "municipal"]
    assert [t["chave"] for t in documentos.exigidos(conn, cid2, "projeto")["tipos"]] == ["federal", "fgts"]


def test_contrato_sem_orgao_usa_os_tipos_padrao(conn):
    cid = _contrato(conn, None)
    assert [t["chave"] for t in documentos.exigidos(conn, cid, "execucao")["tipos"]] == ["federal", "fgts", "trabalhista"]


def test_situacao_limiar_pela_validade_da_propria_certidao(conn):
    _cert(conn, 1, "fgts", "2026-08-31", "2026-09-29")          # 29 dias de validade -> limiar 7
    _cert(conn, 1, "federal", "2026-06-24", "2026-10-05")       # longa -> limiar 15
    _cert(conn, 1, "municipal", "2026-06-24", "2026-07-24")     # vencida
    s = lambda ch: documentos.situacao(conn, 1, documentos.tipo_por_chave(conn, ch), D(2026, 9, 23))
    assert (s("fgts")["situacao"], s("fgts")["dias"]) == ("vencendo", 6)
    assert (s("federal")["situacao"], s("federal")["dias"]) == ("vencendo", 12)
    assert s("municipal")["situacao"] == "vencida"
    assert s("trabalhista")["situacao"] == "faltando"


def test_competencia_esperada_da_regularidade():
    assert documentos.competencia_esperada(D(2026, 6, 22)) == "2026-04"
    assert documentos.competencia_esperada(D(2026, 8, 3)) == "2026-05"     # antes do dia 10: mes - 3
    assert documentos.competencia_esperada(D(2026, 9, 16)) == "2026-07"
    assert documentos.competencia_esperada(D(2026, 1, 12)) == "2025-11"


def test_regularidade_vale_a_maior_competencia_e_repetida_e_recusada(conn):
    documentos.registrar_regularidade(conn, 1, 1, "2026-06", "regularidades/a.pdf", "a" * 64, 10, "062026 - LOTUFO.pdf")
    documentos.registrar_regularidade(conn, 1, 1, "2026-07", "regularidades/b.pdf", "b" * 64, 10, "072026 - LOTUFO.pdf")
    assert documentos.regularidade_vigente(conn, 1)["competencia"] == "2026-07"
    assert documentos.situacao_regularidade(conn, 1, D(2026, 9, 23))["situacao"] == "ok"
    assert documentos.situacao_regularidade(conn, 1, D(2026, 10, 10))["situacao"] == "atrasada"
    with pytest.raises(ValueError, match="já está anexad"):
        documentos.registrar_regularidade(conn, 1, 1, "2026-07", "regularidades/b.pdf", "b" * 64, 10, None)
    with pytest.raises(ValueError, match="competência"):
        documentos.registrar_regularidade(conn, 1, 1, "2026-12", "regularidades/c.pdf", "c" * 64, 10, None)


def test_ler_resolve_empresa_e_recusa_cnpj_de_fora(conn):
    texto = (FIX / "federal-lotufo.txt").read_text(encoding="utf-8")
    r = documentos.ler(conn, texto)
    assert (r["entidade_id"], r["tipo_id"], r["tipo"]) == (1, 1, "federal")
    with pytest.raises(leitura_certidao.Recusa) as e:
        documentos.ler(conn, (FIX / "federal-oriundi.txt").read_text(encoding="utf-8"))   # Oriundi nao cadastrado aqui
    assert e.value.motivo == "empresa-desconhecida"


def test_gravar_lida_e_repetida(conn):
    r = documentos.ler(conn, (FIX / "trabalhista-lotufo.txt").read_text(encoding="utf-8"))
    cid = documentos.gravar_certidao(conn, 1, r, "certidoes/x.pdf", "c" * 64, "cndt.pdf", "automatica")
    linha = conn.execute("SELECT natureza, leitura, nome_original, numero FROM certidoes WHERE id=?", (cid,)).fetchone()
    assert tuple(linha) == ("negativa", "automatica", "cndt.pdf", "57104469/2026")
    with pytest.raises(ValueError, match="já está cadastrada"):
        documentos.gravar_certidao(conn, 1, r, "certidoes/x.pdf", "c" * 64, "cndt.pdf", "automatica")


def test_manual_da_falencia_calcula_a_validade(conn):
    d = documentos.dados_manuais(conn, 1, "falencia", "2026-08-03", None, "negativa", None)
    assert d["validade"] == "2026-09-14"
    with pytest.raises(ValueError, match="negativa"):
        documentos.dados_manuais(conn, 1, "fgts", "2026-08-03", "2026-09-01", "positiva", None)


def test_manual_confere_a_empresa_contra_o_cnpj_do_texto(conn):
    with pytest.raises(ValueError, match="CNPJ"):
        documentos.dados_manuais(conn, 1, "estadual", "2026-06-24", "2026-08-22", "negativa", None,
                                 cnpjs_do_texto=["00000000000700"])          # PDF da Guaxe, empresa Lotufo
    assert documentos.dados_manuais(conn, 1, "estadual", "2026-06-24", "2026-08-22", "negativa", None,
                                    cnpjs_do_texto=["00000000000100"])["entidade_id"] == 1


def test_avisos_uma_linha_por_empresa_e_regularidade_do_mes(conn):
    oid = _orgao(conn, ["fgts", "municipal", "regularidade"], ["estadual"])
    _contrato(conn, oid)
    _cert(conn, 1, "fgts", "2026-08-31", "2026-09-27")
    _cert(conn, 1, "municipal", "2026-06-20", "2026-09-20")
    av = documentos.avisos(conn, D(2026, 9, 23))
    doc = [a for a in av if a["tipo"] == "documentos_empresa"]
    assert len(doc) == 1 and doc[0]["entidade_id"] == 1 and doc[0]["nivel"] == "acao"
    assert "municipal vencida em 20/09" in doc[0]["mensagem"] and "FGTS vence em 4 dias" in doc[0]["mensagem"]
    assert "estadual" in doc[0]["mensagem"]             # exigida no reajuste e nunca anexada
    reg = [a for a in av if a["tipo"] == "regularidade_mes"]
    assert len(reg) == 1 and "07/2026" in reg[0]["mensagem"]
    assert [a for a in documentos.avisos(conn, D(2026, 9, 9)) if a["tipo"] == "regularidade_mes"] == []


def test_zip_das_vigentes_na_data(conn, tmp_path):
    pasta = db.db_path().parent / "certidoes"
    pasta.mkdir(exist_ok=True)
    (pasta / "1fgts.pdf").write_bytes(b"%PDF-1.4 fgts")
    conn.execute("UPDATE entidades SET nome_curto='Lotufo' WHERE id=1")
    conn.commit()
    _cert(conn, 1, "fgts", "2026-08-31", "2026-09-29")
    nome, dados = documentos.zip_vigentes(conn, 1, "2026-09-23")
    assert nome == "Certidoes - Lotufo - 2026-09-23.zip"
    assert zipfile.ZipFile(io.BytesIO(dados)).namelist() == ["Lotufo - FGTS - 2026-09-29.pdf"]
    with pytest.raises(ValueError, match="nenhuma certidão vigente"):
        documentos.zip_vigentes(conn, 1, "2026-10-15")
```

- [ ] **Step 3: Rodar e ver falhar**

Run: `cd backend && .venv\Scripts\python -m pytest tests/test_documentos.py -v`
Expected: FAIL (`No module named 'app.documentos'`).

- [ ] **Step 4: Implementar**

```python
# backend/app/documentos.py
"""Documentos de protocolo (spec 2026-09-21 §9, bloco 4).

Duas gavetas. CERTIDAO tem validade e e' da empresa: tabela `certidoes`, historico append-only de
`certidoes.py`, que continua sendo a unica fonte de "o que valia na data". REGULARIDADE MENSAL e'
por competencia e por empresa: tabela `regularidades`, o PDF que o DP monta (folha, SEFIP/eSocial,
INSS), anexado uma vez e usado em todos os protocolos do mes.

O que e' EXIGIDO vem do cadastro: lista do orgao por natureza (medicao/projeto ou reajuste),
excecao do contrato, e em obra de consorcio as certidoes do consorcio e de cada consorciada.
"""
import datetime
import io
import json
import re
import sqlite3
import zipfile
from pathlib import Path

from app import (arquivos, auditoria, certidoes, contratos, db, entidades, feriados, leitura_certidao,
                 leitura_pdf, tempo)

TIPOS = leitura_certidao.TIPOS
REGULARIDADE = "regularidade"
ROTULO = {"federal": "federal", "fgts": "FGTS", "trabalhista": "trabalhista", "estadual": "estadual",
          "municipal": "municipal", "falencia": "falência"}
VALIDADE_CURTA_DIAS = 31          # FGTS e municipal: ~30 dias de validade
LIMIAR_CURTA, LIMIAR_LONGA = 7, 15
DIA_REGULARIDADE = 10
_COMPETENCIA = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def _d(iso: str) -> datetime.date:
    return datetime.date.fromisoformat(iso)


def _br(iso: str) -> str:
    return _d(iso).strftime("%d/%m/%Y")


def _br_curta(iso: str) -> str:
    return _d(iso).strftime("%d/%m")


def _mes_br(mes: str) -> str:
    return f"{mes[5:7]}/{mes[:4]}"


def _nome(e: dict) -> str:
    return e.get("nome_curto") or e["nome"]


def limiar(cert: dict) -> int:
    """7 dias para a certidao de ate 31 dias de validade (FGTS, municipal), 15 para as demais."""
    total = (_d(cert["validade"]) - _d(cert["emissao"])).days
    return LIMIAR_CURTA if total <= VALIDADE_CURTA_DIAS else LIMIAR_LONGA


def tipo_por_chave(conn: sqlite3.Connection, chave: str) -> dict:
    r = conn.execute("SELECT * FROM certidao_tipos WHERE chave=?", (chave,)).fetchone()
    if r is None:
        raise ValueError(f"Tipo de certidão sem cadastro: {chave}")
    return dict(r)


# --- exigencia --------------------------------------------------------------------------------

def exigidos(conn: sqlite3.Connection, contrato_id: int, natureza: str) -> dict:
    """{'entidades': [ids], 'tipos': [linhas de certidao_tipos], 'regularidade': id da Lotufo | None}.

    Precedencia: excecao do contrato > lista do orgao > (contrato SEM orgao) tipos
    `aplicavel_por_padrao`, o comportamento de antes do cadastro versionado, que os contratos da tela
    antiga e os testes ainda usam. Projeto segue a lista da medicao.
    """
    c = conn.execute("SELECT * FROM contratos WHERE id=?", (contrato_id,)).fetchone()
    if c is None:
        raise ValueError(f"Contrato {contrato_id} não encontrado")
    chave = "reajuste" if natureza == "reajuste" else "medicao"
    lista = None
    if c["documentos"]:
        lista = json.loads(c["documentos"]).get(chave)
    if lista is None and c["orgao_id"] is not None:
        o = conn.execute("SELECT regras FROM orgaos WHERE id=?", (c["orgao_id"],)).fetchone()
        lista = json.loads(o["regras"]).get(f"documentos_{chave}") if o else None
    if lista is None:
        tipos = [dict(r) for r in conn.execute(
            "SELECT * FROM certidao_tipos WHERE aplicavel_por_padrao=1 ORDER BY id")]
        lista = []
    else:
        tipos = [tipo_por_chave(conn, k) for k in lista if k in TIPOS]
    ent = contratos.entidade_de(c)
    ents = [ent] + [r[0] for r in conn.execute(
        "SELECT consorciada_id FROM entidade_consorciadas WHERE consorcio_id=? ORDER BY consorciada_id", (ent,))]
    lotufo = conn.execute("SELECT id FROM entidades WHERE papel='lotufo' ORDER BY id LIMIT 1").fetchone()
    return {"entidades": ents, "tipos": tipos,
            "regularidade": (lotufo[0] if lotufo else None) if REGULARIDADE in lista else None}


def _exigidos_ativos(conn) -> tuple[dict[int, dict[int, dict]], dict[int, int], set[int]]:
    """Uniao das exigencias dos contratos ATIVOS, nas duas naturezas.
    -> ({entidade: {tipo_id: tipo}}, {entidade: primeiro contrato}, {entidades com regularidade exigida})"""
    cert: dict[int, dict[int, dict]] = {}
    contrato_de: dict[int, int] = {}
    regs: set[int] = set()
    for r in conn.execute("SELECT id FROM contratos WHERE estado='ativo' ORDER BY id").fetchall():
        for natureza in ("execucao", "reajuste"):
            ex = exigidos(conn, r["id"], natureza)
            for e in ex["entidades"]:
                contrato_de.setdefault(e, r["id"])
                cert.setdefault(e, {}).update({t["id"]: t for t in ex["tipos"]})
            if ex["regularidade"]:
                regs.add(ex["regularidade"])
                contrato_de.setdefault(ex["regularidade"], r["id"])
    return cert, contrato_de, regs


# --- situacao ---------------------------------------------------------------------------------

def situacao(conn: sqlite3.Connection, entidade_id: int, tipo: dict, hoje: datetime.date) -> dict:
    v = certidoes.vigente(conn, entidade_id, tipo["id"], na_data=hoje.isoformat())
    if v:
        dias = (_d(v["validade"]) - hoje).days
        return {"situacao": "vencendo" if dias <= limiar(v) else "ok", "dias": dias, "certidao": v}
    if certidoes.nao_se_aplica_vigora(conn, entidade_id, tipo["id"]):
        return {"situacao": "nao_se_aplica", "dias": None, "certidao": None}
    ultima = certidoes.ultima_emissao(conn, entidade_id, tipo["id"], hoje.isoformat())
    return {"situacao": "vencida" if ultima else "faltando", "dias": None, "certidao": ultima}


# --- regularidade mensal ----------------------------------------------------------------------

def _mes_menos(mes: str, n: int) -> str:
    a, m = int(mes[:4]), int(mes[5:7])
    total = a * 12 + (m - 1) - n
    return f"{total // 12:04d}-{total % 12 + 1:02d}"


def competencia_esperada(hoje: datetime.date) -> str:
    """Competencia da regularidade que o protocolo de HOJE leva.

    Medido nos protocolos de 2026: 22/06 levou 04/2026 e 16/09 levou 07/2026 (mes menos 2); 03/08
    levou 05/2026 (mes menos 3): antes do dia 10 o DP ainda nao fechou a do mes menos 2.
    """
    return _mes_menos(hoje.isoformat()[:7], 2 if hoje.day >= DIA_REGULARIDADE else 3)


def registrar_regularidade(conn, usuario_id: int, entidade_id: int, competencia: str, arquivo: str,
                           sha256: str, tamanho: int, nome_original: str | None) -> int:
    if not _COMPETENCIA.match(competencia or ""):
        raise ValueError(f"Competência inválida: {competencia!r} (use AAAA-MM)")
    if competencia > tempo.hoje_local().isoformat()[:7]:
        raise ValueError(f"A competência {_mes_br(competencia)} ainda não aconteceu")
    with db.mutacao(conn):
        if entidades.detalhe(conn, entidade_id) is None:
            raise ValueError(f"Entidade {entidade_id} não encontrada")
        if conn.execute("SELECT 1 FROM regularidades WHERE entidade_id=? AND competencia=? AND sha256=?",
                        (entidade_id, competencia, sha256)).fetchone():
            raise ValueError("Este arquivo já está anexado para essa competência")
        cur = conn.execute(
            "INSERT INTO regularidades (entidade_id, competencia, arquivo, sha256, tamanho, nome_original, usuario_id) "
            "VALUES (?,?,?,?,?,?,?)", (entidade_id, competencia, arquivo, sha256, tamanho, nome_original, usuario_id))
        rid = cur.lastrowid
        auditoria.registrar(conn, usuario_id, "regularidade.registrar", "regularidade", rid, None,
                            {"entidade_id": entidade_id, "competencia": competencia, "arquivo": arquivo,
                             "sha256": sha256, "tamanho": tamanho, "nome_original": nome_original})
    return rid


def regularidade_vigente(conn, entidade_id: int) -> dict | None:
    r = conn.execute("SELECT * FROM regularidades WHERE entidade_id=? ORDER BY competencia DESC, id DESC LIMIT 1",
                     (entidade_id,)).fetchone()
    return dict(r) if r else None


def situacao_regularidade(conn, entidade_id: int, hoje: datetime.date) -> dict:
    v = regularidade_vigente(conn, entidade_id)
    esperada = competencia_esperada(hoje)
    s = "ok" if v and v["competencia"] >= esperada else ("atrasada" if v else "faltando")
    return {"situacao": s, "competencia": v["competencia"] if v else None, "esperada": esperada, "regularidade": v}


# --- gravar certidao --------------------------------------------------------------------------

def ler(conn, texto: str) -> dict:
    """Leitura + empresa do cadastro (pelo CNPJ) + tipo cadastrado. Recusa com motivo estavel."""
    cads = {e["cnpj"]: e for e in entidades.listar(conn)}
    lido = leitura_certidao.ler(texto, frozenset(cads))
    e = cads.get(lido["cnpj"])
    if e is None:
        c = lido["cnpj"]
        raise leitura_certidao.Recusa(
            "empresa-desconhecida",
            f"O CNPJ {c[:2]}.{c[2:5]}.{c[5:8]}/{c[8:12]}-{c[12:]} do documento não é de nenhuma empresa do cadastro.")
    t = tipo_por_chave(conn, lido["tipo"])
    return {**lido, "entidade_id": e["id"], "entidade": _nome(e), "tipo_id": t["id"], "tipo_nome": t["nome"]}


def dados_manuais(conn, entidade_id: int, tipo_chave: str, emissao: str, validade: str | None,
                  natureza: str | None, numero: str | None, cnpjs_do_texto: list[str] = ()) -> dict:
    """Campos digitados. `cnpjs_do_texto`: os CNPJs validos do PDF, quando ele tem texto -- a empresa
    digitada precisa ser uma delas (a CND da Guaxe nao vai para a Lotufo)."""
    if tipo_chave not in TIPOS:
        raise ValueError(f"Tipo inválido: {tipo_chave!r}")
    if natureza not in leitura_certidao.NATUREZAS:
        raise ValueError("Informe se a certidão é negativa ou positiva com efeito de negativa "
                         "(certidão positiva não serve para protocolo)")
    e = entidades.detalhe(conn, entidade_id)
    if e is None:
        raise ValueError(f"Entidade {entidade_id} não encontrada")
    if cnpjs_do_texto and e["cnpj"] not in cnpjs_do_texto:
        raise ValueError(f"O CNPJ de {_nome(e)} não aparece no documento — confira se o arquivo é dessa empresa")
    emissao = _d(emissao).isoformat()
    if not validade and tipo_chave == "falencia":
        validade = feriados.somar_dias_uteis(_d(emissao), leitura_certidao.DIAS_UTEIS_FALENCIA).isoformat()
    if not validade:
        raise ValueError("Informe a validade")
    t = tipo_por_chave(conn, tipo_chave)
    return {"entidade_id": entidade_id, "entidade": _nome(e), "tipo": tipo_chave, "tipo_id": t["id"],
            "tipo_nome": t["nome"], "emissao": emissao, "validade": _d(validade).isoformat(),
            "natureza": natureza, "numero": (numero or "").strip() or None}


def gravar_certidao(conn, usuario_id: int, dados: dict, arquivo: str, sha256: str,
                    nome_original: str | None, leitura: str) -> int:
    with db.mutacao(conn):
        if conn.execute("SELECT 1 FROM certidoes WHERE entidade_id=? AND tipo_id=? AND emissao=? AND validade=? "
                        "AND estado='vigente'", (dados["entidade_id"], dados["tipo_id"], dados["emissao"],
                                                 dados["validade"])).fetchone():
            raise ValueError(f"Esta certidão já está cadastrada (válida até {_br(dados['validade'])})")
        return certidoes.registrar(conn, usuario_id, dados["entidade_id"], dados["tipo_id"], dados["emissao"],
                                   dados["validade"], arquivo, sha256, "upload", dados.get("numero"),
                                   natureza=dados["natureza"], leitura=leitura, nome_original=nome_original)


# --- painel, avisos, ZIP ----------------------------------------------------------------------

def painel(conn, hoje: datetime.date | None = None) -> dict:
    hoje = hoje or tempo.hoje_local()
    cert, _, regs = _exigidos_ativos(conn)
    tipos = [tipo_por_chave(conn, k) for k in TIPOS]
    com_docs = {r[0] for r in conn.execute("SELECT entidade_id FROM certidoes UNION SELECT entidade_id FROM regularidades")}
    ordem = {"lotufo": 0, "consorcio": 1, "consorciada": 2}
    ents = sorted((e for e in entidades.listar(conn) if e["id"] in cert or e["id"] in regs or e["id"] in com_docs),
                  key=lambda e: (ordem.get(e["papel"], 9), _nome(e)))
    empresas = []
    for e in ents:
        linhas = []
        for t in tipos:
            s = situacao(conn, e["id"], t, hoje)
            linhas.append({"tipo_id": t["id"], "chave": t["chave"], "tipo": t["nome"], "link_emissao": t["link_emissao"],
                           "exigida": t["id"] in cert.get(e["id"], {}), **s})
        tem_reg = e["id"] in regs or regularidade_vigente(conn, e["id"]) is not None
        empresas.append({"entidade_id": e["id"], "entidade": _nome(e), "cnpj": e["cnpj"], "papel": e["papel"],
                         "certidoes": linhas, "regularidade_exigida": e["id"] in regs,
                         "regularidade": situacao_regularidade(conn, e["id"], hoje) if tem_reg else None})
    return {"hoje": hoje.isoformat(), "empresas": empresas}


def avisos(conn, hoje: datetime.date | None = None) -> list[dict]:
    """Spec §11: 'Documentos da empresa' (uma linha por empresa) e 'Regularidade do mes' (dia 10)."""
    hoje = hoje or tempo.hoje_local()
    cert, contrato_de, regs = _exigidos_ativos(conn)
    out = []
    for eid in sorted(cert):
        e = entidades.detalhe(conn, eid)
        partes, grave = [], False
        for t in sorted(cert[eid].values(), key=lambda t: TIPOS.index(t["chave"]) if t["chave"] in TIPOS else 99):
            s = situacao(conn, eid, t, hoje)
            rot = ROTULO.get(t["chave"], t["nome"])
            if s["situacao"] == "vencida":
                partes.append(f"{rot} vencida em {_br_curta(s['certidao']['validade'])}")
                grave = True
            elif s["situacao"] == "faltando":
                partes.append(f"{rot} sem certidão")
                grave = True
            elif s["situacao"] == "vencendo":
                partes.append(f"{rot} vence hoje" if s["dias"] == 0 else
                              f"{rot} vence em {s['dias']} dia{'s' if s['dias'] > 1 else ''}")
        if partes:
            out.append({"tipo": "documentos_empresa", "nivel": "acao" if grave else "atencao",
                        "entidade_id": eid, "contrato_id": contrato_de[eid],
                        "mensagem": f"{_nome(e)}: {'; '.join(partes)}"})
    if hoje.day >= DIA_REGULARIDADE:
        for eid in sorted(regs):
            s = situacao_regularidade(conn, eid, hoje)
            if s["situacao"] == "ok":
                continue
            e = entidades.detalhe(conn, eid)
            ultima = f"; a última é de {_mes_br(s['competencia'])}" if s["competencia"] else ""
            out.append({"tipo": "regularidade_mes", "nivel": "acao", "entidade_id": eid,
                        "contrato_id": contrato_de[eid],
                        "mensagem": f"{_nome(e)}: regularidade de {_mes_br(s['esperada'])} não anexada{ultima}"})
    return out


def zip_vigentes(conn, entidade_id: int, na_data: str) -> tuple[str, bytes]:
    e = entidades.detalhe(conn, entidade_id)
    if e is None:
        raise ValueError(f"Entidade {entidade_id} não encontrada")
    nome = re.sub(r'[\\/:*?"<>|]', "-", _nome(e))
    buf, n = io.BytesIO(), 0
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for chave in TIPOS:
            v = certidoes.vigente(conn, entidade_id, tipo_por_chave(conn, chave)["id"], na_data=na_data)
            if v is None or not v["arquivo"].startswith("certidoes/"):
                continue
            z.write(arquivos.caminho_seguro(v["arquivo"]), f"{nome} - {chave.upper()} - {v['validade']}.pdf")
            n += 1
    if n == 0:
        raise ValueError(f"{_nome(e)} não tem nenhuma certidão vigente em {_br(na_data)}")
    return f"Certidoes - {nome} - {na_data}.zip", buf.getvalue()


# --- carga inicial (decisao 13) ---------------------------------------------------------------

class _Ensaio(Exception):
    """Sinal interno: desfaz a transacao do ensaio."""


def importar_pasta(conn, usuario_id: int, pasta: Path, ensaio: bool, hoje: datetime.date | None = None) -> dict:
    hoje_iso = (hoje or tempo.hoje_local()).isoformat()
    rel = {"ensaio": ensaio, "gravadas": [], "repetidas": [], "vencidas": [], "positivas": [], "sem_leitura": []}
    candidatos = []
    for p in sorted(Path(pasta).rglob("*.pdf")):
        nome = str(p.relative_to(pasta))
        if p.stat().st_size > arquivos.TETO_BYTES:       # mesmo teto do upload
            rel["sem_leitura"].append({"arquivo": nome, "motivo": f"maior que {arquivos.TETO_MB} MB"})
            continue
        dados = p.read_bytes()
        try:
            texto = leitura_pdf.texto_de_pdf_com_limite(dados)
        except Exception as e:        # PDF que nao abre ou estoura teto: fila humana
            rel["sem_leitura"].append({"arquivo": nome, "motivo": type(e).__name__})
            continue
        try:
            lido = ler(conn, texto)
        except leitura_certidao.Recusa as e:
            (rel["positivas"] if e.motivo == "positiva" else rel["sem_leitura"]).append(
                {"arquivo": nome, "motivo": e.motivo})
            continue
        if lido["validade"] < hoje_iso:
            rel["vencidas"].append({"arquivo": nome, "validade": lido["validade"]})
            continue
        candidatos.append((nome, dados, lido))
    if not ensaio:     # arquivo em disco ANTES do banco: orfao por hash e' inofensivo, linha sem arquivo nao
        for _, dados, _ in candidatos:
            arquivos.gravar_bytes("certidoes", dados, "pdf")
    try:
        with db.mutacao(conn):
            for nome, dados, lido in candidatos:
                sha = arquivos.sha_de(dados)
                try:
                    cid = gravar_certidao(conn, usuario_id, lido, f"certidoes/{sha}.pdf", sha, Path(nome).name,
                                          "automatica")
                except ValueError:
                    rel["repetidas"].append({"arquivo": nome})
                    continue
                rel["gravadas"].append({"arquivo": nome, "id": cid, "entidade": lido["entidade"],
                                        "tipo": lido["tipo"], "validade": lido["validade"]})
            if ensaio:
                raise _Ensaio
    except _Ensaio:
        pass
    return rel
```

- [ ] **Step 5: Rodar e ver passar**

Run: `cd backend && .venv\Scripts\python -m pytest tests/test_documentos.py tests/test_certidoes.py -v`
Expected: PASS. Se `db.mutacao` aninhado não propagar a exceção do ensaio como esperado, conferir o padrão de `cadastro_aplicar._Ensaio` e seguir o mesmo.

- [ ] **Step 6: Commit**

```bash
git add backend/app/documentos.py backend/app/certidoes.py backend/tests/test_documentos.py
git commit -m "feat: servico de documentos de protocolo - exigencia por orgao e consorciadas, regularidade, avisos, ZIP, carga"
```

---

### Task 6: Checklist do protocolo pela exigência nova

**Files:**
- Modify: `backend/app/checklist.py` (`pronto_para_protocolar(conn, contrato_id, natureza="execucao")`)
- Modify: `backend/app/medicoes.py:148-190` (`registrar_protocolo` passa `m["tipo"]`; mensagem com a empresa quando há mais de uma)
- Modify: `backend/app/api_certidoes.py` (rota do checklist aceita `natureza` na query)
- Modify: `backend/tests/test_notas.py` (o fixture `conn` neutraliza `documentos.exigidos`: a fixture `integra` aplica o cadastro REAL, e a lista da SINFRA passaria a travar o protocolo da linha 215)
- Test: `backend/tests/test_checklist.py`

**Interfaces:**
- Consumes: `documentos.exigidos/situacao/situacao_regularidade`.
- Produces: resposta do checklist = `{"contrato_id", "entidade_id", "entidade", "natureza", "itens": [{"entidade_id", "entidade", "tipo_id", "tipo", "chave", "jurisdicao", "situacao", "validade", "dias", "certidao_id", "link_emissao", "competencia"?, "esperada"?}], "pronto"}`; `situacao` continua em `ok|vencendo|pendente|nao_se_aplica` (vencida e faltando viram `pendente`).

- [ ] **Step 1: Testes novos**

```python
# acrescentar em backend/tests/test_checklist.py
def test_consorcio_cobra_consorciadas_e_regularidade(conn, monkeypatch):
    import json
    from app import documentos, tempo
    monkeypatch.setattr(tempo, "hoje_local", lambda: datetime.date(2026, 9, 23))
    conn.execute("INSERT INTO entidades (id, nome, cnpj, papel, nome_curto) VALUES "
                 "(20, 'Consórcio Complexo Leblon', '00000000000400', 'consorcio', 'Complexo Leblon'), "
                 "(21, 'Rivoli', '00000000000500', 'consorciada', 'Rivoli')")
    conn.execute("INSERT INTO entidade_consorciadas VALUES (20, 1), (20, 21)")
    conn.execute("INSERT INTO orgaos (chave, nome, familia, regras) VALUES ('s','S','sinfra',?)",
                 (json.dumps({"documentos_medicao": ["fgts", "regularidade"], "documentos_reajuste": ["estadual"]}),))
    conn.execute("INSERT INTO contratos (orgao, numero_instrumento, objeto, valor_original_centavos, orgao_id, entidade_id) "
                 "VALUES ('S', 'L-1', 'o', 100, 1, 20)")
    cid = conn.execute("SELECT MAX(id) FROM contratos").fetchone()[0]
    ck = checklist.pronto_para_protocolar(conn, cid, "execucao")
    assert [(i["entidade_id"], i["chave"]) for i in ck["itens"]] == [(20, "fgts"), (1, "fgts"), (21, "fgts"), (1, "regularidade")]
    assert ck["pronto"] is False and all(i["situacao"] == "pendente" for i in ck["itens"])
    reaj = checklist.pronto_para_protocolar(conn, cid, "reajuste")
    assert [(i["entidade_id"], i["chave"]) for i in reaj["itens"]] == [(20, "estadual"), (1, "estadual"), (21, "estadual")]
```

Os testes existentes de `test_checklist.py` continuam (contratos sem órgão → tipos `aplicavel_por_padrao`). Ajustar o fixture `conn` do arquivo se ele não tiver `db.migrate` com a 024 (ele usa `db.migrate`, então já tem).

- [ ] **Step 2: Rodar e ver falhar**

Run: `cd backend && .venv\Scripts\python -m pytest tests/test_checklist.py -v`
Expected: FAIL no teste novo (`pronto_para_protocolar() takes 2 positional arguments`).

- [ ] **Step 3: Implementar**

`checklist.py` (docstring do módulo atualizada: a exigência vem de `documentos.exigidos`; as três decisões antigas continuam valendo, a 3 agora só para contrato sem órgão):

```python
def pronto_para_protocolar(conn: sqlite3.Connection, contrato_id: int, natureza: str = "execucao") -> dict:
    c = conn.execute("SELECT * FROM contratos WHERE id=?", (contrato_id,)).fetchone()
    if c is None:
        raise ValueError(f"Contrato {contrato_id} não encontrado")
    hoje = tempo.hoje_local()
    ex = documentos.exigidos(conn, contrato_id, natureza)
    nomes = {e: entidades.detalhe(conn, e) for e in ex["entidades"] + ([ex["regularidade"]] if ex["regularidade"] else [])}
    nome = lambda e: (nomes[e] or {}).get("nome_curto") or (nomes[e] or {}).get("nome")
    itens = []
    for eid in ex["entidades"]:
        for t in ex["tipos"]:
            s = documentos.situacao(conn, eid, t, hoje)
            sit = s["situacao"] if s["situacao"] in ("ok", "vencendo", "nao_se_aplica") else "pendente"
            vale = sit in ("ok", "vencendo")
            itens.append({"entidade_id": eid, "entidade": nome(eid), "tipo_id": t["id"], "tipo": t["nome"],
                          "chave": t.get("chave"), "jurisdicao": t["jurisdicao"], "situacao": sit,
                          "validade": s["certidao"]["validade"] if vale else None, "dias": s["dias"],
                          "certidao_id": s["certidao"]["id"] if vale else None, "link_emissao": t.get("link_emissao")})
    if ex["regularidade"]:
        r = documentos.situacao_regularidade(conn, ex["regularidade"], hoje)
        itens.append({"entidade_id": ex["regularidade"], "entidade": nome(ex["regularidade"]), "tipo_id": None,
                      "tipo": "Regularidade mensal", "chave": "regularidade", "jurisdicao": None,
                      "situacao": "ok" if r["situacao"] == "ok" else "pendente", "validade": None, "dias": None,
                      "certidao_id": None, "link_emissao": None,
                      "competencia": r["competencia"], "esperada": r["esperada"]})
    ent = contratos.entidade_de(c)
    e = entidades.detalhe(conn, ent)
    return {"contrato_id": contrato_id, "entidade_id": ent, "entidade": e["nome"] if e else None,
            "natureza": natureza, "itens": itens, "pronto": all(i["situacao"] in LIBERAM for i in itens)}
```

`medicoes.registrar_protocolo`: `ck = checklist.pronto_para_protocolar(conn, m["contrato_id"], m["tipo"])`; os nomes pendentes passam a `i["tipo"]` quando todos os itens pendentes são da mesma empresa, e `f"{i['entidade']}: {i['tipo']}"` quando há mais de uma. A frase muda de "tipos de certidão sem validade hoje ... Anexe em Certidões" para "documentos sem validade hoje ... Anexe em Documentos"; a chave `ressalva["certidoes_pendentes"]` **não muda de nome** (a auditoria já gravada e `test_api_medicoes.py:227` dependem dela).

`api_certidoes.checklist_protocolo`: parâmetro `natureza: Literal["execucao", "projeto", "reajuste"] = "execucao"` repassado.

**`conftest.sem_certidoes_exigidas` não muda.** Ela zera `aplicavel_por_padrao`, e os contratos criados por API nos testes não têm órgão, então continuam caindo no fallback; neutralizar `exigidos` ali mataria a prova da trava em `test_api_medicoes.py` (`_com_tipo_exigido`, linhas 193-205). Quem usa o cadastro REAL e protocola é `test_notas.py`: no fixture `conn` dele, `monkeypatch.setattr(documentos, "exigidos", lambda conn, cid, natureza: {"entidades": [], "tipos": [], "regularidade": None})`. (`test_espelhos` escapa: o `_cad()` dele não tem lista de documentos.)

- [ ] **Step 4: Suíte inteira**

Run: `cd backend && .venv\Scripts\python -m pytest`
Expected: PASS. Falha em teste que compare a frase antiga de protocolo travado: atualizar a frase esperada no teste (a regra não mudou).

- [ ] **Step 5: Commit**

```bash
git add backend/app/checklist.py backend/app/medicoes.py backend/app/api_certidoes.py backend/tests/test_notas.py backend/tests/test_checklist.py backend/tests/test_api_medicoes.py
git commit -m "feat: checklist do protocolo pela exigencia do orgao, com consorciadas, regularidade e natureza da medicao"
```

---

### Task 7: Rotas `api_documentos.py` e saída do leitor genérico

**Files:**
- Create: `backend/app/api_documentos.py`; Modify: `backend/app/main.py` (incluir o router)
- Modify: `backend/app/api_certidoes.py` (sai `ler_pdf` e `upload`), `backend/app/leitura_pdf.py` (sai a seção "localização por regex" e o validador: `CAMPOS`, `_ROTULO`, `_D` em diante até `ler_certidao`, mantendo `MANUAL`, `TextoInadequado` e a extração)
- Test: `backend/tests/test_api_documentos.py`; Modify: `backend/tests/test_api_certidoes.py`, `backend/tests/test_leitura_pdf.py`

**Interfaces:**
- Consumes: `documentos.*`, `arquivos.blocos_validados/receber_pdf/pasta/caminho_seguro/pasta_certidoes`, `leitura_pdf.texto_de_pdf_com_limite`.
- Produces:
  - `GET /api/documentos` → `documentos.painel` (ver_paineis)
  - `POST /api/documentos/certidoes/ler` (multipart `arquivo`) → `{"ok": true, "leitura": {...}}` ou `{"ok": false, "motivo", "mensagem", "digitavel": bool}` (editar_cadastros; não grava nada)
  - `POST /api/documentos/certidoes` (multipart `arquivo` + opcionais `entidade_id`, `tipo`, `emissao`, `validade`, `natureza`, `numero`) → 201 `{"id", "leitura": "automatica"|"manual", ...dados}`; 422 recusa; 409 repetida
  - `POST /api/documentos/regularidades` (multipart `arquivo`, `entidade_id`, `competencia`) → 201 `{"id"}`
  - `GET /api/documentos/regularidades/{id}/arquivo` → PDF
  - `GET /api/documentos/zip?entidade_id=&data=AAAA-MM-DD` → `application/zip` com `Content-Disposition: attachment; filename*=UTF-8''...`

- [ ] **Step 1: Testes das rotas**

```python
# backend/tests/test_api_documentos.py
import datetime
import io
import pathlib
import zipfile

import pytest

from app import leitura_pdf, tempo
from tests.conftest import _pdf_com_texto

FIX = pathlib.Path(__file__).parent / "fixtures" / "certidoes"


@pytest.fixture(autouse=True)
def hoje(monkeypatch):
    monkeypatch.setattr(tempo, "hoje_local", lambda: datetime.date(2026, 9, 23))


def _texto(monkeypatch, nome_ou_texto):
    texto = (FIX / f"{nome_ou_texto}.txt").read_text(encoding="utf-8") if (FIX / f"{nome_ou_texto}.txt").exists() \
        else nome_ou_texto
    monkeypatch.setattr(leitura_pdf, "texto_de_pdf_com_limite", lambda pdf: texto)


def _arq(nome="c.pdf"):
    return {"arquivo": (nome, _pdf_com_texto("x"), "application/pdf")}


def test_ler_e_gravar_automatico(client_admin, monkeypatch):
    _texto(monkeypatch, "trabalhista-lotufo")
    r = client_admin.post("/api/documentos/certidoes/ler", files=_arq())
    assert r.status_code == 200 and r.json()["ok"] is True
    assert r.json()["leitura"]["tipo"] == "trabalhista" and r.json()["leitura"]["entidade_id"] == 1
    g = client_admin.post("/api/documentos/certidoes", files=_arq("cndt.pdf"),
                          data={"tipo": "federal", "validade": "2030-01-01"})      # ignorados: a leitura manda
    assert g.status_code == 201, g.text
    assert (g.json()["leitura"], g.json()["tipo"], g.json()["validade"]) == ("automatica", "trabalhista", "2026-12-21")
    assert client_admin.post("/api/documentos/certidoes", files=_arq("cndt.pdf")).status_code == 409


def test_positiva_e_recusada_mesmo_com_campos(client_admin, monkeypatch):
    _texto(monkeypatch, "estadual-guaxe-cpd")
    r = client_admin.post("/api/documentos/certidoes/ler", files=_arq())
    # a natureza e' conferida antes da empresa: a Guaxe nem precisa estar no banco de teste
    assert (r.json()["ok"], r.json()["motivo"], r.json()["digitavel"]) == (False, "positiva", False)
    g = client_admin.post("/api/documentos/certidoes", files=_arq(),
                          data={"entidade_id": "1", "tipo": "estadual", "emissao": "2026-06-24",
                                "validade": "2026-08-22", "natureza": "negativa"})
    assert g.status_code == 422


def test_recusa_nao_deixa_pdf_no_disco(client_admin, monkeypatch):
    from app import arquivos
    _texto(monkeypatch, "estadual-guaxe-cpd")
    antes = set(arquivos.pasta_certidoes().glob("*.pdf"))
    assert client_admin.post("/api/documentos/certidoes", files=_arq()).status_code == 422
    assert set(arquivos.pasta_certidoes().glob("*.pdf")) == antes


def test_sem_texto_vira_digitacao(client_admin, monkeypatch):
    _texto(monkeypatch, "")
    r = client_admin.post("/api/documentos/certidoes/ler", files=_arq())
    assert (r.json()["ok"], r.json()["motivo"], r.json()["digitavel"]) == (False, "sem-texto", True)
    assert client_admin.post("/api/documentos/certidoes", files=_arq()).status_code == 422   # sem campos
    g = client_admin.post("/api/documentos/certidoes", files=_arq(),
                          data={"entidade_id": "1", "tipo": "falencia", "emissao": "2026-08-03", "natureza": "negativa"})
    assert g.status_code == 201 and g.json()["leitura"] == "manual" and g.json()["validade"] == "2026-09-14"


def test_regularidade_e_zip(client_admin, monkeypatch):
    r = client_admin.post("/api/documentos/regularidades", files=_arq("072026 - LOTUFO ENGENHARIA.pdf"),
                          data={"entidade_id": "1", "competencia": "2026-07"})
    assert r.status_code == 201, r.text
    assert client_admin.get(f"/api/documentos/regularidades/{r.json()['id']}/arquivo").status_code == 200
    assert client_admin.post("/api/documentos/regularidades", files=_arq(),
                             data={"entidade_id": "1", "competencia": "07/2026"}).status_code == 422
    _texto(monkeypatch, "fgts-lotufo")
    monkeypatch.setattr(tempo, "hoje_local", lambda: datetime.date(2026, 8, 1))
    assert client_admin.post("/api/documentos/certidoes", files=_arq()).status_code == 201
    z = client_admin.get("/api/documentos/zip", params={"entidade_id": 1, "data": "2026-08-01"})
    assert z.status_code == 200 and z.headers["content-type"] == "application/zip"
    assert zipfile.ZipFile(io.BytesIO(z.content)).namelist()[0].endswith("FGTS - 2026-08-09.pdf")
    assert client_admin.get("/api/documentos/zip", params={"entidade_id": 1, "data": "2026-12-01"}).status_code == 422


def test_rotas_antigas_de_leitura_e_upload_sairam(client_admin):
    assert client_admin.post("/api/certidoes/ler-pdf", files=_arq()).status_code in (404, 405)
    assert client_admin.post("/api/certidoes/upload", files=_arq()).status_code in (404, 405)
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `cd backend && .venv\Scripts\python -m pytest tests/test_api_documentos.py -v`
Expected: FAIL (404 nas rotas novas).

- [ ] **Step 3: Implementar `api_documentos.py`**

```python
# backend/app/api_documentos.py
"""Rotas dos documentos de protocolo (bloco 4, spec §9 e §10.4).

Gravar RELE o PDF no servidor: o que a tela mostrou e' conferencia, nao fonte (decisao 5 do plano).
Os campos do formulario so' valem quando o leitor nao consegue (motivo em DIGITAVEIS).
"""
import datetime
import sqlite3
import urllib.parse
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response

from app import arquivos, documentos, leitura_certidao, leitura_pdf, tempo
from app.api_auth import conexao
from app.permissoes import exigir

router = APIRouter()
MAX_INT64 = 9223372036854775807


def _texto(pdf: bytes) -> str:
    try:
        return leitura_pdf.texto_de_pdf_com_limite(pdf)
    except leitura_pdf.TextoInadequado as e:
        raise HTTPException(422, str(e))
    except Exception as e:
        raise HTTPException(422, f"Não foi possível ler o PDF enviado ({type(e).__name__}) — envie o arquivo original.")


@router.get("/api/documentos")
def painel(usuario: dict = Depends(exigir("ver_paineis", com_csrf=False)),
           conn: sqlite3.Connection = Depends(conexao)):
    return documentos.painel(conn)


@router.post("/api/documentos/certidoes/ler")
def ler(arquivo: UploadFile = File(...), usuario: dict = Depends(exigir("editar_cadastros")),
        conn: sqlite3.Connection = Depends(conexao)):
    texto = _texto(b"".join(arquivos.blocos_validados(arquivo)))
    try:
        return {"ok": True, "leitura": documentos.ler(conn, texto)}
    except leitura_certidao.Recusa as e:
        return {"ok": False, "motivo": e.motivo, "mensagem": str(e), "digitavel": e.motivo in leitura_certidao.DIGITAVEIS}


@router.post("/api/documentos/certidoes", status_code=201)
def gravar(arquivo: UploadFile = File(...),
           entidade_id: int | None = Form(default=None, ge=1, le=MAX_INT64),
           tipo: Literal["federal", "fgts", "trabalhista", "estadual", "municipal", "falencia"] | None = Form(default=None),
           emissao: datetime.date | None = Form(default=None),
           validade: datetime.date | None = Form(default=None),
           natureza: Literal["negativa", "positiva_efeito_negativa"] | None = Form(default=None),
           numero: str | None = Form(default=None, max_length=100),
           usuario: dict = Depends(exigir("editar_cadastros")),
           conn: sqlite3.Connection = Depends(conexao)):
    # Em memoria (teto de 10 MB em blocos); a extracao em subprocesso prova que o PDF abre. O arquivo
    # so' vai para o disco depois de decidido gravar: recusa nao deixa PDF orfao na pasta de dados.
    pdf = b"".join(arquivos.blocos_validados(arquivo))
    texto = _texto(pdf)
    try:
        dados, leitura = documentos.ler(conn, texto), "automatica"
    except leitura_certidao.Recusa as e:
        if e.motivo not in leitura_certidao.DIGITAVEIS:
            raise HTTPException(422, str(e))
        if entidade_id is None or tipo is None or emissao is None:
            raise HTTPException(422, f"{e} Faltam empresa, tipo e emissão.")
        try:
            dados = documentos.dados_manuais(conn, entidade_id, tipo, emissao.isoformat(),
                                             validade.isoformat() if validade else None, natureza, numero,
                                             cnpjs_do_texto=leitura_certidao.cnpjs_no_texto(texto))
        except ValueError as v:
            raise HTTPException(422, str(v))
        leitura = "manual"
    _, sha = arquivos.gravar_bytes("certidoes", pdf, "pdf")
    try:
        cid = documentos.gravar_certidao(conn, usuario["id"], dados, f"certidoes/{sha}.pdf", sha,
                                         arquivo.filename, leitura)
    except ValueError as v:
        raise HTTPException(409 if "já está cadastrada" in str(v) else 422, str(v))
    return {"id": cid, "leitura": leitura, **{k: v for k, v in dados.items() if k != "evidencia"}}


@router.post("/api/documentos/regularidades", status_code=201)
def regularidade(arquivo: UploadFile = File(...),
                 entidade_id: int = Form(..., ge=1, le=MAX_INT64),
                 competencia: str = Form(..., pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
                 usuario: dict = Depends(exigir("editar_cadastros")),
                 conn: sqlite3.Connection = Depends(conexao)):
    pasta = arquivos.pasta("regularidades")
    sha = arquivos.receber_pdf(arquivo, pasta)
    try:
        rid = documentos.registrar_regularidade(conn, usuario["id"], entidade_id, competencia,
                                                f"regularidades/{sha}.pdf", sha, (pasta / f"{sha}.pdf").stat().st_size,
                                                arquivo.filename)
    except ValueError as v:
        raise HTTPException(422, str(v))
    return {"id": rid}


@router.get("/api/documentos/regularidades/{rid}/arquivo")
def baixar_regularidade(rid: int, usuario: dict = Depends(exigir("ver_paineis", com_csrf=False)),
                        conn: sqlite3.Connection = Depends(conexao)):
    r = conn.execute("SELECT * FROM regularidades WHERE id=?", (rid,)).fetchone()
    if r is None:
        raise HTTPException(404, "Regularidade não encontrada")
    caminho = arquivos.caminho_seguro(r["arquivo"])
    if not caminho.is_file():
        raise HTTPException(404, "Arquivo da regularidade não encontrado")
    return FileResponse(caminho, media_type=arquivos.MIME, filename=f"regularidade-{r['competencia']}.pdf",
                        headers={"X-Content-Type-Options": "nosniff"})


@router.get("/api/documentos/zip")
def zip_vigentes(entidade_id: int, data: datetime.date | None = None,
                 usuario: dict = Depends(exigir("ver_paineis", com_csrf=False)),
                 conn: sqlite3.Connection = Depends(conexao)):
    na_data = (data or tempo.hoje_local()).isoformat()
    try:
        nome, dados = documentos.zip_vigentes(conn, entidade_id, na_data)
    except ValueError as v:
        raise HTTPException(422, str(v))
    return Response(dados, media_type="application/zip",
                    headers={"Content-Disposition": f"attachment; filename*=UTF-8''{urllib.parse.quote(nome)}"})
```

`main.py`: `from app import api_documentos` e `app.include_router(api_documentos.router)` ao lado dos outros. `arquivos.caminho_seguro` precisa aceitar `regularidades/`; conferir que ele só exige estar dentro da pasta do banco.

- [ ] **Step 4: Tirar o leitor genérico**

- `api_certidoes.py`: apagar `ler_pdf` e `upload` (e imports que ficarem sem uso: `leitura_pdf`, `certidoes.registrar` via rota).
- `leitura_pdf.py`: apagar da linha `# --- localizacao por regex` até o fim (`ler_certidao`), e `CAMPOS`/`_ROTULO`; a docstring do módulo passa a dizer que ele extrai texto de PDF com tetos e subprocesso, e que a leitura de certidão mora em `leitura_certidao.py`.
- `test_leitura_pdf.py`: apagar os testes de `localizar`/`validar`/`ler_certidao` (linhas 72-162 e 395-452 hoje: CND completa, CRF, CNDT, estadual genérica, avisos, datas, CNPJ, tipo, mojibake, rótulo de contribuinte, evidência); ficam os de extração, tetos, bomba, subprocesso.
- `test_api_certidoes.py`: o helper `_upload` (linha 45, chamado 39 vezes) não serve só às guardas: ele SEMEIA certidões para os testes de download, dedupe, não-se-aplica e estado. Reescrever o helper para semear sem a rota que sai: gravar o PDF com `arquivos.gravar_bytes("certidoes", pdf, "pdf")` e a linha com `certidoes.registrar(conn, 1, entidade_id, tipo_id, emissao, validade, f"certidoes/{sha}.pdf", sha, "upload")`, devolvendo o mesmo que o teste usava (o id). Os testes que provam as guardas do arquivo (content-type, `%PDF-`, 10 MB, PDF que não abre) passam para `test_api_documentos.py` apontando para `/api/documentos/regularidades` (mesmas guardas, sem leitura no meio); os de `ler-pdf` saem. Conferir no fim que nenhum teste chama `/api/certidoes/upload` ou `/api/certidoes/ler-pdf` (só o `test_rotas_antigas_de_leitura_e_upload_sairam`).

- [ ] **Step 5: Suíte inteira**

Run: `cd backend && .venv\Scripts\python -m pytest`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/api_documentos.py backend/app/main.py backend/app/api_certidoes.py backend/app/leitura_pdf.py backend/tests
git commit -m "feat: rotas de documentos de protocolo (ler, gravar, regularidade, ZIP) e saida do leitor generico"
```

---

### Task 8: Alertas de documentos no lugar dos de certidão

**Files:**
- Modify: `backend/app/paineis.py` (`alertas` chama `documentos.avisos(conn, hoje_d)`; apagar `_alertas_de_certidao` e `_entidades_com_contrato_ativo` se ficar sem uso)
- Test: `backend/tests/test_paineis.py` (os testes de `certidao_vencida_ou_ausente`/`certidao_vencendo` viram um teste do novo formato)

**Interfaces:**
- Consumes: `documentos.avisos`.
- Produces: em `GET /api/paineis/alertas` (rota atual), itens `{"tipo": "documentos_empresa"|"regularidade_mes", "nivel", "entidade_id", "contrato_id", "mensagem"}` no lugar dos dois tipos de certidão.

- [ ] **Step 1: Teste**

```python
# substituir os testes de alerta de certidao em backend/tests/test_paineis.py
def test_alertas_de_documentos_substituem_os_de_certidao(conn):
    # contrato ativo sem orgao -> exige os tipos padrao (federal, fgts, trabalhista), nenhum anexado
    conn.execute("INSERT INTO contratos (orgao, numero_instrumento, objeto, valor_original_centavos) VALUES ('S','X','o',100)")
    conn.commit()
    tipos = {a["tipo"] for a in paineis.alertas(conn, hoje="2026-09-23")}
    assert "documentos_empresa" in tipos
    assert not tipos & {"certidao_vencida_ou_ausente", "certidao_vencendo"}


def test_contrato_encerrado_e_nao_se_aplica_nao_geram_alerta(conn):
    # as duas garantias dos testes antigos de `_alertas_de_certidao` (test_paineis.py:202-250) continuam
    conn.execute("INSERT INTO contratos (orgao, numero_instrumento, objeto, valor_original_centavos, estado) "
                 "VALUES ('S','X','o',100,'encerrado')")
    conn.commit()
    assert [a for a in paineis.alertas(conn, hoje="2026-09-23") if a["tipo"] == "documentos_empresa"] == []
    conn.execute("UPDATE contratos SET estado='ativo'")
    conn.commit()
    for tid in (1, 2, 3):
        certidoes.marcar_nao_se_aplica(conn, 1, 1, tid, "teste")
    assert [a for a in paineis.alertas(conn, hoje="2026-09-23") if a["tipo"] == "documentos_empresa"] == []
```

(Conferir a coluna e os valores de `contratos.estado` no teste antigo que este substitui e copiar a forma dele.)

(Se o módulo usa a fixture `sem_certidoes_exigidas` como autouse, marcar este teste para não usá-la ou criar o contrato depois de restaurar `documentos.exigidos` com `monkeypatch.undo()`; conferir como o arquivo organiza as fixtures.)

- [ ] **Step 2: Implementar, rodar e commitar**

Em `alertas`: trocar `out.extend(_alertas_de_certidao(conn, hoje_d))` por `out.extend(documentos.avisos(conn, hoje_d))`; importar `documentos`; apagar `_alertas_de_certidao` e o que ficar sem uso.

Run: `cd backend && .venv\Scripts\python -m pytest tests/test_paineis.py tests/test_api_paineis.py -v`
Expected: PASS.

```bash
git add backend/app/paineis.py backend/tests/test_paineis.py
git commit -m "feat: alertas de documentos da empresa e regularidade do mes no lugar dos de certidao"
```

---

### Task 9: Carga das certidões por comando

**Files:**
- Modify: `backend/app/cli.py` (subcomando `documentos importar <pasta> --usuario <e-mail> [--ensaio]`)
- Test: `backend/tests/test_cli_documentos.py`

**Interfaces:**
- Consumes: `documentos.importar_pasta`.

- [ ] **Step 1: Teste**

```python
# backend/tests/test_cli_documentos.py
import datetime
import pathlib

from app import auth, cli, db, leitura_pdf, tempo
from tests.conftest import _pdf_com_texto

FIX = pathlib.Path(__file__).parent / "fixtures" / "certidoes"


def test_importar_ensaio_e_real(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("DASH_DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setattr(tempo, "hoje_local", lambda: datetime.date(2026, 9, 23))
    c = db.get_conn(); db.migrate(c)
    auth.criar_usuario(c, "U", "u@lotufo.com", "senha-forte-123", "admin"); c.close()
    pasta = tmp_path / "Certidoes" / "Lotufo"
    pasta.mkdir(parents=True)
    textos = {"cndt.pdf": "trabalhista-lotufo", "fgts.pdf": "fgts-lotufo", "vazio.pdf": None}
    for nome in textos:
        (pasta / nome).write_bytes(_pdf_com_texto(nome))
    por_pdf = {_pdf_com_texto(n): (FIX / f"{t}.txt").read_text(encoding="utf-8") if t else "" for n, t in textos.items()}
    monkeypatch.setattr(leitura_pdf, "texto_de_pdf_com_limite", lambda pdf: por_pdf[pdf])
    args = ["documentos", "importar", str(tmp_path / "Certidoes"), "--usuario", "u@lotufo.com"]
    assert cli.main(args + ["--ensaio"]) == 0
    saida = capsys.readouterr().out
    assert "ENSAIO" in saida and "gravadas: 1" in saida and "vencidas: 1" in saida and "sem_leitura: 1" in saida
    c = db.get_conn()
    assert c.execute("SELECT COUNT(*) FROM certidoes").fetchone()[0] == 0
    c.close()
    assert cli.main(args) == 0
    c = db.get_conn()
    assert c.execute("SELECT COUNT(*) FROM certidoes").fetchone()[0] == 1       # a CNDT (o FGTS de 09/08 venceu)
    c.close()
```

- [ ] **Step 2: Implementar**

Em `cli.py`, no padrão de `_legado`:

```python
def _documentos(args) -> int:
    """`documentos importar <pasta> [--ensaio]`: carga das certidoes vigentes de uma pasta local (bloco 4)."""
    conn = db.get_conn()
    try:
        db.migrate(conn)
        u = conn.execute("SELECT id FROM usuarios WHERE email=? AND ativo=1", (args.usuario,)).fetchone()
        if u is None:
            print(f"Usuário não encontrado ou inativo: {args.usuario}")
            return 1
        if not Path(args.pasta).is_dir():
            print(f"Pasta não encontrada: {args.pasta}")
            return 1
        rel = documentos.importar_pasta(conn, u["id"], Path(args.pasta), ensaio=args.ensaio)
    finally:
        conn.close()
    print("ENSAIO (nada foi gravado)" if rel["ensaio"] else "APLICADO")
    for chave in ("gravadas", "repetidas", "vencidas", "positivas", "sem_leitura"):
        print(f"  {chave}: {len(rel[chave])}")
        for item in rel[chave]:
            print(f"    - {item}")
    return 0
```

e no `main`: `doc = sub.add_parser("documentos", help="carga das certidões (bloco 4)")`, `dsub = doc.add_subparsers(dest="acao", required=True)`, `imp = dsub.add_parser("importar")`, `imp.add_argument("pasta")`, `imp.add_argument("--usuario", required=True)`, `imp.add_argument("--ensaio", action="store_true")`, e `if args.cmd == "documentos": return _documentos(args)`.

- [ ] **Step 3: Rodar**

Run: `cd backend && .venv\Scripts\python -m pytest tests/test_cli_documentos.py -v`
Expected: PASS.

- [ ] **Step 4: Ensaio sobre o backup real (cópia de banco no scratchpad)**

Com `DASH_DB_PATH` apontando para uma cópia da produção no scratchpad: `python -m app.cli cadastro aplicar --ensaio` e depois real (na cópia, para ter `nome_curto` e as consorciadas), e `python -m app.cli documentos importar "C:\Users\<usuario>\dev\lotufo-dashboard\backup-sharepoint-2026-08-04\certidoes-pdfs" --usuario <e-mail do Leonardo> --ensaio`. Esperado com hoje = 23/09/2026: as vigentes do backup (validade ≥ 23/09) gravadas, Montante em `sem_leitura` como `empresa-desconhecida`, as 2 CPD em `positivas`, os 14 sem texto em `sem_leitura`. Guardar o relatório para o runbook.

- [ ] **Step 5: Commit**

```bash
git add backend/app/cli.py backend/tests/test_cli_documentos.py
git commit -m "feat: comando documentos importar para a carga das certidoes vigentes"
```

---

### Task 10: Frontend — tela "Documentos de protocolo"

**Files:**
- Create: `frontend/src/Documentos.tsx`, `frontend/src/Documentos.test.tsx`
- Delete: `frontend/src/Certidoes.tsx`
- Modify: `frontend/src/rota.tsx` (tela `documentos`; `/certidoes` antigo cai em `documentos`) e `frontend/src/rota.test.ts` (linha 8 espera `{ tela: "certidoes" }`: passa a esperar `documentos`, mais um caso para `/documentos`), `frontend/src/App.tsx` (menu "Documentos", título "Documentos de protocolo"), `frontend/src/Alertas.tsx` (tipos `documentos_empresa` "Documentos da empresa" nível pelo campo `nivel`, `regularidade_mes` "Regularidade do mês"; clique abre Documentos; sai o campo `tipos?: number[]` dos alertas antigos, linhas 8-13), `frontend/src/ContratoPagina.tsx` (checklist mostra "empresa — tipo", competência da regularidade e link "Emitir"), `frontend/src/Medicoes.tsx` (checklist do protocolo com `?natureza=<tipo da medição>`; pendências com a empresa), `frontend/src/icones.tsx` se o ícone mudar de nome

**Interfaces:**
- Consumes: as rotas da Task 7 via `api` e `apiForm` de `api.ts`.
- `Documentos.tsx` exporta `default function Documentos({ usuario }: { usuario: Usuario })`.

- [ ] **Step 1: Teste (vitest, padrão de `Notas.test.tsx`)**

```tsx
// frontend/src/Documentos.test.tsx
import { render, screen, waitFor } from "@testing-library/react";
import { vi } from "vitest";
import Documentos from "./Documentos";

vi.mock("./api", () => ({
  api: vi.fn(async (caminho: string) => {
    if (caminho === "/api/documentos") return {
      hoje: "2026-09-23",
      empresas: [{
        entidade_id: 1, entidade: "Lotufo", cnpj: "00000000000100", papel: "lotufo", regularidade_exigida: true,
        regularidade: { situacao: "atrasada", competencia: "2026-06", esperada: "2026-07", regularidade: null },
        certidoes: [
          { tipo_id: 2, chave: "fgts", tipo: "CRF/FGTS", link_emissao: "https://consulta-crf.caixa.gov.br/x", exigida: true,
            situacao: "vencendo", dias: 4, certidao: { id: 7, emissao: "2026-08-29", validade: "2026-09-27", natureza: "negativa" } },
          { tipo_id: 5, chave: "municipal", tipo: "Certidão de Débitos Gerais (Prefeitura de Cuiabá)", link_emissao: "https://x",
            exigida: true, situacao: "vencida", dias: null, certidao: { id: 8, emissao: "2026-08-20", validade: "2026-09-20", natureza: "negativa" } },
          { tipo_id: 6, chave: "falencia", tipo: "Certidão de Falência e Recuperação Judicial (TJMT)", link_emissao: "https://x",
            exigida: false, situacao: "faltando", dias: null, certidao: null },
        ],
      }],
    };
    return {};
  }),
  apiForm: vi.fn(),
  ApiErro: class extends Error {},
}));

const usuario = { id: 1, nome: "U", email: "u@lotufo.com", perfil: "engenharia" } as any;

test("mostra a empresa, o que vence, o que venceu, a regularidade atrasada e o link de emissão", async () => {
  render(<Documentos usuario={usuario} />);
  await waitFor(() => expect(screen.getByText("Lotufo")).toBeInTheDocument());
  expect(screen.getByText(/vence em 4 dias/i)).toBeInTheDocument();
  expect(screen.getByText(/vencida em 20\/09/i)).toBeInTheDocument();
  expect(screen.getByText(/não exigida/i)).toBeInTheDocument();
  expect(screen.getByText(/07\/2026/)).toBeInTheDocument();
  expect(screen.getAllByRole("link", { name: /emitir/i })[0]).toHaveAttribute("href", "https://consulta-crf.caixa.gov.br/x");
  expect(screen.getByRole("button", { name: /baixar zip/i })).toBeInTheDocument();
});
```

- [ ] **Step 2: Implementar `Documentos.tsx`**

Mesma linguagem visual de `Espelho.tsx`/`Notas.tsx` (cartões, `tokens.css`, sem cor nova):

1. **Área de arrastar no topo**: "Arraste certidões ou o PDF de regularidade aqui" + `<input type="file" accept="application/pdf" multiple>`. Cada arquivo é lido (`apiForm("/api/documentos/certidoes/ler", fd)`) e vira um cartão de conferência na fila:
   - `ok: true`: "Lotufo · trabalhista · negativa · emitida em 24/06/2026 · válida até 21/12/2026 · nº 57104469/2026" (na falência, "validade calculada: 30 dias úteis") + botões **Gravar** (`apiForm("/api/documentos/certidoes", fd)` com o mesmo arquivo) e **Descartar**.
   - `ok: false, digitavel: true`: a mensagem + formulário (empresa [select das empresas do painel], tipo [seis], emissão, validade [opcional na falência], natureza [negativa / positiva com efeito de negativa], número opcional) + Gravar, que manda o arquivo com os campos.
   - `ok: false, digitavel: false`: a mensagem em tom de atenção, sem formulário; se o nome do arquivo parecer regularidade (`/^\d{6}\b/` ou contém "REGULARIDADE"), oferecer "É regularidade do mês?" que abre o formulário de regularidade com a competência pré-preenchida.
   - Um arquivo por vez na chamada; a fila mostra o resultado de cada um ("gravada", "repetida", erro).
2. **Um cartão por empresa** (`empresas` na ordem do servidor): título com o nome curto, CNPJ formatado e botão "Copiar CNPJ" (`navigator.clipboard.writeText`); tabela com os seis tipos: tipo, situação ("válida até dd/mm/aaaa", "vence em N dias" em atenção, "vencida em dd/mm" em ação, "falta" em ação quando exigida, "não exigida" em tom neutro quando não exigida e sem certidão), natureza ("positiva c/ efeito de negativa" quando for), link para o PDF vigente (`/api/certidoes/{id}/arquivo`) e link **Emitir** (`link_emissao`, `target="_blank" rel="noreferrer"`).
3. **Regularidade** no cartão da empresa quando `regularidade_exigida` ou quando existe alguma: "Competência 06/2026 · esperada 07/2026" com a situação e o botão **Anexar regularidade** (input de arquivo + campo `AAAA-MM` pré-preenchido pelo nome `MMAAAA - ...`) → `apiForm("/api/documentos/regularidades", fd)`.
4. **ZIP**: campo de data (padrão hoje) + botão **Baixar ZIP das vigentes** → `window.location.href = "/api/documentos/zip?entidade_id=..&data=.."` (GET com cookie de sessão; o navegador baixa pelo `Content-Disposition`).
5. Sem permissão de edição (`usuario.perfil === "diretoria"`): esconde a área de arrastar e os botões de anexar.

Depois de gravar qualquer coisa: recarregar `/api/documentos`.

- [ ] **Step 3: Demais telas**

- `rota.tsx`: `{ tela: "documentos" }` substitui `{ tela: "certidoes" }`; `ehSimples` aceita `certidoes` e o converte em `documentos` (link antigo não quebra).
- `App.tsx`: item de menu "Documentos"; renderiza `<Documentos usuario={usuario} />`.
- `Alertas.tsx`: `documentos_empresa: { rotulo: "Documentos da empresa", nivel: <do item> }`, `regularidade_mes: { rotulo: "Regularidade do mês", nivel: "acao" }`; o clique desses dois abre Documentos (onde hoje o de certidão abria Certidões).
- `ContratoPagina.tsx` e `Medicoes.tsx`: o tipo `Checklist` ganha `entidade`, `chave`, `link_emissao`, `competencia`, `esperada` nos itens; a lista de pendências mostra "Rivoli — FGTS" quando há mais de uma empresa; a regularidade aparece como "Regularidade mensal (07/2026 esperada)". Em `Medicoes.tsx` o checklist é buscado com `?natureza=${m.tipo}`.

- [ ] **Step 4: Rodar testes e build**

Run: `cd frontend && npm test -- --run && npm run build`
Expected: PASS; build sem erro de tipo.

- [ ] **Step 5: Verificação visual sobre cópia da produção**

Cópia de `C:\DashboardLotufo\dados\dashboard.db` no scratchpad; entrada temporária `backend-review` em `.claude/launch.json` (porta 8090, `DASH_DB_PATH` na cópia, `DASH_DEV=1`, `DASH_SEM_JOBS=1`); na cópia: `cadastro aplicar` e `documentos importar` sobre o backup de 04/08; abrir Documentos: cartões de Lotufo, consórcios e consorciadas; arrastar um PDF real do backup (ler → gravar), um sem texto (digitar), a CPD da Guaxe (recusa sem formulário); anexar uma regularidade; baixar o ZIP; abrir um contrato de consórcio (Integra BRT) e conferir o checklist com as consorciadas; conferir os alertas novos. Screenshot. Remover a entrada do `launch.json` ao terminar.

- [ ] **Step 6: Commit**

```bash
git add frontend/src
git commit -m "feat: tela Documentos de protocolo - arrastar e conferir certidoes, regularidade do mes, ZIP, checklist com consorciadas"
```

---

### Task 11: Documentação e backlog

**Files:**
- Modify: `docs/runbook.md` (seção "Documentos de protocolo (bloco 4)"), `docs/backlog.md`, `README.md` se listar telas

- [ ] **Step 1: Runbook**

(1) Operação: arrastar certidão, o que o sistema lê, positiva recusada, digitação quando não há texto; FGTS salvo pela página da Caixa pelo navegador ("Imprimir → Salvar como PDF"), não por driver de impressão; regularidade do mês a partir do dia 10 (competência do mês menos 2); ZIP "vigentes em". (2) Exigência: onde mora (`orgaos.yaml`, exceção no contrato, `consorciadas` em `entidades.yaml`) e como mudar (editar YAML, `cadastro validar`, `cadastro aplicar --ensaio`, aplicar). (3) Carga: baixar a biblioteca `Certidoes` do site GestaoContratosFaturamento para uma pasta local; backup do banco; `python -m app.cli documentos importar <pasta> --usuario <e-mail do Leonardo> --ensaio`; conferir o relatório; rodar sem `--ensaio`; a operação digita os de `sem_leitura` pela tela. (4) Receita de deploy do bloco 4: `deploy.ps1` com frontend (migração 024 aplica na subida) → `cadastro aplicar --ensaio` e real (nomes curtos, consorciadas, regularidade na SINFRA) → `documentos importar` (ato separado, com OK).

- [ ] **Step 2: Backlog** (uma linha cada, datadas)

- Rotas antigas de certidão (`GET /api/certidoes`, entidade, tipo, não se aplica, estado) e `certidoes.painel` ficam até o bloco 9.
- Comprovante do CNO da obra entra no pacote do bloco 5.
- SES e prefeituras: incluir `regularidade` na lista do órgão se algum protocolo delas levar o PDF do DP.
- Composição de Via Parecis e BR-163 não cadastrada (não protocolamos por eles).
- Integra BRT: nenhum protocolo com certidão na caixa do Leonardo; a caixa do consórcio negou acesso (403). Composição Lotufo, Guaxe, Encomind vem dos emissores do espelho. Indício de que o protocolo dele leva FALÊNCIA: o faturamento circulou internamente em 16/09 a "CERTIDÃO FALÊNCIA INTEGA BRT" (validade de 30 dias). Confirmar com acesso de leitura à caixa do consórcio e, se confirmado, pôr `documentos_medicao` com `falencia` no YAML do Integra BRT (exceção por contrato). Folha própria do consórcio também não confirmada.
- Deciolândia, BR-163, Granito e Coxipó 3ª etapa: nenhum protocolo com certidão encontrado na caixa do Leonardo (busca ampla em 2026-09-23).
- Cavalaria 6ª (11/09/2026) levou a certidão de falência no ZIP e as demais obras SINFRA de 14/09 não: tratado como incidente (decisão 6).
- Apostilamento do reajuste anual da Prefeitura de Cuiabá pede falência, contrato social, documento do representante e balanço (Região Oeste, 25/06/2026): levar para o pleito de reajuste do bloco 7.
- Guaxe e Encomind com estadual positiva pura (CPD) em 22/08/2026: o protocolo do Integra BRT vai acusar a falta até regularizarem.

- [ ] **Step 3: Commit**

```bash
git add docs/runbook.md docs/backlog.md README.md
git commit -m "docs: runbook e backlog do bloco 4 (documentos de protocolo, carga das certidoes)"
```

---

### Task 12: Suíte, gate Sol, pedido de merge e produção

- [ ] **Step 1: Suíte inteira**: `cd backend && .venv\Scripts\python -m pytest` e `cd frontend && npm test -- --run && npm run build`. Expected: tudo verde.
- [ ] **Step 2: Gate Sol** sobre o diff inteiro da branch (`git diff master...bloco4-documentos | codex exec -m gpt-5.6-sol`), um round de correção, registro em `docs/backlog.md` (ou a dispensa, se o Leonardo decidir como no bloco 3).
- [ ] **Step 3: Pedir OK ao Leonardo** para o merge `--no-ff` em `master`.
- [ ] **Step 4: Produção** pela receita do runbook, com OK separado: deploy com frontend → `cadastro aplicar --ensaio` → real → health. **Carga das certidões** (`documentos importar`) só com a pasta do dia e OK próprio, com backup antes; conferir o relatório e acompanhar a primeira certidão arrastada por uma das operadoras.

## Self-review (feito ao escrever, 2026-09-23)

- **Cobertura da spec:** §3 passo 0 (arrastar certidão, regularidade mensal) → Tasks 5, 7, 10; §9 duas gavetas, seis leitores portados e provados, falência em dias úteis com feriados, natureza e recusa da positiva, digitação sem OCR, maior validade, histórico, exigência do órgão com exceção por contrato, consórcio com consorciadas, reajuste SINFRA só estadual, prévia com link de emissão (checklist), ZIP com data de referência → Tasks 1 a 7 e 10; §10.4 → Task 10; §11 "Documentos da empresa" e "Regularidade do mês" → Tasks 5 e 8; §12 `certidoes` seis tipos e natureza, `regularidade_mensal` (aqui `regularidades`) → Task 1; §14.3 carga → Tasks 5 e 9; §15 testes contra textos reais → Task 4. Fora: prévia do protocolo e pacote (bloco 5), tela inicial (bloco 6), comprovante do CNO (bloco 5, decisão 8).
- **Placeholders:** nenhum valor esperado em aberto; os gabaritos da Task 4 saíram do protótipo rodado sobre os PDFs reais. Um ponto pede conferência na execução e está marcado: o padrão de ensaio aninhado em `db.mutacao` (Task 5).
- **Consistência de nomes:** `documentos.exigidos/situacao/situacao_regularidade/competencia_esperada/regularidade_vigente/registrar_regularidade/ler/dados_manuais/gravar_certidao/painel/avisos/zip_vigentes/importar_pasta/tipo_por_chave` usados igual nas Tasks 5 a 10; `leitura_certidao.ler/Recusa/DIGITAVEIS/NATUREZAS/TIPOS/plano` iguais nas Tasks 4, 5 e 7; `feriados.somar_dias_uteis` nas Tasks 3, 4 e 5; colunas da 024 com os mesmos nomes em todas as tasks.
- **Riscos que ficam:** (a) `_exigidos_ativos` roda `exigidos` duas vezes por contrato ativo a cada painel e a cada leitura de alertas (22 contratos: barato); (b) a regra "competência esperada" foi medida em três protocolos: pode errar em mês de fechamento atrasado do DP, e o aviso é só aviso; (c) contrato em encerramento (`estado='ativo'` com `encerramento_iniciado_em`) continua exigindo documentos, o que é o certo enquanto ainda há medição final a protocolar.

## Revisão adversarial (Fable, 2026-09-23) e arbitragem

O revisor rodou o leitor e os feriados do plano sobre os 12 PDFs reais (todos os gabaritos batem) e conferiu contra o código as assinaturas usadas (`arquivos.*`, `db.mutacao` reentrante com SAVEPOINT, `_sem_alters_ja_aplicados` com `ADD COLUMN ... CHECK`, `certidoes.*`, `contratos.entidade_de`, `entidades.*`, `conftest._pdf_com_texto` determinístico), as contas dos testes (limiares, competência, ordens, mensagens, ZIP, CLI) e o banco de produção (tipos 1 a 3 com os nomes que os `UPDATE` da 024 exigem, 0 certidões, 9 entidades). Treze achados, todos aceitos:

1. DML cru sem `commit()` nos helpers de `test_documentos.py` faria `db.mutacao` recusar a transação aberta: commits acrescentados.
2. Neutralizar `exigidos` na fixture `sem_certidoes_exigidas` mataria a prova da trava em `test_api_medicoes`: a fixture não muda.
3. `test_notas.py` aplica o cadastro real e protocola: neutraliza `exigidos` no próprio fixture.
4. `test_certidoes.py` conta entidades × 3 tipos: contagens ajustadas na Task 1.
5. `_upload` de `test_api_certidoes.py` semeia 39 testes: reescrito para semear direto, sem a rota que sai.
6. PDF recusado ficava órfão em disco: a gravação lê em memória e só grava o arquivo depois de decidir.
7. Digitação aceitava empresa que não está no PDF: confere contra `cnpjs_no_texto`.
8. Deciolândia (ativa, Via Parecis) passaria a cobrar certidões que ninguém anexa: exceção vazia no YAML (decisão 6).
9. "Vale a de maior validade" não era literal em `certidoes.vigente`: ordem trocada, com teste (decisão 15).
10. `rota.test.ts` e o campo `tipos` de `Alertas.tsx`: na Task 10.
11. Cobertura de "contrato encerrado" e "não se aplica" nos alertas: mantida na Task 8.
12. `importar_pasta` sem teto de tamanho: mesmo teto do upload.
13. Frase "Anexe em Certidões" na trava: vira "Documentos", sem renomear a chave `certidoes_pendentes`.
