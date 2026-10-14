# 02 — Vermelho estático (revisão de segurança só por leitura de código)

Data: 10/10/2026. Escopo: `backend/app` (FastAPI + SQLite), `frontend/src`, `backend/requirements.lock`,
`frontend/package.json`, `scripts/rodar_producao.ps1`. Nada foi executado contra o servidor; as sondas abaixo
são para os agentes dinâmicos rodarem contra `http://localhost:8080`.

**AVISO PARA QUEM RODAR AS SONDAS DE ENVIO (V-01, V-02, V-12):** só rode com `DASH_GRAPH_SIMULADOR=<pasta>`
ligado no servidor de teste. Sem o simulador o e-mail sai de verdade pelo Outlook de quem está logado. A prova
de envio é a contagem de arquivos em `<pasta>/enviados/*.json`.

**AVISO PARA V-04/V-05:** use uma conta de TESTE criada para isso ({EMAIL_TESTE}), nunca o admin real.

Placeholders: `{COOKIE}` = valor do cookie `sessao`; `{CSRF}` = campo `csrf` de `GET /api/auth/eu`;
`{ID}`/`{PID}` = ids reais do banco de teste.

Contagem: **4 altas, 4 médias, 6 baixas** (nenhuma crítica).

---

## V-01 — Duplo envio de e-mail por corrida (TOCTOU) no envio de protocolo, nota e pleito; espelho sem trava nenhuma
- **Severidade:** alta
- **Onde:** `backend/app/protocolo.py:773-775` (confere `situacao`), `:793` (manda o e-mail), `:799-802` (marca `enviado`);
  `backend/app/pleitos.py:352-353`, `:366`, `:370-372`; `backend/app/espelhos.py:249-279` (não confere envio anterior);
  rotas `api_protocolos.py:212`, `api_notas_envio.py:67`, `api_pleitos.py:173`, `api_espelhos.py:140`.
- **Por quê:** a checagem "já enviado?" é uma leitura fora de transação; o e-mail sai pelo Graph (segundos) e só
  depois um `db.mutacao` marca o protocolo como `enviado`. Dois pedidos simultâneos (duas abas, dois usuários,
  um retry do navegador) passam os dois pela checagem e mandam dois e-mails ao órgão, com dois registros em
  `envios`; o segundo `UPDATE` sobrescreve `envio_id`. No espelho não há checagem alguma: cada POST reenvia.
  O botão do front fica desabilitado (`ocupado`), mas isso não protege o servidor.
- **Sonda:**
```python
import requests, threading
B="http://localhost:8080"; H={"Cookie":"sessao={COOKIE}","X-CSRF-Token":"{CSRF}"}
pv = requests.post(f"{B}/api/protocolos/envio/previa", json={"protocolo_ids":[{PID}]}, headers=H).json()
corpo = {"protocolo_ids":[{PID}], "para":pv["para"] or ["teste@exemplo.com"], "copia":[], "assunto":pv["assunto"] or "x",
         "corpo":pv["corpo"] or "x", "justificativa":"teste de corrida - nao enviar de verdade"}
res=[]
def f(): res.append(requests.post(f"{B}/api/protocolos/envio", json=corpo, headers=H))
ts=[threading.Thread(target=f) for _ in range(3)]; [t.start() for t in ts]; [t.join() for t in ts]
print([(r.status_code, r.text[:120]) for r in res])
# Espelho (sem trava): repetir 2x em sequencia
# requests.post(f"{B}/api/espelhos/{ID}/enviar", json={...}, headers=H)  -> 2x 200
```
- **Falha existe:** dois ou três `200` com `envio_id` diferentes; `enviados/` ganha 2-3 arquivos; `SELECT COUNT(*) FROM envios`
  sobe 2-3. No espelho, dois POSTs seguidos dão dois `200`.
- **Falha não existe:** um `200` e os demais `422 "Protocolo N já enviado"` (ou `409`); um arquivo só em `enviados/`.

## V-02 — E-mail enviado e não registrado; o 503 diz "tente novamente" e convida o reenvio
- **Severidade:** alta
- **Onde:** `backend/app/correio.py:205-228` (`enviar_e_registrar`: `c.enviar` na linha 222, `registrar_envio` na 224,
  em transação própria); `backend/app/protocolo.py:793` x `:799` (segunda transação, separada);
  `backend/app/main.py:72-87` (handler `banco_ocupado` → 503 "tente novamente").
