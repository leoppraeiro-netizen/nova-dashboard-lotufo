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

// rodada 1 de correcao da PR #193
describe("CampoValor: cursor, zero, colar inválido e ajuda", () => {
  afterEach(cleanup);

  it("S1: com o cursor no início, o dígito entra no fim e o cursor volta ao fim", () => {
    render(<Campo inicial="12,34" />);
    campo().focus();
    campo().setSelectionRange(0, 0);
    fireEvent.change(campo(), { target: { value: "512,34" } });    // o 5 digitado antes do 1
    expect(campo().value).toBe("123,45");
    expect(campo().selectionStart).toBe(6);
    fireEvent.change(campo(), { target: { value: "12,45" } });     // apagou o 3 do meio: sai o ultimo digito
    expect(campo().value).toBe("12,34");
    fireEvent.change(campo(), { target: { value: "1234" } });      // apagou a virgula: sai o ultimo digito
    expect(campo().value).toBe("1,23");
  });

  it("S1: tudo selecionado e um dígito digitado começa do zero", () => {
    render(<Campo inicial="12,34" />);
    fireEvent.change(campo(), { target: { value: "7" } });
    expect(campo().value).toBe("0,07");
  });

  it("S3: digitar 0 ou 00 mostra 0,00 (glosa total); apagar 0,00 volta a vazio", () => {
    render(<Campo />);
    digitar("0"); expect(campo().value).toBe("0,00");
    digitar("0"); expect(campo().value).toBe("0,00");
    digitar("5"); expect(campo().value).toBe("0,05");
    fireEvent.change(campo(), { target: { value: "" } });
    digitar("00"); expect(campo().value).toBe("0,00");
    apagar(); expect(campo().value).toBe("");
  });

  it("R1: colar fora do formato avisa no campo; o próximo valor certo tira o aviso", () => {
    render(<Campo inicial="10,00" />);
    colar("8900000.00");
    expect(campo().value).toBe("10,00");
    expect(campo().getAttribute("aria-invalid")).toBe("true");
    const erro = screen.getByRole("alert");
    expect(erro.textContent).toContain("Valor colado em formato inválido: use vírgula nos centavos, ex.: 1.234,56");
    expect(campo().getAttribute("aria-describedby")).toContain(erro.id);
    colar("89.000,00");
    expect(campo().value).toBe("89.000,00");
    expect(screen.queryByRole("alert")).toBeNull();
    expect(campo().getAttribute("aria-invalid")).toBeNull();
  });

  it("R3: vários caracteres de uma vez, sem evento de colar, são lidos em reais", () => {
    render(<Campo />);
    fireEvent.change(campo(), { target: { value: "50000" } });
    expect(campo().value).toBe("50.000,00");
    fireEvent.change(campo(), { target: { value: "8900000.00" } });
    expect(campo().value).toBe("50.000,00");
    expect(screen.getByRole("alert").textContent).toContain("formato inválido");
  });

  it("R2: a ajuda aparece e o campo aponta para ela; com ajudaId, usa a da tela", () => {
    render(<Campo />);
    const ajuda = document.getElementById(campo().getAttribute("aria-describedby") ?? "");
    expect(ajuda?.textContent).toBe("Digite só os números: os centavos e os pontos entram sozinhos.");
    cleanup();
    render(<><p id="fora">ajuda da tela</p><label htmlFor="w">W</label>
      <CampoValor id="w" name="w" value="" onChange={() => {}} ajudaId="fora" /></>);
    expect(screen.getByLabelText("W").getAttribute("aria-describedby")).toBe("fora");
    expect(screen.queryByText(/Digite só os números/)).toBeNull();
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
