import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import ContratoPagina from "./ContratoPagina";
import type { Usuario } from "./Login";

const { api } = vi.hoisted(() => ({ api: vi.fn() }));
vi.mock("./api", async (original) => ({ ...(await original<typeof import("./api")>()), api, apiForm: vi.fn() }));
// O atalho de iniciar a medição tem fluxo proprio (IniciarProxima.test.tsx); aqui so' importa que ele avise a pagina quando cria algo.
vi.mock("./IniciarProxima", () => ({
  default: ({ aoCriar }: { aoCriar: () => void }) => <button type="button" onClick={aoCriar}>Gerar espelho (teste)</button>,
}));

const usuario = { id: 1, nome: "Leonardo Praeiro", email: "l@l.com", perfil: "admin" } as Usuario;
const CABECALHO = { id: 1, obra: "Hospital", orgao: "SES", instrumento: "CT 1/2026", valor_vigente_centavos: 100000,
  cota_vigente_centavos: null, percentual_lotufo_bp: 10000, execucao_fim: null, dias_execucao: null,
  vigencia_fim: null, dias_vigencia: null, status: "ativo" };
const MEDICAO = { id: 5, numero: 23, tipo: "execucao", titulo: "23ª Medição", estado: "nota_emitida",
  competencia: "2026-09", valor_protocolado_centavos: 1000000 };
const LISTA = { familia: "ses", etapas: [{ chave: "unico", rotulo: "Protocolo", carta: false }], pecas: [],
  medicoes: [MEDICAO], protocolos: [] };

const leituras = (caminho: string) => api.mock.calls.filter(c => c[0] === caminho && !c[1]);

function responder() {
  api.mockImplementation(async (url: string, opcoes?: { method?: string }) => {
    if (url.endsWith("/cabecalho")) return CABECALHO;
    if (url.endsWith("/curva")) return { saldo: { vigente_centavos: 0, atestado_execucao_centavos: 0, saldo_centavos: 0, formula: "" } };
    if (url === "/api/inicio") return { avisos: [] };
    if (url.endsWith("/protocolos")) return opcoes?.method === "POST" ? {} : LISTA;
    if (url.endsWith("/medicoes")) return [];
    if (url.startsWith("/api/medicoes/andamento")) return [];
    if (url === "/api/rm/status") return { configurado: false, ultima_sincronizacao: null, ultimo_erro: null };
    return {};
  });
}

describe("Página da obra: os cartões se atualizam entre si", () => {
  afterEach(() => { cleanup(); api.mockReset(); });

  it("depois de criar um protocolo, a tabela de medições é lida de novo", async () => {
    responder();
    render(<ContratoPagina contratoId={1} usuario={usuario} aba="medicoes" origem={null} busca={{}} />);
    fireEvent.click(await screen.findByLabelText(/23ª Medição/));
    await waitFor(() => expect(leituras("/api/contratos/1/medicoes")).toHaveLength(1));
    fireEvent.click(screen.getByRole("button", { name: "Criar protocolo" }));
    await waitFor(() => expect(leituras("/api/contratos/1/medicoes")).toHaveLength(2));
  });

  it("depois de gerar o espelho (que cria ou avança medição), o cartão de novo protocolo lê as medições de novo", async () => {
    responder();
    render(<ContratoPagina contratoId={1} usuario={usuario} aba="medicoes" origem={null} busca={{}} />);
    await screen.findByLabelText(/23ª Medição/);
    expect(leituras("/api/contratos/1/protocolos")).toHaveLength(1);
    fireEvent.click(screen.getByRole("button", { name: "Gerar espelho (teste)" }));
    await waitFor(() => expect(leituras("/api/contratos/1/protocolos")).toHaveLength(2));
  });

  it("a releitura não troca a tabela por 'Carregando' e não leva ao servidor medição que deixou de ser elegível", async () => {
    responder();
    render(<ContratoPagina contratoId={1} usuario={usuario} aba="medicoes" origem={null} busca={{}} />);
    fireEvent.click(await screen.findByLabelText(/23ª Medição/));
    await waitFor(() => expect(screen.getByRole("heading", { name: "Em andamento" })).toBeTruthy());
    // o espelho avança a medição 5: ela some da lista de elegíveis
    api.mockImplementation(async (url: string) => {
      if (url.endsWith("/protocolos")) return { ...LISTA, medicoes: [] };
      if (url.endsWith("/medicoes")) return [];
      if (url.startsWith("/api/medicoes/andamento")) return [];
      return {};
    });
    fireEvent.click(screen.getByRole("button", { name: "Gerar espelho (teste)" }));
    await waitFor(() => expect(screen.queryByLabelText(/23ª Medição/)).toBeNull());
    expect(screen.queryByText("Carregando medições…")).toBeNull();
    expect((screen.getByRole("button", { name: "Criar protocolo" }) as HTMLButtonElement).disabled).toBe(true);
  });
});
