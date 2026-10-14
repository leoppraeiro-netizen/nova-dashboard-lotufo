# 06 — Verificação adversarial pela API (fase 3, 10/10/2026, verificador A)

Instância própria na porta 8081 (`DASH_DEV=1`, `DASH_SEM_JOBS=1`, `DASH_SEM_FRONTEND=1`, banco e arquivos em
`backend/dados/verif/`, correio em `DASH_GRAPH_SIMULADOR=backend/dados/verif/correio-simulado`). Banco restaurado de
`dashboard-limpo.db` antes dos grupos que mudam estado (A-01/A-12/A-16/A-03; A-02 ×2; A-17/A-18 ×2). Cada item foi rodado
duas vezes. Scripts e saídas brutas em `docs/testes-2026-10-10/verificacao/api/` (`aNN.py`, `saida-aNN*.txt`,
`subir.sh`, `restaurar.sh`). Nenhum e-mail saiu do simulador: os 12 arquivos em `correio-simulado/enviados/` têm
remetente `teste.eng@lotufo.com` e todas as linhas de `envios` têm `mensagem_id = <simulado-N@dashboard>`; a instância
nunca teve `DASH_GRAPH_CLIENT_ID`.

Observação sobre severidade: o roteiro (05) não traz a severidade alegada por item e os relatórios 02–04 eram proibidos
para mim. A coluna "severidade final" abaixo é a minha proposta a partir da evidência (alta / média / baixa); quem
consolidar deve tomá-la como teto — nunca elevar acima do que foi alegado.

Achado colateral do ambiente de teste (importa para a parte B): o `CorreioSimulado` nomeia o arquivo pela contagem de
`.json` da pasta (`correio.py:185`). Com envios simultâneos, dois ou três envios calculam o mesmo número e **sobrescrevem
o mesmo arquivo** — em A-01 e A-02, 3 envios registrados renderam 2 e depois 1 arquivo. Contar arquivos do simulador
subestima envios concorrentes; a tabela `envios` é a prova confiável. O critério de B-05 ("um arquivo no simulador")
pode dar falso "protegido" por esse motivo.

## Tabela

