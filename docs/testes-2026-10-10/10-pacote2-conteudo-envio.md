# Pacote 2 — o que vai ao órgão (fase 4, 10/10/2026)

Branch `fix/conteudo-envio` (a partir de `master` c7b0638). Sem merge, sem push, produção não tocada.
Corrige A-16, A-17, A-18, A-19, A-13 e A-11 de `06-verificacao-api.md`. Para cada item: primeiro o teste que reproduz o
defeito (commit `teste(...)`, rodado e falhando), depois a correção (commit `fix(...)`).

## Commits

| Commit | Item |
|---|---|
| e33d98c teste / cf1e2b0 fix | A-16 — valor do espelho editável à mão |
| 282c217 teste / dcd0ebb fix | A-17 — Cco do envio da nota descartado |
| 282c217 teste / d249186 fix | A-18 — medição sai sem o reajuste irmão |
| 0133da0 teste / 7dda442 fix | A-19 — certidão digitada com validade em 2099 |
| dd3861b teste / d87cf17 fix | A-13 — link "do OneDrive" de qualquer site |
| dd3861b teste / 21ef501 fix | A-11 — qualquer arquivo como .eml |

## O que mudou, item por item (linguagem simples)

**A-16 — valor da medição que veio do espelho.** Se o valor da medição foi preenchido pelo espelho, ninguém mais o
muda à mão, em estado nenhum: o servidor responde "O valor desta medição vem do espelho: para mudar, gere o espelho de
novo" (e gerar o espelho de novo já é bloqueado depois de protocolada). Na página da medição, no lugar do botão
"Editar o valor" aparece "vem do espelho". O atestado continua editável (glosa). As medições com valor de origem
`aceito` (as 629 da carga) e `manual` ficam como estavam.
Arquivos: `backend/app/medicoes.py` (`definir_valor`, também na condição do UPDATE, para fechar a janela entre ler e
gravar), `frontend/src/MedicaoAtos.tsx` (`valorEditavel`), `frontend/src/MedicaoPagina.tsx`.

**A-17 — Cco do envio da nota.** O endereço escrito em "Cco" na tela "Enviar a nota" agora vai no e-mail e fica gravado
em `envios.cco`, como já acontecia no espelho e no protocolo. Arquivos: `backend/app/api_notas_envio.py` (campo `cco`
no corpo), `backend/app/notas_envio.py` (repassa ao `protocolo.enviar`), `frontend/src/EnviarNota.tsx` (o POST leva o
Cco).

**A-18 — medição e reajuste juntos na SINFRA e na Pref. VG.** Quando o órgão junta medição e reajuste (regra D9) e a
"irmã" do mesmo contrato, mesmo número e mesma competência está com nota emitida e não está neste envio (nem em outro
envio ainda ativo da mesma etapa), a prévia ganha a pendência "Reajuste da 7ª Medição (mesma competência) está com nota
emitida e não vai neste e-mail: junte pela opção 'Juntar outra nota desta obra' ou justifique". Como toda pendência,
aparece em "O que falta" e só deixa enviar com justificativa de 10 caracteres ou mais. O sistema não junta sozinho.
Na MTPAR e na SES (que não juntam) nada muda. Arquivo: `backend/app/protocolo.py` (`_irmas_fora` e `pendencias`).

**A-19 — certidão digitada à mão.** Na digitação (quando o PDF não tem texto legível), a emissão não pode ser futura e
a validade não pode passar de 180 dias depois da emissão. **Depois do gate (S5): o teto passou a ser por tipo**,
ver a seção do gate. Na primeira versão a certidão lida do PDF não passava por essa regra; **depois do gate (S6) passa**. Na matriz de Documentos, a certidão digitada ganha o selo "digitada" ao
lado da data. Arquivos: `backend/app/documentos.py` (`VALIDADE_MAXIMA_DIAS`, `dados_manuais`), `frontend/src/matriz.ts`
(campo `leitura`), `frontend/src/Documentos.tsx`.

**A-13 — link do OneDrive.** Só aceita link cujo endereço seja exatamente `lotufoengmt-my.sharepoint.com` ou
`lotufoengmt.sharepoint.com`; o resto recebe "Cole um link do OneDrive ou SharePoint da Lotufo (…)". Endereço disfarçado
(`lotufoengmt-my.sharepoint.com.evil.test`) também é recusado. O texto de ajuda da tela diz a mesma frase. Arquivos:
`backend/app/protocolo.py` (`DOMINIOS_LINK`, `adicionar_link`), `frontend/src/EnviarNota.tsx`.

