# Pacote 4 — regras de estado e de entrada (fase 4, 10/10/2026)

Branch `fix/regras-entrada` (a partir de `master` e16a108). Sem merge, sem push, produção e portas 80/8080 não tocadas;
frontend não mexido. Corrige A-09, A-20, A-07, A-08, A-14 e A-15 de `06-verificacao-api.md`. Para cada item: primeiro
o teste que reproduz o defeito (rodado e falhando), depois a correção, depois o teste passando — teste e correção no
mesmo commit.

## Commits

| Commit | Item |
|---|---|
| 7876a96 | A-09 — protocolo feito fora antes da nota vira pendência |
| 65ec8a2 | A-20 — competência antes do início do contrato recusada; antes da última medição, aviso |
| ab3f998 | A-07 — id acima de int64 é 422 na entrada, em todas as rotas |
| dd41177 | A-08 — teto de R$ 99.999.999.999,99 em todo valor digitado |
| 8fc51bc | A-14 — só dígitos 0-9 nos formatos de entrada |
| bc93017 | A-15 — número do órgão vazio é recusado e não apaga o gravado |

## O que mudou, item por item (linguagem simples)

**A-09 — "Registrar protocolo feito fora" não pula mais a nota sem justificativa.** Antes dava para marcar uma medição
como protocolada direto do começo (prevista, espelho gerado ou enviado), só com data e ofício, pulando faturamento, nota
e envio. Agora, nesse caso, aparece a pendência "Nota fiscal ainda não emitida: protocolar agora pula o faturamento e a
nota", na mesma lista das certidões pendentes. O protocolo só passa marcando "apesar das pendências" e escrevendo uma
justificativa de pelo menos 10 caracteres; a pendência e a justificativa ficam na auditoria. Com a nota já emitida,
nada muda. O envio pelo sistema, o envio feito por fora e a carga do histórico continuam como estavam.
Arquivos: `backend/app/medicoes.py` (`registrar_protocolo`), `backend/app/api_medicoes.py`.

**A-20 — espelho com mês fora da vida do contrato.** A prévia e a geração recusam competência anterior ao mês de início
da execução do contrato (ou da vigência, quando a execução está em branco): "Competência 01/2020 é anterior ao início
do contrato (03/2023)". Competência anterior à da última medição do mesmo tipo (sem contar canceladas, desistidas e a
própria medição sendo gerada de novo) só gera aviso na prévia: "Competência 07/2026 é anterior à da última medição
(nº 5, 08/2026): confira". Arquivo: `backend/app/espelhos.py`.

**A-07 — número de id gigante não derruba mais nenhuma tela.** Todo número de registro que vem no endereço (medição,
contrato, protocolo, pleito, espelho, nota, usuário etc.) só é aceito entre 1 e 9.223.372.036.854.775.807; fora disso o
servidor responde "dado inválido" (422) antes de consultar o banco. O mesmo vale para `contrato_id` em "medições em
andamento" e `entidade_id` no zip de documentos. Arquivos: todos os `backend/app/api_*.py` com id no endereço.

**A-08 — valor gigante não derruba mais a gravação.** Todo valor em reais digitado (nota manual, valores da medição,
cronograma, espelho, cadastro) agora tem teto de R$ 99.999.999.999,99, o mesmo que o espelho já usava; acima disso:
"Valor acima do máximo aceito (R$ 99.999.999.999,99)". Conferido: o maior contrato do banco é R$ 431 milhões e o maior
valor protocolado R$ 1,2 milhão — longe do teto. Arquivo: `backend/app/dinheiro.py`.

**A-14 — só algarismos comuns.** O padrão que conferia valores e meses aceitava algarismos árabes ("١٢٣,٤٥" virava
R$ 123,45). Agora só 0-9 em: valores em reais, competência da regularidade (rota e conferência), data-base do pleito,
período do espelho e mês/ciclo do cadastro. Arquivos: `dinheiro.py`, `api_documentos.py`, `documentos.py`,
`api_pleitos.py`, `espelhos.py`, `cadastro_arquivos.py`.

**A-15 — número do órgão vazio não apaga o gravado.** Mandar o número em branco (pela API das notas ou dos protocolos)
gravava "sem número" sem avisar. Agora é recusado com "Informe o número do protocolo no órgão" e o número anterior fica.
Vale para o envio pelo sistema e para o envio feito por fora. Arquivos: `backend/app/protocolo.py`,
`backend/app/notas_envio.py`.

## Saídas antes / depois

