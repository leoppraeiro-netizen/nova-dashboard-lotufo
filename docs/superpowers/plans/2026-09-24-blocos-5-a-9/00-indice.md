# Blocos 5 a 9 (protocolo, tela inicial e avisos, reajuste e prazos, diretoria e QDOP, corte): plano de execução contínua

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Leia este índice inteiro antes de abrir o arquivo de um bloco.

**Goal:** terminar a reestruturação: a operação monta, assina e envia o protocolo de medição pelo sistema (bloco 5); abre o dia numa tela inicial com avisos confiáveis e navega pelas medições e pela página da obra (bloco 6); manda pleito de reajuste, carta de prazo e comunicação de conclusão, com instrumentos, paralisação e encerramento acompanhados (bloco 7); a diretoria vê onde está o dinheiro, na cota da Lotufo, e exporta o QDOP no leiaute oficial (bloco 8); e o código de detecção sai do sistema novo (bloco 9). A dashboard antiga e os fluxos do Power Automate dela continuam ligados (decisão do Leonardo em 2026-09-24).

**Architecture:** cinco branches encadeadas, uma por bloco, executadas em sequência sem parar entre blocos (salvo as paradas listadas abaixo). O que é comum aos blocos 5 e 7 (carta em PDF, número do ofício, conferência do PDF assinado, texto por página) nasce no bloco 5 como módulo próprio e é reusado no 7. Os avisos do catálogo da spec §11 passam a morar num registro único (`app/avisos.py`, bloco 6), que os blocos 7 e 8 alimentam. Três migrações: 025 (bloco 5), 026 (bloco 7), 027 (bloco 9).

**Tech Stack:** Python 3.12, FastAPI, SQLite, pytest, pypdf 6.16.2 (juntar e ler PDF), **fpdf2 2.8.8** (novo: gerar carta, capa e divisória em PDF), openpyxl 3.1.5 (QDOP), Tesseract local (bloco 4, já em produção), React 18 + Vite + vitest.

