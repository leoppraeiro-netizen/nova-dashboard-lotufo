# Pacote 5 — tela e textos (fase 4, 10/10/2026)

Branch `fix/tela-textos` (a partir de `master` 7e7f67a, pacotes 1 a 4 em produção). Sem merge, sem push; produção,
portas 80/8080 e 5173 não tocadas. Corrige B-01, A-21, N-01, B-09, B-02, B-03, B-06, B-07, B-08, B-11, B-12, B-13 e o
resíduo do pacote 4 (ajuda do nº do órgão) e B-04 (corrigido depois, com a decisão do espaçamento; ver abaixo). Para cada item:
primeiro o teste que reproduz o defeito (rodado e falhando), depois a correção, depois o teste passando.

## Commits

| Commit | Item |
|---|---|
| ffb63e7 | B-01 — medido no mês pela competência, contra o mês anterior inteiro |
| cda2195 | A-21 — uma definição de "obras ativas" e a base dita no farol |
| 792ef0b | N-01 — aba Aguardando pagamento conta as notas da tabela |
| 15de4af | B-09 — diretoria sem ações de escrita nem mensagem crua de permissão |
| 3460345 | B-02 — linha do tempo mostra a edição de valor |
| 4967a91 | B-03, B-12 — valor inválido ensina o formato; medição sem código interno |
| 3cb724c | B-12 — validação da API em português; acentos que faltavam |
| 0fe4ff4 | B-08 — recusa de PDF corrompido sem o nome da exceção |
| 0a473c1 | B-11 — rótulo em português para toda ação da auditoria |
| 83844c9 | B-06 — envio da nota troca o aviso velho por "Nota enviada às HH:MM." |
| cbbf53b | B-07 — "Número gravado." ao registrar o nº do órgão; coluna e dica do SIGA |
| f4cd1cb | Resíduo do pacote 4 — ajuda do nº do órgão |
| d5a117d | B-13 — celular: valor numa linha, título da medição sem "Es…" |
| feb414f | B-04 — tabela de notas da etapa 3 densa: cabe a 1024 px |

## O que mudou, item por item (linguagem simples)

**B-01 — "Medido no mês" do Início com a regra da Carteira.** Antes o Início somava as medições pela data em que foram
lançadas no sistema; a carga do legado, feita em setembro, virou "setembro R$ 765 mi" e o Início mostrava "▼ 97%".
Agora soma pela competência (o mês da medição), em valor cheio, sem canceladas, desistidas e previstas — a mesma
regra do "medido no mês" da Carteira (que mostra a cota). A comparação é com o mês anterior inteiro.
Antes: "Medido em outubro · até dia 10 … ▼ 97% sobre 01 a 10 de setembro · medições lançadas no período".
Depois: "Medido em outubro … ▲/▼ N% sobre setembro · valor cheio · medições da competência". O gráfico "Medido por
contratante" segue a mesma regra (legenda "setembro" / "outubro"). O aviso de mês vazio diz "Nenhuma medição da
competência de outubro." e continua mostrando o último lançamento.
Arquivos: `backend/app/inicio.py`, `frontend/src/Inicio.tsx`.

**A-21 — "obras ativas" com uma definição só.** "Obra ativa" = contrato ativo sem encerramento iniciado (a regra de
`avisos.ativos`, a do Início). Medições continua listando as obras em encerramento (elas ainda medem a final), mas a
legenda passa a dizer "19 obras ativas · 2 em encerramento · N medições em andamento". O farol da Carteira conta tudo
que não é rescindido (é o QDOP) e agora diz a base: "14 de 22 obras (19 ativas, 2 em encerramento, 1 suspensa) com
farol em Atenção ou Crítico". A API ganhou `encerramento` em cada obra de `/api/medicoes/resumo` e `obras_base` em
`/api/diretoria`. Arquivos: `backend/app/medicoes.py`, `backend/app/diretoria.py`, `frontend/src/MedicoesPagina.tsx`,
`frontend/src/Diretoria.tsx`, `frontend/src/resumoMedicoes.ts`.

**N-01 — a aba "Aguardando pagamento" e a tabela contam a mesma coisa.** A aba contava linhas do resumo (medição +
reajuste viram uma) e a tabela contava notas. Agora a aba conta as medições protocoladas, uma por nota, o mesmo número
do título "N notas" da tabela. Arquivo: `backend/app/medicoes.py`.

