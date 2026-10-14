// Numeros que nao sao dinheiro nem data (DESIGN.md › Numeros e datas): virgula decimal, e espaco
// NAO separavel entre o numero e a unidade ("1,5 MB" nunca quebra entre o 5 e o MB). Dinheiro e'
// `brl` (aqui, re-exportado por Medicoes.tsx); data e competencia moram em tempo.ts. Nada de `toFixed` +
// `replace` a mao.

/** Dinheiro: "R$ 1.234.567,89"; nulo vira tracinho e negativo leva o sinal de menos (U+2212), nao o hifen:
 *  "−R$ 5.555.566,66" (DESIGN.md › Numeros e datas). Centavos inteiros. */
export function brl(centavos: number | null): string {
  if (centavos === null) return "\u2014";
  const texto = (centavos / 100).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
  return texto.startsWith("-") ? `\u2212${texto.slice(1)}` : texto;
}

/** Contagem com o substantivo no numero certo: "1 medição", "3 medições" (milhar pt-BR). */
export function contar(n: number, um: string, varios: string): string {
  return `${n.toLocaleString("pt-BR")} ${n === 1 ? um : varios}`;
}

const NBSP = "\u00a0";

/** Tamanho de arquivo: "48 KB" ou "1,5 MB" (arquivo menor que 1 KB aparece como 1 KB). */
export function fmtTamanho(bytes: number): string {
  if (bytes >= 1024 * 1024) {
    const mb = (bytes / 1024 / 1024).toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
    return `${mb}${NBSP}MB`;
  }
  return `${Math.max(1, Math.round(bytes / 1024))}${NBSP}KB`;
}

/** Dias: "1 dia", "1.234 dias" (milhar pt-BR; o numero nao se separa da unidade). */
export function fmtDias(n: number): string {
  return `${n.toLocaleString("pt-BR")}${NBSP}${n === 1 ? "dia" : "dias"}`;
}

/** Fracao -> percentual pt-BR: 0,4 -> "40%"; 0,0462 -> "4,62%". Com `fixas`, sempre `casas` decimais, para coluna
 *  alinhada: fmtPercentual(0,298, 1, true) -> "29,8%"; fmtPercentual(0,01, 1, true) -> "1,0%". */
export function fmtPercentual(fracao: number, casas = 2, fixas = false): string {
  return fracao.toLocaleString("pt-BR", {
    style: "percent", maximumFractionDigits: casas, ...(fixas ? { minimumFractionDigits: casas } : {}),
  });
}

/** A base dos valores da obra (NAVEGACAO.md, principio 7): tudo em valor cheio; a cota vai junto quando a
 *  Lotufo nao tem 100%. Usada na topbar da obra e da medicao (F-50). */
export function baseDosValores(percentualBp: number): string {
  return percentualBp === 10000 ? "valores cheios (100% da Lotufo)"
    : `valores cheios · cota da Lotufo: ${fmtPercentual(percentualBp / 10000)}`;
}
