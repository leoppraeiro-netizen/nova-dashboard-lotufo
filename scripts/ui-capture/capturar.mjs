// Captura do loop de refino visual (/ui-loop).
//
// Uso, na raiz do repo:   node scripts/ui-capture/capturar.mjs 00
//                         node scripts/ui-capture/capturar.mjs 01 --so inicio,obra --viewports 1440x900
//                         node scripts/ui-capture/capturar.mjs --saida .ui-review/arquitetura/capturas/base --sem-recortes
// Em frontend/:           npm run ui:capture -- 00
// Opcoes: --so <ids>  (so' essas telas)  --viewports <nomes>  --sem-build (reusa .ui-review/.build)
//         --sobrescrever (refaz uma rodada que ja' tem arquivos)
//         --saida <pasta> (grava ali em vez de round-NN; precisa ficar dentro de .ui-review/)
//         --sem-recortes (so' as janelas por secao, sem os recortes 2x)
// Navegador: o Chrome instalado (canal "chrome"); UI_CAPTURE_CANAL=msedge troca pelo Edge.
//
// O que faz: builda o frontend em .ui-review/.build (frontend/dist nao e' tocado), serve o build numa
// porta local e abre cada tela de .ui-review/routes.json em cada viewport, com TODA chamada /api
// respondida pelas fixtures de .ui-review/fixtures: nenhum backend e nenhum banco entram na captura.
// Relogio congelado, movimento reduzido, animacoes desligadas, fontes e rede assentadas antes do clique.
// Grava em .ui-review/round-NN/: a janela por secao (<tela>--<viewport>[--sN].png), os recortes 2x dos
// componentes-chave (<tela>--<viewport>--<recorte>@2x.png) e o report.json (axe-core, rolagem
// horizontal, texto cortado sem reticencias, console, fixture ausente e as medidas da arquitetura de
// informacao: altura da pagina em telas, itens de lista renderizados e onde comeca cada bloco).
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

const args = process.argv.slice(2);
const opcao = nome => { const i = args.indexOf(nome); return i >= 0 ? args[i + 1] : undefined; };
const rodada = args.find(a => /^\d{1,2}$/.test(a));
const saidaOpcao = opcao("--saida");
if (!rodada && !saidaOpcao) {
  console.error("uso: node scripts/ui-capture/capturar.mjs NN|--saida <pasta> [--so id1,id2] [--viewports 1440x900] [--sem-build] [--sobrescrever] [--sem-recortes]");
  process.exit(2);
}
const NN = rodada ? rodada.padStart(2, "0") : null;
const SAIDA = saidaOpcao ? path.resolve(RAIZ, saidaOpcao) : path.join(UI, `round-${NN}`);
// --sobrescrever apaga a pasta de saida inteira: fora de .ui-review/ isso poderia levar outra coisa junto.
if (!SAIDA.startsWith(UI + path.sep)) {
  console.error(`--saida precisa ficar dentro de .ui-review/ (veio ${saidaOpcao})`);
  process.exit(2);
}
const semRecortes = args.includes("--sem-recortes");
const so = opcao("--so")?.split(",").filter(Boolean);
const soViewports = opcao("--viewports")?.split(",").filter(Boolean);
const CANAL = process.env.UI_CAPTURE_CANAL || "chrome";

// As dependencias moram em frontend/node_modules; este arquivo mora fora de frontend/, onde a
// resolucao do Node nao as acharia. Importa pela entrada ESM declarada no package.json de cada uma.
async function modulo(nome) {
  const dir = path.join(FRONT, "node_modules", ...nome.split("/"));
  const pkg = JSON.parse(await fs.readFile(path.join(dir, "package.json"), "utf8"));
  const exp = pkg.exports?.["."] ?? pkg.exports;
  const entrada = typeof exp === "string" ? exp : exp?.import ?? exp?.default ?? pkg.module ?? pkg.main;
  return import(pathToFileURL(path.join(dir, entrada)).href);
}

const TIPOS = { ".json": "application/json; charset=utf-8", ".svg": "image/svg+xml", ".png": "image/png" };

