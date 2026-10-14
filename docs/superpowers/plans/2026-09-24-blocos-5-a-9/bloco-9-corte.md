# Bloco 9 (Corte): remoção da detecção, dados arquivados, telas antigas fora, limpeza externa do sistema novo. Plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. **Leia antes `00-indice.md`.** Branch `bloco9-corte`, criada de `bloco8-diretoria`.

**Goal:** o código que observava Outlook e SharePoint e a fila de sugestões saem do sistema, com os dados arquivados no próprio banco. Saem também as telas e rotas que o cadastro versionado e os blocos 5 a 8 substituíram. A tela de administração passa a listar as contas Microsoft conectadas. **A dashboard antiga e os fluxos do Power Automate dela continuam ligados** (decisão do Leonardo em 2026-09-24): o corte é só no sistema novo, e o roteiro externo se reduz às permissões de leitura do app do Entra ID e aos argumentos de leitura da tarefa agendada.

**Architecture:**
- Remoção por dependência:
  1. primeiro quem usa, depois quem é usado;
  2. os testes dos módulos removidos saem junto;
  3. os que só tocavam de passagem são ajustados.
- A migração 027 renomeia as sete tabelas da detecção para `arquivo_*`: o dado continua no banco e nos backups, e nenhum código lê mais.
- `graph.py` fica só com o que o envio de e-mail usa.

**Tech Stack:** o do índice.

**Spec:** §0.2 ("nada adivinha"), §1 (administrador), §5.1 (permissões que deixam de ser pedidas), §10.6, §12 (tabelas que saem, com os dados arquivados), §13. §14.4 e §14.5 foram substituídos pela decisão de 2026-09-24 (Power Automate e dashboard antiga continuam ligados).

**Status:** APROVADO pelo Leonardo em 2026-09-24 (ver `00-indice.md`).

## Decisões deste bloco (para aprovação)

1. **Arquivar é renomear.** `sugestoes`, `deteccao_padroes`, `deteccao_config`, `mensagens_observadas`, `planilhas_config`, `planilhas_observadas` e `graph_sincronizacoes` viram `arquivo_<nome>`. Sem `DROP`: histórico não se apaga. O SQLite atualiza sozinho as referências de chave estrangeira das outras tabelas no `RENAME` (versão ≥ 3.26 com `legacy_alter_table` desligado, o padrão). A tarefa confere com `PRAGMA foreign_key_check`.
2. **Sai do código:**

   | Grupo | Itens |
   |---|---|
   | Módulos | `deteccao.py`, `sincronizacao_graph.py`, `sugestoes.py`, `api_sugestoes.py`, `api_graph.py`, `importar_faturamento.py` (carga única feita em 10/09/2026) e seu subcomando no CLI, `leitura_termo.py` (só a rota `ler-pdf` de aditivo o usava) |
   | Em `graph.py` | `ClienteGraph`, `SimuladorGraph`, `configuracao`, `de_ambiente`, `logado` e o `ESCOPOS` de leitura. Fica o que `correio` usa: `ErroGraph`, `GRAPH`, `LOGIN`, `TIMEOUT`, `_SEM_REDIRECT`, `Token`, `iniciar_device_code`, `concluir_device_code`, `gravar_token` |
   | Em `paineis.py` | `engenharia`, `consolidado`, `saldo`, `caixa` e as rotas `consolidado`, `consolidado.csv`, `medicoes.csv` e `engenharia`. `curva` fica, porque a aba Contrato usa |
   | Rotas antigas de certidão | `GET /api/certidoes`, criar entidade, criar tipo, "não se aplica", mudar estado. A rota do checklist vai para `api_documentos.py`, com o mesmo caminho |
   | Rotas de escrita de contrato e aditivo | criar, atualizar, mudar estado, criar e assinar aditivo, cancelar, `ler-pdf`. Somem com a trava `permissoes.exigir_cadastro_editavel` e a variável `DASH_CADASTRO_VERSIONADO`: o cadastro é sempre versionado |
   | Telas | `Sugestoes.tsx`, `PainelEngenharia.tsx`, `Microsoft365.tsx`, `PainelGeral.tsx`; os formulários de `Contratos.tsx` e `Aditivos.tsx` (ficam só listas de leitura) |
   | Tarefa agendada | `sincronizacao_graph.agendar` em `main.py` |

