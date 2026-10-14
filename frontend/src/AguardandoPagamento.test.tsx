import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import AguardandoPagamento from "./AguardandoPagamento";

const { api } = vi.hoisted(() => ({ api: vi.fn() }));
vi.mock("./api", async (original) => ({ ...(await original<typeof import("./api")>()), api }));

const HOJE = "2026-10-14";
const linha = (extra: Record<string, unknown> = {}) => ({
  medicao_id: 635, contrato_id: 13, obra: "Complexo Xtreme", orgao: "MTPAR", descricao: "15ª medição",
  valor_centavos: 100_000, enviada_em: "2026-10-08", numero_orgao: null, familia: "mtpar", origem: "sistema", ...extra });
// enviadas a 50, 44, 30 e 29 dias de HOJE (45 e 30 sao os limites das faixas) e a 1 dia
const cinco = () => [
  linha({ medicao_id: 1, obra: "Granito", enviada_em: "2026-08-25" }),
  linha({ medicao_id: 2, obra: "MT-402", familia: "sinfra", orgao: "SINFRA", enviada_em: "2026-08-31" }),
  linha({ medicao_id: 3, obra: "Hospital", familia: "ses", orgao: "SES-MT", enviada_em: "2026-09-14", origem: "externo", numero_orgao: "SES-1" }),
  linha({ medicao_id: 4, obra: "MT-388", familia: "sinfra", orgao: "SINFRA", enviada_em: "2026-09-15" }),
  linha({ medicao_id: 5, obra: "Leblon", familia: "sinfra", orgao: "SINFRA", enviada_em: "2026-10-13" }),
];
const faixa = (nome: RegExp) => screen.getByText(nome).closest("tbody") as HTMLElement;

describe("Aguardando pagamento", () => {
  afterEach(() => { cleanup(); api.mockReset(); });

  it("divide em Atrasadas (45+), Atenção (30 a 44) e Em dia, com subtotal e total", async () => {
    api.mockResolvedValue(cinco());
    render(<AguardandoPagamento podeEditar hoje={HOJE} />);
    await screen.findByText(/Atrasadas \(45 dias ou mais\)/);
    const atrasadas = faixa(/Atrasadas \(45 dias ou mais\)/);
    expect(within(atrasadas).getByText(/Granito/)).toBeTruthy();
    expect(within(atrasadas).queryByText(/MT-402/)).toBeNull();
    const atencao = faixa(/Atenção \(30 a 44 dias\)/);
    expect(within(atencao).getByText(/MT-402/)).toBeTruthy();   // 44 dias
    expect(within(atencao).getByText(/Hospital/)).toBeTruthy();  // 30 dias
    const emDia = faixa(/Em dia/);
    expect(within(emDia).getByText(/MT-388/)).toBeTruthy();      // 29 dias
    expect(within(emDia).getByText(/Leblon/)).toBeTruthy();
    expect(atencao.textContent).toContain("2 · R$");
    expect(screen.getByText(/5 notas/)).toBeTruthy();
  });

  it("Parada há: âmbar a partir de 30 dias, vermelho a partir de 45", async () => {
    api.mockResolvedValue(cinco());
    render(<AguardandoPagamento podeEditar hoje={HOJE} />);
    expect((await screen.findByText("50 dias")).className).toContain("parada--acao");
    expect(screen.getByText("44 dias").className).toContain("parada--atencao");
    expect(screen.getByText("30 dias").className).toContain("parada--atencao");
    expect(screen.getByText("29 dias").className).not.toContain("parada--");
  });

  it("escolher uma nota abre o painel com valor, protocolo e links da medição e da obra", async () => {
    api.mockResolvedValue(cinco());
    render(<AguardandoPagamento podeEditar hoje={HOJE} />);
    fireEvent.click(await screen.findByRole("row", { name: /MT-402/ }));
    const painel = screen.getByRole("complementary", { name: "Detalhe da nota" });
    expect(within(painel).getByRole("heading", { name: /MT-402/ })).toBeTruthy();
    expect(within(painel).getByLabelText("Nº do protocolo no órgão")).toBeTruthy();
    expect(within(painel).getByRole("link", { name: /Abrir a medição/ })).toBeTruthy();
    expect(within(painel).getByRole("link", { name: "Abrir a obra" })).toBeTruthy();
  });

  it("MTPAR: campo do SIGA e pílula 'sem protocolo SIGA'; nos outros órgãos, campo do órgão e sem pílula", async () => {
    api.mockResolvedValue([cinco()[0], cinco()[1]]);
    render(<AguardandoPagamento podeEditar hoje={HOJE} />);
    const painel = await screen.findByRole("complementary", { name: "Detalhe da nota" });   // 1ª da lista: Granito, MTPAR
    expect(within(painel).getByLabelText("Nº do protocolo no SIGA")).toBeTruthy();
    expect(within(painel).getByText("sem protocolo SIGA")).toBeTruthy();
    expect(screen.getAllByText("sem protocolo SIGA")).toHaveLength(2);   // linha + painel
    fireEvent.click(screen.getByRole("row", { name: /MT-402/ }));
    expect(within(screen.getByRole("complementary", { name: "Detalhe da nota" })).getByLabelText("Nº do protocolo no órgão")).toBeTruthy();
    expect(screen.getAllByText("sem protocolo SIGA")).toHaveLength(1);   // so' a linha da Granito
  });

  it("diretoria vê o número do órgão sem o formulário de registrar (B-09, 10/10/2026)", async () => {
    api.mockResolvedValue([linha({ familia: "sinfra", orgao: "SINFRA", numero_orgao: "SEI 123" })]);
    render(<AguardandoPagamento podeEditar={false} hoje={HOJE} />);
    const painel = await screen.findByRole("complementary", { name: "Detalhe da nota" });
    expect(within(painel).getByText("SEI 123")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Registrar" })).toBeNull();
    expect(screen.queryByRole("textbox")).toBeNull();
  });

  it("registrar o número confirma \"Número gravado.\" (B-07, 10/10/2026)", async () => {
    api.mockImplementation((url: string) => Promise.resolve(url === "/api/notas/aguardando-pagamento" ? [linha()] : {}));
    render(<AguardandoPagamento podeEditar hoje={HOJE} />);
    fireEvent.change(await screen.findByLabelText("Nº do protocolo no SIGA"), { target: { value: "X-1" } });
    fireEvent.click(screen.getByRole("button", { name: "Registrar" }));
    expect((await screen.findByText("Número gravado.")).getAttribute("role")).toBe("status");
    expect(api).toHaveBeenCalledWith("/api/notas/635/numero-orgao", { method: "POST", body: JSON.stringify({ numero: "X-1" }) });
  });

  it("enquanto o número é gravado, o botão vira 'Registrando…' e fica desabilitado", async () => {
    api.mockImplementation((url: string) => url === "/api/notas/aguardando-pagamento"
      ? Promise.resolve([linha()]) : new Promise(() => {}));
    render(<AguardandoPagamento podeEditar hoje={HOJE} />);
    fireEvent.change(await screen.findByLabelText("Nº do protocolo no SIGA"), { target: { value: "X-1" } });
    fireEvent.click(screen.getByRole("button", { name: "Registrar" }));
    const botao = await screen.findByRole("button", { name: "Registrando…" }) as HTMLButtonElement;
    expect(botao.disabled).toBe(true);
  });

  it("sem notas, mostra o estado vazio", async () => {
    api.mockResolvedValue([]);
    render(<AguardandoPagamento podeEditar hoje={HOJE} />);
    expect(await screen.findByText("Nenhuma nota esperando pagamento.")).toBeTruthy();
  });
});
