// Teste de navegação da Fase C do /ui-architecture: percorre cada tarefa de scripts/ui-tasks/tarefas.mjs no
// build do frontend, com toda chamada /api respondida pelas fixtures de .ui-review/fixtures (como a captura),
// conta os cliques e mede onde a resposta aparece (em alturas de tela) e se aparece sem rolar.
//
// Uso, na raiz do repo:   node scripts/ui-tasks/percorrer.mjs --ate 3
// Em frontend/:           npm run ui:tasks -- --ate 3
// Opções: --ate <N>        fatias já feitas: tarefa com `desde` maior fica "pendente" e não falha
//         --so T04,T15     só essas tarefas (prefixo do id)
//         --viewports 1366x768   --sem-build (reusa .ui-review/.build)
// Cada tarefa entra por "/" e confere que caiu na entrada do perfil (antes da fatia que muda a entrada, só
// avisa e abre a rota de início). Falha (código 1) quando uma tarefa já possível não acha a resposta, passa
// do custo em cliques, rola mais que na linha de base (regressão) ou quebra a página. Rolagem acima do
// proposto × 1,3 vira aviso, e também a rolagem do caminho (até ver cada elemento clicado) acima de 0,3
// tela. Grava o resultado em .ui-review/arquitetura/capturas/ui-tasks.json (ignorado pelo git, como as
// capturas).
import { existsSync } from "node:fs";
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const RAIZ = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const FRONT = path.join(RAIZ, "frontend");
const UI = path.join(RAIZ, ".ui-review");
const FIXTURES = path.join(UI, "fixtures");
const BUILD = path.join(UI, ".build");
const CONFIG_VITE = path.join(FRONT, "vite.config.ts");
const SAIDA = path.join(UI, "arquitetura", "capturas", "ui-tasks.json");

const args = process.argv.slice(2);
const opcao = n => { const i = args.indexOf(n); return i >= 0 ? args[i + 1] : undefined; };
const ate = Number(opcao("--ate") ?? 99);
const so = opcao("--so")?.split(",").filter(Boolean);
const soVp = opcao("--viewports")?.split(",").filter(Boolean);

async function modulo(nome) {
  const dir = path.join(FRONT, "node_modules", ...nome.split("/"));
  const pkg = JSON.parse(await fs.readFile(path.join(dir, "package.json"), "utf8"));
  const exp = pkg.exports?.["."] ?? pkg.exports;
  const entrada = typeof exp === "string" ? exp : exp?.import ?? exp?.default ?? pkg.module ?? pkg.main;
  return import(pathToFileURL(path.join(dir, entrada)).href);
}

// Mesma regra da captura: GET /api/contratos/7/cabecalho -> api/contratos/7/cabecalho.json; a consulta vira
// sufixo e cai no arquivo sem sufixo quando não há variante; método diferente de GET vira sufixo.
function arquivoFixture(metodo, caminho, busca) {
  const base = path.join(FIXTURES, ...caminho.replace(/^\/+/, "").split("/"));
  const consulta = [...new URLSearchParams(busca)].filter(([k]) => k !== "v")
    .sort(([a], [b]) => a.localeCompare(b)).map(([k, v]) => `${k}=${v}`).join("&");
  const nomes = metodo === "GET"
    ? [...(consulta ? [`${base}.${consulta}.json`] : []), `${base}.json`, `${base}.svg`, `${base}.png`]
    : [...(consulta ? [`${base}.${consulta}.${metodo}.json`] : []), `${base}.${metodo}.json`];
  return nomes.find(n => existsSync(n)) ?? null;
}

const TIPOS = { ".json": "application/json; charset=utf-8", ".svg": "image/svg+xml", ".png": "image/png" };

