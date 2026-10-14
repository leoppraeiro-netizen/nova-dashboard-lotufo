import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { useEffect } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { SituacaoFrc } from "./Frc";
import type { Usuario } from "./Login";
import MedicaoPagina from "./MedicaoPagina";

const { api, frcLida } = vi.hoisted(() => ({ api: vi.fn(), frcLida: { atual: null as unknown, lida: false } }));
vi.mock("./api", async (original) => ({ ...(await original<typeof import("./api")>()), api, apiForm: vi.fn() }));
// Cada cartao tem fluxo proprio; aqui so' importa que, ao avisar a pagina, ela releia o que os outros mostram.
vi.mock("./Espelho", () => ({ default: () => null }));
// a FRC so' conta o que leu (aoLer), como o cartao de verdade depois de GET /frc
vi.mock("./Frc", () => ({
  FrcConsorcio: ({ aoLer }: { aoLer?: (s: SituacaoFrc) => void }) => {
    useEffect(() => { if (frcLida.atual) { aoLer?.(frcLida.atual as SituacaoFrc); frcLida.lida = true; } }, [aoLer]);
    return null;
  },
}));
vi.mock("./Notas", () => ({
  Notas: ({ aoMudar }: { aoMudar: () => void }) => <button type="button" onClick={aoMudar}>Anexar nota (teste)</button>,
}));
vi.mock("./Protocolo", async () => {
  const real = await vi.importActual<typeof import("./Protocolo")>("./Protocolo");
  return {
    ...real,
    ProtocolosDaMedicao: ({ aoMudar }: { aoMudar: () => void }) =>
      <button type="button" onClick={aoMudar}>Enviar protocolo (teste)</button>,
  };
});

const usuario = { id: 1, nome: "Leonardo Praeiro", email: "l@l.com", perfil: "admin" } as Usuario;
const MEDICAO = { id: 5, numero: 23, tipo: "execucao", competencia: "2026-09", estado: "protocolada",
  valor_protocolado_centavos: 1000000, valor_protocolado_origem: null, valor_atestado_centavos: null,
  valor_atestado_origem: null, atestado_em: null, nf_emitida_em: null, recebida_em: null, congelada: 0,
  protocolos: [], notas: [], documentos: [] };
const LISTA = { familia: "ses", etapas: [], pecas: [], medicoes: [], protocolos: [] };

const leituras = (caminho: string) => api.mock.calls.filter(c => c[0] === caminho && !c[1]);

function responder() {
  api.mockImplementation(async (url: string) => {
    if (url.endsWith("/cabecalho")) return { obra: "Hospital", orgao: "SES", instrumento: "CT 1/2026", percentual_lotufo_bp: 10000 };
    if (url === "/api/contratos/1/medicoes") return [MEDICAO];
    if (url === "/api/contratos/1/protocolos") return LISTA;
    if (url.startsWith("/api/medicoes/andamento")) return [];
    if (url === "/api/contratos/1/espelho") return { espelhos: [] };
    return {};
  });
}