// Arquivo que espelha o caminho da API: GET /api/contratos/7/cabecalho -> api/contratos/7/cabecalho.json.
// Consulta vira sufixo (checklist-protocolo.natureza=reajuste.json) e cai no arquivo sem sufixo quando
// nao ha variante; metodo diferente de GET vira sufixo (previa.POST.json). O "v" de cache nao conta.
function arquivoFixture(metodo, caminho, busca) {
  const base = path.join(FIXTURES, ...caminho.replace(/^\/+/, "").split("/"));
  const consulta = [...new URLSearchParams(busca)].filter(([k]) => k !== "v")
    .sort(([a], [b]) => a.localeCompare(b)).map(([k, v]) => `${k}=${v}`).join("&");
  const nomes = metodo === "GET"
    ? [...(consulta ? [`${base}.${consulta}.json`] : []), `${base}.json`, `${base}.svg`, `${base}.png`]
    : [...(consulta ? [`${base}.${consulta}.${metodo}.json`] : []), `${base}.${metodo}.json`];
  return nomes.find(n => { try { return existsSync(n); } catch { return false; } }) ?? null;
}

async function main() {
  const rotas = JSON.parse(await fs.readFile(path.join(UI, "routes.json"), "utf8"));
  const telas = rotas.telas.filter(t => !so || so.includes(t.id));
  const viewports = rotas.viewports.filter(v => !soViewports || soViewports.includes(v.nome));
  if (so && telas.length !== so.length) throw new Error(`tela desconhecida em --so: ${so.join(", ")}`);

  if (existsSync(SAIDA) && (await fs.readdir(SAIDA)).length > 0) {
    if (!args.includes("--sobrescrever")) {
      throw new Error(`${path.relative(RAIZ, SAIDA)} ja' tem arquivos: use outra rodada ou --sobrescrever`);
    }
    if (!so && !soViewports) await fs.rm(SAIDA, { recursive: true, force: true });
  }
  await fs.mkdir(SAIDA, { recursive: true });

  const { build, preview } = await modulo("vite");
  const { chromium } = await modulo("playwright");
  const AxeBuilder = (await modulo("@axe-core/playwright")).default;

  if (!args.includes("--sem-build") || !existsSync(path.join(BUILD, "index.html"))) {
    console.log("build do frontend em .ui-review/.build ...");
    await build({ root: FRONT, configFile: CONFIG_VITE, logLevel: "warn", build: { outDir: BUILD, emptyOutDir: true } });
  }
  // proxy vazio: nada pode escapar para um backend de verdade (a interceptacao e' do navegador).
  const servidor = await preview({ root: FRONT, configFile: CONFIG_VITE, logLevel: "warn", build: { outDir: BUILD },
    preview: { host: "127.0.0.1", port: 4179, strictPort: false, open: false, proxy: {} } });
  const BASE = `http://127.0.0.1:${servidor.httpServer.address().port}`;
  const navegador = await chromium.launch({ channel: CANAL });
  const relogio = new Date(rotas.relogio);

  // A versao do navegador muda o desenho do texto: comparar rodadas de versoes diferentes e' comparar o Chrome,
  // nao a interface. Se mudou desde a rodada anterior, a anterior precisa ser recapturada antes da comparacao.
  const relatorio = { rodada: NN ?? path.relative(UI, SAIDA).replaceAll(path.sep, "/"), gerado_em: new Date().toISOString(),
    relogio_congelado: rotas.relogio, fuso: rotas.fuso, navegador: CANAL, chrome_versao: navegador.version(), telas: {} };
  const anterior = NN ? path.join(UI, `round-${String(Number(NN) - 1).padStart(2, "0")}`, "report.json") : null;
  if (anterior && Number(NN) > 0 && existsSync(anterior)) {
    const versaoAnterior = JSON.parse(await fs.readFile(anterior, "utf8")).chrome_versao;
    if (versaoAnterior !== relatorio.chrome_versao) {
      relatorio.alerta_versao = `Chrome ${relatorio.chrome_versao} nesta rodada e ${versaoAnterior ?? "desconhecido"} na anterior: recapture a anterior antes de comparar`;
      console.log(`ATENCAO: ${relatorio.alerta_versao}`);
    }
  }
  const t0 = Date.now();

  async function abrir(tela, vp, escala, registro) {
    const contexto = await navegador.newContext({
      viewport: { width: vp.width, height: vp.height }, deviceScaleFactor: escala, locale: "pt-BR",
      timezoneId: rotas.fuso, reducedMotion: "reduce", colorScheme: "light", serviceWorkers: "block",
    });
    const intencionais = new Set();
    await contexto.route(url => url.pathname.startsWith("/api/"), async rota => {
      const req = rota.request();
      const u = new URL(req.url());
      const chave = `${req.method()} ${u.pathname}`;
      const troca = tela.fixtures?.[chave + u.search] ?? tela.fixtures?.[chave];
      if (troca && typeof troca === "object") {
        if ((troca.status ?? 200) >= 400) intencionais.add(u.pathname);
        return rota.fulfill({ status: troca.status ?? 200, contentType: TIPOS[".json"], body: JSON.stringify(troca.json ?? {}) });
      }
      const arq = typeof troca === "string" ? path.join(FIXTURES, troca) : arquivoFixture(req.method(), u.pathname, u.search);
      if (!arq) {
        registro?.fixtures_ausentes.push(`${chave}${u.search}`);
        intencionais.add(u.pathname);
        return rota.fulfill({ status: 404, contentType: TIPOS[".json"], body: JSON.stringify({ detail: `Sem fixture para ${chave}` }) });
      }
      return rota.fulfill({ status: 200, contentType: TIPOS[path.extname(arq)] ?? "application/octet-stream", body: await fs.readFile(arq) });
    });
    const pagina = await contexto.newPage();
    pagina.setDefaultTimeout(15000);
    if (registro) {
      pagina.on("console", msg => {
        if (msg.type() !== "error" && msg.type() !== "warning") return;
        const origem = msg.location()?.url ?? "";
        const esperado = [...intencionais].some(p => origem.includes(p));
        registro.console.push({ tipo: msg.type(), texto: msg.text().slice(0, 300), ...(esperado ? { esperado: true } : {}) });
      });
      pagina.on("pageerror", e => registro.console.push({ tipo: "pageerror", texto: String(e).slice(0, 300) }));
      pagina.on("requestfailed", r => registro.console.push({ tipo: "requestfailed", texto: `${r.method()} ${r.url()} ${r.failure()?.errorText ?? ""}` }));
    }
    await pagina.clock.setFixedTime(relogio);
    await pagina.goto(BASE + tela.rota, { waitUntil: "networkidle" });
    if (!(await assentar(pagina))) registro?.avisos.push("ainda mostrava 'Carregando' depois de 8 s (antes das acoes)");
    for (const a of tela.acoes ?? []) {
      const alvo = pagina.locator(a.seletor).first();
      if (a.acao === "clicar") await alvo.click();
      else if (a.acao === "marcar") await alvo.check();
      else if (a.acao === "selecionar") await alvo.selectOption(a.valor);
      else if (a.acao === "preencher") await alvo.fill(a.valor);
      else if (a.acao === "esperar") await alvo.waitFor({ state: "visible" });
      else throw new Error(`acao desconhecida em ${tela.id}: ${a.acao}`);
      await pagina.waitForLoadState("networkidle").catch(() => {});
    }
    // o ponteiro que clicou fica parado em cima do botao e deixa hover na captura: leva para o canto da logo
    if (tela.acoes?.length) await pagina.mouse.move(1, 1);
    if (!(await assentar(pagina))) registro?.avisos.push("ainda mostrava 'Carregando' depois de 8 s");
    return { contexto, pagina };
  }

  for (const tela of telas) {
    relatorio.telas[tela.id] = { rota: tela.rota, descricao: tela.descricao ?? "", viewports: {} };
    for (const vp of viewports) {
      const nome = `${tela.id}--${vp.nome}`;
      const reg = { arquivos: [], recortes: [], axe: [], layout: null, medidas: null, sanidade: null, console: [], fixtures_ausentes: [], avisos: [] };
      relatorio.telas[tela.id].viewports[vp.nome] = reg;
      process.stdout.write(`${nome} `);
      try {
        const { contexto, pagina } = await abrir(tela, vp, 1, reg);
        await pagina.evaluate(() => window.scrollTo({ top: 0, behavior: "instant" }));
        const axe = await new AxeBuilder({ page: pagina }).analyze();
        reg.axe = axe.violations.map(v => ({ regra: v.id, impacto: v.impact, ajuda: v.help, nos: v.nodes.length,
          alvos: v.nodes.slice(0, 6).map(n => ({ alvo: n.target.join(" "),
            detalhe: (n.failureSummary ?? "").split("\n").slice(1, 3).join(" ").trim().slice(0, 220) })) }));
        reg.layout = await pagina.evaluate(verificarLayout);
        reg.medidas = await pagina.evaluate(medirPagina);
        // fidelidade da captura: fonte da marca carregada e nenhuma imagem quebrada
        reg.sanidade = await pagina.evaluate(() => ({
          titulo: document.title,
          fontes: [...new Set([...document.fonts].filter(f => f.status === "loaded").map(f => f.family.replaceAll('"', "")))],
          imagens_quebradas: [...document.images].filter(i => i.complete && i.naturalWidth === 0).map(i => i.getAttribute("src")),
        }));
        const ys = await posicoes(pagina, tela.foco);
        for (const [i, y] of ys.entries()) {
          await pagina.evaluate(top => window.scrollTo({ top, behavior: "instant" }), y);
          await quadros(pagina);
          const arquivo = ys.length === 1 ? `${nome}.png` : `${nome}--s${i + 1}.png`;
          await pagina.screenshot({ path: path.join(SAIDA, arquivo), animations: "disabled", caret: "hide" });
          reg.arquivos.push(arquivo);
        }
        await contexto.close();

        if (tela.recortes?.length && !semRecortes) {
          const { contexto: c2, pagina: p2 } = await abrir(tela, vp, 2, null);
          await p2.evaluate(() => window.scrollTo({ top: 0, behavior: "instant" }));
          await quadros(p2);
          for (const r of tela.recortes) {
            const alvo = p2.locator(r.seletor).first();
            if (!(await alvo.count())) { reg.avisos.push(`recorte ${r.nome}: seletor sem resultado`); continue; }
            const caixa = await alvo.evaluate(el => {
              const b = el.getBoundingClientRect();
              return { x: b.left + window.scrollX, y: b.top + window.scrollY, width: b.width, height: b.height };
            });
            if (caixa.width < 1 || caixa.height < 1) { reg.avisos.push(`recorte ${r.nome}: elemento sem tamanho`); continue; }
            // pagina inteira + recorte: a faixa fixa do topo fica no topo do documento e nao cobre o componente
            const arquivo = `${nome}--${r.nome}@2x.png`;
            // componente dentro de uma caixa que rola por dentro (Rolagem alta) pode ficar fora da pagina inteira:
            // registra e segue, sem derrubar as capturas da tela
            try {
              await p2.screenshot({ path: path.join(SAIDA, arquivo), fullPage: true, animations: "disabled", caret: "hide",
                clip: { ...caixa, height: Math.min(caixa.height, r.alturaMax ?? caixa.height) } });
              reg.recortes.push(arquivo);
            } catch (e) { reg.avisos.push(`recorte ${r.nome}: ${String(e.message ?? e).split("\n")[0]}`); }
          }
          await c2.close();
        }
        console.log(`ok (${reg.arquivos.length} + ${reg.recortes.length})`);
      } catch (e) {
        reg.avisos.push(`falhou: ${String(e.message ?? e).split("\n")[0]}`);
        console.log(`FALHOU: ${String(e.message ?? e).split("\n")[0]}`);
      }
    }
  }

  // Recaptura parcial (--so / --viewports) numa pasta que ja' tem report: mescla as telas e viewports novos no
  // report existente, em vez de apagar o das outras telas da rodada.
  const arqRelatorio = path.join(SAIDA, "report.json");
  if ((so || soViewports) && existsSync(arqRelatorio)) {
    const velho = JSON.parse(await fs.readFile(arqRelatorio, "utf8"));
    for (const [id, t] of Object.entries(relatorio.telas)) {
      velho.telas[id] = velho.telas[id] ? { ...velho.telas[id], viewports: { ...velho.telas[id].viewports, ...t.viewports } } : t;
    }
    relatorio.telas = velho.telas;
  }
  relatorio.resumo = resumir(relatorio);
  relatorio.duracao_s = Math.round((Date.now() - t0) / 1000);
  await fs.writeFile(path.join(SAIDA, "report.json"), JSON.stringify(relatorio, null, 2) + "\n", "utf8");
  await navegador.close();
  await servidor.close();

  const r = relatorio.resumo;
  console.log(`\n${path.relative(RAIZ, SAIDA)}: ${r.capturas} capturas, ${r.recortes} recortes em ${relatorio.duracao_s} s (Chrome ${relatorio.chrome_versao})`);
  if (relatorio.alerta_versao) console.log(`ATENCAO: ${relatorio.alerta_versao}`);
  console.log(`axe: ${Object.entries(r.axe).map(([k, v]) => `${k} (${v.impacto}, ${v.nos} nos)`).join("; ") || "nenhuma violacao"}`);
  console.log(`rolagem horizontal: ${r.rolagem_horizontal.join(", ") || "nenhuma"}`);
  console.log(`tabela ou grafico rolando por dentro: ${r.rolagem_interna.join(", ") || "nenhum"}`);
  console.log(`texto cortado sem reticencias: ${r.cortados_sem_reticencias} · console: ${r.console} · fixtures ausentes: ${r.fixtures_ausentes.join(", ") || "nenhuma"}`);
  if (r.sem_fonte_da_marca.length) console.log(`SEM A FONTE DA MARCA: ${r.sem_fonte_da_marca.join(", ")}`);
  if (r.imagens_quebradas.length) console.log(`IMAGENS QUEBRADAS: ${r.imagens_quebradas.join(" | ")}`);
  if (r.falhas.length) console.log(`FALHAS: ${r.falhas.join(" | ")}`);
  const altas = Object.entries(r.alturas).sort(([, a], [, b]) => b.telas - a.telas).slice(0, 8);
  console.log(`paginas mais altas: ${altas.map(([k, v]) => `${k} ${v.telas} telas/${v.itens} itens`).join("; ")}`);
}

