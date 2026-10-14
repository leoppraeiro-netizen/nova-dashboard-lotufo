import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import AguardandoPagamento from "./AguardandoPagamento";

const { api } = vi.hoisted(() => ({ api: vi.fn() }));
vi.mock("./api", async (original) => ({ ...(await original<typeof import("./api")>()), api }));

const linha = (extra: Record<string, unknown> = {}) => ({
  medicao_id: 635, contrato_id: 13, obra: "Complexo Xtreme", orgao: "MTPAR", descricao: "15ª medição",
  valor_centavos: 100_000, enviada_em: "2026-10-08", numero_orgao: null, familia: "mtpar", origem: "sistema", ...extra });

describe("Aguardando pagamento", () => {
  afterEach(() => { cleanup(); api.mockReset(); });

  it("diretoria vê o número do órgão sem o formulário de registrar (B-09, 10/10/2026)", async () => {
    api.mockResolvedValue([linha(), linha({ medicao_id: 636, obra: "MT-388", familia: "sinfra", numero_orgao: "SEI 123" })]);
    render(<AguardandoPagamento podeEditar={false} />);
    expect(await screen.findByText("SEI 123")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Registrar" })).toBeNull();
    expect(screen.queryByRole("textbox")).toBeNull();
  });

  it("registrar o número confirma \"Número gravado.\"; a coluna fala do órgão e a dica do SIGA só na MTPAR (B-07, 10/10/2026)", async () => {
    api.mockImplementation((url: string) => Promise.resolve(url === "/api/notas/aguardando-pagamento"
      ? [linha(), linha({ medicao_id: 636, obra: "MT-388", familia: "sinfra", orgao: "SINFRA" })] : {}));
    render(<AguardandoPagamento podeEditar />);
    expect(await screen.findByRole("columnheader", { name: "Nº do protocolo no órgão" })).toBeTruthy();
    expect(screen.getAllByText("(SIGA, na MTPAR)")).toHaveLength(1);
    fireEvent.change(screen.getByLabelText("Nº do protocolo de Complexo Xtreme · 15ª medição"), { target: { value: "X-1" } });
    fireEvent.click(screen.getAllByRole("button", { name: "Registrar" })[0]);
    expect((await screen.findByText("Número gravado.")).getAttribute("role")).toBe("status");
    expect(api).toHaveBeenCalledWith("/api/notas/635/numero-orgao", { method: "POST", body: JSON.stringify({ numero: "X-1" }) });
  });
  it("enquanto o número é gravado, o botão vira 'Registrando…' e fica desabilitado", async () => {
    api.mockImplementation((url: string) => url === "/api/notas/aguardando-pagamento"
      ? Promise.resolve([linha()]) : new Promise(() => {}));
    render(<AguardandoPagamento podeEditar />);
    fireEvent.change(await screen.findByLabelText("Nº do protocolo de Complexo Xtreme · 15ª medição"), { target: { value: "X-1" } });
    fireEvent.click(screen.getByRole("button", { name: "Registrar" }));
    const botao = await screen.findByRole("button", { name: "Registrando…" }) as HTMLButtonElement;
    expect(botao.disabled).toBe(true);
  });
});
