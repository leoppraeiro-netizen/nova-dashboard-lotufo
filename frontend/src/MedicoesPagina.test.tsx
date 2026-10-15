import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Usuario } from "./Login";
import MedicoesPagina from "./MedicoesPagina";
import type { LinhaResumo, ObraResumo, ResumoMedicoes } from "./resumoMedicoes";

const { api } = vi.hoisted(() => ({ api: vi.fn() }));
vi.mock("./api", async (original) => ({ ...(await original<typeof import("./api")>()), api, apiForm: vi.fn() }));

const usuario = { id: 1, nome: "Leonardo Praeiro", email: "l@l.com", perfil: "admin" } as Usuario;

const linha = (extra: Partial<LinhaResumo>): LinhaResumo => ({
  situacao: "enviar-nota", contrato_id: 12, obra: "Estações BRT", contratante: "SINFRA", orgao_sub: "SAGPM / SUOESP",
  medicao_id: 70, medicao_ids: [70, 71], numero: 7, competencia: "2026-09", titulo: "7ª Medição + Reajuste", proximo_passo: "protocolar",
  valor_centavos: 997926492, marco: "2026-10-07", dias: 2, ...extra });

const SEM_PREVISTA = { prevista_id: null, prevista_numero: null, prevista_competencia: null };
const obra = (extra: Partial<ObraResumo>): ObraResumo => ({
  contrato_id: 1, obra: "Obra", contratante: "SINFRA", orgao_sub: null, aberta: false, aberta_id: null, aberta_numero: null,
  aberta_passo: null, ultima: null, prevista_id: null, prevista_numero: null, prevista_competencia: null, projeto: null,
  encerramento: false, ...extra });

const RESUMO: ResumoMedicoes = {
  hoje: "2026-10-09",
  contagens: { "sem-medicao": 3, faturamento: 0, "aguardando-nota": 0, "enviar-nota": 2, "aguardando-pagamento": 0 },
  linhas: [
    linha({}),
    linha({ medicao_id: 72, medicao_ids: [72], numero: 1, titulo: "1ª Medição de Projeto", valor_centavos: 14811701, dias: 24 }),
  ],
  obras: [
    obra({ contrato_id: 12, obra: "Estações BRT", orgao_sub: "SAGPM / SUOESP", aberta: true, aberta_id: 70, aberta_numero: 7,
      aberta_passo: "enviar nota", ultima: { numero: 7, competencia: "2026-09" },
      projeto: { ...SEM_PREVISTA, aberta_id: 72, aberta_numero: 1, aberta_passo: "anexar as notas", ultima: { numero: 1, competencia: "2026-09" } } }),
    obra({ contrato_id: 17, obra: "MT-388", orgao_sub: "SUEF II", prevista_id: 900, prevista_numero: 24, prevista_competencia: "2026-09",
      ultima: { numero: 23, competencia: "2026-01" } }),
    obra({ contrato_id: 4, obra: "Cavalaria", orgao_sub: "SACID", ultima: { numero: 11, competencia: "2026-12" },
      projeto: { ...SEM_PREVISTA, aberta_id: null, aberta_numero: null, aberta_passo: null, ultima: { numero: 2, competencia: "2026-08" } } }),
    obra({ contrato_id: 13, obra: "Granito", contratante: "MTPAR", encerramento: true }),
    obra({ contrato_id: 21, obra: "Terminais", contratante: "SINFRA", ultima: { numero: 8, competencia: "2026-08" },
      projeto: { aberta_id: null, aberta_numero: null, aberta_passo: null, ultima: null,
        prevista_id: 950, prevista_numero: 4, prevista_competencia: "2026-07" } }),
  ],
};

