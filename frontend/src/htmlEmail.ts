// HTML do corpo do e-mail (issue #191). A lista fechada e' a mesma do servidor (backend/app/html_email.py), que e'
// quem garante o que sai; aqui ela so' faz o que se cola no editor mostrar o que vai sair.

const esc = (s: string) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

/** Texto pre-montado -> o HTML que o editor mostra: uma linha por <div>, como o navegador faz ao digitar. */
export function textoParaHtml(texto: string): string {
  return texto.split("\n").map(l => (l ? `<div>${esc(l)}</div>` : "<div><br></div>")).join("");
}

const TAGS: Record<string, string> = {
  b: "b", strong: "strong", i: "i", em: "em", u: "u", s: "s", strike: "s", del: "s", p: "p", ul: "ul", ol: "ol",
  li: "li", br: "br", div: "div", span: "span", font: "span",
};
const SEM_CONTEUDO = new Set(["script", "style", "head", "title", "iframe", "object", "embed", "noscript", "template",
  "svg", "math", "xml", "textarea", "select", "button", "meta", "link", "img"]);
const COR = /^(#[0-9a-f]{3}|#[0-9a-f]{6}|rgba?\(\s*\d{1,3}%?\s*(,\s*\d{1,3}%?\s*){2}(,\s*(0|1|0?\.\d+)\s*)?\)|[a-z]{3,20})$/i;

function estilo(el: HTMLElement): string {
  const partes: string[] = [];
  const cor = (el.tagName === "FONT" && el.getAttribute("color")) || el.style.color;
  const fundo = el.style.backgroundColor;
  if (cor && COR.test(cor.trim())) partes.push(`color: ${cor.trim()}`);
  if (fundo && COR.test(fundo.trim())) partes.push(`background-color: ${fundo.trim()}`);
  return partes.join("; ");
}

function copiar(de: Node, para: Node, doc: Document) {
  de.childNodes.forEach(no => {
    if (no.nodeType === Node.TEXT_NODE) { para.appendChild(doc.createTextNode(no.textContent ?? "")); return; }
    if (no.nodeType !== Node.ELEMENT_NODE) return;          // comentario (o Word manda varios), instrucao
    const el = no as HTMLElement;
    const tag = el.localName.toLowerCase();
    if (SEM_CONTEUDO.has(tag)) return;
    let destino = TAGS[tag];
    let st = "";
    if (destino === "span") { st = estilo(el); if (!st) destino = ""; }
    if (!destino) { copiar(el, para, doc); return; }        // fora da lista: some a tag, fica o texto
    const novo = doc.createElement(destino);
    if (st) novo.setAttribute("style", st);
    para.appendChild(novo);
    copiar(el, novo, doc);
  });
}

/** HTML colado (Word, Outlook, pagina) -> so' a formatacao da lista fechada. */
export function limparHtml(html: string): string {
  const origem = new DOMParser().parseFromString(html, "text/html");
  const saida = document.createElement("div");
  copiar(origem.body, saida, document);
  return saida.innerHTML;
}