// Espera o que a tela precisa para ficar parada: rede, fontes, fim dos "Carregando", imagens e dois quadros.
async function assentar(pagina) {
  await pagina.waitForLoadState("networkidle").catch(() => {});
  await pagina.evaluate(() => document.fonts.ready.then(() => undefined));
  const pronta = await pagina.waitForFunction(
    () => !/Carregando|carregando…|Conferindo os documentos|Verificando as certidões/.test(document.body?.innerText ?? ""),
    null, { timeout: 8000 }).then(() => true, () => false);
  await pagina.waitForFunction(() => [...document.images].every(i => i.complete), null, { timeout: 5000 }).catch(() => {});
  await quadros(pagina);
  return pronta;
}

function quadros(pagina) {
  return pagina.evaluate(() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(() => r()))));
}

// Onde cada secao comeca. A faixa do topo (.topbar) e' sticky: o passo desconta a altura dela para a
// linha que estava escondida sob a faixa aparecer na secao seguinte. Com `foco`, so' a regiao do componente.
async function posicoes(pagina, foco) {
  const m = await pagina.evaluate(() => {
    const topo = document.querySelector(".topbar");
    const sobra = topo && getComputedStyle(topo).position === "sticky" ? topo.getBoundingClientRect().height : 0;
    return { h: window.innerHeight, total: document.documentElement.scrollHeight, sobra };
  });
  let ini = 0, fim = m.total;
  if (foco) {
    const alvo = pagina.locator(foco).first();
    const b = await alvo.evaluate(el => { const r = el.getBoundingClientRect(); return { top: r.top + window.scrollY, bottom: r.bottom + window.scrollY }; });
    ini = Math.max(0, b.top - m.sobra - 12);
    fim = Math.min(m.total, b.bottom + 12);
  }
  const maxY = Math.max(0, m.total - m.h);
  const passo = Math.max(200, m.h - m.sobra - 16);
  const ys = [Math.min(ini, maxY)];
  while (ys.at(-1) + m.h < fim - 1 && ys.at(-1) < maxY) ys.push(Math.min(ys.at(-1) + passo, maxY));
  return ys;
}

