# 04 — Tours no navegador (fase 2, testes de quebra 10/10/2026)

Ambiente: frontend-dev :5173 → backend-dev :8080 com `DASH_GRAPH_SIMULADOR=dados/correio-simulado` e
`DASH_SEM_JOBS=1` (conferido na linha de comando do processo). Banco de dev restaurado de
`dashboard-pre-fase1.db` às 15:47; pastas de documentos copiadas da produção (certidoes, espelhos, frc, notas,
protocolos, regularidades), sem banco, backups nem segredos. Saída do simulador da fase 1 arquivada em
`fuzz/saidas/correio-simulado-fase1/`.

Severidade: alta = dinheiro errado ou e-mail errado ao órgão; média = número inconsistente/fluxo confuso;
baixa = texto, layout.

## Tour 1 — Login e Início (engenharia)

### T-01 — Três definições diferentes de "obras ativas" (média)
- Medições: "21 obras ativas" (`medicoes.py:449`, estado='ativo').
- Início e Carteira: "4 de 19 obras ativas" (`avisos.ativos`, ativo SEM encerramento iniciado).
- Carteira, farol: "14 de 22 obras" (ativo + suspenso).
- Banco: 21 ativos (2 em encerramento) + 1 suspenso. O mesmo rótulo mostra três totais.

### T-02 — "Medido no mês" com duas regras na mesma sessão (média, conhecido)
- Início: "Medido em outubro · até dia 10 R$ 21.516.276,85 ▼ 97% sobre 01 a 10 de setembro"; gráfico
  "setembro R$ 765.934.780,63" — conta pela data de LANÇAMENTO, e a carga do legado (22–25/09) caiu toda em
  setembro. Ninguém mediu R$ 765 mi em 10 dias.
- Carteira: "medido no mês R$ 0,00 (competência 10/2026)" — conta pela competência.
- Já era pendência conhecida ("medido por data de lançamento"); o tour confirma que a comparação do Início é
  enganosa (▼97%).

### T-03 — Formulário de login (ok)
- Senha errada: mensagem única e clara. Senha certa entra. (Uma tentativa minha falhou por foco do campo,
  não por defeito da tela.)

## Tour 2 — Medições e a página da medição em 5 etapas

### T-04 — Valor de medição do espelho editável depois da nota, sem aviso nenhum (alta)
- Medição 631 (Estações BRT 7ª, nascida do espelho nº 7, notas 2315+2318 casadas somando R$ 9.384.834,18,
  estado Nota emitida).
- "Editar o valor" → `1,00` → "Valor protocolado gravado." A etapa 3 continua dizendo "notas completas" e
  "confere" nas duas notas; nenhum aviso no Início/Avisos; a Carteira caiu de R$ 10.223.826,78 para
  R$ 838.993,60 em "nota emitida esperando protocolo". Se protocolasse assim, o valor congelaria em R$ 1,00.
- Causa: `valorEditavel` (`MedicaoAtos.tsx:24-28`) só trava o protocolado em `espelho_gerado`/`espelho_enviado`;
  em `nota_emitida` libera. O servidor também aceita.
- Esperado: valor da medição do espelho segue o espelho (gerar de novo para mudar), ou no mínimo divergência
  valor × espelho × notas vira aviso crítico.
- Valor devolvido a R$ 9.384.834,18 depois do teste.

### T-05 — Linha do tempo não mostra edição de valor (baixa)
- Depois de duas edições de valor, a linha do tempo segue com os mesmos 3 acontecimentos; só a auditoria
  registra.

### T-06 — Mensagem de valor inválido sem acento e sem ensinar o formato (baixa)
- `1234.56` → "Valor monetario invalido: '1234.56'". Esperado: "Use vírgula nos centavos: 1.234,56".

### T-07 — Tabela de notas corta a coluna "Nota" a 1024 px (baixa)
- Etapa 3: a coluna com nº, data e situação da nota fica cortada; é preciso rolar na horizontal dentro do cartão.

### Observado e correto
- Etapa 4 diz "Falta a nota" com as notas só no RM: certo, o e-mail precisa do PDF, e a etapa 3 oferece
  "Anexar notas (PDF)".
- Cota: as obras com medição aberta são 100% Lotufo; Carteira "na cota" = valores cheios está certo aqui.

## Tour 3 — Envio da nota pelo navegador (simulador)

### T-08 — Cco preenchido na tela some do e-mail, sem aviso (alta)
- Medição 631: abri "Cco", adicionei `oculto-fase2@exemplo.com` (o chip apareceu), justificativa, "Enviar a nota".
- Simulador (`correio-simulado/enviados/1.json`): `"cco": []`. Para e Cc foram certos.
- Causa: `EnviarIn` de `api_notas_envio.py` não tem campo `cco`; o front mostra o campo e o descarta.
- Esperado: Cco chega ao e-mail, ou o campo não aparece nesse envio.
- (Confirma S5 do inventário, agora pela tela.)

### T-09 — Medição e reajuste da SINFRA saem em e-mails separados sem aviso (média)
- A tela "Enviar nota" diz: "Medição e reajuste vão juntos na SINFRA e na Prefeitura de VG".
- O protocolo 3 (criado em 07/10, só com a medição 631) foi enviado pela página da medição; o reajuste 632,
  com nota emitida no mesmo dia, ficou para trás como outro envio. Nada avisou "falta juntar o reajuste".
