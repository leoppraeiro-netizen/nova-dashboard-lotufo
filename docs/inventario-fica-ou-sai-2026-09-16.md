# Inventário de decisão: o que fica, o que sai, o que muda (2026-09-16)

Base da reestruturação: a dashboard NOVA. A antiga (`~/dev/lotufo-dashboard`) é fonte de funções.
Legenda da coluna "Hoje": A = só na antiga · N = só na nova · AN = nas duas · — = em nenhuma.
Legenda da recomendação: **FICA** (como está) · **MUDA** (fica, com ajuste descrito) · **ENTRA** (portar da antiga ou criar) · **SAI** (remover ou não trazer).

Responder por código: ex. "A3 sai, E2 entra com 90 dias, F4 depois".

## A. Home de quem opera (avisos)

| Cód. | Item | Hoje | Recomendação |
|---|---|---|---|
| A1 | Vigência do contrato vencida / vencendo (com aditivos) | N (60 d) · A (90/30 d) | **MUDA**: 90 d atenção, 30 d ação, como na antiga |
| A2 | Execução vencida / vencendo (separada da vigência) | N | **FICA** |
| A3 | Aniversário da data-base (60 d) | N | **MUDA**: vira o ciclo de reajuste do bloco E |
| A4 | Execução após data-base sem reajuste par | N | **SAI** até o cadastro por índice existir (84 de 102 são falso positivo) |
| A5 | Competência prevista sem medição protocolada | N | **FICA** |
| A6 | Medição parada no órgão (protocolada sem NF) | N (lista, 30 d visual) | **MUDA**: vira aviso com limiar 45 d e valor |
| A7 | NF emitida sem baixa | N (sem limiar, 588 casos) | **MUDA**: só com limiar (ex. 60 d) e só medições pós-carga |
| A8 | Saldo contratual abaixo de 10% / 5% | A | **ENTRA** (inclui saldo negativo, que a antiga ignorava) |
| A9 | Certidão sem cobertura / vencendo em 15 d | N · A (15 d) | **FICA** |
| A10 | Medição com mais de 60 d sem NF (por competência) | A | **SAI**: A6 e A7 cobrem, com a máquina de estados |
| A11 | Sugestões pendentes (contagem) | N | **MUDA**: contagem por obra, não total |
| A12 | Aviso com VALOR em risco e prazo em dias | — | **ENTRA**: todo aviso traz obra, dias e R$ |
| A13 | Registrar "já tratei" (ofício protocolado, certidão pedida) | — | **ENTRA**: aviso some por ato auditado, não reaparece igual |
| A14 | Gráfico consolidado mensal e CSV da carteira na home | N | **MUDA**: saem da home, vão para Relatórios (I) |

## B. Carteira e indicadores (diretoria)

| Cód. | Item | Hoje | Recomendação |
|---|---|---|---|
| B1 | Carteira: valor cheio × cota da Lotufo lado a lado | N (dica) · A (cota) | **MUDA**: cota como número principal, cheio na dica |
| B2 | Medido / Emitido / Recebido / A receber | N | **FICA** |
| B3 | Saldo = vigente − medido (execução), fórmula na tela | N | **FICA** |
| B4 | % executado por obra | A | **ENTRA** (medido execução ÷ vigente) |
| B5 | Billing: faturado bruto − medido | A | **SAI** por ora (a nova não guarda bruto da NF; retenção real mediana 7,6%) |
| B6 | Backlog em "meses de produção" | A | **ENTRA** (saldo ÷ média dos últimos 6 meses medidos) |
| B7 | Evolução do faturamento (acumulado/mensal, 12/6/3 meses) | A · N (previsto × medido) | **MUDA**: um gráfico só, em Relatórios |
| B8 | Carteira por contratante | A | **ENTRA** em Relatórios |
| B9 | Obras por status | A | **SAI** (a tabela já filtra) |
| B10 | Top 10 obras | A | **SAI** (tabela ordenável basta) |
| B11 | Mapa de MT com bolhas | A | **SAI** |
| B12 | Tabela WIP compacta (1 linha por obra + ponto de saúde) com drawer | A | **ENTRA** como tabela central da diretoria |
| B13 | Ponto de saúde por obra (8 dimensões) | A | **MUDA**: 5 dimensões (vigência, saldo, reajuste, medição parada, certidão) |
| B14 | Sparkline "tendência" na tabela | A | **SAI** |
| B15 | SPI (prazo) e Curva S previsto × medido | A (só obra 181) · N | **FICA** na nova |
| B16 | Custo, margem, CPI, EAC, TCPI, fade, waterfall de caixa | A (desligado) | **SAI** até custo vir do RM (decisão pendente sua) |
| B17 | Exportar CSV de toda listagem | N (parcial) | **MUDA**: todas as tabelas exportam |