**A-11 — envio feito por fora.** O arquivo anexado como prova precisa ser um e-mail salvo de verdade: não pode começar
como PDF, PNG, ZIP ou JPEG e precisa ter remetente (`From`) e data (`Date`). Se não for, a resposta é "O arquivo não é
um e-mail salvo (.eml): na caixa de Enviados do Outlook, arraste o e-mail para uma pasta do computador e anexe o arquivo
.eml gerado" e nada é gravado (nem o arquivo, nem a evidência, nem a medição protocolada). Arquivo:
`backend/app/notas_envio.py` (`_e_email`).

## Testes novos

- `backend/tests/test_api_medicoes.py`: PUT do protocolado com origem espelho em `nota_emitida` → 422 e valor intacto;
  atestado da mesma → 200; origem `aceito` → 200.
- `frontend/src/MedicaoAtos.test.tsx` (novo): `valorEditavel` falso para protocolado de espelho, verdadeiro para
  atestado e para origem `aceito`/sem valor.
- `backend/tests/test_notas_envio.py`: Cco no arquivo do simulador e em `envios.cco`; pendência `irma_fora` na SINFRA e
  na VG com só a medição, ausente na MTPAR e quando o reajuste está em outro envio ativo; envio sem justificativa → 422
  (nenhum e-mail), com justificativa → 200; link de site qualquer e de domínio disfarçado → 422, do OneDrive → 200;
  PNG como .eml → 422 sem gravar nada; .eml mínimo (From/To/Date/Subject + corpo) → 200.
- `frontend/src/EnviarNota.test.tsx` (novo): o Cco digitado vai no POST; a ajuda do link cita os dois domínios.
- `backend/tests/test_api_documentos.py`: validade 2099 → 422 e nada gravado; emissão + 180 → 201; emissão amanhã →
  422; leitura automática com validade de 18 meses → 201.
- `frontend/src/Documentos.test.tsx`: certidão com `leitura: "manual"` mostra o selo "digitada" (só ela).

### ANTES (só os testes, código de `master`)

```
== A-16 backend
FAILED test_api_medicoes.py::test_valor_do_espelho_nao_se_edita_a_mao_depois_da_nota   assert (200 == 422)
PASSED test_atestado_da_medicao_do_espelho_continua_editavel
PASSED test_valor_aceito_continua_editavel_depois_da_nota
== A-16 frontend
× valor que veio do espelho não se edita à mão   AssertionError: expected true to be false

== A-17/A-18 backend
FAILED test_cco_do_envio_da_nota_chega_ao_email_e_ao_registro          AssertionError: assert [] == ['oculto@exemplo.com']
FAILED test_sinfra_medicao_sem_o_reajuste_irmao_vira_pendencia         assert [] == ["Reajuste da 23ª Medição (mesma competência) …"]
FAILED test_envio_sem_o_reajuste_irmao_exige_justificativa             assert (False is True)   (justificativa_obrigatoria)
PASSED test_reajuste_irmao_em_outro_envio_ativo_nao_cobra
== A-17 frontend
× o Cco escrito no e-mail vai no envio   AssertionError: expected undefined to deeply equal [ 'oculto@exemplo.com' ]

== A-19 backend
FAILED test_digitada_com_validade_de_2099_e_recusada     assert 201 == 422
FAILED test_digitada_com_emissao_futura_e_recusada       assert (201 == 422)
PASSED test_digitada_com_180_dias_e_aceita
PASSED test_lida_do_documento_com_validade_longa_continua_aceita
== A-19 frontend
× certidão digitada à mão leva o selo 'digitada'   Unable to find an element with the text: digitada

== A-13/A-11 backend
FAILED test_link_so_do_onedrive_ou_sharepoint_da_lotufo      AssertionError: https://exemplo-malicioso.test/x  assert 200 == 422
FAILED test_envio_por_fora_recusa_arquivo_que_nao_e_email    assert 200 == 422
PASSED test_envio_por_fora_aceita_eml_minimo
== A-13 frontend
× a ajuda do link diz que só vale o OneDrive ou SharePoint da Lotufo   Unable to find an element with the text: /Cole um link …/
```