// Roda NA PAGINA. Rolagem horizontal da pagina (com os elementos que a causam) e texto que nao cabe:
// mede cada no de texto (Range) contra a primeira caixa que o recorta. Cortado sem reticencias
// (overflow escondido, sem text-overflow), com reticencias (informativo) ou transbordando (nenhuma
// caixa recorta e o texto passa do bloco dele, invadindo o vizinho). Caixa com rolagem nao corta.
function verificarLayout() {
  const vw = document.documentElement.clientWidth;
  const sw = document.documentElement.scrollWidth;
  const descrever = el => {
    let s = el.tagName.toLowerCase();
    if (el.id) s += `#${el.id}`;
    const classes = [...el.classList].slice(0, 3).join(".");
    if (classes) s += `.${classes}`;
    const texto = (el.innerText || el.textContent || "").trim().replace(/\s+/g, " ").slice(0, 70);
    return texto ? `${s} "${texto}"` : s;
  };
  const visivel = el => {
    const r = el.getBoundingClientRect(), cs = getComputedStyle(el);
    return r.width > 1 && r.height > 1 && cs.visibility !== "hidden" && cs.display !== "none";
  };
  const dentroDeRolagem = el => {
    for (let p = el.parentElement; p && p !== document.body; p = p.parentElement) {
      if (getComputedStyle(p).overflowX !== "visible") return true;
    }
    return false;
  };
  const culpados = [];
  if (sw > vw + 1) {
    for (const el of document.body.querySelectorAll("*")) {
      if (el instanceof SVGElement && !(el instanceof SVGSVGElement)) continue;
      if (!visivel(el) || el.getBoundingClientRect().right <= vw + 1 || dentroDeRolagem(el)) continue;
      if (culpados.some(c => c.contains(el))) continue;
      culpados.push(el);
    }
  }
  const caixaInterna = el => {
    const b = el.getBoundingClientRect();
    const left = b.left + el.clientLeft, top = b.top + el.clientTop;
    return { left, top, right: left + el.clientWidth, bottom: top + el.clientHeight };
  };
  const semReticencias = new Set(), comReticencias = new Set(), transbordando = new Set();
  const andador = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT,
    { acceptNode: n => (n.textContent.trim() ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT) });
  for (let n = andador.nextNode(); n; n = andador.nextNode()) {
    const pai = n.parentElement;
    if (!pai || pai.closest("script, style, noscript, option, select, textarea, title, .sr-only") || !visivel(pai)) continue;
    const intervalo = document.createRange();
    intervalo.selectNodeContents(n);
    const linhas = [...intervalo.getClientRects()].filter(r => r.width > 0 && r.height > 0);
    if (!linhas.length) continue;
    let recortou = false;
    for (let a = pai; a && a !== document.body; a = a.parentElement) {
      const cs = getComputedStyle(a);
      const ox = cs.overflowX, oy = cs.overflowY;
      if (["auto", "scroll"].includes(ox) || ["auto", "scroll"].includes(oy)) { recortou = true; break; }
      const cortaX = ["hidden", "clip"].includes(ox), cortaY = ["hidden", "clip"].includes(oy);
      if (!cortaX && !cortaY) continue;
      recortou = true;
      const c = caixaInterna(a);
      if (c.right - c.left <= 2 || c.bottom - c.top <= 2) break;          // padrao sr-only / recorte zero
      const foraX = cortaX && linhas.some(r => r.right > c.right + 1 || r.left < c.left - 1);
      const foraY = cortaY && linhas.some(r => r.bottom > c.bottom + 2 || r.top < c.top - 2);
      if (foraX || foraY) {
        const reticencias = (foraX && cs.textOverflow === "ellipsis") || (foraY && cs.webkitLineClamp && cs.webkitLineClamp !== "none");
        (reticencias ? comReticencias : semReticencias).add(descrever(a));
      }
      break;
    }
    if (recortou) continue;
    let bloco = pai;
    while (bloco !== document.body && ["inline", "contents"].includes(getComputedStyle(bloco).display)) bloco = bloco.parentElement;
    const c = caixaInterna(bloco);
    if (linhas.some(r => r.right > c.right + 1 || r.left < c.left - 1)) transbordando.add(descrever(bloco));
  }
  // caixa com rolagem horizontal propria (tabela mais larga que o cartao): o que passa da borda so' aparece rolando
  const rolagemInterna = [];
  for (const el of document.body.querySelectorAll("*")) {
    if (!visivel(el) || el === document.documentElement) continue;
    const ox = getComputedStyle(el).overflowX;
    if ((ox === "auto" || ox === "scroll") && el.scrollWidth > el.clientWidth + 1) {
      rolagemInterna.push(`${descrever(el).slice(0, 90)} (${el.scrollWidth - el.clientWidth}px escondidos)`);
    }
  }
  return {
    rolagem_horizontal: sw > vw + 1, scroll_width: sw, client_width: vw, culpados: culpados.slice(0, 12).map(descrever),
    rolagem_interna: rolagemInterna.slice(0, 20),
    cortados_sem_reticencias: [...semReticencias].slice(0, 30), cortados_com_reticencias: [...comReticencias].slice(0, 30),
    transbordando: [...transbordando].slice(0, 30),
  };
}