async function main() {
  const { tarefas, ENTRADA } = await import(pathToFileURL(path.join(RAIZ, "scripts", "ui-tasks", "tarefas.mjs")).href);
  const rotas = JSON.parse(await fs.readFile(path.join(UI, "routes.json"), "utf8"));
  const viewports = rotas.viewports.filter(v => !soVp || soVp.includes(v.nome));
  const lista = tarefas.filter(t => !so || so.some(s => t.id.startsWith(s)));
  const { build, preview } = await modulo("vite");
  const { chromium } = await modulo("playwright");

  if (!args.includes("--sem-build") || !existsSync(path.join(BUILD, "index.html"))) {
    console.log("build do frontend em .ui-review/.build ...");
    await build({ root: FRONT, configFile: CONFIG_VITE, logLevel: "warn", build: { outDir: BUILD, emptyOutDir: true } });
  }
  const servidor = await preview({ root: FRONT, configFile: CONFIG_VITE, logLevel: "warn", build: { outDir: BUILD },
    preview: { host: "127.0.0.1", port: 4189, strictPort: false, open: false, proxy: {} } });
  const BASE = `http://127.0.0.1:${servidor.httpServer.address().port}`;
  const navegador = await chromium.launch({ channel: process.env.UI_CAPTURE_CANAL || "chrome" });
  const saida = { gerado_em: new Date().toISOString(), ate, tarefas: [] };

  for (const t of lista) {
    for (const vp of viewports) {
      const reg = { id: t.id, viewport: vp.nome, desde: t.desde, meta_cliques: t.cliques, situacao: "ok",
        telas: [], cliques: 0, passos: [], resposta: null, faltou: [], erros: [], avisos: [] };
      saida.tarefas.push(reg);
      if (t.desde > ate) { reg.situacao = "pendente"; continue; }
      const ctx = await navegador.newContext({ viewport: { width: vp.width, height: vp.height }, locale: "pt-BR",
        timezoneId: rotas.fuso, reducedMotion: "reduce", serviceWorkers: "block" });
      await ctx.route(u => u.pathname.startsWith("/api/"), async rota => {
        const req = rota.request(); const u = new URL(req.url());
        const chave = `${req.method()} ${u.pathname}`;
        if (chave === "GET /api/auth/eu" && t.perfil) {
          return rota.fulfill({ status: 200, contentType: TIPOS[".json"], body: JSON.stringify({ ...t.perfil, csrf: "csrf-fixture" }) });
        }
        const troca = t.fixtures?.[chave + u.search] ?? t.fixtures?.[chave];
        if (troca) {
          const arq = typeof troca === "string" ? path.join(FIXTURES, troca) : null;
          if (arq) return rota.fulfill({ status: 200, contentType: TIPOS[".json"], body: await fs.readFile(arq) });
          return rota.fulfill({ status: troca.status ?? 200, contentType: TIPOS[".json"], body: JSON.stringify(troca.json ?? {}) });
        }
        const arq = arquivoFixture(req.method(), u.pathname, u.search);
        if (!arq) { reg.faltou.push(`${chave}${u.search}`); return rota.fulfill({ status: 404, contentType: TIPOS[".json"], body: '{"detail":"sem fixture"}' }); }
        return rota.fulfill({ status: 200, contentType: TIPOS[path.extname(arq)] ?? "application/octet-stream", body: await fs.readFile(arq) });
      });
      const p = await ctx.newPage();
      p.setDefaultTimeout(8000);
      p.on("pageerror", e => reg.erros.push(String(e).slice(0, 200)));
      await p.clock.setFixedTime(new Date(rotas.relogio));
      try {
        // a entrada do perfil: "/" leva à tela de início da tarefa?
        await p.goto(BASE + "/", { waitUntil: "networkidle" });
        await assentar(p);
        const entrada = new URL(p.url()).pathname;
        if (entrada !== t.inicio) {
          const e = ENTRADA[t.perfil?.perfil ?? "admin"];
          const msg = `"/" levou a ${entrada}, o mapa diz ${t.inicio}`;
          if (e && ate >= e.desde) reg.erros.push(msg); else reg.avisos.push(`${msg} (até a fatia ${e?.desde})`);
          await p.goto(BASE + t.inicio, { waitUntil: "networkidle" });
          await assentar(p);
        }
        reg.telas.push(onde(p));
        for (const passo of t.passos ?? []) {
          const alvo = p.locator(passo.clicar).first();
          // rolagem do caminho: o quanto a pessoa rola, na tela em que esta', ate' ver o que vai clicar
          const caixa = await alvo.evaluate(el => ({ fim: el.getBoundingClientRect().bottom, h: window.innerHeight }));
          reg.rolagem_caminho = +((reg.rolagem_caminho ?? 0) + Math.max(0, caixa.fim - caixa.h) / caixa.h).toFixed(2);
          await alvo.click();
          reg.cliques++;
          await assentar(p);
          if (reg.telas.at(-1) !== onde(p)) reg.telas.push(onde(p));
          reg.passos.push(passo.rotulo ?? passo.clicar);
        }
        if (!t.manterRolagem) await p.evaluate(() => window.scrollTo({ top: 0, behavior: "instant" }));
        reg.resposta = await medirResposta(p, t.resposta, t.manterRolagem);
      } catch (e) {
        reg.erros.push(String(e.message ?? e).split("\n")[0].slice(0, 200));
      }
      await ctx.close();
      if (!reg.resposta?.achou) reg.situacao = "falhou";
      if (reg.cliques > t.cliques) { reg.situacao = "falhou"; reg.erros.push(`${reg.cliques} cliques, o mapa diz ${t.cliques}`); }
      if (reg.resposta?.achou) {
        // rolagem até ver o fim da resposta: o quanto o fim passa da primeira tela
        const rolagem = +Math.max(0, reg.resposta.fim_telas - 1).toFixed(2);
        reg.resposta.rolagem_telas = rolagem;
        const base = t.base?.[vp.nome], proposto = t.proposto?.[vp.nome];
        if (base !== undefined && rolagem > base + 0.05) reg.erros.push(`rola ${rolagem} telas, a linha de base rolava ${base}`);
        else if (proposto !== undefined && rolagem > proposto * 1.3 + 0.3) reg.avisos.push(`rola ${rolagem} telas, o proposto era ${proposto}`);
        if (!reg.resposta.sem_rolar) reg.avisos.push(`resposta começa a ${reg.resposta.topo_telas} telas`);
      }
      if ((reg.rolagem_caminho ?? 0) > 0.3) reg.avisos.push(`o caminho rola ${reg.rolagem_caminho} telas até os cliques`);
      if (reg.erros.length) reg.situacao = "falhou";
    }
  }

  await fs.mkdir(path.dirname(SAIDA), { recursive: true });
  await fs.writeFile(SAIDA, JSON.stringify(saida, null, 2) + "\n", "utf8");
  await navegador.close();
  await servidor.close();

  for (const r of saida.tarefas) {
    const resp = r.resposta?.achou ? `resposta ${r.resposta.topo_telas}–${r.resposta.fim_telas} telas, rola ${r.resposta.rolagem_telas}${r.resposta.sem_rolar ? " (começa sem rolar)" : ""}` : "";
    console.log(`${r.situacao.padEnd(8)} ${r.id.padEnd(15)} ${r.viewport.padEnd(9)} ${r.situacao === "pendente" ? `fatia ${r.desde}`
      : `${r.cliques}/${r.meta_cliques} cliques · ${r.telas.join(" > ")} · ${resp}`}${r.avisos.length ? " · " + r.avisos.join("; ") : ""}${r.erros.length ? " · ERRO " + r.erros.join(" | ") : ""}${r.faltou.length ? " · sem fixture " + r.faltou.join(", ") : ""}`);
  }
  const falhas = saida.tarefas.filter(r => r.situacao === "falhou");
  const ok = saida.tarefas.filter(r => r.situacao === "ok").length;
  const pend = saida.tarefas.filter(r => r.situacao === "pendente").length;
  console.log(`\n${ok} ok · ${falhas.length} falharam · ${pend} pendentes (fatia > ${ate}) · ${path.relative(RAIZ, SAIDA)}`);
  if (falhas.length) process.exit(1);
}

