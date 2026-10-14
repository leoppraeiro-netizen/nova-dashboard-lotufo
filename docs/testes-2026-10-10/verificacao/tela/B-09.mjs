// B-09: diretoria vê o botão "Enviar a nota →" e recebe mensagem crua "Permissão necessária: editar_cadastros"? E /conta?
// Diretoria não tem editar_cadastros: todo POST leva 403 antes de qualquer e-mail (nada é enviado nem criado).
import { abrir, login, ir, captura, gravarTexto, escritas } from "./_lib.mjs";

const saida = [];
for (const rodada of [1, 2]) {
  const { browser, page, rede } = await abrir();
  try {
    await login(page, "diretoria");
    await ir(page, "/medicoes/enviar-nota");
    await page.waitForSelector(".nota-cartao", { timeout: 20000 });
    const menu = await page.locator("nav.trilho .trilho__rotulo").allInnerTexts();
    // (a) envio sem protocolo ainda (632): o clique tenta iniciar o protocolo → 403
    await page.locator('.nota-cartao:has-text("Reajuste da 7ª medição")').first().click();
    await page.waitForTimeout(300);
    const botao = page.locator('button:has-text("Enviar a nota →")');
    const botaoVisivel = await botao.isVisible();
    const [respIniciar] = await Promise.all([
      page.waitForResponse(r => r.url().includes("/api/notas/envio/iniciar"), { timeout: 20000 }),
      botao.click(),
    ]);
    await page.waitForTimeout(500);
    const erroA = await page.locator(".nota-painel p.erro").allInnerTexts();
    const capA = await captura(page, `B-09-r${rodada}-enviar-nota`, false);

    // (b) envio com protocolo já aberto (631, protocolo 3): o clique leva à página da medição, etapa 4, com a janela de e-mail
    await page.locator('.nota-cartao:has-text("7ª medição")').first().click();
    await page.waitForTimeout(300);
    await botao.click();
    await page.waitForURL(/\/obras\/20\/medicoes\/631/, { timeout: 20000 });
    await page.waitForSelector(".ol-enviar", { timeout: 20000 });
    const just = page.locator("#nota-just");
    if (await just.count()) await just.fill("Verificação B-09: diretoria tentando enviar.");
    const enviar = page.locator('button.ol-enviar:has-text("Enviar a nota")');
    const enviarVisivel = await enviar.isVisible();
    const enviarHabilitado = await enviar.isEnabled();
    let respEnviar = null, erroB = [];
    if (enviarHabilitado) {
      const [r] = await Promise.all([
        page.waitForResponse(x => x.url().includes("/api/notas/envio/3/enviar"), { timeout: 20000 }),
        enviar.click(),
      ]);
      respEnviar = { status: r.status(), corpo: (await r.text().catch(() => "")).slice(0, 200) };
      await page.waitForTimeout(500);
      erroB = await page.locator(".nota-envio p.erro").allInnerTexts();
    }
    const capB = await captura(page, `B-09-r${rodada}-etapa4`, false);

    // (c) /conta
    await ir(page, "/conta");
    await page.waitForTimeout(1500);
    const textoConta = await page.locator("main, body").first().innerText();
    const errosConta = await page.locator("p.erro, [role=alert]").allInnerTexts();
    const capC = await captura(page, `B-09-r${rodada}-conta`, false);

    saida.push({ rodada, menu, a: { botaoVisivel, status: respIniciar.status(), corpo: (await respIniciar.text().catch(() => "")).slice(0, 200), erroNaTela: erroA },
      b: { enviarVisivel, enviarHabilitado, respEnviar, erroNaTela: erroB }, conta: { errosConta, trecho: textoConta.slice(0, 600) },
      escritas: escritas(rede), capturas: [capA, capB, capC] });
  } finally { await browser.close(); }
}
gravarTexto("B-09-evidencia.json", saida);
console.log(JSON.stringify(saida, null, 1));
