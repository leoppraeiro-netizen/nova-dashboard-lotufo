// B-04: tabela de notas da etapa 3 em 1024x768 — a coluna "Nota" fica cortada / rola na horizontal? (engenharia, só leitura)
import { abrir, login, ir, captura, gravarTexto } from "./_lib.mjs";

const saida = [];
for (const rodada of [1, 2]) {
  const { browser, page } = await abrir({ viewport: { width: 1024, height: 768 } });
  try {
    await login(page, "engenharia");
    await ir(page, "/obras/20/medicoes/631");
    await page.waitForSelector("#etapa-3", { timeout: 20000 });
    // se a etapa 3 estiver recolhida (feita), abre
    const tag = await page.locator("#etapa-3").evaluate(e => e.tagName);
    if (tag === "DETAILS") await page.locator("#etapa-3 > summary").click();
    await page.waitForSelector("#etapa-3 table", { timeout: 20000 });
    await page.locator("#etapa-3 table").first().scrollIntoViewIfNeeded();
    const medidas = await page.locator("#etapa-3 table").first().evaluate(t => {
      const rol = t.closest("[class*=rolagem], .rolagem, div") ;
      let c = t.parentElement; while (c && getComputedStyle(c).overflowX !== "auto" && getComputedStyle(c).overflowX !== "scroll" && c !== document.body) c = c.parentElement;
      const cont = c ?? t.parentElement;
      const ths = [...t.querySelectorAll("th")].map(th => ({ texto: th.innerText, left: Math.round(th.getBoundingClientRect().left), right: Math.round(th.getBoundingClientRect().right) }));
      const r = cont.getBoundingClientRect();
      return { tabela: { scrollWidth: t.scrollWidth, clientWidth: t.clientWidth, offsetWidth: t.offsetWidth },
        contêiner: { classe: cont.className, overflowX: getComputedStyle(cont).overflowX, scrollWidth: cont.scrollWidth, clientWidth: cont.clientWidth, left: Math.round(r.left), right: Math.round(r.right) },
        rolaHorizontal: cont.scrollWidth > cont.clientWidth + 1,
        colunas: ths, janela: window.innerWidth, _rol: rol?.className };
    });
    const cap = await captura(page, `B-04-r${rodada}-1024`, false);
    const capFull = await captura(page, `B-04-r${rodada}-1024-pagina`, true);
    // rolar o contêiner até o fim para ver se a coluna aparece
    await page.locator("#etapa-3 table").first().evaluate(t => { let c = t.parentElement; while (c && !["auto","scroll"].includes(getComputedStyle(c).overflowX) && c !== document.body) c = c.parentElement; if (c) c.scrollLeft = 9999; });
    const cap2 = await captura(page, `B-04-r${rodada}-1024-rolado`, false);
    saida.push({ rodada, medidas, capturas: [cap, capFull, cap2] });
  } finally { await browser.close(); }
}
gravarTexto("B-04-evidencia.json", saida);
console.log(JSON.stringify(saida, null, 1));
