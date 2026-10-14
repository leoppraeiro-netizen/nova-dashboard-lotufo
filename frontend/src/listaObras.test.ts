import { describe, expect, it } from "vitest";
import { filtrarObras, type ObraLista } from "./listaObras";

const o = (id: number, nome: string, extra: Partial<ObraLista> = {}): ObraLista => ({
  id, orgao: "SINFRA", numero_instrumento: `${id}/2026`, nome_curto: nome, estado: "ativo", ...extra });

describe("lista de obras", () => {
  const lista = [
    o(1, "MT-388", { dias_execucao: 187, dias_vigencia: 277 }),
    o(2, "5 Bairros", { dias_execucao: 9, dias_vigencia: 3 }),
    o(3, "Granito", { dias_execucao: 150, dias_vigencia: 60 }),
    o(4, "Deciolândia", { estado: "encerrado", dias_execucao: -300 }),
    o(5, "Maternidade VG", { orgao: "SMS-VG", dias_execucao: 80, dias_vigencia: 40, vigencia_automatica: true }),
  ];

  it("em andamento por padrão, na ordem do nome; todas com o filtro", () => {
    expect(filtrarObras(lista, {}).map(x => x.nome_curto)).toEqual(["5 Bairros", "Granito", "Maternidade VG", "MT-388"]);
    expect(filtrarObras(lista, { todas: true })).toHaveLength(5);
  });

  it("terminam em 90 dias: execução ou vigência (a que o órgão não prorroga junto), a vencida na frente", () => {
    const comVencida = [...lista, o(6, "Terminais BRT", { dias_execucao: -24, dias_vigencia: -4 })];
    expect(filtrarObras(comVencida, { termina: 90 }).map(x => x.nome_curto)).toEqual(["Terminais BRT", "5 Bairros", "Granito", "Maternidade VG"]);
    // a encerrada, com prazo vencido ha' muito, nao entra mesmo com "todas"
    expect(filtrarObras(comVencida, { termina: 90, todas: true }).map(x => x.id)).not.toContain(4);
  });

  it("busca sem acento e sem caixa", () => {
    expect(filtrarObras([o(9, "Coxipó 2ª Etapa")], { q: "coxipo 2a" }).map(x => x.id)).toEqual([9]);
  });

  it("busca por nome ou instrumento, e órgão", () => {
    expect(filtrarObras(lista, { q: "mt-3" }).map(x => x.id)).toEqual([1]);
    expect(filtrarObras(lista, { q: "4/2026", todas: true }).map(x => x.id)).toEqual([4]);
    expect(filtrarObras(lista, { orgao: "SMS-VG" }).map(x => x.id)).toEqual([5]);
  });
});
