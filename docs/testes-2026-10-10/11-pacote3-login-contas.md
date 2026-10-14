# Pacote 3 — login e contas (fase 4, 10/10/2026)

Branch `fix/login-contas` (a partir de `master` 81cc580). Sem merge, sem push, produção e portas 80/8080 não tocadas.
Corrige A-06, A-10, A-05 e A-04 de `06-verificacao-api.md` e B-10 de `07-verificacao-tela.md`. Para cada item: primeiro
o teste que reproduz o defeito (rodado e falhando), depois a correção.

## Commits

| Commit | Item |
|---|---|
| 5f16f52 (teste e correção juntos) | A-06 — contador de senhas erradas não era atômico |
| 5bdcb49 teste / 744e78f fix | A-10 — texto do campo e-mail ia inteiro para a auditoria |
| 61f61e0 teste / 323cc26 fix | A-05 + B-10 — desbloquear, redefinir senha, trocar a própria senha (servidor) |
| 13da218 teste / 87921aa fix | A-05 — desbloquear e redefinir senha pela linha de comando |
| 51b5883 teste / 56ac24d fix | B-10 — a tela de Usuários e a de Minha conta |
| 9e81cc0 teste / 9d9fc7b fix | A-04 — corpo gigante lido inteiro antes do 401 |

## O que mudou, item por item (linguagem simples)

**A-06 — cinco senhas erradas agora bloqueiam mesmo em rajada.** Antes, cada tentativa lia o contador, conferia a
senha e gravava "o que leu + 1"; dez tentativas ao mesmo tempo liam todas zero e gravavam todas 1, e o bloqueio nunca
chegava. Agora quem soma é o banco, dentro da transação exclusiva, e o valor novo é relido ali mesmo; ao chegar a 5,
grava o bloqueio de 15 minutos e zera o contador no mesmo passo. O caminho do e-mail inexistente continua gastando o
mesmo tempo (não foi mexido). Acréscimo pequeno: o login certo reconfere o bloqueio antes de zerar o contador, para
uma tentativa que começou antes do bloqueio não "destrancar" a conta ao terminar depois dele.
Arquivo: `backend/app/auth.py` (`autenticar`).

**A-10 — senha colada no campo e-mail não vai mais para a auditoria.** No login recusado, o texto do campo e-mail só é
gravado se tiver cara de e-mail: um "@", sem espaço, e um domínio com ponto terminado em letras (endurecido no gate
Sol, S3). Senão a auditoria guarda `{"email": null, "motivo": "texto inválido no campo e-mail", "faixa": "1-16" |
"17-32" | ">32"}` — só a faixa do tamanho, não o número exato (S6). Arquivo: `backend/app/api_auth.py`.

**A-05 + B-10 — destravar a conta e trocar senha sem mexer no banco.**
- O administrador ganhou, em Administração › Usuários: a coluna **Bloqueio** ("—" ou "até 14:35" com o botão
  **Desbloquear**), o botão **Redefinir senha** (abre um campo de senha de no mínimo 10 caracteres e "Confirmar a senha
  nova") e o **perfil editável** em cada linha. A linha do próprio administrador continua sem nada disso (nem
  desativar, nem perfil, nem redefinir senha: a própria senha se troca em Minha conta).
- Redefinir a senha zera o bloqueio e derruba todas as sessões abertas daquela pessoa.
- Em Minha conta há o bloco **Trocar senha** (atual, nova, confirmar a nova). A confirmação diferente é recusada na tela,
  sem ir ao servidor; os erros do servidor aparecem no bloco. Ao trocar, as outras sessões da pessoa caem e a atual fica.
- Pela linha de comando, para o caso de o único administrador se trancar:
  `python -m app.cli desbloquear <email>` e `python -m app.cli redefinir-senha <email>` (a senha é pedida sem eco).
- Tudo vai para a auditoria (`usuario.desbloquear`, `usuario.senha_redefinida`, `usuario.senha_trocada`), nunca com a
  senha. Pela linha de comando o evento fica sem autor.
- Rotas: `POST /api/admin/usuarios/{id}/desbloquear`, `POST /api/admin/usuarios/{id}/senha` (só administrador),
  `POST /api/auth/senha` (qualquer perfil logado, com CSRF). `PUT /api/admin/usuarios/{id}` já aceitava `perfil`; não
  mudou. `GET /api/admin/usuarios` passa a devolver `bloqueado_ate` e `tentativas_falhas`.
