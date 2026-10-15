import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import CampoCompetencia, { competenciaDaTela, competenciaParaTela, mascaraCompetencia } from "./CampoCompetencia";

afterEach(cleanup);

function Caixa({ inicial = "", aoMudar = () => {}, aoEnviar = () => {} }:
  { inicial?: string; aoMudar?: (v: string) => void; aoEnviar?: () => void }) {
  const [v, setV] = useState(inicial);
  return (
    <form onSubmit={e => { e.preventDefault(); aoEnviar(); }}>
      <label htmlFor="c">Competência</label>
      <CampoCompetencia id="c" value={v} onChange={x => { setV(x); aoMudar(x); }} />
      <button type="submit">Enviar</button>
    </form>
  );
}
const campo = () => screen.getByLabelText("Competência") as HTMLInputElement;
const digitar = (t: string) => fireEvent.change(campo(), { target: { value: t } });

describe("CampoCompetencia", () => {
  it("máscara: só números, a barra entra sozinha", () => {
    const aoMudar = vi.fn();
    render(<Caixa aoMudar={aoMudar} />);
    digitar("092026");
    expect(campo().value).toBe("09/2026");
    expect(aoMudar).toHaveBeenLastCalledWith("2026-09");
  });

  it("aceita 9/2026 e cola 09/2026 e 2026-09", () => {
    render(<Caixa />);
    digitar("9/2026");
    expect(campo().value).toBe("09/2026");
    digitar("2026-09");
    expect(campo().value).toBe("09/2026");
    digitar("09/2026");
    expect(campo().value).toBe("09/2026");
  });

  it("teclado numérico e placeholder", () => {
    render(<Caixa />);
    expect(campo().getAttribute("inputmode")).toBe("numeric");
    expect(campo().placeholder).toBe("MM/AAAA");
  });

  it("valor da API aparece como MM/AAAA", () => {
    render(<Caixa inicial="2026-09" />);
    expect(campo().value).toBe("09/2026");
  });

  it("mês 13 é recusado: erro em português, nada vai e o formulário não envia", () => {
    const aoMudar = vi.fn();
    const aoEnviar = vi.fn();
    render(<Caixa aoMudar={aoMudar} aoEnviar={aoEnviar} />);
    digitar("132026");
    expect(aoMudar).toHaveBeenLastCalledWith("");
    fireEvent.click(screen.getByRole("button", { name: "Enviar" }));
    expect(screen.getByRole("alert").textContent).toContain("Competência no formato MM/AAAA, ex.: 09/2026");
    expect(aoEnviar).not.toHaveBeenCalled();
  });

  it("ano incompleto não envia; completo envia", () => {
    const aoEnviar = vi.fn();
    render(<Caixa aoEnviar={aoEnviar} />);
    digitar("09/20");
    fireEvent.click(screen.getByRole("button", { name: "Enviar" }));
    expect(aoEnviar).not.toHaveBeenCalled();
    digitar("092026");
    fireEvent.click(screen.getByRole("button", { name: "Enviar" }));
    expect(aoEnviar).toHaveBeenCalledTimes(1);
  });

  it("conversão ida e volta", () => {
    expect(competenciaParaTela("2026-09")).toBe("09/2026");
    expect(competenciaDaTela("09/2026")).toBe("2026-09");
    expect(competenciaDaTela("00/2026")).toBe("");
    expect(mascaraCompetencia("0")).toBe("0");
  });
});