**Spec:** `docs/superpowers/specs/2026-09-21-reestruturacao-design.md` (§2 a §17; emenda do OCR de 2026-09-24). Decisões: `docs/decisoes-reestruturacao-2026-09-16.md`. Levantamentos usados: `docs/mapeamento-emails-medicao*`, `docs/nomes-arquivo-por-obra*`, `docs/reajuste-pleitos-2026-09-17.md`, `docs/prazos-vigencia-execucao-2026-09-17.md`, `docs/inventario-fica-ou-sai*`; protocolos reais baixados em 2026-09-23 (scratchpad da sessão `9f83d3e0`, pasta `protocolos/`); PDFs assinados no DocuSign em `C:\Users\<usuario>\dev\aditivos-lotufo\`; QDOP oficial em `C:\Users\<usuario>\Downloads\LICITAÇÕES 11.08.2026\GL.SGI.FRP.DE.250 - QDOP - QUADRO DEMONSTRATIVO DE OBRAS E PROJETOS (3).xlsx` (22/09/2026).

**Status:** APROVADO pelo Leonardo em 2026-09-24, com a mudança da D9.3 (Power Automate e dashboard antiga continuam ligados).

## Arquivos do plano

| Arquivo | Bloco | Branch | Migração |
|---|---|---|---|
| `bloco-5-protocolo.md` | 5. Protocolo: carta, pacote, assinatura com conferência, envio | `bloco5-protocolo` (de `master`) | 025 |
| `bloco-6-inicio-avisos.md` | 6. Tela inicial, avisos, lista de medições, página da obra | `bloco6-inicio` (de `bloco5-protocolo`) | — |
| `bloco-7-reajuste-prazos.md` | 7. Pleito de reajuste, carta de prazo, conclusão, instrumentos, paralisação, encerramento | `bloco7-reajuste-prazos` (de `bloco6-inicio`) | 026 |
| `bloco-8-diretoria-qdop.md` | 8. Tela da diretoria e exportação do QDOP | `bloco8-diretoria` (de `bloco7-reajuste-prazos`) | — |
| `bloco-9-corte.md` | 9. Remoção da detecção, dados arquivados, limpeza da leitura do Graph | `bloco9-corte` (de `bloco8-diretoria`) | 027 |

## Global Constraints (valem para todas as tarefas dos cinco arquivos)

- **Banco.** `backend/dados/dashboard.db` é o caminho padrão de dev e de produção nesta máquina. Testes usam `tmp_path` com `DASH_DB_PATH`. **Nunca semear nem apagar o banco padrão nem o de produção** (`C:\DashboardLotufo\dados\dashboard.db`). Leitura da produção só com `?mode=ro`; ensaio sobre cópia feita por `sqlite3.backup` no scratchpad. Servidor de revisão visual: entrada `backend-review` em `.claude/launch.json`, porta 8090, `DASH_DEV=1`, `DASH_SEM_JOBS=1`, `DASH_DB_PATH` no scratchpad; remover a entrada ao terminar.
- **Sem custo de API** (spec §15): nada pago por uso. OCR só o local (Tesseract, bloco 4). Nenhuma chamada a LLM.
- **Dinheiro.** Centavos inteiros (`int`), arredondamento único, valor protocolado congelado no protocolo, correção é evento novo, nada de exclusão física de registro financeiro. Diretoria sempre na **cota** (`contratos.cota(centavos, percentual_bp)`); medições guardam o valor cheio.
- **Escrita.** Toda escrita dentro de `with db.mutacao(conn):` com `auditoria.registrar(conn, usuario_id, acao, entidade, entidade_id, antes, depois)` no mesmo commit. `db.mutacao` é reentrante (SAVEPOINT).
- **E-mail.** Só `correio.enviar_e_registrar(conn, usuario, tipo, para, copia, assunto, corpo_html, anexos) -> envio_id`: envia e SÓ ENTÃO registra; **falha de envio não muda estado nenhum** (spec §5.1). Todo o resto (mudar estado da medição, ligar envio ao protocolo) acontece DEPOIS do envio aceito, numa transação. Tudo o que pode recusar é conferido ANTES de enviar. Testes de envio usam `DASH_GRAPH_SIMULADOR=<tmp>/sim` e `DASH_GRAPH_TOKENS_DIR=<tmp>/tok`.
- **Arquivos.** Recebidos pelo validador do projeto (`arquivos.blocos_validados`, estendido no bloco 5 para teto por rota e para planilha `.xlsx`), gravados por hash (`arquivos.gravar_bytes(pasta, dados, ext) -> (rel, sha)`), lidos só por `arquivos.caminho_seguro(rel)`. Leitura de PDF só em subprocesso (`leitura_pdf.com_limite`). Arquivo do cadastro (timbre, comprovante do CNO, modelo do QDOP, PDF de instrumento) é **copiado para a pasta de dados por `cadastro aplicar`**, como os modelos do espelho: a produção não lê o checkout.
- **"Hoje"** é `tempo.hoje_local()` (America/Cuiaba). Nunca `date.today()`.
- **Avisa e deixa seguir** (spec §0.5): nada bloqueia a operação; o que foge da regra pede uma linha de justificativa, gravada na auditoria. Exceções que BLOQUEIAM, por serem erro e não regra: medição cancelada/desistida/recebida, arquivo inválido, e-mail sem destinatário.
- **Cadastro sem tela.** Tudo que é regra (textos das cartas, ordem do pacote, destinatários, fiscais, datas-base, instrumentos, QDOP) entra por YAML em `cadastro/` e `python -m app.cli cadastro aplicar`. A operação não edita cadastro.
- **Textos** de interface, erros e commits em português. Commit `tipo: descricao` sem acento no assunto, terminando com a linha `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- **Testes.** `cd backend && .venv\Scripts\python -m pytest` (suíte inteira só ao fim de cada bloco; durante a tarefa, o arquivo de teste da tarefa). Frontend: `cd frontend && npm test -- --run` e `npm run build`. **Nunca rodar backend e frontend em paralelo** (a CPU desta máquina cai a 13% sob carga; memória `maquina-cpu-freada`). Um teste focado por comportamento, no arquivo `backend/tests/test_<modulo>.py`.
- **Hooks de UI.** O impeccable roda como lint em Edit/Write de arquivo de UI; seguir os tokens de `frontend/src/tokens.css` e as classes existentes (`cartao`, `btn`, `campo`, `tabela`, `selo--*`, `aviso`, `abas`).
- **Subagentes**, se usados: Opus ou Fable; nunca Sonnet ou Haiku.

## Decisões para aprovação (resumo; o texto completo está em cada bloco)

