import { IconeAlerta } from "./icones";

// Caixa de aviso (F-46, D2/D10): a FORMA sai do nivel, como no Selo. Critico (trava, venceu, diverge)
// leva o triangulo na cor do critico; atencao (nao trava) leva o ponto no ambar. Quem chama diz o
// nivel, nunca o icone: o triangulo ambar dizia "critico" pela forma e "atencao" pela cor.
export default function CaixaAviso({ nivel, como = "p", role, children }: {
  nivel: "critico" | "atencao"; como?: "p" | "span"; role?: "alert" | "status"; children: React.ReactNode;
}) {
  const Tag = como;
  return (
    <Tag className={nivel === "critico" ? "aviso aviso--critico" : "aviso"} role={role}>
      {nivel === "critico" ? <IconeAlerta className="icone icone--p" /> : <span className="aviso__ponto" aria-hidden="true" />}
      {/* a palavra do nivel para o leitor de tela: o icone e' decorativo (aria-hidden) */}
      <span><span className="sr-only">{nivel === "critico" ? "Crítico: " : "Atenção: "}</span>{children}</span>
    </Tag>
  );
}
