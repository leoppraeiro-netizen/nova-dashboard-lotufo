import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiErro } from "./api";
import Espelho from "./Espelho";
import { ir } from "./rota";

const { api } = vi.hoisted(() => ({ api: vi.fn() }));
vi.mock("./api", () => ({ api, ApiErro: class ApiErro extends Error {
  status: number; corpo?: unknown;
  constructor(status = 0, mensagem = "", corpo?: unknown) { super(mensagem); this.status = status; this.corpo = corpo; }
} }));

const REGRA = { situacao: "ativa", saidas: 4, entradas: [
  { chave: "medicao", rotulo: "Valor da medição", natureza: "medicao" },
  { chave: "reajuste", rotulo: "Valor do reajuste", natureza: "reajuste" }] };

const saida = (chave: string, natureza: string, municipio: string, valor: number) => ({
  chave, natureza, rotulo: natureza === "medicao" ? "Medição" : "Reajuste", emissor: "lotufo", municipio,
  valor, mo: 1, material: 1, inss: 1, iss: 1, irrf: 1, ibs: null, cbs: null, liquido: valor - 3 });

const PREVIA = { medicoes: [{ tipo: "execucao", valor_centavos: 63452958, existente: null },
                            { tipo: "reajuste", valor_centavos: 3865583, existente: null }], avisos: [],
  saidas: [saida("caceres-medicao", "medicao", "Cáceres", 52843623), saida("porto-medicao", "medicao", "Porto Esperidião", 10609335),
           saida("caceres-reajuste", "reajuste", "Cáceres", 3219258), saida("porto-reajuste", "reajuste", "Porto Esperidião", 646325)] };

const ESPELHO = { id: 7, numero: 10, competencia: "2026-05", versao: 1, situacao: "vigente", criado_em: "2026-09-22 14:00:00",
  entradas: { medicao: 63452958, reajuste: 3865583 },
  criado_por_nome: "Maria", motivo: null, saidas: PREVIA.saidas, medicoes: [{ id: 1, tipo: "execucao", estado: "espelho_gerado" }],
  arquivos: [{ documento_id: 3, saida: "caceres-medicao", nome: "ESPELHO - MT-388 - 10ª Medição (05.2026) - Cáceres.docx", tamanho: 29000 }],
  envio: null };

