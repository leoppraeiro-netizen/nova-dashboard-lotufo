import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
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
  // le de novo quando a pagina muda a versao, como o cartao de verdade
  FrcConsorcio: ({ aoLer, versao }: { aoLer?: (s: SituacaoFrc) => void; versao: number }) => {
    // eslint-disable-next-line react-hooks/exhaustive-deps
    useEffect(() => { if (frcLida.atual) { aoLer?.(frcLida.atual as SituacaoFrc); frcLida.lida = true; } }, [versao]);
    return null;
  },
}));
vi.mock("./Notas", () => ({
  Notas: ({ aoMudar, rotulo, medicao, podeDesfazer }: { aoMudar: () => void; rotulo?: string; medicao: { id: number }; podeDesfazer?: boolean }) =>
    <div data-medicao={medicao.id} data-desfazer={String(!!podeDesfazer)}>{rotulo}<button type="button" onClick={aoMudar}>Anexar nota (teste)</button></div>,
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

  // issue #71 (revisor na PR #202): desfazer o vinculo da nota so' para o admin e so' em medicao aberta
  it.each([["protocolada", "true"], ["recebida", "false"], ["cancelada", "false"], ["desistida", "false"]])(
    "medição %s: desfazer vínculo da nota = %s", async (estado, esperado) => {
      responder();
      const base = api.getMockImplementation()!;
      api.mockImplementation(async (url: string, opcoes?: unknown) =>
        url === "/api/contratos/1/medicoes" ? [{ ...MEDICAO, estado }] : base(url, opcoes));
      const { container } = render(<MedicaoPagina contratoId={1} medicaoId={5} usuario={usuario} origem={null} />);
      await waitFor(() => expect(container.querySelector("[data-medicao='5']")).not.toBeNull());
      expect(container.querySelector("[data-medicao='5']")!.getAttribute("data-desfazer")).toBe(esperado);
    });

  it("engenharia não desfaz vínculo de nota", async () => {
    responder();
    const { container } = render(<MedicaoPagina contratoId={1} medicaoId={5} usuario={{ ...usuario, perfil: "engenharia" } as Usuario} origem={null} />);
    await waitFor(() => expect(container.querySelector("[data-medicao='5']")).not.toBeNull());
    expect(container.querySelector("[data-medicao='5']")!.getAttribute("data-desfazer")).toBe("false");
  });

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

  // issue #208: o espelho misto que ficou vigente para outra medicao (superado para esta) nao e' o espelho dela
  it("a etapa do espelho mostra a versão mais nova da medição, não o misto superado", async () => {
    responder();
    const base = api.getMockImplementation()!;
    const esp = (id: number, versao: number, superado: boolean) => ({ id, numero: 23, versao, situacao: "vigente",
      criado_em: "2026-10-15 12:00:00", criado_por_nome: null, envio: null,
      medicoes: [{ id: 5, tipo: "execucao", superado }] });
    api.mockImplementation(async (url: string, opcoes?: unknown) =>
      url === "/api/contratos/1/espelho" ? { espelhos: [esp(7, 1, true), esp(8, 2, false)] } : base(url, opcoes));
    render(<MedicaoPagina contratoId={1} medicaoId={5} usuario={usuario} origem={null} />);
    expect(await screen.findByText(/nº 23 · versão 2/)).toBeTruthy();
    expect(screen.queryByText(/nº 23 · versão 1/)).toBeNull();
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

  it("anexar a FRC assinada na etapa 4 relê a FRC e a etapa 3 fecha, sem recarregar a página", async () => {
    const ITEM = { chave: "frc:5", rotulo: "FRC assinada", medicao_id: 5, frc_gerada: 77, estado: "falta",
      acao: "anexar_frc", detalhe: "Falta a assinada" };
    const ENVIO = { chave: "m5", contrato_id: 1, obra: "Hospital", orgao: "SINFRA", orgao_sub: null, familia: "sinfra",
      grupo: "SINFRA", a_pedido: false, medicao_ids: [5], descricao: "23ª medição", notas: [], valor_centavos: 100,
      emitida_em: "2026-10-13", dias: 1, situacao: "pendente", aviso: null, protocolo_id: 3, itens: [ITEM] };
    responder();
    const base = api.getMockImplementation()!;
    api.mockImplementation(async (url: string, opcoes?: unknown) => {
      if (url === "/api/contratos/1/medicoes") return [{ ...MEDICAO, estado: "nota_emitida" }];
      if (url === "/api/notas/a-enviar") return { envios: [ENVIO], contadores: {} };
      if (url === "/api/notas/envio/3") return { envio: ENVIO, familia: "sinfra", etapa: "nota", situacao_protocolo: "rascunho",
        carta: null, previa: { para: [], copia: [], assunto: "Notas", corpo: "Bom dia.", anexos: [], links: [] },
        bloqueio: null, pendencias: [], justificativa_obrigatoria: false, extras: [] };
      if (url.startsWith("/api/correio/contatos")) return [];
      return base(url, opcoes);
    });
    frcLida.atual = consorcio({});
    const { container } = render(<MedicaoPagina contratoId={1} medicaoId={5} usuario={usuario} origem={null} />);
    const etapa = () => container.querySelector("#etapa-3") as HTMLDetailsElement;
    await waitFor(() => expect(etapa().open).toBe(true));
    frcLida.atual = consorcio({ assinada: true });
    const pdf = new File(["%PDF-1.4"], "FRC 77 assinada.pdf", { type: "application/pdf" });
    fireEvent.change(await screen.findByLabelText("Anexar FRC assinada"), { target: { files: [pdf] } });
    await waitFor(() => expect(etapa().open).toBe(false));
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

// issue #188: a execucao e o reajuste da mesma competencia na mesma pagina; onde o orgao junta os dois no mesmo
// e-mail, a metade pronta espera a outra (opcao A: a espera fica na tela e no envio, nao no estado)
describe("Página da medição: notas da medição e do reajuste", () => {
  afterEach(() => { cleanup(); api.mockReset(); });

  const REAJ = { ...MEDICAO, id: 6, tipo: "reajuste", estado: "espelho_enviado", valor_protocolado_centavos: 50000 };
  const metade = (id: number, tipo: string, extra: Record<string, unknown> = {}) => ({
    medicao_id: id, tipo, titulo: tipo === "execucao" ? "23ª Medição" : "Reajuste da 23ª Medição", estado: "nota_emitida",
    faltam: 0, esperadas: [], completa: true, espera: null, liberacao: null, ...extra });
  const ESPERA = { medicao_id: 6, titulo: "Reajuste da 23ª Medição", tipo: "reajuste", texto: "esperando as notas do reajuste" };

  function comPar(par: unknown) {
    responder();
    const base = api.getMockImplementation()!;
    api.mockImplementation(async (url: string, opcoes?: unknown) => {
      if (url === "/api/contratos/1/medicoes") return [{ ...MEDICAO, estado: "nota_emitida" }, REAJ];
      if (url === "/api/medicoes/5/par") return par;
      if (url === "/api/notas/a-enviar") return { envios: [], contadores: {} };
      return base(url, opcoes);
    });
  }

  const SINFRA = { junta: true, orgao: "SINFRA", metades: [metade(5, "execucao", { espera: ESPERA }),
    metade(6, "reajuste", { estado: "espelho_enviado", completa: false, faltam: 2 })] };

  it("órgão que junta: dois blocos, o que falta por bloco, o passo em espera e o aviso", async () => {
    comPar(SINFRA);
    const { container } = render(<MedicaoPagina contratoId={1} medicaoId={5} usuario={usuario} origem={null} />);
    expect(await screen.findByRole("region", { name: "Execução · 23ª Medição" })).toBeTruthy();
    expect(screen.getByRole("region", { name: "Reajuste da 23ª Medição" })).toBeTruthy();
    expect(container.querySelector("[data-medicao='6']")).toBeTruthy();       // a nota do reajuste vai para o reajuste
    const etapa3 = container.querySelector("#etapa-3") as HTMLElement;
    expect(etapa3.querySelector(".etapa__cabeca")!.textContent).toBe("3Nota fiscalexecução completa · reajuste: faltam 2 notas");
    const barra = screen.getByRole("navigation", { name: "Etapas da medição" });
    expect(within(barra).getByRole("link", { name: /Nota fiscal · em espera/ })).toBeTruthy();
    expect(barra.querySelector(".etapas-barra__item--espera")).toBeTruthy();
    expect(etapa3.textContent).toContain("Na SINFRA a medição e o reajuste vão no mesmo e-mail. O envio ao órgão abre "
      + "quando chegarem as notas do reajuste.");
    // a etapa 4 (o envio) ainda nao abriu
    expect(container.querySelector("#etapa-4")!.className).toContain("etapa--futura");
  });

  it("na página do reajuste que falta: os mesmos blocos e o aviso, mas a etapa é a da vez, não em espera", async () => {
    comPar(SINFRA);
    const base = api.getMockImplementation()!;
    api.mockImplementation(async (url: string, opcoes?: unknown) => url === "/api/medicoes/6/par" ? SINFRA : base(url, opcoes));
    const { container } = render(<MedicaoPagina contratoId={1} medicaoId={6} usuario={usuario} origem={null} />);
    expect(await screen.findByRole("region", { name: "Execução · 23ª Medição" })).toBeTruthy();
    expect(screen.getByRole("region", { name: "Reajuste da 23ª Medição" })).toBeTruthy();
    expect(container.querySelector(".etapas-barra__item--espera")).toBeNull();
    expect(container.querySelector("#etapa-3")!.textContent).toContain("O envio ao órgão abre quando chegarem as notas do reajuste.");
    // a saida de emergencia libera a execucao (a metade pronta), tambem a partir daqui
    expect(screen.getByRole("button", { name: "Enviar a medição sem o reajuste…" })).toBeTruthy();
  });

  it("saída de emergência: justificativa obrigatória, libera só a medição pronta", async () => {
    comPar(SINFRA);
    render(<MedicaoPagina contratoId={1} medicaoId={5} usuario={usuario} origem={null} />);
    fireEvent.click(await screen.findByRole("button", { name: "Enviar a medição sem o reajuste…" }));
    const liberar = screen.getByRole("button", { name: "Liberar o envio só da medição" }) as HTMLButtonElement;
    expect(liberar.disabled).toBe(true);
    fireEvent.change(screen.getByLabelText("Justificativa (obrigatória)"), { target: { value: "notas do reajuste presas no faturamento" } });
    fireEvent.click(liberar);
    await waitFor(() => expect(api).toHaveBeenCalledWith("/api/medicoes/5/envio-sem-a-outra",
      { method: "POST", body: JSON.stringify({ justificativa: "notas do reajuste presas no faturamento" }) }));
  });

  it("a justificativa da liberação aparece na linha do tempo", async () => {
    comPar({ ...SINFRA, metades: [metade(5, "execucao", { liberacao: { justificativa: "notas presas no faturamento",
      em: "2026-10-15 13:00:00", por: "Engenharia" } }), SINFRA.metades[1]] });
    render(<MedicaoPagina contratoId={1} medicaoId={5} usuario={usuario} origem={null} />);
    expect((await screen.findAllByText(/Envio liberado sem o reajuste por Engenharia\. Justificativa: “notas presas no faturamento”/)).length)
      .toBeGreaterThan(0);
    expect(screen.queryByRole("button", { name: "Enviar a medição sem o reajuste…" })).toBeNull();
  });

  it("órgão que separa: duas trilhas, sem espera e sem saída de emergência", async () => {
    comPar({ junta: false, orgao: "MTPAR", metades: [metade(5, "execucao"),
      metade(6, "reajuste", { estado: "espelho_enviado", completa: false, faltam: 1 })] });
    const { container } = render(<MedicaoPagina contratoId={1} medicaoId={5} usuario={usuario} origem={null} />);
    const exec = await screen.findByRole("navigation", { name: "Etapas: execução" });
    const reaj = screen.getByRole("navigation", { name: "Etapas: reajuste" });
    expect(exec.querySelector("[aria-current='step']")!.textContent).toContain("Envio ao órgão");
    expect(reaj.querySelector("[aria-current='step']")!.textContent).toContain("Nota fiscal");
    expect(screen.queryByRole("navigation", { name: "Etapas da medição" })).toBeNull();
    // a trilha da outra metade leva aos cartoes da pagina dela; a desta pagina, aos cartoes daqui (gate Sol S3)
    expect(within(reaj).getByRole("link", { name: "Nota fiscal" }).getAttribute("href")).toMatch(/6.*#etapa-3$/);
    expect(within(exec).getByRole("link", { name: "Envio ao órgão" }).getAttribute("href")).toBe("#etapa-4");
    expect(container.querySelector(".etapas-barra__item--espera")).toBeNull();
    expect(screen.queryByRole("button", { name: /sem o reajuste/ })).toBeNull();
    expect(container.querySelector("#etapa-4")!.className).toContain("etapa--atual");
  });

  it("medição sem reajuste: um bloco só e a barra de sempre", async () => {
    comPar({ junta: true, orgao: "SINFRA", metades: [] });
    const { container } = render(<MedicaoPagina contratoId={1} medicaoId={5} usuario={usuario} origem={null} />);
    expect(await screen.findByRole("navigation", { name: "Etapas da medição" })).toBeTruthy();
    expect(container.querySelectorAll("[data-medicao]")).toHaveLength(1);
    expect(screen.queryByRole("region", { name: "Execução · 23ª Medição" })).toBeNull();
  });
});

// issue #53 (decisao do dono, 15/10/2026): o recebimento a mao e' so' do admin; a engenharia espera o RM
describe("Página da medição: recebimento à mão", () => {
  afterEach(() => { cleanup(); api.mockReset(); });

  it("o admin vê “Registrar recebimento” na medição protocolada", async () => {
    responder();
    render(<MedicaoPagina contratoId={1} medicaoId={5} usuario={usuario} origem={null} />);
    expect(await screen.findByRole("button", { name: "Registrar recebimento" })).toBeTruthy();
  });

  it("a engenharia não vê o botão: o RM marca a baixa", async () => {
    responder();
    render(<MedicaoPagina contratoId={1} medicaoId={5} usuario={{ ...usuario, perfil: "engenharia" }} origem={null} />);
    expect(await screen.findByText(/O RM marca a baixa sozinho/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Registrar recebimento" })).toBeNull();
  });
});
