import { IconeAlerta, IconeProximo } from "./icones";

// Selo de status unico (DESIGN.md › Components): SEMPRE forma + rotulo, para o estado nunca depender
// so' da cor. `classe` e' o nivel no vocabulario do tokens.css: "" neutro, "selo--ok" em dia,
// "selo--atencao" atencao, "selo--acao" critico. `forte` e' o nivel "Acao" do D2 (ambar com contorno
// cheio). A FORMA sai do nivel, e nao de quem chama: critico leva o triangulo, "Acao" leva a seta em
// circulo, o resto leva o ponto — o mesmo nivel tem a mesma cara em qualquer tela. A maiuscula
// inicial vem do CSS; o texto fica como o servidor manda.
export default function Selo({ classe = "", forte = false, icone, sufixo, title, children }: {
  classe?: string; forte?: boolean; icone?: React.ReactNode; sufixo?: React.ReactNode; title?: string;
  children: React.ReactNode;
}) {
  const forma = icone
    ?? (classe === "selo--acao" ? <IconeAlerta className="icone icone--p" />
      : forte ? <IconeProximo className="icone icone--p" />
      : <span className="selo__ponto" aria-hidden="true" />);
  return (
    <span className={`selo${classe ? ` ${classe}` : ""}${forte ? " selo--forte" : ""}`} title={title}>
      {forma}
      <span className="selo__texto">{children}</span>
      {sufixo}
    </span>
  );
}

// Selo do nivel de uma pendencia (F-46): a palavra e' o proprio nivel, no vocabulario dos avisos.
// O neutro e' o passo do ciclo ("Passo"), que nao trava nem atrasa.
export function SeloNivel({ nivel }: { nivel: "critico" | "atencao" | "neutro" }) {
  return nivel === "critico" ? <Selo classe="selo--acao">Crítico</Selo>
    : nivel === "atencao" ? <Selo classe="selo--atencao">Atenção</Selo>
    : <Selo>Passo</Selo>;
}