| Item | Antes da correção | Depois |
|---|---|---|
| A-09 | `3 failed, 1 passed` — prevista/espelho_gerado/espelho_enviado: `assert (201 == 422)` | `4 passed` |
| A-20 | prévia 2020-01 com início 03/2023 → `assert 200 == 422`, `avisos: []`; aviso da última medição ausente | `2 passed` |
| A-07 | teste que percorre o OpenAPI: ao menos 22 rotas com `500 OverflowError('Python int too large to convert to SQLite INTEGER')` visíveis (a lista do pytest foi truncada; 77 falhas no total, contando as rotas que davam 404 sem teto na entrada) | `1 passed` |
| A-08 | nota manual: `OverflowError` (500); `/valor`: 422 com "Valor monetário fora do limite" (acima do teto, abaixo do int64, passava) | `3 passed` |
| A-14 | `parse_brl("١٢٣,٤٥")` → `DID NOT RAISE`; atestado → `200`; regularidade e pleito → 422 só por acaso (mensagem de outra regra: "A competência 08/٢٠٢٦ ainda não aconteceu", "Data-base '٢٠٢٤-06' não é do contrato") | `5 passed`, 422 pelo formato |
| A-15 | `""` → `assert (200 == 422)` nos dois caminhos | `2 passed` |

Suíte inteira do backend no fim: `914 passed, 1 skipped in 442.58s`. Frontend não foi tocado (sem `npm test`/`typecheck`).

## Decisões e desvios do desenho

1. **A-09 — interruptor explícito em vez de "origem manual".** O desenho dizia "origem `manual`", mas o envio pelo
   sistema (`protocolo.enviar`) e o envio por fora (`notas_envio.envio_externo`) também gravam origem `manual`. Para não
   mexer neles, `registrar_protocolo` ganhou `exige_nota=False`, ligado só pela rota `POST /api/medicoes/{id}/protocolo`.
   As ~25 chamadas diretas de `registrar_protocolo` nos testes (montagem de cenário) continuam valendo.
2. **A-09 — onde a pendência fica gravada.** Entrou na MESMA lista, como pedido; na auditoria a lista continua sob a
   chave `certidoes_pendentes` (nenhum consumidor lê essa chave). A exigência de 10 caracteres vale quando a pendência
   da nota está presente; só certidão pendente continua aceitando qualquer justificativa não vazia, como antes.
3. **A-09 — testes antigos ajustados.** 7 testes protocolavam medição `prevista` pela rota como montagem de cenário.
   Os de `test_api_medicoes.py` passaram a pôr a medição em `nota_emitida` antes; os de `test_api_inicio.py` e
   `test_api_paineis.py` passaram a protocolar "apesar das pendências" com justificativa.
4. **A-20 — aviso não compara a medição com ela mesma.** Gerar de novo a medição nº 5 com outra competência não avisa
   "anterior à da última medição (nº 5…)".
5. **A-07 — id 0, negativo e gigante agora são 422, não 404.** Um teste antigo (`test_api_certidoes.py`, id gigante →
   404) foi ajustado para 422. As conferências de faixa que já existiam dentro de algumas rotas (`1 <= id <= MAX_INT64`
   em espelhos, protocolos, certidões, aditivos, documentos) ficaram, agora sem efeito — não removidas.
6. **A-08 — conferências antigas de int64.** `if centavos > MAX_INT64` em `api_medicoes.py` e `api_cronograma.py` ficou
   sem efeito (o teto novo é menor); não removido.
7. **A-14 — o que ficou de fora.** Os padrões que leem texto de PDF (certidão, NFS-e, folha) e o de número de ofício
   (`oficios.py`, que transforma "٣٠١" em "CT-301-…" corretamente) não foram mexidos: não validam formato digitado.
   O caso do pedido "٢٠٢٦-٠٨" já era recusado (o mês em árabe não casa `0[1-9]`); o furo real era "٢٠٢٦-08", usado nos
   testes.
8. **A-15 — envio de comprovante sem número.** `POST /api/protocolos/{id}/numero-orgao` aceitava só o comprovante (com
   número vazio, apagando o número). Agora exige o número; nenhuma tela manda comprovante hoje.

## Riscos

- **Medições de obra sem regra de espelho** ficam em `prevista` para sempre (não existe passagem de `prevista` para
  `nota_emitida`). Protocolá-las pela API agora exige justificativa. A tela não oferece esse protocolo para `prevista`
  (o botão "Registrar protocolo feito fora" só aparece depois de protocolada), então nada muda para quem usa a tela.
