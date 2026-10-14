import { describe, expect, it } from "vitest";
import { motivosDaLinha, obrasComProblema, porFarol, type Farol, type Motivo, type ObraCarteira } from "./carteira";

const o = (seq: number, farol: Farol): ObraCarteira => ({ contrato_id: 100 + seq, seq, obra: `Obra ${seq}`, farol });
const m = (texto: string): Motivo => ({ tipo: "pagamento_atrasado", nivel: "acao", dias: 60, valor_centavos: null, texto });

describe("carteira", () => {
  const obras = [o(1, "amarelo"), o(2, "verde"), o(3, "vermelho"), o(4, "amarelo"), o(5, "vermelho"), o(6, "amarelo"), o(7, "amarelo")];

  it("o QDOP pelo farol, e no mesmo farol a ordem oficial (seq)", () => {
    expect(porFarol(obras).map(x => x.seq)).toEqual([3, 5, 1, 4, 6, 7, 2]);
  });

  it("obras com problema: sem as verdes, até 5, com o total", () => {
    const r = obrasComProblema(obras);
    expect(r.itens.map(x => x.seq)).toEqual([3, 5, 1, 4, 6]);
    expect(r.total).toBe(6);
  });

  it("até 2 motivos na linha; o resto vira 'mais N'", () => {
    expect(motivosDaLinha([m("a"), m("b"), m("c")])).toEqual({ visiveis: [m("a"), m("b")], mais: 1 });
    expect(motivosDaLinha(undefined)).toEqual({ visiveis: [], mais: 0 });
  });
});
