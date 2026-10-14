import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import EnviarNota from "./EnviarNota";

const { api } = vi.hoisted(() => ({ api: vi.fn() }));
vi.mock("./api", () => ({ api, apiForm: vi.fn(), ApiErro: class ApiErro extends Error { status = 0; } }));

const det = {
  envio: { chave: "c20:m631-m632", contrato_id: 20, obra: "MT-401", orgao: "SINFRA", orgao_sub: "SUEF II", familia: "sinfra",
    grupo: "SINFRA", a_pedido: false, medicao_ids: [631, 632], descricao: "7ª medição + reajuste", notas: [],
    valor_centavos: 100, emitida_em: "2026-10-08", dias: 2, situacao: "pronto", aviso: null, protocolo_id: 3, itens: [] },
  familia: "sinfra", etapa: "nota", situacao_protocolo: "rascunho", carta: null,
  previa: { para: ["orgao@exemplo.com"], copia: [], assunto: "Notas", corpo: "Bom dia.", anexos: [], links: [] },
  bloqueio: null, pendencias: [], justificativa_obrigatoria: false, extras: [],
};

describe("Enviar a nota", () => {
  afterEach(() => { cleanup(); api.mockReset(); });

  it("o Cco escrito no e-mail vai no envio (testes de quebra 10/10, A-17)", async () => {
    api.mockImplementation((caminho: string) => {
      if (caminho === "/api/notas/envio/3") return Promise.resolve(det);
      if (caminho.startsWith("/api/correio/remetente")) return Promise.resolve({ remetente: "eu@lotufo.com" });
      return Promise.resolve({});
    });
    render(<EnviarNota protocoloId={3} podeEditar embutido={{ aoConcluir: () => {}, aoTrocar: () => {} }} />);
    fireEvent.click(await screen.findByText("Cco"));
    const cco = screen.getByLabelText(/Cco: digite/);
    fireEvent.change(cco, { target: { value: "oculto@exemplo.com" } });
    fireEvent.blur(cco);
    fireEvent.click(screen.getByRole("button", { name: "Enviar a nota" }));
    await waitFor(() => expect(api.mock.calls.some(c => c[0] === "/api/notas/envio/3/enviar")).toBe(true));
    const [, opcoes] = api.mock.calls.find(c => c[0] === "/api/notas/envio/3/enviar")!;
    expect(JSON.parse(opcoes.body).cco).toEqual(["oculto@exemplo.com"]);
  });

  it("ao concluir o envio embutido, avisa a página com a hora (B-06, 10/10/2026)", async () => {
    api.mockImplementation((caminho: string) => Promise.resolve(caminho === "/api/notas/envio/3" ? det : {}));
    const aoConcluir = vi.fn();
    render(<EnviarNota protocoloId={3} podeEditar embutido={{ aoConcluir, aoTrocar: () => {} }} />);
    fireEvent.click(await screen.findByRole("button", { name: "Enviar a nota" }));
    await waitFor(() => expect(aoConcluir).toHaveBeenCalled());
    expect(aoConcluir.mock.calls[0][0]).toMatch(/^Nota enviada às \d{2}:\d{2}\.$/);
  });

  it("diretoria vê o que vai no envio, sem e-mail, anexos nem registro por fora (B-09, 10/10/2026)", async () => {
    api.mockImplementation((caminho: string) => Promise.resolve(caminho === "/api/notas/envio/3" ? det : {}));
    render(<EnviarNota protocoloId={3} podeEditar={false} embutido={{ aoConcluir: () => {}, aoTrocar: () => {} }} />);
    expect(await screen.findByText(/Seu perfil só consulta esta tela/)).toBeTruthy();
    expect(screen.getByText("O que vai no e-mail")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Enviar a nota" })).toBeNull();
    expect(screen.queryByText("Anexar outro documento")).toBeNull();
    expect(screen.queryByText("Registrar envio feito por fora")).toBeNull();
    expect(screen.queryByRole("button", { name: /Juntar outra nota/ })).toBeNull();
  });

  it("a meta do topo leva o texto inteiro no title, porque corta com reticências no celular (issue #13)", async () => {
    api.mockImplementation((caminho: string) => Promise.resolve(caminho === "/api/notas/envio/3" ? det : {}));
    const { container } = render(<EnviarNota protocoloId={3} podeEditar />);
    await screen.findByRole("button", { name: "Enviar a nota" });
    const meta = container.querySelector(".topbar__linha > .topbar__meta")!;
    expect(meta.getAttribute("title")).toBe(meta.textContent);
    expect(meta.getAttribute("title")).toContain("SINFRA · SUEF II");
  });

  // issue #11: com documento faltando o Enviar não fica apagado; o clique diz o que falta, junto da justificativa
  it("sem a justificativa pedida, o clique em Enviar a nota mostra o erro no campo e não envia", async () => {
    api.mockImplementation((caminho: string) => Promise.resolve(caminho === "/api/notas/envio/3"
      ? { ...det, justificativa_obrigatoria: true, pendencias: ["Falta a certidão federal"] } : {}));
    render(<EnviarNota protocoloId={3} podeEditar embutido={{ aoConcluir: () => {}, aoTrocar: () => {} }} />);
    const botao = await screen.findByRole("button", { name: "Enviar a nota" }) as HTMLButtonElement;
    expect(botao.disabled).toBe(false);
    fireEvent.click(botao);
    const campo = screen.getByLabelText("Justificativa para enviar sem o documento");
    expect(campo.getAttribute("aria-invalid")).toBe("true");
    expect(document.getElementById(campo.getAttribute("aria-describedby") ?? "")?.textContent).toContain("pelo menos 10 caracteres");
    expect(api.mock.calls.some(c => c[0] === "/api/notas/envio/3/enviar")).toBe(false);
    fireEvent.change(campo, { target: { value: "DP confirmou o envio direto" } });
    fireEvent.click(botao);
    await waitFor(() => expect(api.mock.calls.some(c => c[0] === "/api/notas/envio/3/enviar")).toBe(true));
  });

  it("a ajuda do link diz que só vale o OneDrive ou SharePoint da Lotufo (testes de quebra 10/10, A-13)", async () => {
    api.mockImplementation((caminho: string) => Promise.resolve(caminho === "/api/notas/envio/3" ? det : {}));
    render(<EnviarNota protocoloId={3} podeEditar embutido={{ aoConcluir: () => {}, aoTrocar: () => {} }} />);
    expect(await screen.findByText(/Cole um link do OneDrive ou SharePoint da Lotufo; link de outro endereço é recusado\./))
      .toBeTruthy();
    // issue #118: o endereço permitido é do servidor (DASH_SHAREPOINT_HOSTS); a tela não traz o tenant da empresa
    expect(document.body.innerHTML).not.toMatch(/[a-z0-9-]+(-my)?\.sharepoint\.com/i);
  });
});