**B-09 — diretoria só consulta.** (1) Em Notas a enviar, Enviar a nota e Aguardando pagamento, quem não pode editar
(diretoria) não vê "Enviar a nota →", "Registrar envio feito por fora", "Anexar", o e-mail, os documentos
complementares nem o formulário do nº do órgão; vê o que vai no envio e o número já registrado. A página da medição
(etapa 4) segue a mesma regra. (2) Se alguma ação ainda der 403, a mensagem deixa de ser "Permissão necessária:
editar_cadastros" e vira "Seu perfil só consulta esta tela: a ação é da engenharia ou da administração." (3) `/conta`
da diretoria mostra "Você entra com o e-mail …" e a troca de senha; a conta Microsoft e a assinatura ficam só para
quem pode editar. `GET /api/correio/status` passa a exigir só `ver_paineis`; conectar, testar e assinatura continuam
com `editar_cadastros`. Arquivos: `frontend/src/{NotasAEnviar,EnviarNota,AguardandoPagamento,MinhaConta,MedicoesPagina,
App,Etapas,Login,api}.tsx/ts`, `backend/app/api_correio.py`.

**B-02 — editar o valor aparece na linha do tempo.** A edição do valor protocolado e do atestado sai da auditoria com
o texto pronto: "Valor protocolado definido em R$ 1.000,00 por Fulano", "Valor protocolado alterado de R$ 1.000,00 para
R$ 1.234,56 por Fulano", "Atestado definido em R$ 1.200,00 por Fulano". Gravar o mesmo valor não vira evento. Vem na
lista de medições da obra (que a página da medição lê) e no detalhe da medição. Arquivos: `backend/app/medicoes.py`
(`edicoes_valor`), `backend/app/api_medicoes.py`, `frontend/src/medicao.ts`.

**B-03 e B-12 — mensagens sem acento, com código interno ou em inglês.**
- Valor: antes "Valor monetario invalido: '1234.56'"; depois "Valor monetário inválido: use vírgula nos centavos, ex.:
  1.234,56 (recebido: '1234.56')".
- Espelho: antes "Medição 32 (execucao) já está recebida: não pode gerar espelho de novo"; depois "Medição 32 de
  execução já está recebida: não pode gerar espelho de novo". O mesmo vale para "já tem espelho", "já existe neste
  contrato" e "está cancelada: o espelho não pode ser enviado". O estado também sai por extenso ("com nota emitida" em
  vez de "nota_emitida") — pequena extensão do pedido, mesmo problema.
- Validação: um tratador único traduz os erros do validador, mantendo a lista com o campo: "campo obrigatório", "no
  máximo N", "no mínimo N", "maior que N", "menor que N", "no máximo N caracteres", "valor fora das opções"; o resto
  vira "valor inválido" (nunca o inglês). Antes "dias (Input should be less than or equal to 3650)"; depois "dias (no
  máximo 3650)". A resposta não ecoa mais o valor enviado (`input`). Incluí `greater_than`/`less_than`/
  `string_too_short` além da lista pedida porque o próprio formulário do pleito usa `gt=0` e `min_length=1`.
- Varredura de mensagens sem acento em `backend/app`: sobravam duas em ValueError ("Transicao invalida" em
  `contratos.py`, só usada pela carga do legado, e "Parcela-resto … nao esta no rateio" em `dinheiro.py`); corrigidas.
  O resto já estava acentuado; comentários, logs e o erro de inicialização do banco ficaram como estavam.
Arquivos: `backend/app/dinheiro.py`, `backend/app/medicoes.py`, `backend/app/espelhos.py`, `backend/app/main.py`,
`backend/app/contratos.py`.

**B-08 — PDF corrompido.** Antes "PDF inválido ou corrompido (ValueError) — envie o arquivo original emitido pelo
órgão"; depois a mesma frase sem "(ValueError)", nos dois lugares que a montam (leitura de certidão e gravação de
arquivo). Arquivos: `backend/app/leitura_pdf.py` (constante `PDF_CORROMPIDO`), `api_documentos.py`, `arquivos.py`.