3. **Dúvida de casamento do RM.** `sincronizacao_rm` deixa de criar a sugestão `nf_ambigua`. Registra em log (`log.info`) e deixa a nota sem alocação. A spec §7.1 põe essa dúvida no botão "vincular nota" da medição, que já existe (`notas.candidatas_rm` e `vincular_rm`), e o aviso "nota ausente do RM" cobre a medição sem nota.
4. **Parâmetros da tarefa de produção.**
   - `rodar_producao.ps1` continua **aceitando** `-GraphSite` e `-GraphCaixa` e passa a ignorá-los. A tarefa agendada é chamada com eles; parâmetro que some quebraria a subida.
   - Saem só as variáveis de ambiente de leitura: `DASH_GRAPH_SITE`, `DASH_GRAPH_CAIXA` e `DASH_GRAPH_TOKEN_ARQUIVO`.
   - `DASH_GRAPH_CLIENT_ID`, `DASH_GRAPH_TENANT` e `DASH_GRAPH_TOKENS_DIR` ficam, porque o envio usa.
   - Limpar os argumentos da tarefa agendada é ato do Leonardo, no roteiro.
5. **Admin: contas Microsoft conectadas.** Tabela com usuário, e-mail, perfil e "conectada" (`correio.conectado(usuario_id)`), mais a data do arquivo do token. É só leitura: cada pessoa conecta a própria conta em Minha conta, como hoje.
6. **Power Automate e dashboard antiga ficam ligados** (decisão do Leonardo em 2026-09-24, que substitui os itens 4 e 5 da spec §14). Nada neste bloco toca a dashboard antiga, os fluxos, o robô `robo-nf` nem o cartão FRC. O roteiro externo (tarefa 9.5) fica com dois itens do sistema novo.

## Estrutura de arquivos

| Arquivo | Ação |
|---|---|
| `backend/migrations/027_corte.sql` | renomeia as sete tabelas |
| `backend/app/deteccao.py`, `sincronizacao_graph.py`, `sugestoes.py`, `api_sugestoes.py`, `api_graph.py`, `importar_faturamento.py`, `leitura_termo.py` | apagar |
| `backend/app/graph.py`, `main.py`, `medicoes.py`, `sincronizacao_rm.py`, `carga_legado.py`, `paineis.py`, `api_paineis.py`, `api_certidoes.py`, `api_documentos.py`, `api_contratos.py`, `api_aditivos.py`, `permissoes.py`, `cli.py`, `api_admin.py` | ajustar |
| `backend/tests/test_deteccao.py`, `test_graph.py`, `test_sugestoes.py`, `test_api_sugestoes.py`, testes de `importar_faturamento` e de `leitura_termo` | apagar; ajustar `test_rm.py`, `test_transacao.py`, `test_paineis.py`, `test_api_paineis.py`, `test_medicoes.py`, `test_api_certidoes.py`, `test_contratos.py`, `test_aditivos.py`, `test_permissoes.py` |
| `frontend/src/Sugestoes.tsx`, `PainelEngenharia.tsx` (+ teste), `Microsoft365.tsx`, `PainelGeral.tsx` | apagar |
| `frontend/src/App.tsx`, `rota.tsx`, `Admin.tsx`, `Contratos.tsx`, `Aditivos.tsx` | ajustar |
| `scripts/rodar_producao.ps1` | ignorar os parâmetros de leitura |
| `docs/runbook.md`, `README.md`, `PRODUCT.md`, `CLAUDE.md`, `docs/backlog.md` | atualizar; limpeza externa do sistema novo |

---

### Task 9.1: Migração 027 (arquivar as tabelas da detecção)

**Files:**
- Create: `backend/migrations/027_corte.sql`
- Test: `backend/tests/test_migracao_027.py`

- [ ] **Step 1: Teste**

```python
"""Migracao 027: tabelas da deteccao arquivadas (renomeadas), nada apagado."""
from app import db

TABELAS = ("sugestoes", "deteccao_padroes", "deteccao_config", "mensagens_observadas", "planilhas_config",
           "planilhas_observadas", "graph_sincronizacoes")


def test_027_renomeia_e_preserva(tmp_path, monkeypatch):
    monkeypatch.setenv("DASH_DB_PATH", str(tmp_path / "t.db"))
    c = db.get_conn()
    db.migrate(c)
    nomes = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert not set(TABELAS) & nomes
    assert {f"arquivo_{t}" for t in TABELAS} <= nomes
    assert c.execute("PRAGMA foreign_key_check").fetchall() == []
    db.migrate(c)                                          # reexecucao
    c.close()
```

