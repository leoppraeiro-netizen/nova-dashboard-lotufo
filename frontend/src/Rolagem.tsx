import { useEffect, useRef, useState } from "react";

// Caixa com rolagem propria: tabela mais larga que o cartao, grafico de muitos meses, tabela longa.
// Quando o conteudo passa da caixa, ela vira uma REGIAO nomeada que o teclado alcanca (o Tab entra, as
// setas rolam) e ganha o modificador `--rola`, que acende a borda da coluna ancorada (tokens.css). Quando
// cabe, fica uma div comum: uma parada de Tab numa tabela que nao rola e' so' uma tecla a mais para quem
// navega por teclado. O nome diz para onde rola: o cartao em volta costuma ter o mesmo titulo, e dois
// landmarks com o mesmo nome nao se distinguem.
// `alta` (F-49): tabela de mais de uma tela. A caixa tem altura maxima, o cabecalho fica fixo no topo dela
// e a barra horizontal fica a' vista (antes ela so' aparecia no fim da tabela, telas abaixo).
// N05-05: `alta` diz "pode ficar alta". O modificador so' entra quando a tabela (o primeiro filho) e' mais alta
// que a janela util (innerHeight - 200, o mesmo calc do CSS); numa janela que mostra a tabela inteira a caixa
// nao limita nada (a 1920 a matriz de Documentos escondia a 8a empresa).
export default function Rolagem({ rotulo, className = "tabela-wrap", alta = false, children }:
    { rotulo: string; className?: string; alta?: boolean; children: React.ReactNode }) {
  const caixa = useRef<HTMLDivElement>(null);
  const [rola, setRola] = useState<{ h: boolean; v: boolean }>({ h: false, v: false });
  const [passaDaJanela, setPassaDaJanela] = useState(false);

  useEffect(() => {
    const el = caixa.current;
    if (!el) return;
    const medir = () => {
      const h = el.scrollWidth > el.clientWidth + 1, v = el.scrollHeight > el.clientHeight + 1;
      setRola(r => (r.h === h && r.v === v ? r : { h, v }));
      // a altura do primeiro filho nao depende do modificador, entao medir aqui nao gira em falso
      const filho = el.firstElementChild as HTMLElement | null;
      const alto = alta && !!filho && filho.offsetHeight > window.innerHeight - 200;
      setPassaDaJanela(a => (a === alto ? a : alto));
    };
    medir();
    window.addEventListener("resize", medir);
    // jsdom (testes) nao tem ResizeObserver: la' a medicao unica basta
    if (typeof ResizeObserver === "undefined") return () => window.removeEventListener("resize", medir);
    const observador = new ResizeObserver(medir);
    observador.observe(el);
    if (el.firstElementChild) observador.observe(el.firstElementChild);
    return () => { observador.disconnect(); window.removeEventListener("resize", medir); };
  }, [alta]);

  const algum = rola.h || rola.v;
  const sentido = rola.h && rola.v ? "rola" : rola.h ? "rola na horizontal" : "rola na vertical";
  const classes = [className, passaDaJanela && `${className}--alta`, rola.h && `${className}--rola`].filter(Boolean).join(" ");
  return (
    <div ref={caixa} className={classes}
      {...(algum ? { tabIndex: 0, role: "region", "aria-label": `${rotulo} (${sentido})` } : {})}>
      {children}
    </div>
  );
}
