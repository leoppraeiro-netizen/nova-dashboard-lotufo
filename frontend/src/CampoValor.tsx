import { useLayoutEffect, useRef, useState } from "react";
import ErroCampo from "./ErroCampo";
import { coladoParaBrl, digitosParaBrl, MAX_DIGITOS_VALOR } from "./formato";

// Campo unico de valor em dinheiro (issue #190): espelho (medicao e reajuste), nota manual e valor da medicao.
// Os digitos entram pela direita com 2 casas ("5000000" -> "50.000,00"); apagar tira o ultimo digito; colar
// "50.000,00", "50000,5" ou "50000" le em reais. O valor que sai e' o texto "50.000,00" (ou "" quando vazio),
// o mesmo formato que as telas ja' mandavam ao servidor.

const AJUDA_VALOR = "Digite só os números: os centavos e os pontos entram sozinhos.";
const ERRO_COLADO = "Valor colado em formato inválido: use vírgula nos centavos, ex.: 1.234,56";

const soDigitos = (texto: string) => texto.replace(/\D/g, "").replace(/^0+/, "");

/** O que a edicao fez, comparando o texto de antes com o de depois: o trecho tirado e o trecho posto. */
function diferenca(antes: string, depois: string): { removido: string; inserido: string } {
  let p = 0;
  while (p < antes.length && p < depois.length && antes[p] === depois[p]) p++;
  let s = 0;
  while (s < antes.length - p && s < depois.length - p && antes[antes.length - 1 - s] === depois[depois.length - 1 - s]) s++;
  return { removido: antes.slice(p, antes.length - s), inserido: depois.slice(p, depois.length - s) };
}

/** Novo texto do campo depois da edicao, como caixa registradora: o digito entra sempre no fim e apagar tira
 *  sempre o ultimo, onde quer que esteja o cursor (gate Sol S1). Varios caracteres de uma vez (teclado que cola
 *  sem evento de colar, arrastar) sao lidos em reais, como o colar (R3). `null`: a edicao nao entra; `erro`:
 *  texto em formato que o servidor recusaria. */
function editar(antes: string, depois: string): string | null | { erro: true } {
  if (!depois) return "";
  const { removido, inserido } = diferenca(antes, depois);
  if (inserido.length > 1) return coladoParaBrl(inserido) ?? { erro: true };
  if (inserido && !/\d/.test(inserido)) return null;   // letra, virgula ou ponto digitados: nao entram
  let digitos = soDigitos(antes);
  if (removido === antes) digitos = "";   // tudo selecionado e substituido
  else if (removido) digitos = digitos.slice(0, Math.max(0, digitos.length - (removido.replace(/\D/g, "").length || 1)));
  if (!inserido) return digitos ? digitosParaBrl(digitos) : "";   // apagar ate' o fim volta a vazio
  digitos = soDigitos(digitos + inserido);
  if (digitos.length > MAX_DIGITOS_VALOR) return null;   // acima do teto do servidor: o digito nao entra
  return digitosParaBrl(digitos || "0");   // "0" digitado e' R$ 0,00 (glosa total), nao vazio (S3)
}

export default function CampoValor({ id, name, value, onChange, className = "entrada--media entrada--num num",
  placeholder = "Ex.: 50.000,00…", required, autoFocus, ajudaId }: {
  id: string; name: string; value: string; onChange: (valor: string) => void;
  className?: string; placeholder?: string; required?: boolean; autoFocus?: boolean;
  /** Id de uma ajuda que a tela ja' mostra (o espelho tem uma so' para todos os valores); sem ele, o campo
   *  mostra a sua. */
  ajudaId?: string;
}) {
  const ref = useRef<HTMLInputElement>(null);
  const [erro, setErro] = useState("");
  // o cursor fica no fim: e' la' que o digito entra
  useLayoutEffect(() => {
    const el = ref.current;
    if (el && document.activeElement === el) el.setSelectionRange(el.value.length, el.value.length);
  });
  const aplicar = (r: string | null | { erro: true }) => {
    if (r === null) return;
    if (typeof r === "object") { setErro(ERRO_COLADO); return; }
    setErro("");
    onChange(r);
  };
  const ajuda = ajudaId ?? `${id}-ajuda`;
  return (
    <>
      <input ref={ref} id={id} name={name} autoComplete="off" spellCheck={false} className={className} inputMode="numeric"
        placeholder={placeholder} required={required} autoFocus={autoFocus} value={value}
        aria-invalid={erro ? true : undefined} aria-describedby={erro ? `${ajuda} ${id}-erro` : ajuda}
        onChange={ev => aplicar(editar(value, ev.target.value))}
        onPaste={ev => {
          // colar substitui o campo inteiro; texto que o servidor recusaria (ex.: "1234.56") nao entra e avisa
          ev.preventDefault();
          aplicar(coladoParaBrl(ev.clipboardData.getData("text")) ?? { erro: true });
        }} />
      {!ajudaId && <span className="campo__nota" id={ajuda}>{AJUDA_VALOR}</span>}
      <ErroCampo id={`${id}-erro`} erro={erro} />
    </>
  );
}
