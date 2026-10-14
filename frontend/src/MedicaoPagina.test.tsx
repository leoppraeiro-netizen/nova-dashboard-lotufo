import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Usuario } from "./Login";
import MedicaoPagina from "./MedicaoPagina";

const { api } = vi.hoisted(() => ({ api: vi.fn() }));
vi.mock("./api", () => ({ api, apiForm: vi.fn(), ApiErro: class ApiErro extends Error { status = 0; } }));
// Cada cartao tem fluxo proprio; aqui so' importa que, ao avisar a pagina, ela releia o que os outros mostram.
vi.mock("./Espelho", () => ({ default: () => null }));
vi.mock("./Frc", () => ({ FrcConsorcio: () => null }));
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
