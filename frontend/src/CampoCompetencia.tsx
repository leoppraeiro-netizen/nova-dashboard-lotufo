import { useEffect, useRef, useState } from "react";
import ErroCampo from "./ErroCampo";

const MSG = "Competência no formato MM/AAAA, ex.: 09/2026";

/** "2026-09" -> "09/2026"; qualquer outra coisa -> "". */
export function competenciaParaTela(v: string): string {
  const m = /^(\d{4})-(0[1-9]|1[0-2])$/.exec(v);
  return m ? `${m[2]}/${m[1]}` : "";
}

/** "09/2026" (ou "9/2026") -> "2026-09"; texto incompleto ou inválido -> "". */
export function competenciaDaTela(t: string): string {
  const m = /^([1-9]|0[1-9]|1[0-2])\/(\d{4})$/.exec(t);
  return m ? `${m[2]}-${m[1].padStart(2, "0")}` : "";
}

/** A máscara: só números entram, a barra vem sozinha; aceita "9/2026" e o colado "2026-09". */
export function mascaraCompetencia(bruto: string): string {
  const t = bruto.trim();
  const iso = /^(\d{4})-(\d{2})$/.exec(t);
  if (iso) return `${iso[2]}/${iso[1]}`;
  const barra = /^(\d{1,2})\/(\d*)$/.exec(t);
  // o zero do mês só se completa ao sair do campo: completar enquanto edita trava a correção de um campo cheio
  if (barra) return `${barra[1]}/${barra[2].slice(0, 4)}`;
  const d = t.replace(/\D/g, "").slice(0, 6);
  return d.length > 2 ? `${d.slice(0, 2)}/${d.slice(2)}` : d;
}

/** Competência digitada como MM/AAAA. `value` e `onChange` usam "AAAA-MM" (o formato gravado); texto
 *  incompleto ou inválido entrega "" e bloqueia o envio do formulário com o erro em português no campo. */
export default function CampoCompetencia({ id, value, onChange, className, name, required = true }: {
  id: string; value: string; onChange: (aaaaMm: string) => void; className?: string; name?: string; required?: boolean;
}) {
  const [texto, setTexto] = useState(competenciaParaTela(value));
  const [tocado, setTocado] = useState(false);
  const ref = useRef<HTMLInputElement>(null);
  const invalido = texto !== "" && competenciaDaTela(texto) === "";

  // valor que chega de fora (outro formulário, arquivo escolhido) e não é o que o texto já diz
  useEffect(() => {
    if (value !== competenciaDaTela(texto)) setTexto(competenciaParaTela(value));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value]);

  useEffect(() => { ref.current?.setCustomValidity(invalido ? MSG : ""); }, [invalido, texto]);

  const mostrar = invalido && tocado;
  return (
    <>
      <input ref={ref} id={id} name={name} type="text" inputMode="numeric" autoComplete="off" spellCheck={false}
        placeholder="MM/AAAA…" maxLength={7} className={className} required={required} value={texto}
        aria-invalid={mostrar || undefined} aria-describedby={mostrar ? `${id}-erro` : undefined}
        onChange={e => {
          const t = mascaraCompetencia(e.target.value);
          setTexto(t);
          onChange(competenciaDaTela(t));
        }}
        onBlur={() => {
          setTocado(true);
          if (/^[1-9]\/\d{4}$/.test(texto)) setTexto(`0${texto}`);
        }} onInvalid={() => setTocado(true)} />
      <ErroCampo id={`${id}-erro`} erro={mostrar ? MSG : ""} />
    </>
  );
}