const onde = p => { const u = new URL(p.url()); return u.pathname + u.search + u.hash; };

async function assentar(p) {
  await p.waitForLoadState("networkidle").catch(() => {});
  await p.waitForFunction(() => !/Carregando|carregando…|Verificando as certidões/.test(document.body?.innerText ?? ""), null, { timeout: 8000 }).catch(() => {});
  await p.evaluate(() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(() => r()))));
}

// Resposta = um ou mais alvos {seletor, texto?}; mede o primeiro e o último elemento visível encontrados, em
// telas a partir do topo (ou, com manterRolagem, de onde a página está: a âncora do link já rolou).
// Com vários alvos, cada um precisa aparecer.
async function medirResposta(p, resposta, manterRolagem = false) {
  const alvos = Array.isArray(resposta) ? resposta : [resposta];
  const caixas = [];
  let faltaAlvo = false;
  for (const a of alvos) {
    let loc = p.locator(a.seletor);
    if (a.texto) loc = loc.filter({ hasText: a.texto });
    const n = await loc.count();
    let deste = 0;
    for (let i = 0; i < Math.min(n, 400); i++) {
      // checkVisibility: o conteúdo de <details> fechado tem caixa no Chrome atual, mas não aparece
      const b = await loc.nth(i).evaluate(el => { if (el.checkVisibility && !el.checkVisibility()) return null; const r = el.getBoundingClientRect();
        return r.width > 0 && r.height > 0 ? { top: r.top + window.scrollY, bottom: r.bottom + window.scrollY } : null; });
      if (b) { caixas.push(b); deste++; }
    }
    if (!deste) faltaAlvo = true;
  }
  const h = await p.evaluate(() => window.innerHeight);
  const total = await p.evaluate(() => document.documentElement.scrollHeight);
  const y0 = manterRolagem ? await p.evaluate(() => window.scrollY) : 0;
  if (!caixas.length || faltaAlvo) return { achou: 0, pagina_telas: +(total / h).toFixed(2) };
  const topo = Math.min(...caixas.map(c => c.top)) - y0, fim = Math.max(...caixas.map(c => c.bottom)) - y0;
  return { achou: caixas.length, topo_telas: +(topo / h).toFixed(2), fim_telas: +(fim / h).toFixed(2),
    sem_rolar: topo >= 0 && topo < h - 40, pagina_telas: +(total / h).toFixed(2), ...(manterRolagem ? { ancora_rolou_telas: +(y0 / h).toFixed(2) } : {}) };
}

main().catch(e => { console.error(e); process.exit(1); });