describe("Medições com abas", () => {
  afterEach(() => { cleanup(); api.mockReset(); });

  it("Resumo: cartões por situação, a tabela em andamento e as obras sem medição por contratante", async () => {
    api.mockResolvedValue(RESUMO);
    render(<MedicoesPagina aba="resumo" busca={{}} usuario={usuario} />);
    const quadro = await screen.findByRole("region", { name: "Todas as obras" });
    // A-21 (10/10/2026): a obra em encerramento nao conta como ativa; a legenda diz a base
    expect(within(quadro).getByText("4 obras ativas · 1 em encerramento · 2 medições em andamento")).toBeTruthy();
    // a medição abre na etapa pendente (enviar a nota = etapa 4)
    expect(within(quadro).getByRole("link", { name: "7ª Medição + Reajuste" }).getAttribute("href")).toBe("/obras/12/medicoes/70#etapa-4");
    // a segunda medição aberta da mesma obra não repete o nome como link
    expect(within(quadro).getAllByRole("link", { name: "Estações BRT" })).toHaveLength(1);
    expect(within(quadro).getByText(/^24\s+dias$/).className).toContain("medicoes__parada--acao");
    // sem medição: grupos por contratante, o maior primeiro, fechados
    const grupos = quadro.querySelectorAll("details");
    expect([...grupos].map(d => d.querySelector("summary")?.textContent)).toEqual(
      ["SINFRA3 obras sem medição aberta", "MTPAR1 obra sem medição aberta"]);
    expect([...grupos].every(d => !d.open)).toBe(true);
    // cartão leva à aba; a aba diz a contagem
    const cartoes = screen.getByRole("navigation", { name: "Medições por situação" });
    expect(within(cartoes).getByRole("link", { name: /Enviar nota/ }).getAttribute("href")).toBe("/medicoes/enviar-nota");
    const abas = screen.getByRole("navigation", { name: "Seções de Medições" });
    expect(within(abas).getByRole("link", { name: "Resumo" }).getAttribute("aria-current")).toBe("page");
    expect(within(abas).getByRole("link", { name: /Sem medição aberta/ }).textContent).toBe("Sem medição aberta3");
  });

  it("aba Aguardando nota: estado vazio sem medição, e a linha da medição que espera a nota", async () => {
    api.mockResolvedValue(RESUMO);
    const { unmount } = render(<MedicoesPagina aba="aguardando-nota" busca={{}} usuario={usuario} />);
    expect(await screen.findByText("Nenhuma medição esperando nota.")).toBeTruthy();
    expect(screen.queryByRole("navigation", { name: "Medições por situação" })).toBeNull();
    unmount();
    api.mockResolvedValue({ ...RESUMO, linhas: [linha({ situacao: "aguardando-nota", proximo_passo: "anexar as notas" })] });
    render(<MedicoesPagina aba="aguardando-nota" busca={{}} usuario={usuario} />);
    const quadro = await screen.findByRole("region", { name: "Aguardando nota" });
    expect(within(quadro).getByText("R$ 9.979.264,92")).toBeTruthy();
  });

  describe("Iniciar processo de medição (#151)", () => {
    async function abrir() {
      api.mockResolvedValue(RESUMO);
      render(<MedicoesPagina aba="resumo" busca={{}} usuario={usuario} />);
      fireEvent.click(await screen.findByRole("button", { name: /Iniciar processo de medição/ }));
      return screen.getByRole("dialog", { name: "Iniciar processo de medição" });
    }
    const escolher = (janela: HTMLElement, obra: string) => fireEvent.click(within(janela).getByRole("radio", { name: new RegExp(obra) }));

    it("lista as obras por contratante com a última medição e a situação; sem escolha, o botão espera", async () => {
      const janela = await abrir();
      expect(within(janela).getByText("A medição começa pelo espelho", { exact: false })).toBeTruthy();
      expect(within(janela).getAllByRole("radio")).toHaveLength(5);
      expect(within(janela).getByRole("radio", { name: /Estações BRT.*7ª em andamento: Enviar nota.*1ª de Projeto em andamento/ })).toBeTruthy();
      expect(within(janela).getByRole("radio", { name: /MT-388.*última: 23ª · 01\/2026.*Prevista pelo cronograma: 24ª · 09\/2026/ })).toBeTruthy();
      expect((within(janela).getByRole("button", { name: "Escolha uma obra" }) as HTMLButtonElement).disabled).toBe(true);
    });

    it("obra em andamento: só abre a medição, sem campos para criar outra", async () => {
      const janela = await abrir();
      escolher(janela, "Estações BRT");
      expect(within(janela).getByText(/já tem a 7ª em andamento \(enviar nota\)/)).toBeTruthy();
      expect(within(janela).queryByLabelText(/Nº da medição/)).toBeNull();
      fireEvent.click(within(janela).getByRole("button", { name: "Abrir a 7ª medição" }));
      expect(window.location.pathname).toBe("/obras/12/medicoes/70");
    });

    it("obra com prevista: campos fixos e começa pela prevista", async () => {
      const janela = await abrir();
      escolher(janela, "MT-388");
      expect((within(janela).getByLabelText("Nº da medição") as HTMLInputElement).readOnly).toBe(true);
      expect((within(janela).getByLabelText("Competência") as HTMLInputElement).value).toBe("setembro de 2026");
      fireEvent.click(within(janela).getByRole("button", { name: "Começar a 24ª pelo espelho" }));
      expect(window.location.pathname).toBe("/obras/17/medicoes/900");
    });

    it("obra sem nada: sugere a próxima (virada de ano), deixa mudar e leva ao espelho com número e competência", async () => {
      const janela = await abrir();
      escolher(janela, "Cavalaria");
      const numero = within(janela).getByLabelText(/Nº da medição/) as HTMLInputElement;
      expect(numero.value).toBe("12");
      expect((within(janela).getByLabelText("Competência") as HTMLInputElement).value).toBe("01/2027");
      fireEvent.change(numero, { target: { value: "15" } });
      fireEvent.click(within(janela).getByRole("button", { name: "Começar a 15ª pelo espelho" }));
      expect(window.location.pathname + window.location.search).toBe("/obras/4/medicoes/nova?numero=15&competencia=2027-01");
    });

    it("série de Projeto: só a obra que tem escolhe Execução / Projeto, e a sugestão segue a série", async () => {
      const janela = await abrir();
      escolher(janela, "MT-388");
      expect(within(janela).queryByRole("radio", { name: "Projeto" })).toBeNull();
      escolher(janela, "Cavalaria");
      fireEvent.click(within(janela).getByRole("radio", { name: "Projeto" }));
      expect((within(janela).getByLabelText(/Nº da medição de Projeto/) as HTMLInputElement).value).toBe("3");
      expect((within(janela).getByLabelText("Competência") as HTMLInputElement).value).toBe("09/2026");
      fireEvent.click(within(janela).getByRole("radio", { name: "Execução" }));
      expect((within(janela).getByLabelText(/Nº da medição/) as HTMLInputElement).value).toBe("12");
      escolher(janela, "Estações BRT");
      fireEvent.click(within(janela).getByRole("radio", { name: "Projeto" }));
      expect(within(janela).getByText(/já tem a 1ª de Projeto em andamento/)).toBeTruthy();
      fireEvent.click(within(janela).getByRole("button", { name: "Abrir a 1ª medição de Projeto" }));
      expect(window.location.pathname).toBe("/obras/12/medicoes/72");
    });

    it("Projeto escolhido segue na URL da Nova medição (tipo=projeto)", async () => {
      const janela = await abrir();
      escolher(janela, "Cavalaria");
      fireEvent.click(within(janela).getByRole("radio", { name: "Projeto" }));
      fireEvent.click(within(janela).getByRole("button", { name: "Começar a 3ª de Projeto pelo espelho" }));
      expect(window.location.pathname + window.location.search).toBe("/obras/4/medicoes/nova?numero=3&competencia=2026-09&tipo=projeto");
    });

    it("a prevista de Projeto aparece só na série de Projeto, nunca em Execução", async () => {
      const janela = await abrir();
      escolher(janela, "Terminais");
      expect(within(janela).queryByText(/prevista pelo cronograma/, { selector: "span" })).toBeNull();
      expect((within(janela).getByLabelText(/Nº da medição/) as HTMLInputElement).value).toBe("9");
      fireEvent.click(within(janela).getByRole("radio", { name: "Projeto" }));
      expect(within(janela).getByText(/tem a 4ª de Projeto prevista pelo cronograma \(07\/2026\)/)).toBeTruthy();
      fireEvent.click(within(janela).getByRole("button", { name: "Começar a 4ª de Projeto pelo espelho" }));
      expect(window.location.pathname).toBe("/obras/21/medicoes/950");
    });

    it("sem número o botão não segue; a busca filtra e mostra o vazio", async () => {
      const janela = await abrir();
      escolher(janela, "Granito");
      expect(within(janela).getByText(/ainda não tem medição lançada/)).toBeTruthy();
      expect((within(janela).getByRole("button", { name: "Informe o número" }) as HTMLButtonElement).disabled).toBe(true);
      fireEvent.change(within(janela).getByRole("searchbox"), { target: { value: "granito" } });
      expect(within(janela).getAllByRole("radio")).toHaveLength(1);
      fireEvent.change(within(janela).getByRole("searchbox"), { target: { value: "zzz" } });
      expect(within(janela).getByText("Nenhuma obra ativa com “zzz”.")).toBeTruthy();
    });
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
