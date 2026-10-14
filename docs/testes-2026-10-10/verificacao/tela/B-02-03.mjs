// B-02: editar o valor da medição 632 e voltar ao original — a linha do tempo mostra as edições?
// B-03: valor "1234.56" — qual a mensagem de recusa?
// Engenharia. Valor original da 632: R$ 594.430,74 (59443074 centavos). O script restaura e confere pela API.
import { abrir, login, ir, captura, gravarTexto, escritas } from "./_lib.mjs";

const ORIGINAL = "594.430,74", ORIGINAL_CENTAVOS = 59443074;

async function editarValor(page, valor) {
  await page.click("#ato-protocolado");
  await page.waitForSelector("#campo-valor", { timeout: 10000 });
  await page.fill("#campo-valor", valor);
  const [resp] = await Promise.all([
    page.waitForResponse(r => r.url().includes("/api/medicoes/632/valor"), { timeout: 20000 }),
    page.click('button:has-text("Salvar valor")'),
  ]);
  await page.waitForTimeout(800);
  return { status: resp.status(), corpo: (await resp.text().catch(() => "")).slice(0, 300) };
}
const linhaTempo = page => page.locator(".lateral .linha-tempo li").allInnerTexts();
const valorApi = page => page.evaluate(async () => (await (await fetch("/api/contratos/20/medicoes")).json()).find(m => m.id === 632).valor_protocolado_centavos);

const saida = [];
for (const rodada of [1, 2]) {
  const { browser, page, rede } = await abrir();
  try {
    await login(page, "engenharia");
    await ir(page, "/obras/20/medicoes/632");
    await page.waitForSelector("#ato-protocolado", { timeout: 20000 });
    const antes = await linhaTempo(page);
    const valorAntes = await valorApi(page);
    const capAntes = await captura(page, `B-02-r${rodada}-antes`, false);

    // B-02: edita para 1,00 e volta
    const e1 = await editarValor(page, "1,00");
    const status1 = await page.locator('[role="status"]').allInnerTexts();
    const valorMeio = await valorApi(page);
    const e2 = await editarValor(page, ORIGINAL);
    const status2 = await page.locator('[role="status"]').allInnerTexts();
    const depois = await linhaTempo(page);
    const detalhesEstreito = await page.locator(".so-estreito .cartao__dica").allInnerTexts().catch(() => []);
    // recarrega a página para garantir que a linha do tempo vem fresca do servidor
    await ir(page, "/obras/20/medicoes/632");
    await page.waitForSelector("#ato-protocolado", { timeout: 20000 });
    const depoisRecarregado = await linhaTempo(page);
    const capDepois = await captura(page, `B-02-r${rodada}-depois`, false);
    const valorFinal = await valorApi(page);
    const novosEventos = depoisRecarregado.filter(x => !antes.includes(x));

    // B-03: valor com ponto decimal
    await page.click("#ato-protocolado");
    await page.waitForSelector("#campo-valor", { timeout: 10000 });
    await page.fill("#campo-valor", "1234.56");
    const [resp3] = await Promise.all([
      page.waitForResponse(r => r.url().includes("/api/medicoes/632/valor"), { timeout: 20000 }),
      page.click('button:has-text("Salvar valor")'),
    ]);
    await page.waitForTimeout(500);
    const erro3 = await page.locator("form p.erro").allInnerTexts();
    const cap3 = await captura(page, `B-03-r${rodada}-mensagem`, false);
    const corpo3 = (await resp3.text().catch(() => "")).slice(0, 300);
    await page.click('form button:has-text("Cancelar")');
    const valorFinal3 = await valorApi(page);

    saida.push({ rodada,
      b02: { valorAntes, e1, status1, valorMeio, e2, status2, antes, depois, depoisRecarregado, novosEventos, detalhesEstreito, valorFinal, restaurado: valorFinal === ORIGINAL_CENTAVOS, capturas: [capAntes, capDepois] },
      b03: { status: resp3.status(), corpo: corpo3, mensagemNaTela: erro3, valorDepois: valorFinal3, captura: cap3 },
      escritas: escritas(rede) });
  } finally { await browser.close(); }
}
gravarTexto("B-02-03-evidencia.json", saida);
console.log(JSON.stringify(saida, null, 1));
