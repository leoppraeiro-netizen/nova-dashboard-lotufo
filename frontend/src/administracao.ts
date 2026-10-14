// Administracao (NAVEGACAO.md › Administracao): as abas, os grupos da reconciliacao RM × dashboard e os filtros da
// auditoria, no front, sobre o que a API ja' manda (`/api/rm/reconciliacao`, `/api/admin/auditoria`).
import type { AbaAdmin } from "./rota";
import { diaLocal } from "./tempo";

/** As abas da Administracao, na ordem do mapa (a Saude e' a padrao). */
export const ABAS_ADMIN: { id: AbaAdmin; rotulo: string }[] = [
  { id: "saude", rotulo: "Saúde" }, { id: "reconciliacao", rotulo: "Reconciliação" },
  { id: "usuarios", rotulo: "Usuários" }, { id: "auditoria", rotulo: "Auditoria" },
];

/* ------------------------------------------------------------ reconciliacao */

export type NfSolta = { id: number; coligada: number; numero: string; serie: string | null; emissao: string | null;
                        valor_centavos: number; campo_livre1: string | null };
export type MedSemNf = { medicao_id: number; contrato_id: number; numero_instrumento: string; numero: number; tipo: string;
                         competencia: string; estado: string; valor_centavos: number | null };
export type Divergencia = { medicao_id: number; contrato_id: number; numero_instrumento: string; numero: number; tipo: string;
                            competencia: string | null; valor_centavos: number; alocado_centavos: number };
// A API nao manda o id da obra na alocacao desfeita, so' o instrumento.
export type Desfeita = { medicao_id: number; desfeita_em: string; motivo_desfazer: string; numero: string; serie: string | null;
                         numero_instrumento: string; numero_medicao: number; estado: string };
export type Reconciliacao = { nfs_sem_medicao: NfSolta[]; medicoes_sem_nf: MedSemNf[]; divergencias: Divergencia[];
                              alocacoes_desfeitas: Desfeita[] };

export type CategoriaRec = "nfs" | "medicoes" | "divergencias" | "desfeitas";
/** Os quatro grupos, na ordem da tela (`?categoria=` na URL). */
export const CATEGORIAS_REC: { id: CategoriaRec; campo: keyof Reconciliacao; titulo: string }[] = [
  { id: "nfs", campo: "nfs_sem_medicao", titulo: "NFs sem medição" },
  { id: "medicoes", campo: "medicoes_sem_nf", titulo: "Medições sem NF do RM" },
  { id: "divergencias", campo: "divergencias", titulo: "Divergências de valor" },
  { id: "desfeitas", campo: "alocacoes_desfeitas", titulo: "Alocações desfeitas" },
];

// A API corta duas listas (`sincronizacao_rm.reconciliacao`): as 200 NFs sem medicao e as 50 alocacoes desfeitas
// mais recentes. Quando a lista chega no teto pode haver mais, e a quantidade diz isso.
export const TETO_REC: Partial<Record<CategoriaRec, number>> = { nfs: 200, desfeitas: 50 };

/** A quantidade de um grupo: "37", ou "200 ou mais" quando a lista chega no teto da API. */
export function quantidadeRec(c: CategoriaRec, n: number): string {
  const teto = TETO_REC[c];
  return teto !== undefined && n >= teto ? `${n} ou mais` : String(n);
}

/** O rotulo de um grupo sem o numero ("divergências de valor"), no singular quando n vale 1. */
export function rotuloRec(c: CategoriaRec, n: number): string {
  switch (c) {
    case "nfs": return n === 1 ? "NF sem medição" : "NFs sem medição";
    case "medicoes": return n === 1 ? "medição sem NF do RM" : "medições sem NF do RM";
    case "divergencias": return n === 1 ? "divergência de valor" : "divergências de valor";
    case "desfeitas": return n === 1 ? "alocação desfeita" : "alocações desfeitas";
  }
}

/** A contagem de um grupo, em palavras ("37 divergências de valor"; "200 ou mais NFs sem medição" no teto). */
export function contagemRec(c: CategoriaRec, n: number): string {
  return `${quantidadeRec(c, n)} ${rotuloRec(c, n)}`;
}

