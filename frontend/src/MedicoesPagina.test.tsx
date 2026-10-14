import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Usuario } from "./Login";
import MedicoesPagina from "./MedicoesPagina";
import type { LinhaResumo, ResumoMedicoes } from "./resumoMedicoes";

const { api } = vi.hoisted(() => ({ api: vi.fn() }));
vi.mock("./api", () => ({ api, apiForm: vi.fn(), ApiErro: class ApiErro extends Error { status = 0; } }));

const usuario = { id: 1, nome: "Leonardo Praeiro", email: "l@l.com", perfil: "admin" } as Usuario;

const linha = (extra: Partial<LinhaResumo>): LinhaResumo => ({
  situacao: "enviar-nota", contrato_id: 12, obra: "Estações BRT", contratante: "SINFRA", orgao_sub: "SAGPM / SUOESP",
  medicao_id: 70, medicao_ids: [70, 71], numero: 7, titulo: "7ª Medição + Reajuste", proximo_passo: "protocolar",
  valor_centavos: 997926492, marco: "2026-10-07", dias: 2, ...extra });

const RESUMO: ResumoMedicoes = {
  hoje: "2026-10-09",
  contagens: { "sem-medicao": 3, faturamento: 0, "aguardando-nota": 0, "enviar-nota": 2, "aguardando-pagamento": 0 },
  linhas: [
    linha({}),
    linha({ medicao_id: 72, medicao_ids: [72], numero: 1, titulo: "1ª Medição de Projeto", valor_centavos: 14811701, dias: 24 }),
  ],
  obras: [
    { contrato_id: 12, obra: "Estações BRT", contratante: "SINFRA", orgao_sub: "SAGPM / SUOESP", aberta: true, prevista_id: null, encerramento: false },
    { contrato_id: 17, obra: "MT-388", contratante: "SINFRA", orgao_sub: "SUEF II", aberta: false, prevista_id: 900, encerramento: false },
    { contrato_id: 4, obra: "Cavalaria", contratante: "SINFRA", orgao_sub: "SACID", aberta: false, prevista_id: null, encerramento: false },
    { contrato_id: 13, obra: "Granito", contratante: "MTPAR", orgao_sub: null, aberta: false, prevista_id: null, encerramento: true },
  ],
};