- `notas_envio.iniciar` aceita juntar, mas não junta nem cobra por padrão.
- Esperado (D9): na SINFRA/VG a irmã da mesma competência entra junto, ou o envio avisa antes de sair.

### T-10 — Clique duplo em "Enviar a nota" (ok)
- Clique duplo gerou UM POST e UM e-mail no simulador: o botão trava. A corrida F-01 só acontece com
  duas abas/duas pessoas ou chamada direta à API.

### T-11 — Mensagem velha fica na tela depois do envio (baixa)
- Depois do envio, o topo da página continuava com "Valor protocolado gravado." (da edição anterior), sem
  confirmação do envio.

## Tour 4 — Aguardando pagamento

### T-12 — Registrar nº do protocolo sem confirmação visual (baixa)
- "Registrar" grava (POST 200, some o "Sem protocolo SIGA"), mas não aparece "gravado".
- A coluna se chama "Nº do protocolo (SIGA)" também nas linhas da SINFRA, onde não há SIGA.
- Campo vazio: o front não deixa enviar (o apagamento F-14 só acontece pela API). Também não há como
  corrigir um número errado para "nenhum" pela tela.

## Tour 5 — Documentos e certidões

### T-13 — Página em branco com validade 31/12/2099 vira certidão vigente (alta)
- PDF válido sem texto (uma página em branco) → o sistema pede os dados à mão → Lotufo, Municipal,
  emissão 10/10/2026, validade 31/12/2099 → "Gravada".
- A matriz passou a mostrar Lotufo Municipal "Em dia até 31/12/2099" no lugar da real que vence em 17/10;
  o aviso "municipal vence em 7 dias" sumiu do Início e do envio; a página em branco entraria no ZIP de
  certidões mandado ao órgão.
- Esperado: teto de validade por tipo (municipal ~90 dias, federal 180) e aviso de PDF sem texto como
  pendência a conferir.
- (Confirma S9.)

### T-14 — Uploads ruins: recusas corretas, um texto técnico (baixa)
- Texto renomeado .pdf, PDF corrompido e arquivo vazio: os três recusados com mensagem clara.
- A do corrompido diz "(ValueError)"; o aviso do topo mostra só o último dos três.

## Tour 6 — Perfis (diretoria e admin)

### T-15 — Diretoria vê botões de escrita e recebe mensagem crua (média)
- Diretoria em "Enviar nota": vê "Enviar a nota →" e "Registrar envio feito por fora"; ao clicar,
  "Permissão necessária: editar_cadastros". Em /conta, a página inteira é só essa frase.
- Correto: a página da medição esconde os botões; /admin redireciona para o Início.
- (Confirma S16; /conta já estava no backlog.)

### T-16 — Administração sem trocar senha nem perfil (média)
- Usuários: só "Ativar/Desativar". Não há redefinir senha (V-14) nem mudar o perfil de alguém pela tela.

### T-17 — Auditoria com códigos internos e janela curta (baixa)
- Ações como "certidao.registrar", "frc.gerar", "medicao.remover_teste", "protocolo.link",
  "regularidade.competencia_corrigida" aparecem sem tradução.
- A tela mostra só os últimos 500 eventos; a sincronização horária do RM ocupa ~24 por dia.

## Tour 7 — Nova medição (espelho) e prazos

### T-18 — Espelho aceita competência 3 anos antes do contrato (média)
- MT-401 (início 03/2023, última medição nº 32 em 11/2025): nº 33 com competência 01/2020 e R$ 100,00 →
  a prévia montou o espelho sem aviso. Não gerei para não sujar o banco.
- Esperado: recusar competência antes do início da execução e avisar quando for anterior à última medição.
- Correto: nº já recebido é recusado; valores zerados são recusados.

### T-19 — Mensagens com código interno e inglês (baixa)
- "Medição 32 (execucao) já está recebida" (código "execucao").
- Pleito com 99999 dias: "Campos obrigatórios ausentes ou inválidos: dias (Input should be less than or
  equal to 3650)".

### Observado e correto
- Pedido de prorrogação: dias negativos barrados pelo navegador; ofício repetido vira aviso (como manda a
  regra); HTML na justificativa aparece como texto.

## Tour 8 — Celular (375 px)

### T-20 — Quebras de layout no celular (baixa)
- Início: "R$ 21.516.276,8" e o "5" final na linha de baixo.
- Página da medição: o nome da obra vira "Es…" porque divide a linha com órgão e "valores cheios".
- Sem rolagem horizontal da página.

## Console e servidor
- Nenhum erro de JavaScript nem 500 no servidor durante os tours. Os 4xx do console são os testes
  provocados; um 404 é a assinatura não cadastrada (`/api/correio/assinatura`), ruído.

## Estado do banco de dev depois da fase 2
- Medição 631 protocolada (envio pelo simulador, protocolo 3), nº "SIGA-TESTE-123" na 635, certidão 55
  (Lotufo municipal até 2099), pleito de prazo rascunho no MT-401 com ofício 137. Restaurar
  `dashboard-pre-fase1.db` antes da fase 3. Simulador: 1 e-mail (`enviados/1.json`), todos os
  destinatários reais ficaram só no arquivo.

## Resumo da fase 2

| Severidade | Achados |
|---|---|
| Alta | T-04, T-08, T-13 |
| Média | T-01, T-02, T-09, T-15, T-16, T-18 |
| Baixa | T-05, T-06, T-07, T-11, T-12, T-14, T-17, T-19, T-20 |
