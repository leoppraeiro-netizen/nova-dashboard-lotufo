import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import ComporEmail from "./ComporEmail";

const { api } = vi.hoisted(() => ({ api: vi.fn() }));
vi.mock("./api", () => ({ api, ApiErro: class ApiErro extends Error { status = 0; } }));

describe("ComporEmail", () => {
  afterEach(() => { cleanup(); api.mockReset(); });

  it("destinatario vira etiqueta pela sugestao ou pelo e-mail digitado e sai no envio", async () => {
    api.mockImplementation((caminho: string) => {
      if (caminho.startsWith("/api/correio/remetente")) return Promise.resolve({ remetente: "eu@lotufo.com" });
      if (caminho.includes("q=fat")) return Promise.resolve([{ nome: "Faturamento Exemplo", email: "faturamento@lotufo.com" }]);
      return Promise.resolve([]);
    });
    const aoEnviar = vi.fn();
    render(<ComporEmail ocupado={false} anexos={[{ nome: "ESPELHO.docx", tamanho: 28894 }]} aoEnviar={aoEnviar}
      aoDescartar={() => {}} inicial={{ para: [], copia: [], cco: [], assunto: "Emissão NF", corpo: "Bom dia." }} />);
    expect(await screen.findByText("De: eu@lotufo.com")).toBeTruthy();
    const para = screen.getByLabelText(/Para: digite/);
    fireEvent.change(para, { target: { value: "fat" } });
    fireEvent.mouseDown(await screen.findByText("Faturamento Exemplo"));
    expect(screen.getByTitle("faturamento@lotufo.com")).toBeTruthy();
    fireEvent.click(screen.getByText("Cco"));
    const cco = screen.getByLabelText(/Cco: digite/);
    fireEvent.change(cco, { target: { value: "oculto@lotufo.com" } });
    fireEvent.blur(cco);                       // digitou e foi direto ao Enviar: o endereco nao pode ficar para tras
    fireEvent.click(screen.getByRole("button", { name: "Enviar" }));
    await waitFor(() => expect(aoEnviar).toHaveBeenCalled());
    expect(aoEnviar.mock.calls[0][0]).toEqual({ para: ["faturamento@lotufo.com"], copia: [], cco: ["oculto@lotufo.com"],
      assunto: "Emissão NF", corpo: "Bom dia." });
  });

  // issue #11: o Enviar não fica apagado esperando o formulário valer; o clique diz o que falta, junto do campo
  it("Enviar fica clicável: sem destinatário ou sem assunto, o clique mostra o erro junto do campo", async () => {
    api.mockResolvedValue([]);
    const aoEnviar = vi.fn();
    render(<ComporEmail ocupado={false} anexos={[]} aoEnviar={aoEnviar} aoDescartar={() => {}}
      inicial={{ para: [], copia: [], cco: [], assunto: "", corpo: "Bom dia." }} />);
    const enviar = screen.getByRole("button", { name: "Enviar" }) as HTMLButtonElement;
    expect(enviar.disabled).toBe(false);
    fireEvent.click(enviar);
    const para = screen.getByLabelText(/Para: digite/);
    const erroPara = screen.getByText("Informe ao menos um destinatário.");
    expect(erroPara.getAttribute("role")).toBe("alert");
    expect(para.getAttribute("aria-invalid")).toBe("true");
    expect(document.getElementById(para.getAttribute("aria-describedby") ?? "")).toBe(erroPara);
    const assunto = screen.getByLabelText("Assunto");
    expect(document.getElementById(assunto.getAttribute("aria-describedby") ?? "")?.textContent).toContain("Informe o assunto.");
    expect(aoEnviar).not.toHaveBeenCalled();
    fireEvent.change(para, { target: { value: "fab@lotufo.com" } });
    fireEvent.blur(para);
    fireEvent.change(assunto, { target: { value: "Emissão NF" } });
    expect(screen.queryByText("Informe o assunto.")).toBeNull();
    fireEvent.click(enviar);
    await waitFor(() => expect(aoEnviar).toHaveBeenCalled());
  });

  it("o erro do campo que o ComporEmail não vê vem de quem o abriu (validarAntes)", () => {
    api.mockResolvedValue([]);
    const aoEnviar = vi.fn();
    const validarAntes = vi.fn(() => false);
    render(<ComporEmail ocupado={false} anexos={[]} aoEnviar={aoEnviar} aoDescartar={() => {}} validarAntes={validarAntes}
      inicial={{ para: ["a@lotufo.com"], copia: [], cco: [], assunto: "Assunto", corpo: "" }} />);
    fireEvent.click(screen.getByRole("button", { name: "Enviar" }));
    expect(validarAntes).toHaveBeenCalled();
    expect(aoEnviar).not.toHaveBeenCalled();
  });

  // issue #28: descartar o que a pessoa escreveu pede confirmação; sem nada mudado, não há o que perder
  it("Descartar com o e-mail mexido pede confirmação; sem mudança descarta direto", async () => {
    api.mockResolvedValue([]);
    const aoDescartar = vi.fn();
    const inicial = { para: [], copia: [], cco: [], assunto: "Emissão NF", corpo: "Bom dia." };
    render(<ComporEmail ocupado={false} anexos={[]} aoEnviar={() => {}} aoDescartar={aoDescartar} inicial={inicial} />);
    fireEvent.change(screen.getByLabelText("Corpo da mensagem"), { target: { value: "Bom dia, segue a nota." } });
    fireEvent.click(screen.getByRole("button", { name: "Descartar" }));
    expect(aoDescartar).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Continuar escrevendo" }));
    expect(aoDescartar).not.toHaveBeenCalled();
    expect(screen.getByLabelText("Corpo da mensagem")).toHaveProperty("value", "Bom dia, segue a nota.");
    fireEvent.click(screen.getByRole("button", { name: "Descartar" }));
    fireEvent.click(screen.getByRole("button", { name: "Descartar o e-mail" }));
    expect(aoDescartar).toHaveBeenCalledTimes(1);
    // quem abriu embutido não fecha a janela: o descarte volta o e-mail ao texto com que abriu (revisor, #28)
    expect(screen.getByLabelText("Corpo da mensagem")).toHaveProperty("value", "Bom dia.");
    cleanup();

    const aoDescartar2 = vi.fn();
    render(<ComporEmail ocupado={false} anexos={[]} aoEnviar={() => {}} aoDescartar={aoDescartar2} inicial={inicial} />);
    fireEvent.click(screen.getByRole("button", { name: "Descartar" }));
    expect(aoDescartar2).toHaveBeenCalledTimes(1);
  });
});
