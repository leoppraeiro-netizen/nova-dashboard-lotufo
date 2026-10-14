import { useCallback, useEffect, useState } from "react";
import CaixaAviso from "./CaixaAviso";
import { api, apiForm, ApiErro } from "./api";
import { brl } from "./formato";
import { IconeAlerta } from "./icones";
import { ir, Link, trocarBusca, type Busca } from "./rota";
import { fmtDataPura, hojeLocal } from "./tempo";
import "./notas.css";

// Notas a enviar (2026-10-09; plano docs/superpowers/plans/2026-10-09-notas-envio.md): as notas emitidas que
// ainda nao foram ao contratante, por grupo de orgao, e o painel do envio escolhido. As regras (o que vai junto,
// o que bloqueia) moram no servidor (GET /api/notas/a-enviar); a tela so' desenha.

export type ItemEnvio = {
  chave: string; rotulo: string; detalhe?: string | null; estado: "ok" | "aviso" | "falta" | "vencida";
  acao?: string | null; entidade_id?: number | null; competencia?: string | null; medicao_id?: number | null;
};
export type NotaEnvio = { numero: string; natureza: string; municipio?: string | null; arquivo?: string | null; valor_centavos: number };
export type Envio = {
  chave: string; contrato_id: number; obra: string; orgao: string; orgao_sub?: string | null; familia: string;
  grupo: string; a_pedido: boolean; medicao_ids: number[]; descricao: string; notas: NotaEnvio[];
  valor_centavos: number; emitida_em: string | null; dias: number | null; situacao: string;
  aviso: string | null; itens: ItemEnvio[]; protocolo_id: number | null;
};
export type ListaEnvios = { envios: Envio[]; contadores: Record<string, number> };

const GRUPOS = ["SINFRA", "MTPAR", "SES-MT", "Pref. VG", "Pref. Cuiabá"];

export function mensagem(e: unknown): string {
  return e instanceof ApiErro ? e.message : String(e);
}

/** "4 notas de 08/10/2026" / "NF 2322 de 08/10/2026" */
export function notasDe(e: Envio): string {
  const qtd = e.notas.length === 1 ? `NF ${e.notas[0].numero}` : `${e.notas.length} notas`;
  return e.emitida_em ? `${qtd} de ${fmtDataPura(e.emitida_em)}` : qtd;
}

function emitida(e: Envio): string {
  const plural = e.notas.length > 1;
  if (e.dias === null) return "";
  if (e.dias <= 0) return plural ? "emitidas hoje" : "emitida hoje";
  if (e.dias === 1) return plural ? "emitidas ontem" : "emitida ontem";
  return `${plural ? "emitidas" : "emitida"} há ${e.dias} dias`;
}

/** Inicia (ou reabre) o protocolo do envio com estas medicoes; devolve o id. */
export async function iniciarEnvio(contratoId: number, medicaoIds: number[], familia?: string): Promise<number> {
  const corpo: Record<string, unknown> = { contrato_id: contratoId, medicao_ids: medicaoIds };
  // MTPAR, SES e prefeituras levam carta com numero de oficio; a SINFRA (etapa nota) nao.
  if (familia && familia !== "sinfra") {
    const n = window.prompt("Número do ofício desta nota (só o número, ex.: 361)");
    if (n === null) throw new Error("Envio não iniciado: informe o número do ofício.");
    corpo.numero_oficio = n.trim();
  }
  const r = await api<{ protocolo_id: number }>("/api/notas/envio/iniciar", { method: "POST",
    body: JSON.stringify(corpo) });
  return r.protocolo_id;
}

const ESTADO_ITEM: Record<ItemEnvio["estado"], string> = { ok: "Pronto", aviso: "Atenção", falta: "Falta", vencida: "Vencida" };

/** Check (pronto/concluido); serve tambem ao passo concluido do envio. */
export function IconeCheck() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3.5" strokeLinecap="round"
      strokeLinejoin="round" aria-hidden="true"><path d="M20 6L9 17l-5-5" /></svg>
  );
}

