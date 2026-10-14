# Plano — Notas a enviar em produção (09/10/2026)

Objetivo do dia: o Leo precisa enviar várias notas fiscais hoje pela dashboard. Entra em produção o fluxo
"nota emitida → enviar a nota ao contratante → aguardando pagamento", com as 12 decisões do
`docs/mapeamento-envio-nota-2026-10-08.md` §6a e as telas v3 do quadro (lista, SINFRA, MTPAR, consórcio).
Sem revisores/críticos nesta rodada (decisão do Leo). Branch `feat/notas-envio`. Outras telas (Login 3D,
Início v3) ficam para depois. O protocolo da medição (etapa `medicao` da SINFRA) continua existindo; a
página nova usa só a etapa `nota`/`unico`.

Referências: §3 (Para/Cc/assunto por obra), §5 (anexos), §6a (D1–D12) do mapeamento; v3 das telas em
`scratchpad f316f4b7…\notas-v2\gerar_notas_v3.py` e capturas `notas-v2\capturas\*-v3.png`.

## Regras que entram (resumo das decisões)
- D1 assunto MTPAR: `{oficio_barra} - {medicao} ({competencia}) - {obra}` → `CT/361/LT/2026 - 15ª Medição (09/2026) - Complexo Xtreme`.
- D2 corpo do e-mail montado pela lista real de anexos (só o que está pronto).
- D3 carta MTPAR em timbrado com a linha "Engenheiro(a) Fiscal: {fiscal}" abaixo do A/C.
- D4 regularidade mensal anexada com o nome `Regularidade mensal - {Empresa} - {MM-AAAA}.pdf`.
- D5 sem ficha CNO nos anexos.
- D7 zip de certidões só com as 5 (federal, FGTS, trabalhista, estadual, municipal); falência fora.
- D8 certidão a <15 dias = aviso; vencida = **bloqueia** o envio (sem justificativa).
- D9 medição + reajuste no mesmo e-mail na SINFRA e Pref. VG; separados na MTPAR e SES. Botão juntar/separar.
- D10 nº do SIGA (MTPAR) registrado na lista "Aguardando pagamento".
- D11 regularidade de quem tem folha própria (`entidades.regularidade_propria`).
- Estadual e municipal passam a ser cobradas por padrão (`certidao_tipos.aplicavel_por_padrao=1`).
- Cobrança por e-mail de certidão vencendo (<15 dias, 1×/dia 08:00) e vencida (a cada 2 h, 08–18 h Cuiabá), **só para o e-mail do Leonardo**.
- "Registrar envio feito por fora": data + observação (+ .eml opcional) → medição vira `protocolada` (aguardando pagamento), origem `externo`.
- Depois do envio a medição vai para "Aguardando pagamento" (= `protocolada`); na MTPAR com a marca "sem protocolo SIGA" até registrar o número.

## Contrato da API (backend expõe, frontend consome)
`GET /api/notas/a-enviar` →
```
{ "envios": [ {
    "chave": "c12:m637",            # contrato + medições (ids ordenados) — estável
    "contrato_id": 12, "obra": "MT-388 Porto Esperidião/Cáceres", "orgao": "SINFRA", "orgao_sub": "SUEF II",
    "familia": "sinfra", "grupo": "SINFRA" | "MTPAR" | "SES-MT" | "Pref. VG" | "Pref. Cuiabá",
    "a_pedido": false,               # true só para pref-cuiaba
    "medicao_ids": [637, 638], "descricao": "14ª medição + reajuste",
    "notas": [ {"numero": "2340", "natureza": "execucao", "municipio": "Cáceres", "arquivo": "NFS 2340 …pdf", "valor_centavos": 123} ],
    "valor_centavos": 241890633, "emitida_em": "2026-10-08", "dias": 1,
    "situacao": "pronto" | "pendente" | "bloqueado" | "a_pedido",
    "aviso": "Falta a regularidade · municipal vence em 8 dias" | null,
    "itens": [ {"chave":"notas","rotulo":"Notas fiscais (4)","detalhe":"NFS 2340, 2341 (medição) · 2342, 2343 (reajuste)","estado":"ok"},
               {"chave":"certidoes:lotufo","rotulo":"Certidões Lotufo (5)","detalhe":"municipal vence em 8 dias","estado":"aviso"},
               {"chave":"regularidade:lotufo","rotulo":"Regularidade mensal","detalhe":"O DP ainda não enviou o arquivo de 08/2026","estado":"falta","acao":"anexar_regularidade","entidade_id":1,"competencia":"2026-08"} ],
    "protocolo_id": 55 | null        # protocolo (etapa nota/unico) já iniciado para esse envio
  } ],
  "contadores": {"Todas": 8, "SINFRA": 3, "MTPAR": 2, "SES-MT": 1, "Pref. VG": 1, "Pref. Cuiabá": 1} }
```
Estados de item: `ok` (verde), `aviso` (âmbar, <15 dias), `falta` (âmbar, documento ausente → justificativa), `vencida` (vermelho → bloqueia).

