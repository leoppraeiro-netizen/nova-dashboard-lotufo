# Tornar o repositório público sem expor dado nenhum

Decisão do Leo em 13/10/2026: o repositório vira público para ter GitHub Actions ilimitado
(runners padrão, Linux e Windows, são gratuitos em repositório público). A cota de 2.000
min/mês do plano gratuito acabou em 13/10 e a CI parou; as PRs #101 (ci.yml) e #102
(suíte rápida) ficaram sem execução.

Público não quer dizer código aberto: não há licença; o README passa a dizer "todos os
direitos reservados, Lotufo Engenharia". Publicar o sistema interno sob a conta pessoal do
Leo é decisão da empresa, não deste plano.

## O princípio: repositório NOVO, histórico novo

O repositório privado atual **nunca** vira público. Motivo: o GitHub mantém todo commit já
enviado acessível pelo SHA e pelos refs `refs/pull/N/head`, que o dono não consegue apagar.
Reescrever o histórico e trocar a visibilidade no mesmo repositório deixaria 720 commits
de dados reais ao alcance de quem tiver um link antigo ou um fork. Além disso, reescrever
720 commits de docs que evoluíram é a receita para deixar passar algo.

Então: o conteúdo limpo nasce num repositório novo, com **um único commit inicial**. O
privado fica arquivado (somente leitura) como registro histórico. O `git blame` público
começa do zero; o histórico completo continua no privado.

## O que sai, o que fica, o que muda

### 1. Cadastro (`cadastro/`) → repositório privado `lotufo-cadastro`