/** A reconciliacao de uma obra: as medicoes sem NF e as divergencias pelo id da obra; as alocacoes desfeitas pelo
 *  instrumento; as NFs sem medicao nao tem obra e saem. Sem obra, tudo. */
export function reconciliacaoDaObra(rec: Reconciliacao, obra: { id: number; numero_instrumento: string | null } | null): Reconciliacao {
  if (obra === null) return rec;
  return {
    nfs_sem_medicao: [],
    medicoes_sem_nf: rec.medicoes_sem_nf.filter(m => m.contrato_id === obra.id),
    divergencias: rec.divergencias.filter(d => d.contrato_id === obra.id),
    alocacoes_desfeitas: obra.numero_instrumento === null ? [] : rec.alocacoes_desfeitas.filter(d => d.numero_instrumento === obra.numero_instrumento),
  };
}

/* ---------------------------------------------------------------- auditoria */

export type Evento = { id: number; acao: string; entidade: string | null; entidade_id?: string | null; criado_em: string;
                       usuario_id: number | null };
export type FiltroAuditoria = { acao?: string | null; pessoa?: string | null; desde?: string | null };

// F-85: a acao e o objeto do evento em portugues. B-11 (10/10/2026): o mapa cobre toda acao que backend/app grava
// (grep de auditoria.registrar) e as que scripts gravaram no banco; a desconhecida cai no codigo legivel.
const ROTULO_ACAO: Record<string, string> = {
  "auth.login": "Entrada no sistema", "usuario.login": "Entrada no sistema",
  "auth.login_falha": "Tentativa de entrada recusada", "auth.logout": "Saída do sistema",
  "usuario.criar": "Usuário criado", "usuario.atualizar": "Usuário alterado", "usuario.desbloquear": "Usuário desbloqueado",
  "usuario.senha_redefinida": "Senha redefinida pelo admin", "usuario.senha_trocada": "Senha trocada",
  "medicao.criar": "Medição criada", "medicao.estado": "Mudança de estado da medição",
  "medicao.protocolo": "Protocolo da medição", "medicao.final": "Medição final marcada",
  "medicao.valor_protocolado": "Valor protocolado alterado", "medicao.valor_atestado": "Atestado alterado",
  "medicao.numero_orgao": "Número do órgão registrado na medição", "medicao.remover_teste": "Medição de teste removida",
  "medicao.documento": "Documento da medição", "medicao.faturada_legado": "Faturamento carregado do legado",
  "espelho.gerar": "Espelho gerado", "espelho.enviar": "Espelho enviado",
  "protocolo.criar": "Protocolo criado", "protocolo.peca": "Peça do protocolo anexada",
  "protocolo.peca_removida": "Peça do protocolo removida", "protocolo.montar": "Protocolo montado",
  "protocolo.assinado": "Protocolo assinado", "protocolo.enviar": "Protocolo enviado",
  "protocolo.numero_orgao": "Número do órgão registrado", "protocolo.descartar": "Protocolo descartado",
  "protocolo.link": "Link adicionado ao protocolo", "protocolo.link_removido": "Link removido do protocolo",
  "envio.liberar": "Envio liberado à mão", "notas.envio_externo": "Envio feito por fora registrado", "frc.gerar": "FRC gerada",
  "pleito.criar": "Pleito criado", "pleito.anexo": "Anexo do pleito", "pleito.anexo_removido": "Anexo do pleito removido",
  "pleito.montar": "Pleito montado", "pleito.assinado": "Pleito assinado", "pleito.enviar": "Pleito enviado",
  "pleito.descartar": "Pleito descartado",
  "nf.alocar": "NF alocada à medição", "nf.desalocar": "Alocação de NF desfeita",
  "nota.confirmacao": "Nota confirmada pelo RM", "nota.conferencia": "Nota conferida", "nota.justificar": "Nota justificada",
  "nota.manual": "Nota lançada à mão", "rm.sincronizacao": "Sincronização com o RM",
  "aditivo.criar": "Aditivo criado", "aditivo.atualizar": "Aditivo alterado", "aditivo.cancelar": "Aditivo cancelado",
  "aditivo.assinar": "Aditivo assinado", "aditivo.carga": "Aditivos carregados do legado",
  "contrato.criar": "Obra criada", "contrato.atualizar": "Obra alterada", "contrato.mudar_estado": "Mudança de estado da obra",
  "contrato.encerramento": "Obra em encerramento", "cronograma.nova_versao": "Nova versão do cronograma",
  "certidao.marcar_estado": "Estado da certidão alterado", "certidao_tipo.criar": "Tipo de certidão criado",
  "certidao.registrar": "Certidão registrada", "certidao.nao_se_aplica": "Certidão marcada como não se aplica",
  "regularidade.registrar": "Regularidade registrada", "regularidade.competencia_corrigida": "Competência da regularidade corrigida",
  "entidade.criar": "Entidade criada", "entidade.coligada_rm": "Coligada do RM da entidade", "entidade.desativar": "Entidade desativada",
  "correio.envio": "E-mail enviado", "correio.assinatura": "Assinatura de e-mail gravada",
  "cadastro.aplicar": "Cadastro aplicado", "cadastro.orgao": "Cadastro: órgão", "cadastro.entidade": "Cadastro: entidade",
  "cadastro.consorciadas": "Cadastro: consorciadas", "cadastro.contrato": "Cadastro: obra", "cadastro.datas_base": "Cadastro: datas-base",
  "cadastro.fiscal": "Cadastro: fiscal", "cadastro.pleito": "Cadastro: pleito", "cadastro.instrumento": "Cadastro: instrumento",
  "cadastro.geral": "Cadastro: geral", "cadastro.espelho": "Cadastro: espelho",
};
const ROTULO_ENTIDADE: Record<string, string> = {
  medicao: "Medição", contrato: "Obra", usuario: "Usuário", entidade: "Entidade", orgao: "Órgão", instrumento: "Instrumento",
  aditivo: "Aditivo", cadastro: "Cadastro", cadastro_geral: "Cadastro geral", certidao: "Certidão", certidao_tipo: "Tipo de certidão",
  regularidade: "Regularidade", protocolo: "Protocolo", pleito: "Pleito", envio: "E-mail", nota: "Nota", nf: "NF",
};