- **Por quê:** a promessa "falha de envio não deixa rastro" vale, mas o inverso não: se o banco estiver travado
  (busy_timeout de 5 s estourado — ver `maquina-cpu-freada`, backup horário, sync do RM) depois que o Graph
  aceitou a mensagem, `registrar_envio` levanta `OperationalError: database is locked`, o handler devolve 503
  com a frase "nada foi gravado e a operação pode ser repetida" — falsa aqui — e o protocolo continua `montado`.
  O usuário repete e o órgão recebe o e-mail de novo. Mesmo efeito se só a segunda transação (protocolo.py:799)
  falhar: há linha em `envios`, mas o protocolo não fica `enviado`.
- **Sonda:**
```python
import sqlite3, threading, time, requests
DB=r"{CAMINHO_DO_BANCO_DE_TESTE}"   # o DASH_DB_PATH do servidor em 8080
def segura():
    c=sqlite3.connect(DB, timeout=1); c.execute("BEGIN IMMEDIATE"); time.sleep(8); c.rollback(); c.close()
B="http://localhost:8080"; H={"Cookie":"sessao={COOKIE}","X-CSRF-Token":"{CSRF}"}
corpo={...}  # mesmo corpo da V-01
t=threading.Thread(target=segura); t.start(); time.sleep(0.3)
r=requests.post(f"{B}/api/protocolos/envio", json=corpo, headers=H); t.join()
print(r.status_code, r.text)
# depois: contar enviados/*.json, SELECT COUNT(*) FROM envios, SELECT situacao FROM protocolos WHERE id={PID}
```
  (Com o lock pego antes do pedido, o `previa_envio` só lê — WAL não bloqueia leitura — e o `BEGIN IMMEDIATE`
  de `registrar_envio` espera 5 s e estoura. Se o lock pegar a leitura também, aumente o `sleep(0.3)` para
  logo depois do início do pedido.)
- **Falha existe:** `503 "Banco de dados ocupado — tente novamente"`, mas `enviados/` ganhou um arquivo, `envios` não
  ganhou linha e o protocolo segue `montado`; repetir o POST manda outro e-mail. Log com `CRITICAL ... E-mail ENVIADO e nao registrado`.
- **Falha não existe:** ou o e-mail não sai (lock tomado antes do envio, tudo recusado) ou ele sai e o registro
  acontece (fila/retry interno), e a resposta não convida a repetir.

## V-03 — Corpo da requisição sem teto e lido ANTES da autenticação (DoS pré-login de disco e memória)
- **Severidade:** alta
- **Onde:** `backend/.venv/Lib/site-packages/fastapi/routing.py:430` (`await request.form()` / `request.body()`)
  roda antes de `solve_dependencies` (`:481`), que é onde `exigir()` barra; `starlette/formparsers.py:147,230`
  (arquivo vai para `SpooledTemporaryFile` sem limite de tamanho); `scripts/rodar_producao.ps1:188` (uvicorn em
  `0.0.0.0:80`, sem `--limit-concurrency` nem limite de corpo); o teto de 10/40 MB de `arquivos.blocos_validados`
  só roda dentro da rota, depois que o upload inteiro já foi gravado.
- **Por quê:** qualquer máquina da rede, sem login, manda um multipart de vários GB para qualquer rota de upload
  (ou um JSON gigante para qualquer POST de corpo JSON) e o servidor grava tudo no `%TEMP%` (ou na RAM, no
  caso do JSON) antes de responder 401. A máquina é o `<servidor>`, que também roda o RM: disco cheio ou RAM
  esgotada derruba as duas coisas.
- **Sonda (use 300-500 MB, não mais — a máquina tem CPU freada):**
```bash
# sem cookie nenhum
fsutil file createnew %TEMP%\grande.bin 500000000      # (Windows)  ou: head -c 500000000 /dev/zero > grande.bin
curl -s -o NUL -w "%{http_code} %{time_total}s\n" -F "arquivo=@grande.bin;type=application/pdf" http://localhost:8080/api/documentos/certidoes/ler
# observe o %TEMP% do processo do servidor crescer durante o envio
python -c "import requests;print(requests.post('http://localhost:8080/api/protocolos/envio',data=b'{\"x\":\"'+b'a'*400_000_000+b'\"}',headers={'Content-Type':'application/json'}).status_code)"
# observe a memoria do python.exe do servidor no Gerenciador de Tarefas
```
- **Falha existe:** o `401` só chega depois do upload inteiro (tempo proporcional ao tamanho); `%TEMP%` ganha um
  arquivo de ~500 MB enquanto dura; a memória do processo sobe ~400 MB no teste do JSON.
