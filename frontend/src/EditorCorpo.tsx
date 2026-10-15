import { useEffect, useMemo, useRef, useState } from "react";
import { limparHtml, textoParaHtml } from "./htmlEmail";

// Corpo do e-mail com formatacao como no Outlook (issue #191): ao selecionar um trecho aparece a barra perto da
// selecao, e a mesma barra fica fixa acima do corpo. So' o que o servidor deixa passar (backend/app/html_email.py):
// negrito, italico, sublinhado, tachado, cor da fonte, realce e listas. Fonte, tamanho, link e imagem ficam fora.
// O corpo pre-montado chega em texto; enquanto ninguem mexe, sai em texto (igual a antes). Mexeu, sai o HTML.

// paleta curta, como a primeira linha do Outlook
const CORES_FONTE = [
  { nome: "Preto", cor: "#000000" }, { nome: "Vermelho", cor: "#FF0000" }, { nome: "Azul", cor: "#0070C0" },
  { nome: "Verde", cor: "#00B050" }, { nome: "Laranja", cor: "#FFC000" },
];
const CORES_REALCE = [
  { nome: "Amarelo", cor: "#FFFF00" }, { nome: "Verde", cor: "#00FF00" }, { nome: "Azul-claro", cor: "#00FFFF" },
  { nome: "Rosa", cor: "#FF00FF" }, { nome: "Sem realce", cor: "transparent" },
];

// --- barra de formatacao ------------------------------------------------------------------------------------
type Comando = (cmd: string, valor?: string) => void;
const tecla = typeof navigator !== "undefined" && /Mac/.test(navigator.platform) ? "Cmd" : "Ctrl";

function Paleta({ rotulo, cores, cmd, comando, icone }: {
  rotulo: string; cores: { nome: string; cor: string }[]; cmd: string; comando: Comando; icone: React.ReactNode;
}) {
  const [aberta, setAberta] = useState(false);
  return (
    <span className="ol-paleta">
      <button type="button" className="ol-formato" aria-label={rotulo} title={rotulo} aria-haspopup="true"
        aria-expanded={aberta} onMouseDown={e => e.preventDefault()} onClick={() => setAberta(a => !a)}>{icone}</button>
      {aberta && (
        <span className="ol-paleta__cores" role="group" aria-label={rotulo}
          onKeyDown={e => { if (e.key === "Escape") { e.stopPropagation(); setAberta(false); } }}>
          {cores.map(c => (
            <button type="button" key={c.nome} className="ol-cor" aria-label={c.nome} title={c.nome}
              style={{ background: c.cor === "transparent" ? undefined : c.cor }}
              onMouseDown={e => e.preventDefault()} onClick={() => { comando(cmd, c.cor); setAberta(false); }}>
              {c.cor === "transparent" && <span aria-hidden="true">✕</span>}
            </button>
          ))}
        </span>
      )}
    </span>
  );
}

function Botao({ rotulo, atalho, cmd, comando, children }: {
  rotulo: string; atalho?: string; cmd: string; comando: Comando; children: React.ReactNode;
}) {
  const titulo = atalho ? `${rotulo} (${tecla}+${atalho})` : rotulo;
  return (
    <button type="button" className="ol-formato" aria-label={rotulo} title={titulo}
      onMouseDown={e => e.preventDefault()} onClick={() => comando(cmd)}>{children}</button>
  );
}