Um segundo teste migra só até a 026 (usar o mecanismo de `test_migracao_024.py` para parar numa migração, se houver). Insere uma sugestão e uma mensagem observada, aplica a 027 e confere que as linhas estão em `arquivo_sugestoes` e `arquivo_mensagens_observadas`.

- [ ] **Step 2:** FAIL. **Step 3: Migração.** O runner executa o arquivo uma vez só (tabela `schema_migrations`); para a reexecução manual não falhar, cada renomeação vem numa forma que o runner aceite. Se o runner não pular `ALTER TABLE ... RENAME` de tabela que já não existe, verificar em `db.migrate` como a 020 e a 022 fizeram a troca de nome (`... RENAME TO ...`) e seguir o mesmo padrão.

```sql
-- 027: corte (bloco 9; spec 2026-09-21 §12 e §13). A deteccao sai do codigo; os dados ficam arquivados
-- no proprio banco (e nos backups) com o prefixo arquivo_. Nada e' apagado.
ALTER TABLE sugestoes RENAME TO arquivo_sugestoes;
ALTER TABLE deteccao_padroes RENAME TO arquivo_deteccao_padroes;
ALTER TABLE deteccao_config RENAME TO arquivo_deteccao_config;
ALTER TABLE mensagens_observadas RENAME TO arquivo_mensagens_observadas;
ALTER TABLE planilhas_config RENAME TO arquivo_planilhas_config;
ALTER TABLE planilhas_observadas RENAME TO arquivo_planilhas_observadas;
ALTER TABLE graph_sincronizacoes RENAME TO arquivo_graph_sincronizacoes;
```

- [ ] **Step 4:** PASS. **Step 5:** não commitar sozinha: a migração quebra o código que ainda lê as tabelas. Vai no mesmo commit da 9.2.

---

### Task 9.2: Remover a detecção e as rotas antigas do backend

**Files:** os da tabela acima (backend).

- [ ] **Step 1: Mapa de dependências.** Para cada módulo a apagar, `grep -rn "import <modulo>\|from app import.*<modulo>\|<modulo>\." backend/app backend/tests`, e anotar cada ponto de uso. Pontos conhecidos:
  - `main.py:96,100,111,119,128-131`: routers e o agendamento;
  - `medicoes.py:73,77`: `mensagens_da_medicao` em `detalhe()`. Tirar a chave `mensagens` do detalhe e ajustar quem lê (frontend `Medicoes.tsx`);
  - `sincronizacao_rm.py:49,220,386,508,521`: sugestão `nf_ambigua`. Trocar pelo log da decisão 3;
  - `carga_legado.py:186`: `deteccao.chave_do_cadastro`. Copiar a função para dentro de `carga_legado.py` (ela é pequena e só a carga usa);
  - `carga_legado.py:251-266`: escreve em `deteccao_padroes` e `planilhas_config`. Tirar esse trecho: a carga do legado já rodou e essas tabelas passam a ser arquivo;
  - `paineis.py:207`: SQL em `sugestoes`, dentro de `engenharia`, que sai inteira;
  - `api_espelhos.py:8` e `api_correio.py:8`: importam `graph`. Conferir que só usam o que fica.
- [ ] **Step 2: Remover e ajustar**, na ordem:
  1. rotas e jobs em `main.py`;
  2. `api_sugestoes`, `api_graph`;
  3. `sincronizacao_graph`, `sugestoes`, `deteccao`;
  4. `importar_faturamento` e o subcomando do CLI;
  5. `leitura_termo` e a rota `ler-pdf`;
  6. a parte de leitura de `graph.py`;
  7. `paineis` e `api_paineis`;
  8. as rotas antigas de `api_certidoes`, com o checklist movido para `api_documentos`;
  9. a escrita de `api_contratos` e `api_aditivos`, com `exigir_cadastro_editavel`.

  Se `cadastro_aplicar` usar funções de `aditivos.py`, elas ficam; só saem as rotas.
- [ ] **Step 3: Testes.** Apagar os testes dos módulos removidos. Ajustar os demais:
  - em `test_rm.py` e `test_transacao.py`, o caso de nota ambígua afirma "nota sem alocação e nenhuma sugestão";
  - em `test_paineis.py`, saem os testes do painel geral e da engenharia;
  - em `test_api_certidoes.py`, só o checklist, com o caminho novo;
  - em `test_contratos.py`, `test_aditivos.py` e `test_permissoes.py`, tirar o que testava escrita pela API.

  Um teste novo por comportamento que mudou:
  - `test_rotas_da_deteccao_sairam`: `GET /api/sugestoes`, `/api/graph/status` e `/api/paineis/engenharia` → 404;
  - `test_nota_ambigua_nao_vira_sugestao`, em `test_rm.py`.
