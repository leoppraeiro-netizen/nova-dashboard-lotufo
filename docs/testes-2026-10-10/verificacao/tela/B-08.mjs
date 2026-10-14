// B-08: /documentos — anexar ao mesmo tempo texto renomeado .pdf, PDF corrompido e arquivo vazio.
// As três recusadas? Alguma traz "ValueError"? O "topo" (região viva) mostra só a última? (engenharia; a leitura não grava nada)
import { abrir, login, ir, captura, gravarTexto, escritas } from "./_lib.mjs";
import crypto from "node:crypto";

const arquivos = [
  { name: "texto-renomeado.pdf", mimeType: "application/pdf", buffer: Buffer.from("Isto é só um texto com extensão .pdf, não é um PDF.\n") },
  { name: "corrompido.pdf", mimeType: "application/pdf", buffer: Buffer.concat([Buffer.from("%PDF-1.4\n"), crypto.randomBytes(4096)]) },
  { name: "vazio.pdf", mimeType: "application/pdf", buffer: Buffer.alloc(0) },
];

const saida = [];
for (const rodada of [1, 2]) {
  const { browser, page, rede } = await abrir();
  try {
    await login(page, "engenharia");
    await ir(page, "/documentos");
    const input = page.locator('input[type="file"][multiple]');
    await input.waitFor({ state: "attached", timeout: 20000 });
    const respostas = [];
    page.on("response", async r => { if (r.url().includes("/certidoes/ler")) respostas.push({ status: r.status(), corpo: (await r.text().catch(() => "")).slice(0, 300) }); });
    await input.setInputFiles(arquivos);
    // espera as três respostas (um upload por vez, em ordem)
    const inicio = Date.now();
    while (respostas.length < 3 && Date.now() - inicio < 90000) await page.waitForTimeout(500);
    await page.waitForTimeout(800);
    const fila = await page.locator(".documentos__fila li").allInnerTexts();
    const anuncio = await page.locator('p[role="status"]').allInnerTexts();
    const visiveisNoTopo = await page.locator("p.erro:visible, [role=alert]:visible").allInnerTexts();
    const temValueError = { fila: fila.some(t => /ValueError/.test(t)), anuncio: anuncio.some(t => /ValueError/.test(t)), respostas: respostas.some(r => /ValueError/.test(r.corpo)) };
    const cap = await captura(page, `B-08-r${rodada}-fila`, false);
    saida.push({ rodada, respostas, fila, anuncio, visiveisNoTopo, temValueError, recusadas: fila.filter(t => !/lendo/.test(t)).length, escritas: escritas(rede), captura: cap });
  } finally { await browser.close(); }
}
gravarTexto("B-08-evidencia.json", saida);
console.log(JSON.stringify(saida, null, 1));