Os PASSED do "antes" são os controles (o que deve continuar funcionando como hoje).

### DEPOIS (`fix/conteudo-envio`)

```
PASSED test_api_medicoes.py::test_valor_do_espelho_nao_se_edita_a_mao_depois_da_nota
PASSED test_api_medicoes.py::test_atestado_da_medicao_do_espelho_continua_editavel
PASSED test_api_medicoes.py::test_valor_aceito_continua_editavel_depois_da_nota
PASSED test_notas_envio.py::test_cco_do_envio_da_nota_chega_ao_email_e_ao_registro
PASSED test_notas_envio.py::test_sinfra_medicao_sem_o_reajuste_irmao_vira_pendencia
PASSED test_notas_envio.py::test_reajuste_irmao_em_outro_envio_ativo_nao_cobra
PASSED test_notas_envio.py::test_envio_sem_o_reajuste_irmao_exige_justificativa
PASSED test_api_documentos.py::test_digitada_com_validade_de_2099_e_recusada
PASSED test_api_documentos.py::test_digitada_com_180_dias_e_aceita
PASSED test_api_documentos.py::test_digitada_com_emissao_futura_e_recusada
PASSED test_api_documentos.py::test_lida_do_documento_com_validade_longa_continua_aceita
PASSED test_notas_envio.py::test_link_so_do_onedrive_ou_sharepoint_da_lotufo
PASSED test_notas_envio.py::test_envio_por_fora_recusa_arquivo_que_nao_e_email
PASSED test_notas_envio.py::test_envio_por_fora_aceita_eml_minimo
vitest: MedicaoAtos.test.tsx 2 passed · EnviarNota.test.tsx 2 passed · Documentos.test.tsx 4 passed
```

Suíte inteira no fim (uma vez, sem paralelo): backend `pytest -q` → **865 passed, 1 skipped** (7 min 18 s);
frontend `npm test` → **29 arquivos, 90 testes passed**; `npm run typecheck` → limpo.

## Testes antigos que mudaram (e por quê)

- `test_protocolo.py::test_sinfra_medicao_nao_protocola_e_nota_protocola_com_o_oficio_da_medicao`: mandava a nota da
  SINFRA só com a medição, com o reajuste da mesma competência em `nota_emitida` fora do e-mail — exatamente o cenário
  do A-18. Agora espera a pendência `irma_fora` (e só ela) e envia com justificativa.
- `test_notas_envio.py::test_envio_feito_por_fora_e_numero_do_siga`: o .eml de teste não tinha `Date`; ganhou o
  cabeçalho (todo .eml salvo do Outlook tem).
- `test_api_documentos.py` (o teste novo de 2099): a primeira versão conferia no painel, mas num banco novo a empresa
  nem aparece lá; passou a conferir no banco que nenhuma certidão com validade 2099 foi gravada. A falha do "antes"
  (201 em vez de 422) acontece antes dessa linha, então a reprodução não mudou.

## Decisões e pontos em que me afastei do desenho

1. **(Substituído pelo S2 do gate: par exato execução × reajuste.)** **A-18, só o par reajuste × não-reajuste.** O desenho fala em "outra medição do mesmo contrato, número e
   competência". Restringi a irmã ao par reajuste ↔ medição (execução ou projeto): projeto e execução são séries de
   numeração diferentes e podem coincidir número e competência num contrato com os dois (Terminais BRT), o que daria
   pendência falsa. A regra D9 é "medição e reajuste juntos".
2. **(Substituído pelo S1 do gate: o envio separado também cobra.)** **A-18, "etapa de nota" e "envio ativo".** "Etapa de nota" = etapa que leva as notas (SINFRA `nota`, prefeituras
   `unico`); a etapa `medicao` da SINFRA não cobra. "Outro protocolo ativo" = da mesma etapa, nem descartado nem
   enviado (o mesmo critério de `notas_envio._ativos`). Consequência que vale saber: se alguém abrir dois envios
   separados (um para a medição, outro para o reajuste), nenhum dos dois cobra a irmã — foi o que o desenho pediu.
3. **A-18 continua aparecendo depois do envio.** A pendência é calculada também no detalhe de um protocolo já
   enviado, enquanto a irmã seguir `nota_emitida` (como já acontece com outras pendências). Não filtrei para não mexer
   além do pedido.
