// Regras de APRESENTACAO da matriz de Documentos (NAVEGACAO.md › Documentos): funcoes puras sobre /api/documentos.
// A situacao de cada certidao (em dia, vencendo, vencida, faltando) e' do servidor; aqui so' se conta, filtra e ordena.

export type CertidaoDoc = { id: number; emissao: string; validade: string; natureza: string | null;
  leitura?: string | null };    // "manual" = digitada (A-19, 10/10/2026)
export type LinhaCertidao = {
  tipo_id: number; chave: string; tipo: string; link_emissao: string | null; exigida: boolean;
  situacao: "ok" | "vencendo" | "vencida" | "faltando" | "nao_se_aplica"; dias: number | null;
  certidao: CertidaoDoc | null;
};
export type RegularidadeDoc = { situacao: "ok" | "atrasada" | "faltando"; competencia: string | null; esperada: string };
export type EmpresaDoc = {
  entidade_id: number; entidade: string; cnpj: string; papel: string; certidoes: LinhaCertidao[];
  regularidade_exigida: boolean; regularidade: RegularidadeDoc | null;
  obras?: { contrato_id: number; obra: string }[];      // A7: as obras ativas que exigem a empresa
};

// Decisao 5 do mapa: "antes do proximo protocolo" vira "vence em ate' 30 dias".
export const JANELA_DIAS = 30;

/** Pendencia de uma certidao: exigida e vencida, faltando ou vencendo em ate' 30 dias (os dias sao do servidor). */
export function certidaoPendente(l: LinhaCertidao): boolean {
  if (!l.exigida) return false;
  if (l.situacao === "vencida" || l.situacao === "faltando") return true;
  return (l.situacao === "ok" || l.situacao === "vencendo") && l.dias !== null && l.dias <= JANELA_DIAS;
}

/** Quantas pendencias a empresa tem: as certidoes e a regularidade do mes que nao esta' em dia. */
export function pendenciasDa(e: EmpresaDoc): number {
  const reg = e.regularidade && e.regularidade.situacao !== "ok" ? 1 : 0;
  return e.certidoes.filter(certidaoPendente).length + reg;
}

/** 0 = o que ja' trava (certidao exigida vencida ou faltando, regularidade fora do dia); 1 = o que vence em ate'
 *  30 dias; 2 = nada pendente. */
export function gravidade(e: EmpresaDoc): number {
  const trava = e.certidoes.some(l => l.exigida && (l.situacao === "vencida" || l.situacao === "faltando"))
    || (e.regularidade !== null && e.regularidade.situacao !== "ok");
  return trava ? 0 : pendenciasDa(e) > 0 ? 1 : 2;
}

/** Os dias da certidao exigida que vence primeiro (dentro da janela), para desempatar pela mais urgente. */
function menorDias(e: EmpresaDoc): number {
  return Math.min(999, ...e.certidoes.filter(l => l.exigida && l.dias !== null && certidaoPendente(l)).map(l => l.dias!));
}

/** Pela gravidade (o que ja' trava, o que vence, o resto), depois pela que vence primeiro, depois a ordem do
 *  servidor; `soPendentes` e' o filtro da URL. */
export function matriz(empresas: EmpresaDoc[], soPendentes: boolean): EmpresaDoc[] {
  const ordem = new Map(empresas.map((e, i) => [e.entidade_id, i]));
  return empresas.filter(e => !soPendentes || pendenciasDa(e) > 0)
    .sort((a, b) => gravidade(a) - gravidade(b) || menorDias(a) - menorDias(b)
      || ordem.get(a.entidade_id)! - ordem.get(b.entidade_id)!);
}

/** As colunas da matriz: os tipos de certidao que alguma empresa tem, na ordem dada. */
export function colunas(empresas: EmpresaDoc[], ordem: string[]): string[] {
  const tem = new Set(empresas.flatMap(e => e.certidoes.map(l => l.chave)));
  return [...ordem.filter(c => tem.has(c)), ...[...tem].filter(c => !ordem.includes(c))];
}