Bloco 5
- **D5.1** Carta, capa e divisória geradas **em PDF pelo sistema** com fpdf2 (fonte Arial do Windows; na falta dela, Helvetica). Não existe modelo Word de carta de protocolo em lugar nenhum (levantamento de 2026-09-24); o texto vem de `cadastro/cartas.yaml` por família e o timbre é imagem recortada de uma carta real. O corpo é editável na prévia antes de montar.
- **D5.2** Um **protocolo** = um documento a assinar = um ofício. Um e-mail pode levar mais de um protocolo (SINFRA: execução e reajuste no mesmo e-mail, em PDFs separados).
- **D5.3** Famílias no código, detalhes no cadastro: MTPAR (PDF único: carta, notas, certidões; um e-mail por natureza; pede devolutiva), SES (capa, carta com lista numerada, divisórias e peças técnicas; um e-mail por natureza), SINFRA em **duas etapas** (medição assinada: carta + peças, planilha editável solta; depois nota: NFS-e, ZIP de certidões, regularidade e CNO, sem carta), Prefeitura (carta e notas no PDF; ZIP e peças soltos; corpo editável para link).
- **D5.4** Na SINFRA a medição vira `protocolada` na **etapa da nota**, com o número do ofício da etapa da medição. A etapa da medição registra o envio e não muda o estado (a nota ainda não existe quando a medição assinada sai: MT-388, 09/09 e 16/09).
- **D5.5** Conferência do assinado **por texto de cada página** (carimbo `Docusign Envelope ID` retirado antes de comparar), com as três regras da spec §6; resultado vira aviso, e enviar com aviso pede justificativa. Tetos próprios do pacote: 40 MB e 400 páginas.
- **D5.6** Comprovante do CNO: PDF por obra no cadastro (`cno_pdf`), copiado para a pasta de dados; falta vira aviso na prévia (hoje os 22 contratos estão sem CNO).
- **D5.7** Teto do e-mail sobe de 25 MB para 35 MB (limite padrão de envio do Exchange Online); o limite de 25 MB **por documento** da SINFRA vira aviso.
- **D5.8** `medicao_protocolos` ganha `protocolo_id` (a coluna `origem` tem CHECK antigo e continua `manual`): o protocolo feito pelo sistema fica ligado ao envio.

Bloco 6
- **D6.1** Registro único de avisos (`app/avisos.py`) no formato da spec §11 (tipo, nível, público, obra, dias, valor, mensagem, destino). Saem da tela os alertas antigos `reajuste_sem_par`, `data_base`, `medicao_sem_protocolo`, `vigencia_vencida` e `execucao_vencida` (substituídos pelos do catálogo nos blocos 6 e 7).
- **D6.2** Tela inicial da operação: avisos, "medições protocoladas no mês: X de N obras ativas" (pela data do protocolo), valor protocolado no mês e no mês anterior (valor cheio, que é o que a operação protocola).
- **D6.3** Página da obra com as abas da spec §10.3 (Medições, Notas, Documentos, Reajuste, Prazos, Contrato); o protocolo passa para dentro de Medições; os links antigos `/cronograma`, `/aditivos` e `/protocolo` continuam abrindo a aba certa.
- **D6.4** Menu: Início, Medições, Obras, Documentos, Diretoria (diretoria e admin), Administração. Sugestões e Engenharia saem do menu (o código sai no bloco 9).

Bloco 7
- **D7.1** `pleitos` (reajuste, prazo, conclusão) seguem o mesmo caminho do protocolo: ofício gerado, assinado por fora, conferido, enviado. O instrumento que atende o pleito é **calculado** a partir do cadastro (não é gravado): o apostilamento de reajuste com a mesma data-base e ciclo; qualquer instrumento de prazo com data posterior ao envio.
- **D7.2** Ciclo do reajuste = ano do aniversário; o aviso "pleito não enviado" vale do dia 1º do mês de aniversário menos 30 dias até o envio; "apostilamento pendente" do envio até o apostilamento; para a diretoria depois de 90 dias. Só o ciclo corrente de cada data-base conta.
- **D7.3** Carta de prazo com a seção "HISTÓRICO DO CONTRATO" montada dos instrumentos de prazo cadastrados; a pessoa digita justificativa e dias. A carta não oferece "chuva" como texto pronto (vedação contratual).
- **D7.4** Medição final marcada pela operação: grava `medicoes.final` e põe o contrato em encerramento (`encerramento_iniciado_em`); `cadastro aplicar` **não apaga** esse marco quando o YAML ainda diz `ativo` (mostra a divergência no ensaio).