/** A acao de um evento em portugues ("medicao.protocolo" vira "Protocolo da medição"); sem rotulo, o codigo legivel
 *  ("algo.novo_aqui" vira "Algo novo aqui"). */
export function rotuloAcao(acao: string): string {
  if (ROTULO_ACAO[acao]) return ROTULO_ACAO[acao];
  const texto = acao.replace(/[._]+/g, " ").trim();
  return texto.charAt(0).toUpperCase() + texto.slice(1);
}

/** O objeto de um evento em portugues ("medicao 700" vira "Medição 700"); sem entidade, "—". */
export function rotuloObjeto(entidade: string | null, id?: string | null): string {
  if (!entidade) return "—";
  const nome = ROTULO_ENTIDADE[entidade] ?? entidade.charAt(0).toUpperCase() + entidade.slice(1).replace(/_/g, " ");
  return id ? `${nome} ${id}` : nome;
}

/** O campo do formulario de Novo usuario a que a mensagem de erro da API se refere (para o aria-invalid), se der para saber. */
export function campoDoErroDeUsuario(msg: string): "nome" | "email" | "senha" | "perfil" | null {
  if (/senha/i.test(msg)) return "senha";
  if (/e-?mail/i.test(msg)) return "email";
  if (/perfil/i.test(msg)) return "perfil";
  if (/nome/i.test(msg)) return "nome";
  return null;
}

/** A pessoa de um evento, como o filtro a guarda na URL: o id do usuario, ou "sistema" quando nao ha usuario. */
export function pessoaDoEvento(e: Evento): string {
  return e.usuario_id === null ? "sistema" : String(e.usuario_id);
}

/** Os eventos que passam nos filtros: a acao exata, a pessoa, e `desde` (AAAA-MM-DD) pelo dia de Cuiaba do evento. */
export function filtrarEventos(eventos: Evento[], f: FiltroAuditoria): Evento[] {
  return eventos.filter(e => (!f.acao || e.acao === f.acao)
    && (!f.pessoa || pessoaDoEvento(e) === f.pessoa)
    && (!f.desde || (diaLocal(e.criado_em) ?? "") >= f.desde));
}