## C. Página da obra / contrato

| Cód. | Item | Hoje | Recomendação |
|---|---|---|---|
| C1 | Cabeçalho: órgão, instrumento, vigente, estado, % Lotufo | N (sem %) | **MUDA**: mostrar % de participação e empreita |
| C2 | Abas Medições, Cronograma, Aditivos, Protocolo | N | **FICA** |
| C3 | Aba Notas fiscais (NFs do RM, líquido, recebido) | A · N (dentro da medição) | **ENTRA** como aba própria |
| C4 | Aba Documentos (e-mails, planilhas, PDFs vinculados) | N (espremido na medição) | **ENTRA** como aba própria |
| C5 | Aba Reajuste (data-base por índice, ciclos, ofícios) | A (caixa) | **ENTRA** (bloco E) |
| C6 | Caixa de vigência com dias e farol | A | **ENTRA** no cabeçalho |
| C7 | Dados contratuais: PI, aditivo, bases SINAPI/SICRO, empreita, CNO, ART, município | A (parcial) | **ENTRA** os campos que faltam (CNO, ART, município, empreita) |
| C8 | Avanço por etapa / serviço (quantidades) | A (só 181, chumbado) | **SAI** |
| C9 | Gerar espelho de NF | A (via Power Automate) | **ENTRA** na fase 7, sem Power Automate |
| C10 | FRC de consórcio | A (só Integra BRT) | **ENTRA** na fase 8 |
| C11 | Linha do tempo da medição (protocolo, atesto, espelho, NF, baixa, e-mails) | N | **MUDA**: vira painel lateral, não célula de tabela |

## D. Medições e fila de sugestões

| Cód. | Item | Hoje | Recomendação |
|---|---|---|---|
| D1 | Máquina de estados (prevista → protocolada → NF → recebida), congelamento, auditoria | N | **FICA** (é o núcleo) |
| D2 | Fila única com 7 tipos misturados, ordenada por id | N | **MUDA**: agrupar em 4 blocos: criar medição · confirmar evento · vincular NF · só ciência |
| D3 | Rótulos em jargão (FRC recebida, espelho detectado, classificar) | N | **MUDA**: frases de ação ("Confirmar envio do espelho da 12ª") |
| D4 | Execução e reajuste da mesma medição em 2 linhas | N | **MUDA**: 1 linha por medição, "aceitar as duas" |
| D5 | Botão "Aceitar" com 6 comportamentos | N | **MUDA**: rótulo por tipo (Criar, Registrar, Vincular, Arquivar) |
| D6 | Filtro por obra e por tipo, busca | — | **ENTRA** |
| D7 | Desfazer (NF vinculada, medição criada por engano) | — (spec promete) | **ENTRA** |
| D8 | Corrigir data/ofício antes de aceitar protocolo detectado | — | **ENTRA** |
| D9 | Motivos de não auto-aplicar como chips | N (escondido) | **ENTRA** |
| D10 | Importação CSV dentro da fila | N | **MUDA**: vai para a página do contrato |
| D11 | Sugestão só de ciência (FRC, classificar) | N | **MUDA**: FRC vira vínculo automático; classificar fica |
| D12 | Checklist de certidões trava o protocolo humano, mas detecção passa sempre | N | **MUDA**: detecção também registra a ressalva visível na medição |

## E. Ciclo de reajuste (portar da antiga, corrigido)

| Cód. | Item | Hoje | Recomendação |
|---|---|---|---|
| E1 | Data-base por índice (SINAPI e SICRO separados) | A | **ENTRA**: 2 colunas no contrato (7 obras têm os dois) |
| E2 | Último reajuste por índice → próximo ciclo (aniversário anual) | A | **ENTRA** |
| E3 | Prazo de ofício: 60 dias antes, fixo | A | **MUDA**: 60 d padrão, configurável por órgão |
| E4 | Farol vencido / urgente (30) / atenção (60) / em dia | A | **ENTRA**, com 5ª faixa "sem data-base cadastrada" (a antiga contava como em dia) |
| E5 | Ciclo avança quando a medição de reajuste é protocolada | — | **ENTRA**: "último reajuste" vem da medição, não de digitação |
| E6 | Obra sem direito a reajuste não gera alerta | A (ignorava) | **ENTRA** |
| E7 | Registro do ofício de reajuste protocolado (append-only) | — | **ENTRA** (é o A13 aplicado) |
| E8 | Cálculo do VALOR do reajuste por índice | — | **SAI** (fora do escopo declarado) |
| E9 | Tabela "Controle de data-base por obra" | A | **ENTRA** como Relatório |