- [ ] **Step 4:** suíte inteira do backend → PASS. `python -m app.cli --help` sem os subcomandos removidos.
- [ ] **Step 5: `rodar_producao.ps1`.**
  - `-GraphSite` e `-GraphCaixa` continuam declarados, com o comentário "ignorado desde o bloco 9 (leitura do Graph saiu); mantido para a tarefa agendada não quebrar";
  - saem as linhas que exportam `DASH_GRAPH_SITE`, `DASH_GRAPH_CAIXA` e `DASH_GRAPH_TOKEN_ARQUIVO`.
- [ ] **Step 6: Commit** (junto com a 027) `feat: corte - deteccao, sugestoes e leitura do Graph fora; tabelas arquivadas`.

---

### Task 9.3: Frontend (telas antigas fora, contas conectadas na administração)

**Files:**
- Delete: `frontend/src/Sugestoes.tsx`, `frontend/src/PainelEngenharia.tsx`, `frontend/src/PainelEngenharia.test.tsx`, `frontend/src/Microsoft365.tsx`, `frontend/src/PainelGeral.tsx`
- Modify: `frontend/src/App.tsx`, `frontend/src/rota.tsx`, `frontend/src/rota.test.ts`, `frontend/src/Admin.tsx`, `frontend/src/Contratos.tsx`, `frontend/src/Aditivos.tsx`, `frontend/src/Medicoes.tsx` (sem `mensagens`)
- Backend: `backend/app/api_admin.py` (`GET /api/admin/contas-microsoft`), teste em `backend/tests/test_api_admin.py`

- [ ] **Step 1: Rotas.** Saem `sugestoes` e `engenharia` do tipo `Rota` e de `SIMPLES`. `parseRota` manda `/sugestoes` e `/engenharia` para `raiz` (que vai à tela inicial) e `/painel` para `diretoria` (link antigo). `rota.test.ts` cobre os três.
- [ ] **Step 2: Admin.** `GET /api/admin/contas-microsoft` (`administrar`) devolve `[{usuario_id, nome, email, perfil, conectada, token_em}]`; `token_em` é o `mtime` do arquivo `correio.arquivo_token(id)` em ISO, ou `null`. `Admin.tsx` troca o `<Microsoft365>` por uma tabela "Contas Microsoft conectadas", com o selo "conectada" ou "não conectada" e a nota "cada pessoa conecta a própria conta em Minha conta". Teste da rota no backend.
- [ ] **Step 3: Leitura só.** `Contratos.tsx` vira uma lista de obras (nome, órgão, status, link) sem os botões "novo" e "editar"; `Aditivos.tsx` vira uma tabela de instrumentos sem formulários. Nos dois, a nota "O cadastro é editado pelo Leonardo em arquivo (cadastro/)".
- [ ] **Step 4:** `npm test -- --run` e `npm run build` → PASS; `grep -rn "Sugestoes\|PainelEngenharia\|Microsoft365\|PainelGeral" frontend/src` vazio.
- [ ] **Step 5: Verificação visual** no `backend-review` sobre cópia da produção migrada até a 027:
  - menu sem os itens antigos;
  - `/sugestoes` e `/engenharia` caem no Início;
  - a administração lista as contas conectadas;
  - a página de obra abre sem erro no console;
  - o detalhe da medição abre sem `mensagens`.
- [ ] **Step 6: Commit** `feat: corte no frontend - telas antigas fora e contas Microsoft na administracao`.

---

### Task 9.4: Documentação do sistema

- [ ] **Step 1:** `README.md`, `PRODUCT.md` e `CLAUDE.md` do projeto: tirar tudo que descreve detecção, sugestões, leitura de caixa e de planilha, Painel da Engenharia e cadastro por tela. O `CLAUDE.md` ganha uma linha: "Blocos 1 a 9 da reestruturação entregues; o sistema não lê caixa de e-mail nem SharePoint; a única fonte automática é o RM".
- [ ] **Step 2:** `docs/runbook.md`:
  - sai a seção "Microsoft 365 (fase 6, leitura)";
  - a seção "Envio de e-mail" passa a dizer que só o envio usa o Graph;
  - nova seção "Tabelas arquivadas", com os nomes `arquivo_*`, "não ler nem apagar" e como consultar se preciso.