| ID | Veredito | Severidade final | Evidência curta |
|---|---|---|---|
| A-01 | CONFIRMADO | alta | 3 POST simultâneos em `/api/espelhos/9/enviar` → 3× `200` (`envio_id` 20, 21, 22), `envios` +3, `envio_medicoes` 3 linhas para a medição 641; simulador +2 (colisão de nome). Rodada 2 (espelho 10): 3× 200, +3 envios, simulador +1 |
| A-02 | CONFIRMADO | alta | 3 POST simultâneos em `/api/notas/envio/3/enviar` → 3× `200` (envio_id 20–22), `envios` tipo=protocolo +3, `medicao_protocolos` da 631: 0 → 3, protocolo 3 `enviado` com `envio_id=22`. Idêntico na rodada 2 (3 envios com o MESMO `mensagem_id <simulado-12@dashboard>`) |
| A-03 | CONFIRMADO | média | Com `BEGIN IMMEDIATE` segurado 8 s: `POST /api/espelhos/11/enviar` → `503` após 5,6 s, `Retry-After: 1`, "Banco de dados ocupado — tente novamente"; simulador +1 (`6.json`, para `destino@exemplo.com`), `envios` +0, espelho `envio_id=None`, medição 643 segue `espelho_gerado`. Rodada 2 igual (espelho 12) |
| A-04 | CONFIRMADO | baixa | `PUT /api/medicoes/631/valor` sem cookie: 1 KB → 401 em 4 ms; 100 MB → 401 em 1,39 s (×334); 10 MB → 401 em 0,63 s (×26). Com cookie, os mesmos 100 MB deram 200 em 0,48 s |
| A-05 | CONFIRMADO | baixa (rebaixada: o bloqueio expira sozinho em 15 min) | 5 senhas erradas → `bloqueado_ate` gravado, `tentativas_falhas` volta a 0; a senha certa recebe 401. Nenhuma rota, tela ou comando de `cli.py` mexe em `bloqueado_ate` (`grep` só acha `auth.py`). Destravado por SQL no banco da 8081 |
| A-06 | CONFIRMADO | média | 10 logins errados em paralelo → 10× 401 mas `tentativas_falhas = 1` (não 10) e sem bloqueio; a senha certa em seguida **entrou** (200). Idêntico na rodada 2 |
| A-07 | CONFIRMADO | baixa | `GET /api/medicoes/9223372036854775808` e `GET /api/contratos/99999999999999999999` → `500 Internal Server Error`; log: `OverflowError: Python int too large to convert to SQLite INTEGER`. Controle: 2^63−1 → 404; espelhos/protocolos com o mesmo id → 404 |
| A-08 | CONFIRMADO | baixa | `POST /api/medicoes/640/notas/manual` com valor `99999999999999999999,00` → `500` (OverflowError no INSERT). Controle `9999999999999999,00` (cabe em int64) → 200 |
| A-09 | CONFIRMADO | média | Engenharia, `POST /api/medicoes/591/protocolo` com só data e ofício → `201 {"id":635,"ressalva":null}`; 591 saiu de `prevista` para `protocolada` sem nota nem envio, sem pedir justificativa. Rodada 2 com a 592 (reajuste, `prevista`) → 201, `protocolada` |
| A-10 | CONFIRMADO | baixa | Login com e-mail `minha frase secreta 123 rodada1` → 401; `GET /api/admin/auditoria` (admin) mostra `auth.login_falha` com `depois = {"email": "minha frase secreta 123 rodada1"}` — texto inteiro, na cadeia append-only |
| A-11 | CONFIRMADO | baixa | `POST /api/notas/envio-externo` (medição 632, `eml` = PNG de 4 px chamado `imagem.eml`) → `200 {"ok":true}`; 632 virou `protocolada` (`envio_origem=externo`); arquivo `evidencias/9a7f…eml` começa com `\x89PNG`. Rodada 2 com a 638: igual |
| A-12 | CONFIRMADO | baixa | `POST /api/espelhos/10/enviar` para `qualquer1@exemplo.com` com `cco ["oculto1@exemplo.com"]` → 200; `4.json` traz `para=[qualquer1@…]`, `cco=[oculto1@…]`; `envios.cco` gravado. Rodada 2 igual |
| A-13 | CONFIRMADO | média | `POST /api/protocolos/3/links {url: https://exemplo-malicioso.test/x1}` → 200; `GET /api/notas/envio/3` → corpo da prévia: "Arquivos por link (OneDrive):\nPlanilha: https://exemplo-malicioso.test/x1". Rodada 2 acrescenta `/x2` |
| A-14 | CONFIRMADO | baixa | `PUT /api/medicoes/591/valor {campo: atestado, valor: "١٢٣,٤٥"}` → 200; `valor_atestado_centavos = 12345`, origem `manual`. 2×. |
| A-15 | CONFIRMADO | baixa | `POST /api/notas/635/numero-orgao {numero:"X-1"}` → 200 e `protocolos.numero_orgao = X-1`; `{numero:""}` → 200 e volta a `NULL` (`sem_numero_orgao: true`), sem erro nem confirmação. 2× |
| A-16 | CONFIRMADO | média | `PUT /api/medicoes/631/valor {protocolado, "1,00"}` em `nota_emitida` → 200; valor 938.483.418 → 100 (origem `espelho` → `manual`); `/notas` segue `faltam 0`, `conferencia []` (confere); `/api/inicio` continua com 49 avisos (nenhum novo); diretoria `nota_esperando_protocolo` cai de R$ 10.223.826,78 para R$ 838.993,60. Só a auditoria registra. 2× |
| A-17 | CONFIRMADO | média | `POST /api/notas/envio/3/enviar` com `cco: ["oculto@exemplo.com"]` → 200; `10.json` com `cco: []`; `envios.cco = NULL`. 2× (restaurando) |
| A-18 | CONFIRMADO | média | Mesmo envio do protocolo 3 (só a 631): `pendencias = ["7ª Medição: nota fiscal não anexada"]`, nada sobre a 632; detalhe e e-mail não citam reajuste; 631 → `protocolada`, 632 segue `nota_emitida` e aparece sozinha em `/api/notas/a-enviar` (`c20:m632`). 2× |
| A-19 | CONFIRMADO | média | PDF de uma página em branco: `/certidoes/ler` → `{ok:false, motivo:"sem-texto", digitavel:true}`; `/certidoes` com Lotufo, municipal, emissão 2026-10-01, validade 2099-12-31 → `201 {"id":55, leitura:"manual"}`; `/api/documentos` mostra municipal Lotufo `situacao: ok`, `dias: 26745`, `certidao.id 55` no lugar da nº 39 (válida até 17/10/2026). Rodada 2 → id 56, igual |
| A-20 | CONFIRMADO | baixa | `POST /api/contratos/5/espelho/previa {33, "2020-01", medicao "100,00"}` → 200 com `periodo "01/01/2020 A 31/01/2020"`, `avisos: []`; o cadastro do MT-401 tem `vigencia_inicio = 2023-03-01`. 2× |
| A-21 | CONFIRMADO (com ressalva) | baixa | `/api/medicoes/resumo` → 21 obras (contratos `ativo`); `/api/inicio/painel` → `obras_ativas: 19` (`ativo` e sem encerramento iniciado); `/api/diretoria.obras` (farol) → 22 linhas (tudo que não é `rescindido`, inclui 1 `suspenso`). Banco: 21 ativo + 1 suspenso; 19 ativos sem encerramento. Se os três têm o MESMO rótulo na tela é da parte B |

