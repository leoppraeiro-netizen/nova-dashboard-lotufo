---
name: Dashboard Lotufo
description: Dashboard administrativo claro para contratos de obra pública, ciclos de medição e certidões — sidebar, superfícies brancas, um acento derivado da marca.
colors:
  bg: "#f6f7f9"
  superficie: "#ffffff"
  superficie-2: "#fafbfc"
  superficie-vidro: "rgb(255 255 255 / .92)"
  hover: "#f2f4f7"
  pressionado: "#eef0f4"
  linha: "#e5e8ee"
  linha-forte: "#d5dae3"
  linha-hover: "#c3cad6"
  previsto: "#cbd5e1"
  texto: "#101828"
  texto-2: "#5b6474"
  texto-fraco: "#9aa3b2"
  marca: "#FF6500"
  acento: "#C2410C"
  acento-forte: "#9A3412"
  acento-mais: "#7c2d12"
  acento-fundo: "#fff5ed"
  acento-linha: "#fed7aa"
  acao: "#b42318"
  acao-forte: "#912018"
  acao-fundo: "#fef3f2"
  acao-linha: "#fecdca"
  atencao: "#93540A"
  atencao-fundo: "#FEF0C7"
  atencao-linha: "#fde68a"
  ok: "#067647"
  ok-fundo: "#ecfdf3"
  ok-linha: "#abefc6"
typography:
  display:
    fontFamily: "Hanken Grotesk, system-ui, Segoe UI, Roboto, sans-serif"
    fontSize: "22px"
    fontWeight: 600
    lineHeight: 1.2
    letterSpacing: "-0.02em"
    fontFeature: "tnum 1, lnum 1"
  headline:
    fontFamily: "Hanken Grotesk, system-ui, Segoe UI, Roboto, sans-serif"
    fontSize: "20px"
    fontWeight: 600
    lineHeight: 1.45
    letterSpacing: "-0.018em"
  numero:
    fontFamily: "Hanken Grotesk, system-ui, Segoe UI, Roboto, sans-serif"
    fontSize: "15px"
    fontWeight: 600
    lineHeight: 1.45
    letterSpacing: "normal"
    fontFeature: "tnum 1, lnum 1"
  title:
    fontFamily: "Hanken Grotesk, system-ui, Segoe UI, Roboto, sans-serif"
    fontSize: "14px"
    fontWeight: 600
    lineHeight: 1.45
    letterSpacing: "-0.014em"
  body:
    fontFamily: "Hanken Grotesk, system-ui, Segoe UI, Roboto, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.45
    letterSpacing: "normal"
  tabela:
    fontFamily: "Hanken Grotesk, system-ui, Segoe UI, Roboto, sans-serif"
    fontSize: "13.5px"
    fontWeight: 400
    lineHeight: 1.45
    letterSpacing: "normal"
  controle:
    fontFamily: "Hanken Grotesk, system-ui, Segoe UI, Roboto, sans-serif"
    fontSize: "13px"
    fontWeight: 500
    lineHeight: 1.45
    letterSpacing: "normal"
  meta:
    fontFamily: "Hanken Grotesk, system-ui, Segoe UI, Roboto, sans-serif"
    fontSize: "12.5px"
    fontWeight: 400
    lineHeight: 1.45
    letterSpacing: "normal"
  nota:
    fontFamily: "Hanken Grotesk, system-ui, Segoe UI, Roboto, sans-serif"
    fontSize: "12px"
    fontWeight: 400
    lineHeight: 1.45
    letterSpacing: "normal"
  label:
    fontFamily: "Hanken Grotesk, system-ui, Segoe UI, Roboto, sans-serif"
    fontSize: "11.5px"
    fontWeight: 600
    lineHeight: 1.45
    letterSpacing: "0.04em"
  eixo:
    fontFamily: "Hanken Grotesk, system-ui, Segoe UI, Roboto, sans-serif"
    fontSize: "11px"
    fontWeight: 400
    lineHeight: 1
    letterSpacing: "normal"
  mono:
    fontFamily: "ui-monospace, Cascadia Mono, Consolas, monospace"
    fontSize: "0.92em"
    fontWeight: 400
    lineHeight: 1.45
rounded:
  micro: "4px"
  ctrl: "6px"
  superficie: "8px"
  pilula: "999px"
spacing:
  "2xs": "2px"
  xs: "4px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "20px"
  "2xl": "24px"
  "3xl": "32px"
components:
  button-secundario:
    backgroundColor: "{colors.superficie}"
    textColor: "{colors.texto}"
    rounded: "{rounded.ctrl}"
    padding: "0 12px"
    height: "32px"
    typography: "13px/500"
  button-secundario-hover:
    backgroundColor: "{colors.hover}"
    textColor: "{colors.texto}"
  button-secundario-active:
    backgroundColor: "{colors.pressionado}"
  button-secundario-disabled:
    textColor: "{colors.texto-fraco}"
  button-primario:
    backgroundColor: "{colors.acento}"
    textColor: "#ffffff"
    rounded: "{rounded.ctrl}"
    padding: "0 12px"
    height: "32px"
  button-primario-hover:
    backgroundColor: "{colors.acento-forte}"
  button-primario-active:
    backgroundColor: "{colors.acento-mais}"
  button-destrutivo:
    backgroundColor: "{colors.acao}"
    textColor: "#ffffff"
    rounded: "{rounded.ctrl}"
    height: "32px"
  button-destrutivo-hover:
    backgroundColor: "{colors.acao-forte}"
  button-pequeno:
    height: "28px"
    padding: "0 9px"
    typography: "12.5px/500"
  button-voltar:
    backgroundColor: "transparent"
    textColor: "{colors.texto-2}"
    height: "26px"
    padding: "0 8px 0 6px"
  entrada:
    backgroundColor: "{colors.superficie}"
    textColor: "{colors.texto}"
    rounded: "{rounded.ctrl}"
    padding: "0 10px"
    height: "32px"
    typography: "13px"
  entrada-focus:
    backgroundColor: "{colors.superficie}"
    textColor: "{colors.texto}"
  entrada-curta:
    width: "84px"
  entrada-media:
    width: "168px"
  entrada-larga:
    width: "320px"
  entrada-arquivo:
    backgroundColor: "{colors.superficie}"
    textColor: "{colors.texto-2}"
    rounded: "{rounded.ctrl}"
    padding: "2px 10px 2px 2px"
    height: "auto"
    typography: "13px"
  entrada-arquivo-botao:
    backgroundColor: "{colors.superficie}"
    textColor: "{colors.texto}"
    rounded: "{rounded.ctrl}"
    padding: "0 9px"
    height: "26px"
    typography: "13px/500"
  cartao:
    backgroundColor: "{colors.superficie}"
    textColor: "{colors.texto}"
    rounded: "{rounded.superficie}"
    padding: "14px 20px"
  cartao-cabeca:
    backgroundColor: "{colors.superficie}"
    textColor: "{colors.texto}"
    padding: "13px 20px"
    typography: "{typography.title}"
  cartao-rodape:
    backgroundColor: "{colors.superficie-2}"
    padding: "14px 20px"
  tabela-cabecalho:
    backgroundColor: "{colors.superficie-2}"
    textColor: "{colors.texto-2}"
    padding: "9px 12px"
    typography: "{typography.label}"
  tabela-celula:
    backgroundColor: "{colors.superficie}"
    textColor: "{colors.texto-2}"
    padding: "10px 12px"
    height: "40px"
    typography: "{typography.tabela}"
  tabela-celula-par:
    backgroundColor: "{colors.superficie-2}"
  tabela-celula-hover:
    backgroundColor: "{colors.hover}"
  tabela-grupo:
    backgroundColor: "{colors.superficie-2}"
    textColor: "{colors.texto}"
    padding: "10px 20px"
    typography: "13.5px/600"
  tabela-totais:
    backgroundColor: "{colors.superficie-2}"
    textColor: "{colors.texto}"
    padding: "10px 12px"
  nav-item:
    backgroundColor: "transparent"
    textColor: "{colors.texto-2}"
    rounded: "{rounded.ctrl}"
    padding: "8px 10px"
    typography: "13.5px/500"
  nav-item-ativo:
    backgroundColor: "{colors.acento-fundo}"
    textColor: "{colors.acento}"
    rounded: "{rounded.ctrl}"
    padding: "8px 10px"
    typography: "13.5px/600"
  aba:
    backgroundColor: "transparent"
    textColor: "{colors.texto-2}"
    padding: "0 12px"
    height: "36px"
    typography: "13.5px/400"
  aba-selecionada:
    backgroundColor: "transparent"
    textColor: "{colors.acento}"
    height: "36px"
    typography: "13.5px/600"
  selo:
    backgroundColor: "{colors.superficie-2}"
    textColor: "{colors.texto-2}"
    rounded: "{rounded.pilula}"
    padding: "2px 9px"
    typography: "{typography.label}"
  selo-ok:
    backgroundColor: "{colors.ok-fundo}"
    textColor: "{colors.ok}"
    rounded: "{rounded.pilula}"
    padding: "2px 9px"
  selo-acao:
    backgroundColor: "{colors.acao-fundo}"
    textColor: "{colors.acao}"
    rounded: "{rounded.pilula}"
    padding: "2px 9px"
  selo-atencao:
    backgroundColor: "{colors.atencao-fundo}"
    textColor: "{colors.atencao}"
    rounded: "{rounded.pilula}"
    padding: "2px 9px"
  aviso:
    backgroundColor: "{colors.atencao-fundo}"
    textColor: "{colors.atencao}"
    rounded: "{rounded.ctrl}"
    padding: "4px 9px"
    typography: "12.5px"
  erro:
    backgroundColor: "{colors.acao-fundo}"
    textColor: "{colors.acao}"
    rounded: "{rounded.ctrl}"
    padding: "10px 12px"
    typography: "13px"
  painel-linha:
    backgroundColor: "{colors.acento-fundo}"
    textColor: "{colors.texto}"
    padding: "16px 20px"
  vazio:
    backgroundColor: "{colors.superficie}"
    textColor: "{colors.texto-2}"
    padding: "32px 20px"
    typography: "{typography.tabela}"
