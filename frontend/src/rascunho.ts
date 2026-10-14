import { useEffect, useRef } from "react";

// Guarda de rascunho (issue #27): formulario com coisa digitada que ainda nao foi salva nem enviada (espelho,
// cronograma, e-mail, carta). Cada formulario declara `useRascunho(sujo)`; o roteador (`ir`, Voltar) e o
// navegador (recarregar, fechar a aba) perguntam antes de jogar fora.

const sujos = new Set<symbol>();

export const AVISO_RASCUNHO = "Há alterações que ainda não foram salvas ou enviadas. Sair desta tela e perder o que foi digitado?";

export function haRascunho(): boolean {
  return sujos.size > 0;
}

/** Pergunta antes de sair da tela; sem rascunho, deixa passar sem perguntar. */
export function confirmarSaida(): boolean {
  return !haRascunho() || window.confirm(AVISO_RASCUNHO);
}

function antesDeFechar(ev: BeforeUnloadEvent) {
  if (!haRascunho()) return;
  ev.preventDefault();
  ev.returnValue = "";
}

/** Marca o formulario como sujo enquanto `sujo` for verdadeiro; ao desmontar, solta a marca. */
export function useRascunho(sujo: boolean) {
  const id = useRef(Symbol("rascunho"));
  useEffect(() => {
    if (!sujo) return;
    const marca = id.current;
    if (sujos.size === 0) window.addEventListener("beforeunload", antesDeFechar);
    sujos.add(marca);
    return () => {
      sujos.delete(marca);
      if (sujos.size === 0) window.removeEventListener("beforeunload", antesDeFechar);
    };
  }, [sujo]);
}