Contagem: **21 CONFIRMADO, 0 NÃO CONFIRMADO, 0 INCONCLUSIVO.**

## Item a item

**A-01.** Gerei o espelho nº 33 do MT-401 (`POST /api/contratos/5/espelho`, competência 2026-10, R$ 100,00 → `espelho_id 9`),
peguei a prévia (`GET /api/espelhos/9/envio`) e disparei 3 `POST /api/espelhos/9/enviar` em threads com o mesmo corpo.
As três voltaram `200` com `envio_id` 20, 21 e 22; a tabela `envios` (tipo `espelho`) foi de 5 para 8 e `envio_medicoes`
tem três linhas para a medição 641. O simulador ganhou só 2 arquivos (`1.json`, `2.json`) porque dois envios calcularam o
mesmo nome — colisão do próprio simulador, não do produto. Rodada 2 (nº 34, espelho 10): 3× 200, +3 envios, +1 arquivo.
Explicação inocente procurada: "a segunda e a terceira seriam recusadas por já enviado" — não há essa recusa; o código
permite reenviar (aviso "este envio substitui") e as checagens ficam fora da transação. Confirmado.

**A-02.** Banco restaurado. `GET /api/notas/envio/3` traz `pendencias: ["7ª Medição: nota fiscal não anexada"]` (exige
justificativa ≥10). Três `POST /api/notas/envio/3/enviar` simultâneos com a prévia + justificativa: 3× `200`
(`envio_id` 20–22), `envios` tipo `protocolo` +3, `medicao_protocolos` da 631 de 0 para 3 (ids 635–637, todas
`protocolo_id=3`), protocolo 3 `enviado` com `envio_id=22` (o último a gravar). Na rodada 2 as três linhas de `envios`
têm o mesmo `mensagem_id <simulado-12@dashboard>` e só 1 arquivo novo — de novo a colisão do simulador. Confirmado: o
órgão receberia três e-mails iguais.

