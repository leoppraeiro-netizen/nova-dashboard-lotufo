import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import Admin from "./Admin";

const { api } = vi.hoisted(() => ({ api: vi.fn() }));
vi.mock("./api", () => ({ api, ApiErro: class ApiErro extends Error { status = 0; } }));

afterEach(() => { cleanup(); api.mockReset(); });

test("Usuários: sem Desativar na própria linha; desativar outro pede confirmação antes do pedido", async () => {
  api.mockImplementation(async (url: string) => {
    if (url === "/api/admin/usuarios") return [
      { id: 1, nome: "Leonardo", email: "l@x.com", perfil: "admin", ativo: 1 },
      { id: 2, nome: "Maria", email: "m@x.com", perfil: "engenharia", ativo: 1 }];
    if (url === "/api/admin/contas-microsoft") return [];
    return { ok: true };
  });
  render(<Admin aba="usuarios" eu={1} />);
  // o jsdom junta o texto oculto sem o espaço do começo ("DesativarMaria"); o navegador mantém o espaço
  fireEvent.click(await screen.findByRole("button", { name: /Desativar\s*Maria/ }));
  expect(screen.queryByRole("button", { name: /Desativar\s*Leonardo/ })).toBeNull();
  expect(api).not.toHaveBeenCalledWith("/api/admin/usuarios/2", expect.anything());
  fireEvent.click(screen.getByRole("button", { name: /Confirmar a desativação\s*de Maria/ }));
  expect(api).toHaveBeenCalledWith("/api/admin/usuarios/2", expect.objectContaining({ method: "PUT" }));
});

// A-05/B-10 (10/10/2026): conta trancada só destravava sozinha ou no banco; senha e perfil não se mudavam pela tela
test("Usuários: bloqueio com Desbloquear, Redefinir senha e perfil editável (menos na própria linha)", async () => {
  api.mockImplementation(async (url: string) => {
    if (url === "/api/admin/usuarios") return [
      { id: 1, nome: "Leonardo", email: "l@x.com", perfil: "admin", ativo: 1, bloqueado_ate: null, tentativas_falhas: 0 },
      { id: 2, nome: "Maria", email: "m@x.com", perfil: "engenharia", ativo: 1,
        bloqueado_ate: "2026-10-10T14:35:00-04:00", tentativas_falhas: 0 }];
    if (url === "/api/admin/contas-microsoft") return [];
    return { ok: true };
  });
  render(<Admin aba="usuarios" eu={1} />);
  expect(await screen.findByText("até 14:35")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: /Desbloquear\s*Maria/ }));
  expect(api).toHaveBeenCalledWith("/api/admin/usuarios/2/desbloquear", expect.objectContaining({ method: "POST" }));

  expect(screen.queryByRole("combobox", { name: /Perfil de Leonardo/ })).toBeNull();
  fireEvent.change(screen.getByRole("combobox", { name: /Perfil de Maria/ }), { target: { value: "diretoria" } });
  expect(api).toHaveBeenCalledWith("/api/admin/usuarios/2", { method: "PUT", body: JSON.stringify({ perfil: "diretoria" }) });

  expect(screen.queryByRole("button", { name: /Redefinir senha\s*de Leonardo/ })).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: /Redefinir senha\s*de Maria/ }));
  fireEvent.change(screen.getByLabelText(/Senha nova de Maria/), { target: { value: "senha-nova-456" } });
  fireEvent.click(screen.getByRole("button", { name: /Confirmar a senha nova/ }));
  expect(api).toHaveBeenCalledWith("/api/admin/usuarios/2/senha", { method: "POST", body: JSON.stringify({ senha: "senha-nova-456" }) });
});

