import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Notas } from "./Notas";

const { api, apiForm } = vi.hoisted(() => ({ api: vi.fn(), apiForm: vi.fn() }));
vi.mock("./api", async (original) => ({ ...(await original<typeof import("./api")>()), api, apiForm }));

const medicao = { id: 1, numero: 27, tipo: "execucao", competencia: "2026-08", estado: "espelho_enviado" } as any;

const DADOS = {
  esperadas: [
    { chave: "medicao", natureza: "medicao", emissor: "lotufo", municipio: "Cuiabá", valor: 71919072,
      iss: 1438381, inss: 3164439, irrf: 863029, ibs: null, cbs: null, liquido: 66352723, nota_id: null },
  ],
  notas: [],
  faltam: 1,
  pode_declarar: true,
};

describe("Notas", () => {
  afterEach(() => { cleanup(); api.mockReset(); apiForm.mockReset(); });

  it("mostra a nota esperada e a falta, sem lista de NFs do RM", async () => {
    api.mockResolvedValueOnce(DADOS);
    render(<Notas medicao={medicao} podeEditar aoMudar={() => {}} />);
    await waitFor(() => expect(screen.getByText(/Cuiabá/)).toBeTruthy());
    expect(screen.getAllByText(/719\.190,72/).length).toBeGreaterThan(0);
    expect(screen.getByText(/falta 1 nota/)).toBeTruthy();
    expect(screen.queryByText(/Vincular nota do RM/)).toBeNull();
    // sem nota vinculada, declarar completas nao aparece
    expect(screen.queryByRole("button", { name: /Declarar completas/ })).toBeNull();
  });

  it("gravar a justificativa muda o rótulo e desabilita o botão enquanto a chamada roda", async () => {
    api.mockResolvedValueOnce({
      ...DADOS, faltam: 0,
      esperadas: [{ ...DADOS.esperadas[0], nota_id: 5 }],
      notas: [{ nota_id: 5, coligada: 1, numero: "2288", serie: null, emissao: "2026-09-14", valor_centavos: 71919072,
                valor_pdf_centavos: 71919072, origem_nota: "pdf", confirmacao: "aguardando_rm", documento_id: 3,
                conferencia: [{ campo: "iss", espelho: 1438381, nota: 1438581, grau: "divergente" }],
                justificativa: null, leitura: "cuiaba", municipio: "Cuiabá", regra: "pdf", recebido_centavos: 0 }],
      pode_declarar: false,
    });
    render(<Notas medicao={{ ...medicao, estado: "nota_emitida" }} podeEditar aoMudar={() => {}} />);
    await waitFor(() => expect(screen.getByText(/notas completas/)).toBeTruthy());
    fireEvent.click(screen.getByRole("button", { name: "Justificar" }));
    fireEvent.change(screen.getByLabelText(/Justificativa da divergência/), { target: { value: "Arredondamento do município" } });
    api.mockReturnValueOnce(new Promise(() => {}));   // a chamada nunca termina
    fireEvent.click(screen.getByRole("button", { name: "Gravar justificativa" }));
    const botao = await screen.findByRole("button", { name: "Gravando…" }) as HTMLButtonElement;
    expect(botao.disabled).toBe(true);
  });

  it("a tabela de notas é densa: cabe a 1024 px sem rolar (B-04, 10/10/2026)", async () => {
    api.mockResolvedValueOnce(DADOS);
    render(<Notas medicao={medicao} podeEditar aoMudar={() => {}} />);
    await waitFor(() => expect(screen.getByText(/Cuiabá/)).toBeTruthy());
    expect(screen.getByRole("table").className).toContain("tabela--densa");
  });

  it("nota vinculada e divergente mostra a diferenca e o botao de justificar", async () => {
    api.mockResolvedValueOnce({
      ...DADOS, faltam: 0,
      esperadas: [{ ...DADOS.esperadas[0], nota_id: 5 }],
      notas: [{ nota_id: 5, coligada: 1, numero: "2288", serie: null, emissao: "2026-09-14", valor_centavos: 71919072,
                valor_pdf_centavos: 71919072, origem_nota: "pdf", confirmacao: "aguardando_rm", documento_id: 3,
                conferencia: [{ campo: "iss", espelho: 1438381, nota: 1438581, grau: "divergente" }],
                justificativa: null, leitura: "cuiaba", municipio: "Cuiabá", regra: "pdf", recebido_centavos: 0 }],
      pode_declarar: false,
    });
    render(<Notas medicao={{ ...medicao, estado: "nota_emitida" }} podeEditar aoMudar={() => {}} />);
    await waitFor(() => expect(screen.getByText(/notas completas/)).toBeTruthy());
    expect(screen.getByText(/aguardando o RM/)).toBeTruthy();
    expect(screen.getByText(/diverge do espelho: ISS/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Justificar" }));
    expect(screen.getByLabelText(/Justificativa da divergência/)).toBeTruthy();
  });

  it("destaca só a célula do campo que diverge, com o valor lido na nota (G3-11)", async () => {
    api.mockResolvedValueOnce({
      ...DADOS, faltam: 0,
      esperadas: [{ ...DADOS.esperadas[0], nota_id: 5 }],
      notas: [{ nota_id: 5, coligada: 1, numero: "2288", serie: null, emissao: "2026-09-14", valor_centavos: 71919072,
                valor_pdf_centavos: 71919072, origem_nota: "pdf", confirmacao: "aguardando_rm", documento_id: 3,
                conferencia: [{ campo: "iss", espelho: 1438381, nota: 1438581, grau: "divergente" },
                              { campo: "irrf", espelho: 863029, nota: 863030, grau: "arredondamento" }],
                justificativa: null, leitura: "cuiaba", municipio: "Cuiabá", regra: "pdf", recebido_centavos: 0 }],
      pode_declarar: false,
    });
    render(<Notas medicao={{ ...medicao, estado: "nota_emitida" }} podeEditar aoMudar={() => {}} />);
    await waitFor(() => expect(screen.getByText(/notas completas/)).toBeTruthy());
    const linha = screen.getByRole("table").querySelector("tbody tr")!;
    const destacadas = Array.from(linha.querySelectorAll("td.notas__celula--diverge"));
    expect(destacadas).toHaveLength(1);
    expect(destacadas[0].textContent).toContain("14.383,81");
    expect(destacadas[0].textContent).toMatch(/na nota.*14\.385,81/);
    expect(linha.querySelector(".notas__celula--diverge:not(td)")).toBeNull();     // municipio confere
  });

  it("líquido divergente destaca a célula do Líquido e diz o nome do campo (revisão da PR #97)", async () => {
    api.mockResolvedValueOnce({
      ...DADOS, faltam: 0,
      esperadas: [{ ...DADOS.esperadas[0], nota_id: 5 }],
      notas: [{ nota_id: 5, coligada: 1, numero: "2288", serie: null, emissao: "2026-09-14", valor_centavos: 71919072,
                valor_pdf_centavos: 71919072, origem_nota: "pdf", confirmacao: "aguardando_rm", documento_id: 3,
                conferencia: [{ campo: "liquido", espelho: 66352723, nota: 66357723, grau: "divergente" }],
                justificativa: null, leitura: "cuiaba", municipio: "Cuiabá", regra: "pdf", recebido_centavos: 0 }],
      pode_declarar: false,
    });
    render(<Notas medicao={{ ...medicao, estado: "nota_emitida" }} podeEditar aoMudar={() => {}} />);
    await waitFor(() => expect(screen.getByText(/notas completas/)).toBeTruthy());
    const destacadas = Array.from(screen.getByRole("table").querySelectorAll("td.notas__celula--diverge"));
    expect(destacadas).toHaveLength(1);
    expect(destacadas[0].textContent).toMatch(/663\.527,23 no espelho; na nota .*663\.577,23/);
    expect(screen.getByText(/diverge do espelho: líquido/)).toBeTruthy();
  });

  it("conferência antiga que hoje bate com o espelho (versão nova) não destaca dois valores iguais", async () => {
    api.mockResolvedValueOnce({
      ...DADOS, faltam: 0,
      esperadas: [{ ...DADOS.esperadas[0], iss: 1438581, nota_id: 5 }],     // espelho novo: ISS igual ao da nota
      notas: [{ nota_id: 5, coligada: 1, numero: "2288", serie: null, emissao: "2026-09-14", valor_centavos: 71919072,
                valor_pdf_centavos: 71919072, origem_nota: "pdf", confirmacao: "aguardando_rm", documento_id: 3,
                conferencia: [{ campo: "iss", espelho: 1438381, nota: 1438581, grau: "divergente" }],
                justificativa: null, leitura: "cuiaba", municipio: "Cuiabá", regra: "pdf", recebido_centavos: 0 }],
      pode_declarar: false,
    });
    render(<Notas medicao={{ ...medicao, estado: "nota_emitida" }} podeEditar aoMudar={() => {}} />);
    await waitFor(() => expect(screen.getByText(/notas completas/)).toBeTruthy());
    expect(screen.getByRole("table").querySelectorAll(".notas__celula--diverge")).toHaveLength(0);
  });

  it("município divergente destaca o município da saída, não os valores", async () => {
    api.mockResolvedValueOnce({
      ...DADOS, faltam: 0,
      esperadas: [{ ...DADOS.esperadas[0], nota_id: 5 }],
      notas: [{ nota_id: 5, coligada: 1, numero: "2288", serie: null, emissao: "2026-09-14", valor_centavos: 71919072,
                valor_pdf_centavos: 71919072, origem_nota: "pdf", confirmacao: "aguardando_rm", documento_id: 3,
                conferencia: [{ campo: "municipio", espelho: "Cuiabá", nota: "Várzea Grande", grau: "divergente" }],
                justificativa: null, leitura: "cuiaba", municipio: "Várzea Grande", regra: "pdf", recebido_centavos: 0 }],
      pode_declarar: false,
    });
    render(<Notas medicao={{ ...medicao, estado: "nota_emitida" }} podeEditar aoMudar={() => {}} />);
    await waitFor(() => expect(screen.getByText(/notas completas/)).toBeTruthy());
    const linha = screen.getByRole("table").querySelector("tbody tr")!;
    expect(linha.querySelectorAll("td.notas__celula--diverge")).toHaveLength(0);
    const municipio = linha.querySelector("span.notas__celula--diverge")!;
    expect(municipio.textContent).toMatch(/^Cuiabá no espelho; na nota Várzea Grande$/);
  });
});

describe("Notas: só o botão da ação em curso troca o rótulo", () => {
  afterEach(() => { cleanup(); api.mockReset(); apiForm.mockReset(); });

  const COM_DIVERGENCIA = {
    ...DADOS, faltam: 1, pode_declarar: true,
    esperadas: [{ ...DADOS.esperadas[0], nota_id: 5 }],
    notas: [{ nota_id: 5, coligada: 1, numero: "2288", serie: null, emissao: "2026-09-14", valor_centavos: 71919072,
              valor_pdf_centavos: 71919072, origem_nota: "pdf", confirmacao: "aguardando_rm", documento_id: 3,
              conferencia: [{ campo: "iss", espelho: 1438381, nota: 1438581, grau: "divergente" }],
              justificativa: null, leitura: "cuiaba", municipio: "Cuiabá", regra: "pdf", recebido_centavos: 0 }],
  };

  async function abrir() {
    api.mockImplementation((_url: string, opts?: { method?: string }) =>
      opts?.method === "POST" ? new Promise(() => {}) : Promise.resolve(COM_DIVERGENCIA));
    render(<Notas medicao={{ ...medicao, estado: "nota_emitida" }} podeEditar aoMudar={() => {}} />);
    await waitFor(() => expect(screen.getByText(/diverge do espelho: ISS/)).toBeTruthy());
  }

  it("justificativa em curso: 'Declarar completas' fica desabilitado mas mantém o rótulo", async () => {
    await abrir();
    fireEvent.click(screen.getByRole("button", { name: "Justificar" }));
    fireEvent.change(screen.getByLabelText(/Justificativa da divergência/), { target: { value: "Arredondamento" } });
    fireEvent.click(screen.getByRole("button", { name: "Gravar justificativa" }));
    await screen.findByRole("button", { name: "Gravando…" });
    const vizinho = screen.getByRole("button", { name: "Declarar completas" }) as HTMLButtonElement;
    expect(vizinho.disabled).toBe(true);
  });

  it("declaração em curso: 'Declarar completas' vira 'Gravando…' e desabilita", async () => {
    await abrir();
    fireEvent.change(screen.getByLabelText(/Declarar as notas completas/), { target: { value: "Sem serviço no mês" } });
    fireEvent.click(screen.getByRole("button", { name: "Declarar completas" }));
    const botao = await screen.findByRole("button", { name: "Gravando…" }) as HTMLButtonElement;
    expect(botao.disabled).toBe(true);
  });

  it("registro manual em curso: 'Registrar nota' vira 'Registrando…' e 'Declarar completas' mantém o rótulo", async () => {
    apiForm.mockResolvedValue({ documento_id: 9, repetido: false, nota_id: null, conferencia: [], faltam: 1,
      estado: "espelho_enviado", leitura: { ok: false, motivo: "ilegível" } });
    await abrir();
    const arquivo = new File(["x"], "nota.pdf", { type: "application/pdf" });
    fireEvent.change(screen.getByLabelText(/Anexar notas à medição/), { target: { files: [arquivo] } });
    await screen.findByRole("button", { name: "Registrar nota" });
    fireEvent.change(screen.getByLabelText("Número da nota"), { target: { value: "2290" } });
    fireEvent.change(screen.getByLabelText("Emissão"), { target: { value: "2026-09-14" } });
    fireEvent.change(screen.getByLabelText(/^Valor/), { target: { value: "719190,72" } });
    fireEvent.click(screen.getByRole("button", { name: "Registrar nota" }));
    const botao = await screen.findByRole("button", { name: "Registrando…" }) as HTMLButtonElement;
    expect(botao.disabled).toBe(true);
    expect((screen.getByRole("button", { name: "Declarar completas" }) as HTMLButtonElement).disabled).toBe(true);
  });
});
