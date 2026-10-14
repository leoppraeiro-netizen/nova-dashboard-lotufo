import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import NotasAEnviar from "./NotasAEnviar";

const { api, apiForm } = vi.hoisted(() => ({ api: vi.fn(), apiForm: vi.fn() }));
vi.mock("./api", async (original) => ({ ...(await original<typeof import("./api")>()), api, apiForm }));

const envio = (chave: string, obra: string, grupo: string, extra: Record<string, unknown> = {}) => ({
  chave, contrato_id: 12, obra, orgao: grupo, orgao_sub: null, familia: "sinfra", grupo, a_pedido: false,
  medicao_ids: [637], descricao: "14ª medição", notas: [{ numero: "2340", natureza: "execucao", valor_centavos: 241890633 }],
  valor_centavos: 241890633, emitida_em: "2026-10-08", dias: 1, situacao: "pronto", aviso: null, protocolo_id: null,
  itens: [{ chave: "notas", rotulo: "Notas fiscais (1)", detalhe: "NFS 2340", estado: "ok" }], ...extra });

describe("Notas a enviar", () => {
  afterEach(() => { cleanup(); api.mockReset(); apiForm.mockReset(); });

  it("agrupa por órgão, conta nas pílulas e mostra o envio no painel; bloqueado não envia nem registra por fora", async () => {
    api.mockResolvedValue({
      envios: [
        envio("c12:m637", "MT-388 Porto Esperidião/Cáceres", "SINFRA", {
          situacao: "bloqueado", aviso: "certidão federal da Rivoli vencida",
          itens: [{ chave: "certidoes:rivoli", rotulo: "Certidões Rivoli (4 de 5)", detalhe: "Federal vencida", estado: "vencida" },
                  { chave: "regularidade:lotufo", rotulo: "Regularidade mensal", detalhe: "O DP ainda não enviou", estado: "falta",
                    acao: "anexar_regularidade", entidade_id: 1, competencia: "2026-08" }] }),
        envio("c20:m700", "Complexo Xtreme", "MTPAR"),
      ],
      contadores: { Todas: 2, SINFRA: 1, MTPAR: 1, "SES-MT": 0, "Pref. VG": 0, "Pref. Cuiabá": 0 },
    });
    render(<NotasAEnviar busca={{}} podeEditar />);
    // o contador vai na pilula (v3: numero no selo redondo, sem parenteses)
    expect(within(await screen.findByRole("link", { name: /Todas/ })).getByText("2")).toBeTruthy();
    expect(screen.getByRole("region", { name: "MTPAR" }).textContent).toContain("Complexo Xtreme");
    const painel = screen.getByRole("complementary", { name: "Envio selecionado" });
    expect(within(painel).getByRole("heading").textContent).toContain("MT-388");
    expect(within(painel).getByText("Vencida")).toBeTruthy();
    expect(within(painel).getByLabelText("Anexar Regularidade mensal")).toBeTruthy();
    expect((within(painel).getByRole("button", { name: /Enviar a nota/ }) as HTMLButtonElement).disabled).toBe(true);
    expect(within(painel).queryByText("Registrar envio feito por fora")).toBeNull();
  });

  it("diretoria vê o envio sem botão de enviar, de anexar nem de registrar por fora (B-09, 10/10/2026)", async () => {
    api.mockResolvedValue({
      envios: [envio("c20:m700", "Complexo Xtreme", "MTPAR", {
        itens: [{ chave: "regularidade:lotufo", rotulo: "Regularidade mensal", detalhe: "O DP ainda não enviou", estado: "falta",
                  acao: "anexar_regularidade", entidade_id: 1, competencia: "2026-08" }] })],
      contadores: { Todas: 1, MTPAR: 1 },
    });
    render(<NotasAEnviar busca={{}} podeEditar={false} />);
    const painel = await screen.findByRole("complementary", { name: "Envio selecionado" });
    expect(within(painel).getByText("Regularidade mensal")).toBeTruthy();
    expect(within(painel).queryByRole("button", { name: /Enviar a nota/ })).toBeNull();
    expect(within(painel).queryByLabelText("Anexar Regularidade mensal")).toBeNull();
    expect(within(painel).queryByText("Registrar envio feito por fora")).toBeNull();
  });

  describe("envio por fora com a irmã no mesmo e-mail (issue #172)", () => {
    const irmas = [{ medicao_id: 638, titulo: "Reajuste da 14ª Medição", tipo: "reajuste" }];
    const ROTULO = "Incluir também o Reajuste da 14ª Medição (saiu no mesmo e-mail)";

    async function registrar(desmarcar: boolean) {
      api.mockResolvedValue({ envios: [envio("c12:m637", "MT-388", "SINFRA", { irmas })], contadores: { Todas: 1, SINFRA: 1 } });
      apiForm.mockResolvedValue({ ok: true });
      render(<NotasAEnviar busca={{}} podeEditar />);
      fireEvent.click(await screen.findByText("Registrar envio feito por fora"));
      const opcao = screen.getByLabelText(ROTULO) as HTMLInputElement;
      expect(opcao.checked).toBe(true);
      if (desmarcar) fireEvent.click(opcao);
      fireEvent.change(screen.getByLabelText("Observação"), { target: { value: "Pelo Outlook" } });
      fireEvent.click(screen.getByRole("button", { name: "Registrar" }));
      await waitFor(() => expect(apiForm).toHaveBeenCalled());
      const [caminho, fd] = apiForm.mock.calls[0] as [string, FormData];
      expect(caminho).toBe("/api/notas/envio-externo");
      return { medicoes: fd.getAll("medicao_ids"), irmas: fd.getAll("irma_ids") };
    }

    it("a irmã com nota emitida vem marcada e o registro leva as duas medições", async () => {
      expect(await registrar(false)).toEqual({ medicoes: ["637"], irmas: ["638"] });
      expect((await screen.findByRole("status")).textContent)
        .toBe("Envio registrado: MT-388 · 14ª medição + Reajuste da 14ª Medição foram para Aguardando pagamento.");
    });

    it("desmarcar e cancelar não deixa a irmã desmarcada na próxima abertura", async () => {
      api.mockResolvedValue({ envios: [envio("c12:m637", "MT-388", "SINFRA", { irmas })], contadores: { Todas: 1, SINFRA: 1 } });
      render(<NotasAEnviar busca={{}} podeEditar />);
      fireEvent.click(await screen.findByText("Registrar envio feito por fora"));
      fireEvent.click(screen.getByLabelText(ROTULO));
      fireEvent.click(screen.getByRole("button", { name: "Cancelar" }));
      fireEvent.click(screen.getByText("Registrar envio feito por fora"));
      expect((screen.getByLabelText(ROTULO) as HTMLInputElement).checked).toBe(true);
    });

    it("desmarcada, o registro leva só a medição do envio", async () => {
      expect(await registrar(true)).toEqual({ medicoes: ["637"], irmas: [] });
    });

    it("sem irmã (MTPAR tramita separado) a opção não aparece", async () => {
      api.mockResolvedValue({ envios: [envio("c20:m700", "Complexo Xtreme", "MTPAR", { familia: "mtpar", irmas: [] })],
        contadores: { Todas: 1, MTPAR: 1 } });
      render(<NotasAEnviar busca={{}} podeEditar />);
      fireEvent.click(await screen.findByText("Registrar envio feito por fora"));
      expect(screen.getByRole("dialog")).toBeTruthy();
      expect(screen.queryByLabelText(/Incluir também/)).toBeNull();
    });
  });

  it("vazio: diz que não há nota e leva para Aguardando pagamento", async () => {
    api.mockResolvedValue({ envios: [], contadores: { Todas: 0 } });
    render(<NotasAEnviar busca={{}} podeEditar />);
    expect(await screen.findByText("Nenhuma nota a enviar")).toBeTruthy();
    expect(screen.getByRole("link", { name: "Ver notas aguardando pagamento" }).getAttribute("href")).toBe("/medicoes/aguardando-pagamento");
  });
});
