# Contexto e Especificação — Dashboard de Contratos e Medições

> Documento autossuficiente para revisão externa. Nomes de pessoas, e-mails e servidores internos foram substituídos por papéis/apelidos genéricos. Nenhuma credencial está presente.

## Contexto da empresa e do problema

- Construtora brasileira de médio porte ("Lotufo") executa obras públicas (rodovias, edifícios públicos, BRT) para órgãos estaduais e clientes públicos no Mato Grosso. Alguns contratos são executados via **consórcio** com outras construtoras.
- O ciclo central do negócio: todo mês, cada obra tem uma **medição** (levantamento do executado no período), que é protocolada no órgão contratante com um pacote de documentos (planilha de medição, certidões de regularidade fiscal, fatura). Após aprovação/atesto, emite-se **nota fiscal**; depois acompanha-se o recebimento. **Reajustes anuais** por data-base tramitam como medições separadas.
- Antes da emissão de cada NF, a engenharia monta um **"espelho de NF"**: documento Word com dados do cliente, contrato, período, valor por extenso, divisão mão de obra × materiais (ex.: 40/60) e retenções calculadas (INSS 11% sobre a parcela de mão de obra, ISSQN 5% sobre a parcela de 40%, IRRF 1,5% sobre o total), enviado ao setor de faturamento para conferência.
- Em obras de consórcio, após as NFs, emite-se a **FRC (Fatura de Recebimento de Consórcio)**: documento numerado sequencialmente por consórcio, com o rateio dos valores entre as consorciadas conforme percentuais de participação; cada consorciada emite sua NFS-e contra o consórcio.
- Hoje esses controles vivem em planilhas, e-mails e fluxos de Power Automate (que falham com frequência). As regras fiscais por obra e os rateios por consórcio estão codificados nesses fluxos.
- **ERP**: TOTVS RM, em servidor local. As NFs emitidas e o financeiro (baixas de recebimento) vivem lá.
- **Documentos**: SharePoint corporativo com pastas por obra (medições assinadas, planilhas, contratos, aditivos).
- Usuários do sistema: equipe de engenharia (~poucas pessoas, operam o sistema) e diretoria (visualiza). O dono do projeto é engenheiro da empresa, administrador do sistema, com apoio de IA para desenvolvimento e manutenção.

## Restrições técnicas verificadas (fatos, não suposições)

- O sistema rodará num servidor Windows da empresa, na rede interna, sem acesso externo.
- O acesso direto ao banco SQL Server do RM está **bloqueado** pela trava de segurança da TOTVS (usuário do alias enxerga só tabelas globais; tabelas de movimento/financeiro negadas). Autenticação Windows entre as máquinas falha (domínios não confiáveis).
- A **API REST do RM** no servidor de banco fica **sempre ligada** (verificado). O caminho de integração escolhido: API + "Consultas SQL" cadastradas dentro do RM, executadas via endpoint `consultaSQLServer/RealizaConsulta` com um usuário do RM — roda com a permissão da aplicação, contornando o bloqueio do banco.
- Não é possível criar conta corporativa dedicada para o SharePoint; a integração usará **token delegado da conta pessoal do dono do projeto** (Microsoft Graph), com renovação automática e re-login ocasional.
- Status "NF paga" depende de o setor financeiro dar baixa no RM — premissa ainda não confirmada (pendência registrada).

---

## Especificação aprovada

# Dashboard de Gestão de Contratos e Medições — Lotufo Engenharia

**Status:** Aprovado em brainstorming; aguardando plano de implementação

## 1. Objetivo

Sistema web interno para a Lotufo gerenciar contratos de obras públicas e seus ciclos de medição, do cronograma previsto ao recebimento, substituindo controles manuais em planilhas, e-mails e fluxos frágeis de Power Automate. Usuários: engenharia (opera) e diretoria (acompanha).

Funcionalidades centrais:

1. Acompanhamento físico-financeiro (previsto × realizado por obra e consolidado mensal).
2. Controle do ciclo de medições (elaboração → protocolo → aprovação → NF → recebimento).
3. Acompanhamento de processos de aditivos.
4. Indicação de prazos (vigência e execução) e alerta antecipado de reajuste por data-base.
5. Geração de espelhos de notas fiscais.
6. Controle de vencimento e repositório de certidões.
7. Geração de FRC (Fatura de Recebimento de Consórcio) para obras em consórcio.
8. Controle de faturamento mensal (previsto, medido, emitido, recebido).

**Fora do escopo (decisões explícitas do dono):**
- Conceito de "medição em atraso" (alerta de protocolo fora do prazo) — as datas ficam registradas, permitindo reintroduzir depois.
- Cálculo automático do valor de reajuste por índice — a dashboard alerta e acompanha o processo, não calcula.
- Acesso externo à rede da empresa (pode ser adicionado via túnel futuramente).

