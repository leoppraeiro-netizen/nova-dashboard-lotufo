// B-11: admin em /admin/auditoria — filtro de ações com códigos internos sem tradução e texto "últimos 500"? (só leitura)
import { abrir, login, ir, captura, gravarTexto } from "./_lib.mjs";

const saida = [];
for (const rodada of [1, 2]) {
  const { browser, page } = await abrir();
  try {
    await login(page, "admin");
    await ir(page, "/admin/auditoria");
    await page.waitForSelector("#aud-acao option:nth-child(2)", { timeout: 30000, state: "attached" });
    const opcoes = await page.locator("#aud-acao option").evaluateAll(l => l.map(o => ({ valor: o.value, rotulo: o.innerText })));
    const semTraducao = opcoes.filter(o => o.valor && o.valor === o.rotulo);
    const nota = await page.locator("p.cartao__corpo.campo__nota").first().innerText();
    const colunaAcao = await page.locator("table tbody tr td:nth-child(3)").evaluateAll(l => [...new Set(l.map(e => e.innerText))]);
    const acoesCruasNaTabela = colunaAcao.filter(t => /^[a-z_]+\.[a-z_]+$/.test(t));
    const cap = await captura(page, `B-11-r${rodada}-auditoria`, false);
    // abre o select para a captura (o Chromium headless nao desenha o popup; registramos as opcoes em texto)
    saida.push({ rodada, totalOpcoes: opcoes.length, semTraducao, nota, acoesCruasNaTabela, linhasNaTabela: colunaAcao.length, captura: cap });
  } finally { await browser.close(); }
}
gravarTexto("B-11-evidencia.json", saida);
console.log(JSON.stringify(saida, null, 1));
