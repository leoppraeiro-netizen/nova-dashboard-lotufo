import { SeloNivel } from "./Selo";

// "O que falta" do protocolo e do oficio (a lista vem do servidor: app/protocolo.py, app/pleitos.py).
// Certidao sem validade e' CRITICO (D10, 2026-09-26); o resto (peca, assinatura, pacote montado) pede
// atencao. O nivel vai no selo (forma + palavra), nunca so' na cor da linha (F-46).
const CRITICAS = new Set(["certidao"]);

export default function Pendencias({ itens }: { itens: { codigo: string; mensagem: string }[] }) {
  return (
    <ul className="pendencias">
      {itens.map((q, i) => (
        <li key={i}><SeloNivel nivel={CRITICAS.has(q.codigo) ? "critico" : "atencao"} /><span>{q.mensagem}</span></li>
      ))}
    </ul>
  );
}
