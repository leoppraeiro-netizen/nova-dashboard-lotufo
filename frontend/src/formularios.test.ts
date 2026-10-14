/// <reference types="node" />
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

// Convenção dos formulários (issue #11, auditor S2 de 28/09/2026): campo de código ou número não deixa o
// navegador sugerir nem corrigir o que se digita, e placeholder termina em reticências. O jsdom não conta
// isso sozinho; aqui o teste lê as telas do disco (o vitest roda na pasta frontend), como o celular.test.ts.
const pasta = join(process.cwd(), "src");
const telas = readdirSync(pasta).filter(n => n.endsWith(".tsx") && !n.endsWith(".test.tsx"));
const fonte = (nome: string) => readFileSync(join(pasta, nome), "utf8");

// Login não entra: a máscara de senha e o endereço de exemplo não são dica de preenchimento
const PLACEHOLDER_FORA = new Set(["Login.tsx"]);

function campos(codigo: string): string[] {
  return codigo.match(/<input\b[\s\S]*?\/>/g) ?? [];
}

// campo de código ou número: ofício, processo, valor, dias, número de nota/medição/protocolo, endereço (url)
function ehCodigoOuNumero(tag: string): boolean {
  if (/type="(file|checkbox|radio|date|month|search|password|email)"/.test(tag)) return false;
  // o texto do exemplo ("até 5 dias") não conta: só o que o campo é
  const semExemplo = tag.replace(/placeholder=(?:"[^"]*"|\{[^}]*\})/g, "");
  return /inputMode="(numeric|decimal)"|type="(number|url)"|numero|oficio|processo|valor|dias|protocolo/i.test(semExemplo);
}

describe("formulários: campos de código e número", () => {
  it("têm name, autoComplete=off e spellCheck={false}", () => {
    const faltam: string[] = [];
    for (const nome of telas) {
      for (const tag of campos(fonte(nome))) {
        if (!ehCodigoOuNumero(tag)) continue;
        const rotulo = `${nome}: ${tag.replace(/\s+/g, " ").slice(0, 80)}`;
        if (!/\bname=/.test(tag)) faltam.push(`${rotulo} sem name`);
        if (!/autoComplete="off"/.test(tag)) faltam.push(`${rotulo} sem autoComplete="off"`);
        if (!/spellCheck=\{false\}/.test(tag)) faltam.push(`${rotulo} sem spellCheck={false}`);
      }
    }
    expect(faltam).toEqual([]);
  });

  it("a conferência acha os campos que importam (não passa por não olhar nada)", () => {
    const todos = telas.flatMap(n => campos(fonte(n))).filter(ehCodigoOuNumero);
    expect(todos.length).toBeGreaterThanOrEqual(12);
  });
});

describe("formulários: placeholders", () => {
  it("terminam em reticências", () => {
    const sem: string[] = [];
    for (const nome of telas) {
      if (PLACEHOLDER_FORA.has(nome)) continue;
      for (const m of fonte(nome).matchAll(/placeholder=(?:"([^"]*)"|\{"([^"]*)"\})/g)) {
        const texto = (m[1] ?? m[2]).replace(/\\n/g, "\n");
        if (!texto.endsWith("…")) sem.push(`${nome}: ${texto}`);
      }
    }
    expect(sem).toEqual([]);
  });
});