---

# Design System: Dashboard Lotufo

> Registrado do mundo construído em 2026-08-31, ao fechar a fase 2; **estendido em
> 2026-09-02**, ao fechar a fase 3 (certidões, checklist de protocolo, 5º item de
> nav). A fonte da verdade dos tokens é `frontend/src/tokens.css`; este arquivo
> descreve o que aquele arquivo já faz. Onde o contrato de direção e o código
> divergem, vale o código — as divergências materiais estão anotadas no fim.

## Overview

**Creative North Star: "A Mesa de Trabalho da Engenharia"**

Um dashboard administrativo canônico, jogado limpo. Nada aqui tenta parecer o
assunto que trata: não há carimbo, papel timbrado, textura de processo nem
qualquer maquiagem temática de obra pública. O que existe é uma superfície
branca, larga, densa e silenciosa onde tabelas financeiras podem ser lidas por
uma hora seguida sem cansar — escritório diurno, monitor de mesa, rede interna.
O acabamento se mede contra app de banco empresarial com a tensão de produto de
Linear/Notion: réguas retas, densidade alta, tipografia pequena mas confortável,
zero decoração.

O sistema tem exatamente **uma cor com voz**. O laranja da Lotufo aparece na
logo e num detalhe decorativo; tudo que é interativo usa o mesmo laranja
escurecido até passar em contraste. Vermelho, âmbar e verde só existem para
dizer o que significam. Todo o resto do desenho — hierarquia, agrupamento,
prioridade — é feito com **peso, tamanho, linha e distância**, nunca com mais
cor. É por isso que a tela suporta uma matriz de oito colunas agrupada por
entidade sem virar um vitral.

Densidade é uma decisão, não um acidente: linha de tabela de 40px, corpo de
14px, controles de 32px, cartões colados num ritmo de 20px. A tela é feita para
mostrar mais linhas, não para respirar mais. O contrapeso da densidade é a
disciplina de contraste e de medida: só dois tons de texto legíveis, um único
nível de sombra, nenhum cinza fraco fazendo hierarquia, e todo texto de apoio
com teto de medida para não correr 170 caracteres numa tela larga.

**Key Characteristics:**
- Modo único claro; sem dark mode nesta fase (`color-scheme: light`).
- Uma cor de acento (`--acento`), derivada da marca por contraste, não por gosto.
- Estado nunca é só cor: sempre ponto + rótulo, e o rótulo carrega o **trabalho**
  ("Vencida em 13/08/2026" e "Sem cobertura" são o mesmo vermelho, não a mesma frase).
- Densidade de planilha: linha 40px, corpo 14px, tabela 13,5px.
- **Um único valor de sombra** no arquivo inteiro; profundidade se faz com borda e
  camada tonal.
- Nenhuma tela declara cor própria — todas consomem `tokens.css`.
- Fonte servida pelo próprio servidor; nada no HTML aponta para fora.
- Um único momento animado na interface inteira.
- Todo texto de apoio tem teto de medida (78ch); todo dado longo em tabela trunca
  com reticências de verdade e guarda o inteiro no `title`.

## Colors

Neutros frios de papel de escritório, um acento terroso derivado do laranja da
marca, e três semânticas que nunca decoram.

### Primary

- **Acento Tijolo** (`--acento`): o único laranja que carrega texto. Botão
  primário (fundo, com texto branco), link, aba selecionada, item ativo da nav,
  anel de foco, `caret-color` dos campos, série "medido" do gráfico. Nasceu do
  laranja da marca escurecido até ~5,2:1 sobre branco.
- **Acento Forte** (`--acento-forte`): hover de tudo que usa o acento; cor de
  link em hover; texto do valor editável em hover.
- **Acento Mais** (`--acento-mais`): `:active` do botão primário, texto sobre a
  tinta clara do acento, e a **segunda série** empilhada do gráfico (reajuste e
  projeto) — mesma família do medido, um tom acima, para que a distinção entre
  séries não dependa de dois laranjas vizinhos.
- **Tinta do Acento** (`--acento-fundo`): fundo do item ativo da nav, do painel
  que abre sob a linha da tabela, e do hover dos botões-valor dentro da célula.
- **Linha do Acento** (`--acento-linha`): borda superior do painel expandido e
  fundo de `::selection`.

### Secondary

- **Laranja Lotufo** (`--marca`): a cor real da marca, re-amostrada do arquivo
  em alta resolução. Faz 2,96:1 sobre branco — **nunca carrega texto**. Aparece
  em dois lugares e só neles: a logo (`/logo-lotufo.png`, 150px no sidebar) e a
  barra decorativa de 3px encostada na borda esquerda do item ativo da nav.

### Tertiary

- **Cinza Previsto** (`--previsto`): a série "previsto" dos gráficos e o ponto
  do estado "prevista"/"em aberto". É neutro de propósito — o previsto é o
  fundo contra o qual o acento marca o que foi medido.

### Semânticas

Três significados, e nada além deles. Na fase 3 os três estão em uso como **chip
claro** (fundo tênue + borda da própria semântica + texto escuro).