## F. Certidões (reestruturar)

| Cód. | Item | Hoje | Recomendação |
|---|---|---|---|
| F1 | Matriz entidade × tipo com semáforo 15 d e checklist de protocolo | N | **FICA** |
| F2 | 8 entidades e 6 tipos (federal, FGTS, CNDT, estadual, municipal, falência) | A (8×6) · N (6 entidades × 3 tipos) | **MUDA**: cadastrar as 8 entidades e os 6 tipos na nova |
| F3 | Leitura do PDF: perfis estadual (SEFAZ-MT), municipal (extenso) e falência (TJMT) | A | **ENTRA** (a nova só lê os 3 federais) |
| F4 | Validade calculada da falência: emissão + 30 dias úteis | A | **ENTRA**, com feriados nacionais |
| F5 | OCR local para PDF digitalizado | A (tesseract no navegador) | **SAI** (regra sem custo permite, mas pesa; reavaliar se digitalizado for frequente) |
| F6 | Ler a pasta /Certidoes do SharePoint e sugerir | — | **ENTRA**: aposenta o upload e 3 fluxos do Power Automate |
| F7 | Pacote ZIP por entidade / por medição | A (por entidade) | **ENTRA** por medição (pacote de protocolo) |
| F8 | "Vigente na data X" (sessão ou protocolo), não só hoje | — | **ENTRA** |
| F9 | Município da certidão municipal por obra (não fixo em Cuiabá) | A (fixo) | **ENTRA** com o campo município (C7) |
| F10 | Link "emitir no órgão" por tipo | A | **ENTRA** |
| F11 | Alerta diário por e-mail (fluxo às 08:00) | A (Power Automate) | **MUDA**: vira e-mail da nova (bloco H) e o fluxo desliga |
| F12 | Histórico append-only, revogar, não se aplica | N | **FICA** |
| F13 | Tipos além dos 6 (CEIS, CNJ improbidade, seguro-garantia, CNO) | — | **ENTRA** como tipos cadastráveis "não cobrados por padrão" |

## G. Acessos e perfis

| Cód. | Item | Hoje | Recomendação |
|---|---|---|---|
| G1 | Diretoria só lê | N | **FICA** |
| G2 | Engenharia opera | N | **FICA** |
| G3 | Admin | N | **FICA** |
| G4 | Perfil Administrativo/Financeiro (espelho, NF, certidões, sem editar contrato) | — | **ENTRA** (você citou a operadora) |
| G5 | Permissão por obra | — | **SAI** por ora (equipe pequena) |
| G6 | Trocar a própria senha | — | **ENTRA** |
| G7 | Sessão de 12 h | N | **MUDA**: 30 dias com renovação silenciosa (rede interna) |

## H. Automações

| Cód. | Item | Hoje | Recomendação |
|---|---|---|---|
| H1 | Outlook + SharePoint a cada 15 min (Graph delegado) | N | **FICA** |
| H2 | RM a cada hora (NF, baixa, casamento) | N | **FICA** |
| H3 | Backup horário com ensaio de restauração, watchdog 3 min | N | **FICA**; saúde do backup passa a aparecer na Administração |
| H4 | E-mail diário de avisos (o "gatilho" que a antiga nunca teve) | — | **ENTRA**: precisa de Mail.Send numa caixa dedicada |
| H5 | 7 fluxos do Power Automate | A | **SAI** um a um, cada um depois do substituto validado |
| H6 | Coletor PNCP e robô de custos | A | **SAI** |
| H7 | Leitura da pasta de certidões e da pasta ADITIVO (termo assinado) | — | **ENTRA** (mesma permissão já concedida) |
| H8 | Threads no processo web (sem worker separado) | N | **FICA** por ora; registrar como dívida |

## I. Administração e relatórios

| Cód. | Item | Hoje | Recomendação |
|---|---|---|---|
| I1 | Usuários, auditoria encadeada, status RM e Graph, padrões, planilhas | N | **FICA** |
| I2 | Reconciliação RM (NF sem medição, divergência) | N | **FICA** |
| I3 | Seção "Relatórios": carteira por contratante, evolução, data-base, CSVs | — | **ENTRA** (recebe o que sai da home) |
| I4 | Runbook linkado na tela | — | **ENTRA** |

## J. Sai de vez

| Cód. | Item |
|---|---|
| J1 | Aba Licitações (PNCP, SINFRA, fichas, favoritas, coletor) |
| J2 | Mapa de MT, presença por município |
| J3 | Modo escuro (decisão de marca da nova) |
| J4 | Google Sheets como fonte |
| J5 | Dados chumbados da obra 181 |
| J6 | Página Receita × Custo (até custo vir do RM) |