describe("Página da medição: as etapas se atualizam entre si", () => {
  afterEach(() => { cleanup(); api.mockReset(); });

  it("depois de anexar ou vincular nota, os protocolos e a medição são lidos de novo", async () => {
    responder();
    render(<MedicaoPagina contratoId={1} medicaoId={5} usuario={usuario} origem={null} />);
    fireEvent.click(await screen.findByRole("button", { name: "Anexar nota (teste)" }));
    await waitFor(() => expect(leituras("/api/contratos/1/protocolos")).toHaveLength(2));
    await waitFor(() => expect(leituras("/api/contratos/1/medicoes")).toHaveLength(2));
  });

  // issue #100 (revisor na PR #141): NF anexada na etapa 3 com o envio aberto na etapa 4 faz o envio reler os anexos
  it("com a nota emitida, anexar nota na etapa 3 relê o envio aberto na etapa 4", async () => {
    responder();
    const base = api.getMockImplementation()!;
    api.mockImplementation(async (url: string, opcoes?: unknown) => {
      if (url === "/api/contratos/1/medicoes") return [{ ...MEDICAO, estado: "nota_emitida" }];
      if (url === "/api/notas/a-enviar") return { envios: [{ chave: "m5", contrato_id: 1, medicao_ids: [5], protocolo_id: 3, notas: [] }], contadores: {} };
      if (url === "/api/notas/envio/3") return null;
      return base(url, opcoes);
    });
    render(<MedicaoPagina contratoId={1} medicaoId={5} usuario={usuario} origem={null} />);
    await waitFor(() => expect(leituras("/api/notas/envio/3")).toHaveLength(1));
    fireEvent.click(screen.getByRole("button", { name: "Anexar nota (teste)" }));
    await waitFor(() => expect(leituras("/api/notas/envio/3")).toHaveLength(2));
  });

  it("depois de enviar um protocolo, a medição é lida de novo", async () => {
    responder();
    render(<MedicaoPagina contratoId={1} medicaoId={5} usuario={usuario} origem={null} />);
    fireEvent.click(await screen.findByRole("button", { name: "Enviar protocolo (teste)" }));
    await waitFor(() => expect(leituras("/api/contratos/1/medicoes")).toHaveLength(2));
  });
});

// issue #148: com a ultima nota a FRC e' gerada e a medicao passa para o envio; a etapa 3 continua aberta ate' a
// FRC assinada estar anexada, porque e' dali que se baixa a FRC para assinar
describe("Página da medição: etapa 3 da obra de consórcio", () => {
  afterEach(() => { cleanup(); api.mockReset(); frcLida.atual = null; frcLida.lida = false; });

  const FRC = { numero: 77, data_geracao: "2026-10-14", gerada_em: "2026-10-14T10:00:00", gerada_por: null,
    bruto_centavos: 100, liquido_centavos: 90, desatualizada: false };
  const consorcio = (extra: Partial<SituacaoFrc>): SituacaoFrc =>
    ({ disponivel: true, consorcio: "Consórcio X", motivo: null, itens: [], frc: FRC, assinada: false, ...extra });

  // devolve a etapa 3 depois que a pagina recebeu a leitura da FRC (aoLer) e renderizou de novo
  async function etapa3(frc: SituacaoFrc, estado = "nota_emitida") {
    responder();
    const base = api.getMockImplementation()!;
    api.mockImplementation(async (url: string, opcoes?: unknown) => {
      if (url === "/api/contratos/1/medicoes") return [{ ...MEDICAO, estado }];
      if (url === "/api/notas/a-enviar") return { envios: [], contadores: {} };
      return base(url, opcoes);
    });
    frcLida.atual = frc;
    const { container } = render(<MedicaoPagina contratoId={1} medicaoId={5} usuario={usuario} origem={null} />);
    await screen.findByRole("button", { name: "Anexar nota (teste)" });
    await waitFor(() => expect(frcLida.lida).toBe(true));
    await act(async () => {});
    return container.querySelector("#etapa-3") as HTMLDetailsElement;
  }

  it("FRC gerada e ainda não assinada: a etapa 3 fica aberta", async () => {
    const etapa = await etapa3(consorcio({}));
    expect(etapa.open).toBe(true);
  });

  it("com a FRC assinada anexada, a etapa 3 fecha", async () => {
    const etapa = await etapa3(consorcio({ assinada: true }));
    expect(etapa.tagName).toBe("DETAILS");
    expect(etapa.open).toBe(false);
  });

  it("medição encerrada sem a FRC assinada: a etapa 3 não abre sozinha", async () => {
    const etapa = await etapa3(consorcio({}), "recebida");
    expect(etapa.open).toBe(false);
  });

  it("obra que não é de consórcio: a etapa 3 feita fica recolhida, como antes", async () => {
    const etapa = await etapa3({ disponivel: false, consorcio: null, motivo: null });
    expect(etapa.open).toBe(false);
  });
});
