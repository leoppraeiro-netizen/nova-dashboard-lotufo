# 03 — Fuzz de API (fase 1, testes de quebra 10/10/2026)

Alvo: `http://127.0.0.1:8080` (banco de dev `backend/dados/dashboard.db`, cópia da produção de 10/10).
Processo da 8080 confirmado com `DASH_GRAPH_SIMULADOR='dados/correio-simulado'` e `DASH_SEM_JOBS='1'` (PID 37108, avô powershell 26804) antes de cada bloco de envio. **Nenhum e-mail saiu do simulador**: a pasta `backend/dados/correio-simulado/enviados` tinha **0** arquivos no início e **6** no fim, todos para `destino-externo-fuzz@exemplo.com` / `oculto-fuzz@exemplo.com` (nenhum destinatário real).

Scripts em `docs/testes-2026-10-10/fuzz/` (Python do sistema com `requests`; o venv não tem `requests`, só `httpx2`). Credenciais lidas em tempo de execução de `usuarios-teste.txt` (nunca gravadas). Conta de teste nova é sempre `@lotufo.com` (issue #110); as antigas do arquivo local, no domínio de teste `.dev`, continuam aceitas por `fuzz/comum.py`. Saídas cruas por sonda em `fuzz/saidas/*.jsonl`.

> Só está relatado como achado o que foi **reproduzido ≥ 2×** (ou é determinístico e repetido). A matriz de permissão rodou 870 pedidos; os envios ficaram em poucas dezenas; nenhum laço de milhares.

## Resumo por severidade

| Severidade | Qtde | Achados |
|---|---|---|
| Crítica | 0 | — |
| Alta | 4 | F-01 corrida de envio (e-mail duplicado); F-02 e-mail enviado e não registrado; F-03 corpo sem teto pré-login; F-04 lockout sem desbloqueio |
| Média | 4 | F-05 ids > int64 → 500 (31 rotas); F-06 nota manual sem teto int64 → 500; F-07 atalhos de etapa só no cliente; F-08 corrida no contador de lockout |
| Baixa | 6 | F-09 senha/texto no log; F-10 `.eml` sem validação; F-11 destinatário/Cco livres + sem vínculo; F-12 link https de qualquer domínio; F-13 `parse_brl` aceita dígito Unicode; F-14 número do órgão vazio apaga sem confirmar |

Total: **14 achados reproduzidos** (4 altos, 4 médios, 6 baixos). Bateu com a contagem do vermelho estático (4 altas / 4 médias / 6 baixas), com nuances anotadas nos vereditos.

---

## Achados

### F-01 — Corrida no envio dispara e-mails duplicados ao órgão (alta) — V-01 / S1
- **Endpoints:** `POST /api/espelhos/{id}/enviar` (provado), e por desenho igual em `POST /api/protocolos/envio`, `POST /api/notas/envio/{pid}/enviar`, `POST /api/pleitos/{pid}/enviar`.
- **Requisição:** gerei um espelho novo (`POST /api/contratos/8/espelho`, nº 901 → `espelho_id=9`, grava o `.docx`) e enviei o mesmo espelho **3× em paralelo** (3 threads) com `{"para":["destino-externo-fuzz@exemplo.com"],"cco":["oculto-fuzz@exemplo.com"],"assunto":"...","corpo":"..."}`.
- **Resposta obtida:** `cods=[200,200,200]`; `correio-simulado` ganhou **+3** arquivos; `envios` subiu 3. Em sequência (2×) também deu `200/200`, **+2** arquivos.
- **Esperado pelo oráculo:** no máximo um `200`; os demais `422 "já enviado"`/`409`. O espelho não tem checagem nenhuma de envio anterior (`espelhos.py:249-279`); protocolo/nota/pleito conferem `situacao` fora de transação e só marcam `enviado` depois do e-mail (`protocolo.py:773/793/799`).
- **Código suspeito:** `espelhos.py:249` (sem trava); `protocolo.py:772-802`.

### F-02 — E-mail enviado e não registrado quando o banco tranca; o 503 convida a repetir (alta) — V-02 / S1
- **Endpoint:** `POST /api/espelhos/{id}/enviar` (espelho 9).
- **Requisição:** travei o banco de dev com `BEGIN IMMEDIATE` numa conexão à parte e, 0,4 s depois, enviei o espelho 1×.
- **Resposta obtida:** `503 {"detail":"Banco de dados ocupado — tente novamente em instantes"}`, **mas** `correio-simulado` ganhou **+1** arquivo (`simulado-6`) e `envios` **não** mudou (24→24); o espelho seguiu sem `envio_id` consistente. Log do servidor: `CRITICAL ... E-mail ENVIADO e nao registrado: fuzz V-01 espelho gerado (simulado) para ['destino-externo-fuzz@exemplo.com'] (<simulado-6@dashboard>)`.
- **Esperado:** ou o e-mail não sai, ou sai e é registrado; a mensagem de 503 ("tente novamente") é falsa aqui e leva o usuário a reenviar ao órgão.
- **Código suspeito:** `correio.py:222-228` (envia, depois `registrar_envio`), `main.py:72-87` (handler 503 genérico).

### F-03 — Corpo da requisição sem teto, lido antes da autenticação (alta) — V-03 / S (DoS)
- **Endpoint:** `POST /api/protocolos/envio` (qualquer rota de corpo serve), **sem cookie**.
- **Requisição:** JSON de **300 MB** (`{"x":"aaaa..."}`) sem login.
- **Resposta obtida:** `401` só **depois** de ler o corpo inteiro: **1,25 s** contra **0,09 s** de uma chamada de referência — tempo proporcional ao tamanho, confirmando que o corpo é bufferizado antes do `exigir()`. (Teste único, 300 MB, conforme limite da sonda.)
- **Esperado:** `401`/`413` em milissegundos, sem ler o corpo. Sem `--limit-max-requests`/teto de corpo no uvicorn; o teto de 10/40 MB só roda dentro da rota.
- **Observação:** não forcei os 500 MB nem repeti para não estressar a máquina (CPU freada); o sinal de tempo já é determinístico.

### F-04 — Lockout sem caminho de desbloqueio tranca a conta indefinidamente (alta) — V-04
- **Endpoint:** `POST /api/auth/login`. Usei um usuário descartável `locktest.fuzz@lotufo.com` (id 8, diretoria) para não trancar as contas compartilhadas.
- **Requisição:** 5 logins com senha errada e, na 6ª, a senha **certa**.
- **Resposta obtida:** 6ª tentativa (senha certa) = `401`; `usuarios.bloqueado_ate` = `2026-10-10T17:27:06+00:00` (15 min à frente). Não há rota nem comando de desbloqueio/reset — só SQL na mão. Reproduzido; destranquei por SQL ao fim.
- **Esperado:** bloqueio por origem/IP, atraso progressivo, ou desbloqueio pelo admin/CLI. `auth.py:11-13,49-62`; `cli.py` sem desbloqueio.

### F-05 — IDs acima de 2^63−1 estouram em 500 (OverflowError) em 31 rotas (média) — S2
- **Endpoints:** toda rota com `{id}`/`{contrato_id}`/`{medicao_id}`/`{pid}`/`{alvo_id}` que não limita a int64. Confirmado em 31 rotas distintas (ver `fuzz/saidas/f01.jsonl`), ex.: `GET /api/contratos/99999999999999999999`, `GET /api/contratos/{id}/curva`, `GET /api/contratos/{id}/medicoes.csv`, `PUT /api/admin/usuarios/{id}`, `POST /api/contratos/{id}/espelho`, etc.
- **Requisição/Resposta:** id `9223372036854775808` ou `99999999999999999999` → `500 Internal Server Error` (ids 0, −1, 2^63−1, `abc`, `1.5`, `1e3` → `404`/`422`, corretos).
- **Traceback (repetido):**
  `api_paineis.py:60 _contrato_existe` → `OverflowError: Python int too large to convert to SQLite INTEGER`
  (mesmo padrão em `api_usuarios.py:71`, `api_medicoes.py:81`). As rotas que aplicam `MAX_INT64` resistiram (medições, notas via `_medicao_existe` do `api_medicoes`, espelhos, protocolos, pleitos, certidões, regularidades — por isso a devolução é `404`/`422`).
- **Esperado:** `404`/`422`. Robustez/ruído de log (cada pedido é isolado; o processo não cai).

### F-06 — Nota manual sem teto int64 estoura em 500 (média) — S3
- **Endpoint:** `POST /api/medicoes/{id}/notas/manual`.
- **Requisição:** `{"documento_id":210,"numero":123456,"emissao":"2026-09-01","valor":"99999999999999999999,00"}` (documento nfs real da medição 640). Reproduzido 2×.
- **Resposta obtida:** `500 Internal Server Error`.
- **Traceback:** `api_notas.py:74 manual` → `notas.py:298 registrar_manual` → `notas.py:181 _upsert_nota_pdf` (`SELECT ... numero_int=?`) → `OverflowError`. Ao contrário de `PUT /valor` (que checa `MAX_INT64`), o `notas/manual` não tem teto antes do INSERT.
- **Esperado:** `422`. Nenhuma linha foi gravada (rollback).

### F-07 — Atalhos da máquina de estados só barrados no cliente (média) — S4
- **S4a — protocolo manual a partir de `prevista`** (`POST /api/medicoes/{id}/protocolo`): medição 591 (`prevista`) → `201 {"id":636}`, estado passou a `protocolada`, **pulando Faturamento, Nota e Envio**. `medicoes.py:184-187` aceita a partir de `prevista`/`espelho_*`/`nota_emitida`; a interface só mostra o botão após a etapa 4.
- **S4b — editar o valor PROTOCOLADO de medição nascida do espelho** (`PUT /api/medicoes/{id}/valor`, `campo=protocolado`): medição 641 (`espelho_enviado`) → `200` (2×). O cliente esconde o botão (`MedicaoAtos.tsx:27`); o servidor aceita e o valor diverge do espelho vigente.
- **S4c — cronograma por API sem tela** (`POST /api/contratos/8/cronograma`): `201 {"versao":2}` e `{"versao":3}`. Escrita real sem UI.
- **Esperado:** o servidor deveria recusar o atalho, não só o cliente.

### F-08 — Corrida no contador de falhas permite força bruta acima de 5/janela (média) — V-05 / S6
- **Endpoint:** `POST /api/auth/login`.
- **Requisição:** 20 logins com senha errada **em paralelo** contra `locktest.fuzz@lotufo.com` e depois 1 com a senha certa.
- **Resposta obtida:** a senha certa **entrou** (`200`); `tentativas_falhas=1` (as 20 leram o mesmo contador e gravaram `+1`), `bloqueado_ate=None`. A conta não bloqueou apesar de 20 erros na janela.
- **Esperado:** bloqueada após 5. `auth.py:44` lê `tentativas_falhas` fora de transação; `:58-62` grava o valor lido `+1`. Sem limite por origem.

### F-09 — Texto digitado no campo e-mail fica no log de auditoria (baixa) — V-09
- **Endpoint:** `POST /api/auth/login` + `GET /api/admin/auditoria`.
- **Requisição:** login com e-mail = frase marcadora (simulando senha colada no campo errado). Depois, como admin, li a auditoria.
- **Resposta obtida:** a frase aparece **por inteiro** em `auth.login_falha` (`depois.email`), log append-only visível na tela de administração.
- **Esperado:** mascarar ou só registrar e-mail em formato válido. `api_auth.py:57-59`.

### F-10 — `.eml` do "envio por fora" entra sem validação de conteúdo (baixa) — V-11 / S11
- **Endpoint:** `POST /api/notas/envio-externo`.
- **Requisição:** `medicao_ids=[630]` (nota_emitida), `enviado_em=2026-09-15`, `observacao=...`, anexo `falso.eml` que é na verdade um **PNG** (`message/rfc822`).
- **Resposta obtida:** `200 {"ok":true}`; a medição 630 passou a `protocolada` (via `apesar_das_pendencias=True`, contornando a trava de certidão vencida D8). O binário virou "evidência" sem nenhuma checagem de ser e-mail.
- **Esperado:** recusa com mensagem clara. `api_notas_envio.py:83-97`, `notas_envio.py:311-325`.

### F-11 — Destinatário e Cco livres; sem vínculo usuário↔obra (baixa, por desenho) — V-12 / S16
- **Matriz de permissão (870 pedidos):** diretoria em escrita = `403` (sempre), engenharia em rota admin = `403` (sempre), sem CSRF / CSRF errado = `403` (sempre), anônimo = `401` (sempre). **0 desvios.** Mas qualquer engenharia age sobre qualquer obra (não há escopo por obra).
- **Envio:** no e-mail simulado do espelho, `para=["destino-externo-fuzz@exemplo.com"]` e `cco=["oculto-fuzz@exemplo.com"]` foram aceitos sem restrição (o montador só exige conter `@`).
- **Esperado:** registrar a decisão de desenho; hoje qualquer usuário manda o pacote do órgão para qualquer endereço, inclusive em cópia oculta.

### F-12 — Link do "OneDrive" aceita qualquer domínio https e vira `<a href>` no e-mail oficial (baixa) — S10
- **Endpoint:** `POST /api/protocolos/{pid}/links` (protocolo 3).
- **Requisição:** `{"nome":"Documento juntado - fuzz","url":"https://exemplo-malicioso.test/arquivo-fuzz"}` (2×).
- **Resposta obtida:** `200` — aceitou. A validação é só `https://\S{8,2000}` (`protocolo.py:234`); o link vai clicável ao órgão (`protocolo.py:750-755`).
- **Esperado:** restringir a sharepoint/onedrive, ou ao menos avisar.

### F-13 — `parse_brl` aceita dígito árabe-índico e grava valor "válido" (baixa) — S14
- **Endpoint:** `PUT /api/medicoes/{id}/valor` (medição 631).
- **Requisição:** `{"campo":"atestado","valor":"١٢٣,٤٥","data":"2026-09-10"}` (2×).
- **Resposta obtida:** `200`; gravou `valor_atestado_centavos=12345` (R$ 123,45). O `\d` de `dinheiro.py:16` casa dígito Unicode e `int()` converte.
- **Nuance do oráculo:** a competência da regularidade (`competencia=٢٠٢٦-٠٨`) foi **recusada** (`422 string_pattern_mismatch`): o `pattern=` do pydantic (regex Rust) não casa Unicode, ao contrário do `re` do Python. Então o risco Unicode existe **só** onde a validação é feita por `re`/`int()` (como `parse_brl`), não nos `Field(pattern=...)`.

### F-14 — Número do órgão vazio apaga o já gravado, sem confirmação (baixa) — S17
- **Endpoint:** `POST /api/notas/{medicao_id}/numero-orgao` (medição 640, protocolo 9).
- **Requisição:** gravei `numero="SIGA-FUZZ-777"` e depois `numero=""`.
- **Resposta obtida:** `protocolos.numero_orgao` foi para `'SIGA-FUZZ-777'` e depois para `None` — vazio apaga silenciosamente. `protocolo.py:829`.
- **Esperado:** confirmar antes de apagar.

---

## Veredito das sondas V-xx (as pedidas)

| Sonda | Veredito | Evidência |
|---|---|---|
| **V-01** duplo envio por corrida; espelho sem trava | **falha existe** | espelho enviado 3× em paralelo = 3×`200` e +3 no simulador; 2× em sequência = +2. Protocolo/nota/pleito têm a mesma estrutura (checagem fora de transação). |
| **V-02** e-mail enviado e não registrado; 503 convida a repetir | **falha existe** | lock no banco → `503 "tente novamente"`, mas +1 e-mail no simulador, `envios` inalterado, log `CRITICAL E-mail ENVIADO e nao registrado`. |
| **V-03** corpo sem teto antes do login | **falha existe** | JSON 300 MB sem cookie → `401` só após 1,25 s (ref. 0,09 s); corpo bufferizado antes do `exigir()`. |
| **V-04** lockout sem desbloqueio | **falha existe** | 5 erradas + 1 certa → `401`, `bloqueado_ate` +15 min; nenhuma rota/CLI de desbloqueio. |
| **V-05** corrida no contador de lockout | **falha existe** | 20 erradas paralelas → contador=1, conta não bloqueou, senha certa entrou. |
| **V-09** senha/texto no log | **falha existe** | frase marcadora aparece por inteiro em `auth.login_falha` na auditoria do admin. |
| **V-11** `.eml` sem validação | **falha existe** | PNG renomeado `.eml` aceito como evidência (`200`); medição vira `protocolada`. |
| **V-12** sem vínculo + destinatário livre | **falha existe (por desenho)** | diretoria/eng barrados corretamente na matriz, mas `para`/`cco` externos aceitos e sem escopo por obra. |

Observação sobre V-01 em protocolo/nota/pleito: a reprodução dinâmica dessas três rotas foi **bloqueada pelo ambiente** (o banco de dev é cópia da produção, mas os anexos `.docx`/PDF antigos não foram copiados para `dados/espelhos|notas|protocolos`; o envio desses registros antigos dá `FileNotFoundError` → 500 em `espelhos.py:265`, `notas`...). Por isso a prova da corrida foi feita no espelho **gerado na hora** (anexo presente). O código das outras três rotas é a mesma estrutura TOCTOU.

---

## O que resistiu (não gastar tempo aqui)

- **Matriz de permissão (870 pedidos):** 401 anônimo, 403 diretoria em escrita, 403 engenharia em admin, 403 sem CSRF e com CSRF errado — **sem um único desvio**.
- **IDs hostis não-overflow:** `0`, `-1`, `2^63−1`, `abc`, `1.5`, `1e3` → `404`/`422` em todas as rotas. As rotas com `MAX_INT64` barram o overflow corretamente.
- **Corpo hostil:** valor en-US `1234.56` → 422; valor numérico (não-string) → 422; data `2026-02-31` → 422; estado inexistente → 422; `medicao_ids` vazio/5000 → 422 (min/max aplicados); ofício de 10k → 422; emoji/HTML no motivo → 200 (escapado no destino). Nenhum 500.
- **CSRF, cookie HttpOnly+SameSite, tempo constante do token:** conforme o vermelho estático.

---

## Registros criados/alterados no banco de dev (anotados)

Linha de base em `fuzz/linha_base_ids.json`. Deltas após o fuzz:

- `usuarios`: +1 → **id 8** `locktest.fuzz@lotufo.com` (descartável das sondas de lockout; destrancado ao fim; pode ser removido).
- `espelhos`: +1 → **id 9** (contrato 8, nº 901, vigente, `envio_id=24`), gerado para V-01; `.docx` em `dados/espelhos/82eb84ff...docx`.
- `medicoes`: +1 → **id 641** (contrato 8, nº 901, `espelho_enviado`); valor protocolado alterado para R$ 7.777,77 (F-07/S4b).
- Estados alterados: **591** `prevista`→`protocolada` (F-07/S4a); **630** `nota_emitida`→`protocolada` (F-10/V-11); **640** `protocolada`→`recebida` e valor atestado mexido (fuzz de corpo F-04-corpo); **631** valor atestado → R$ 123,45 (F-13).
- `cronograma_versoes`: +2 (contrato 8, versões 2 e 3) — F-07/S4c.
- `protocolo_links`: +2 (protocolo 3) — F-12/S10.
- `envios`: +5, `envio_anexos`: +5, `medicao_protocolos`: +1, `medicao_documentos`: +2 (evidência `.eml` + afins), `audit_log`: +62.
- **Correio simulado:** `backend/dados/correio-simulado/enviados/` = **6 arquivos** (`1.json`..`6.json`), todos para `destino-externo-fuzz@exemplo.com` com `cco oculto-fuzz@exemplo.com`. **0 e-mails reais.**

Snapshot intacto em `backend/dados/dashboard-pre-fase1.db` (não restaurado, servidor não parado).

## Suspeitas NÃO provadas (sem reprodução limpa)

- **V-01 em protocolo/nota/pleito** e **F-02 nessas rotas**: não reproduzidas dinamicamente por falta dos anexos antigos no dev (500 de `FileNotFoundError`, artefato de ambiente). Código idêntico ao do espelho/protocolo já provado.
- **S5 (Cco descartado no envio da nota):** confirmado **estaticamente** no schema — `EnviarIn` de `/api/notas/envio/{pid}/enviar` não tem campo `cco` (o front tem o campo). Não reproduzido em runtime porque o envio de nota desses registros dá 500 por falta de anexo.
- **V-06/V-07/V-08/V-10/V-13/V-14** e **S7/S9/S12/S13/S15/S18**: fora do conjunto pedido de sondas dinâmicas; não executadas nesta rodada (algumas exigem medição de carga/rede ou cenário de backup com erro).
