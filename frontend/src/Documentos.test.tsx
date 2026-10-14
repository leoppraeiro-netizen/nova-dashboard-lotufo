import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { apiForm } from "./api";
import Documentos, { competenciaDoNome } from "./Documentos";

vi.mock("./api", async (original) => ({
  ...(await original<typeof import("./api")>()),
  api: vi.fn(async (caminho: string) => {
    if (caminho === "/api/documentos") return {
      hoje: "2026-09-23",
      empresas: [{
        entidade_id: 1, entidade: "Lotufo", cnpj: "31200101000130", papel: "lotufo", regularidade_exigida: true,
        regularidade: { situacao: "atrasada", competencia: "2026-06", esperada: "2026-07" },
        certidoes: [
          { tipo_id: 2, chave: "fgts", tipo: "CRF/FGTS", link_emissao: "https://consulta-crf.caixa.gov.br/x", exigida: true,
            situacao: "vencendo", dias: 4, certidao: { id: 7, emissao: "2026-08-29", validade: "2026-09-27", natureza: "negativa", leitura: "manual" } },
          { tipo_id: 5, chave: "municipal", tipo: "Certidão de Débitos Gerais (Prefeitura de Cuiabá)", link_emissao: "https://x",
            exigida: true, situacao: "vencida", dias: null, certidao: { id: 8, emissao: "2026-08-20", validade: "2026-09-20", natureza: "negativa" } },
          { tipo_id: 6, chave: "falencia", tipo: "Certidão de Falência e Recuperação Judicial (TJMT)", link_emissao: "https://x",
            exigida: false, situacao: "faltando", dias: null, certidao: null },
        ],
      }],
    };
    return {};
  }),
  apiForm: vi.fn(),
}));

afterEach(cleanup);

const usuario = { id: 1, nome: "U", email: "u@lotufo.com", perfil: "engenharia" };

test("mostra a empresa, o que vence, o que venceu, a regularidade atrasada e o link de emissão", async () => {
  render(<Documentos usuario={usuario} />);
  // a empresa e' a linha da matriz, com a ancora que o aviso de documentos usa
  await waitFor(() => screen.getByRole("rowheader", { name: /Lotufo/ }));
  expect(screen.getByRole("rowheader", { name: /Lotufo/ }).id).toBe("emp-1");
  screen.getByText(/vence em 4 dias/i);
  // a celula: a situacao no selo e a validade embaixo
  screen.getByText("vencida");
  screen.getByText("em 20/09/2026");
  screen.getByText(/não exigida/i);
  screen.getByText(/esperada 07\/2026/);
  expect(screen.getAllByRole("link", { name: /emitir/i })[0].getAttribute("href")).toBe("https://consulta-crf.caixa.gov.br/x");
  expect(screen.getByRole("link", { name: /ZIP das certidões vigentes/i }).getAttribute("href"))
    .toBe("/api/documentos/zip?entidade_id=1&data=2026-09-23");
  screen.getByLabelText(/Escolher PDFs/i);
});

test("diretoria não vê onde anexar", async () => {
  render(<Documentos usuario={{ ...usuario, perfil: "diretoria" }} />);
  await waitFor(() => screen.getByRole("rowheader", { name: /Lotufo/ }));
  expect(screen.queryByLabelText(/Escolher PDFs/i)).toBeNull();
  expect(screen.queryByRole("button", { name: /anexar regularidade/i })).toBeNull();
});

test("certidão digitada à mão leva o selo 'digitada' ao lado da data (testes de quebra 10/10, A-19)", async () => {
  render(<Documentos usuario={usuario} />);
  await waitFor(() => screen.getByRole("rowheader", { name: /Lotufo/ }));
  expect(screen.getAllByText("digitada")).toHaveLength(1);          // so' a do FGTS; a municipal veio lida
});

test("datas lidas implausíveis abrem a digitação já preenchida com o que foi lido (gate Sol S6)", async () => {
  vi.mocked(apiForm).mockResolvedValueOnce({
    ok: false, motivo: "datas-implausiveis", digitavel: true,
    mensagem: "As datas lidas (emissão 24/06/2026, validade 21/12/2028) não batem com o prazo normal desta certidão: confira no documento e digite",
    lidos: { entidade_id: 1, tipo: "trabalhista", emissao: "2026-06-24", validade: "2028-12-21", natureza: "negativa" },
  });
  render(<Documentos usuario={usuario} />);
  await waitFor(() => screen.getByRole("rowheader", { name: /Lotufo/ }));
  fireEvent.change(screen.getByLabelText(/Escolher PDFs/i), { target: { files: [new File(["%PDF"], "cndt.pdf", { type: "application/pdf" })] } });
  await screen.findByText(/não batem com o prazo normal/);
  expect((screen.getByLabelText("Empresa") as HTMLSelectElement).value).toBe("1");
  expect((screen.getByLabelText("Tipo") as HTMLSelectElement).value).toBe("trabalhista");
  expect((screen.getByLabelText("Emissão") as HTMLInputElement).value).toBe("2026-06-24");
  expect((screen.getByLabelText(/^Validade/) as HTMLInputElement).value).toBe("2028-12-21");
});

test("competência pelo nome do arquivo do DP", () => {
  expect(competenciaDoNome("042026 - LOTUFO ENGENHARIA.pdf")).toBe("2026-04");
  expect(competenciaDoNome("Documentos Lotufo.pdf")).toBe("");
});