// Roda NA PAGINA, no topo e depois das acoes da tela. Medidas da arquitetura de informacao: altura da
// pagina em telas (scrollHeight / altura da janela), itens de lista renderizados (linhas de tabela e
// itens de lista dentro de <main>) e, para cada <section> com titulo, onde comeca e quanto ocupa, em telas
// a partir do topo do documento (topo < 1 = comeca sem rolar). Contagens de um bloco incluem os aninhados.
function medirPagina() {
  const h = window.innerHeight;
  const principal = document.querySelector("main") ?? document.body;
  // checkVisibility: o conteúdo de <details> fechado tem caixa no Chrome atual, mas não aparece nem conta
  const visivel = el => { if (el.checkVisibility && !el.checkVisibility()) return false; const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
  const contar = (raiz, sel) => [...raiz.querySelectorAll(sel)].filter(visivel).length;
  const telas = px => Math.round((px / h) * 100) / 100;
  const tituloDe = s => {
    const id = s.getAttribute("aria-labelledby");
    const rotulo = id && document.getElementById(id);
    const cab = rotulo ?? [...s.querySelectorAll("h1, h2, h3")].find(t => t.closest("section") === s);
    return (cab?.textContent ?? s.getAttribute("aria-label") ?? "").trim().replace(/\s+/g, " ").slice(0, 80);
  };
  const blocos = [];
  for (const s of principal.querySelectorAll("section")) {
    if (!visivel(s)) continue;
    const titulo = tituloDe(s);
    if (!titulo) continue;
    const r = s.getBoundingClientRect();
    let nivel = 0;
    for (let p = s.parentElement?.closest("section"); p && principal.contains(p); p = p.parentElement?.closest("section")) nivel++;
    blocos.push({ titulo, nivel, topo_telas: telas(r.top + window.scrollY), altura_telas: telas(r.height),
      linhas_tabela: contar(s, "tbody tr"), itens_lista: contar(s, "li") });
  }
  const cartoes = [...principal.querySelectorAll(".cartao")].filter(visivel).map(c => c.getBoundingClientRect().width);
  const total = document.documentElement.scrollHeight;
  return { altura_px: total, altura_telas: telas(total), janela: { largura: window.innerWidth, altura: h },
    largura_main_px: Math.round(principal.getBoundingClientRect().width),
    largura_cartao_max_px: cartoes.length ? Math.round(Math.max(...cartoes)) : null,
    linhas_tabela: contar(principal, "tbody tr"), itens_lista: contar(principal, "li"),
    blocos: blocos.slice(0, 40) };
}

function resumir(relatorio) {
  const r = { capturas: 0, recortes: 0, axe: {}, rolagem_horizontal: [], rolagem_interna: [], cortados_sem_reticencias: 0, transbordando: 0,
    console: 0, fixtures_ausentes: [], sem_fonte_da_marca: [], imagens_quebradas: [], falhas: [], alturas: {} };
  for (const [id, t] of Object.entries(relatorio.telas)) {
    for (const [vp, v] of Object.entries(t.viewports)) {
      const nome = `${id}--${vp}`;
      r.capturas += v.arquivos.length;
      r.recortes += v.recortes.length;
      for (const x of v.axe) {
        const a = (r.axe[x.regra] ??= { impacto: x.impacto, nos: 0, telas: [] });
        a.nos += x.nos;
        a.telas.push(nome);
      }
      if (v.layout?.rolagem_horizontal) r.rolagem_horizontal.push(nome);
      if (v.layout?.rolagem_interna.length) r.rolagem_interna.push(`${nome} (${v.layout.rolagem_interna.length})`);
      r.cortados_sem_reticencias += v.layout?.cortados_sem_reticencias.length ?? 0;
      r.transbordando += v.layout?.transbordando.length ?? 0;
      r.console += v.console.filter(c => !c.esperado).length;
      for (const f of v.fixtures_ausentes) if (!r.fixtures_ausentes.includes(f)) r.fixtures_ausentes.push(f);
      if (v.sanidade && !v.sanidade.fontes.includes("Hanken Grotesk")) r.sem_fonte_da_marca.push(nome);
      if (v.sanidade?.imagens_quebradas.length) r.imagens_quebradas.push(`${nome}: ${v.sanidade.imagens_quebradas.join(", ")}`);
      for (const a of v.avisos) if (a.startsWith("falhou")) r.falhas.push(`${nome}: ${a}`);
      if (v.medidas) r.alturas[nome] = { telas: v.medidas.altura_telas, itens: v.medidas.linhas_tabela + v.medidas.itens_lista };
    }
  }
  return r;
}

main().catch(e => { console.error(e); process.exit(1); });
