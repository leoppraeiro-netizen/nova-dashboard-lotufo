// B-01: "Medido no mês" do Início x "medido no mês" da Carteira (engenharia). Só leitura.
import { abrir, login, ir, captura, gravarTexto, textoPagina } from "./_lib.mjs";

const saida = [];
for (const rodada of [1, 2]) {
  const { browser, page, consola } = await abrir();
  try {
    await login(page, "engenharia");
    await ir(page, "/inicio");
    await page.waitForSelector(".ini-numeros", { timeout: 20000 });
    const numeros = await textoPagina(page, ".ini-numeros");
    const grafico = await textoPagina(page, ".ini-painel--grafico");
    const barras = await page.locator(".ini-barras__svg").evaluateAll(l => l.map(s => s.getAttribute("aria-label")));
    const legenda = await textoPagina(page, ".ini-legenda");
    const rodape = await textoPagina(page, ".ini-painel__rodape");
    const cap1 = await captura(page, `B-01-r${rodada}-inicio`);

    await ir(page, "/carteira");
    await page.waitForSelector(".kpis", { timeout: 20000 });
    const kpis = await page.locator(".kpi").evaluateAll(l => l.map(k => k.innerText.replace(/\n/g, " | ")));
    const cap2 = await captura(page, `B-01-r${rodada}-carteira`);
    saida.push({ rodada, inicio: { numeros, legenda, barras, rodape, grafico }, carteira: { kpis }, capturas: [cap1, cap2], consola });
  } finally { await browser.close(); }
}
gravarTexto("B-01-evidencia.json", saida);
console.log(JSON.stringify(saida, null, 1));