- **Tela de protocolo (`Protocolo.tsx`, campo "Nº do protocolo no órgão (opcional)")** deixa salvar em branco; antes
  apagava o número, agora mostra o erro do servidor. Não mexi no frontend (fora do pedido); se quiser, o botão pode ficar
  desabilitado com o campo vazio, como já é em Aguardando pagamento.
- **A-20 em produção:** conferido na cópia do banco (`dashboard-dev-ANTES-TESTES-20261010.db`) que nenhuma medição
  existente tem competência anterior ao início do contrato — a regra nova não trava nada que já está lá.

## Gate Sol: 6 achados, 5 corrigidos, 1 registrado (S5)

Mesma branch, mesma disciplina (teste falhando antes, depois a correção).

| Commit | Achado | O que mudou |
|---|---|---|
| 2611953 | S1 (média) — o A-15 quebrou "anexar só o comprovante" | Número vazio + comprovante, com número já gravado → mantém o número e salva só o comprovante (200). Vazio sem comprovante → "Informe o número do protocolo no órgão". Vazio + comprovante sem número gravado → "Informe o número do protocolo junto com o comprovante". As notas (sem comprovante) seguem exigindo o número sempre. Tela: o rótulo perde o "(opcional)" e ganha a ajuda "Obrigatório na primeira vez; depois dá para anexar só o comprovante." |
| 59e9560 | S2 (média) — o A-20 não cobria contrato sem data de início | Sem `execucao_inicio` nem `vigencia_inicio`: "Contrato sem data de início cadastrada: complete o cadastro antes de gerar espelho", na prévia e na geração. O contrato de teste com espelho (`_cad_com_espelho`) ganhou início em 11/03/2024. Na cópia do banco de produção, nenhum contrato está sem as duas datas. |
| 861815e | S3 (baixa) — a falta da nota ia em `certidoes_pendentes` | A ressalva traz `pendencias` (tudo, com a nota) e `certidoes_pendentes` só com as certidões (vazia quando só falta a nota). |
| c8c125e | S4 (baixa) — os testes do A-09 fabricavam o estado por SQL | Teste novo pelo caminho real: espelho gerado → protocolo recusado pela nota → nota anexada pela API (`nota_emitida`) → protocolo passa sem pendência. Passou de primeira (era falta de cobertura, não defeito); conferido que falha com a regra desligada. |
| 6deb03e | S6 (baixa) — certidão pendente aceitava justificativa de 1 caractere | Qualquer pendência assumida exige 10 caracteres: "Protocolar com pendência exige justificativa (ao menos 10 caracteres)". 3 chamadas de teste antigas com `"teste"` (5 caracteres) foram ajustadas. A tela do protocolo feito fora só libera o botão com 10 caracteres. |
| — | S5 (registrado) | id 0 ou negativo agora dá 422 em vez de 404; fica assim, anotado no backlog (a tela nunca manda 0). |

Saídas antes da correção: S1 `assert 422 == 200` (comprovante sozinho) e mensagem errada no caso (c); tela: "Unable to find a
label with the text of: Nº do protocolo no órgão". S2 `assert 200 == 422`. S3 `KeyError: 'pendencias'` (4 testes). S6
`assert 201 == 422` (certidão com "x"); envio pelo sistema: `assert (1 == 1 and 2 >= 10)` (a justificativa "ok" chegava
crua à marcação); tela: botão liberado com "  curta   ".

**Decisões do gate.**
- **S6 no envio pelo sistema.** Sem pendência na prévia a justificativa do envio é opcional e pode ser curta. Se uma
  certidão vencer entre a prévia e o envio, a marcação de protocolada (que vem depois do e-mail e não pode recusar)
  cairia pelo mínimo novo. Por isso, em `protocolo.enviar`, justificativa com menos de 10 caracteres é trocada pelo texto
  padrão ("Pendência surgida entre a prévia e o envio…") só na marcação; a auditoria do envio guarda a do usuário.
- **S6 na tela.** `MedicaoAtos.tsx` ganhou `MIN_JUSTIFICATIVA = 10` local, como `EnviarNota.tsx` e `FluxoOficio.tsx`.
- **S1, ponto em aberto.** A tela de protocolo (`Protocolo.tsx` › `NumeroOrgao`) não tem campo de comprovante; só a API
  aceita o arquivo. A ajuda "depois dá para anexar só o comprovante" descreve a regra do servidor, mas hoje nenhuma tela
  oferece o anexo.

Suítes no fim do gate: backend `920 passed, 1 skipped in 454.33s`; frontend `29 arquivos, 97 testes passaram`; `npm run typecheck` sem erro.
