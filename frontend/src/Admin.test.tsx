import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import Admin from "./Admin";

const { api } = vi.hoisted(() => ({ api: vi.fn() }));
vi.mock("./api", async (original) => ({ ...(await original<typeof import("./api")>()), api }));

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

// Issue #20: o sucesso de "Sincronizar agora" não era anunciado
test("Saúde: Sincronizar agora anuncia o sucesso numa região viva", async () => {
  const status = { configurado: true, em_andamento: false, ultima_sincronizacao: null, ultimo_erro: null, rodadas: [] };
  api.mockImplementation(async (url: string, opts?: { method?: string }) => {
    if (url === "/api/rm/sincronizar" && opts?.method === "POST") return { estado: "success" };
    if (url === "/api/rm/status") return status;
    if (url === "/api/health") return {};
    throw new Error("fora do recorte deste teste");
  });
  render(<Admin aba="saude" />);
  fireEvent.click(await screen.findByRole("button", { name: "Sincronizar agora" }));
  const aviso = await screen.findByText("Sincronização concluída.");
  expect(aviso.closest("[role='status']")).not.toBeNull();
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
  ultimo_backup: "2026-10-13T07:30:00-04:00", tamanho_bytes: 3 * 1024 * 1024, guardados: 48, copia_externa_configurada: true,
  atrasado: false, ultimo_snapshot: "2026-10-13T07:30:00-04:00", ultimo_snapshot_erro: null, ultimo_snapshot_erro_em: null,
  ultima_copia_externa: "2026-10-13T03:00:00-04:00", ultima_copia_externa_erro: null, ultima_copia_externa_erro_em: null,
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
  expect(screen.getByText(/3,0\sMB/)).toBeTruthy();
  expect(screen.getByText(/Última cópia externa: 13\/10\/2026 às 03:00/)).toBeTruthy();
  expect(screen.getByText(/Último erro: nenhum/)).toBeTruthy();
  expect(screen.queryByText(/Backup atrasado/)).toBeNull();
  expect(api).not.toHaveBeenCalledWith("/api/health");
});

test("Saúde: backup atrasado acima de 2 h aparece em destaque, e o último erro aparece", async () => {
  saudeCom({ ...BACKUP_EM_DIA, atrasado: true, ultimo_snapshot_erro_em: "2026-10-13T10:30:00-04:00",
             ultimo_snapshot_erro: "não foi possível gravar o snapshot; o detalhe está no log do servidor" });
  const alerta = await screen.findByText(/Backup atrasado/);
  expect(alerta.closest(".aviso--critico")).toBeTruthy();
  expect(alerta.textContent).toMatch(/13\/10\/2026 às 07:30/);
  // sugestao do revisor: instrucao de operacao, nao caminho de arquivo do repositorio
  expect(alerta.textContent).not.toMatch(/runbook/);
  expect(screen.getByText(/em 13\/10\/2026 às 10:30, falhou \(não foi possível gravar o snapshot/)).toBeTruthy();
  expect(screen.queryByText(/runbook/)).toBeNull();
  expect(screen.queryByText(/Último erro: nenhum/)).toBeNull();
});

test("Saúde: sem nenhum backup guardado também é atraso em destaque", async () => {
  saudeCom({ ...BACKUP_EM_DIA, ultimo_backup: null, tamanho_bytes: null, guardados: 0, copia_externa_configurada: false,
             atrasado: true, ultimo_snapshot: null, ultima_copia_externa: null });
  expect((await screen.findByText(/Backup atrasado/)).textContent).toMatch(/nenhum backup guardado/);
  // sem erro registrado, "nenhum erro" desmentiria o alerta; sem pasta externa, não há cópia a esperar
  expect(screen.queryByText(/Último erro: nenhum/)).toBeNull();
  expect(screen.queryByText(/Última cópia externa/)).toBeNull();
});

// Issue #55: o backup passou a copiar as pastas de notas, espelhos, modelos e evidências; a falha dessa cópia
// tem de aparecer na tela, senão o selo diz OK com os arquivos sem cópia
test("Backup: cópia dos arquivos em dia aparece; a falha dela vira Falhou e tira o 'nenhum erro'", async () => {
  saudeCom({ ...BACKUP_EM_DIA, ultima_copia_arquivos: "2026-10-13T07:31:00-04:00",
             ultima_copia_externa_arquivos: "2026-10-13T07:35:00-04:00" });
  expect(await screen.findByText(/Última cópia dos arquivos: 13\/10\/2026 às 07:31/)).toBeTruthy();
  expect(screen.getByText(/Última cópia externa dos arquivos: 13\/10\/2026 às 07:35/)).toBeTruthy();
  expect(screen.getByText(/Último erro: nenhum/)).toBeTruthy();
  cleanup();
  saudeCom({ ...BACKUP_EM_DIA, ultima_copia_arquivos_erro_em: "2026-10-13T10:00:00-04:00",
             ultima_copia_arquivos_erro: "1 arquivo(s) sem cópia: notas/x.pdf (disco cheio)" });
  expect(await screen.findByText(/Última cópia dos arquivos: a última tentativa, em 13\/10\/2026 às 10:00, falhou/)).toBeTruthy();
  expect(screen.getByText(/disco cheio/)).toBeTruthy();
  expect(screen.getByText("Falhou")).toBeTruthy();
  expect(screen.queryByText(/Último erro: nenhum/)).toBeNull();
});

// Revisão da #142: a cópia dos arquivos para fora pode não terminar; aparece, e só existe com pasta externa
test("Backup: cópia externa dos arquivos que não termina aparece; sem pasta externa a linha some", async () => {
  saudeCom({ ...BACKUP_EM_DIA, ultima_copia_externa_arquivos_erro: "a cópia está rodando há 3 horas sem terminar" });
  expect(await screen.findByText(/Última cópia externa dos arquivos: a última tentativa falhou/)).toBeTruthy();
  expect(screen.getByText(/rodando há 3 horas sem terminar/)).toBeTruthy();
  expect(screen.getByText("Falhou")).toBeTruthy();
  cleanup();
  saudeCom({ ...BACKUP_EM_DIA, copia_externa_configurada: false });
  expect(await screen.findByText(/Última cópia dos arquivos: nenhuma/)).toBeTruthy();
  expect(screen.queryByText(/Última cópia externa dos arquivos/)).toBeNull();
});