Bloco 8
- **D8.1** Tela da diretoria nas cinco seções da spec §10.5, sempre na cota. "Prazo normal do órgão" = 3º quartil de dias entre protocolo e baixa nos últimos 12 meses (mínimo 10 medições; abaixo disso, 30 dias); a previsão de recebimento usa a mediana com a mesma regra de mínimo.
- **D8.2** Enquanto `geral.yaml` tiver `diretoria.total_a_receber_liberado: false`, a seção "Onde está o dinheiro" mostra quantidades e dias do que está protocolado esperando pagamento, **sem valores** ("a conciliar com a controladoria", spec §10.5).
- **D8.3** QDOP exportado a partir de um **modelo** recortado do arquivo oficial de 22/09 (cabeçalho, estilos e rodapé), com **valores** e não fórmulas (abre em qualquer visualizador sem recalcular). "Valores faturados" = recebido de execução e projeto (diário T7); "reajuste (recebido)" = medições de reajuste recebidas.
- **D8.4** O cadastro é atualizado pelo QDOP de 22/09 (Rota do Oeste lote 2, BR-163, Estações BRT, Deciolândia, apostilamentos de Leblon e MT-402) numa tarefa de dados com ensaio; o Leonardo confere antes do `aplicar` em produção.

Bloco 9
- **D9.1** Tabelas da detecção **renomeadas** para `arquivo_*` (não apagadas): o dado fica no banco e no backup, e nenhum código lê mais.
- **D9.2** Saem: `deteccao.py`, `sincronizacao_graph.py`, `sugestoes.py`, `api_sugestoes.py`, `api_graph.py`, `importar_faturamento.py` (carga única feita em 10/09), a parte de leitura de `graph.py`, telas Sugestões, Painel da Engenharia e Microsoft 365, formulários de contrato e aditivo, rotas antigas de certidão, a trava `DASH_CADASTRO_VERSIONADO`. A dúvida de casamento do RM deixa de virar sugestão (o botão "vincular nota" da medição já existe).
- **D9.3** **Decisão do Leonardo em 2026-09-24:** os fluxos do Power Automate da dashboard antiga **não serão desligados**, e a dashboard antiga continua no ar com eles (ela depende dos fluxos). O corte do bloco 9 fica só no sistema novo; o roteiro externo se reduz às permissões de leitura do app do Entra ID e aos argumentos de leitura da tarefa agendada.

Transversais
- **DT1 Gate Sol.** O `CLAUDE.md` pede gate nas branches que tocam arquivo externo (bloco 5: pacote, assinado, envio) e dinheiro (bloco 8: diretoria e QDOP). Proposta: fazer o gate nesses dois, um round cada; os blocos 6, 7 e 9 sem gate. O Leonardo pode dispensar.
- **DT2 Levantamentos com o Chrome da empresa** (navegador "Browser 1", este PC). Aprovar o plano autoriza baixar para o scratchpad, só para leitura: (a) a IN 001/2024 com anexos (check-list da SINFRA) do SharePoint da MT-388; (b) um protocolo SINFRA real de medição (carta PDF) e o da nota; (c) a carta CT/245/LT/2026 (conclusão, Orla). Nada é enviado, alterado ou apagado.

## Ordem de execução e paradas

1. **P1: aprovação** deste índice e das decisões (o Leonardo pode ajustar qualquer D).
2. Bloco 5 → 6 → 7 → 8 → 9, tarefa por tarefa, commit por tarefa, suíte inteira ao fim de cada bloco, gate Sol nos blocos 5 e 8 (se mantido).
3. **P2: dados do cadastro que só o Leonardo confere** (não bloqueia a implementação; o sistema avisa o que falta): cargo, tratamento e portaria dos fiscais; fiscais que faltam (Maternidade, Região Oeste, Coxipó 2ª, Deciolândia, MT-401, Atalaia, BR-163); `objeto_completo` de cada contrato (pré-preenchido do QDOP pela tarefa 8.2); comprovante do CNO de cada obra; folga da MTPAR por contrato; paralisações da MT-402 (01/02 a 05/05/2026) e da Coxipó 2ª (desde 01/10/2025).
4. **P3: merge e deploy.** Um pedido só, no fim, com o resumo dos cinco blocos. Com o OK: para cada bloco, em ordem, backup `dashboard-PRE-BLOCO<n>-<ts>.db`, merge em `master`, `scripts\deploy.ps1 -Ref origin/master` (com frontend), `cadastro aplicar --ensaio` e real, conferência de saúde. Se algum bloco falhar em produção, o `deploy.ps1` faz rollback e os seguintes esperam.
5. **P4: limpeza externa** (bloco 9): permissões de leitura do app do Entra ID e argumentos de leitura da tarefa agendada, com OK. Power Automate e dashboard antiga ficam ligados.