- **Ação / Vencido** (`--acao`, forte `--acao-forte`, fundo `--acao-fundo`,
  linha `--acao-linha`): botão destrutivo, bloco de erro, mensagem de erro sob
  o campo, selo de alerta vencido, selo de certidão sem cobertura ou vencida,
  veredito "Pendências" do checklist, e **número negativo onde negativo é um
  problema** (saldo estourado).
- **Atenção** (`--atencao`, fundo `--atencao-fundo`, linha `--atencao-linha`):
  pendência e prazo se aproximando — "Vence em N dias", chip de aviso do
  formulário e do painel inline, hachura clara sobre a barra provisória do
  gráfico e rótulo destacado do eixo.
- **OK** (`--ok`, fundo `--ok-fundo`, linha `--ok-linha`): concluído, atestado,
  dinheiro recebido — e, desde a fase 3, o **chip afirmativo**: "Em dia" no
  semáforo de certidão e "Pronto" no veredito do checklist. Os tons de fundo e
  linha, que estavam declarados e reservados, entraram em uso reais.

### Neutral

- **Fundo do App** (`--bg`): o fundo cinza-frio atrás de tudo; também a borda de
  3px que "recorta" o polegar da barra de rolagem.
- **Superfície** (`--superficie`): cartão, sidebar, controle, célula de tabela — e
  o fundo **opaco** da coluna de ações ancorada, que precisa cobrir as colunas que
  passam por baixo dela.
- **Superfície 2** (`--superficie-2`): zebra da tabela, cabeçalho, rodapé e
  **cabeçalho de grupo** de tabela, rodapé de cartão, avatar do usuário, hover do
  item de nav, selo neutro.
- **Vidro** (`--superficie-vidro`): a topbar, branca a 92% com
  `backdrop-filter: saturate(180%) blur(6px)` — o conteúdo passa por baixo ao rolar.
- **Hover** / **Pressionado** (`--hover`, `--pressionado`): estados de controle
  e linha de tabela neutros.
- **Linha / Linha Forte / Linha Hover** (`--linha`, `--linha-forte`,
  `--linha-hover`): divisor de superfície; borda de controle, topo da linha de
  totais e o sinal de borda da coluna ancorada; borda de controle em hover e
  polegar da barra de rolagem em hover.
- **Texto** (`--texto`) e **Texto 2** (`--texto-2`): os únicos dois tons que
  carregam texto legível. Título, número, dado forte e cabeçalho de grupo no
  primeiro; corpo de célula, rótulo, meta e nota no segundo.
- **Texto Fraco** (`--texto-fraco`): controle desabilitado, ícone desabilitado
  e o traço do riscado de exceção. Nada mais.

### Named Rules

**A Regra da Marca Muda.** O laranja puro da marca nunca carrega texto e nunca
é fundo de controle. Ele existe na logo e num detalhe decorativo não-textual.
Teste: se apagar o laranja puro da folha de estilo, nenhuma palavra da
interface fica ilegível.

**A Regra do Acento Derivado.** Tudo que é interativo usa `--acento`, jamais
`--marca`. Legibilidade vence fidelidade de marca — e a troca é de uma linha:
se o laranja for re-amostrado, muda só o token.

**A Regra dos Dois Cinzas.** Só `--texto` e `--texto-2` carregam texto. Um
terceiro cinza mais claro reprovaria em contraste; para criar hierarquia use
peso e tamanho, nunca um cinza mais fraco.

**A Regra do Significado Exclusivo.** Vermelho, âmbar e verde nunca são
decoração. Se um elemento está vermelho, alguma coisa venceu, está sem cobertura
ou vai ser destruída.

**A Regra do Chip Âmbar.** Nenhuma semântica ganha fundo sólido no selo: os
quatro níveis (neutro, ok, atenção, ação) são chip claro — fundo tênue, borda da
própria semântica, texto escuro. A regra nasceu do âmbar, que sólido colidiria
com o território laranja do acento, e vale para os quatro por consistência de
forma: quando o verde entrou na fase 3, entrou como chip, não como pílula sólida.

**A Regra da Cor Emprestada.** Nenhum `.tsx` escreve cor literal. Se falta um
tom, ele nasce em `tokens.css` — todas as telas das fases 2 e 3 têm zero
`style={{}}` de cor.

## Typography

**Fonte única:** Hanken Grotesk (variável, 100–900), com `system-ui`, "Segoe UI",
Roboto e sans-serif como pilha de reserva.
**Fonte mono:** `ui-monospace`, "Cascadia Mono", Consolas.

**Caráter:** uma grotesca humanista de contadores abertos, que aguenta 11,5px em
caixa alta no cabeçalho de tabela e 13,5px em corpo de célula sem borrar. Não há
fonte de display: o mesmo desenho vai do número de 22px do saldo ao rótulo de
11,5px, e a hierarquia inteira é feita de peso, tamanho e tracking negativo.

A fonte é **servida pelo próprio servidor** (`public/fonts/*.woff2`, `@font-face`
em `tokens.css`), um arquivo por faixa de caracteres — não um por peso: o arquivo
é variável, e por isso `font-weight: 100 900`. `latin` cobre o português inteiro;
`latin-ext` entra para que um caractere avulso vindo de cadastro não troque a
fonte no meio da linha. O `index.html` faz `preload` só do `latin`.

### Hierarchy

A escala tem **nove degraus reais** entre 11,5px e 22px, mais um degrau de eixo.
Ela é mais densa do que a de um site porque a tela é densa: entre 12px e 14px
existem quatro degraus (12 / 12,5 / 13 / 13,5), e cada um tem um trabalho
próprio. A regra que os separa não é decorativa — é o **tipo de superfície** em
que o texto vive: célula de tabela, controle de 32px, texto de apoio, rótulo de
campo. A contagem entre parênteses é o número de usos em `tokens.css` depois da
normalização da fase 3.

- **Display** (600, 22px, altura 1.2, tracking −0.02em — 1 uso): um só uso — o
  total da faixa de saldo, o maior número da tela. Sempre tabular.
- **Headline** (600, 20px, tracking −0.018em — 1 uso): o `h1` da topbar, um por
  tela.
- **Número** (600, 15px, tabular — 4 usos): o valor de uma faixa de grandezas —
  parcela do saldo, operador da conta, item de totais e o **valor vigente do
  contrato**, que na fase 2 tinha um 18px só seu. É o degrau em que um número
  vira dado de leitura, não título.
- **Title** (600, 14px, tracking −0.014em — 1 uso): título de cartão (`h2`/`h3`),
  do mesmo tamanho do corpo. O que separa o título do texto é o peso, não o tamanho.
- **Body** (400, 14px, altura 1.45 — 2 usos): o corpo do app, herdado do `body`.
- **Tabela** (400, 13,5px — 8 usos): a densidade de leitura padrão do sistema —
  célula, item de nav, aba, botão-valor, botão-nome, linha de alerta, mensagem de
  vazio e o **cabeçalho de grupo** da matriz (aqui em 600: é dado, não rótulo de
  coluna). É o degrau mais repetido do arquivo.
- **Controle** (500, 13px — 5 usos): o texto que vive **dentro** de um controle —
  botão, campo, campo de arquivo, nome do usuário no pé da sidebar, bloco de erro.
  Uma unidade abaixo da tabela porque a caixa já delimita.
- **Meta** (400, 12,5px — 7 usos): o texto de apoio que acompanha alguma coisa —
  meta da topbar, dica do cartão, chip de aviso, título do painel inline, legenda
  do gráfico — e também o botão pequeno e o botão voltar, que são controles de
  28px/26px. É a voz secundária da casa.