## 2. Decisões de arquitetura

| # | Decisão | Implicação |
|---|---------|------------|
| 1 | Escopo completo (todas as funcionalidades do §1) numa única spec | Implementação faseada internamente (§7) |
| 2 | Entrada de dados híbrida | Dashboard é o cadastro; importação assistida lê planilhas do SharePoint e propõe valores; nada grava sem confirmação humana |
| 3 | Hospedagem em servidor Windows local, rede interna | Sem custo de nuvem; diretoria acessa pela rede |
| 4 | RM via API REST + Consultas SQL cadastradas | Sincronização automática; pré-requisitos: usuário RM e cadastro das consultas |
| 5 | Status "paga" vem da baixa no RM | Se a baixa não for feita no RM, o status passa a ser manual (mudança pequena) |
| 6 | SharePoint via acesso delegado da conta do administrador | Sem app corporativo; ações aparecem em nome dele; re-login ocasional |
| 7 | Dashboard **gera** espelho de NF e FRC | Regras fiscais e rateios viram configuração por contrato/consórcio, migradas e auditadas a partir do Power Automate |
| 8 | Certidões: kit padrão (CND Federal, CRF/FGTS, CNDT, estadual, municipal) para a construtora + consórcios + consorciadas | Cadastro com validade, PDF, alerta e download |
| 9 | Reajuste: alerta antecipado (X dias configuráveis antes do aniversário da data-base) + acompanhamento do processo | Sem cálculo de índice |
| 10 | Login individual por pessoa, 2 perfis (Engenharia edita, Diretoria visualiza) + log de auditoria e uso | Tela de administração exclusiva do administrador |
| 11 | Stack: Python (FastAPI) + React + SQLite, serviço Windows | PDFs via Word/Excel COM com fallback em bibliotecas Python; backup diário do banco para o SharePoint |
| 12 | Sem indicador de sincronização na interface | Falhas só no log interno / tela de administração |

## 3. Arquitetura

Um único serviço Windows com três partes:

1. **Aplicação web (FastAPI)** — serve a interface React e a API interna na rede local. Autenticação por sessão; autorização por perfil verificada no servidor.
2. **Banco SQLite** — arquivo único; a verdade de contratos, medições, aditivos, certidões e consórcios. Backup automático diário: cópia datada enviada a uma pasta do SharePoint.
3. **Sincronizadores agendados** (no mesmo processo):
   - **RM** (a cada hora): executa as Consultas SQL cadastradas via API com usuário RM dedicado; importa NFs emitidas e status/data de baixa; tenta casar NF ↔ medição por contrato + valor + período; casos ambíguos vão para fila de conferência.
   - **SharePoint** (Microsoft Graph, token delegado com renovação automática): lista documentos das pastas vinculadas a cada obra (links, sem duplicar arquivos) e lê planilhas de medição para a importação assistida.

**Resiliência**: RM ou SharePoint fora do ar não afetam o uso da dashboard com dados locais. Retentativas automáticas com espera progressiva. Nenhum aviso de sincronização na interface dos usuários; estado das integrações visível apenas na administração.

## 4. Modelo de dados

- **Obra/Contrato**: cliente/órgão; nº do instrumento; objeto; valor contratado; data-base e índice (informativo); vigência (início/fim); prazo de execução (início/fim); nº do processo no órgão; pasta SharePoint vinculada; regras fiscais do espelho (split MO×materiais, alíquotas INSS/ISSQN/IRRF, conta bancária); vínculo opcional a consórcio. Valor e prazos **vigentes** = original + aditivos assinados (calculado, nunca digitado por cima).
- **Cronograma previsto**: parcelas mensais previstas por contrato (base do previsto × realizado). Reimportável quando o cronograma for revisado (versões preservadas).
- **Medição**: contrato; número; tipo (execução | reajuste); período medido; valor; datas (elaboração, protocolo — com nº do ofício/processo —, aprovação/atesto); documentos vinculados (links SharePoint); status derivado das datas e da NF.
- **Nota Fiscal**: origem RM (número, série, emissão, valor, tomador, coligada); casamento com medição (automático com fila de conferência manual); status e data de recebimento (baixa RM).
- **Aditivo**: contrato; tipo (prazo | valor | escopo | misto); alterações (novo valor e/ou novas datas); processo com status (em elaboração → protocolado → em análise → assinado) e datas de cada etapa.
- **Consórcio**: nome; consorciadas com CNPJ e percentual de participação; contador sequencial de FRC.
- **FRC**: consórcio; nº sequencial; medição vinculada; valores por consorciada; arquivo gerado.
- **Certidão**: entidade (construtora | consórcio | consorciada); tipo (CND Federal, CRF/FGTS, CNDT, estadual, municipal); datas de emissão e validade; arquivo PDF; histórico (a vigente é a mais recente válida).
- **Usuário**: nome, e-mail, senha (hash), perfil (engenharia | diretoria), ativo.
- **Log de auditoria e uso**: usuário, ação (criar/alterar/excluir/gerar/importar/login/acesso a tela), entidade afetada, dados antes/depois quando aplicável, data/hora. Não editável pela interface.

