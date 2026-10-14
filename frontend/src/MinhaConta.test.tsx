import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import MinhaConta from "./MinhaConta";

// vi.mock e' icado para o topo do arquivo: a funcao falsa precisa nascer em vi.hoisted para
// existir quando a fabrica do mock rodar.
const { api } = vi.hoisted(() => ({ api: vi.fn() }));
vi.mock("./api", () => ({ api }));

const NENHUM = { estado: "nenhum", user_code: null, verification_uri: null };
const ENG = { id: 2, nome: "Maria", email: "maria@lotufo.com", perfil: "engenharia" };

describe("MinhaConta", () => {
  afterEach(() => { cleanup(); api.mockReset(); });

  it("mostra que a conta não está conectada e, ao conectar, o código para digitar", async () => {
    api.mockResolvedValueOnce({ configurado: true, conectado: false, login: NENHUM });
    api.mockResolvedValueOnce({ configurado: true, conectado: false, login: {
      estado: "aguardando", user_code: "ABCD-1234", verification_uri: "https://microsoft.com/devicelogin" } });
    render(<MinhaConta usuario={ENG} />);
    expect(await screen.findByText("Não conectada")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Conectar minha conta Microsoft" }));
    expect(await screen.findByText("ABCD-1234")).toBeTruthy();
  });

  it("conectada, permite mandar o e-mail de teste e mostra para onde foi", async () => {
    api.mockResolvedValueOnce({ configurado: true, conectado: true, login: NENHUM });
    api.mockResolvedValueOnce({ envio_id: 7, remetente: "engenheira.obra@exemplo.com.br" });
    render(<MinhaConta usuario={ENG} />);
    fireEvent.click(await screen.findByRole("button", { name: "Enviar e-mail de teste" }));
    await waitFor(() => expect(screen.getByText(/engenheira\.obra@exemplo\.com\.br/)).toBeTruthy());
  });

  // issue #28: remover a assinatura pede confirmação antes do DELETE
  it("Remover a assinatura pede confirmação; Cancelar não apaga", async () => {
    api.mockResolvedValue({ configurado: true, conectado: true, login: NENHUM, assinatura: true });
    render(<MinhaConta usuario={ENG} />);
    fireEvent.click(await screen.findByRole("button", { name: "Remover a assinatura" }));
    fireEvent.click(screen.getByRole("button", { name: "Cancelar" }));
    expect(api).not.toHaveBeenCalledWith("/api/correio/assinatura", expect.objectContaining({ method: "DELETE" }));
    fireEvent.click(screen.getByRole("button", { name: "Remover a assinatura" }));
    fireEvent.click(screen.getByRole("button", { name: /Confirmar a remoção:\s*a assinatura/ }));
    await waitFor(() => expect(api).toHaveBeenCalledWith("/api/correio/assinatura", { method: "DELETE" }));
  });
});

// A-05/B-10 (10/10/2026): cada um troca a própria senha
describe("MinhaConta › Trocar senha", () => {
  afterEach(() => { cleanup(); api.mockReset(); });

  function preencher(atual: string, nova: string, confirmar: string) {
    fireEvent.change(screen.getByLabelText("Senha atual"), { target: { value: atual } });
    fireEvent.change(screen.getByLabelText(/^Senha nova/), { target: { value: nova } });
    fireEvent.change(screen.getByLabelText("Confirmar a senha nova"), { target: { value: confirmar } });
    fireEvent.click(screen.getByRole("button", { name: "Trocar senha" }));
  }

  it("manda a atual e a nova para /api/auth/senha", async () => {
    api.mockImplementation(async (url: string) =>
      url === "/api/correio/status" ? { configurado: true, conectado: false, login: NENHUM } : { ok: true });
    render(<MinhaConta usuario={ENG} />);
    await screen.findByText("Não conectada");
    preencher("senha-velha-123", "senha-nova-456", "senha-nova-456");
    expect(api).toHaveBeenCalledWith("/api/auth/senha", { method: "POST",
      body: JSON.stringify({ senha_atual: "senha-velha-123", senha_nova: "senha-nova-456" }) });
    expect(await screen.findByText(/Senha trocada/)).toBeTruthy();
  });

  it("confirmação diferente não manda nada; erro do servidor aparece na tela", async () => {
    api.mockImplementation(async (url: string) => {
      if (url === "/api/correio/status") return { configurado: true, conectado: false, login: NENHUM };
      throw new Error("Senha atual não confere");
    });
    render(<MinhaConta usuario={ENG} />);
    await screen.findByText("Não conectada");
    preencher("senha-velha-123", "senha-nova-456", "outra-coisa-789");
    expect(api).not.toHaveBeenCalledWith("/api/auth/senha", expect.anything());
    expect(screen.getByText(/não bate/)).toBeTruthy();
    preencher("senha-errada-00", "senha-nova-456", "senha-nova-456");
    expect(await screen.findByText("Senha atual não confere")).toBeTruthy();
  });
});

// B-09 (10/10/2026): a diretoria nao manda e-mail pela dashboard; ve o e-mail de login e troca a senha
// gate Sol S6: o usuario no formato da resposta de /api/auth/eu, que e' o que o App guarda e passa adiante
const EU_DIRETORIA = { id: 3, nome: "Diretor", email: "dir@lotufo.com", perfil: "diretoria", csrf: "token" };

describe("MinhaConta › diretoria", () => {
  afterEach(() => { cleanup(); api.mockReset(); });

  it("sem e-mail, a frase do e-mail de login não aparece (gate Sol S6)", () => {
    render(<MinhaConta usuario={{ ...EU_DIRETORIA, email: "" }} />);
    expect(screen.queryByText(/Você entra com o e-mail/)).toBeNull();
    expect(screen.getByRole("button", { name: "Trocar senha" })).toBeTruthy();
  });

  it("mostra o e-mail de login e a troca de senha, sem conta Microsoft nem assinatura", async () => {
    api.mockResolvedValue({ configurado: true, conectado: false, login: NENHUM, assinatura: false });
    render(<MinhaConta usuario={EU_DIRETORIA} />);
    expect(await screen.findByText("dir@lotufo.com")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Trocar senha" })).toBeTruthy();
    expect(screen.queryByText("Conta Microsoft")).toBeNull();
    expect(screen.queryByText("Assinatura de e-mail")).toBeNull();
  });
});
