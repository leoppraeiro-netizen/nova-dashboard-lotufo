import { describe, expect, it } from "vitest";
import {
  contagemRec, contaRec, filtrarEventos, juntarPaginaRec, reconciliacaoDaObra, rotaDoObjeto, rotuloAcao, urlPaginaRec, type Evento,
  type Reconciliacao,
} from "./administracao";

const ev = (id: number, acao: string, criado_em: string, usuario_id: number | null): Evento =>
  ({ id, acao, entidade: null, criado_em, usuario_id });

describe("administração", () => {
  it("auditoria: ação, pessoa (ou o sistema) e desde, pelo dia de Cuiabá", () => {
    const eventos = [
      ev(1, "medicao.protocolo", "2026-09-28 12:00:00", 1),
      ev(2, "usuario.login", "2026-09-28 03:30:00", 2),   // 23:30 de 27/09 em Cuiabá
      ev(3, "rm.sincronizar", "2026-09-28 13:00:00", null),
    ];
    expect(filtrarEventos(eventos, { acao: "usuario.login" }).map(e => e.id)).toEqual([2]);
    expect(filtrarEventos(eventos, { pessoa: "sistema" }).map(e => e.id)).toEqual([3]);
    expect(filtrarEventos(eventos, { desde: "2026-09-28" }).map(e => e.id)).toEqual([1, 3]);
  });

  it("contagem da reconciliação: o número exato; 'ou mais' só quando é piso", () => {
    expect(contagemRec("nfs", 250)).toBe("250 NFs sem medição");
    expect(contagemRec("desfeitas", 14)).toBe("14 alocações desfeitas");
    expect(contagemRec("desfeitas", 3, true)).toBe("3 ou mais alocações desfeitas");
  });

  // #22: a API manda as NFs sem medição e as alocações desfeitas em páginas, com o total exato junto
  it("reconciliação paginada: o total vem da API, a página seguinte parte da última linha e se junta", () => {
    const nf = (id: number) => ({ id, coligada: 1, numero: String(id), serie: null, emissao: null, valor_centavos: 100, campo_livre1: null });
    const desf = (id: number, numero_instrumento: string) => ({ id, medicao_id: id, desfeita_em: "2026-09-01 10:00:00", motivo_desfazer: "x",
      numero: String(id), serie: null, numero_instrumento, numero_medicao: 1, estado: "recebida" });
    const rec: Reconciliacao = { nfs_sem_medicao: [nf(9), nf(4)], medicoes_sem_nf: [], divergencias: [],
      alocacoes_desfeitas: [desf(5, "161/2022")], totais: { nfs_sem_medicao: 3, alocacoes_desfeitas: 2 },
      ha_mais: { nfs_sem_medicao: true, alocacoes_desfeitas: true } };
    expect(contaRec(rec, rec, "nfs", false)).toEqual({ n: 3, piso: false, haMais: true });
    expect(contaRec(rec, rec, "divergencias", false)).toEqual({ n: 0, piso: false, haMais: false });
    // a NF leva a emissão que a tela recebeu (vazia quando sem data); a desfeita, só o id
    expect(urlPaginaRec(rec, "nfs")).toBe("/api/rm/reconciliacao?nfs_apos=4&nfs_emissao=");
    expect(urlPaginaRec({ ...rec, nfs_sem_medicao: [{ ...nf(4), emissao: "2026-08-01T00:00:00-04:00" }] }, "nfs"))
      .toBe("/api/rm/reconciliacao?nfs_apos=4&nfs_emissao=2026-08-01T00%3A00%3A00-04%3A00");
    expect(urlPaginaRec(rec, "desfeitas")).toBe("/api/rm/reconciliacao?desfeitas_apos=5");
    // com a obra escolhida, a contagem das desfeitas é do que chegou e vira piso enquanto houver página
    const daObra = reconciliacaoDaObra(rec, { id: 7, numero_instrumento: "161/2022" });
    expect(contaRec(rec, daObra, "desfeitas", true)).toEqual({ n: 1, piso: true, haMais: true });
    expect(contaRec(rec, daObra, "nfs", true)).toEqual({ n: 0, piso: false, haMais: false });
    // a página seguinte das NFs: junta só elas; total e "há mais" passam a ser os dela
    const pagina: Reconciliacao = { nfs_sem_medicao: [nf(2)], medicoes_sem_nf: [], divergencias: [],
      alocacoes_desfeitas: [desf(9, "200/2023")], totais: { nfs_sem_medicao: 3, alocacoes_desfeitas: 2 },
      ha_mais: { nfs_sem_medicao: false, alocacoes_desfeitas: true } };
    const junta = juntarPaginaRec(rec, "nfs", pagina);
    expect(junta.nfs_sem_medicao.map(n => n.id)).toEqual([9, 4, 2]);
    expect(junta.alocacoes_desfeitas).toBe(rec.alocacoes_desfeitas);
    expect(contaRec(junta, junta, "nfs", false)).toEqual({ n: 3, piso: false, haMais: false });
  });

  it("reconciliação de uma obra: pelo id, as desfeitas pelo instrumento, e sem as NFs soltas", () => {
    const rec: Reconciliacao = {
      totais: { nfs_sem_medicao: 1, alocacoes_desfeitas: 1 }, ha_mais: { nfs_sem_medicao: false, alocacoes_desfeitas: false },
      nfs_sem_medicao: [{ id: 1, coligada: 1, numero: "10", serie: null, emissao: null, valor_centavos: 100, campo_livre1: null }],
      medicoes_sem_nf: [
        { medicao_id: 5, contrato_id: 7, numero_instrumento: "161/2022", numero: 1, tipo: "execucao", competencia: "2026-08", estado: "recebida", valor_centavos: 1 },
        { medicao_id: 6, contrato_id: 8, numero_instrumento: "200/2023", numero: 1, tipo: "execucao", competencia: "2026-08", estado: "recebida", valor_centavos: 1 },
      ],
      divergencias: [],
      alocacoes_desfeitas: [{ id: 1, medicao_id: 5, desfeita_em: "2026-09-01 10:00:00", motivo_desfazer: "x", numero: "11", serie: null,
                              numero_instrumento: "161/2022", numero_medicao: 1, estado: "recebida" }],
    };
    const r = reconciliacaoDaObra(rec, { id: 7, numero_instrumento: "161/2022" });
    expect(r.nfs_sem_medicao).toEqual([]);
    expect(r.medicoes_sem_nf.map(m => m.medicao_id)).toEqual([5]);
    expect(r.alocacoes_desfeitas).toHaveLength(1);
    expect(reconciliacaoDaObra(rec, null)).toBe(rec);
  });

  it("auditoria: toda ação que o servidor grava tem rótulo; a desconhecida fica legível (B-11, 10/10/2026)", () => {
    // levantadas com grep de auditoria.registrar em backend/app (10/10/2026), mais as que scripts gravaram no banco
    const acoes = ["aditivo.assinar", "aditivo.atualizar", "aditivo.cancelar", "aditivo.carga", "aditivo.criar", "auth.login",
      "auth.login_falha", "auth.logout", "cadastro.aplicar", "cadastro.consorciadas", "cadastro.contrato", "cadastro.datas_base",
      "cadastro.entidade", "cadastro.espelho", "cadastro.fiscal", "cadastro.geral", "cadastro.instrumento", "cadastro.orgao",
      "cadastro.pleito", "certidao.marcar_estado", "certidao.nao_se_aplica", "certidao.registrar", "certidao_tipo.criar",
      "contrato.atualizar", "contrato.criar", "contrato.encerramento", "contrato.mudar_estado", "correio.assinatura",
      "correio.envio", "cronograma.nova_versao", "entidade.coligada_rm", "entidade.criar", "entidade.desativar", "envio.liberar",
      "espelho.enviar", "espelho.gerar", "frc.gerar", "medicao.criar", "medicao.documento", "medicao.estado",
      "medicao.faturada_legado", "medicao.final", "medicao.numero_orgao", "medicao.protocolo", "medicao.remover_teste",
      "medicao.valor_atestado", "medicao.valor_protocolado", "nf.alocar", "nf.desalocar", "nota.conferencia", "nota.confirmacao",
      "nota.justificar", "nota.manual", "notas.envio_externo", "pleito.anexo", "pleito.anexo_removido", "pleito.assinado",
      "pleito.criar", "pleito.descartar", "pleito.enviar", "pleito.montar", "protocolo.assinado", "protocolo.criar",
      "protocolo.descartar", "protocolo.enviar", "protocolo.link", "protocolo.link_removido", "protocolo.montar",
      "protocolo.numero_orgao", "protocolo.peca", "protocolo.peca_removida", "regularidade.competencia_corrigida",
      "regularidade.registrar", "rm.sincronizacao", "usuario.atualizar", "usuario.criar", "usuario.desbloquear",
      "usuario.senha_redefinida", "usuario.senha_trocada"];
    expect(acoes.filter(a => /[._]/.test(rotuloAcao(a)) || rotuloAcao(a) === a)).toEqual([]);
    expect(rotuloAcao("frc.gerar")).toBe("FRC gerada");
    expect(rotuloAcao("medicao.valor_atestado")).toBe("Atestado alterado");
    expect(rotuloAcao("envio.liberar")).toBe("Envio liberado à mão");
    expect(rotuloAcao("algo.novo_aqui")).toBe("Algo novo aqui");
  });

  it("auditoria: o objeto do evento leva à tela dele; sem tela, fica texto (#21)", () => {
    expect(rotaDoObjeto({ entidade: "contrato", entidade_id: "7" })).toEqual({ tela: "obra", id: 7, aba: "medicoes" });
    expect(rotaDoObjeto({ entidade: "medicao", entidade_id: "700", contrato_id: 7 })).toEqual({ tela: "medicao", obra: 7, id: 700 });
    expect(rotaDoObjeto({ entidade: "protocolo", entidade_id: "3", contrato_id: 7 })).toEqual({ tela: "obra", id: 7, aba: "medicoes" });
    expect(rotaDoObjeto({ entidade: "usuario", entidade_id: "2" })).toEqual({ tela: "admin", aba: "usuarios" });
    // medicao/protocolo cuja obra a API nao achou, objeto sem id, entidade sem tela
    expect(rotaDoObjeto({ entidade: "medicao", entidade_id: "700", contrato_id: null })).toBeNull();
    expect(rotaDoObjeto({ entidade: "protocolo", entidade_id: "3" })).toBeNull();
    expect(rotaDoObjeto({ entidade: "contrato", entidade_id: null })).toBeNull();
    expect(rotaDoObjeto({ entidade: "cadastro", entidade_id: "1" })).toBeNull();
    expect(rotaDoObjeto({ entidade: null, entidade_id: null })).toBeNull();
  });
});
