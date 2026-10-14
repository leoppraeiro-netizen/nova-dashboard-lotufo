// B-13: celular 375x812 — /inicio (valor grande quebra no meio do número?) e /obras/20/medicoes/632 (nome da obra truncado a 2–3 letras?)
import { abrir, login, ir, captura, gravarTexto } from "./_lib.mjs";

// quantas linhas o texto ocupa (retângulos de linha distintos do nó de texto) e se há reticências por text-overflow
function medir(el) {
  const r = el.getBoundingClientRect();
  let linhas = 0;
  const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT); let n;
  while ((n = walker.nextNode())) {
    const rg = document.createRange(); rg.selectNodeContents(n);
    const tops = [...new Set([...rg.getClientRects()].filter(x => x.width > 0).map(x => Math.round(x.top)))];
    linhas = Math.max(linhas, tops.length);
  }
  const cs = getComputedStyle(el);
  return { texto: el.innerText.replace(/\n/g, "⏎"), largura: Math.round(r.width), altura: Math.round(r.height), linhasDoTexto: linhas,
    fonte: cs.fontSize, truncado: el.scrollWidth > el.clientWidth + 1, scrollWidth: el.scrollWidth, clientWidth: el.clientWidth,
    textOverflow: cs.textOverflow, whiteSpace: cs.whiteSpace, overflowWrap: cs.overflowWrap, wordBreak: cs.wordBreak };
}

const saida = [];
for (const rodada of [1, 2]) {
  const { browser, page } = await abrir({ viewport: { width: 375, height: 812 }, mobile: true });
  try {
    await login(page, "engenharia");
    await ir(page, "/inicio");
    await page.waitForSelector(".ini-numeros", { timeout: 20000 });
    const valores = await page.locator(".ini-numero__valor").evaluateAll((l, f) => l.map(new Function("return " + f)()), medir.toString());
    const docLargura = await page.evaluate(() => ({ scrollWidth: document.documentElement.scrollWidth, clientWidth: document.documentElement.clientWidth }));
    const cap1 = await captura(page, `B-13-r${rodada}-inicio`, true);
    const cap1v = await captura(page, `B-13-r${rodada}-inicio-topo`, false);

    await ir(page, "/obras/20/medicoes/632");
    await page.waitForSelector(".topbar__titulo", { timeout: 20000 });
    const titulo = await page.locator(".topbar__titulo").evaluate((e, f) => new Function("return " + f)()(e), medir.toString());
    const metas = await page.locator(".topbar__meta").evaluateAll((l, f) => l.map(new Function("return " + f)()), medir.toString());
    const migalhas = await page.locator(".topbar__trilha").evaluate((e, f) => new Function("return " + f)()(e), medir.toString());
    const valorMed = await page.locator(".dado__valor--principal").evaluate((e, f) => new Function("return " + f)()(e), medir.toString());
    const doc2 = await page.evaluate(() => ({ scrollWidth: document.documentElement.scrollWidth, clientWidth: document.documentElement.clientWidth }));
    const cap2 = await captura(page, `B-13-r${rodada}-medicao-632-topo`, false);
    const cap2f = await captura(page, `B-13-r${rodada}-medicao-632`, true);
    saida.push({ rodada, inicio: { valores, documento: docLargura }, medicao: { titulo, metas, migalhas, valorMed, documento: doc2 }, capturas: [cap1, cap1v, cap2, cap2f] });
  } finally { await browser.close(); }
}
gravarTexto("B-13-evidencia.json", saida);
console.log(JSON.stringify(saida, null, 1));
