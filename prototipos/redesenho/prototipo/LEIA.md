# Protótipos aprovados do redesenho

Aprovados pelo Leo em 16/10/2026 na página de protótipos (dados inventados). São a referência visual e de
conteúdo da implementação de cada tela; abra o `.html` no navegador a partir desta pasta.

| Tela | Issue | Arquivo |
|---|---|---|
| Obras: escolha do contratante e lista de obras | #159 | `obras.html`, `obras-lista.html` |
| Página da obra | #160 | `pagina-da-obra.html` |
| Documentos: empresas e página da empresa | #161 | `documentos.html`, `documentos-empresa.html` |
| A receber | #162 | `a-receber.html` |
| Carteira | #163 | `carteira.html` |
| Administração | #164 | `administracao.html` |
| Minha conta | #165 | `minha-conta.html` |

`base.css` é cópia de `frontend/src/tokens.css` com estilos só de protótipo no fim; `shell.js` desenha a casca
(trilho e barra) igual a `Casca.tsx`. O protótipo mostra todos os botões para todos os perfis: a implementação
mantém as permissões por perfil de hoje. A Página da medição e a aba Enviar nota (#152, #153, #157) ficaram fora:
o Leo pediu análise de fluxos redundantes antes.