function Barra({ rotulo, comando, className, style }: {
  rotulo: string; comando: Comando; className: string; style?: React.CSSProperties;
}) {
  return (
    <div role="toolbar" aria-label={rotulo} className={className} style={style}>
      <Botao rotulo="Negrito" atalho="B" cmd="bold" comando={comando}><b>N</b></Botao>
      <Botao rotulo="Itálico" atalho="I" cmd="italic" comando={comando}><i>I</i></Botao>
      <Botao rotulo="Sublinhado" atalho="U" cmd="underline" comando={comando}><u>S</u></Botao>
      <Botao rotulo="Tachado" cmd="strikeThrough" comando={comando}><s>ab</s></Botao>
      <Paleta rotulo="Cor da fonte" cores={CORES_FONTE} cmd="foreColor" comando={comando}
        icone={<span className="ol-formato__cor">A<span style={{ background: "#FF0000" }} /></span>} />
      <Paleta rotulo="Realce" cores={CORES_REALCE} cmd="hiliteColor" comando={comando}
        icone={<span className="ol-formato__realce">ab</span>} />
      <Botao rotulo="Lista com marcadores" cmd="insertUnorderedList" comando={comando}>
        <svg viewBox="0 0 16 16" width="16" height="16" aria-hidden="true"><circle cx="3" cy="4" r="1.2" fill="currentColor" />
          <circle cx="3" cy="8" r="1.2" fill="currentColor" /><circle cx="3" cy="12" r="1.2" fill="currentColor" />
          <path d="M6 4h8M6 8h8M6 12h8" stroke="currentColor" strokeWidth="1.2" /></svg>
      </Botao>
      <Botao rotulo="Lista numerada" cmd="insertOrderedList" comando={comando}>
        <svg viewBox="0 0 16 16" width="16" height="16" aria-hidden="true"><text x="1" y="6" fontSize="5" fill="currentColor">1</text>
          <text x="1" y="13" fontSize="5" fill="currentColor">2</text>
          <path d="M6 4h8M6 11h8" stroke="currentColor" strokeWidth="1.2" /></svg>
      </Botao>
      <Botao rotulo="Limpar formatação" cmd="removeFormat" comando={comando}>
        <svg viewBox="0 0 16 16" width="16" height="16" aria-hidden="true"><path d="M3 3h9M7.5 3l-2 10" stroke="currentColor"
          strokeWidth="1.3" fill="none" /><path d="M10 10l4 4M14 10l-4 4" stroke="currentColor" strokeWidth="1.2" /></svg>
      </Botao>
    </div>
  );
}

const LARGURA_BARRA = 320;
// as tags que o servidor reconhece como corpo vindo do editor (backend/app/html_email.py, `_TAG`)
const TAG_DO_EDITOR = /<\/?(div|p|br|b|strong|i|em|u|s|strike|span|font|ul|ol|li)(\s[^<>]*)?\/?>/i;

