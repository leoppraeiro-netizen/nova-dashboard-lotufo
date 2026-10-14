import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import AvisosPagina from "./AvisosPagina";

const { api } = vi.hoisted(() => ({ api: vi.fn() }));
vi.mock("./api", () => ({ api, ApiErro: class ApiErro extends Error { status = 0; } }));

const aviso = (extra: Record<string, unknown> = {}) => ({
  tipo: "execucao_vencendo", nivel: "atencao", publico: ["operacao"], contrato_id: 7, obra: "Granito", dias: 20,
  valor_centavos: null, mensagem: "execução termina em 20 dias (20/10/2026)",
  destino: { tela: "contrato", id: 7, aba: "prazos" }, data: "2026-10-20", sentido: "prazo", ...extra });

describe("Avisos por tipo", () => {
  afterEach(() => { cleanup(); api.mockReset(); });

  it("o resumo da Atenção traz a obra em negrito, lida do campo e não do texto (#23)", async () => {
    api.mockResolvedValue({ avisos: [aviso()] });
    const { container } = render(<AvisosPagina busca={{}} perfil="admin" />);
    await screen.findByText(/o mais urgente/);
    const resumo = container.querySelector("summary")!;
    expect(resumo.querySelector(".forte")?.textContent).toBe("Granito");
    expect(resumo.textContent).toContain("Granito: execução termina em 20 dias");
  });
});
