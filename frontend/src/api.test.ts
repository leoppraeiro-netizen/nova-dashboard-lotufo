import { afterEach, describe, expect, it, vi } from "vitest";
import { api, ApiErro } from "./api";

function responde(status: number, corpo: unknown) {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(corpo), { status })));
}

describe("api: detail do servidor", () => {
  afterEach(() => { vi.unstubAllGlobals(); });

  it("detail estruturado (409 de envio reservado): mensagem na tela e corpo cru para a decisao", async () => {
    const detail = { mensagem: "Este envio está em andamento ou foi interrompido.", codigo: "ENVIO_RESERVADO" };
    responde(409, { detail });
    const erro = (await api("/api/protocolos/envio", { method: "POST" }).catch(e => e)) as ApiErro;
    expect(erro).toBeInstanceOf(ApiErro);
    expect(erro.status).toBe(409);
    expect(erro.message).toBe(detail.mensagem);
    expect(erro.corpo).toEqual(detail);
  });

  it("403 de permissão vira frase para quem só consulta (B-09, 10/10/2026)", async () => {
    responde(403, { detail: "Permissão necessária: editar_cadastros" });
    const erro = (await api("/api/notas/envio/iniciar", { method: "POST" }).catch(e => e)) as ApiErro;
    expect(erro.status).toBe(403);
    expect(erro.message).toBe("Seu perfil só consulta esta tela: a ação é da engenharia ou da administração.");
  });

  it("detail texto continua como antes", async () => {
    responde(422, { detail: "Informe ao menos um destinatário" });
    const erro = (await api("/api/x").catch(e => e)) as ApiErro;
    expect(erro.message).toBe("Informe ao menos um destinatário");
  });
});
