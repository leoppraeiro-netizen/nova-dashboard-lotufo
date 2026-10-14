import { describe, expect, it } from "vitest";
import { colunas, matriz, pendenciasDa, type EmpresaDoc, type LinhaCertidao } from "./matriz";

const l = (chave: string, situacao: LinhaCertidao["situacao"], dias: number | null, exigida = true): LinhaCertidao => ({
  tipo_id: chave.length, chave, tipo: chave, link_emissao: null, exigida, situacao, dias, certidao: null });
const e = (id: number, certidoes: LinhaCertidao[], reg: EmpresaDoc["regularidade"] = null): EmpresaDoc => ({
  entidade_id: id, entidade: `E${id}`, cnpj: "", papel: "lotufo", certidoes, regularidade_exigida: reg !== null, regularidade: reg });

describe("matriz de documentos", () => {
  const empresas = [
    e(1, [l("federal", "ok", 80), l("fgts", "ok", 25)]),                         // vence em 25 dias: pendência (decisão 5)
    e(2, [l("federal", "ok", 90), l("municipal", "faltando", null, false)]),     // não exigida não pesa
    e(3, [l("federal", "vencida", null), l("estadual", "faltando", null)],
      { situacao: "atrasada", competencia: "2026-07", esperada: "2026-08" }),
  ];

  it("pendência é certidão exigida vencida, faltando ou vencendo em até 30 dias, e a regularidade fora do dia", () => {
    expect(empresas.map(pendenciasDa)).toEqual([1, 0, 3]);
  });

  it("pela gravidade: o que já trava, depois o que vence (o mais urgente antes); o filtro deixa só as pendentes", () => {
    const mais = [...empresas, e(4, [l("federal", "ok", 20), l("fgts", "vencendo", 12)]), e(5, [l("trabalhista", "vencida", null)])];
    expect(matriz(mais, false).map(x => x.entidade_id)).toEqual([3, 5, 4, 1, 2]);
    expect(matriz(mais, true).map(x => x.entidade_id)).toEqual([3, 5, 4, 1]);
  });

  it("as colunas são os tipos que alguma empresa tem, na ordem dada", () => {
    expect(colunas(empresas, ["federal", "fgts", "trabalhista", "estadual", "municipal"])).toEqual(["federal", "fgts", "estadual", "municipal"]);
  });
});