## 5. Telas

1. **Painel geral (home da Diretoria)**: consolidado mensal — previsto (soma dos cronogramas) × medido × emitido × recebido — com histórico e projeção dos próximos meses; carteira de contratos (valor vigente, saldo); filtro por obra; alertas de data-base, prazos e certidões.
2. **Painel da Engenharia (home da Engenharia)**: avisos urgentes (certidões vencendo, data-base chegando, vigência/execução próximas do fim); protocolos em andamento (medições e aditivos aguardando retorno, com nº do processo, data e dias parados); pendências de fluxo (medições em elaboração, espelhos não gerados, NFs sem casamento, importações aguardando confirmação). Tudo clicável.
3. **Página da obra**: resumo (valores vigentes, prazos, curva previsto × realizado); abas: medições, aditivos, notas fiscais, documentos (da pasta SharePoint), configuração fiscal.
4. **Medição (fluxo)**: criar → lançar valores manualmente ou importar da planilha do SharePoint (tela de conferência) → registrar protocolo → registrar aprovação → gerar espelho → NF casada pela sincronização → recebimento pela baixa.
5. **Aditivos**: lista por contrato com status e datas; "assinado" recalcula o contrato vigente.
6. **Certidões**: tabela por entidade, semáforo de vencimento, upload e download da vigente.
7. **Consórcios**: cadastro de participações; geração de FRC por medição.
8. **Administração (somente o administrador)**: usuários; log de auditoria e uso; saúde das sincronizações; configurações (antecedência de alertas, agendamentos, modelos de documento).

## 6. Geração de documentos

- **Espelho de NF**: botão na medição → docx preenchido a partir de template com dados do contrato e da medição (valor por extenso incluído) → prévia em tela → PDF via Word COM (instância invisível própria; fallback em bibliotecas Python se COM indisponível) → arquivo salvo vinculado à medição. Espelhos separados para execução e reajuste. Bloqueio com mensagem clara se a configuração fiscal do contrato estiver incompleta.
- **FRC**: botão na medição de obra em consórcio → próximo número da sequência do consórcio → rateio pelos percentuais das consorciadas → template Excel preenchido → PDF. FRCs separadas para medição e reajuste. O número só é consumido quando a FRC é confirmada (evita buracos na sequência).
- **Migração das regras do Power Automate**: extrair as regras dos fluxos atuais (percentuais, alíquotas, deduções, participações, numeração), registrá-las como configuração visível por contrato/consórcio, e validar com **auditoria de paridade**: para 2–3 medições recentes de cada obra/consórcio, gerar o documento pela dashboard e comparar com o real enviado por e-mail, antes de aposentar o fluxo antigo.

## 7. Segurança, erros, testes e ordem de implementação

- Senhas com hash forte (bcrypt/argon2). Autorização por perfil no servidor. Credenciais RM e token Microsoft criptografados com DPAPI do Windows. Log de auditoria imutável pela interface. Acesso restrito à rede interna.
- Erros de integração: retentativa com espera progressiva; falha persistente registrada apenas no log/administração. Importação assistida nunca grava sem confirmação. NF sem casamento vai à fila de conferência.
- Testes: TDD para toda regra de cálculo (retenções, valor por extenso, rateio, numeração FRC, consolidação mensal, contrato vigente com aditivos); testes de integração com simuladores de RM e Graph; auditoria de paridade como validação final dos documentos; repositório git desde o primeiro dia.
- Ordem de implementação (cada fase entrega valor usável): 1. Fundação (banco, login, auditoria, cadastro de contratos) → 2. Medições + cronograma + painéis → 3. Aditivos → 4. Integração RM → 5. SharePoint + importação assistida → 6. Espelho de NF → 7. Consórcios + FRC → 8. Certidões.

## 8. Pendências externas (não bloqueiam o início)

- Criar usuário do RM com permissão de executar Consultas SQL (fase 4).
- Cadastrar as Consultas SQL no RM (fase 4).
- Confirmar se o financeiro dá baixa dos recebimentos no RM (fase 4).
- Login delegado da conta Microsoft do administrador (fase 5).
- Acesso aos fluxos do Power Automate para auditoria das regras (fases 6–7).