export default function EditorCorpo({ inicial, aoMudar }: { inicial: string; aoMudar: (html: string) => void }) {
  const editor = useRef<HTMLDivElement>(null);
  const caixa = useRef<HTMLDivElement>(null);
  const salva = useRef<Range | null>(null);
  const [flutuante, setFlutuante] = useState<{ x: number; y: number } | null>(null);
  const html = useMemo(() => ({ __html: textoParaHtml(inicial) }), [inicial]);

  function dentro(no: Node | null): boolean {
    return !!no && !!editor.current?.contains(no);
  }

  // O servidor so' trata como HTML o corpo com alguma tag do editor; texto apagado e redigitado sem nenhuma linha
  // nova fica sem tag (e com &amp;): embrulhado num <div>, nao e' escapado de novo como texto puro.
  function avisar() {
    if (!editor.current) return;
    const h = editor.current.innerHTML;
    aoMudar(TAG_DO_EDITOR.test(h) ? h : `<div>${h}</div>`);
  }

  function atualizar() {
    const s = document.getSelection();
    if (!s || s.rangeCount === 0) return;
    const r = s.getRangeAt(0);
    if (!dentro(r.commonAncestorContainer)) {
      // a pessoa foi para outro campo: a selecao antiga do corpo nao volta no proximo clique da barra
      if (!caixa.current?.contains(document.activeElement)) { setFlutuante(null); salva.current = null; }
      return;
    }
    salva.current = r.cloneRange();
    if (s.isCollapsed) { setFlutuante(null); return; }
    const sel = typeof r.getBoundingClientRect === "function" ? r.getBoundingClientRect() : null;
    const base = caixa.current?.getBoundingClientRect();
    // a barra (~320px) nao passa da borda direita do corpo: sem rolagem lateral a 1024px nem no celular
    const x = sel && base ? Math.max(0, Math.min(sel.left - base.left, base.width - LARGURA_BARRA)) : 0;
    setFlutuante({ x, y: sel && base ? sel.top - base.top : 0 });
  }
  const ouvinte = useRef(atualizar);
  useEffect(() => { ouvinte.current = atualizar; });
  useEffect(() => {
    const f = () => ouvinte.current();
    document.addEventListener("selectionchange", f);
    return () => document.removeEventListener("selectionchange", f);
  }, []);

  const comando: Comando = (cmd, valor) => {
    if (typeof document.execCommand !== "function") return;
    const s = document.getSelection();
    if (salva.current && s) { s.removeAllRanges(); s.addRange(salva.current); }
    else editor.current?.focus();
    // cor e realce em <span style>, o resto em tag (<b>, <i>...): e' o que a lista fechada do servidor aceita
    document.execCommand("styleWithCSS", false, cmd === "foreColor" || cmd === "hiliteColor" ? "true" : "false");
    document.execCommand(cmd, false, valor);
    avisar();
  };

  function teclas(e: React.KeyboardEvent<HTMLDivElement>) {
    if (e.key === "Escape") { setFlutuante(null); return; }
    if (!(e.ctrlKey || e.metaKey) || e.altKey || e.shiftKey) return;
    const cmd = ({ b: "bold", i: "italic", u: "underline" } as Record<string, string>)[e.key.toLowerCase()];
    if (!cmd) return;
    e.preventDefault();
    comando(cmd);
  }

  // colar e soltar o que veio de fora passam pela mesma limpeza: o editor mostra o que vai sair
  function inserir(dados: Pick<DataTransfer, "getData">) {
    const h = dados.getData("text/html");
    if (h) document.execCommand("insertHTML", false, limparHtml(h));
    else document.execCommand("insertText", false, dados.getData("text/plain"));
    avisar();
  }

  function colar(e: React.ClipboardEvent<HTMLDivElement>) {
    if (!e.clipboardData || typeof document.execCommand !== "function") return;
    e.preventDefault();
    inserir(e.clipboardData);
  }

  // revisor na PR #195: arrastar de outra janela e soltar no corpo nao pode trazer link, imagem ou fonte que o
  // servidor tira depois. Arrastar um trecho de dentro do proprio corpo (mover) fica com o navegador.
  const deDentro = useRef(false);
  function soltar(e: React.DragEvent<HTMLDivElement>) {
    // a marca se le' e se zera aqui (o drop vem antes do dragend): movendo uma linha inteira, o navegador apaga o
    // no' de origem e o dragend nao chega, e a marca ligada deixaria todo soltar de fora entrar sem limpeza
    const interno = deDentro.current;
    deDentro.current = false;
    if (interno || !e.dataTransfer || typeof document.execCommand !== "function") return;
    e.preventDefault();
    const d = document as Document & { caretPositionFromPoint?: (x: number, y: number) => { offsetNode: Node; offset: number } | null };
    let ponto: Range | null = null;
    if (typeof document.caretRangeFromPoint === "function") ponto = document.caretRangeFromPoint(e.clientX, e.clientY);
    else if (typeof d.caretPositionFromPoint === "function") {
      const p = d.caretPositionFromPoint(e.clientX, e.clientY);
      if (p) { ponto = document.createRange(); ponto.setStart(p.offsetNode, p.offset); }
    }
    const s = document.getSelection();
    if (ponto && s && dentro(ponto.startContainer)) { s.removeAllRanges(); s.addRange(ponto); }
    else editor.current?.focus();
    inserir(e.dataTransfer);
  }

  return (
    <div className="ol-editor-caixa" ref={caixa}>
      <Barra rotulo="Formatação" comando={comando} className="ol-barra" />
      {flutuante && (
        <Barra rotulo="Formatação da seleção" comando={comando} className="ol-barra ol-barra--flutuante"
          style={{ left: flutuante.x, top: flutuante.y }} />
      )}
      <div ref={editor} className="ol-editor" contentEditable suppressContentEditableWarning role="textbox"
        aria-multiline="true" aria-label="Corpo da mensagem" dangerouslySetInnerHTML={html} spellCheck
        onInput={avisar} onKeyDown={teclas} onPaste={colar} onDrop={soltar}
        onDragStart={() => { deDentro.current = true; }} onDragEnd={() => { deDentro.current = false; }}
        onMouseUp={atualizar} onKeyUp={atualizar} />
    </div>
  );
}