- **Nota** (400, 12px — 6 usos): a tipografia de formulário e de rodapé de
  explicação — rótulo de campo (aqui em 600), nota do campo, erro sob o campo,
  perfil do usuário, nota do saldo, erro da sidebar. Sempre em `--texto-2`,
  exceto o erro, que vai em `--acao`.
- **Label** (600, 11,5px, tracking 0.04em, caixa alta — 5 usos): cabeçalho de
  coluna, rótulo do resumo e dos totais, selo semântico, inicial do avatar, eixo X
  do gráfico. O único degrau em caixa alta.
- **Eixo** (400, 11px — 1 uso): **exceção nomeada**, e a menor tipografia do
  sistema. É o rótulo do eixo Y do gráfico, texto SVG desenhado em px reais —
  onde o número precisa caber entre linhas de grade sem esticar o cartão. O eixo
  X sobe para 11,5px (Label) porque tem espaço horizontal. Nenhuma superfície de
  HTML pode descer abaixo de 11,5px.
- **Mono** (400, 0.92em): só para formato literal digitável, dentro de `<code>`
  com borda e fundo — por exemplo `AAAA-MM;valor` na importação em lote.

### Named Rules

**A Regra do Degrau Existente.** A escala tem nove degraus e eles bastam. Antes
de escrever um `font-size` novo, encontre o degrau cujo **trabalho** é o seu:
dado em tabela → 13,5; dentro de um controle → 13; texto de apoio → 12,5;
formulário → 12; rótulo em caixa alta → 11,5. Um décimo tamanho não cria
hierarquia, só ruído. A fase 3 fechou os dois desvios que a fase 2 tinha
registrado (10,5px e 18px): hoje o arquivo não tem nenhum tamanho de uso único
fora das exceções nomeadas.

**A Regra do Piso de 11,5px.** Nenhuma superfície de HTML desce abaixo de
11,5px — e agora sem asterisco: o único texto menor no sistema é o rótulo do
eixo Y do gráfico (11px), que é SVG desenhado em px reais.

**A Regra da Fonte Local.** A fonte mora no servidor. Nada no HTML ou no CSS
pode voltar a apontar para `fonts.googleapis.com` — numa rede sem saída a fonte
simplesmente não chega, e o `<link>` ainda contaria quem abriu o painel.

**A Regra do Algarismo Tabular.** Toda coluna de dinheiro, todo eixo numérico,
toda data em coluna e todo campo numérico levam `.num`
(`tabular-nums lining-nums`). Sem isso, a coluna alinhada à direita dança a cada
centavo — e a coluna de validade dança a cada dia.

**A Regra do Mono Literal.** Monoespaçada só onde o texto é um formato que a
pessoa vai digitar exatamente. Nunca como fantasia de "coisa técnica".

**A Regra do Peso, Não do Cinza.** Precisa destacar? Suba o peso (600) ou o
tamanho. Nunca crie um cinza mais claro.

**A Regra da Medida.** Todo texto de apoio tem teto de medida, senão uma nota de
12px corre ~170 caracteres numa tela de 1440. O teto da casa é **78ch**
(`.campo__nota`, `.saldo__nota`, `.aviso`); o objeto do contrato, que é prosa
longa dentro de uma faixa, usa **72ch**. Texto de apoio novo herda 78ch em vez
de inventar um teto próprio.

## Layout

**Shell.** Grade de duas colunas: sidebar fixa de 232px (`--sidebar`) e conteúdo
em `minmax(0, 1fr)`, com `min-height: 100vh`. A sidebar é `sticky` no topo, altura
`100vh`, coluna flex — logo, nav (cinco itens: Painel, Sugestões, Contratos,
Certidões e, só para admin, Administração), e o pé (usuário + sair) empurrado por
`margin-top: auto`.

**Área central.** Topbar `sticky` (z-index 5, `padding: 14px 24px`) com título à
esquerda, meta ao lado e um slot de ações à direita (`.topbar__acoes`,
`margin-left: auto`). Abaixo, a página: largura total até 1200px (`--conteudo`),
`padding: 24px`, coluna flex com `gap: 20px` entre cartões.

**Ritmo.** Escala base de 4px, com passos de meia-unidade permitidos dentro de
controles quando a altura da linha manda (9px, 13px, 13,5px). Os valores
canônicos: 20px é a sangria horizontal de cartão, de cabeçalho de grupo e de
primeira/última coluna de tabela; 12px é a sangria interna de célula; 24px é a
moldura da página; 8px e 6px são as folgas entre controles; `gap: 20px` entre
cartões.

**Densidade.** A linha de tabela vale 40px — 10px de sangria vertical mais 19,5px
de linha de texto. A coluna de ações mantém os mesmos 40px com botões de 28px
mais 6px de folga. A **escala de controles é 32 / 28 / 26** e não tem 24: 32px é o
padrão, 28px o botão que cabe na linha da tabela, 26px o botão voltar e o botão
interno do campo de arquivo.

**Responsivo.** Um único ponto de quebra, em 900px: a grade vira uma coluna e a
sidebar deixa de ser lateral — vira faixa horizontal com rolagem (`overflow-x:
auto` **mais** `min-width: 0`, sem o qual a largura natural da faixa, ~678px com
cinco itens, estica a coluna do grid e devolve rolagem à página inteira). Logo a
118px, nav em linha, dados do usuário escondidos. Topbar e página caem para 16px
de sangria; o resumo do contrato empilha; a lista de alertas troca a coluna fixa
do selo por selo sobre a mensagem; a coluna de ações ancorada volta a ser
`static`, porque em 375 ela comeria dois terços da largura visível.

### Named Rules

**A Regra da Linha de 40px.** Uma linha de tabela vale uma linha de altura. Nada
dentro dela quebra em duas: nome longo trunca em 34ch (`.truncar`), dado de
identificação curto trunca em 12ch (`.truncar--curto`), e os dois guardam o texto
inteiro no `title`; protocolo, CNPJ e ações não quebram linha.

**A Regra da Rolagem Interna.** Conteúdo largo demais rola na própria caixa
(`.tabela-wrap`, `.grafico`), nunca na página — e **`position: relative` no
wrapper é parte da regra, não enfeite**. Sem ele o bloco continente dos
descendentes `position: absolute` (os `span.sr-only` dentro das células) é o
documento: um sr-only lá pelo meio de uma tabela de 1463px estica a rolagem do
documento mesmo com a tabela recortada dentro do cartão — medido em Chrome,
`scrollWidth` 678 num viewport de 375 na tela de Certidões. Rolagem interna só é
interna se o que está posicionado dentro dela também for. Toda tabela mora dentro
de um `.tabela-wrap`, inclusive as tabelas pequenas de cadastro.

**A Regra do SVG em Tamanho Natural.** O gráfico é desenhado em px reais e rola
na horizontal se passar da largura do cartão. Esticar por `width: 100%` levaria o
texto do eixo junto, e os 11px legíveis virariam 4px ou 30px conforme o número
de meses.

**A Regra da Coluna Larga Demais.** Antes de ancorar uma coluna, faça a tabela
caber: dado repetido em toda linha vira **cabeçalho de grupo**, dado de
identificação vira truncamento curto, rótulo comprido vira texto curto. A matriz
de certidões saiu de 10 colunas (~1325px, com VALIDADE escondida) para 8 colunas
que cabem em 1440. A ancoragem é rede de segurança, não solução de largura.

## Elevation & Depth