/** Estado do item: a forma (check verde, "!" ambar ou vermelho) e a palavra (leitor de tela e title). */
function EstadoItem({ estado }: { estado: ItemEnvio["estado"] }) {
  const e = ESTADO_ITEM[estado] ? estado : "aviso";
  return (
    <span className={`nota-estado nota-estado--${e}`} title={ESTADO_ITEM[e]}>
      {e === "ok" ? <IconeCheck /> : <span aria-hidden="true">!</span>}
      <span className="sr-only">{ESTADO_ITEM[e]}</span>
    </span>
  );
}

/** O que vai junto no e-mail: um item por documento, com o estado (forma + palavra) e o detalhe. A regularidade
 *  que falta ganha o "Anexar" (o mesmo upload da tela de Documentos); quem so' consulta (B-09) nao ve o "Anexar". */
export function ItensEnvio({ itens, aoMudar, podeEditar = true }: { itens: ItemEnvio[]; aoMudar: () => void; podeEditar?: boolean }) {
  const [erro, setErro] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const [sobre, setSobre] = useState<string | null>(null);

  async function anexar(it: ItemEnvio, input: HTMLInputElement) {
    const f = input.files?.[0];
    input.value = "";
    if (!f) return;
    const fd = new FormData();
    fd.append("arquivo", f);
    fd.append("entidade_id", String(it.entidade_id));
    // sem "competencia": o servidor usa a impressa no PDF (o mes sugerido gravou o Integra 08/2026 como 07, 09/10/2026)
    setOcupado(true); setErro("");
    try { await apiForm("/api/documentos/regularidades", fd); aoMudar(); } catch (e) { setErro(mensagem(e)); } finally { setOcupado(false); }
  }

  // FRC assinada (2026-10-09): o PDF assinado no DocuSign entra como a fatura do consorcio da medicao
  async function anexarFrc(it: ItemEnvio, arquivos: FileList | null) {
    const f = Array.from(arquivos ?? []).find(x => x.type === "application/pdf" || x.name.toLowerCase().endsWith(".pdf"));
    if (!f || !it.medicao_id) return;
    const fd = new FormData();
    fd.append("arquivo", f);
    fd.append("tipo_doc", "fatura");
    setOcupado(true); setErro("");
    try { await apiForm(`/api/medicoes/${it.medicao_id}/notas`, fd); aoMudar(); } catch (e) { setErro(mensagem(e)); } finally { setOcupado(false); }
  }

  return (
    <>
      <ul className="nota-itens">
        {itens.map(it => {
          if (it.acao === "anexar_frc" && podeEditar) {
            return (
              <li key={it.chave}>
                <EstadoItem estado={it.estado} />
                <span className="nota-item nota-item--soltar">
                  <span className="nota-item__texto">
                    <span>{it.rotulo}</span>
                    {it.detalhe && <span className={`nota-item__detalhe nota-item__detalhe--${it.estado}`}>{it.detalhe}</span>}
                  </span>
                  <span className={`nota-complementares__soltar${sobre === it.chave ? " nota-complementares__soltar--sobre" : ""}`}
                    onDragOver={ev => { ev.preventDefault(); if (sobre !== it.chave) setSobre(it.chave); }}
                    onDragLeave={() => setSobre(null)}
                    onDrop={ev => { ev.preventDefault(); setSobre(null); if (!ocupado) void anexarFrc(it, ev.dataTransfer.files); }}>
                    <span>{ocupado ? "Anexando…" : "Arraste a FRC assinada aqui ou"}</span>
                    <label className="btn espelho__anexar nota-anexar">
                      Anexar
                      <input type="file" accept="application/pdf" className="espelho__arquivo" disabled={ocupado}
                        aria-label={`Anexar ${it.rotulo}`} onChange={ev => { const fs = ev.currentTarget.files; void anexarFrc(it, fs); ev.currentTarget.value = ""; }} />
                    </label>
                  </span>
                </span>
              </li>
            );
          }
          return (
            <li key={it.chave}>
              <EstadoItem estado={it.estado} />
              <span className="nota-item">
                <span className="nota-item__texto">
                  <span>{it.rotulo}</span>
                  {it.detalhe && <span className={`nota-item__detalhe nota-item__detalhe--${it.estado}`}>{it.detalhe}</span>}
                </span>
                {podeEditar && it.acao === "anexar_regularidade" && (it.entidade_id && it.competencia ? (
                  <label className="btn espelho__anexar nota-anexar">
                    {ocupado ? "Anexando…" : "Anexar"}
                    <input type="file" accept="application/pdf" className="espelho__arquivo" disabled={ocupado}
                      aria-label={`Anexar ${it.rotulo}`} onChange={ev => void anexar(it, ev.currentTarget)} />
                  </label>
                ) : <Link className="btn nota-anexar" para={{ tela: "documentos" }}>Anexar</Link>)}
              </span>
            </li>
          );
        })}
      </ul>
      {erro && <p className="erro" role="alert"><IconeAlerta className="icone icone--p" />{erro}</p>}
    </>
  );
}

