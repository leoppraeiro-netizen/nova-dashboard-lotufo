import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import Diretoria from "./Diretoria";

const { api } = vi.hoisted(() => ({ api: vi.fn() }));
vi.mock("./api", () => ({ api, ApiErro: class ApiErro extends Error { status = 0; } }));

const g = (quantidade: number, valor_centavos: number | null) => ({ quantidade, valor_centavos });
const PAINEL = {
  hoje: "2026-09-24", total_a_receber_liberado: false,
  dinheiro: {
    medido_esperando_nota: g(2, 150_000), nota_esperando_protocolo: g(0, 0), recebido_mes: g(0, 0),
    protocolado: { ...g(2, null), faixas: { ate_30: g(1, null), de_31_a_60: g(0, null), mais_60: g(1, null) },
                   por_orgao: [{ orgao: "SINFRA", ...g(2, null), maior_dias: 85 }] },
    reajustes_apostilamento: { quantidade: 1, maior_dias: 92 } },
  mes_ano: { mes: "2026-09", medido_mes_centavos: 150_000, previsto_mes_centavos: 200_000,
             mesmo_mes_ano_anterior_centavos: 80_000, acumulado_ano_centavos: 1_000_000, previsto_ano_centavos: 2_000_000,
             serie: [{ competencia: "2026-09", medido_centavos: 150_000, previsto_centavos: 200_000 }] },
  proximos: [{ competencia: "2026-09", faturamento_previsto_centavos: 200_000, recebimento_previsto_centavos: null }],
  carteira: { saldo_centavos: 5_000_000, ritmo_mensal_centavos: 100_000, meses_de_producao: 50, por_orgao: [], terminando: [] },
  obras: [{ contrato_id: 7, seq: 1, obra: "Cavalaria", contratante: "SINFRA", empreita: "PRÓPRIA", direito: 1,
            pi_va: 1_000_000, faturados: 400_000, saldo: 600_000, pct_recebido: 0.4, status: "EM ANDAMENTO",
            termino: "2026-12-20", vigencia: "2027-03-20", farol: "vermelho", motivo: "Cavalaria: execução vencida",
            motivos: [{ tipo: "instrumento_pendente", nivel: "critico", dias: -12, valor_centavos: null, texto: "execução vencida" }] }],
  obras_base: { ativas: 19, encerramento: 2, suspensas: 1, encerradas: 0 },
  avisos: [],
};
const RESPOSTAS: Record<string, unknown> = {
  "/api/diretoria": PAINEL,
  "/api/inicio": { avisos: [], resumo: { mes: "2026-09", obras_protocoladas: 1, obras_ativas: 3 } },
  "/api/contratos": [],
};

describe("Carteira", () => {
  afterEach(() => { cleanup(); api.mockReset(); });

  it("Resumo: 'a conciliar' no protocolado, a obra com problema e quantas obras protocolaram no mês", async () => {
    api.mockImplementation((url: string) => Promise.resolve(RESPOSTAS[url]));
    render(<Diretoria ir={() => {}} />);
    expect(await screen.findByText("Onde está o dinheiro")).toBeTruthy();
    expect(screen.getAllByText("a conciliar").length).toBeGreaterThan(0);
    expect(screen.getByText("Crítico")).toBeTruthy();
    expect(await screen.findByText("1 de 3")).toBeTruthy();
    expect(screen.getByText("obras ativas protocolaram")).toBeTruthy();
    // A-21 (10/10/2026): o farol conta mais que as "obras ativas" e diz a base
    expect(screen.getByText("1 de 1 obras (19 ativas, 2 em encerramento, 1 suspensa) com farol em Atenção ou Crítico")).toBeTruthy();
  });

  it("KPIs são lista nativa (ul/li), sem role explícito", async () => {
    api.mockImplementation((url: string) => Promise.resolve(RESPOSTAS[url]));
    render(<Diretoria ir={() => {}} />);
    await screen.findByText("Onde está o dinheiro");
    const kpis = screen.getAllByRole("listitem").filter(i => i.classList.contains("kpi"));
    expect(kpis.length).toBe(7);
    kpis.forEach(i => {
      expect(i.tagName).toBe("LI");
      expect(i.parentElement?.tagName).toBe("UL");
      expect(i.hasAttribute("role")).toBe(false);
    });
    ["Onde está o dinheiro", "O mês"].forEach(n => expect(screen.getByRole("list", { name: n }).tagName).toBe("UL"));
  });

  it("QDOP: exporta a planilha e mostra os motivos da obra", async () => {
    api.mockImplementation((url: string) => Promise.resolve(RESPOSTAS[url]));
    render(<Diretoria ir={() => {}} aba="qdop" />);
    expect((await screen.findByRole("link", { name: /Exportar QDOP/ })).getAttribute("href")).toBe("/api/diretoria/qdop.xlsx");
    expect(screen.getByText("execução vencida")).toBeTruthy();
  });

  it("Produção: o gráfico de 12 meses tem a tabela com mês, previsto e medido, e o gráfico aponta para ela", async () => {
    const serie = Array.from({ length: 12 }, (_, i) => ({
      competencia: `2025-${String(i + 1).padStart(2, "0")}`, previsto_centavos: (i + 1) * 100_000, medido_centavos: (i + 1) * 50_000,
    }));
    const painel = { ...PAINEL, mes_ano: { ...PAINEL.mes_ano, serie } };
    api.mockImplementation((url: string) => Promise.resolve(url === "/api/diretoria" ? painel : RESPOSTAS[url]));
    render(<Diretoria ir={() => {}} aba="producao" />);
    const tabela = (await screen.findByRole("table", { name: /Previsto e medido nos últimos 12 meses/, hidden: true }));
    const linhas = within(tabela).getAllByRole("row", { hidden: true }).slice(1);
    expect(linhas).toHaveLength(12);
    const texto = (l: HTMLElement) => within(l).getAllByRole("cell", { hidden: true }).map(c => (c.textContent ?? "").replace(/\s/g, " "));
    linhas.forEach((l, i) => {
      const reais = (c: number) => `R$ ${(c / 100).toLocaleString("pt-BR", { minimumFractionDigits: 2 })}`;
      expect(texto(l)).toEqual([`${String(i + 1).padStart(2, "0")}/2025`, reais((i + 1) * 100_000), reais((i + 1) * 50_000)]);
    });
    // a tabela mora no "Tabela por competência", recolhido, que o aviso do gráfico cita
    expect(tabela.closest("details")?.querySelector("summary")?.textContent).toBe("Tabela por competência (12)");
    // o gráfico (role="img") manda o leitor de tela para a tabela, que fica logo abaixo
    const grafico = screen.getByRole("img", { name: /Tabela por competência/ });
    expect(grafico.getAttribute("aria-label")).toContain("nos últimos 12 meses");
    expect(screen.getByText("Tabela por competência (12)").tagName).toBe("SUMMARY");
  });
});
