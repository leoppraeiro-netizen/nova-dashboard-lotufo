// Biblioteca comum dos scripts da verificacao B (fase 3, 10/10/2026).
// Roda com `node` de qualquer pasta: o Playwright e' resolvido a partir de frontend/node_modules.
import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

export const AQUI = path.dirname(fileURLToPath(import.meta.url));
export const RAIZ = path.resolve(AQUI, "../../../..");
const FRONT = path.join(RAIZ, "frontend");
const require = createRequire(path.join(FRONT, "package.json"));
export const { chromium } = require("playwright");

export const SITE = "http://localhost:5173";
export const SIMULADOR = path.join(RAIZ, "backend/dados/correio-simulado/enviados");

export function usuarios() {
  const linhas = fs.readFileSync(path.join(RAIZ, "backend/dados/usuarios-teste.txt"), "utf8")
    .split(/\r?\n/).filter(l => l && !l.startsWith("#"));
  return Object.fromEntries(linhas.map(l => { const [email, senha, perfil] = l.split(/\t+/); return [perfil, { email, senha }]; }));
}

export function arquivosSimulador() {
  if (!fs.existsSync(SIMULADOR)) return [];
  return fs.readdirSync(SIMULADOR).filter(f => f.endsWith(".json")).sort();
}

export async function abrir({ viewport = { width: 1366, height: 900 }, mobile = false } = {}) {
  const browser = await chromium.launch({ headless: true });
  const ctx = await browser.newContext({ viewport, locale: "pt-BR", timezoneId: "America/Cuiaba",
    ...(mobile ? { isMobile: true, hasTouch: true, deviceScaleFactor: 2 } : {}) });
  const page = await ctx.newPage();
  const rede = [];
  page.on("request", r => { if (r.url().includes("/api/")) rede.push({ t: Date.now(), tipo: "req", metodo: r.method(), url: r.url().replace(SITE, ""), corpo: r.method() !== "GET" ? (r.postData() ?? "").slice(0, 400) : undefined }); });
  page.on("response", async r => { if (r.url().includes("/api/")) { let corpo = ""; try { if (r.request().method() !== "GET") corpo = (await r.text()).slice(0, 400); } catch {} rede.push({ t: Date.now(), tipo: "res", status: r.status(), metodo: r.request().method(), url: r.url().replace(SITE, ""), corpo: corpo || undefined }); } });
  page.on("dialog", d => { rede.push({ tipo: "dialog", msg: d.message() }); d.dismiss().catch(() => {}); });
  const consola = [];
  page.on("console", m => { if (["error", "warning"].includes(m.type())) consola.push(`${m.type()}: ${m.text().slice(0, 300)}`); });
  page.on("pageerror", e => consola.push(`pageerror: ${String(e).slice(0, 300)}`));
  return { browser, ctx, page, rede, consola };
}

export async function login(page, perfil) {
  const u = usuarios()[perfil];
  await page.goto(SITE + "/inicio", { waitUntil: "domcontentloaded" });
  await page.fill('input[name="email"]', u.email);
  await page.fill('input[name="senha"]', u.senha);
  await Promise.all([
    page.waitForResponse(r => r.url().includes("/api/auth/eu") && r.status() === 200, { timeout: 20000 }),
    page.click('button.entrar__botao'),
  ]);
  await page.waitForSelector("nav.trilho", { timeout: 20000 });
}

export async function ir(page, caminho, espera = "networkidle") {
  await page.goto(SITE + caminho, { waitUntil: "domcontentloaded" });
  try { await page.waitForLoadState(espera, { timeout: 15000 }); } catch {}
}

export async function captura(page, nome, fullPage = true) {
  const arq = path.join(AQUI, `${nome}.png`);
  await page.screenshot({ path: arq, fullPage });
  return path.basename(arq);
}

export function gravarTexto(nome, conteudo) {
  const arq = path.join(AQUI, nome);
  fs.writeFileSync(arq, typeof conteudo === "string" ? conteudo : JSON.stringify(conteudo, null, 1), "utf8");
  return path.basename(arq);
}

export async function textoPagina(page, seletor = "body") {
  return (await page.locator(seletor).first().innerText()).replace(/\n{3,}/g, "\n\n");
}

export const esperar = ms => new Promise(r => setTimeout(r, ms));

// POSTs/PUTs de escrita observados na rede (fora o login)
export function escritas(rede) {
  return rede.filter(e => e.tipo === "req" && e.metodo !== "GET" && !e.url.includes("/api/auth/"));
}
