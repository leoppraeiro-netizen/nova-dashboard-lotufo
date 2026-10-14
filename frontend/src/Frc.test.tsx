import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { FrcConsorcio } from "./Frc";
import { ItensEnvio } from "./NotasAEnviar";

const { api } = vi.hoisted(() => ({ api: vi.fn() }));
vi.mock("./api", async (original) => ({ ...(await original<typeof import("./api")>()), api, apiForm: vi.fn() }));

const item = (empresa: string, municipio: string, extra: Record<string, unknown> = {}) => ({
  chave: `${empresa}-${municipio}`, empresa, municipio, esperado_centavos: 81887199, situacao: "falta", documento_id: null,
  nome: null, numero: null, problema: null, valores: null, ...extra });
const anexada = (empresa: string, municipio: string, numero: string) => item(empresa, municipio, {
  situacao: "anexada", documento_id: 1, nome: "x.pdf", numero,
  valores: { bruto: 81887199, inss: 3603036, irrf: 982646, iss: 1637744, retencoes: 6223426, liquido: 75663773 } });

describe("FRC do consórcio (etapa 3)", () => {
  afterEach(() => { cleanup(); api.mockReset(); });

  it("checklist incompleto: anexada com o nº lido, falta em âmbar, número sugerido e geração travada", async () => {
    api.mockResolvedValue({
      disponivel: true, consorcio: "Consórcio Integra BRT", motivo: null, completa: false, ultima: 21, sugerido: 22,
      itens: [anexada("Guaxe", "Várzea Grande", "2026204"), item("Encomind", "Várzea Grande")],
      nao_lidas: [{ documento_id: 9, nome: "NFSE 2026205 - GRUPO GUAXE.pdf", motivo: "sem-numero" }], sobras: [],
      bloqueio: "Falta 1 nota: Encomind · Várzea Grande", frc: null, assinada: false });
    render(<FrcConsorcio medicaoId={7} podeEditar versao={0} aoMudar={() => {}} />);
    const lista = await screen.findByRole("list", { name: "Notas esperadas da medição" });
    const [guaxe, encomind] = within(lista).getAllByRole("listitem");
    expect(within(guaxe).getByText("Anexada")).toBeTruthy();
    expect(guaxe.textContent).toContain("anexada · NF nº 2026204");
    expect(within(encomind).getByText("Falta")).toBeTruthy();
    expect(screen.getByText(/rascunho/).textContent).toContain("não conta");
    expect((screen.getByLabelText("Número da FRC") as HTMLInputElement).value).toBe("22");
    expect(screen.getByText(/Última registrada/).textContent).toContain("21");
    expect((screen.getByRole("button", { name: "Gerar a FRC" }) as HTMLButtonElement).disabled).toBe(true);
    expect(screen.queryByRole("link", { name: "Baixar PDF" })).toBeNull();
    expect(screen.getByText(/Assine no DocuSign/)).toBeTruthy();
  });

  it("FRC gerada: gerar de novo e os dois downloads", async () => {
    api.mockResolvedValue({
      disponivel: true, consorcio: "Consórcio Integra BRT", motivo: null, completa: true, ultima: 22, sugerido: 22,
      itens: [anexada("Lotufo", "Cuiabá", "2284")], nao_lidas: [], sobras: [], bloqueio: null, assinada: false,
      frc: { numero: 22, data_geracao: "2026-10-09", gerada_em: "", gerada_por: "Leo", bruto_centavos: 1210048928,
             liquido_centavos: 1118085213, desatualizada: false } });
    render(<FrcConsorcio medicaoId={7} podeEditar versao={0} aoMudar={() => {}} />);
    expect((await screen.findByRole("button", { name: "Gerar de novo" }) as HTMLButtonElement).disabled).toBe(false);
    expect(screen.getByRole("link", { name: "Baixar PDF" }).getAttribute("href")).toBe("/api/medicoes/7/frc/pdf");
    expect(screen.getByRole("link", { name: "Baixar planilha" }).getAttribute("href")).toBe("/api/medicoes/7/frc/xlsx");
    expect(screen.getByText(/00022/)).toBeTruthy();
  });

  it("consórcio sem formulário: avisa que a geração não está disponível", async () => {
    api.mockResolvedValue({ disponivel: false, consorcio: "Consórcio Oriundi",
                            motivo: "Geração da FRC ainda não disponível para este consórcio" });
    render(<FrcConsorcio medicaoId={7} podeEditar versao={0} aoMudar={() => {}} />);
    expect((await screen.findByText(/ainda não disponível/)).textContent).toContain("Consórcio Oriundi");
  });
});

describe("FRC assinada no envio (etapa 4)", () => {
  it("o item que falta tem onde anexar", () => {
    render(<ItensEnvio aoMudar={() => {}} itens={[{ chave: "frc:7", rotulo: "FRC assinada", estado: "falta",
      detalhe: "Falta a FRC assinada", acao: "anexar_frc", medicao_id: 7 }]} />);
    expect(screen.getByLabelText("Anexar FRC assinada")).toBeTruthy();
    expect(screen.getByText(/Arraste a FRC assinada/)).toBeTruthy();
    cleanup();
  });
});