O sistema é **plano por decisão**. Desde a fase 3 existe **um único valor de
sombra no arquivo inteiro** (`0 1px 2px rgb(16 24 40 / .06)`, o token `--sombra`):
o botão carregava uma irmã literal a `.05` de alpha, indistinguível a olho nu mas
um segundo nível escondido que o próximo controle copiaria; ela foi colapsada em
`var(--sombra)`. Cartão e controle usam a mesma sombra; ela some no `:active` e no
`:disabled` para dar a sensação de afundar. Nada mais levanta.

A profundidade real é feita por **borda de 1px e camada tonal**: `--linha`
separa superfícies, `--linha-forte` fecha a linha de totais e desenha a borda dos
controles, e `--superficie-2` marca as camadas secundárias (zebra, cabeçalho,
cabeçalho de grupo, rodapé). O único efeito de material do sistema é a topbar
translúcida com `backdrop-filter` — e ela existe para que o conteúdo *passe por
baixo* ao rolar, não para brilhar.

### Shadow Vocabulary

- **Superfície** (`box-shadow: var(--sombra)` = `0 1px 2px rgb(16 24 40 / .06)`):
  cartões, botões e `.btn`. Um só nível, um só valor. Removida em `:active` e
  `:disabled`.
- **Costura do painel** (`box-shadow: inset 0 1px 0 var(--acento-linha)`): o fio
  claro no topo da linha expandida, que costura o painel à linha que o abriu.
- **Sinal de borda da coluna ancorada**
  (`box-shadow: inset 1px 0 0 var(--linha-forte)`): **não é sombra**, é a borda
  esquerda pintada por outro caminho — `border-left` numa célula `position:
  sticky` sob `border-collapse: collapse` não pinta no Chrome (conferido em
  captura: nenhuma linha aparecia). Só existe com a classe `--rola` posta pelo
  React ao medir `scrollWidth > clientWidth`; numa tabela que cabe inteira seria
  uma divisória inventada.

### Named Rules

**A Regra do Nível Único.** Um valor de sombra no sistema inteiro. Se algo
precisa se destacar, ele ganha borda, camada tonal ou o fundo do acento — não uma
sombra maior. `box-shadow: inset` para pintar uma borda que o navegador se recusa
a pintar não conta como segundo nível, e o comentário no CSS tem de dizer isso.

**A Regra do Momento Animado Único.** A interface tem um só momento animado: o
painel que se abre sob a linha da tabela (`abrir-painel`, 140ms,
`cubic-bezier(.16, 1, .3, 1)`, opacidade + 3px). Fora dele, só transições de cor
de 120ms em hover de botão, borda de campo e fundo de linha. Sob
`prefers-reduced-motion`, a animação some e toda transição cai para 0,01ms.

## Shapes

Cantos calmos, três raios e nada de geometria decorativa.

- **Superfícies** (`--raio`, 8px): cartão, e o canto inferior do rodapé de cartão.
- **Controles** (`--raio-ctrl`, 6px): botão, campo, item de nav, aba (só os cantos
  de cima), botão interno do campo de arquivo, chip de aviso, bloco de erro, e o
  `border-radius` do anel de foco.
- **Micro** (4px, 4 usos): alvos de clique embutidos na própria célula
  (botão-valor, botão-nome), o `<code>` e a chave de 11px da legenda do gráfico —
  que era 3px de uso único e foi normalizada. É o raio de tudo que é menor que um
  controle e mora dentro de outra coisa.
- **Pílula** (999px, 5 usos): selo semântico, ponto de estado, **ponto dentro do
  selo**, avatar do usuário e o polegar da barra de rolagem. Só onde a forma
  redonda é o significado.

Sobrou **uma** exceção literal, num elemento pequeno demais para o raio de micro:

- **Barra da marca** (`border-radius: 0 2px 2px 0`): a barra de 3px × 20px do
  item ativo da nav. Só os cantos da direita são arredondados — o lado esquerdo
  encosta na borda do sidebar. 2px é o teto real: num elemento de 3px de largura,
  4px passaria de metade e a barra viraria uma cápsula.

Zeramento explícito (`border-radius: 0`) aparece na linha de alerta e no anel de
foco dela: a linha ocupa a largura inteira da lista, e um canto arredondado ali
brigaria com o divisor de 1px acima e abaixo. Não é um degrau da escala.

**Bordas.** Praticamente tudo que tem forma tem borda de 1px: controle
(`--linha-forte`), superfície e divisor (`--linha`), chip semântico (a linha da
própria semântica). A borda é o instrumento principal de separação — antes da
sombra e antes do espaço.

**Foco.** Anel de 2px em `color-mix(in srgb, var(--acento) 40%, transparent)`,
`outline-offset: 2px`, derivado do próprio token de acento: trocar `--acento`
leva o anel junto. Campos ganham a borda inteira em `--acento` no foco, com
offset de 1px. A lista de alertas usa `outline-offset: -2px` para que o anel
caiba dentro da linha.

**Barra de rolagem.** Faz parte do mundo: `scrollbar-width: thin`, polegar em
`--linha-forte` com borda de 3px na cor do fundo, arredondado em pílula.

### Named Rules

**A Regra da Borda Antes da Sombra.** Separação se faz com uma linha de 1px. A
sombra existe para dizer "isto é uma superfície", não para hierarquizar.

## Components

### Botões

Sólidos, baixos, retangulares de canto suave — um controle de app financeiro, não
um botão de marketing. A base é aplicada ao elemento `button` **e** à classe
`.btn`, de propósito: uma âncora (o download do CSV, o PDF da certidão) precisa
ser um botão de verdade, e o seletor de elemento sozinho não alcança `<a>`.

- **Forma:** cantos de controle (6px), altura 32px, `padding: 0 12px`,
  `gap: 6px` entre ícone e rótulo, 13px/500.
- **Secundário (o padrão):** superfície branca, borda `--linha-forte`, texto
  `--texto`. Hover troca fundo para `--hover` e borda para `--linha-hover`;
  `:active` afunda para `--pressionado` e perde a sombra.
- **Primário:** fundo `--acento` com texto branco; hover `--acento-forte`;
  `:active` `--acento-mais`. Um por contexto de decisão.
- **Destrutivo:** fundo `--acao` com texto branco. Só quando a ação é
  destrutiva de verdade (revogar uma certidão, por exemplo).
- **Pequeno:** 28px de altura, 12,5px — o botão que cabe na linha da tabela e o
  botão de "mostrar mais" no rodapé do cartão.
- **Voltar:** sem borda, sem sombra, sem fundo, texto `--texto-2` com ícone;
  ganha o fundo `--hover` só no hover. Mora na topbar da página do contrato.
- **Desabilitado:** texto `--texto-fraco`, sem sombra, `cursor: not-allowed`. O
  fundo não muda — o que muda é a cor do texto e do ícone.
- **Linha de ações do editor** (`.editor__acoes`): flex com quebra e `gap: 8px`.
  As ações do formulário ficam **na mesma linha, na ordem em que se usam**
  (preparar antes de gravar); empilhadas na vertical, um bloco de retorno entre
  elas empurra o primário para fora do campo de visão.

### Campos

- **Estilo:** altura 32px, `padding: 0 10px`, borda `--linha-forte`, raio de
  controle, 13px. Hover sobe a borda para `--linha-hover`.
- **Foco:** a borda inteira vira `--acento`, com o anel de foco por fora.
- **Larguras nomeadas:** curta (84px), média (168px), **larga (320px)** e
  numérica (alinhada à direita, tabular). A larga entrou na fase 3 para o
  conteúdo que é **frase e não dado** — nome de entidade, motivo de uma decisão.
  Todas levam `max-width: 100%` e `min-width: 0`.