`POST /api/notas/envio/iniciar` `{contrato_id, medicao_ids}` → cria (ou devolve) o protocolo da etapa `nota` (sinfra) / `unico` (demais) com essas medições; responde `{protocolo_id}`. Juntar/separar = chamar de novo com outra lista de `medicao_ids` (descarta o rascunho anterior se ainda não montado).

`GET /api/notas/envio/{protocolo_id}` → `{envio (como acima), familia, etapa, situacao_protocolo (rascunho|montado|assinado|enviado), carta: {oficio, paginas:[...]} | null, previa: {para:[], copia:[], assunto, corpo, anexos:[{nome, origem}]}, bloqueio: str|null, pendencias:[str], justificativa_obrigatoria: bool}` — reaproveita `protocolo.previa_envio` e `pendencias`.

`POST /api/notas/envio/{protocolo_id}/enviar` `{para, copia, assunto, corpo, justificativa?}` → envia pelo Outlook do usuário (`correio.enviar_e_registrar`), marca `protocolada`, responde `{envio_id}`. Recusa com 409 se `bloqueio`.

`POST /api/notas/envio-externo` `{medicao_ids, enviado_em (YYYY-MM-DD), observacao}` (+ multipart opcional `eml`) → `protocolada`, origem `externo`.

`GET /api/notas/aguardando-pagamento` → `[{medicao_id, contrato_id, obra, orgao, descricao, valor_centavos, enviada_em, numero_orgao, familia, origem}]`.
`POST /api/notas/{medicao_id}/numero-orgao` `{numero}` → grava nº do SIGA (reaproveita `registrar_numero_orgao`).

Endpoints existentes reaproveitados: `/api/protocolos/{pid}/montar`, `/assinado` (upload do PDF assinado, confere páginas), `/api/documentos/zip`, regularidades (`POST` já existente para anexar o PDF do mês).

## Blocos
- **B1 Backend — regras** (`backend/`): cartas.yaml (D1/D2), carta.py (D3), nome da regularidade (D4), tirar `cno` dos soltos da SINFRA e aceitar `pecas_soltas` (relatórios assinados do BRT), zip só 5 (D7), bloqueio por vencida (D8) em `pendencias`, `junta_naturezas` também na prefeitura de VG (D9), migração 031 (estadual/municipal `aplicavel_por_padrao=1`; `medicoes.envio_origem` se precisar), job de cobrança por e-mail (certidoes vencendo/vencidas → só Leo), testes.
- **B2 Backend — API /api/notas** (`backend/app/api_notas_envio.py` + `notas_envio.py`): contrato acima, montado sobre `protocolo.py`; testes com o simulador de e-mail.
- **B3 Frontend** (`frontend/src/`): páginas `Notas` (lista + painel, pílulas, grupos, vazia), `EnviarNota` (seções 1–2 SINFRA/consórcio; 1–3 MTPAR/SES com montar/baixar/anexar assinado), `AguardandoPagamento` (lista + nº SIGA), modal "Registrar envio feito por fora"; menu "Notas" com subitens; identidade visual atual do app (não a nova).
- **B4 Cadastro** (`cadastro/`): Para/Cc por obra conforme §3 (fiscais, `destinatarios_extras`, `protocolo_para`/`protocolo_copia` dos órgãos), `cadastro validar` + `aplicar --ensaio`.
- **B5 Deploy**: merge em master, `scripts/deploy.ps1`, `cadastro aplicar`, `/api/health`, teste real com uma nota.

## Comandos
- Backend: `cd backend; .venv\Scripts\python -m pytest -q`
- Frontend: `cd frontend; npx tsc -b; npm run lint; npm test; npx vite build`
- Dev: `$env:DASH_DEV='1'` (banco de dev); simulador de e-mail `DASH_GRAPH_SIMULADOR=<pasta>`.
