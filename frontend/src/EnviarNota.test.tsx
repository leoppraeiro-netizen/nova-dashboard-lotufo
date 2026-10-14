import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiErro } from "./api";
import EnviarNota from "./EnviarNota";
import { EnvioDaMedicao } from "./Etapas";

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
    expect(await screen.findByText(/Cole um link do OneDrive ou SharePoint da Lotufo; link de outro endereço é recusado\./))
      .toBeTruthy();
    // issue #118: o endereço permitido é do servidor (DASH_SHAREPOINT_HOSTS); a tela não traz o tenant da empresa
    expect(document.body.innerHTML).not.toMatch(/[a-z0-9-]+(-my)?\.sharepoint\.com/i);
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
        if (caminho === "/api/notas/envio/3/enviar") { atual = comFrc([NF, FRC]); return Promise.reject(new ApiErro(422, RECUSA, { codigo: "ANEXOS_MUDARAM", mensagem: RECUSA })); }
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

    // gate Sol S2 (PR #141): 409 de envio em andamento (a outra aba enviou) nao relê o envio nem apaga o texto editado
    it("outro erro de envio mantém o e-mail editado e não relê o envio", async () => {
      api.mockImplementation((caminho: string) => {
        if (caminho === "/api/notas/envio/3") return Promise.resolve(comFrc([NF]));
        if (caminho === "/api/notas/envio/3/enviar") return Promise.reject(new ApiErro(409, "Envio em andamento por Admin.",
          { codigo: "ENVIO_RESERVADO", mensagem: "Envio em andamento por Admin.", reservado_em: null, reservado_por_nome: "Admin", liberavel_a_partir_de: null }));
        return Promise.resolve({});
      });
      render(<EnviarNota protocoloId={3} podeEditar embutido={{ aoConcluir: () => {}, aoTrocar: () => {} }} />);
      const corpo = await screen.findByLabelText("Corpo da mensagem") as HTMLTextAreaElement;
      fireEvent.change(corpo, { target: { value: "Bom dia. Com a observação do fiscal." } });
      fireEvent.click(screen.getByRole("button", { name: "Enviar a nota" }));
      expect(await screen.findByText("Envio em andamento por Admin.")).toBeTruthy();
      expect(api.mock.calls.filter(c => c[0] === "/api/notas/envio/3")).toHaveLength(1);
      expect((screen.getByLabelText("Corpo da mensagem") as HTMLTextAreaElement).value).toBe("Bom dia. Com a observação do fiscal.");
    });

    // gate Sol S3 (PR #141): a conferência do servidor não depende da ordem; a tela também não
    it("os mesmos anexos em outra ordem não refazem a prévia nem mostram o aviso", async () => {
      let atual = comFrc([NF, FRC]);
      api.mockImplementation((caminho: string) => Promise.resolve(caminho === "/api/notas/envio/3" ? atual : {}));
      const props = { protocoloId: 3, podeEditar: true, embutido: { aoConcluir: () => {}, aoTrocar: () => {} } };
      const { rerender } = render(<EnviarNota {...props} versao={0} />);
      const assunto = await screen.findByLabelText("Assunto") as HTMLInputElement;
      fireEvent.change(assunto, { target: { value: "Assunto editado" } });
      atual = comFrc([FRC, NF]);
      rerender(<EnviarNota {...props} versao={1} />);
      await waitFor(() => expect(api.mock.calls.filter(c => c[0] === "/api/notas/envio/3")).toHaveLength(2));
      await waitFor(() => expect(within(screen.getByRole("list", { name: "Anexos" })).getAllByRole("listitem")[0].textContent).toContain("FRC 77.pdf"));
      expect((screen.getByLabelText("Assunto") as HTMLInputElement).value).toBe("Assunto editado");
      expect(screen.queryByText(AVISO)).toBeNull();
    });
  });

  // issue #148: a FRC aparece em "O que vai no e-mail" com a situação certa
  describe("FRC em O que vai no e-mail", () => {
    const itemFrc = (extra: object) => ({ ...det, envio: { ...det.envio, itens: [
      { chave: "frc:631", rotulo: "FRC assinada", medicao_id: 631, ...extra }] } });
    const secao = () => screen.getByRole("region", { name: "O que vai no e-mail" });

    it("gerada e sem a assinada: diz que falta a assinada e oferece baixar a gerada", async () => {
      api.mockImplementation((caminho: string) => Promise.resolve(caminho === "/api/notas/envio/3" ? itemFrc({
        estado: "falta", acao: "anexar_frc", frc_gerada: 77,
        detalhe: "Falta a assinada: baixe a FRC gerada, assine no DocuSign e anexe aqui" }) : {}));
      render(<EnviarNota protocoloId={3} podeEditar embutido={{ aoConcluir: () => {}, aoTrocar: () => {} }} />);
      await screen.findByText("O que vai no e-mail");
      expect(within(secao()).getByText(/Falta a assinada/)).toBeTruthy();
      const link = within(secao()).getByRole("link", { name: "Baixar a FRC gerada (nº 77)" });
      expect(link.getAttribute("href")).toBe("/api/medicoes/631/frc/pdf");
      expect(within(secao()).getByLabelText("Anexar FRC assinada")).toBeTruthy();
    });

    it("quem só consulta também vê o link da FRC gerada", async () => {
      api.mockImplementation((caminho: string) => Promise.resolve(caminho === "/api/notas/envio/3" ? itemFrc({
        estado: "falta", acao: "anexar_frc", frc_gerada: 77, detalhe: "Falta a assinada" }) : {}));
      render(<EnviarNota protocoloId={3} podeEditar={false} embutido={{ aoConcluir: () => {}, aoTrocar: () => {} }} />);
      await screen.findByText("O que vai no e-mail");
      expect(within(secao()).getByRole("link", { name: "Baixar a FRC gerada (nº 77)" })).toBeTruthy();
    });

    it("assinada anexada: mostra pronta, sem o link da gerada", async () => {
      api.mockImplementation((caminho: string) => Promise.resolve(caminho === "/api/notas/envio/3" ? itemFrc({
        estado: "ok", acao: null, frc_gerada: 77, detalhe: "Assinada anexada · FRC 77 assinada.pdf" }) : {}));
      render(<EnviarNota protocoloId={3} podeEditar embutido={{ aoConcluir: () => {}, aoTrocar: () => {} }} />);
      await screen.findByText("O que vai no e-mail");
      expect(within(secao()).getByText("Assinada anexada · FRC 77 assinada.pdf")).toBeTruthy();
      expect(within(secao()).getByTitle("Pronto")).toBeTruthy();
      expect(within(secao()).queryByRole("link", { name: /Baixar a FRC gerada/ })).toBeNull();
    });
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

// issue #172: na pagina da medicao, o registro por fora vem antes de "Começar o envio", que montaria um rascunho a toa
describe("Etapa do envio na página da medição", () => {
  afterEach(() => { cleanup(); api.mockReset(); apiForm.mockReset(); });
  const lista = { envios: [{ ...det.envio, chave: "c20:m631", medicao_ids: [631], descricao: "7ª medição", protocolo_id: null,
    irmas: [{ medicao_id: 632, titulo: "Reajuste da 7ª Medição", tipo: "reajuste" }] }], contadores: { Todas: 1 } };

  it("o link aparece antes de Começar o envio e registra a medição e a irmã sem abrir o envio", async () => {
    api.mockResolvedValue(lista);
    apiForm.mockResolvedValue({ ok: true });
    const aoMudar = vi.fn();
    render(<EnvioDaMedicao medicaoId={631} podeEditar aoMudar={aoMudar} />);
    expect(await screen.findByRole("button", { name: "Começar o envio" })).toBeTruthy();
    fireEvent.click(screen.getByText("Registrar envio feito por fora"));
    expect((screen.getByLabelText("Incluir também o Reajuste da 7ª Medição (saiu no mesmo e-mail)") as HTMLInputElement).checked).toBe(true);
    fireEvent.change(screen.getByLabelText("Observação"), { target: { value: "Pelo Outlook" } });
    fireEvent.click(screen.getByRole("button", { name: "Registrar" }));
    await waitFor(() => expect(aoMudar).toHaveBeenCalledWith("Envio registrado: a nota foi para Aguardando pagamento."));
    expect((apiForm.mock.calls[0][1] as FormData).getAll("medicao_ids")).toEqual(["631", "632"]);
    expect(api.mock.calls.some(c => c[0] === "/api/notas/envio/iniciar")).toBe(false);
  });

  it("quem só consulta continua sem o link", async () => {
    api.mockResolvedValue(lista);
    render(<EnvioDaMedicao medicaoId={631} podeEditar={false} aoMudar={() => {}} />);
    expect(await screen.findByText(/7ª medição/)).toBeTruthy();
    expect(screen.queryByText("Registrar envio feito por fora")).toBeNull();
  });

  it("envio bloqueado não oferece o registro por fora", async () => {
    api.mockResolvedValue({ ...lista, envios: [{ ...lista.envios[0], situacao: "bloqueado", aviso: "Federal vencida" }] });
    render(<EnvioDaMedicao medicaoId={631} podeEditar aoMudar={() => {}} />);
    expect(await screen.findByRole("button", { name: "Começar o envio" })).toBeTruthy();
    expect(screen.queryByText("Registrar envio feito por fora")).toBeNull();
  });
});