- [ ] **Step 3: Commit** `docs: sistema sem deteccao (README, PRODUCT, CLAUDE.md, runbook)`.

---

### Task 9.5: Limpeza externa do sistema novo (runbook)

A dashboard antiga e os fluxos do Power Automate dela **continuam ligados** (decisão do Leonardo em 2026-09-24). Ficam só dois itens externos, ambos do sistema novo. Cada um é feito pelo Leonardo ou por mim com o OK dele **para aquele item**.

| # | Item | Prova antes |
|---|---|---|
| 1 | Permissões de leitura no app do Entra ID (`Mail.Read`, `Mail.Read.Shared`, `Sites.Read.All`, `Files.Read.All`) | bloco 9 em produção; `grep` no código sem uso. **Atenção:** conferir antes se algum fluxo ou robô da dashboard antiga usa o MESMO app (o client ID da tarefa agendada, `-GraphClientId`); se usar, o item não é feito |
| 2 | Argumentos `-GraphSite` e `-GraphCaixa` da tarefa agendada e o arquivo `C:\DashboardLotufo\segredos\graph.txt` (token da leitura) | bloco 9 em produção; depois de retirar os argumentos, `deploy.ps1` com health 200 |

- [ ] **Step 1:** escrever no `docs/runbook.md` a seção "Corte do sistema novo" com a tabela, mais uma linha: "A dashboard antiga e seus fluxos do Power Automate continuam ligados (decisão de 2026-09-24); nada do sistema novo depende deles." **Step 2: Commit** `docs: limpeza externa do sistema novo no runbook`.

---

### Task 9.6: Fechamento dos cinco blocos e pedido de merge e deploy

- [ ] **Step 1:** suíte inteira do backend; depois `npm test -- --run` e `npm run build`. Anotar os números.
- [ ] **Step 2: Ensaio da sequência de produção** sobre uma cópia do banco de produção, no scratchpad:
  - migrações 025 a 027 em ordem;
  - `cadastro aplicar --ensaio` com o cadastro da branch final;
  - `foreign_key_check` vazio;
  - contagem de medições, certidões, notas e protocolos igual à do original.
- [ ] **Step 3: Backlog e memória.** Backlog com uma seção por bloco:
  - o que foi feito;
  - desvios do plano;
  - pendências (P2);
  - gates.

  Memória `reestruturacao-bloco-1-retomada.md` e o gancho do `MEMORY.md` atualizados ("blocos 5 a 9 prontos nas branches; aguardando OK de merge e deploy").
- [ ] **Step 4: Pedido ao Leonardo (P3 do índice)**, com o resumo de cada bloco, os números das suítes, o resultado dos gates e o ensaio do passo 2. Com o OK, para cada bloco de 5 a 9, **em ordem**:
  1. backup `dashboard-PRE-BLOCO<n>-<ts>.db` (backup do SQLite, integridade conferida);
  2. merge `--no-ff` da branch em `master` e push;
  3. `scripts\deploy.ps1 -Ref origin/master` (com frontend);
  4. `cadastro aplicar --ensaio` e real;
  5. health 200 e a verificação rápida da tela nova do bloco.

  O `deploy.ps1` faz rollback se a saúde falhar; se isso acontecer, os blocos seguintes esperam.
- [ ] **Step 5:** depois do deploy, os dois itens da 9.5, com OK por item.

## Self-review

- Spec §13, itens que saem: deteccao, sincronizacao_graph, a leitura de graph, sugestoes com rotas e telas (Sugestões, Painel da Engenharia, Microsoft 365), formulários de contrato, aditivo, entidade e tipo de certidão, painel geral. Todos cobertos em 9.2 e 9.3. O alerta de reajuste sem par saiu no bloco 6.
- Spec §13, itens que ficam: autenticação, permissões, auditoria, dinheiro, cronograma, leitura de PDF, RM, backup, watchdog e deploy pinado. Nenhum tocado, salvo `permissoes.exigir_cadastro_editavel`.
- Spec §12: tabelas que saem, com dados arquivados → 9.1.
- Spec §5.1: permissões de leitura deixam de ser pedidas → 9.2 (código) e 9.5 item 7 (Entra ID).
- Spec §10.6: contas conectadas → 9.3.
- Spec §14.4 e §14.5: substituídos pela decisão de 2026-09-24 (Power Automate e dashboard antiga continuam ligados); o bloco 9 só limpa o sistema novo (9.5).