/** "Registrar envio feito por fora": o e-mail ja' saiu pelo Outlook; data (obrigatoria), observacao e o .eml. */
export function EnvioPorFora({ medicaoIds, aoFeito }: { medicaoIds: number[]; aoFeito: () => void }) {
  const [aberto, setAberto] = useState(false);
  const [data, setData] = useState(hojeLocal());
  const [obs, setObs] = useState("");
  const [eml, setEml] = useState<File | null>(null);
  const [ocupado, setOcupado] = useState(false);
  const [erro, setErro] = useState("");

  async function gravar(ev: React.FormEvent) {
    ev.preventDefault();
    const fd = new FormData();
    for (const id of medicaoIds) fd.append("medicao_ids", String(id));
    fd.append("enviado_em", data);
    fd.append("observacao", obs);
    if (eml) fd.append("eml", eml);
    setOcupado(true); setErro("");
    try {
      await apiForm("/api/notas/envio-externo", fd);
      setAberto(false);
      aoFeito();
    } catch (e) { setErro(mensagem(e)); } finally { setOcupado(false); }
  }

  return (
    <div className="nota-porfora">
      <button type="button" className="botao-link" onClick={() => setAberto(true)}>Registrar envio feito por fora</button>
      <p className="nota-porfora__dica">Quando o e-mail já saiu pelo Outlook: informe a data e anexe o e-mail enviado.</p>
      {aberto && (
        <div className="ol-modal-fundo" role="presentation" onMouseDown={() => setAberto(false)}>
          <form className="cartao nota-modal" role="dialog" aria-modal="true" aria-labelledby="titulo-porfora"
            onMouseDown={ev => ev.stopPropagation()} onKeyDown={ev => { if (ev.key === "Escape") setAberto(false); }} onSubmit={gravar}>
            <div className="cartao__cabeca"><h2 className="cartao__titulo" id="titulo-porfora">Registrar envio feito por fora</h2></div>
            <div className="cartao__corpo pilha">
              <div className="campo">
                <label className="campo__rotulo" htmlFor="porfora-data">Data do envio (obrigatória)</label>
                <input id="porfora-data" type="date" required autoFocus value={data} max={hojeLocal()} onChange={e => setData(e.target.value)} />
              </div>
              <div className="campo">
                <label className="campo__rotulo" htmlFor="porfora-obs">Observação</label>
                <textarea id="porfora-obs" rows={3} maxLength={2000} value={obs} onChange={e => setObs(e.target.value)} />
              </div>
              <div className="campo">
                <label className="campo__rotulo" htmlFor="porfora-eml">E-mail enviado (.eml, opcional)</label>
                <input id="porfora-eml" type="file" accept=".eml,message/rfc822" onChange={e => setEml(e.target.files?.[0] ?? null)} />
              </div>
              {erro && <p className="erro" role="alert"><IconeAlerta className="icone icone--p" />{erro}</p>}
              <div className="form-inline">
                <button type="submit" className="btn btn--primario" disabled={ocupado || !data}>{ocupado ? "Gravando…" : "Registrar"}</button>
                <button type="button" className="btn" onClick={() => setAberto(false)}>Cancelar</button>
              </div>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}

function Painel({ e, aoMudar, podeEditar }: { e: Envio; aoMudar: (msg?: string) => void; podeEditar: boolean }) {
  const [ocupado, setOcupado] = useState(false);
  const [erro, setErro] = useState("");
  const bloqueado = e.situacao === "bloqueado";

  async function enviar() {
    // o envio acontece na etapa 4 da pagina da medicao (opcao A, 2026-10-09); o protocolo e' iniciado aqui
    // para o numero do oficio ser pedido uma vez so'
    setOcupado(true); setErro("");
    try {
      if (!e.protocolo_id) await iniciarEnvio(e.contrato_id, e.medicao_ids, e.familia);
      ir({ tela: "medicao", obra: e.contrato_id, id: e.medicao_ids[0] }, { secao: "etapa-4" });
    }
    catch (x) { setErro(mensagem(x)); setOcupado(false); }
  }

  return (
    <section className="nota-painel" aria-labelledby="titulo-envio">
      <div className="nota-painel__bloco">
        <h2 className="nota-painel__titulo" id="titulo-envio">{e.obra} — {e.descricao}</h2>
        <p className="nota-painel__meta">{[e.orgao, e.orgao_sub, notasDe(e)].filter(Boolean).join(" · ")}</p>
      </div>
      <div className="nota-painel__bloco">
        <p className="nota-painel__valor nota-mono">{brl(e.valor_centavos)}</p>
        {e.notas.length > 1 && <p className="nota-painel__meta">Soma das {e.notas.length} notas</p>}
      </div>
      <div className="nota-painel__junto">
        <span className="nota-painel__sub">O que vai junto</span>
        <ItensEnvio itens={e.itens} aoMudar={() => aoMudar()} podeEditar={podeEditar} />
      </div>
      {bloqueado && <CaixaAviso nivel="critico">{e.aviso ?? "Envio bloqueado."}</CaixaAviso>}
      {/* B-09 (10/10/2026): a diretoria via o botao e recebia 403; quem so' consulta nao ve as acoes */}
      {podeEditar && <div className="nota-painel__acao">
        <button type="button" className="btn btn--primario nota-principal" disabled={bloqueado || ocupado} onClick={() => void enviar()}>
          {ocupado ? "Abrindo…" : "Enviar a nota →"}
        </button>
        {erro && <p className="erro" role="alert"><IconeAlerta className="icone icone--p" />{erro}</p>}
        {!bloqueado && <EnvioPorFora medicaoIds={e.medicao_ids}
          aoFeito={() => aoMudar(`Envio registrado: ${e.obra} · ${e.descricao} foi para Aguardando pagamento.`)} />}
      </div>}
    </section>
  );
}

export default function NotasAEnviar({ busca, podeEditar }: { busca: Busca; podeEditar: boolean }) {
  const [dados, setDados] = useState<ListaEnvios | null>(null);
  const [erro, setErro] = useState("");
  const [sel, setSel] = useState<string | null>(null);
  const [feito, setFeito] = useState(busca.enviada ? `Nota enviada: ${busca.enviada}. Ela está em Aguardando pagamento.`
    : busca.registrada ? `Envio registrado: ${busca.registrada} foi para Aguardando pagamento.` : "");

  const carregar = useCallback(async () => {
    try { setDados(await api<ListaEnvios>("/api/notas/a-enviar")); setErro(""); } catch (e) { setErro(mensagem(e)); }
  }, []);
  useEffect(() => { void carregar(); }, [carregar]);

  const grupo = busca.grupo ?? "";
  const q = busca.q ?? "";
  const termo = q.trim().toLocaleLowerCase("pt-BR");
  const envios = dados?.envios ?? [];
  const filtrados = envios.filter(e => (!grupo || e.grupo === grupo)
    && (!termo || [e.obra, e.descricao, e.orgao, ...e.notas.map(n => n.numero)].join(" ").toLocaleLowerCase("pt-BR").includes(termo)));
  const atual = filtrados.find(e => e.chave === sel) ?? filtrados[0] ?? null;
  const grupos = [...GRUPOS, ...[...new Set(envios.map(e => e.grupo))].filter(g => !GRUPOS.includes(g))];
  const contador = (g: string) => dados?.contadores[g] ?? envios.filter(e => !g || e.grupo === g).length;
  const comGrupo = (g: string): Busca => (g ? { ...(q ? { q } : {}), grupo: g } : (q ? { q } : {}));

  if (!dados) {
    return erro
      ? <div className="form-inline"><p className="erro" role="alert"><IconeAlerta className="icone icone--p" />Não foi possível ler as notas a enviar: {erro}</p>
          <button type="button" className="btn btn--pequeno" onClick={() => void carregar()}>Tentar de novo</button></div>
      : <p className="campo__nota">Carregando as notas…</p>;
  }

  return (
    <div className="pilha notas-v3">
      <p className={feito ? "notas__ok" : "sr-only"} role="status">{feito}</p>
      <div className="nota-busca-caixa">
        <svg className="nota-busca__lupa" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
          strokeWidth="2" strokeLinecap="round" aria-hidden="true"><circle cx="11" cy="11" r="7" /><path d="M21 21l-4.3-4.3" /></svg>
        <input type="search" className="nota-busca" placeholder="Buscar nota ou obra…" aria-label="Buscar nota ou obra"
          autoComplete="off" value={q} onChange={e => trocarBusca({ q: e.target.value || null })} />
      </div>
      <div className="nota-pilulas" role="group" aria-label="Órgão">
        <Link className="nota-pilula" para={{ tela: "medicoes", aba: "enviar-nota" }} busca={comGrupo("")} aria-current={grupo === "" ? "true" : undefined}>
          Todas{" "}<span className="nota-pilula__n num">{contador("Todas")}</span>
        </Link>
        {grupos.map(g => (
          <Link key={g} className="nota-pilula" para={{ tela: "medicoes", aba: "enviar-nota" }} busca={comGrupo(g)} aria-current={grupo === g ? "true" : undefined}>
            {g}{" "}<span className="nota-pilula__n num">{contador(g)}</span>
          </Link>
        ))}
      </div>

      {envios.length === 0 ? (
        <section className="cartao nota-vazia" aria-label="Notas a enviar">
          <div className="vazio">
            <span className="nota-vazia__icone" aria-hidden="true">
              <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"
                strokeLinecap="round" strokeLinejoin="round"><path d="M20 6L9 17l-5-5" /></svg>
            </span>
            <p className="vazio__titulo">Nenhuma nota a enviar</p>
            <p>As próximas aparecem aqui assim que a nota entrar pela sincronização com o RM.</p>
            <p><Link para={{ tela: "medicoes", aba: "aguardando-pagamento" }}>Ver notas aguardando pagamento</Link></p>
          </div>
        </section>
      ) : (
        <div className="nota-colunas">
          <div className="pilha">
            {filtrados.length === 0 && (
              <section className="cartao" aria-label="Notas com esses filtros">
                <div className="vazio vazio--curto">
                  <p className="vazio__titulo">Nenhuma nota com esses filtros.</p>
                  <p><Link para={{ tela: "medicoes", aba: "enviar-nota" }}>Limpar os filtros</Link></p>
                </div>
              </section>
            )}
            {grupos.map(g => {
              const itens = filtrados.filter(e => e.grupo === g);
              if (itens.length === 0) return null;
              return (
                <section key={g} className="pilha nota-grupo" aria-label={g}>
                  <h2 className="nota-grupo__titulo">{g}{itens.some(e => e.a_pedido) ? " · a pedido do órgão" : ""}</h2>
                  {itens.map(e => (
                    <button key={e.chave} type="button" className="nota-cartao" aria-pressed={atual?.chave === e.chave}
                      onClick={() => setSel(e.chave)}>
                      <span className="nota-cartao__texto">
                        <span className="nota-cartao__obra">{e.obra}</span>
                        <span className="nota-cartao__desc">
                          {[e.descricao, e.notas.length === 1 ? `NF ${e.notas[0].numero}`
                            : e.notas.length > 1 ? `${e.notas.length} notas: ${e.notas.map(n => n.numero).join(", ")}` : "", emitida(e)]
                            .filter(Boolean).join(" · ")}
                        </span>
                        {e.aviso && (
                          <CaixaAviso nivel={e.situacao === "bloqueado" ? "critico" : "atencao"} como="span">
                            {e.situacao === "bloqueado" && !/^bloque/i.test(e.aviso) ? `Bloqueado: ${e.aviso}` : e.aviso}
                          </CaixaAviso>
                        )}
                      </span>
                      <span className={`nota-cartao__valor nota-mono${e.a_pedido ? " nota-cartao__valor--espera" : ""}`}>{brl(e.valor_centavos)}</span>
                    </button>
                  ))}
                </section>
              );
            })}
          </div>
          <aside className="nota-lateral" aria-label="Envio selecionado">
            {atual && <Painel key={atual.chave} e={atual} podeEditar={podeEditar} aoMudar={msg => { if (msg) setFeito(msg); void carregar(); }} />}
          </aside>
        </div>
      )}
    </div>
  );
}
