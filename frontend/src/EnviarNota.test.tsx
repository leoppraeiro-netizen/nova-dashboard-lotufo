import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import EnviarNota from "./EnviarNota";

const { api } = vi.hoisted(() => ({ api: vi.fn() }));
vi.mock("./api", async (original) => ({ ...(await original<typeof import("./api")>()), api, apiForm: vi.fn() }));

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
    expect(await screen.findByText(/Cole um link do OneDrive ou SharePoint da Lotufo \(lotufoengmt-my\.sharepoint\.com ou lotufoengmt\.sharepoint\.com\)/))
      .toBeTruthy();
  });

  it("remover documento complementar ou link pede confirmação antes do pedido (issue #28)", async () => {
    const comExtras = { ...det, extras: [{ id: 41, nome: "justificativa.pdf", tamanho: 4096 }],
      previa: { ...det.previa, links: [{ id: 5, nome: "relatorios.zip", url: "https://lotufoengmt.sharepoint.com/x" }] } };
    api.mockImplementation((caminho: string) => Promise.resolve(caminho === "/api/notas/envio/3" ? comExtras : {}));
    render(<EnviarNota protocoloId={3} podeEditar embutido={{ aoConcluir: () => {}, aoTrocar: () => {} }} />);
    fireEvent.click(await screen.findByRole("button", { name: "Remover justificativa.pdf" }));
    fireEvent.click(screen.getByRole("button", { name: "Remover o link relatorios.zip" }));
    expect(api.mock.calls.some(c => String(c[0]).endsWith("/remover"))).toBe(false);
    fireEvent.click(screen.getByRole("button", { name: /Confirmar a remoção:\s*justificativa\.pdf/ }));
    await waitFor(() => expect(api).toHaveBeenCalledWith("/api/protocolos/3/pecas/41/remover", expect.objectContaining({ method: "POST" })));
    fireEvent.click(screen.getByRole("button", { name: /Confirmar a remoção:\s*o link relatorios\.zip/ }));
    await waitFor(() => expect(api).toHaveBeenCalledWith("/api/protocolos/3/links/5/remover", expect.objectContaining({ method: "POST" })));
  });

  it("com o e-mail editado, a confirmação de remover avisa que o texto será montado de novo (revisor, #28)", async () => {
    const comExtras = { ...det, extras: [{ id: 41, nome: "justificativa.pdf", tamanho: 4096 }] };
    api.mockImplementation((caminho: string) => Promise.resolve(caminho === "/api/notas/envio/3" ? comExtras : {}));
    render(<EnviarNota protocoloId={3} podeEditar embutido={{ aoConcluir: () => {}, aoTrocar: () => {} }} />);
    fireEvent.click(await screen.findByRole("button", { name: "Remover justificativa.pdf" }));
    expect(screen.queryByText(/será montado de novo/)).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Cancelar" }));
    fireEvent.change(screen.getByLabelText("Corpo da mensagem"), { target: { value: "Bom dia, texto meu." } });
    fireEvent.click(screen.getByRole("button", { name: "Remover justificativa.pdf" }));
    expect(screen.getByText("O texto do e-mail que você editou será montado de novo.")).toBeTruthy();
  });

  it("a lixeira do e-mail editado pergunta antes de sair da tela (issue #27)", async () => {
    api.mockImplementation((caminho: string) => Promise.resolve(caminho === "/api/notas/envio/3" ? det : {}));
    window.history.replaceState(null, "", "/notas/envio/3");
    const confirmar = vi.spyOn(window, "confirm").mockReturnValue(false);
    render(<EnviarNota protocoloId={3} podeEditar />);
    fireEvent.change(await screen.findByLabelText("Assunto"), { target: { value: "Outro" } });
    // #28: a lixeira pergunta na própria janela do e-mail; confirmado, sai sem a segunda pergunta do navegador
    fireEvent.click(screen.getByRole("button", { name: "Descartar" }));
    expect(window.location.pathname).toBe("/notas/envio/3");
    fireEvent.click(screen.getByRole("button", { name: "Continuar escrevendo" }));
    expect(window.location.pathname).toBe("/notas/envio/3");
    fireEvent.click(screen.getByRole("button", { name: "Descartar" }));
    fireEvent.click(screen.getByRole("button", { name: "Descartar o e-mail" }));
    expect(confirmar).not.toHaveBeenCalled();
    expect(window.location.pathname).toBe("/medicoes/enviar-nota");
    vi.restoreAllMocks();
  });
});