4. **A-16, também na condição do UPDATE.** Além da recusa com mensagem, a gravação só acontece se a origem ainda não
   for `espelho` no momento do UPDATE (fecha a janela de alguém gerar o espelho entre a leitura e a gravação); nesse
   caso raro a mensagem é a genérica "congelada ou encerrada concorrentemente". `carga_legado` e `importar_ledger`
   chamam `definir_valor` só em medição recém-criada, então não são afetados.
5. **A-16 na tela.** "vem do espelho" aparece para quem pode editar sempre que a origem é espelho, inclusive em
   `espelho_gerado`/`espelho_enviado` (antes o botão só sumia, sem explicar).
6. **A-11, mensagem da emissão futura do A-19.** O desenho não fixou o texto; usei "A data de emissão não pode ser
   futura: confira as datas no documento".
7. **A-11, parser.** Se o cabeçalho for tão torto que o parser de e-mail do Python levanta erro, conta como "não é
   e-mail" (a única exceção larga do pacote, comentada no código).

## Riscos

- **A-16**: as 11 medições de produção com origem `espelho` deixam de aceitar edição do protocolado. Se alguma estiver
  com valor errado e já protocolada, não há caminho de correção pela tela (desenho decidido: correção pós-protocolo é
  reapresentação).
- **A-18**: envios da SINFRA/VG com só uma das irmãs passam a pedir justificativa. Em produção, conferir a lista de
  notas a enviar antes de liberar (o "a enviar" já agrupa as irmãs por competência quando nenhum envio foi iniciado).
- **A-11**: um .eml exportado de outro programa sem `Date` seria recusado. O Outlook sempre grava `Date`.
- **A-13**: link de OneDrive pessoal ou de outro tenant passa a ser recusado (o único link em produção é do
  `lotufoengmt-my`).

## Gate Sol: 7 achados, 6 corrigidos, 1 refutado (S4, já coberto em api_documentos.py:89)

Mesma branch e mesma disciplina: teste que falha antes, depois a correção.

| Achado | Commits (teste / fix) | O que mudou |
|---|---|---|
| S1 (alta) | a00cbc6 / 4d074db | A irmã que está em OUTRO envio ainda ativo da mesma etapa continua cobrando, com o texto "Reajuste da 7ª Medição (mesma competência) está em outro envio separado: na SINFRA e na Pref. VG medição e reajuste vão no mesmo e-mail — junte pela opção 'Juntar outra nota desta obra' (o outro rascunho é descartado) ou justifique". Só sai da conta a irmã já enviada (protocolo `enviado`) ou protocolada (estado ≠ `nota_emitida`). |
| S2 (média) | a00cbc6 / 4d074db | Par exato execução × reajuste: projeto nº N e reajuste nº N não se acusam. |
| S3 (média) | ab9a260 / ec80d66 | O .eml precisa de `From` com endereço de verdade (com @ e domínio com ponto), `Date` que o Python consiga interpretar e `To` ou `Subject` preenchido. A data não é comparada com a do envio informado. |
| S4 | ab9a260 (só teste) | Refutado: a rota já recusa validade anterior ou igual à emissão. Ficou um teste de API que prova isso (validade = emissão − 1 dia → 422). Nenhum código mudou. |
| S5 (média) | 13d4c3c / cd7463f | Teto por tipo: federal e trabalhista 185, estadual 65, municipal 95, FGTS 35, falência 60 dias (prazos reais das 54 certidões de produção em 10/10/2026 mais uma folga). Mensagem: "Validade de N dias passa do máximo de M para certidão <tipo>: confira as datas no documento". Falência sem validade continua calculada por dias úteis. |
| S6 (média) | 5750550 / 13b1d4a | Leitura automática com validade acima do teto do tipo ou emissão futura não grava: devolve `ok: false`, motivo `datas-implausiveis` (digitável), a mensagem "As datas lidas (emissão DD/MM/AAAA, validade DD/MM/AAAA) não batem com o prazo normal desta certidão: confira no documento e digite" e o que foi lido em `lidos`. A tela abre a digitação já preenchida com empresa, tipo, datas e natureza (antes ela sempre abria vazia: esse ajuste na tela foi necessário). A digitação passa pelo teto do S5. |
| S7 (baixa) | 17839af / 5e64e69 | Texto no lugar do botão: "vem do espelho · para mudar, gere o espelho de novo"; depois de protocolada, "vem do espelho · protocolada: corrija por reapresentação". |