**B-11 — auditoria em português.** Todas as ações que `backend/app` grava (levantadas com o grep de
`auditoria.registrar`, inclusive as dinâmicas `medicao.valor_{campo}` e `certidao.registrar`/`certidao.nao_se_aplica`)
mais as que scripts gravaram no banco (`medicao.remover_teste`, `regularidade.competencia_corrigida`) têm rótulo:
"FRC gerada", "Certidão registrada", "Link adicionado ao protocolo", "Envio liberado à mão", "Usuário desbloqueado",
"Senha redefinida pelo admin", "Senha trocada", "Atestado alterado" etc. Ação nova sem rótulo aparece legível
("algo.novo_aqui" → "Algo novo aqui"). A janela de 500 eventos não foi mexida (fora do desenho).
Arquivo: `frontend/src/administracao.ts`.

**B-06 — confirmação do envio.** Na página da medição, ao enviar a nota, o aviso antigo ("Valor protocolado gravado.")
some e aparece "Nota enviada às HH:MM." (região de status). O registro de envio feito por fora, pelo mesmo caminho,
mostra "Envio registrado: a nota foi para Aguardando pagamento." Arquivos: `frontend/src/EnviarNota.tsx`,
`Etapas.tsx`, `MedicaoPagina.tsx`.

**B-07 — registrar o nº do protocolo.** Depois de "Registrar" aparece "Número gravado." (região de status) por 4
segundos. A coluna "Nº do protocolo (SIGA)" virou "Nº do protocolo no órgão", e a dica "(SIGA, na MTPAR)" só aparece
nas linhas da MTPAR. Arquivo: `frontend/src/AguardandoPagamento.tsx`.

**Resíduo do pacote 4 — ajuda do nº do órgão.** Em Protocolo, antes "Obrigatório na primeira vez; depois dá para anexar
só o comprovante." (a tela não tem campo de comprovante); depois "Obrigatório; informe o número dado pelo órgão."
**Para o backlog:** upload do comprovante do protocolo pela tela (não registrei em `docs/backlog.md` porque o pacote só
commita backend/ e frontend/src/). Arquivo: `frontend/src/Protocolo.tsx`.

**B-13 — celular.** (1) Início abaixo de 420 px: o valor grande fica numa linha e a fonte acompanha a largura
(`clamp(16px, 5.8vw, 22px)`): 21,75 px a 375 px e 18,6 px a 320 px. (2) Página da medição abaixo de 600 px: a meta
(órgão · instrumento, "valores cheios") desce para baixo do título e o título quebra linha em vez de cortar. A regra
vale só para a página da medição (classe `topbar__linha--quebra`); a página da obra e a Enviar a nota não mudaram.
Arquivos: `frontend/src/inicio.css`, `frontend/src/tokens.css`, `frontend/src/MedicaoPagina.tsx`.
Conferência com Playwright (build de produção servido pelo próprio Playwright, API simulada, nada em 5173/8080):
- 375 px: os quatro valores do Início com 1 linha, largura 239 = scrollWidth 239 (nada transborda), página sem rolagem
  lateral (375/375). Título "Estações BRT · Reajuste da 7ª Medição" em 2 linhas, inteiro; meta embaixo, sem corte.
- 320 px: valores com 1 linha (184 = 184), título em 3 linhas, sem corte.
Script e capturas no scratchpad da sessão (`b13.mjs`, `b13-inicio-375.png`, `b13-medicao-375.png`).

## B-04 — corrigido (tabela densa)

Primeiro desenho (deixar a coluna "Nota" quebrar linha) não resolvia: medi com Playwright a 1024 px, com as mesmas
duas notas da captura do verificador, e a coluna "Nota" já quebrava linha e estava na largura mínima (110 px). Quem
empurra a tabela são as seis colunas de dinheiro, em fonte mono e sem quebra: tabela de 886 px num contêiner de
854 px, coluna "Nota" de x=893 a 1003 com a borda em 971.

Decisão (coordenação, 10/10/2026): espaço lateral de 8 px em todas as células, inclusive a primeira e a última, **só**
na tabela de notas da etapa 3, com a classe própria `tabela--densa` (`frontend/src/Notas.tsx`, regra em
`frontend/src/tokens.css` com o comentário da medida). Teste vitest de presença da classe (`Notas.test.tsx`).

Conferência com Playwright (build de produção, API simulada, nada em 5173/8080):
- 1024 px: antes 886 px em 854 px, com rolagem; depois 854 px em 854 px, **sem rolagem**, coluna "Nota" de 851 a 971
  (borda em 971).
