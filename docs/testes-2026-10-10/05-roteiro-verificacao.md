# 05 — Roteiro da verificação adversarial (fase 3, 10/10/2026)

Cada item é uma ALEGAÇÃO a ser derrubada. Quem verifica recebe só o passo e o critério; o objetivo é
tentar provar que a alegação é FALSA. Veredito por item: CONFIRMADO (reproduzido 2×, com evidência),
NÃO CONFIRMADO (o sistema se comportou certo; diga o que viu), INCONCLUSIVO (não deu para montar o teste;
diga por quê). Severidade só pode ser mantida ou rebaixada, com motivo.

Dados de partida (banco limpo, cópia da produção de 10/10 03:06):
- Usuários de teste em `backend/dados/usuarios-teste.txt` (admin id 5, engenharia id 6, diretoria id 7).
- Contrato 20 = Estações BRT (SINFRA, 100% Lotufo). Medição 631 = 7ª execução, nascida do espelho nº 7,
  estado `nota_emitida`, com notas do RM somando R$ 9.384.834,18. Medição 632 = reajuste da mesma 7ª,
  também `nota_emitida`. Protocolo 3 = envio da nota que contém só a 631.
- Contrato 5 = MT-401 (execução desde 03/2023; última medição nº 32, competência 11/2025, recebida).
- Contrato 17 = Complexo Xtreme (MTPAR). Medição 591 = 12ª execução em `prevista`. Medição 635 = 15ª,
  `protocolada`, sem nº do órgão.
- Login: POST `/api/auth/login` {email, senha} → cookie `sessao`; CSRF em GET `/api/auth/eu` (campo `csrf`),
  enviado no cabeçalho `X-CSRF-Token` em toda escrita.

---

## Parte A — pela API (verificador A, instância própria na porta 8081)

| ID | Alegação | Passos | Confirma se |
|---|---|---|---|
| A-01 | Envios simultâneos do mesmo espelho geram e-mails duplicados | Gerar um espelho novo (ex.: MT-401 nº 33, competência 2026-10, R$ 100,00) e disparar 3 POST de envio desse espelho ao mesmo tempo | mais de um 200 e mais de um arquivo novo no simulador |
| A-02 | Envio simultâneo do MESMO protocolo de nota duplica o e-mail | 3 POST simultâneos de envio do protocolo 3 (justificativa ≥10 caracteres) | mais de um 200 ou mais de um e-mail no simulador |
| A-03 | Com o banco travado, o e-mail sai, o envio não é registrado e a resposta manda repetir | Abrir outra conexão SQLite no banco da instância e segurar `BEGIN IMMEDIATE` ~8 s; durante isso, enviar um espelho/protocolo | resposta 503 "tente novamente" + arquivo novo no simulador + nenhuma linha nova na tabela de envios |
| A-04 | Pedido enorme sem login é lido inteiro antes de recusar | POST sem cookie com corpo JSON de 100 MB numa rota de escrita; comparar o tempo do 401 com um corpo de 1 KB | o 401 grande demora proporcionalmente mais (dezenas de vezes) |
| A-05 | 5 senhas erradas trancam a conta e não há como destrancar pelo sistema | Com uma conta de teste: 5 logins errados, depois a senha certa; procurar rota/tela/comando de desbloqueio | a senha certa é recusada e não existe desbloqueio fora de SQL |
| A-06 | Tentativas erradas simultâneas passam do limite de 5 | 10 logins errados em paralelo numa conta destrancada e depois a senha certa | a senha certa ENTRA (o bloqueio não pegou) |
| A-07 | ID gigante derruba rotas com erro interno | GET `/api/medicoes/9223372036854775808`, `/api/contratos/99999999999999999999` | 500 em vez de 404/422 |
| A-08 | Nota manual com valor gigante dá erro interno | POST de nota manual numa medição com valor `99999999999999999999,00` | 500 |
| A-09 | Dá para protocolar uma medição pulando nota e envio | Como engenharia, protocolar a medição 591 (`prevista`) pela rota de protocolo manual, com justificativa se pedir | a medição vai para `protocolada` |
| A-10 | O texto do campo e-mail de um login falho fica na auditoria | Login com e-mail `minha frase secreta 123` e qualquer senha; como admin, ler a auditoria | o texto aparece inteiro |
| A-11 | "Envio feito por fora" aceita qualquer arquivo como .eml | Registrar envio externo de uma medição com nota emitida anexando uma imagem PNG renomeada `.eml` | aceito (200) |
| A-12 | Envio aceita destinatário e Cco externos livres | Enviar um espelho para `qualquer@exemplo.com` com Cco `oculto@exemplo.com` | aceito e os dois aparecem no arquivo do simulador |
| A-13 | Link "do OneDrive" aceita qualquer site e entra no e-mail | Adicionar ao protocolo 3 um link `https://exemplo-malicioso.test/x`; ver a prévia ou o e-mail | aceito e o link aparece no corpo |
| A-14 | Valor com algarismo arábico-índico é aceito | Gravar o atestado de uma medição com `١٢٣,٤٥` | gravado como R$ 123,45 |
| A-15 | Número do órgão em branco apaga o já gravado | Gravar nº `X-1` na medição 635 e depois gravar `""` | o número some, sem erro |
| A-16 | Valor de medição do espelho é editável depois da nota, sem aviso | Alterar o valor protocolado da 631 para `1,00`; ler a medição, a conferência das notas, os avisos (`/api/inicio`) e o painel da diretoria | aceito; notas seguem "confere"; nenhum aviso novo; o "nota esperando protocolo" da diretoria cai |
| A-17 | Cco do envio da nota é descartado | Enviar o protocolo 3 com `cco: ["oculto@exemplo.com"]` no corpo (justificativa ≥10) | 200 e o arquivo do simulador com `cco` vazio |
| A-18 | Na SINFRA, a medição sai sem o reajuste irmão e sem aviso | Enviar o protocolo 3 (só a 631) | aceito sem pendência/aviso sobre a 632, que segue `nota_emitida` |
| A-19 | Certidão manual com validade em 2099 vira a vigente | Ler uma certidão de PDF válido sem texto (página em branco) e gravar à mão: Lotufo, municipal, validade 2099-12-31; ler `/api/documentos` | gravada e mostrada como vigente até 2099 no lugar da atual |
| A-20 | Espelho aceita competência anterior ao contrato | Prévia de espelho no MT-401: nº 33, competência 2020-01, R$ 100,00 | a prévia monta sem recusa |
| A-21 | Três números diferentes para "obras ativas" | Comparar o total de obras ativas em `/api/medicoes/resumo`, `/api/inicio/painel` e no farol de `/api/diretoria` com a contagem do banco | três números diferentes para o mesmo rótulo |