describe("Medições com abas", () => {
  afterEach(() => { cleanup(); api.mockReset(); });

  it("Resumo: cartões por situação, a tabela em andamento e as obras sem medição por contratante", async () => {
    api.mockResolvedValue(RESUMO);
    render(<MedicoesPagina aba="resumo" busca={{}} usuario={usuario} />);
    const quadro = await screen.findByRole("region", { name: "Todas as obras" });
    // A-21 (10/10/2026): a obra em encerramento nao conta como ativa; a legenda diz a base
    expect(within(quadro).getByText("3 obras ativas · 1 em encerramento · 2 medições em andamento")).toBeTruthy();
    // a medição abre na etapa pendente (enviar a nota = etapa 4)
    expect(within(quadro).getByRole("link", { name: "7ª Medição + Reajuste" }).getAttribute("href")).toBe("/obras/12/medicoes/70#etapa-4");
    // a segunda medição aberta da mesma obra não repete o nome como link
    expect(within(quadro).getAllByRole("link", { name: "Estações BRT" })).toHaveLength(1);
    expect(within(quadro).getByText(/^24\s+dias$/).className).toContain("medicoes__parada--acao");
    // sem medição: grupos por contratante, o maior primeiro, fechados
    const grupos = quadro.querySelectorAll("details");
    expect([...grupos].map(d => d.querySelector("summary")?.textContent)).toEqual(
      ["SINFRA2 obras sem medição aberta", "MTPAR1 obra sem medição aberta"]);
    expect([...grupos].every(d => !d.open)).toBe(true);
    // cartão leva à aba; a aba diz a contagem
    const cartoes = screen.getByRole("navigation", { name: "Medições por situação" });
    expect(within(cartoes).getByRole("link", { name: /Enviar nota/ }).getAttribute("href")).toBe("/medicoes/enviar-nota");
    const abas = screen.getByRole("navigation", { name: "Seções de Medições" });
    expect(within(abas).getByRole("link", { name: "Resumo" }).getAttribute("aria-current")).toBe("page");
    expect(within(abas).getByRole("link", { name: /Sem medição aberta/ }).textContent).toBe("Sem medição aberta3");
  });

  it("aba provisória: a tabela filtrada, com estado vazio", async () => {
    api.mockResolvedValue(RESUMO);
    render(<MedicoesPagina aba="aguardando-nota" busca={{}} usuario={usuario} />);
    expect(await screen.findByText("Nenhuma medição aguardando a nota.")).toBeTruthy();
    expect(screen.queryByRole("navigation", { name: "Medições por situação" })).toBeNull();
  });

  it("Iniciar processo: a obra com medição prevista abre essa medição; as outras, a nova medição", async () => {
    api.mockResolvedValue(RESUMO);
    render(<MedicoesPagina aba="resumo" busca={{}} usuario={usuario} />);
    fireEvent.click(await screen.findByRole("button", { name: /Iniciar processo de medição/ }));
    const janela = screen.getByRole("dialog", { name: "Iniciar processo de medição" });
    expect(within(janela).getByRole("link", { name: /MT-388/ }).getAttribute("href")).toBe("/obras/17/medicoes/900");
    expect(within(janela).getByRole("link", { name: /Granito/ }).getAttribute("href")).toBe("/obras/13/medicoes/nova");
    fireEvent.change(within(janela).getByRole("searchbox"), { target: { value: "granito" } });
    expect(within(janela).getAllByRole("link")).toHaveLength(1);
  });

  it("a diretoria não vê o botão de iniciar", async () => {
    api.mockResolvedValue(RESUMO);
    render(<MedicoesPagina aba="resumo" busca={{}} usuario={{ ...usuario, perfil: "diretoria" }} />);
    await screen.findByRole("region", { name: "Todas as obras" });
    expect(screen.queryByRole("button", { name: /Iniciar processo/ })).toBeNull();
  });

  it("os filtros da aba Enviar nota vêm da URL e vão para a URL (sobrevivem ao recarregar)", async () => {
    const env = (chave: string, obra: string) => ({
      chave, contrato_id: 12, obra, orgao: "SINFRA", orgao_sub: null, familia: "sinfra", grupo: "SINFRA", a_pedido: false,
      medicao_ids: [637], descricao: "14ª medição", notas: [{ numero: "2340", natureza: "execucao", valor_centavos: 100 }],
      valor_centavos: 100, emitida_em: "2026-10-08", dias: 1, situacao: "pronto", aviso: null, protocolo_id: null, itens: [] });
    api.mockImplementation(async (c: string) => c.includes("a-enviar")
      ? { envios: [env("a", "MT-388"), env("b", "Granito")], contadores: { Todas: 2, SINFRA: 2 } } : RESUMO);
    window.history.replaceState(null, "", "/medicoes/enviar-nota");
    const { unmount } = render(<MedicoesPagina aba="enviar-nota" busca={{}} usuario={usuario} />);
    const caixa = await screen.findByRole("searchbox", { name: "Buscar nota ou obra" });
    fireEvent.change(caixa, { target: { value: "granito" } });
    expect(window.location.search).toBe("?q=granito");
    unmount();
    // recarregar: a busca da URL reabre a lista ja' filtrada
    render(<MedicoesPagina aba="enviar-nota" busca={Object.fromEntries(new URLSearchParams(window.location.search))} usuario={usuario} />);
    const de = await screen.findByRole("searchbox", { name: "Buscar nota ou obra" }) as HTMLInputElement;
    expect(de.value).toBe("granito");
    expect(screen.queryByText("MT-388")).toBeNull();
  });
});
