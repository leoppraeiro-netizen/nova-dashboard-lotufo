// Captura das referencias visuais do /ui-loop (.ui-review/referencias.md): Mercury e AWS Cloudscape.
//
// Uso, na raiz do repo:   node scripts/ui-capture/referencias.mjs
//                         node scripts/ui-capture/referencias.mjs --so mercury-transactions --saida .ui-review/referencias
// Grava <id>--<viewport>[--sN].png (no maximo 3 secoes por tela) e indice.json em .ui-review/referencias/
// (mesma regra de .gitignore das rodadas). Sites de terceiros ao vivo: nada e' interceptado, so' o relogio
// e o movimento ficam como na captura da dashboard. Banner de cookies: recusa o nao essencial quando aparece.
// Serve so' para comparar padroes (densidade, tabela, filtro, estado); nunca marca, cor ou texto.
import { existsSync } from "node:fs";
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const RAIZ = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const FRONT = path.join(RAIZ, "frontend");
const UI = path.join(RAIZ, ".ui-review");

const args = process.argv.slice(2);
const opcao = nome => { const i = args.indexOf(nome); return i >= 0 ? args[i + 1] : undefined; };
const SAIDA = path.resolve(RAIZ, opcao("--saida") ?? ".ui-review/referencias");
if (!SAIDA.startsWith(UI + path.sep)) { console.error("--saida precisa ficar dentro de .ui-review/"); process.exit(2); }
const so = opcao("--so")?.split(",").filter(Boolean);
const CANAL = process.env.UI_CAPTURE_CANAL || "chrome";

const MERCURY = "https://demo.mercury.com";
const CLOUDSCAPE = "https://cloudscape.design/examples/react";
// espera: o demo da Mercury fica escuro uns 8 s ate' montar o app e a tabela ainda passa uns segundos em esqueleto
const REFERENCIAS = [
  ...["dashboard", "transactions", "accounts", "tasks", "insights/overview", "invoicing", "invoicing/customers", "bill-pay", "settings/users"]
    .map(p => ({ id: `mercury-${p.replaceAll("/", "-")}`, url: `${MERCURY}/${p}`, espera: 20000 })),
  ...["table", "table-property-filter", "table-select-filter", "table-date-filter", "table-expandable", "details", "details-tabs",
    "dashboard", "form-validation", "delete-with-simple-confirmation"]
    .map(p => ({ id: `cloudscape-${p}`, url: `${CLOUDSCAPE}/${p}.html`, espera: 3000 })),
];

async function modulo(nome) {
  const dir = path.join(FRONT, "node_modules", ...nome.split("/"));
  const pkg = JSON.parse(await fs.readFile(path.join(dir, "package.json"), "utf8"));
  const exp = pkg.exports?.["."] ?? pkg.exports;
  const entrada = typeof exp === "string" ? exp : exp?.import ?? exp?.default ?? pkg.module ?? pkg.main;
  return import(pathToFileURL(path.join(dir, entrada)).href);
}

async function recusarCookies(pagina) {
  for (const nome of [/reject( all)?|decline|deny|only (necessary|essential)|necessary only/i, /^(ok|dismiss|close)$/i]) {
    const botao = pagina.getByRole("button", { name: nome }).first();
    if (await botao.isVisible().catch(() => false)) { await botao.click().catch(() => {}); await pagina.waitForTimeout(500); return; }
  }
}

async function main() {
  const rotas = JSON.parse(await fs.readFile(path.join(UI, "routes.json"), "utf8"));
  const lista = REFERENCIAS.filter(r => !so || so.includes(r.id));
  await fs.mkdir(SAIDA, { recursive: true });
  const { chromium } = await modulo("playwright");
  const navegador = await chromium.launch({ channel: CANAL });
  const indice = existsSync(path.join(SAIDA, "indice.json"))
    ? JSON.parse(await fs.readFile(path.join(SAIDA, "indice.json"), "utf8")) : { referencias: {} };
  indice.gerado_em = new Date().toISOString();
  indice.chrome_versao = navegador.version();

  for (const ref of lista) {
    indice.referencias[ref.id] = { url: ref.url, viewports: {} };
    for (const vp of rotas.viewports) {
      const nome = `${ref.id}--${vp.nome}`;
      process.stdout.write(`${nome} `);
      const contexto = await navegador.newContext({ viewport: { width: vp.width, height: vp.height }, locale: "en-US",
        reducedMotion: "reduce", colorScheme: "light" });
      const pagina = await contexto.newPage();
      const reg = { arquivos: [], erro: null };
      indice.referencias[ref.id].viewports[vp.nome] = reg;
      try {
        await pagina.goto(ref.url, { waitUntil: "domcontentloaded", timeout: 45000 });
        await pagina.waitForLoadState("networkidle", { timeout: 20000 }).catch(() => {});
        await pagina.waitForTimeout(ref.espera);
        await recusarCookies(pagina);
        await pagina.keyboard.press("Escape").catch(() => {}); // balao de dica do demo
        await pagina.evaluate(() => document.fonts.ready.then(() => undefined));
        reg.url_final = pagina.url();
        reg.titulo = await pagina.title();
        const m = await pagina.evaluate(() => ({ h: window.innerHeight, total: document.documentElement.scrollHeight }));
        const maxY = Math.max(0, m.total - m.h);
        const ys = [0];
        while (ys.length < 3 && ys.at(-1) < maxY) ys.push(Math.min(ys.at(-1) + m.h - 80, maxY));
        for (const [i, y] of ys.entries()) {
          await pagina.evaluate(top => window.scrollTo({ top, behavior: "instant" }), y);
          await pagina.waitForTimeout(300);
          const arquivo = ys.length === 1 ? `${nome}.png` : `${nome}--s${i + 1}.png`;
          await pagina.screenshot({ path: path.join(SAIDA, arquivo), animations: "disabled" });
          reg.arquivos.push(arquivo);
        }
        console.log(`ok (${ys.length})`);
      } catch (e) {
        reg.erro = String(e).slice(0, 300);
        console.log(`ERRO ${reg.erro}`);
      }
      await contexto.close();
    }
  }
  await navegador.close();
  await fs.writeFile(path.join(SAIDA, "indice.json"), JSON.stringify(indice, null, 2));
  console.log(`\n${path.relative(RAIZ, SAIDA)}`);
}

main().catch(e => { console.error(e); process.exit(1); });