Contém os 22 contratos reais, e-mails de ~20 servidores da SINFRA, MT-PAR e Prefeitura,
cartas, regras de espelho e modelos `.docx` com papel timbrado. É o mais sensível e o mais
fácil de separar: a regra do produto ("cadastro versionado, editado pelo Leo com o Claude,
aplicado por `cadastro aplicar`") continua valendo num repositório privado próprio, sem CI.

- `git filter-repo --path cadastro/` extrai só essa pasta com o histórico dela para o
  repositório novo (privado, então o histórico pode ir junto).
- O app lê o cadastro de `DASH_CADASTRO_DIR`. O `--raiz` do CLI já existe; o padrão passa
  a vir da variável. Produção: clone em `C:\DashboardLotufo\cadastro`. Dev: pasta irmã
  `..\lotufo-cadastro`.
- No repositório público fica `cadastro-exemplo/`: um órgão fictício, um contrato, um
  consórcio, cartas e um modelo `.docx` neutro, suficiente para os testes de cadastro,
  espelho e carta.
- `test_espelho_cadastro_real.py` (regressão contra os valores reais) passa a pular quando
  `DASH_CADASTRO_DIR` não existe: roda na máquina do Leo, não na CI.
- A skill `deploy` ganha o passo "atualizar o clone do cadastro".

Alternativa descartada: submódulo privado dentro do público. Cada worktree de agente teria
que inicializar o submódulo com credencial, e o clone público quebraria no `cadastro/`.

### 2. Fixtures de teste → anonimizadas no lugar

`backend/tests/fixtures/` tem 8 NFS-e reais (CNPJ, chave de acesso, valores, retenções da
Lotufo e das consorciadas), 15 certidões reais, 1 PDF escaneado real e 3 relatórios do
DocuSign com nomes. 12 módulos de teste dependem delas.

- Um script único (`scripts/anonimizar_fixtures.py`, roda uma vez e é apagado) aplica um
  mapa consistente: CNPJ real → CNPJ fictício com dígito válido; razão social → "Construtora
  Alfa Ltda", "Engenharia Beta S.A."...; chave de acesso → recalculada com os dados
  fictícios; nomes de pessoas → fictícios; e-mails → `@exemplo.com.br`; códigos de controle
  de certidão → aleatórios. Valores em reais ficam: não identificam ninguém sozinhos e são
  o que os testes de FRC e conciliação conferem.
- O mesmo mapa é aplicado aos 12 testes (eles citam CNPJ e nome em asserções). A suíte
  inteira é a prova de que nada quebrou.
- O PDF escaneado real vira um PDF gerado (imagem sintética com o mesmo tipo de texto).

### 3. Docs e `.claude/` → limpeza no lugar

- Nomes de funcionárias (aparecem dezenas de vezes) viram papel: "faturamento",
  "controladoria", "engenheira da obra". E-mails corporativos e de órgão saem.
- Nome da máquina de produção, porta da API do RM e nome da tarefa
  agendada viram placeholders ou variável (`DASH_SERVIDOR`). Caminhos `C:\DashboardLotufo`
  ficam: sozinhos não abrem porta nenhuma, e a máquina só existe na rede interna.
- `docs/runbook.md`, `scripts/deploy.ps1` e `scripts/rodar_producao.ps1` ficam no público
  depois dessa limpeza (mover quebraria a skill `deploy`). Se o Leo preferir, o runbook vai
  para `lotufo-cadastro/docs/` e o CLAUDE.md aponta para lá.
- Specs e planos (`docs/superpowers/`) ficam: são desenho de produto. O que eles revelam de
  relação com órgãos (pleitos, cobrança, fluxo real da SINFRA) é aceito pela decisão de
  publicar; nomes de pessoas de órgão saem.
- `cadastro/` some dos textos como pasta local; vira "repositório `lotufo-cadastro`".

### 4. O que nunca entra: `.gitignore` e pasta fora do repositório

Hoje estão só não rastreados: `PENDENCIAS.md`, `cobranca.ps1`, `contexto-2026-10-11/`,
`monitor-siga/` (lê o SIGA com CPF e senha do cofre), `prototipos/*`. Entram no
`.gitignore` explicitamente, e `monitor-siga/` sai da pasta do projeto (vai para
`C:\DashboardLotufo\monitor-siga` ou `~/dev`).

### 5. Issues → recriadas no público, numeração preservada

66 abertas, 14 fechadas, 22 PRs; só a #49 tem dado sensível (reescrever antes). Transferir
issue de privado para público o GitHub não permite; então um script recria. Para que todo
`#N` em docs, CLAUDE.md, memória e mensagens de commit continue válido, os 36 números
usados por issues fechadas e PRs viram issues-stub fechadas ("número reservado: usado por
PR/issue fechada no repositório de origem"). Labels recriados (`decisao`, `parar`,
`precisa-do-leo`, `risco:*`, `divida`, `ui`...). Comentários das abertas vão junto.

### 6. Configuração do repositório público

- Actions: "Require approval for all outside collaborators" (PR de fork não roda sozinha);
  `GITHUB_TOKEN` somente leitura por padrão.
- Proteção do `master` (de graça em repositório público; no privado exigia plano Pro):
  só por PR, CI verde obrigatória, sem force push, sem apagar branch. A orquestradora já
  trabalha assim.
- Secret scanning + push protection ligados (gratuitos em público); Dependabot alerts.
- Wiki, Projects e Discussions desligados. Issues ligadas.
- README com aviso de direitos reservados e sem licença.

### 7. Guardas permanentes (cada push passa a ser público na hora)

- Job `vazamento` na CI e verificação no `.githooks/pre-commit`: falha se aparecer CNPJ ou
  CPF com dígito válido, e-mail fora de `@exemplo.com.br`/`@lotufo.com` (domínio de teste),
  domínio `lotufoengenharia.com.br` ou `mt.gov.br`, chave de acesso de NFS-e, ou o nome da
  máquina. Lista de exceções explícita e curta.
- `gitleaks` (ação gratuita) na CI para segredo técnico.
- `.claude/rules/dados-de-teste.md`: trabalhadora nunca cola NF, certidão, e-mail ou nome
  real; dado de teste é sintético; cadastro real mora fora do repositório.
- CLAUDE.md: regra "repositório público" na seção "Regras que o código não conta".

## Sequência de corte

1. **No privado, por PRs normais** (CI parada; testes do módulo localmente; merge do Leo):
   a. cadastro: variável `DASH_CADASTRO_DIR`, `cadastro-exemplo/`, teste real pula sem a pasta;
   b. fixtures anonimizadas + testes ajustados (suíte inteira verde);
   c. docs e `.claude/` limpos; `.gitignore`; regra nova;
   d. job `vazamento` e `gitleaks` no `ci.yml` (junto com a #101).
   Estimativa: 3 a 5 trabalhadoras, 2 a 4 dias, mais a revisão do Leo.
2. **Auditoria final da árvore**: varredura por padrão (o mesmo script do job `vazamento`)
   em TODOS os arquivos, `gitleaks detect --no-git`, e leitura humana de uma lista curta:
   `cadastro-exemplo/`, `backend/tests/fixtures/`, `docs/runbook.md`, `scripts/`, `.claude/`.
3. **`lotufo-cadastro`** (privado): `filter-repo` da pasta `cadastro/` + clone em produção.
4. **Renomear** o privado para `nova-dashboard-lotufo-arquivo` e **criar** o público com o
   nome `nova-dashboard-lotufo`, para que URLs, `gh` e a skill `deploy` continuem iguais.
5. **Commit inicial**: branch órfã a partir da árvore limpa (`git checkout --orphan`), um
   commit, push como `master` do público.
6. Labels, issues (script do item 5), configurações do item 6.
7. **Remotes locais**: pasta principal troca `origin` para o público e reaponta `master`
   (`git fetch` + `git checkout -B master origin/master`); o worktree pinado da produção
   segue o mesmo `.git`, então o próximo `deploy` já pega o commit novo. Nada de re-clonar.
8. Reabrir as PRs #101 e #102 no público (cherry-pick dos commits sobre a base nova). CI
   ilimitada a partir daqui.
9. **Arquivar** o privado. Não apagar.

## Riscos aceitos

- Algo pode escapar da anonimização. Mitigação: varredura automática + leitura humana antes
  do push; depois do push, considerar copiado o que vazou (um fork ou cache já pode ter).
  Se vazar depois, o conserto é `filter-repo` + force push + pedido ao suporte do GitHub
  para purgar, e por isso a push protection e o pre-commit existem.
- Desenho do produto e processo com órgãos ficam visíveis. Decisão de 13/10.
- Histórico público começa em 13/10/2026; o anterior fica no privado arquivado.
- Autorização da Lotufo para publicar: do Leo.
