import { coladoParaBrl, digitosParaBrl, MAX_DIGITOS_VALOR } from "./formato";

// Campo unico de valor em dinheiro (issue #190): espelho (medicao e reajuste), nota manual e valor da medicao.
// Os digitos entram pela direita com 2 casas ("5000000" -> "50.000,00"); apagar tira o ultimo digito; colar
// "50.000,00", "50000,5" ou "50000" le em reais. O valor que sai e' o texto "50.000,00" (ou "" quando vazio),
// o mesmo formato que as telas ja' mandavam ao servidor.
export default function CampoValor({ id, name, value, onChange, className = "entrada--media entrada--num num",
  placeholder = "Ex.: 50.000,00…", required, autoFocus }: {
  id: string; name: string; value: string; onChange: (valor: string) => void;
  className?: string; placeholder?: string; required?: boolean; autoFocus?: boolean;
}) {
  return (
    <input id={id} name={name} autoComplete="off" spellCheck={false} className={className} inputMode="numeric"
      placeholder={placeholder} required={required} autoFocus={autoFocus} value={value}
      onChange={ev => {
        const digitos = ev.target.value.replace(/\D/g, "").replace(/^0+/, "");
        if (digitos.length > MAX_DIGITOS_VALOR) return;   // acima do teto do servidor: o digito nao entra
        onChange(digitosParaBrl(digitos));
      }}
      onPaste={ev => {
        // colar substitui o campo inteiro; texto que o servidor recusaria (ex.: "1234.56") nao entra
        ev.preventDefault();
        const colado = coladoParaBrl(ev.clipboardData.getData("text"));
        if (colado !== null) onChange(colado);
      }} />
  );
}