### ANTES (só os testes do gate)

```
== S1/S2
FAILED test_reajuste_irmao_em_outro_envio_separado_tambem_cobra     assert [] == ["Reajuste da 23ª Medição (mesma competência) está em outro envio separado: …"]
FAILED test_projeto_e_reajuste_do_mesmo_numero_nao_sao_irmas        AssertionError: assert 'irma_fora' not in ['sem_nota', 'irma_fora']
== S3/S4
FAILED test_envio_por_fora_recusa_texto_com_from_e_date_escritos_a_mao   assert (200 == 422)
PASSED test_digitada_com_validade_antes_da_emissao_e_recusada            (S4: já protegido)
== S5
FAILED test_digitada_com_validade_de_2099_e_recusada                     (mensagem ainda com "máximo de 180")
FAILED test_digitada_no_teto_do_tipo_passa_e_um_dia_a_mais_nao[estadual|falencia|fgts|municipal]   assert 201 == 422
FAILED test_digitada_no_teto_do_tipo_passa_e_um_dia_a_mais_nao[federal|trabalhista]               (mensagem sem o tipo)
== S6
FAILED test_lida_com_datas_implausiveis_vira_digitacao_pre_preenchida    KeyError: 'motivo'  (leitura veio ok: true)
FAILED test_lida_com_emissao_futura_vira_digitacao                       KeyError: 'motivo'
× datas lidas implausíveis abrem a digitação já preenchida               AssertionError: expected '' to be '1'
== S7
× diz como mudar o valor que veio do espelho, antes e depois de protocolada   TypeError: notaDoEspelho is not a function
```

### DEPOIS

Todos os testes acima passam. Suíte inteira no fim: backend `pytest -q` → **874 passed, 1 skipped** (6 min 44 s); frontend `npm test` → **29 arquivos, 92 testes passed**; `npm run typecheck` → limpo.

### Testes que mudaram por causa do gate

- `test_reajuste_irmao_em_outro_envio_ativo_nao_cobra` virou `test_reajuste_irmao_em_outro_envio_separado_tambem_cobra`
  (agora cobra, como pedido) e ganhou um caso a mais (ver abaixo).
- `test_digitada_com_180_dias_e_aceita` virou o teste por tipo (no teto passa, um dia a mais não); o de 2099 espera
  "máximo de 95 para certidão municipal".
- `test_lida_do_documento_com_validade_longa_continua_aceita` (desta branch) se inverteu: agora é
  `test_lida_com_datas_implausiveis_vira_digitacao_pre_preenchida`, como o S6 pede.
- `test_envio_feito_por_fora_e_numero_do_siga` (antigo): o .eml de teste ganhou `From` com endereço e `To`.

### Pontos em que fui além do texto do conserto

1. **S1, dois protocolos no mesmo e-mail.** Com o S1, a prévia de um e-mail que leva os dois protocolos juntos (o
   da medição e o do reajuste, pela rota de protocolos que aceita vários) cobraria a irmã que está no outro protocolo
   do mesmo e-mail. A prévia agora descarta essa pendência quando a irmã vai no mesmo e-mail (a pendência carrega o
   `medicao_id` da irmã para isso). Coberto por teste em `test_reajuste_irmao_em_outro_envio_separado_tambem_cobra`,
   acrescentado no commit do fix.
2. **S6, a tela.** O conserto supunha que a tela já preenchia o formulário com o que viesse; ela abria sempre vazia.
   `Documentos.tsx` passa a usar `lidos` quando vem. Teste de tela novo em `Documentos.test.tsx`.
3. **S6, onde mora o teto.** A tabela do S5 e a checagem ficam numa função só (`documentos.problema_nas_datas`), usada
   pela digitação e pela leitura automática. A leitura de `leitura_certidao.ler` em si (usada também pelo CLI de carga)
   não mudou; a checagem fica em `documentos.ler`, que é por onde passam a tela e a carga. Na carga pelo CLI, uma
   certidão assim cai em "sem leitura" com o motivo novo.
4. **S7.** O texto mora numa função pequena (`notaDoEspelho` em `MedicaoAtos.tsx`) para poder ser testado sem montar a
   página inteira.