**A-03.** Banco restaurado antes do grupo; logado antes do lock (o login grava). Gerei o espelho nº 35 (id 11); uma
thread abriu outra conexão SQLite, fez `BEGIN IMMEDIATE` + UPDATE e dormiu 8 s; nesse meio-tempo
`POST /api/espelhos/11/enviar` (para `destino@exemplo.com`). Resposta após 5,6 s (busy_timeout 5 s): `503`,
`Retry-After: 1`, "Banco de dados ocupado — tente novamente em instantes." O simulador ganhou `6.json`, `envios` não
ganhou linha, `espelhos.envio_id` ficou `NULL` e a medição 643 continua `espelho_gerado` — quem repetir manda o segundo
e-mail. Rodada 2 (nº 36, id 12) idêntica. A mensagem do 503 afirma "nada foi gravado", o que é verdade, mas o e-mail já
saiu. Confirmado; média porque exige lock >5 s, que é raro, mas o efeito é duplicata sem rastro do primeiro.

**A-04.** `PUT /api/medicoes/631/valor` sem cookie com JSON de 1 KB: 401 em 4–8 ms (3 medições). Com 100 MB
(`{"campo":…,"x":"AAAA…"}`, enviado uma única vez sem cookie): 401 em 1,39 s (×334). Controle com cookie e os mesmos
100 MB: 200 em 0,48 s — isto é, o servidor gasta o mesmo trabalho de leitura esteja ou não autenticado; o 401 só vem
depois do corpo inteiro. Rodada 2 com 10 MB (para não repetir o corpo grande): 401 em 0,63 s (×26). Confirmado; baixa
(rede interna, sem crash, uvicorn leu 100 MB em ~1 s).

**A-05.** Conta de teste da diretoria (id 7). Cinco `POST /api/auth/login` errados em série: 5× 401, banco com
`tentativas_falhas 0` e `bloqueado_ate` 15 min à frente; a senha certa em seguida → 401. Procurei desbloqueio:
`grep bloqueado_ate|desbloque` no backend só acha `auth.py`; `cli.py` não tem comando; a tela de usuários só ativa /
desativa (e desativar/reativar não mexe em `bloqueado_ate`). Destranquei por SQL no banco da minha instância. Confirmado
quanto ao fato; rebaixei a severidade porque o bloqueio é temporário (15 min) — a alegação "não há como destrancar" vale
só dentro da janela.

**A-06.** Mesma conta destrancada: 10 logins errados em paralelo (10 threads). Todos 401, mas `tentativas_falhas = 1`
(cada thread leu 0 e gravou 1; o `UPDATE` grava valor absoluto, não `+1`). A senha certa logo depois: `200` — entrou.
Rodada 2 idêntica. Confirmado: o limite de 5 não segura tentativas concorrentes.

**A-07.** `GET /api/medicoes/9223372036854775808` e `GET /api/contratos/99999999999999999999` → `500 Internal Server
Error` nas duas rodadas; log da 8081 com `OverflowError: Python int too large to convert to SQLite INTEGER`. Controles:
`…807` (2^63−1) → 404 nas duas rotas; `/api/espelhos/9223372036854775808` e `/api/protocolos/99999999999999999999` → 404
(rotas que limitam o id). Confirmado; baixa (sem efeito colateral, exige sessão).

**A-08.** `POST /api/medicoes/640/notas/manual` (documento nfs 210 da 640) com `valor "99999999999999999999,00"` →
`500` nas duas rodadas. Controle: `"9999999999999999,00"` (999.999.999.999.999.900 centavos, cabe em int64) → 200
(`nota_id 2165`, "divergente"). Meu primeiro controle com 17 dígitos também deu 500 — porque ×100 já passa de 2^63;
corrigi para 16. Confirmado: falta teto; deveria ser 422.

