import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { afterEach, describe, expect, it } from "vitest";
import CampoValor from "./CampoValor";
import { coladoParaBrl, digitosParaBrl } from "./formato";

// Campo de valor da issue #190: digitos pela direita, 2 casas, sem float.
function Campo({ inicial = "" }: { inicial?: string }) {
  const [v, setV] = useState(inicial);
  return <><label htmlFor="v">Valor</label><CampoValor id="v" name="v" value={v} onChange={setV} /></>;
}

const campo = () => screen.getByLabelText("Valor") as HTMLInputElement;
// teclar: cada digito entra no fim do que o campo mostra (como o navegador faz com o cursor no fim)
const digitar = (texto: string) => { for (const c of texto) fireEvent.change(campo(), { target: { value: campo().value + c } }); };
const apagar = () => fireEvent.change(campo(), { target: { value: campo().value.slice(0, -1) } });
const colar = (texto: string) => fireEvent.paste(campo(), { clipboardData: { getData: () => texto } });

describe("CampoValor", () => {
  afterEach(cleanup);

  it("os dígitos entram pela direita: 1, 12, 1234, 5000000", () => {
    render(<Campo />);
    digitar("1"); expect(campo().value).toBe("0,01");
    digitar("2"); expect(campo().value).toBe("0,12");
    digitar("34"); expect(campo().value).toBe("12,34");
    fireEvent.change(campo(), { target: { value: "" } });
    digitar("5000000"); expect(campo().value).toBe("50.000,00");
  });

  it("apagar tira o último dígito, até o campo ficar vazio", () => {
    render(<Campo />);
    digitar("12345");
    apagar(); expect(campo().value).toBe("12,34");
    apagar(); expect(campo().value).toBe("1,23");
    apagar(); expect(campo().value).toBe("0,12");
    apagar(); expect(campo().value).toBe("0,01");
    apagar(); expect(campo().value).toBe("");
  });

  it("colar 50.000,00, 50000,5 e 50000 lê em reais", () => {
    render(<Campo />);
    colar("50.000,00"); expect(campo().value).toBe("50.000,00");
    colar("50000,5"); expect(campo().value).toBe("50.000,50");
    colar("50000"); expect(campo().value).toBe("50.000,00");
    colar("R$ 1.234.567,89"); expect(campo().value).toBe("1.234.567,89");
  });

  it("colar formato que o servidor recusaria não muda o campo", () => {
    render(<Campo inicial="10,00" />);
    colar("1234.56"); expect(campo().value).toBe("10,00");
    colar("12,345"); expect(campo().value).toBe("10,00");
    colar("abc"); expect(campo().value).toBe("10,00");
  });

  it("vazio continua vazio (vale zero) e letras não entram", () => {
    render(<Campo />);
    expect(campo().value).toBe("");
    fireEvent.change(campo(), { target: { value: "a" } });
    expect(campo().value).toBe("");
  });

  it("nenhum arredondamento: centavo ímpar e valor grande no teto do servidor", () => {
    render(<Campo />);
    digitar("9999999999999"); expect(campo().value).toBe("99.999.999.999,99");
    digitar("9"); expect(campo().value).toBe("99.999.999.999,99");   // acima do teto: o digito nao entra
    fireEvent.change(campo(), { target: { value: "" } });
    digitar("123456789"); expect(campo().value).toBe("1.234.567,89");
  });
});

describe("digitosParaBrl e coladoParaBrl", () => {
  it("convertem em texto, sem float", () => {
    expect(digitosParaBrl("")).toBe("");
    expect(digitosParaBrl("007")).toBe("0,07");
    expect(digitosParaBrl("100")).toBe("1,00");
    expect(digitosParaBrl("123456789012")).toBe("1.234.567.890,12");
    expect(coladoParaBrl("0,01")).toBe("0,01");
    expect(coladoParaBrl("0")).toBe("0,00");
    expect(coladoParaBrl("100000000000")).toBeNull();   // R$ 100 bilhoes: acima do teto
  });
});