// Issue #5: a auditoria passava de 500 eventos sem acesso aos anteriores; "Carregar mais" busca a página seguinte pelo cursor
test("Auditoria: Carregar mais busca a página anterior pelo cursor, mantém os filtros e some no primeiro evento", async () => {
  const ev = (id: number, acao: string) => ({ id, acao, entidade: null, criado_em: "2026-10-10 12:00:00", usuario_id: null });
  api.mockImplementation(async (url: string) => {
    if (url === "/api/admin/usuarios") return [];
    if (url === "/api/admin/auditoria?limite=500")
      return { cadeia_integra: true, ha_mais: true, eventos: [ev(30, "auth.login"), ev(29, "medicao.criar")] };
    if (url === "/api/admin/auditoria?limite=500&antes_de=29")
      return { cadeia_integra: null, ha_mais: false, eventos: [ev(28, "auth.login"), ev(27, "medicao.criar")] };
    throw new Error(`chamada inesperada: ${url}`);
  });
  render(<Admin aba="auditoria" busca={{ acao: "auth.login" }} />);
  expect(await screen.findByText(/2 eventos/)).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Carregar mais" }));
  // 4 eventos carregados, 2 passam no filtro de ação (o filtro vale sobre as duas páginas)
  expect(await screen.findByText(/2 de 4 eventos/)).toBeTruthy();
  expect(screen.getAllByText("Entrada no sistema").length).toBe(3); // 2 linhas + a opção do filtro
  expect(screen.queryByRole("button", { name: "Carregar mais" })).toBeNull();
  // a página seguinte vem sem a verificação da cadeia: o selo da primeira fica
  expect(screen.getByText("cadeia íntegra")).toBeTruthy();
});

test("Auditoria: filtro sem resultado nos já carregados avisa que há anteriores, em vez de dizer que não existe", async () => {
  api.mockImplementation(async (url: string) => {
    if (url === "/api/admin/usuarios") return [];
    return { cadeia_integra: true, ha_mais: true,
             eventos: [{ id: 9, acao: "auth.login", entidade: null, criado_em: "2026-10-10 12:00:00", usuario_id: null }] };
  });
  render(<Admin aba="auditoria" busca={{ acao: "medicao.criar" }} />);
  expect(await screen.findByText(/entre os já carregados/)).toBeTruthy();
  expect(screen.getByRole("button", { name: "Carregar mais" })).toBeTruthy();
});

// Issue #31: a Saúde mostra o último backup, quantos estão guardados e o último erro; atrasado acima de 2 h em destaque
const BACKUP_EM_DIA = {
  ultimo_backup: "2026-10-13T07:30:00-04:00", tamanho_bytes: 3 * 1024 * 1024, guardados: 48, copias_externas: 7,
  atrasado: false, ultimo_snapshot: "2026-10-13T07:30:00-04:00", ultimo_snapshot_erro: null,
  ultima_copia_externa: "2026-10-13T03:00:00-04:00", ultima_copia_externa_erro: null,
};

function saudeCom(backup: object) {
  api.mockImplementation(async (url: string) => {
    if (url === "/api/admin/backup") return backup;
    throw new Error(`fora do recorte: ${url}`);
  });
  render(<Admin aba="saude" />);
}

test("Saúde: backup em dia mostra a data e hora do último, a quantidade guardada e nenhum erro", async () => {
  saudeCom(BACKUP_EM_DIA);
  expect(await screen.findByText(/Último backup: 13\/10\/2026 às 07:30/)).toBeTruthy();
  expect(screen.getByText(/48 snapshots guardados/)).toBeTruthy();
  expect(screen.getByText(/7 cópias externas/)).toBeTruthy();
  expect(screen.getByText(/Último erro: nenhum/)).toBeTruthy();
  expect(screen.queryByText(/Backup atrasado/)).toBeNull();
  expect(api).not.toHaveBeenCalledWith("/api/health");
});

test("Saúde: backup atrasado acima de 2 h aparece em destaque, e o último erro aparece", async () => {
  saudeCom({ ...BACKUP_EM_DIA, atrasado: true, ultimo_snapshot_erro: "2026-10-13T10:30:00-04:00: disco cheio" });
  const alerta = await screen.findByText(/Backup atrasado/);
  expect(alerta.closest(".aviso--critico")).toBeTruthy();
  expect(alerta.textContent).toMatch(/13\/10\/2026 às 07:30/);
  expect(screen.getByText(/disco cheio/)).toBeTruthy();
  expect(screen.queryByText(/Último erro: nenhum/)).toBeNull();
});

test("Saúde: sem nenhum backup guardado também é atraso em destaque", async () => {
  saudeCom({ ...BACKUP_EM_DIA, ultimo_backup: null, tamanho_bytes: null, guardados: 0, copias_externas: null,
             atrasado: true, ultimo_snapshot: null, ultima_copia_externa: null });
  expect((await screen.findByText(/Backup atrasado/)).textContent).toMatch(/nenhum backup guardado/);
});