**A-09.** Como engenharia, `POST /api/medicoes/591/protocolo {"data":"2026-10-10","numero_oficio":"OF-A09"}` →
`201 {"id":635,"ressalva":null}` já na primeira tentativa (não havia certidão pendente, então nem justificativa foi
pedida); a 591 passou de `prevista` para `protocolada`. Rodada 2 com a 592 (reajuste 12, `prevista`) → 201,
`protocolada`. A rota é a de "protocolo feito fora" e o inventário já diz que o servidor aceita desde `prevista`
(`medicoes.py:184-187`); a tela só mostra o botão depois da etapa 4. Confirmado; média (pula nota e envio pela API).

**A-10.** `POST /api/auth/login {"email":"minha frase secreta 123 rodada1","senha":…}` → 401. Como admin,
`GET /api/admin/auditoria?limite=20` devolve o evento `auth.login_falha` com `depois = {"email": "minha frase secreta
123 rodada1"}`, inteiro. É comportamento desenhado (o código grava o e-mail de propósito e nunca a senha), mas quem
digitar a senha no campo errado a deixa na cadeia append-only legível por admin. Confirmado; baixa.

**A-11.** PNG válido de 4×1 px enviado como `eml` chamado `imagem.eml` (`message/rfc822`) em
`POST /api/notas/envio-externo` com a 632 (`nota_emitida`), `enviado_em 2026-10-09`, observação preenchida → `200`.
A 632 virou `protocolada` com `envio_origem=externo`; o arquivo em `evidencias/<sha>.eml` começa com `\x89PNG`.
Rodada 2 com a 638: igual. Confirmado; baixa (evidência inútil, mas só quem tem `editar_cadastros` grava).

**A-12.** `POST /api/espelhos/10/enviar` com `para ["qualquer1@exemplo.com"]`, `copia []`, `cco ["oculto1@exemplo.com"]`
→ 200; `4.json` do simulador traz exatamente esses dois e `envios.cco = ["oculto1@exemplo.com"]`. Rodada 2 com
`qualquer2`/`oculto2`: igual. A regra do servidor é só "contém @". Confirmado; baixa (é um envio deliberado por usuário
autenticado; o risco é erro de digitação, não ataque).

**A-13.** `POST /api/protocolos/3/links {"nome":"Planilha","url":"https://exemplo-malicioso.test/x1"}` → 200 (nenhuma
restrição de domínio). `GET /api/notas/envio/3` → `previa.corpo` com "Arquivos por link (OneDrive):\nPlanilha:
https://exemplo-malicioso.test/x1"; na rodada 2 as duas URLs. É o texto que vira `<a href>` no e-mail oficial ao órgão.
Confirmado; média.

**A-14.** `PUT /api/medicoes/591/valor {"campo":"atestado","valor":"١٢٣,٤٥","data":"2026-10-01"}` → 200;
`GET /api/medicoes/591` → `valor_atestado_centavos 12345`, origem `manual`. Rodada 2 (data 02/10) igual. Confirmado;
baixa (o valor gravado é o correto; só mostra que a validação é mais frouxa do que o formato pt-BR anunciado).

**A-15.** Medição 635 (MTPAR, protocolada pelo sistema, protocolo 6). `POST /api/notas/635/numero-orgao {"numero":"X-1"}`
→ 200 e `protocolos.numero_orgao = X-1` (`aguardando-pagamento` mostra `X-1`); `{"numero":""}` → 200 e `NULL`
(`sem_numero_orgao: true`). Nenhum erro, nenhuma confirmação. 2×. Confirmado; baixa (desenho documentado: "vazio apaga").