- **Campo de arquivo** (`.entrada--arquivo`): o único controle do sistema que traz
  um botão do próprio navegador dentro de si. `::file-selector-button` é
  estilizado como botão secundário de 26px, senão o formulário ganha um botão
  cinza de outro mundo no meio de uma linha de controles de 32px. A altura vira
  `auto` (quem manda é o botão interno) e 2px de sangria vertical devolvem os
  mesmos ~32px da linha.
- **Área de texto:** desfaz a altura fixa, ganha 480px de teto e `resize:
  vertical` — são duas colunas de dado colado, não texto corrido.
- **Estrutura:** rótulo em cima (600, 12px, `--texto-2`), campo, nota ou erro
  embaixo (12px; a nota com teto de 78ch, o erro em `--acao`). Formulário em
  linha (`.form-inline`, alinhado pela base, com `min-width: 0` em cada campo
  para o flex poder encolher) ou em bloco (`.editor`, uma coluna).

### Cartões

- **Forma:** raio de superfície (8px), borda `--linha`, sombra de nível único.
- **Cabeça:** 13px 20px, título de 14px/600, dica em 12,5px `--texto-2`, ações
  empurradas para a direita. Um selo de veredito na cabeça **não encolhe**
  (`flex: none`): quem cede espaço é o título, que quebra em duas linhas.
- **Corpo:** 14px 20px. Tabela e gráfico entram sem corpo, colados na borda.
- **Rodapé:** 14px 20px, fundo `--superficie-2`, cantos inferiores acompanhando
  o cartão. É onde mora o formulário de criação e o botão "mostrar mais".

### Tabelas

O componente central do sistema. Densa, zebrada, com cabeçalho em rótulo de caixa
alta e todo dinheiro tabular à direita.

- **Cabeçalho:** fundo `--superficie-2`, texto `--texto-2` em 11,5px/600 caixa
  alta com tracking 0.04em, alinhado à esquerda, sem quebra de linha.
- **Célula:** 10px 12px, texto `--texto-2`, alinhamento vertical ao meio; a
  primeira e a última coluna ganham 20px de sangria para casar com o cartão.
- **Cabeçalho de grupo** (`tr.grupo > th[scope="rowgroup"]`): um `<tbody>` por
  entidade, aberto por uma linha que atravessa a tabela (`colSpan` = número de
  colunas) com o nome e o papel. Tira do corpo as colunas que se repetiam em toda
  linha, e o leitor de tela anuncia a entidade ao entrar nas linhas dela. Mesma
  faixa `--superficie-2` do `thead`, mas em `--texto` 13,5px/600 — é dado, não
  rótulo de coluna. Borda superior de 1px repõe o divisor que o
  `tr:last-child td { border-bottom: 0 }` do grupo anterior deixa de pintar. A
  zebra recomeça em cada grupo.
- **Zebra:** por classe (`.par`), nunca por `:nth-child` — as linhas de painel
  expandido entram no meio do `tbody` e embaralhariam a contagem.
- **Hover:** linha inteira para `--hover`, com transição de 120ms.
- **Linha abrível:** cursor de ponteiro **mais** um botão de verdade no nome
  (600, alvo de clique no próprio texto), que leva ao mesmo destino pelo teclado
  sem custar uma coluna "Abrir".
- **Coluna de ações ancorada** (`.col-acoes--fixa`): `position: sticky; right: 0`
  com fundo **opaco por estado da linha** (branco, zebra, hover) — transparente
  ela mostraria as outras colunas passando por baixo do texto. O cabeçalho
  ancorado repete a faixa do `thead`. É **rede de segurança**: só faz diferença
  quando a tabela de fato não cabe (zoom, janela estreita, nome comprido), e
  volta a `static` abaixo de 900px.
- **Totais:** `tfoot` com borda superior `--linha-forte`, fundo `--superficie-2`,
  texto `--texto` em 600. O rótulo é um `th scope="row"` normalizado para não
  herdar o negrito centralizado do navegador.
- **Negativo:** só onde negativo é um problema — cor de ação, e nunca só a cor:
  quem usa põe o ícone de alerta com `title` ao lado.

### Estado (badge)

Ponto de 7px em pílula mais rótulo, sempre juntos, em `--texto`. Prevista e "em
aberto" usam o cinza `--previsto`; protocolada, `--texto-2`; NF emitida, o
acento; recebida e atestado, `--ok`; provisório, âmbar. Exceção (cancelada,
desistida) fica em `--texto-2` riscado, com o traço em `--texto-fraco`. Congelada
acrescenta o ícone de cadeado com `title` explicando o que congelou.

### Selo semântico

O irmão do estado: pílula com borda que **carrega o rótulo do tipo**, em quatro
níveis e nada além deles — neutro (`--superficie-2`), ok, atenção, ação. Estrutura
de três partes, e as três importam:

- `.selo__ponto` — 7px em pílula, cor por `currentColor`, que faz o ponto seguir o
  modificador do chip sem uma regra por nível. É o que junta as duas gramáticas da
  casa: o chip diz a palavra, o ponto repete a semântica em forma, e quem não
  distingue as cores lê a mesma coisa.
- `.selo__texto` — o rótulo num filho de **bloco** com `min-width: 0`. As
  reticências precisam disso: `text-overflow` só funciona em caixa de bloco, e o
  `.selo` é `inline-flex` — declarado lá, o "…" nunca era desenhado e o rótulo
  aparecia cortado no meio da letra, parecendo defeito de renderização. O ponto e
  o ícone ficam de fora, inteiros.
- um `sr-only` com a explicação completa, **dentro** do chip. O chip é um `<span>`
  não focável: tooltip não existe para teclado nem para leitor de tela. O `title`
  fica na célula, só como conveniência de mouse (em `<td>` ele não é anunciado,
  então não duplica).

### Semáforo de certidão (componente-assinatura da fase 3)

O selo aplicado à pergunta "dá para protocolar hoje?". Quatro cores, **cinco
rótulos**, porque a cor diz a gravidade e o rótulo diz o trabalho:

| Nível | Rótulo | O que a pessoa faz |
|---|---|---|
| ok | **Em dia** | nada |
| atenção | **Vence em N dias** (ou "Vence hoje" / "Vence amanhã") | renove antes do próximo protocolo |
| ação | **Vencida em dd/mm/aaaa** | renove no órgão e arquive a emissão nova |
| ação | **Sem cobertura** | emita pela primeira vez |
| neutro | **Não se aplica** / **Não cobrada** | nada — declaração de alguém, ou tipo fora da cobrança |

"Vencida em dd/mm/aaaa" e "Sem cobertura" são o mesmo vermelho de propósito (a
entidade está travada nos dois casos) e não o mesmo trabalho. O cinza nunca vira
vermelho, e a data da emissão que caducou fica na explicação, não no rótulo —
dentro do selo ela alargaria a coluna inteira.

### Matriz de certidões

Tabela entidade × tipo, oito colunas, um `<tbody>` por entidade. A leitura é de
cima para baixo dentro de cada grupo; o número da certidão trunca em 12ch
(`.truncar--curto`) porque passa de 30 caracteres, não se lê por inteiro na
tabela e era ele que empurrava a coluna de ações para fora do cartão — o começo
distingue uma emissão da outra, e o inteiro fica no `title` e no PDF. Uma faixa
de `.totais` acima conta os quatro níveis do semáforo. Cada linha vermelha sem
emissão ganha a porta de saída ("Não se aplica" pelo par), senão ela ficaria
vermelha para sempre travando o checklist.

### Bloco de sugestão (retorno de leitura)