## Parte B — pela tela (verificador B, Playwright contra http://localhost:5173 → 8080)

| ID | Alegação | Passos | Confirma se |
|---|---|---|---|
| B-01 | "Medido no mês" do Início compara com um setembro irreal | Engenharia, /inicio: ler "Medido em outubro" e o gráfico; /carteira: ler "medido no mês" | Início e Carteira mostram valores incompatíveis para o mesmo mês e setembro aparece com centenas de milhões |
| B-02 | Linha do tempo não mostra edição de valor | Editar o valor da medição 632 e voltar ao valor original; abrir a linha do tempo | as edições não aparecem |
| B-03 | Mensagem de valor inválido sem acento e sem formato | Editar valor da 632 com `1234.56` | mensagem "monetario invalido" sem orientar "1.234,56" |
| B-04 | Tabela de notas corta a coluna "Nota" a 1024 px | /obras/20/medicoes/631, abrir a etapa 3, viewport 1024×768 | a coluna fica cortada/rola na horizontal |
| B-05 | Clique duplo em "Enviar a nota" manda um e-mail só | /obras/20/medicoes/631, justificativa, clique duplo em "Enviar a nota" | um POST e um arquivo no simulador (`backend/dados/correio-simulado/enviados`) — aqui "confirma" significa que a tela PROTEGE |
| B-06 | Mensagem antiga fica depois do envio | Editar o valor da 632 (mesmo valor) e em seguida enviar a nota dela | o aviso de valor gravado continua e não há confirmação do envio |
| B-07 | Registrar nº do protocolo não mostra "gravado" | /medicoes/aguardando-pagamento, registrar um nº numa linha MTPAR | nenhuma confirmação visível |
| B-08 | Recusas de upload: uma traz "ValueError" e o topo mostra só a última | /documentos, anexar ao mesmo tempo: texto renomeado .pdf, PDF corrompido (`%PDF-1.4` + lixo), arquivo vazio | as três recusadas; aparece "ValueError"; o topo mostra só uma |
| B-09 | Diretoria vê botão de envio e recebe mensagem crua | Diretoria, /medicoes/enviar-nota, clicar "Enviar a nota →"; abrir /conta | aparece "Permissão necessária: editar_cadastros" |
| B-10 | Admin não troca senha nem perfil pela tela | Admin, /admin/usuarios | só há ativar/desativar |
| B-11 | Auditoria com códigos internos e janela de 500 | Admin, /admin/auditoria, filtro de ações | ações como "certidao.registrar" sem tradução; texto de "últimos 500" |
| B-12 | Mensagens com código interno e em inglês | Nova medição MT-401 nº 32 → prévia; Prazos MT-401 → pedir prorrogação com 99999 dias | "(execucao)" na primeira; "Input should be less than or equal to 3650" na segunda |
| B-13 | Quebras de layout no celular | Viewport 375×812: /inicio e /obras/20/medicoes/632 | valor grande quebra no meio do número; nome da obra truncado a 2–3 letras |
