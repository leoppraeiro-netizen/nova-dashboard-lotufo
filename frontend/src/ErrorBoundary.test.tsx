import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import ErrorBoundary from "./ErrorBoundary";

function Quebra(): never {
  throw new Error("dado inesperado");
}

describe("ErrorBoundary", () => {
  // O React reporta o erro capturado no console; silenciar so' aqui, para o teste
  // nao parecer uma falha.
  beforeEach(() => { vi.spyOn(console, "error").mockImplementation(() => {}); });
  afterEach(() => { cleanup(); vi.restoreAllMocks(); });

  it("mostra a tela de falha com a mensagem e o botão de recarregar", () => {
    render(<ErrorBoundary><Quebra /></ErrorBoundary>);
    expect(screen.getByRole("alert")).toBeTruthy();
    expect(screen.getByText("dado inesperado")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Recarregar a página" })).toBeTruthy();
  });

  it("sem erro, renderiza o filho", () => {
    render(<ErrorBoundary><p>tudo certo</p></ErrorBoundary>);
    expect(screen.getByText("tudo certo")).toBeTruthy();
    expect(screen.queryByRole("alert")).toBeNull();
  });
});