O retorno da leitura do PDF (`.sugestao`, `role="status"`). Não é bloco de erro
(nada falhou) nem de sucesso (nada foi gravado): é uma **proposta que o humano
confere antes de enviar**, e por isso não herda `.erro` nem `.resultado`. Grade
com `gap: 8px` e `justify-items: start`; cada campo reprovado vira um chip de
atenção próprio dentro de uma lista sem marcador, que é exatamente o que ele é —
uma pendência deixada para a pessoa. Fica **abaixo** da linha de ações: é
consequência do que se acabou de clicar, e ali o `role="status"` continua sendo
anunciado sem partir a linha de botões em duas.

### Lista de alertas

Grade de duas colunas — 152px fixos para o selo, resto para a mensagem — e não
flex: com selos de larguras diferentes, as mensagens ficariam com a margem
esquerda serrilhada e a lista perderia a leitura de cima para baixo. Cada item é
um botão de linha inteira, sem borda nem fundo, que ganha `--hover`. **Teto de
cinco itens visíveis**, ordenados por gravidade (ação, atenção, neutro) com ordem
estável dentro de cada nível; o resto entra por "Mostrar os outros N" no rodapé do
cartão, e volta por "Mostrar só os 5 primeiros". Nada é escondido de vez — cinco é
o que deixa o conteúdo seguinte entrar na primeira tela em 1440. Em telas estreitas
o selo sobe para cima da mensagem.

### Checklist de protocolo

Cartão da aba Protocolo da página do contrato. Cabeça com a pergunta ("Pronto para
protocolar?"), o **selo de veredito** (ok "Pronto" / ação "Pendências", que não
encolhe) e o botão de escape para a tela de Certidões. Corpo com a frase do
veredito — nota neutra quando está tudo em dia, chip `.aviso` âmbar quando falta
alguma coisa, sempre nomeando a entidade (habilitação é por CNPJ). Depois, a
tabela dos tipos exigidos com o mesmo selo de quatro níveis. O veredito só aparece
quando há o que verificar: lista vazia não é "Pronto".

### Abas

Faixa de 36px sobre uma linha de 1px, com a aba selecionada em `--acento` e uma
borda inferior de 2px na mesma cor, sobreposta à linha do grupo por
`margin-bottom: -1px`. Aba não selecionada é `--texto-2` e ganha
`--superficie-2` no hover. Padrão ARIA completo: a faixa é uma parada de tabulação
(roving tabindex) e ←/→/Home/End andam por ela com ativação automática.

### Navegação (sidebar)

Cinco itens de 13,5px/500 em `--texto-2`, raio de controle, ícone herdando a cor
do texto. Hover: fundo `--superficie-2`. Ativo (`aria-current="page"`): fundo
`--acento-fundo`, texto e ícone em `--acento`, peso 600, e a barra decorativa de
3px em laranja puro da marca encostada na borda esquerda do sidebar. O pé traz o
avatar de inicial (28px, pílula), nome, perfil e o botão de sair.

### Painel inline (componente-assinatura)

O substituto do `prompt()`/`confirm()`. Uma linha nova abre **sob** a linha da
tabela, com fundo `--acento-fundo`, sangria de 16px 20px e a costura clara no
topo; dentro dela, um título de 12,5px/600, o formulário, um chip `.aviso` dizendo
o que a ação preserva, e o rodapé de ações. `Escape` fecha. É o único elemento
animado do sistema. O seletor é prefixado com `.tabela tbody` de propósito, senão
a regra da célula venceria e o painel herdaria a sangria apertada.

### Gráfico SVG

Barras empilhadas desenhadas em px reais dentro do cartão, com legenda no pé.
Previsto em `--previsto`; medido em `--acento`; demais séries em `--acento-mais`.
Grade em `--linha`, linha-base em `--linha-forte`, eixos em `--texto-2` a
11–11,5px. Competência sem lançamento vira um **talo no zero** em
`--linha-forte`, nunca uma barra de altura zero. Provisório (protocolado sem
atestado) ganha hachura clara em `--atencao-linha` por cima da própria cor da
série, mais selo e rótulo de eixo em âmbar — sobre branco, onde o âmbar aparece.

### Faixas de número (saldo, totais e resumo)

Três parentes. **Saldo** mostra a fórmula como conta legível — vigente − medido =
saldo, com os três números na tela, o total em 22px/600 e a regra em texto de
12px vinda do servidor; se o saldo é negativo, o total vira cor de ação.
**Totais** põe grandezas lado a lado com rótulo próprio (15px/600), sem a leitura
de conta — serve tanto às séries do gráfico quanto à contagem do semáforo.
**Resumo** do contrato traz o objeto (prosa, 72ch) à esquerda e o valor vigente à
direita, também no degrau Número.

### Vazios

Nunca uma tela em branco: título em 600 mais uma frase que diz o que fazer
("Nenhuma medição — crie a primeira abaixo"), com 32px de palco. A variante curta
existe para o vazio que é **boa notícia** (nenhum alerta): mesma linguagem, sem o
palco. E vazio nunca mente por omissão: quando a leitura falhou, o cartão diz que
não conseguiu verificar — nunca que está tudo em dia.

### Ícones

Todos desenhados à mão em `icones.tsx`: grade 24, traço 1,6 (1,7 no tamanho
pequeno), pontas e junções arredondadas, sem preenchimento, herdando
`currentColor`. Dois tamanhos: 18px padrão e 15px pequeno. Ícone decorativo é
`aria-hidden`; ícone que carrega significado recebe `titulo` e vira
`role="img"` com `<title>`.

## Do's and Don'ts

### Do:

- **Do** consumir `tokens.css` para toda cor, raio, sombra e medida. Se faltar um
  tom, ele nasce lá — nunca no `.tsx`.
- **Do** usar `--acento` para tudo que é interativo e reservar `--marca` para a
  logo e o detalhe decorativo não-textual.
- **Do** marcar dinheiro, data e número com `.num` e alinhar à direita com `.col-num`.
- **Do** dizer estado com **forma + rótulo** (ponto + texto, ou selo que carrega
  o tipo). A cor é reforço, nunca o recado — e o rótulo diz o **trabalho**, não só
  a gravidade.
- **Do** pôr a explicação longa de um chip como `sr-only` dentro dele, com o
  `title` na célula. Tooltip não existe para teclado nem para leitor de tela.
- **Do** envolver toda tabela num `.tabela-wrap` (com `position: relative`),
  inclusive as pequenas de cadastro.
- **Do** fazer a tabela caber antes de ancorar coluna: cabeçalho de grupo
  (`tr.grupo > th[scope=rowgroup]`, um `<tbody>` por entidade) elimina o dado que
  se repete em toda linha.
- **Do** truncar com `.truncar` (34ch) ou `.truncar--curto` (12ch) e guardar o
  texto inteiro no `title`.
- **Do** dar teto de medida (78ch) a todo texto de apoio novo.
- **Do** abrir formulário inline ou painel sob a linha para pedir dado. Toda
  entrada tem rótulo, foco, `Escape` e cancelamento de verdade.
- **Do** limitar lista longa a ~5 itens visíveis com "Mostrar os outros N" — nunca
  esconder de vez.
- **Do** escrever vazio instrutivo, e distinguir "verificamos, está tudo em dia"
  de "não conseguimos verificar".
- **Do** desenhar ícone novo em `icones.tsx`, na mesma grade 24 e traço 1,6.

### Don't:

- **Don't** usar `--marca` (`#FF6500`) atrás de texto ou como fundo de controle —
  ele faz 2,96:1 sobre branco.
- **Don't** inventar um terceiro cinza de texto para hierarquia. Suba o peso ou o
  tamanho. `--texto-fraco` só serve para desabilitado e traço de riscado.
