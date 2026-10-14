import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiErro } from "./api";
import EnviarNota from "./EnviarNota";

const { api, apiForm } = vi.hoisted(() => ({ api: vi.fn(), apiForm: vi.fn() }));
vi.mock("./api", async (original) => ({ ...(await original<typeof import("./api")>()), api, apiForm }));

const det = {
  envio: { chave: "c20:m631-m632", contrato_id: 20, obra: "MT-401", orgao: "SINFRA", orgao_sub: "SUEF II", familia: "sinfra",
    grupo: "SINFRA", a_pedido: false, medicao_ids: [631, 632], descricao: "7ª medição + reajuste", notas: [],
    valor_centavos: 100, emitida_em: "2026-10-08", dias: 2, situacao: "pronto", aviso: null, protocolo_id: 3, itens: [] },
  familia: "sinfra", etapa: "nota", situacao_protocolo: "rascunho", carta: null,
  previa: { para: ["orgao@exemplo.com"], copia: [], assunto: "Notas", corpo: "Bom dia.", anexos: [], links: [] },
  bloqueio: null, pendencias: [], justificativa_obrigatoria: false, extras: [],
};

describe("Enviar a nota", () => {
  afterEach(() => { cleanup(); api.mockReset(); apiForm.mockReset(); });

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

  // issue #100: como no protocolo (PR #92), o Enviar leva os anexos que a prévia mostrou, para o servidor recusar se mudaram
  describe("anexos da prévia", () => {
    const NF = { nome: "NFS 2301.pdf", origem: "nota", tamanho: 10 };
    const FRC = { nome: "FRC 77.pdf", origem: "nota", tamanho: 20 };
    const AVISO = "A prévia foi refeita com os anexos de agora e o texto voltou ao padrão; confira antes de enviar.";
    const comFrc = (anexos: object[]) => ({ ...det,
      envio: { ...det.envio, itens: [{ chave: "frc", rotulo: "FRC assinada", estado: "falta", acao: "anexar_frc", medicao_id: 631 }] },
      previa: { ...det.previa, anexos } });

    it("o envio leva nome e tamanho dos anexos mostrados na prévia", async () => {
      api.mockImplementation((caminho: string) => Promise.resolve(caminho === "/api/notas/envio/3" ? comFrc([NF]) : {}));
      render(<EnviarNota protocoloId={3} podeEditar embutido={{ aoConcluir: () => {}, aoTrocar: () => {} }} />);
      fireEvent.click(await screen.findByRole("button", { name: "Enviar a nota" }));
      await waitFor(() => expect(api.mock.calls.some(c => c[0] === "/api/notas/envio/3/enviar")).toBe(true));
      const [, opcoes] = api.mock.calls.find(c => c[0] === "/api/notas/envio/3/enviar")!;
      expect(JSON.parse(opcoes.body).anexos).toEqual([{ nome: "NFS 2301.pdf", tamanho: 10 }]);
    });

    it("anexar a FRC com a prévia aberta fecha a prévia: o e-mail editado é refeito com os anexos novos", async () => {
      let atual = comFrc([NF]);
      api.mockImplementation((caminho: string) => Promise.resolve(caminho === "/api/notas/envio/3" ? atual : {}));
      apiForm.mockImplementation(async () => { atual = comFrc([NF, FRC]); return {}; });
      render(<EnviarNota protocoloId={3} podeEditar embutido={{ aoConcluir: () => {}, aoTrocar: () => {} }} />);
      const assunto = await screen.findByLabelText("Assunto") as HTMLInputElement;
      fireEvent.change(assunto, { target: { value: "Assunto editado antes do anexo" } });
      const pdf = new File(["%PDF-1.4"], "FRC 77.pdf", { type: "application/pdf" });
      fireEvent.change(screen.getByLabelText("Anexar FRC assinada"), { target: { files: [pdf] } });
      await waitFor(() => expect(within(screen.getByRole("list", { name: "Anexos" })).queryByText("FRC 77.pdf")).toBeTruthy());
      expect((screen.getByLabelText("Assunto") as HTMLInputElement).value).toBe("Notas");
      fireEvent.click(screen.getByRole("button", { name: "Enviar a nota" }));
      await waitFor(() => expect(api.mock.calls.some(c => c[0] === "/api/notas/envio/3/enviar")).toBe(true));
      const [, opcoes] = api.mock.calls.find(c => c[0] === "/api/notas/envio/3/enviar")!;
      expect(JSON.parse(opcoes.body).anexos).toEqual([{ nome: "NFS 2301.pdf", tamanho: 10 }, { nome: "FRC 77.pdf", tamanho: 20 }]);
    });

    it("envio recusado porque a FRC entrou em outra aba recarrega e mostra a prévia nova, com o aviso", async () => {
      let atual = comFrc([NF]);
      const RECUSA = "Os anexos mudaram depois da prévia: descarte esta prévia e abra outra para conferir o que vai no e-mail";
      api.mockImplementation((caminho: string) => {
        if (caminho === "/api/notas/envio/3") return Promise.resolve(atual);
        if (caminho === "/api/notas/envio/3/enviar") { atual = comFrc([NF, FRC]); return Promise.reject(new ApiErro(422, RECUSA)); }
        return Promise.resolve({});
      });
      render(<EnviarNota protocoloId={3} podeEditar embutido={{ aoConcluir: () => {}, aoTrocar: () => {} }} />);
      const corpo = await screen.findByLabelText("Corpo da mensagem") as HTMLTextAreaElement;
      fireEvent.change(corpo, { target: { value: "Bom dia. Segue com a observação do fiscal." } });
      expect(screen.queryByText(AVISO)).toBeNull();
      fireEvent.click(screen.getByRole("button", { name: "Enviar a nota" }));
      expect(await screen.findByText(RECUSA)).toBeTruthy();
      await waitFor(() => expect(within(screen.getByRole("list", { name: "Anexos" })).queryByText("FRC 77.pdf")).toBeTruthy());
      // revisor na PR #141: o texto editado se perdeu na prévia nova; a tela diz isso antes do próximo Enviar
      expect((screen.getByLabelText("Corpo da mensagem") as HTMLTextAreaElement).value).toBe("Bom dia.");
      expect(screen.getAllByRole("status").some(x => x.textContent?.endsWith(AVISO))).toBe(true);
    });

    it("documento novo da medição avisado pela página (versao) relê o envio e refaz a prévia com o aviso", async () => {
      let atual = comFrc([NF]);
      api.mockImplementation((caminho: string) => Promise.resolve(caminho === "/api/notas/envio/3" ? atual : {}));
      const props = { protocoloId: 3, podeEditar: true, embutido: { aoConcluir: () => {}, aoTrocar: () => {} } };
      const { rerender } = render(<EnviarNota {...props} versao={0} />);
      await screen.findByRole("button", { name: "Enviar a nota" });
      atual = comFrc([NF, FRC]);
      rerender(<EnviarNota {...props} versao={1} />);
      await waitFor(() => expect(within(screen.getByRole("list", { name: "Anexos" })).queryByText("FRC 77.pdf")).toBeTruthy());
      expect(screen.getByText(AVISO)).toBeTruthy();
    });
  });

  it("a lixeira do e-mail editado pergunta antes de sair da tela (issue #27)", async () => {
    api.mockImplementation((caminho: string) => Promise.resolve(caminho === "/api/notas/envio/3" ? det : {}));
    window.history.replaceState(null, "", "/notas/envio/3");
    const confirmar = vi.spyOn(window, "confirm").mockReturnValue(false);
    render(<EnviarNota protocoloId={3} podeEditar />);
    fireEvent.change(await screen.findByLabelText("Assunto"), { target: { value: "Outro" } });
    fireEvent.click(screen.getByRole("button", { name: /Descartar/ }));
    expect(confirmar).toHaveBeenCalledTimes(1);
    expect(window.location.pathname).toBe("/notas/envio/3");
    vi.restoreAllMocks();
  });
});