## Interfaces compartilhadas (nomes que atravessam blocos)

| Módulo | Função | Nasce | Usado em |
|---|---|---|---|
| `app/oficios.py` | `canonico(digitado, sigla, ano) -> str`; `na_carta(canon) -> str`; `usos(conn, canon, ignorar=None) -> list[str]` | 5 | 5, 7 |
| `app/carta.py` | `Carta` (dataclass); `gerar(c) -> bytes`; `pagina_titulo(linhas, emitente=None) -> bytes`; `data_extenso(d) -> str`; `config(conn) -> dict`; `preencher(modelo, campos) -> str`; `emitente(conn, entidade_id) -> dict`; `fiscal_vigente(conn, contrato_id, na_data) -> dict | None` | 5 | 5, 7 |
| `app/pdfs.py` | `juntar(partes) -> bytes`; `paginas(pdf) -> int`; `TETO_BYTES_PACOTE`, `TETO_PAGINAS_PACOTE` | 5 | 5, 7 |
| `app/leitura_pdf.py` | `textos_por_pagina_com_limite(pdf, teto_paginas=400) -> list[str]` | 5 | 5, 7 |
| `app/assinatura.py` | `conferir(montado, assinado) -> dict`; `conferir_pdfs(montado_pdf, assinado_pdf) -> dict` | 5 | 5, 7 |
| `app/protocolo.py` | `FAMILIAS`, `Etapa`; `criar`, `detalhe`, `listar`, `adicionar_peca`, `remover_peca`, `corpo_padrao`, `montar`, `receber_assinado`, `previa_envio`, `enviar`, `registrar_numero_orgao`, `descartar` | 5 | 5, 6, 8 |
| `app/avisos.py` | `listar(conn, hoje=None, publico="operacao") -> list[dict]`; `resumo_mes(conn, hoje=None) -> dict`; `FONTES` | 6 | 6, 7, 8 |
| `app/reajuste.py` | `ciclos(conn, contrato_id, hoje=None) -> list[dict]`; `avisos(conn, hoje=None) -> list[dict]` | 7 | 7, 8 |
| `app/prazos.py` | `situacao(conn, contrato_id, hoje=None) -> dict`; `avisos(conn, hoje=None) -> list[dict]`; `historico_texto(conn, contrato_id) -> str` | 7 | 7, 8 |
| `app/pleitos.py` | `criar`, `detalhe`, `listar`, `adicionar_anexo`, `corpo_padrao`, `montar`, `receber_assinado`, `previa_envio`, `enviar` | 7 | 7 |
| `app/diretoria.py` | `prazo_orgao(conn, orgao_id, hoje, quantil) -> int`; `painel(conn, hoje=None) -> dict`; `avisos(conn, hoje=None) -> list[dict]` | 8 | 8 |
| `app/qdop.py` | `linhas(conn, hoje=None) -> list[dict]`; `gerar_xlsx(conn, hoje=None) -> bytes` | 8 | 8 |

**Formato de aviso** (bloco 6 em diante): `{"tipo": str, "nivel": "critico"|"acao"|"atencao", "publico": ["operacao"] | ["diretoria"] | ["operacao","diretoria"], "contrato_id": int|None, "obra": str|None, "dias": int|None, "valor_centavos": int|None, "mensagem": str, "destino": {"tela": "contrato", "id": int, "aba": str} | {"tela": "documentos"} | {"tela": "medicao", "contrato_id": int, "medicao_id": int}}`.

## Self-review (feito ao escrever, 2026-09-24)

- **Cobertura da spec**:
  - §2 medição final e protocolo sem nota: blocos 7 e 5.
  - §3 passos 4 a 7: bloco 5.
  - §5.1 a §5.4: bloco 5 (protocolo) e bloco 7 (pleito, prazo, conclusão).
  - §6: bloco 5.
  - §7.2 a §7.4: bloco 7.
  - §10.1 a §10.3: bloco 6.
  - §10.5: bloco 8.
  - §10.6 (contas Microsoft conectadas): bloco 9.
  - §11: blocos 6, 7 e 8.
  - §12: migrações 025 a 027.
  - §13 e §14.4 e 5: bloco 9.
  - §16 (fora de escopo): respeitado; FRC continua fora; a dashboard antiga e seus fluxos continuam ligados (decisão de 2026-09-24).
- **Lacunas que ficaram como decisão ou parada, e não como tarefa**:
  - o check-list da IN 001/2024 (DT2 e tarefa 5.0);
  - dados de fiscais e CNO (P2);