- **Don't** usar vermelho, âmbar ou verde fora do significado, nem dar fundo
  sólido a um selo semântico — os quatro níveis são chip claro.
- **Don't** declarar `text-overflow: ellipsis` num contêiner `inline-flex`: o
  rótulo precisa de um filho de bloco com `min-width: 0` (`.selo__texto`).
- **Don't** deixar um `.tabela-wrap` estático: um `sr-only` absoluto lá dentro
  estica a rolagem do documento inteiro.
- **Don't** ancorar uma coluna para resolver excesso de largura — resolva a
  largura; a âncora é rede de segurança.
- **Don't** chamar `prompt()`, `alert()` ou `confirm()`.
- **Don't** usar emoji ou glifo unicode fazendo as vezes de ícone.
- **Don't** acrescentar um segundo valor de sombra, nem sombra para hierarquizar.
- **Don't** zebrar com `:nth-child` — as linhas de painel expandido entram no meio
  do `tbody` e embaralham a contagem. Use `.par`.
- **Don't** desenhar barra de altura zero num gráfico: competência sem lançamento
  é talo no zero.
- **Don't** esticar o SVG do gráfico com `width: 100%` — o texto do eixo vai
  junto e perde a legibilidade.
- **Don't** apontar fonte, CSS ou script para fora da rede interna.
- **Don't** introduzir dark mode nesta fase: o sistema declara `color-scheme: light`.

---

## Superfícies pendentes (não fazem parte do sistema)

Três telas da fase 1 ainda **não** foram passadas por este mundo visual e entram
no shell herdando só as regras de elemento nu (`button`, `input`, `a`, `table`):

- `frontend/src/Contratos.tsx` — 13 `style={{…}}` inline com cores literais fora
  do sistema (`#ddd`, `crimson`, `2px solid #333`) e tabela montada à mão sem
  `.tabela`; é a única tela que ainda aparece no censo de rolagem horizontal das
  capturas de revisão.
- `frontend/src/Admin.tsx` (4 estilos inline) e `frontend/src/Login.tsx` (2) —
  sem classes do mundo.

**Nada dessas telas é regra de design.** Elas são dívida conhecida: quando forem
retrabalhadas, devem passar a consumir `.cartao`, `.tabela`, `.btn`, `.campo` e
os tokens, exatamente como as telas das fases 2 e 3. O `frontend/src/index.css`
que sobrou da fase 1 (16px `system-ui`, `color-scheme: light dark`) também é
resto: `tokens.css` é importado depois, de propósito, para vencê-lo.

## Defeitos que a fase 3 carrega (não canonizados)

Registrados como dívida, não como regra. Nenhum deles deve ser imitado numa
superfície nova.

1. **Cabeçalho AÇÕES desalinhado.** Na matriz de certidões o `th` leva `.col-num`,
   mas `.tabela thead th` vence em especificidade e o rótulo fica à esquerda
   enquanto as células vão à direita (~200px de vão em 1440). É defeito de
   alinhamento, não estilo da casa; a correção é um seletor
   (`.tabela thead th.col-num`). Parado para T11.
2. **Falha no fio da coluna ancorada.** Com a matriz rolando, o
   `box-shadow: inset` da coluna fixa não é pintado na linha `tr.grupo` (o
   cabeçalho de grupo é um `th` com `colSpan`, sem célula ancorada), e a faixa de
   separação aparece interrompida. Cosmético, e só num estado que a matriz
   normalmente não alcança.
3. **Resto do reset de 900px.** O bloco responsivo devolve
   `.col-acoes--fixa { position: static; border-left: 0 }`, mas a borda naquela
   coluna nunca foi `border-left` — é `box-shadow: inset`, aplicado pela classe
   `--rola`. A declaração não faz mal e não faz nada: é linha morta, não padrão.
4. **Selo cortado em 375 sem sinal.** Na matriz em telas estreitas o chip de
   SITUAÇÃO trunca no meio da palavra ("Sem", "Venc") e nada indica que há mais
   tabela à direita — a classe `--rola` só pinta na coluna ancorada, que em 375 é
   `static`. Herdado, e a única forma em que o sistema hoje admite um estado
   chegando perto de "cor pura".

O `ignoreValues` de raio `2px` em `.impeccable/config.json` é silenciamento de
detector para a barra da nav, que já é exceção nomeada aqui. **Não é** licença
para um quinto raio.

## Divergências entre o contrato de direção e o construído

Registradas porque a construção venceu, e por bom motivo em cada caso:

1. **Fonte.** O contrato dizia "Hanken Grotesk (Google Fonts)". O construído
   **auto-hospeda** os `.woff2` em `public/fonts` com `@font-face` de peso
   variável `100 900` e `preload` no HTML — "rede interna, sem nuvem" do
   PRODUCT.md; um `<link>` externo simplesmente não chegava.
2. **Segunda série do gráfico.** O contrato previa só "medido = acento". O
   construído acrescentou `--acento-mais` para reajuste e projeto, porque duas
   séries em laranjas vizinhos não se distinguiam.
3. **Terceiro tom de texto.** `--texto-fraco` não estava no contrato; foi criado
   e **cercado** (só desabilitado e riscado) em vez de virar um cinza de
   hierarquia.
4. **Cabeçalho de tabela.** Contrato: 12px/600 caixa alta. Construído: 11,5px/600
   com tracking 0.04em.
5. **Responsividade.** O contrato não a especificava. O construído tem um ponto
   de quebra em 900px que converte a sidebar em faixa horizontal rolável.
6. **Escala de espaçamento.** O contrato pedia escala estrita de 4px. O
   construído mantém 4px na moldura (8/12/16/20/24) e usa meias-unidades ópticas
   dentro de controles e células (9px, 13px) para fechar a linha de 40px.
7. **Quarto nível de selo.** O contrato da fase 2 previa três níveis semânticos.
   A fase 3 abriu o `ok`: "em dia" é uma afirmação positiva que o painel de
   certidões precisa fazer, e o verde já estava declarado e reservado.
8. **Nav de cinco itens.** O contrato da fase 2 desenhou quatro. Certidões entrou
   sem guarda de perfil (a tela é `ver_paineis`); as permissões aparecem dentro
   dela, não na navegação.
9. **Carimbo de frescor.** O slot existe (`.topbar__acoes`), mas nada é
   renderizado nele — o dado importado só chega na fase 6.

## Valores de uso único — censo da fase 3

O censo da fase 2 apontou três valores de uso único e **os três foram resolvidos
na fase 3**, sem virar regra:

| Valor | Onde estava | Desfecho |
|---|---|---|
| `font-size: 10.5px` | `.nav__tag` | **Removido.** Era CSS morto e o único texto abaixo do piso de 11,5px. Se a tag voltar, nasce no degrau Label. |
| `font-size: 18px` | `.resumo__valor strong` | **Colapsado em 15px** (degrau Número): o valor vigente é uma grandeza entre outras; Display fica com o total do saldo, que mora na mesma página. |
| `border-radius: 3px` | `.legenda__chave` | **Normalizado para 4px** (degrau Micro). |
| `box-shadow: 0 1px 2px rgb(16 24 40 / .05)` | `button`, `.btn` | **Colapsado em `var(--sombra)`.** Era um segundo nível de sombra escondido no arquivo. |

O censo atual não encontra novo valor órfão. Os tamanhos, raios e sombras
repetidos são degraus reais das escalas; as duas exceções que sobram — `11px` no
eixo Y do gráfico e o raio `0 2px 2px 0` da barra de 3px da nav — continuam
nomeadas, com justificativa física.