- **Falha não existe:** `401`/`413` em milissegundos, sem crescimento de disco nem de memória.

## V-04 — Qualquer pessoa da rede tranca o administrador indefinidamente (lockout sem desbloqueio)
- **Severidade:** alta
- **Onde:** `backend/app/auth.py:11-12` (`MAX_FALHAS=5`, `BLOQUEIO_MIN=15`), `:49-51` (bloqueado recusa até a senha
  certa), `:58-62`; `backend/app/cli.py:169-186` (não há comando de desbloqueio nem de troca de senha); não há
  rota de redefinição.
- **Por quê:** o bloqueio é por conta, não por origem. Cinco POSTs com senha errada para o e-mail do admin (o
  e-mail é previsível: padrão nome@dominio-da-empresa) trancam a conta por 15 min; repetir a cada 15 min mantém
  o admin fora para sempre, sem ferramenta de desbloqueio além de SQL na mão. Vale para qualquer usuário.
- **Sonda:**
```bash
for i in 1 2 3 4 5; do curl -s -o /dev/null -w "%{http_code}\n" -X POST http://localhost:8080/api/auth/login \
  -H "Content-Type: application/json" -d '{"email":"{EMAIL_TESTE}","senha":"errada-'$i'"}'; done
curl -s -w "\n%{http_code}\n" -X POST http://localhost:8080/api/auth/login -H "Content-Type: application/json" \
  -d '{"email":"{EMAIL_TESTE}","senha":"{SENHA_CERTA_TESTE}"}'
```
- **Falha existe:** a 6ª chamada, com a senha CERTA, devolve `401`, e continua `401` por 15 min; nenhum caminho de
  desbloqueio pela aplicação.
- **Falha não existe:** bloqueio atrelado a origem/IP, ou atraso progressivo em vez de trava dura, ou desbloqueio
  disponível para o admin/CLI.

## V-05 — Corrida no contador de falhas: força bruta muito acima de 5 tentativas por janela; sem limite por origem
- **Severidade:** média
- **Onde:** `backend/app/auth.py:44` (lê `tentativas_falhas` fora de transação), `:58-62` (grava `falhas+1` lido antes).
- **Por quê:** N tentativas simultâneas leem o mesmo contador (ex.: 0) e todas gravam o mesmo valor (1), então o bloqueio demora bem mais que 5 erros para acontecer. Também não há
  limite por máquina de origem, o que permite testar uma senha comum contra todas as contas.
- **Como verificar:** com a conta de teste, disparar várias tentativas erradas ao mesmo tempo e depois entrar
  com a senha certa; esperado (correto): conta bloqueada. Se entrar, a falha existe.

## V-06 — Login caro em memória, sem teto de concorrência e senha sem tamanho máximo
- **Severidade:** média
- **Onde:** `backend/app/auth.py:10,19,24-29` (argon2 com o padrão de 64 MiB por verificação, inclusive o hash falso
  para e-mail inexistente); `backend/app/api_auth.py:43` (`senha: str` sem `max_length`).
- **Por quê:** cada tentativa de login, mesmo com e-mail inexistente, ocupa 64 MiB e uma das ~40 threads do
  servidor. Muitas tentativas simultâneas, sem login, esgotam memória e threads e travam todas as telas
  (e o `/api/health`, o que pode fazer o watchdog reiniciar o serviço).
- **Como verificar:** observar no Gerenciador de Tarefas a memória do processo enquanto várias pessoas/abas fazem
  login com e-mail inexistente ao mesmo tempo; esperado (correto): a memória não cresce em proporção e as
  outras telas continuam respondendo.

## V-07 — Produção em HTTP puro: senha e cookie de sessão em claro na rede interna
- **Severidade:** média
- **Onde:** `scripts/rodar_producao.ps1:188` (`--port 80` sem TLS); `backend/app/api_auth.py:69-71`
  (`secure=False` quando `DASH_SEM_TLS=1`).