Arquivos: `backend/app/auth.py` (`desbloquear`, `redefinir_senha`, `trocar_senha`), `backend/app/api_usuarios.py`,
`backend/app/api_auth.py`, `backend/app/cli.py`, `frontend/src/Admin.tsx`, `frontend/src/MinhaConta.tsx`,
`frontend/src/tempo.ts` (`fmtHora`).

**A-04 — pedido gigante é recusado antes de ser lido.** Um porteiro novo (`backend/app/limites.py`, ligado em
`main.py`) olha o tamanho de todo pedido antes de qualquer rota: até 45 MB só para envio de arquivo às 12 rotas de
upload (a maior aceita 40 MB) e até 2 MB para todo o resto, seja qual for o tipo declarado (S2 do gate Sol). Se o pedido já declara um tamanho maior, a resposta é "Pedido acima do tamanho
permitido" (413) na hora, sem ler nada; se não declara (envio em pedaços), ele conta os bytes e para no que passa do
teto. Os limites de cada rota (10 MB da certidão, 40 MB do pacote) continuam valendo dentro delas.

## Saídas antes e depois

| Item | Antes (teste novo falhando) | Depois |
|---|---|---|
| A-06 | `test_dez_falhas_em_paralelo_bloqueiam_a_conta` FAILED: `bloqueado_ate` ficou vazio depois de 10 falhas simultâneas | `test_auth.py` 22 passed |
| A-10 | `test_login_falho_com_texto_que_nao_e_email_nao_grava_o_texto` FAILED: auditoria com `{'email': 'minha frase secreta 123'}` (o caso do e-mail válido já passava) | `test_auth.py` 24 passed |
| A-05/B-10 servidor | `test_api_usuarios.py` 7 failed, 11 passed: `KeyError 'bloqueado_ate'` na lista; 404 nas rotas novas | `test_api_usuarios.py` + `test_auth.py` 42 passed; `test_permissoes`/`test_api_admin`/`test_auditoria` 35 passed |
| A-05 linha de comando | `test_cli_contas.py` 3 failed (comandos desconhecidos) | 3 passed |
| B-10 tela | vitest `Admin.test.tsx` + `MinhaConta.test.tsx`: 3 failed, 3 passed | 6 passed; typecheck limpo |
| A-04 | `test_limites.py` 3 failed, 2 passed: JSON de 3 MB, JSON em pedaços de 3 MB e multipart de 46 MB sem login davam 401 depois de ler tudo | 5 passed |

Medição real do A-04 com o servidor de verdade (uvicorn numa porta livre, 8093, banco temporário): `PUT` de 1 KB sem
cookie → 401 em 28 ms; `PUT` de 100 MB sem cookie → **413 em 13 ms** (o verificador mediu, antes, 401 em 1,39 s). O
porteiro chamado direto com tamanho declarado de 100 MB: o corpo foi lido 0 vezes e a rota chamada 0 vezes.

Suíte inteira no fim: backend 893 passed, 1 skipped (7 min 08 s); frontend 29 arquivos, 95 testes passed; typecheck limpo.

## Decisões e desvios do desenho

1. **Admin rebaixando o próprio perfil continua dando 409, não 422.** O desenho dizia "422 (regra existente)", mas a
   regra existente (trava de 28/09) responde 409 e já tem teste (`test_admin_nao_se_desativa_nem_tira_o_proprio_perfil`).
   Mantive 409 para não mudar comportamento já em produção.
2. **Trocar a própria senha usa o próprio login para conferir a atual** (`autenticar`): errar a senha atual ali conta
   para o bloqueio de 5 tentativas. Sem isso, quem pegasse uma sessão aberta poderia chutar a senha à vontade por essa
   rota. Efeito colateral aceito: com a conta bloqueada, a troca responde "Senha atual não confere" até o bloqueio passar.
3. **Senha nova igual à atual** é recusada (422) antes de conferir a atual.
4. **`bloqueado_ate` na lista só aparece se o bloqueio está em vigor**, em hora de Cuiabá (`…-04:00`); vencido vem
   `null`, porque o banco só limpa o carimbo no próximo login certo e um bloqueio vencido já não tranca nada.
5. **A própria linha do admin não tem "Redefinir senha"** (derrubaria a sessão dele mesmo); ele usa Minha conta. A rota
   do servidor não proíbe (um admin que a chame para si só se desloga).
6. **Mudar o perfil grava ao escolher no seletor**, sem botão de confirmar, como já era o Reativar; vai para a
   auditoria como `usuario.atualizar` (antes/depois).
