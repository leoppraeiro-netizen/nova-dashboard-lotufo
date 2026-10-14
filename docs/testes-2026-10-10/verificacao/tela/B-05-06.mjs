// B-05: clique duplo em "Enviar a nota" manda um e-mail só? (confirmar = a tela protege)
// B-06: depois de editar o valor (mesmo valor) e enviar a nota, o aviso "Valor protocolado gravado." fica e não há confirmação do envio?
// Engenharia. Backend 8080 com simulador de e-mail (arquivos .json em backend/dados/correio-simulado/enviados).
// Rodadas: (1) 631, clique duplo [B-05 r1]; (2) 632, edição do valor + clique simples [B-06 r1];
//          (3) 638, edição do valor + clique duplo [B-05 r2 + B-06 r2]. A 630 (MT-402) fica intacta.
import fs from "node:fs";
import path from "node:path";
import { abrir, login, ir, captura, gravarTexto, escritas, arquivosSimulador, SIMULADOR } from "./_lib.mjs";

const brlCampo = c => (c / 100).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const medicaoApi = (page, id) => page.evaluate(async id => { const m = (await (await fetch("/api/contratos/20/medicoes")).json()).find(x => x.id === id); return { estado: m.estado, valor: m.valor_protocolado_centavos, congelada: m.congelada, protocolos: m.protocolos.length }; }, id);

async function rodar({ rodada, id, editarAntes, duplo }) {
  const { browser, page, rede, consola } = await abrir();
  const simAntes = arquivosSimulador();
  try {
    await login(page, "engenharia");
    await ir(page, `/obras/20/medicoes/${id}`);
    await page.waitForSelector("#etapa-4", { timeout: 20000 });
    const antes = await medicaoApi(page, id);
    let edicao = null;
    if (editarAntes) {
      await page.click("#ato-protocolado");
      await page.waitForSelector("#campo-valor", { timeout: 10000 });
      await page.fill("#campo-valor", brlCampo(antes.valor));
      const [r] = await Promise.all([
        page.waitForResponse(x => x.url().includes(`/api/medicoes/${id}/valor`), { timeout: 20000 }),
        page.click('button:has-text("Salvar valor")'),
      ]);
      await page.waitForTimeout(800);
      edicao = { status: r.status(), statusDepoisDaEdicao: await page.locator('[role="status"]').allInnerTexts() };
    }
    // etapa 4: com protocolo já aberto a janela de e-mail aparece; sem ele, "Começar o envio"
    const comecar = page.locator('button:has-text("Começar o envio")');
    if (await comecar.count()) {
      await Promise.all([
        page.waitForResponse(x => x.url().includes("/api/notas/envio/iniciar"), { timeout: 20000 }),
        comecar.click(),
      ]);
    }
    await page.waitForSelector("button.ol-enviar", { timeout: 30000 });
    const just = page.locator("#nota-just");
    if (await just.count()) await just.fill(`Verificação fase 3 (B-05/B-06), rodada ${rodada}: envio de teste ao simulador.`);
    await page.waitForTimeout(300);
    const botao = page.locator('button.ol-enviar:has-text("Enviar a nota")');
    const habilitado = await botao.isEnabled();
    const capAntes = await captura(page, `B-05-r${rodada}-antes-do-clique`, false);
    const t0 = Date.now();
    const esperaResp = page.waitForResponse(x => /\/api\/notas\/envio\/\d+\/enviar/.test(x.url()), { timeout: 90000 });
    if (duplo) await botao.dblclick(); else await botao.click();
    const resp = await esperaResp;
    const respTexto = (await resp.text().catch(() => "")).slice(0, 300);
    // deixa a página recarregar e eventuais segundos pedidos chegarem
    await page.waitForTimeout(4000);
    const posts = rede.filter(e => e.tipo === "req" && e.metodo === "POST" && /\/api\/notas\/envio\/\d+\/enviar/.test(e.url));
    const respostas = rede.filter(e => e.tipo === "res" && /\/api\/notas\/envio\/\d+\/enviar/.test(e.url)).map(e => ({ status: e.status, corpo: e.corpo }));
    const statusTextos = await page.locator('[role="status"]').allInnerTexts();
    const erros = await page.locator("p.erro").allInnerTexts();
    const textoPag = await page.locator("body").innerText();
    const confirmacaoEnvio = /enviad[ao]|Aguardando pagamento|Protocolo enviado/i.test(textoPag);
    const trechosEnvio = [...textoPag.matchAll(/[^\n]*(enviad[ao]|Protocolo enviado|Aguardando)[^\n]*/gi)].map(m => m[0].trim()).slice(0, 8);
    const capDepois = await captura(page, `B-05-r${rodada}-depois`, true);
    const depois = await medicaoApi(page, id);
    const simDepois = arquivosSimulador();
    const novos = simDepois.filter(f => !simAntes.includes(f)).map(f => {
      try { const j = JSON.parse(fs.readFileSync(path.join(SIMULADOR, f), "utf8")); const m = j.mensagem ?? j.message ?? j;
        const lista = x => Array.isArray(x) ? x.map(d => d?.emailAddress?.address ?? d?.endereco ?? d?.email ?? d) : x;
        return { arquivo: f, para: lista(m.toRecipients ?? m.para ?? j.para), copia: lista(m.ccRecipients ?? m.copia ?? j.copia), cco: lista(m.bccRecipients ?? m.cco ?? j.cco), assunto: m.subject ?? m.assunto ?? j.assunto, chaves: Object.keys(j) }; }
      catch (e) { return { arquivo: f, erro: String(e) }; }
    });
    return { rodada, medicao: id, duplo, editarAntes, antes, edicao, botaoHabilitado: habilitado, primeiroStatus: resp.status(), primeiraResposta: respTexto, duracaoMs: Date.now() - t0,
      postsDeEnvio: posts.length, respostasDeEnvio: respostas, statusTextosDepois: statusTextos, errosDepois: erros, confirmacaoEnvioNaTela: confirmacaoEnvio, trechosEnvio,
      depois, simulador: { antes: simAntes.length, depois: simDepois.length, novos }, escritas: escritas(rede), consola: consola.filter(c => !/WebGL|401/.test(c)), capturas: [capAntes, capDepois] };
  } finally { await browser.close(); }
}

const plano = [
  { rodada: 1, id: 631, editarAntes: false, duplo: true },
  { rodada: 2, id: 632, editarAntes: true, duplo: false },
  { rodada: 3, id: 638, editarAntes: true, duplo: true },
];
const so = process.argv[2] ? plano.filter(p => String(p.rodada) === process.argv[2]) : plano;
const saida = [];
for (const p of so) { const r = await rodar(p); saida.push(r); console.log(JSON.stringify(r, null, 1)); }
const anterior = fs.existsSync(path.join(path.dirname(new URL(import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1")), "B-05-06-evidencia.json")) && process.argv[2]
  ? JSON.parse(fs.readFileSync(path.join(path.dirname(new URL(import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1")), "B-05-06-evidencia.json"), "utf8")) : [];
gravarTexto("B-05-06-evidencia.json", [...anterior.filter(a => !saida.some(s => s.rodada === a.rodada)), ...saida].sort((a, b) => a.rodada - b.rodada));
