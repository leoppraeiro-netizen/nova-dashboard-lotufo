# Espelho de NF: regras de negócio por obra (levantamento de 2026-09-16)

Fonte: leitura autorizada de `~/dev/lotufo-dashboard` (js/espelho.js, _worker.js, backup do SharePoint) e
`~/dev/lotufo-automacao-medicao` (scripts/motor-multi.ts, cadastro-obras.json, modelos/*.docx, testes).
Objetivo: reconstruir o gerador de espelho em Python dentro da dashboard nova (decisão T1, opção b).
Este documento traz REGRA e CADASTRO, não código.

## 1. Entradas e fluxo (como é hoje)

| Campo digitado | Formato | Validação | Uso |
|---|---|---|---|
| Nº da medição | "24" → `24ª` | 1 a 3 dígitos | controles do Word + nome do arquivo |
| Competência | `MM/AAAA` | mês 1–12; ano entre ano−5 e ano+1 | período `01/MM/AAAA A ult/MM/AAAA` |
| 1 a 4 valores brutos | máscara de moeda | ao menos um > 0; vazio = 0 | células de input da planilha-motor |

- A obra não é escolhida num seletor: o card casa o nome da obra por palavras-chave (`match`), 1º acerto vence.
- O navegador manda `{obraId, inputs[], medicao, periodo}` ao Worker, que repassa ao fluxo do Power Automate.
- Volta um `.docx` em base64 POR SAÍDA (NF). Uma nota baixa direto; várias viram um ZIP
  `Espelhos Nª medição MM-AAAA - <obra>.zip`. PDF não existe mais no fluxo atual.
- Depois, "LANÇAR" gravava no SharePoint 1 medição + 1 item de faturamento por nota (`ValorPI` = soma das
  notas sem "reaj" no rótulo; `Reajuste` = soma das com "reaj"). Idempotência pelo título `OBRAID · N · MM/AAAA`.
- Princípio declarado do motor: "a planilha .xlsm de cada obra é a FONTE DA VERDADE e o MOTOR; alíquotas e
  arredondamento não são parâmetros do script: vivem na planilha". O script só escreve os inputs, recalcula,
  lê células, trunca/arredonda, formata e preenche o Word. Os únicos cálculos próprios do script são o
  líquido e o valor por extenso.

## 2. Uma medição vira mais de uma NF? Sim, em 8 das 19 obras

| Obra (id do motor) | Contrato / órgão | Emissor | NFs por medição | Eixo de desdobramento | Reajuste | Projeto |
|---|---|---|---|---|---|---|
| SINFRA-MT402 | 019/2024 SINFRA | Lotufo | 2 | execução × reajuste | sim | não |
| SINFRA-MT401 | 014/2023 SINFRA | Lotufo | 2 | execução × reajuste | sim | não |
| SINFRA-CAVALARIA | 004/2026 SINFRA | Lotufo | 2 | execução × reajuste | sim | não |
| SINFRA-5BAIRROS | 161/2022 SINFRA | Lotufo | 2 | execução × reajuste | sim | não |
| MTPAR-COMPLEXO-CULTURAL | 099/2024 MTPAR | Lotufo | 2 | medição × reajuste | sim | não |
| MTPAR-ESPACO-SHOW | 060/2024 MTPAR | Lotufo | 2 | medição × reajuste | sim (há consolidado 21ª–23ª) | não |
| MTPAR-ORLA | 067/2024 MTPAR | Lotufo | 2 | medição × reajuste | sim | não |
| MTPAR-XTREME | 077/2025 MTPAR | Lotufo | 2 | medição × reajuste | sim | não |
| MTPAR-GRANITO | 130/2025 MTPAR | Lotufo | 1 | só medição | nunca faturou (`off`) | não |
| PREF-CBA-REGIAO-OESTE-L3 | 128/2022 PMC | Lotufo | 2 | medição × reajuste | sim | não |
| PMC-COXIPO2-CT392 | 392/2024 PMC | Lotufo | 2 | medição × reajuste | sim | não |
| PREF-COXIPO-RES3 | 248/2024 PMC | Lotufo | 3 | fonte de recurso (SUDECO + FONTE 100) × reajuste | sim (1) | não |
| SES-ALTA-FLORESTA | 102/2022 SES | Lotufo | 2 | medição × reajuste (cada uma soma reequilíbrio ISSQN) | sim | não |
| SINFRA-MT388 | 082/2025 SINFRA | Lotufo | 4 | município (Cáceres, P. Esperidião) × (medição, reajuste) | sim | não |
| SINFRA-LEBLON | 012/2024 SINFRA | Consórcio Leblon, NF por consorciada | 4 | consorciada 50/50 (Lotufo, Rivoli) × (medição, reajuste) | sim | não |
| SINFRA-ATALAIA | 074/2021 SINFRA | Consórcio Oriundi, NF por consorciada | 8 | município (CBA, VG) × consorciada (Lotufo 80, Rivoli 20) × (medição, reajuste) | sim | não |
| SINFRA-BRT | 041/2025 SINFRA | Consórcio Integra BRT | 9 (6 exec + 3 projeto) | município × consorciada (49/49/2) × (execução, projeto) | não modelado | sim |
| SINFRA-ESTACOES-BRT | 176/2025 SINFRA | Lotufo | 6 | município (CBA, VG) × (execução, reajuste) + projeto CBA × (medição, reajuste) | sim | sim |
| SINFRA-DECIOLANDIA | 155/2022 SINFRA | Consórcio Via Parecis, Lotufo emite só a cota 33,33% | 2 | cota × (medição, reajuste) | sim | não |

- Condição de emissão: bloco com valor zero não emite (`emitirSe = 0` em todas as 59 saídas). Aba
  inexistente lê como zero. É assim que o BRT gera 6 notas quando só há execução.
- Cadastros divergem entre si: motor 19 obras/59 saídas; `cadastro-obras.json` 18 (falta Deciolândia);
  `Saidas-Modelo.json` 18/55; `_manifest.json` defasado; `espelho.js` tem `PVG-MATERNIDADE-VG`, que o motor
  não conhece (erro garantido). O Python precisa de UMA fonte.

## 3. Regras fiscais por obra (o motor lê a planilha; o Python terá de reimplementar)

Padrão dominante ("execução"): valor NF (input ou rateado) → MO = TRUNC(valor × 0,40; 2) → material =
valor − MO (resíduo) → INSS 11% sobre MO → ISSQN 5% sobre MO → IRRF sobre o TOTAL → líquido = valor − INSS −
ISS − IRRF. Material nunca é tributado. Não há CSRF/PIS/COFINS/CSLL em nenhum espelho.

| Obra | Split MO/Mat | INSS | ISS (base, %) | IRRF | Líquido | Arredondamento na planilha |
|---|---|---|---|---|---|---|
| MT-402 | 40/60 TRUNC | 11% s/ MO | 5% s/ MO | 1,2% s/ total | deduz ISS | só TRUNC na MO; tributos crus (motor arredonda IRRF) |
| MT-401 | 40/60 TRUNC | 11% s/ MO | 5% s/ MO | 1,2% | deduz ISS | idem |
| CAVALARIA | 40/60 TRUNC | 11% s/ MO | 5% s/ MO | 1,2% | deduz ISS (célula do líquido muda entre aba Medição e Reajuste) | só TRUNC na MO |
| 5 BAIRROS | 40/60 TRUNC | 11% TRUNC | 5% TRUNC s/ MO | 1,2% cru | deduz ISS | MO/INSS/ISS TRUNC; IRRF cru (motor arredonda) |
| REGIÃO OESTE | 40/60 TRUNC | 11% TRUNC | 5% TRUNC | 1,2% TRUNC | deduz ISS | TRUNC puro em tudo (caso mais limpo) |
| COMPLEXO CULTURAL | 40/60 TRUNC | 11% ROUND | 5% ROUND | 1,5% ROUND | deduz ISS | TRUNC na MO + ROUND nos tributos |
| ESPAÇO SHOW | idem | idem | idem | 1,5% ROUND | idem | idem |
| GRANITO | idem | idem | idem | 1,5% ROUND | idem | idem |
| ORLA | idem | idem | idem | 1,5% ROUND | idem | idem |
| XTREME | idem | idem | idem | 1,5% ROUND | idem | idem |
| COXIPÓ 2ª (CT392) | 40/60 TRUNC | 11% | 5% s/ MO | 1,2% | deduz ISS | inconsistente entre versões (ora ROUND, ora cru) |
| COXIPÓ 3ª (CT248) | 40/60 | 11% | 5% s/ MO | 1,2% | deduz ISS | abas Medição = ROUND em tudo; aba Reajuste = TRUNC na MO + tributos crus |
| ALTA FLORESTA (SES) | 60/40 TRUNC | sem INSS (IN 2.110/2022 art. 114 II) | 5% s/ MO 60% | 1,2% s/ total | líquido = valor − IRRF | ISS/IRRF crus; espelho usa TRUNC |
| MT-388 Cáceres | 40/60 TRUNC | 11% s/ MO | 5% sobre MATERIAL (60%) | 1,2% s/ total do município | NÃO deduz ISS | espelho lê coluna truncada |
| MT-388 P. Esperidião | 40/60 TRUNC | 11% s/ MO | 5% s/ MO | 1,2% | NÃO deduz ISS | coluna truncada |
| LEBLON (Lotufo, Rivoli) | 40/60 TRUNC sobre a metade | 11% s/ MO | 5% s/ MO | 1,2% s/ a metade | deduz ISS | tributos crus; motor arredonda INSS, ISS, IRRF |
| ATALAIA (Lotufo, Rivoli) | 40/60 TRUNC | 11% s/ MO | 5% s/ MO | 1,2% s/ total da cota | deduz ISS | tributos crus; motor trunca |
| BRT execução | 40/60 TRUNC | 11% s/ MO | 5% s/ MO | 1,2% | deduz ISS | crus; motor trunca |
| BRT projeto | sem split | sem INSS | 5% sobre 100% | 4,8% | deduz ISS | base ROUND, tributos crus |
| ESTAÇÕES execução | 40/60 TRUNC | 11% TRUNC | 5% TRUNC | 1,2% TRUNC | deduz ISS | TRUNC em tudo |
| ESTAÇÕES projeto | sem split | sem INSS | 5% s/ total | 4,8% | deduz ISS | base ROUND, tributos crus |
| DECIOLÂNDIA (cota 33,33%) | 40/60 | 11% s/ MO | 5% s/ MO, DESTACADO e não retido | sem IRRF | líquido sem ISS | — |
| MATERNIDADE VG (só no front) | — | — | ISS 2% sobre o TOTAL sem dedução (LC 5.177/2023) | — | — | sem motor: implementação nova |

Rateios (todos na planilha): MT-388 por km (fator 36.184/43.444 = 0,8328; Cáceres = ROUND(input × fator),
Porto = resto); ESTAÇÕES por estação (61 de 81; CBA = TRUNC(input × fator), VG = resto); ATALAIA por
município (TRUNC(input × 0,5872), VG = resto) e depois por empresa (Lotufo 80, Rivoli 20); BRT por km
(6.740/7.820 = 86,19%) e por empresa (ROUND(× 0,49) para Lotufo e Guaxe, Encomind = resto); LEBLON 50/50
(Lotufo = ROUND(× 0,5), Rivoli = resto, pode ficar 1 centavo menor).

O que o script calcula de fato (replicar ao pé da letra): leitura com truncamento a 2 casas por padrão
(com epsilon 1e-4 para ruído de ponto flutuante) e arredondamento só nos campos listados por obra
(`roundFields`: MT-402 irrf; MT-401 irrf; 5 BAIRROS irrf; LEBLON inss, iss, irrf); líquido = trunc(valor −
inss − iss − irrf) ou, em MT-388 e Deciolândia, trunc(valor − inss − irrf); o líquido não é impresso, só
confere. Formato BR com vírgula decimal e milhar. Valor por extenso com acento (três, milhão/milhões), "cem"
exato, conector " e " antes do último grupo se < 100 ou múltiplo de 100 senão ", ", " de" quando múltiplo
exato de 1.000.000 ("um milhão de reais"), centavos arredondados, saída em CAIXA ALTA.

Campos que vão ao Word (content controls): valor (5001), mo (5002), material (5003), inss (5004), iss
(5005), irrf (5006), valor_extenso (5007), medicao (5008/5009/5010), periodo (5030). A lista por saída vem
do campo `docx` (ex.: projeto BRT só valor, iss, irrf, extenso; SES sem inss; Deciolândia sem irrf). Todo o
resto do espelho é texto fixo do modelo: CNPJ do cliente, endereço, CNO, nº do IC/contrato, O.S., extensão
em km, descrição do serviço, favorecido bancário. Não há ART nem código de serviço municipal em modelo algum.

## 4. IBS / CBS

Zero ocorrências em modelos, motor, cadastro, backup e Worker. A única menção é o leitor de PDF da FRC
reconhecendo o leiaute nacional da NFS-e. O espelho em Python precisará de duas linhas novas por saída
(IBS 0,9%, CBS 0,1%) e controles novos nos modelos: é trabalho novo, não porte.

## 5. Modelos Word

61 arquivos `.docx` ativos em `~/dev/lotufo-automacao-medicao/modelos/<OBRA-ID>/`, um por saída, com content
controls. Particularidades: Espaço Show tem um modelo consolidado de reajuste (21ª–23ª) órfão; Região Oeste
sem `valor_extenso` e sem `periodo`; SES sem `inss`; BRT declara 9 saídas e tem 6 modelos no disco;
Deciolândia sem `irrf`; MT-388 com a competência `(05.2026)` embutida no nome. O nome do arquivo final é
derivado do nome do modelo por regex (nº da medição e competência): gerar a partir dos dados, não do nome.

## 6. Gabaritos (viram os testes do Python)

Catorze notas conferidas ao centavo (`motor-generico.md` §2):

| Obra (medição; inputs) | Saída | Valor NF | MO | Material | INSS | ISS | IRRF |
|---|---|---|---|---|---|---|---|
| MT-388 (10ª; Medição 634.529,58, Reajuste 38.655,83) | Cáceres medição | 528.436,23 | 211.374,49 | 317.061,74 | 23.251,19 | 15.853,08 | 6.341,23 |
| | Cáceres reajuste | 32.192,58 | 12.877,03 | 19.315,55 | 1.416,47 | 965,77 | 386,31 |
| | Porto medição | 106.093,35 | 42.437,34 | 63.656,01 | 4.668,10 | 2.121,86 | 1.273,12 |
| | Porto reajuste | 6.463,25 | 2.585,30 | 3.877,95 | 284,38 | 129,26 | 77,55 |
| ATALAIA (43ª; Medição 780.224,80, Reajuste 623.268,84) | Med. Cuiabá Lotufo | 366.518,40 | 146.607,36 | 219.911,04 | 16.126,80 | 7.330,36 | 4.398,22 |
| | Med. V. Grande | 257.661,44 | 103.064,57 | 154.596,87 | 11.337,10 | 5.153,22 | 3.091,93 |
| | Reaj. Cuiabá | 292.786,76 | 117.114,70 | 175.672,06 | 12.882,61 | 5.855,73 | 3.513,44 |
| | Reaj. V. Grande | 205.828,30 | 82.331,32 | 123.496,98 | 9.056,44 | 4.116,56 | 2.469,93 |
| BRT (10ª; Execução 7.382.048,52) | Execução CBA | 3.117.641,10 | 1.247.056,44 | 1.870.584,66 | 137.176,20 | 62.352,82 | 37.411,69 |
| | Execução VG | 499.562,67 | 199.825,06 | 299.737,61 | 21.980,75 | 9.991,25 | 5.994,75 |
| ESTAÇÕES (3ª; Exec 3.198.742,98, Reaj 202.800,30) | Exec. CBA | 2.408.929,89 | 963.571,95 | 1.445.357,94 | 105.992,91 | 48.178,59 | 28.907,15 |
| | Exec. VG | 789.813,09 | 315.925,23 | 473.887,86 | 34.751,77 | 15.796,26 | 9.477,75 |
| | Reaj. CBA | 152.726,15 | 61.090,46 | 91.635,69 | 6.719,95 | 3.054,52 | 1.832,71 |
| | Reaj. VG | 50.074,15 | 20.029,66 | 30.044,49 | 2.203,26 | 1.001,48 | 600,88 |

Não emitidos por bloco zerado (prova da condição): BRT projeto CBA e ESTAÇÕES projeto CBA.

MT-402, caso simples (23ª real): input 278.509,92 → MO 111.403,96 · material 167.105,96 · INSS 12.254,43 ·
ISSQN 5.570,19 · IRRF 3.342,12 (arredondado; truncado daria 3.342,11, revisto contra o espelho real).

Extenso: 3.578,54 → "três mil, quinhentos e setenta e oito reais e cinquenta e quatro centavos";
278.509,92 → "duzentos e setenta e oito mil, quinhentos e nove reais e noventa e dois centavos";
2.408.929,89 → "dois milhões, quatrocentos e oito mil, novecentos e vinte e nove reais e oitenta e nove
centavos"; 1.000.000,00 → "um milhão de reais"; 13,13 → "treze reais e treze centavos".

Outros invariantes já testados no motor (portar): sem chave `docx` duplicada; template existe; lista `docx`
bate com os controles reais do modelo; detecção de modelos órfãos.

## 7. Consórcios e FRC

A NF é sempre de cada consorciada, nunca do consórcio. O consórcio aparece só como favorecido bancário no
rodapé do espelho e como emissor da FRC (fatura única que consolida as NFS-e e vai ao órgão).

| Consórcio | Obra | Cotas | NFs de espelho | FRC |
|---|---|---|---|---|
| Integra BRT | SINFRA-BRT | Lotufo 49 / Guaxe 49 / Encomind 2 | 6 execução + 3 projeto | completa; numeração sequencial (a partir de 20) |
| Oriundi | SINFRA-ATALAIA | Lotufo 80 / Rivoli 20 | 8 | completa; numeração por data AAAAMMDD + dígito (1 medição, 2 reajuste) |
| Complexo Leblon | SINFRA-LEBLON | 50/50 | 4 | esqueleto (falta prestador/tomador/modelo); a partir de 48 |
| Via Parecis | SINFRA-DECIOLANDIA | Lotufo 33,33% | 2, só a cota Lotufo | não existe |

Deciolândia é o caso especial: a pessoa digita o valor CHEIO do consórcio, a NF sai com a cota, e o
lançamento gravava o cheio na curva ("PI cheio do consórcio, NFs registradas = cota Lotufo"). ISS destacado,
não retido; sem IRRF.

Espelho e FRC são fluxos independentes que se encontram só nos números: o espelho gera o Word antes da
NFS-e existir; a FRC lê as NFS-e em PDF já emitidas (leitores ISSNet/Cuiabá e Tangará da Serra), soma
bruto/INSS/IRRF/ISS/líquido e preenche a planilha da fatura, com duas travas (soma das retenções = total
retido; bruto − retenções = líquido).

## 8. Diagnóstico e ordem de porte

1. Estável e replicável: split por percentual fixo, INSS 11% e ISS 5% sobre MO, IRRF sobre total, líquido,
   bloco zerado não emite, extenso (já é código puro com gabarito).
2. Estável mas a tabelar, não inferir: IRRF 1,2% (SINFRA, prefeituras) × 1,5% (MTPAR) × 4,8% (projeto);
   ISS sobre material em Cáceres; SES 60/40 sem INSS; MT-388 e Deciolândia com líquido sem ISS.
3. Não replicar: `roundFields` (arredondamento definido por obra porque a planilha esqueceu o ROUND).
   Definir política fiscal por tributo em Decimal e provar contra os gabaritos.
4. ~~Não replicar: epsilon 1e-4 (só existe pelo float do Excel). Decimal com ROUND_DOWN/ROUND_HALF_UP.~~
   Revogado em 2026-09-23: o motor imita o ponto flutuante do Excel e a leitura com epsilon do motor
   antigo (ver `app/espelho.py`), porque o espelho real da Oriundi 46ª (Rivoli VG, MO 6.764,19) só sai
   assim.
5. Não replicar: nome do arquivo por regex sobre o nome do modelo.
6. Risco 1, planilha como motor: aba renomeada (`'REAJUSTE - PROJ. '` com espaço no fim), célula deslocada,
   coluna trocada produzem NF errada em silêncio. A reconstrução em Python elimina isso.
7. Risco 2, cadastros divergentes (19 × 18 × 18 × 20). Consolidar UMA fonte.
8. Risco 3, macro VBA de extenso: já substituída; não reintroduzir.
9. Risco 4, rótulos errados: Orla e Xtreme com nº de medição desatualizado no nome; Espaço Show com reajuste
   consolidado. Casar saída pelo valor, nunca pelo nome do arquivo.
10. Ordem de porte: (1) MT-402, MT-401, Cavalaria; (2) Região Oeste; (3) MTPAR (Cultural, Espaço Show, Orla,
    Xtreme, Granito); (4) 5 Bairros, Coxipó 2ª e 3ª; (5) SES Alta Floresta; (6) MT-388; (7) Estações BRT;
    (8) Leblon; (9) Atalaia; (10) BRT; (11) Deciolândia; (12) Maternidade VG (implementação nova).
