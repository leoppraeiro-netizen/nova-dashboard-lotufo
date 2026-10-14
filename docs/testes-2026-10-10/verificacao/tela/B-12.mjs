// B-12: mensagens com código interno / inglês. (1) Nova medição MT-401 nº 32 → prévia; (2) Prazos MT-401 → prorrogação de 99999 dias.
// A prévia não grava; o pleito de 99999 dias deve ser recusado (422). Se o servidor aceitar, o script descarta o pleito criado.
import { abrir, login, ir, captura, gravarTexto, escritas } from "./_lib.mjs";

const saida = [];
for (const rodada of [1, 2]) {
  const { browser, page, rede } = await abrir();
  try {
    await login(page, "engenharia");
    // (1) prévia do espelho nº 32 (já existe a 32ª, competência 11/2025)
    await ir(page, "/obras/5/medicoes/nova");
    await page.waitForSelector("#esp-numero", { timeout: 20000 });
    await page.fill("#esp-numero", "32");
    await page.fill("#esp-competencia", "2025-11");
    await page.fill("#esp-medicao", "100,00");
    await Promise.all([
      page.waitForResponse(r => r.url().includes("/espelho/previa"), { timeout: 20000 }),
      page.click('button:has-text("Conferir")'),
    ]);
    await page.waitForTimeout(500);
    const erro1 = await page.locator("p.erro").allInnerTexts();
    const cap1 = await captura(page, `B-12-r${rodada}-previa`, false);

    // (2) prorrogação de 99999 dias
    await ir(page, "/obras/5/prazos");
    await page.waitForSelector("#pedir-prorrogacao", { timeout: 20000 });
    await page.click("#pedir-prorrogacao");
    await page.waitForSelector("#prazo-dias", { timeout: 10000 });
    await page.fill("#oficio-prazo", "999");
    await page.fill("#prazo-dias", "99999");
    await page.fill("#prazo-just", "Teste de verificação B-12 (fase 3).");
    const [resp] = await Promise.all([
      page.waitForResponse(r => r.url().includes("/pleitos") && r.request().method() === "POST", { timeout: 20000 }),
      page.click('button:has-text("Criar ofício")'),
    ]);
    const status2 = resp.status();
    let corpo2 = ""; try { corpo2 = await resp.text(); } catch {}
    await page.waitForTimeout(500);
    const erro2 = await page.locator("p.erro").allInnerTexts();
    const cap2 = await captura(page, `B-12-r${rodada}-prazo`, false);
    let limpeza = null;
    if (status2 === 201) {
      // não deveria acontecer; descarta o pleito criado para não deixar rastro
      const id = JSON.parse(corpo2).id;
      limpeza = await page.evaluate(async (id) => {
        const eu = await (await fetch("/api/auth/eu")).json();
        const r = await fetch(`/api/pleitos/${id}/descartar`, { method: "POST", headers: { "content-type": "application/json", "X-CSRF-Token": eu.csrf }, body: JSON.stringify({ motivo: "criado por engano no teste B-12" }) });
        return r.status;
      }, id);
    }
    saida.push({ rodada, previa: { erro: erro1, rede: rede.filter(e => e.url.includes("previa")) }, prazo: { status: status2, corpo: corpo2.slice(0, 400), erro: erro2, limpeza }, escritas: escritas(rede), capturas: [cap1, cap2] });
  } finally { await browser.close(); }
}
gravarTexto("B-12-evidencia.json", saida);
console.log(JSON.stringify(saida, null, 1));