- 1366 px: a tabela continua com 1196 px, sem rolagem, nos dois casos. Muda pouco, mas muda: o recuo da primeira e da
  última coluna passa de 20 px para 8 px (o texto de "Saída" encosta mais na borda do cartão), as colunas de dinheiro
  ficam 8 px mais estreitas e "Saída" e "Nota" ganham a sobra (na captura, "nº 2315 · 07/10/2026 · só no RM (PDF não
  anexado)" passa a caber numa linha e "Medição · Lotufo · Cuiabá" também). Os valores e a ordem são os mesmos.
  Capturas `b04-atual-1366.png` e `b04-antigo-1366.png` no scratchpad da sessão.

## Riscos e observações

- B-01 muda o número do Início para quem já se acostumou: setembro deixa de mostrar R$ 765 mi e passa a mostrar só as
  medições de competência 09/2026. O Início segue em valor cheio; a Carteira, na cota.
- A-21: a lista de Medições continua com as obras em encerramento (a "Nova medição" precisa delas para a medição
  final); só a contagem do rótulo mudou.
- N-01: a aba conta medições protocoladas; as `nf_emitida` do legado aparecem no "Todas as obras" do resumo, mas não
  entram na aba nem na tabela (como a tabela já fazia).
- B-09: a `/conta` da diretoria não chama mais o estado da conta Microsoft (não precisa); a rota foi aberta para
  `ver_paineis` como decidido, para quem precisar.
- B-02: a leitura das edições varre a auditoria uma vez por lista de medições da obra (não há índice por entidade em
  `audit_log`); com o volume de hoje é desprezível.
- B-12: o 422 de validação não traz mais `input` nem `ctx`/`url`; quem consome a API usa `loc` e `msg` (a tela só usa
  esses dois).

## Gate Sol: 6 achados, 6 corrigidos, + S7

Todos procederam; corrigidos na mesma branch, depois do B-04, com teste que falha antes.

| Commit | Achado | O que mudou |
|---|---|---|
| 8aea4c9 | S1 (média) | Linha de auditoria antiga com JSON torto ou que não é dicionário (`antes=''`, `'[]'`, `'{torto'`) derrubava a medição e a lista da obra com 500. Agora o evento sai da linha do tempo com `log.warning`. |
| eaa434c | S2 (média) | A linha do tempo varria todas as edições de valor da auditoria a cada obra aberta. Agora filtra por `entidade_id` no SQL, em lotes de 500, e a migração `036_audit_log_indice.sql` cria `ix_audit_log_entidade (entidade, entidade_id, acao, id)`; o teste confere que o plano da consulta usa o índice. |
| d8f2703 | S3 (baixa) | Corpo JSON torto (`{"x":`) virava "valor inválido" com `loc` = posição do erro. Agora "JSON inválido ou incompleto", `loc` `["body"]`. |
| f1c1c51 | S4 (baixa) | `parse_brl` não ecoa mais o valor digitado: "Valor monetário inválido: use vírgula nos centavos, ex.: 1.234,56". |
| ea26289 | S5 (baixa) | Edição de valor sem usuário (detecção, carga) termina em "pelo sistema". |
| fe7c004 | S6 (baixa) | `/api/auth/eu` já devolvia o e-mail; o login passa a devolver também. No front `Usuario.email` é obrigatório; o teste da conta usa o usuário no formato da resposta de `/api/auth/eu` (o que o App guarda); sem e-mail, a frase "Você entra com o e-mail…" não aparece. |
| 31be0ae | S7 (baixa, coordenação) | Início com o mês atual zerado mostrava "R$ 0,00 ▼ 100% sobre setembro". Agora "ainda sem medição desta competência · setembro: R$ X"; com o anterior zerado e o atual > 0, "setembro sem medição", sem percentual. |

Desvios: nenhum de regra. No S6, "usar a resposta real do login no teste" foi lido assim: o backend testa que login e
`/eu` devolvem o e-mail; o teste do front usa um objeto com o formato exato da resposta de `/eu` (o front não chama o
servidor nos testes).

## Verificação final

- Backend, suíte inteira: 928 passaram, 1 pulado (7 min 35 s).
- Frontend (depois do B-04): `npm test` 31 arquivos / 109 testes passaram; `npm run typecheck` limpo; `npm run build` ok.
- Depois do gate Sol (S1 a S7): backend 932 passaram, 1 pulado (7 min 42 s); `npm test` 31 arquivos / 111 testes; `typecheck` limpo; `build` ok.