**A-16.** Fotografia antes/depois de `PUT /api/medicoes/631/valor {"campo":"protocolado","valor":"1,00"}` (631 em
`nota_emitida`, nascida do espelho, `congelada 0`): 200; valor 938.483.418 → 100, origem `espelho` → `manual`;
`GET /api/medicoes/631/notas` continua `faltam 0`, `esperadas` com os valores do espelho (706.759.117 e 231.724.301) e
`conferencia []` nas duas notas do RM (nada aponta a divergência de R$ 9,38 mi); `/api/inicio` segue com os mesmos 49
avisos; `/api/diretoria.dinheiro.nota_esperando_protocolo` cai de R$ 10.223.826,78 para R$ 838.993,60 (mesma
quantidade 4). Só o `audit_log` registra `medicao.valor_protocolado` antes/depois. Rodada 2 (`2,00`) idêntica. Confirmado;
média.

**A-17.** Banco restaurado. `POST /api/notas/envio/3/enviar` com `cco: ["oculto@exemplo.com"]` no corpo (mais
`para ["orgao@exemplo.com"]` e justificativa) → 200; `10.json` do simulador com `cco: []`; `envios.cco = NULL`. O modelo
`EnviarIn` não tem `cco` e o pydantic ignora o campo em silêncio. Rodada 2 (restaurado) igual. Confirmado; média.

**A-18.** Mesmo envio da A-17. Antes: `GET /api/notas/envio/3` só tem a pendência da nota; nem o detalhe nem a prévia
citam "632" ou "reajuste"; `/api/notas/a-enviar` já listava 631 (`c20:m631`) e 632 (`c20:m632`) como envios separados
para a SINFRA. Depois do 200: 631 `protocolada`, 632 segue `nota_emitida` e continua sozinha em `a-enviar`; avisos da
obra inalterados; a auditoria do envio lista só `sem_nota`. Nada avisa que a regra do órgão junta medição e reajuste.
2×. Confirmado; média.

**A-19.** PDF mínimo de uma página em branco (sem fluxo de conteúdo). `POST /api/documentos/certidoes/ler` →
`{"ok":false,"motivo":"sem-texto",…,"digitavel":true}` (OCR não achou texto). `POST /api/documentos/certidoes` com
`entidade_id 1` (Lotufo), `tipo municipal`, `emissao 2026-10-01`, `validade 2099-12-31`, `natureza negativa` → `201
{"id":55,"leitura":"manual","ocr":false,…,"validade":"2099-12-31"}`. `GET /api/documentos` passa a mostrar a municipal da
Lotufo como `situacao: ok`, `dias: 26745`, apontando a certidão 55 — a nº 39 (válida até 17/10/2026) deixa de ser a
exibida. Rodada 2 (emissão 02/10) → id 56, mesmo efeito. Confirmado; média (exige engenharia logada e fica auditado,
mas destrava checklist e envio).

**A-20.** `POST /api/contratos/5/espelho/previa {"numero":33,"competencia":"2020-01","entradas":{"medicao":"100,00"}}`
→ 200, `periodo "01/01/2020 A 31/01/2020"`, `avisos []`, nome do arquivo "ESPELHO - MT-401 - 33ª Medição (01.2020)".
`GET /api/contratos/5` → `vigencia_inicio 2023-03-01`, `execucao_inicio 2023-03-01`. 2×. Confirmado; baixa.

**A-21.** Três leituras no mesmo instante: `/api/medicoes/resumo.obras` tem 21 itens (filtro `estado='ativo'`,
`medicoes.py:449`); `/api/inicio/painel.protocoladas.obras_ativas = 19` (`ativo` e `encerramento_iniciado_em IS NULL`,
`avisos.py:42-46`); `/api/diretoria.obras` (farol) tem 22 linhas (`qdop.linhas`, `estado <> 'rescindido'`, inclui o
contrato suspenso). Banco: 21 `ativo`, 1 `suspenso`, 19 ativos sem encerramento, 22 não rescindidos. Cada número está
certo para a sua própria definição; o que a alegação diz é que a tela chama os três de "obras ativas" — isso a API não
prova, fica para a parte B. Confirmado com ressalva; baixa.
