import { cleanup, render } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useRascunho } from "./rascunho";
import { ir, useRota } from "./rota";

function Formulario({ sujo }: { sujo: boolean }) {
  useRascunho(sujo);
  useRota();   // assina o roteador (o Voltar so' e' tratado enquanto ha' uma tela montada)
  return null;
}

describe("guarda de rascunho", () => {
  beforeEach(() => { window.history.replaceState(null, "", "/medicoes"); });
  afterEach(() => { cleanup(); vi.restoreAllMocks(); });

  it("trocar de tela com formulário sujo pede confirmação; recusar fica na tela", () => {
    const confirmar = vi.spyOn(window, "confirm").mockReturnValue(false);
    render(<Formulario sujo />);
    ir({ tela: "avisos" });
    expect(confirmar).toHaveBeenCalledTimes(1);
    expect(window.location.pathname).toBe("/medicoes");
  });

  it("aceitar a confirmação troca de tela", () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    render(<Formulario sujo />);
    ir({ tela: "avisos" });
    expect(window.location.pathname).toBe("/avisos");
  });

  it("sem rascunho, ou depois de limpo, não pergunta", () => {
    const confirmar = vi.spyOn(window, "confirm").mockReturnValue(false);
    const { rerender } = render(<Formulario sujo />);
    rerender(<Formulario sujo={false} />);
    ir({ tela: "avisos" });
    expect(confirmar).not.toHaveBeenCalled();
    expect(window.location.pathname).toBe("/avisos");
  });

  it("filtro da mesma tela e navegação concluída (forcar) não perguntam", () => {
    const confirmar = vi.spyOn(window, "confirm").mockReturnValue(false);
    render(<Formulario sujo />);
    ir({ tela: "medicoes" }, { busca: { q: "mt" } });
    expect(window.location.search).toBe("?q=mt");
    ir({ tela: "avisos" }, { forcar: true });
    expect(confirmar).not.toHaveBeenCalled();
    expect(window.location.pathname).toBe("/avisos");
  });

  it("Voltar do navegador com formulário sujo: recusar repõe a tela; aceitar segue", () => {
    const confirmar = vi.spyOn(window, "confirm").mockReturnValue(false);
    render(<Formulario sujo />);
    window.history.pushState(null, "", "/avisos");   // o navegador ja' trocou a URL quando o popstate chega
    window.dispatchEvent(new PopStateEvent("popstate"));
    expect(confirmar).toHaveBeenCalledTimes(1);
    expect(window.location.pathname).toBe("/medicoes");
    confirmar.mockReturnValue(true);
    window.history.pushState(null, "", "/avisos");
    window.dispatchEvent(new PopStateEvent("popstate"));
    expect(window.location.pathname).toBe("/avisos");
  });

  it("o formulário sujo avisa o navegador ao recarregar ou fechar a aba", () => {
    const { unmount } = render(<Formulario sujo />);
    const ev = new Event("beforeunload", { cancelable: true });
    window.dispatchEvent(ev);
    expect(ev.defaultPrevented).toBe(true);
    unmount();
    const livre = new Event("beforeunload", { cancelable: true });
    window.dispatchEvent(livre);
    expect(livre.defaultPrevented).toBe(false);
  });
});