- **Por quê:** qualquer máquina na mesma rede que intercepte o tráfego lê a senha no login e o cookie `sessao`,
  e passa a agir como aquele usuário. É decisão registrada (02/09/2026), mas o risco continua.
- **Como verificar:** na produção, abrir o login pelo navegador e ver nas ferramentas do desenvolvedor que o
  endereço é `http://` e que o cookie `sessao` não tem a marca "Secure"; esperado (correto): `https://` e cookie Secure.

## V-08 — Fila de leitura de PDF trava por até 60 s e devolve "tente de novo" a quem chega depois
- **Severidade:** média
- **Onde:** `backend/app/leitura_pdf.py:53` (`_VAGAS` = 2), `:630` (espera de só 10 s por vaga), `:80`
  (`TEMPO_PACOTE_S` = 60 s), `:74` (OCR até 40 s segurando a vaga).
- **Por quê:** duas montagens de pacote grande ou dois OCRs ocupam as duas vagas por até 60 s; nesse tempo
  qualquer outra leitura de PDF (certidão, nota, regularidade) falha com 422/415 após 10 s, e cada pedido
  em espera prende uma thread do servidor. Qualquer usuário engenharia, mesmo sem querer, bloqueia os outros.
- **Como verificar:** com dois usuários, montar dois pacotes grandes ao mesmo tempo e, em paralelo, anexar uma
  certidão; esperado (correto): a certidão é lida (talvez com atraso), sem a mensagem "leituras de PDF demais".

## V-09 — Login que falha grava para sempre o texto digitado no campo e-mail
- **Severidade:** baixa
- **Onde:** `backend/app/api_auth.py:57-59` (`auth.login_falha` com o e-mail digitado); `backend/app/api_admin.py:10`
  (o admin lê o log inteiro).
- **Por quê:** quem cola a senha no campo de e-mail por engano deixa a senha em texto puro no log de auditoria,
  que é só de acréscimo (não se apaga) e aparece na tela de administração.
- **Como verificar:** tentar entrar digitando uma frase qualquer no campo e-mail e depois, como admin, abrir a
  auditoria; esperado (correto): o texto não aparece por inteiro (mascarado ou só se for e-mail válido).

## V-10 — `/api/health` sem login mostra a mensagem de erro do backup
- **Severidade:** baixa
- **Onde:** `backend/app/main.py:53-70`; `backend/app/backup.py:197,212` (grava `str(e)` da exceção).
- **Por quê:** a rota é pública e, quando o backup falha, devolve o texto da exceção do Windows, que costuma
  trazer o caminho completo das pastas de dados e de backup.
- **Como verificar:** sem estar logado, abrir `/api/health` quando houver erro de backup registrado; esperado
  (correto): só "ok"/"erro", sem caminhos.

## V-11 — Arquivo .eml do "envio feito por fora" entra sem conferência de conteúdo
- **Severidade:** baixa
- **Onde:** `backend/app/api_notas_envio.py:83-97` (lê até 25 MB sem checar tipo); `backend/app/notas_envio.py:311-325`
  (grava em `evidencias/` e liga à medição); download em `backend/app/api_espelhos.py:188-204` (servido como DOCX).
- **Por quê:** qualquer arquivo de até 25 MB, com qualquer conteúdo e nome, vira "evidência" da medição; não há
  conferência de que é um e-mail. O download sai como anexo (sem risco de abrir na página), mas o rótulo de
  tipo é errado e a evidência não prova nada. A lista `medicao_ids` também não tem tamanho máximo.
- **Como verificar:** registrar um envio por fora anexando um arquivo que não é e-mail (ex.: uma imagem renomeada
  para .eml); esperado (correto): recusa com mensagem clara.

## V-12 — Sem vínculo usuário↔obra e destinatário livre no envio
- **Severidade:** baixa (por desenho, registrar a decisão)
- **Onde:** `backend/app/permissoes.py:8-12` (só três perfis, sem escopo por obra); rotas de envio
  `api_protocolos.py:212`, `api_notas_envio.py:67`, `api_espelhos.py:140`, `api_pleitos.py:173` (`para`, `copia`, `cco` livres).