describe("Espelho", () => {
  afterEach(() => { cleanup(); api.mockReset(); });

  it("obra sem regra ativa mostra o aviso do fluxo antigo e nenhum botão", async () => {
    api.mockResolvedValueOnce({ regra: null, espelhos: [] });
    render(<Espelho contratoId={1} podeEditar aoMudar={() => {}} />);
    expect(await screen.findByText(/fluxo antigo/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Gerar espelho/ })).toBeNull();
  });

  it("o formulário só conta como rascunho depois de preenchido (guarda de saída)", async () => {
    const confirmar = vi.spyOn(window, "confirm").mockReturnValue(false);
    window.history.replaceState(null, "", "/obras/1");
    api.mockResolvedValueOnce({ regra: REGRA, espelhos: [] });
    render(<Espelho contratoId={1} podeEditar aoMudar={() => {}} abrirForm />);
    await screen.findByLabelText("Nº da medição");
    ir({ tela: "avisos" });                       // aberto e vazio: sai sem perguntar
    expect(confirmar).not.toHaveBeenCalled();
    window.history.replaceState(null, "", "/obras/1");
    fireEvent.change(screen.getByLabelText("Nº da medição"), { target: { value: "10" } });
    ir({ tela: "avisos" });
    expect(confirmar).toHaveBeenCalledTimes(1);
    expect(window.location.pathname).toBe("/obras/1");
    confirmar.mockRestore();
  });

  it("conferir manda número, competência e valores e renderiza uma linha por nota", async () => {
    api.mockResolvedValueOnce({ regra: REGRA, espelhos: [] });
    api.mockResolvedValueOnce(PREVIA);
    render(<Espelho contratoId={1} podeEditar aoMudar={() => {}} />);
    fireEvent.click(await screen.findByRole("button", { name: /Gerar espelho/ }));
    fireEvent.change(screen.getByLabelText("Nº da medição"), { target: { value: "10" } });
    fireEvent.change(screen.getByLabelText("Competência"), { target: { value: "2026-05" } });
    fireEvent.change(screen.getByLabelText("Valor da medição"), { target: { value: "634.529,58" } });
    fireEvent.change(screen.getByLabelText("Valor do reajuste"), { target: { value: "38.655,83" } });
    fireEvent.click(screen.getByRole("button", { name: "Conferir" }));
    await waitFor(() => expect(screen.getAllByText(/528\.436,23/).length).toBeGreaterThan(0));
    expect(api).toHaveBeenLastCalledWith("/api/contratos/1/espelho/previa", expect.objectContaining({
      method: "POST",
      body: JSON.stringify({ numero: 10, competencia: "2026-05", entradas: { medicao: "634.529,58", reajuste: "38.655,83" } }) }));
    expect(screen.getAllByRole("row")).toHaveLength(5);      // cabecalho + 4 notas
    expect(screen.getByRole("button", { name: "Gerar" })).toBeTruthy();
  });

  it("período vem com o mês da competência e só vai ao servidor quando muda", async () => {
    api.mockResolvedValueOnce({ regra: REGRA, espelhos: [] });
    api.mockResolvedValueOnce({ ...PREVIA, periodo: "05/02/2026 A 28/02/2026" });
    render(<Espelho contratoId={1} podeEditar aoMudar={() => {}} />);
    fireEvent.click(await screen.findByRole("button", { name: /Gerar espelho/ }));
    fireEvent.change(screen.getByLabelText("Nº da medição"), { target: { value: "15" } });
    fireEvent.change(screen.getByLabelText("Competência"), { target: { value: "2026-02" } });
    expect((screen.getByLabelText("Período: de") as HTMLInputElement).value).toBe("2026-02-01");
    expect((screen.getByLabelText("até") as HTMLInputElement).value).toBe("2026-02-28");
    fireEvent.change(screen.getByLabelText("Período: de"), { target: { value: "2026-02-05" } });
    fireEvent.change(screen.getByLabelText("Valor da medição"), { target: { value: "100,00" } });
    fireEvent.click(screen.getByRole("button", { name: "Conferir" }));
    expect(await screen.findByText("05/02/2026 A 28/02/2026")).toBeTruthy();
    expect(JSON.parse(api.mock.lastCall![1].body)).toMatchObject({ periodo_inicio: "2026-02-05", periodo_fim: "2026-02-28" });
  });

  it("trocar a competência volta o período ao mês inteiro dela", async () => {
    api.mockResolvedValueOnce({ regra: REGRA, espelhos: [] });
    render(<Espelho contratoId={1} podeEditar aoMudar={() => {}} />);
    fireEvent.click(await screen.findByRole("button", { name: /Gerar espelho/ }));
    fireEvent.change(screen.getByLabelText("Competência"), { target: { value: "2026-08" } });
    fireEvent.change(screen.getByLabelText("Período: de"), { target: { value: "2026-07-01" } });
    fireEvent.change(screen.getByLabelText("Competência"), { target: { value: "2026-07" } });
    expect((screen.getByLabelText("Período: de") as HTMLInputElement).value).toBe("2026-07-01");
    expect((screen.getByLabelText("até") as HTMLInputElement).value).toBe("2026-07-31");
  });

  it("na medição, o espelho vigente não enviado mostra o arquivo e o botão de enviar", async () => {
    api.mockResolvedValueOnce({ regra: REGRA, espelhos: [ESPELHO] });
    render(<Espelho contratoId={1} podeEditar aoMudar={() => {}} medicao={{ id: 1, tipo: "execucao" }} />);
    expect(await screen.findByText("Não enviado ao faturamento")).toBeTruthy();
    expect(screen.getByRole("link", { name: /ESPELHO - MT-388/ }).getAttribute("href")).toBe("/api/espelhos/7/arquivos/3");
    expect(screen.getByRole("button", { name: "Enviar ao faturamento" })).toBeTruthy();
    // "Gerar de novo" parte dos valores da versao vigente
    fireEvent.click(screen.getByRole("button", { name: "Gerar de novo" }));
    expect((screen.getByLabelText("Valor da medição") as HTMLInputElement).value).toBe("634.529,58");
    expect((screen.getByLabelText("Nº da medição") as HTMLInputElement).value).toBe("10");
  });

  it("versão já enviada: reenvio só com a confirmação marcada (S8)", async () => {
    const enviado = { ...ESPELHO, envio: { id: 9, remetente: "maria@l.com", para: ["f@x.com"], copia: [], assunto: "A",
      enviado_em: "2026-10-10 13:00:00" } };
    const posts: Record<string, unknown>[] = [];
    const MSG = "Esta versão do espelho já foi enviada ao faturamento (às 10:05 por Leo). Para mandar de novo, confirme o reenvio.";
    api.mockImplementation((caminho: string, opts?: RequestInit) => {
      if (caminho === "/api/contratos/1/espelho") return Promise.resolve({ regra: REGRA, espelhos: [enviado] });
      if (caminho === "/api/espelhos/7/envio") return Promise.resolve({ para: ["f@x.com"], copia: [], assunto: "Emissão NF",
        corpo: "Bom dia.", anexos: [], total: 0, limite: 1,
        avisos: ["a versão 1 deste espelho já foi enviada ao faturamento; este envio substitui"] });
      if (caminho === "/api/espelhos/7/enviar") {
        const corpo = JSON.parse(String(opts?.body));
        posts.push(corpo);
        return corpo.reenviar ? Promise.resolve({ envio_id: 10 })
          : Promise.reject(new ApiErro(409, MSG, { mensagem: MSG, codigo: "ESPELHO_JA_ENVIADO" }));
      }
      if (caminho.startsWith("/api/correio/remetente")) return Promise.resolve({ remetente: "eu@lotufo.com" });
      return Promise.resolve([]);
    });
    render(<Espelho contratoId={1} podeEditar aoMudar={() => {}} medicao={{ id: 1, tipo: "execucao" }} />);
    fireEvent.click(await screen.findByRole("button", { name: "Enviar de novo" }));
    const caixa = await screen.findByLabelText("Confirmo o reenvio desta versão (substitui o envio anterior)") as HTMLInputElement;
    expect(caixa.checked).toBe(false);
    fireEvent.click(screen.getByRole("button", { name: "Enviar" }));          // sem marcar: nao pede reenvio
    expect(await screen.findByText(MSG)).toBeTruthy();
    expect(posts[0].reenviar).toBeUndefined();
    expect(screen.queryByRole("button", { name: "Liberar envio" })).toBeNull();   // nao ha reserva a liberar
    fireEvent.click(screen.getByLabelText("Confirmo o reenvio desta versão (substitui o envio anterior)"));
    fireEvent.click(screen.getByRole("button", { name: "Enviar" }));
    await waitFor(() => expect(posts).toHaveLength(2));
    expect(posts[1].reenviar).toBe(true);
  });
});
