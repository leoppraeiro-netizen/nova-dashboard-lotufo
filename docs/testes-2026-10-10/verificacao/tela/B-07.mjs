// B-07: /medicoes/aguardando-pagamento — registrar um nº numa linha MTPAR mostra alguma confirmação? (engenharia)
// Usa a medição 635 (Complexo Xtreme · 15ª medição, sem nº). No fim apaga o número pela API (numero "") e confere.
import { abrir, login, ir, captura, gravarTexto, escritas } from "./_lib.mjs";

const ROTULO = "Nº do protocolo de Complexo Xtreme · 15ª medição";
const numeroApi = page => page.evaluate(async () => (await (await fetch("/api/notas/aguardando-pagamento")).json()).find(l => l.medicao_id === 635)?.numero_orgao ?? null);

const saida = [];
for (const rodada of [1, 2]) {
  const { browser, page, rede } = await abrir();
  try {
    await login(page, "engenharia");
    await ir(page, "/medicoes/aguardando-pagamento");
    const campo = page.locator(`input[aria-label="${ROTULO}"]`);
    await campo.waitFor({ timeout: 20000 });
    const linha = campo.locator("xpath=ancestor::tr[1]");
    const antes = { numeroApi: await numeroApi(page), linha: await linha.innerText(), seloSiga: await linha.locator("text=sem protocolo SIGA").count() };
    const capAntes = await captura(page, `B-07-r${rodada}-antes`, false);
    await campo.fill(`X-TESTE-${rodada}`);
    const [resp] = await Promise.all([
      page.waitForResponse(r => r.url().includes("/api/notas/635/numero-orgao"), { timeout: 20000 }),
      linha.locator('button:has-text("Registrar")').click(),
    ]);
    await page.waitForTimeout(1200);
    const statusTextos = await page.locator('[role="status"], [aria-live], .notas__ok, .erro, .selo').allInnerTexts();
    const textoPagina = await page.locator("body").innerText();
    const depois = { numeroApi: await numeroApi(page), linha: await linha.innerText(), seloSiga: await linha.locator("text=sem protocolo SIGA").count(),
      valorCampo: await campo.inputValue(), botaoDesabilitado: await linha.locator('button:has-text("Registrar")').isDisabled(),
      temPalavraGravado: /gravad|registrad|salvo|confirmad/i.test(textoPagina), statusTextos };
    const capDepois = await captura(page, `B-07-r${rodada}-depois`, false);
    // desfaz: apaga o número pela API (texto vazio apaga, conforme o inventário)
    const limpeza = await page.evaluate(async () => {
      const eu = await (await fetch("/api/auth/eu")).json();
      const r = await fetch("/api/notas/635/numero-orgao", { method: "POST", headers: { "content-type": "application/json", "X-CSRF-Token": eu.csrf }, body: JSON.stringify({ numero: "" }) });
      return r.status;
    });
    const numeroFinal = await numeroApi(page);
    saida.push({ rodada, antes, post: { status: resp.status(), corpo: (await resp.text().catch(() => "")).slice(0, 200) }, depois, limpeza, numeroFinal, restaurado: numeroFinal === antes.numeroApi, escritas: escritas(rede), capturas: [capAntes, capDepois] });
  } finally { await browser.close(); }
}
gravarTexto("B-07-evidencia.json", saida);
console.log(JSON.stringify(saida, null, 1));