7. **A regra "mínimo de 10 caracteres" virou uma constante só** (`auth.SENHA_MIN`), usada também na criação de usuário
   (o texto da mensagem não mudou).
8. **A-04, teto pela leitura em pedaços**: quando o excesso é descoberto no meio da leitura, o porteiro levanta um 413
   que o FastAPI repassa como está (é o caminho previsto por ele para erro vindo de middleware); se algo ler o corpo fora
   de uma rota, o próprio porteiro responde.
9. **A-06 teste e correção no mesmo commit** (os outros itens têm commits separados); a saída falhando foi rodada e
   guardada antes da correção, como nos demais.

## Riscos

- **2 MB para pedido que não é arquivo**: conferi as rotas — todo upload vai como multipart, e o maior texto aceito é o
  corpo de e-mail de 20.000 caracteres. Uma rota futura que receba JSON grande (ex.: importação em lote pela API) vai
  bater no 413 e precisará de exceção no porteiro. Rota nova de upload precisa entrar em `ROTAS_UPLOAD`
  (`backend/app/limites.py`); o teste `test_toda_rota_com_formulario_esta_na_lista_de_upload` lê o OpenAPI e falha
  se ela ficar de fora.
- **Sessões derrubadas**: redefinir a senha de quem está no meio de um trabalho desloga a pessoa na hora (é o objetivo).
- **Visual não conferido no navegador**: o servidor de teste da 8080 é de outra sessão e estava fora do combinado; a
  tela foi conferida pelos testes de componente e pelo typecheck. Vale uma olhada em Administração › Usuários com uma
  conta bloqueada (a tabela ganhou uma coluna e a última coluna tem dois botões por linha).

## Gate Sol: 6 achados, 4 corrigidos, 2 para o backlog

| Achado | Gravidade | O que era | O que mudou | Commits |
|---|---|---|---|---|
| S1 | alta | Trocar a própria senha podia gravar por cima de uma redefinição feita pelo admin no meio da troca (sessão roubada + senha antiga) | A troca guarda a senha observada antes de conferir; na gravação exige a sessão ainda viva ("Sua sessão foi encerrada: entre de novo") e a senha ainda igual à observada ("A senha mudou enquanto você trocava…"). A do admin prevalece | 03c22a2 teste / a5f382c fix |
| S2 | alta | O teto de 45 MB valia para qualquer rota que se dissesse "envio de arquivo": um JSON de 44 MB assim rotulado era lido inteiro | 45 MB só para multipart nas 12 rotas de upload (`ROTAS_UPLOAD`, método + caminho); todo o resto 2 MB | 8959476 teste / 6693cbc fix |
| S3 | média | "Senha@2026" passava pelo padrão de e-mail e ia à auditoria | Domínio precisa ter ponto e terminar em letras. Resíduo: uma senha que seja um e-mail válido ainda entra | d304751 teste / c5f708c fix |
| S6 | baixa | O tamanho exato do texto recusado ficava na auditoria | Grava só a faixa: "1-16", "17-32", ">32" | d304751 teste / c5f708c fix |
| S4 | — | Diferença de tempo de resposta no login | Backlog: é o V-13, conhecido e anterior à branch | — |
| S5 | — | Bloqueio por senhas erradas usado para trancar a conta dos outros (negação de serviço) | Backlog: é o V-04/A-05, mitigado pelo Desbloquear da tela e pelo comando `desbloquear`; ainda sem limite por origem | — |

Saídas: S1 antes `DID NOT RAISE ValueError` (a troca gravou por cima), depois `test_auth.py` + `test_api_usuarios.py`
43 passed. S2 antes `test_limites.py` 3 failed, 5 passed (JSON 3 MB rotulado multipart para `/api/protocolos/envio` e
multipart de 10 MB para `PUT /api/medicoes/1/valor` davam 401 depois de ler tudo), depois 8 passed. S3/S6 antes
2 failed, 1 passed (`tamanho: 23`; `senha@2026` gravado), depois `test_auth.py` 26 passed.

Desvios no gate: (1) a guarda que confere a lista de rotas de upload lê o OpenAPI, porque nesta versão do FastAPI a lista
de rotas do app vem aninhada por router; o ajuste do teste foi junto no commit da correção do S2. (2) A faixa do S6 conta
o texto como digitado; texto vazio cai em "1-16".

Suíte inteira depois do gate: backend 898 passed, 1 skipped (6 min 52 s); frontend 29 arquivos, 95 testes passed; typecheck limpo.
