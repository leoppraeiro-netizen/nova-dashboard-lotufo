import { cliqueSimples, hrefDe, ir, type Busca, type Ir, type Rota } from "./rota";

// Fica fora de rota.tsx para o fast refresh: aquele arquivo so' exporta funcoes e tipos.
/** <a> que navega pelo roteador. Mesmo `href` real: copiar o link, abrir em nova aba e o leitor de tela
 *  ("link") funcionam como em qualquer pagina. `menu` marca o link do menu: ele nao guarda origem. */
export function Link({ para, busca, secao, menu, ir: irPor = ir, children, ...resto }:
    { para: Rota; busca?: Busca; secao?: string; menu?: boolean; ir?: Ir; children: React.ReactNode }
    & Omit<React.AnchorHTMLAttributes<HTMLAnchorElement>, "href" | "onClick">) {
  return (
    <a href={hrefDe(para, busca, secao)} {...resto}
      onClick={ev => { if (cliqueSimples(ev)) { ev.preventDefault(); irPor(para, { busca, secao, menu }); } }}>
      {children}
    </a>
  );
}