- **Por quê:** qualquer usuário engenharia altera, cancela, marca como protocolada e envia qualquer medição de
  qualquer obra, e pode mandar o pacote (certidões, notas, ofícios) para qualquer endereço externo, inclusive
  em cópia oculta. Só a auditoria registra. O perfil diretoria baixa todos os arquivos de todas as obras.
- **Como verificar:** logar com a conta de teste engenharia e abrir/alterar uma medição de uma obra que não é
  dela; hoje é permitido. Com a conta diretoria, tentar qualquer POST de escrita; esperado: 403 (isso funciona).

## V-13 — Tempo de resposta do login pode indicar quais e-mails existem
- **Severidade:** baixa
- **Onde:** `backend/app/auth.py:46-63`.
- **Por quê:** e-mail inexistente e conta bloqueada gastam só o hash falso; senha errada de conta existente gasta
  o hash real mais uma escrita com commit no banco (`UPDATE` da contagem). A diferença é de poucos
  milissegundos, mas em rede local dá para medir com muitas repetições. A mensagem de erro é a mesma (isso está certo).
- **Como verificar:** medir o tempo médio de muitas tentativas com um e-mail que existe e com um que não existe;
  esperado (correto): médias iguais dentro do ruído.

## V-14 — Sessão: sem troca de senha, sem encerrar as outras sessões, sem expiração por inatividade
- **Severidade:** baixa
- **Onde:** `backend/app/auth.py:13,76-92` (12 h fixas, sessões vencidas nunca apagadas); `backend/app/api_usuarios.py`
  (nenhuma rota de senha); `backend/app/cli.py:169` (só `criar-admin`).
- **Por quê:** quem suspeita que a senha vazou não consegue trocá-la nem derrubar as sessões abertas; o admin
  também não consegue redefinir a senha de ninguém. A sessão vale 12 h mesmo com o computador abandonado.
  Desativar o usuário funciona na hora (isso está certo). Também faltam cabeçalhos como CSP e X-Frame-Options;
  o risco é pequeno porque o cookie é SameSite=Strict.
- **Como verificar:** procurar na tela Minha conta e na administração uma opção de trocar/redefinir senha;
  esperado (correto): existir, e ao usá-la as outras sessões do usuário deixarem de valer.

---

## O que está bem feito (não gastar tempo aqui)
1. **SQL:** todo valor vai por parâmetro `?`; os poucos nomes de coluna montados no texto vêm de listas fixas
   do código (`api_usuarios.py:84`, `contratos.py:57`, `medicoes.py:131`, `notas.py:188`). Não achei injeção.
2. **Caminhos de arquivo:** nome em disco é o sha256 do conteúdo; leitura passa por `arquivos.caminho_seguro`
   (recusa sair da pasta de dados); token Microsoft e assinatura usam `int(usuario_id)`. Sem path traversal.
3. **Uploads:** tipo declarado + assinatura do arquivo (`%PDF-`, `PK`) + teto por rota; PDF aberto em
   processo separado com limite de tempo e pré-checagem contra bomba de descompressão (`leitura_pdf.py`).
4. **CSRF e cookie:** token por sessão comparado em tempo constante (`api_auth.py:28-36`), exigido em toda
   escrita via `exigir()`; cookie HttpOnly + SameSite=Strict; sem CORS liberado. Nenhuma rota GET altera dado.
5. **Sessão:** token guardado só como hash; usuário desativado ou com perfil trocado vale na hora (conferido a
   cada pedido); admin não consegue se desativar nem tirar o próprio perfil.
6. **Permissões:** matriz imutável (`frozenset`); rotas de usuários, auditoria, RM e contas Microsoft exigem
   `administrar`; diretoria só lê.
7. **E-mail:** corpo escapado nos três montadores (`protocolo._html`, `espelhos._html`, `pleitos._html`);
   link só `https://`; o token só vai ao host do Graph e redirecionamentos não são seguidos (`correio.py`, `graph.py`).
8. **Modelos de texto:** `carta.preencher` (format_map) só recebe modelos do cadastro, nunca o texto digitado.
9. **Downloads:** saem como anexo, com `nosniff` nos PDFs; nome do arquivo no cabeçalho é codificado pelo Starlette.
10. **Transações:** `db.mutacao` com BEGIN IMMEDIATE e savepoints; dado e auditoria no mesmo commit; 503 para lock.
    Dependências: nenhuma versão do `requirements.lock`/`package.json` com falha conhecida que eu tenha certeza.
