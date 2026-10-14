// B-10: admin em /admin/usuarios — há como trocar senha ou perfil pela tela? (só leitura)
import { abrir, login, ir, captura, gravarTexto, textoPagina } from "./_lib.mjs";

const saida = [];
for (const rodada of [1, 2]) {
  const { browser, page } = await abrir();
  try {
    await login(page, "admin");
    await ir(page, "/admin/usuarios");
    await page.waitForSelector("table", { timeout: 20000 });
    const controlesTabela = await page.locator("table button, table input, table select, table a").evaluateAll(l =>
      l.map(e => `${e.tagName.toLowerCase()}:${(e.innerText || e.getAttribute("aria-label") || e.getAttribute("type") || "").trim().replace(/\s+/g, " ")}`));
    const botoesPagina = await page.locator("main button, .pagina button, button").evaluateAll(l => [...new Set(l.map(e => e.innerText.trim().replace(/\s+/g, " ")).filter(Boolean))]);
    const rotulos = await page.locator("label").evaluateAll(l => l.map(e => e.innerText.trim()));
    const texto = await textoPagina(page, "main, body");
    const temSenhaForaDoNovo = /trocar senha|redefinir|nova senha|alterar senha|mudar perfil|trocar perfil/i.test(texto);
    const cap = await captura(page, `B-10-r${rodada}-usuarios`);
    saida.push({ rodada, controlesTabela, botoesPagina, rotulos, temSenhaForaDoNovo, cabecalhoTabela: await page.locator("table th").allInnerTexts(), captura: cap });
  } finally { await browser.close(); }
}
gravarTexto("B-10-evidencia.json", saida);
console.log(JSON.stringify(saida, null, 1));
