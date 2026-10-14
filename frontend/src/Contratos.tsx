import { useEffect, useRef, useState } from "react";
import type { Aviso, Nivel } from "./Alertas";
import { api, ApiErro } from "./api";
import { STATUS, type StatusObra } from "./ContratoPagina";
import { IconeAlerta } from "./icones";
import {
  avisosParaLeitor, avisosPorObra, classePrazo, contagemObras, filtrarObras, nivelDoPrazo, nomeDaObra, prazoDaObra,
  quandoVence, rotuloCriticos, type ObraLista, type PrazoObra,
} from "./listaObras";
import { fmtDias } from "./formato";
import { brl } from "./Medicoes";
import { Link, trocarBusca, type Busca, type Ir } from "./rota";
import { fmtDataPura } from "./tempo";
import Rolagem from "./Rolagem";
import Selo from "./Selo";

// Obras (NAVEGACAO.md › Obras): a lista para achar uma obra e saber quando ela termina. Valores cheios. Filtros na
// URL: ?situacao=todas, ?orgao=, ?termina=90|180, ?q=. O nome da empresa vem de /api/entidades, pelo id que a lista
// ja' manda; os avisos, do /api/inicio, pela obra. O cadastro (contrato, aditivo, entidade) e' editado pelo Leonardo
// em arquivo (`cadastro/*.yaml` + `python -m app.cli cadastro aplicar`); a tela so' mostra.

type Entidade = { id: number; nome: string; nome_curto?: string | null };

function status(c: ObraLista): StatusObra {
  return (c.estado === "ativo" && c.encerramento_iniciado_em ? "em_encerramento" : c.estado) as StatusObra;
}

/** O fim (execucao ou vigencia) com os dias do servidor embaixo, na palavra dos Avisos ("vence em N dias", "vence
 *  hoje", "venceu ha' N dias") e na cor do nivel do aviso da obra (`nivel`; sem aviso, neutro). Obra paralisada
 *  (`paralisada`, so' na execucao): "Paralisada desde DD/MM/AAAA" em Atencao, sem contar o vencimento (D16). */
function Fim({ fim, dias, automatica, nivel: nivelDoAviso = null, aberta = true, paralisada }: {
  fim?: string | null; dias?: number | null; automatica?: boolean; nivel?: Nivel | null; aberta?: boolean;
  paralisada?: { desde: string | null };
}) {
  if (!fim && !paralisada) return <>—</>;
  // o nivel tambem vai em forma (triangulo no Critico, ponto na Atencao), nao so' na cor (F-58)
  const nivel = nivelDoPrazo(nivelDoAviso, dias, aberta);
  return (
    <>
      {fim ? fmtDataPura(fim.slice(0, 10)) : "—"}
      {paralisada ? (
        <div className="campo__nota prazo--atencao prazo--paralisada">
          {paralisada.desde ? <>Paralisada desde <span className="sem-quebra">{fmtDataPura(paralisada.desde.slice(0, 10))}</span></> : "Paralisada"}
        </div>
      ) : fim && dias !== null && dias !== undefined && (
        <div className={`campo__nota prazo--data${classePrazo(nivel)}`}>
          {nivel === "critico" ? <IconeAlerta className="icone icone--p" /> : nivel ? <span className="prazo__ponto" aria-hidden="true" /> : null}
          {quandoVence(dias)}
        </div>
      )}
      {fim && automatica && <div className="campo__nota">o órgão prorroga junto</div>}
    </>
  );
}

/** A coluna Avisos: a contagem; com critico, "N críticos" no selo do nivel (triangulo + palavra) e o total embaixo. */
function AvisosDaObra({ obra, prazo }: { obra: ObraLista; prazo: PrazoObra }) {
  const c = prazo.criticos;
  return (
    <>
      <Link para={{ tela: "avisos" }} busca={{ obra: String(obra.id) }}>
        <span aria-hidden="true">{c > 0 ? <Selo classe="selo--acao" title={rotuloCriticos(c)}>{c}<span className="criticos__palavra">{c === 1 ? " crítico" : " críticos"}</span></Selo> : prazo.total}</span>
        <span className="sr-only">{avisosParaLeitor(prazo, nomeDaObra(obra))}</span>
      </Link>
      {c > 0 && prazo.total > c && <div className="campo__nota sem-quebra" aria-hidden="true">de {prazo.total}{"\u00a0"}avisos</div>}
    </>
  );
}

export default function Contratos({ ir, busca = {} }: { ir: Ir; busca?: Busca }) {
  const [lista, setLista] = useState<ObraLista[] | null>(null);
  const [empresas, setEmpresas] = useState<Map<number, string> | null>(new Map());
  const [avisos, setAvisos] = useState<Map<number, Aviso[]> | null | undefined>(undefined);
  const [erro, setErro] = useState("");

  useEffect(() => {
    let vivo = true;
    api<ObraLista[]>("/api/contratos").then(l => { if (vivo) setLista(l); })
      .catch(e => { if (vivo) setErro(e instanceof ApiErro ? e.message : String(e)); });
    // o nome da empresa e o numero de avisos completam a linha; sem eles, a lista continua
    api<Entidade[]>("/api/entidades")
      .then(l => { if (vivo) setEmpresas(new Map(l.map(e => [e.id, e.nome_curto || e.nome]))); })
      .catch(() => { if (vivo) setEmpresas(null); });
    api<{ avisos: Aviso[] }>("/api/inicio").then(d => { if (vivo) setAvisos(avisosPorObra(d.avisos)); })
      .catch(() => { if (vivo) setAvisos(null); });
    return () => { vivo = false; };
  }, []);

  const todas = busca.situacao === "todas";
  const termina = busca.termina === "90" ? 90 : busca.termina === "180" ? 180 : null;
  const orgao = busca.orgao || null;
  const q = busca.q ?? "";
  const [texto, setTexto] = useState(q);
  const espera = useRef<number | undefined>(undefined);
  // a URL mudou por fora (Voltar, "Limpar os filtros"): o campo acompanha, menos enquanto a pessoa digita nele
  useEffect(() => { if (document.activeElement?.id !== "obras-busca") setTexto(q); }, [q]);
  useEffect(() => () => window.clearTimeout(espera.current), []);
  const digitar = (v: string) => {
    setTexto(v);
    window.clearTimeout(espera.current);
    espera.current = window.setTimeout(() => trocarBusca({ q: v || null }), 300);
  };
  const temFiltro = Object.keys(busca).some(k => ["situacao", "termina", "orgao", "q"].includes(k));
  // o prazo de cada obra, lido dos avisos ja' carregados; a paralisada nao conta o vencimento da execucao (D16)
  const prazos = new Map((lista ?? []).map(o => [o.id, prazoDaObra(o, avisos?.get(o.id))] as const));
  const paralisadas = new Set([...prazos].filter(([, p]) => p.paralisada).map(([id]) => id));
  const filtradas = lista ? filtrarObras(lista, { todas, orgao, termina, q, paralisadas }) : [];
  const { titulo, detalhe } = contagemObras(filtradas.length, lista?.length ?? 0, { todas, termina, orgao, q });
  const orgaos = lista ? [...new Set(lista.map(o => o.orgao))].sort((a, b) => a.localeCompare(b, "pt-BR")) : [];
  const aqui = { tela: "obras" as const };
  const com = (m: Record<string, string | null>): Busca => {
    const b: Busca = { ...busca };
    for (const [k, v] of Object.entries(m)) { if (v === null) delete b[k]; else b[k] = v; }
    return b;
  };

  return (
    <section className="cartao" aria-labelledby="titulo-obras">
      <div className="cartao__cabeca">
        {/* o titulo diz quantas obras a tela mostra (o h1 ja' e' "Obras"); o recorte em vigor, em palavras, fica ao lado
            (o que o filtro deixa de fora, tambem) */}
        <h2 className="cartao__titulo" id="titulo-obras">{lista ? <span role="status">{titulo}</span> : "Lista de obras"}</h2>
        {lista && detalhe && <span className="cartao__dica num">{detalhe}</span>}
      </div>
      {!lista && !erro && <div className="vazio"><p>Carregando as obras…</p></div>}
      {erro && <div className="cartao__corpo"><p className="erro" role="alert">
        <IconeAlerta className="icone icone--p" />{erro} Recarregue a página para tentar de novo.
      </p></div>}
      {lista && (
        <div className="cartao__corpo filtros-avisos__linhas">
          <p className="filtros-avisos__linha">
            <span className="resumo__rotulo">Terminam</span>
            <Link para={aqui} busca={com({ termina: "90" })} aria-current={termina === 90 ? "true" : undefined}>em 90 dias</Link>
            <Link para={aqui} busca={com({ termina: "180" })} aria-current={termina === 180 ? "true" : undefined}>em 6 meses</Link>
            <Link para={aqui} busca={com({ termina: null })} aria-current={termina === null ? "true" : undefined}>em qualquer data</Link>
          </p>
          <div className="form-inline">
            <div className="campo">
              <label className="campo__rotulo" htmlFor="obras-busca">Buscar</label>
              <input id="obras-busca" type="search" value={texto} placeholder="Coxipó, 161/2022…" autoComplete="off" spellCheck={false}
                onChange={e => digitar(e.target.value)} />
            </div>
            <div className="campo">
              <label className="campo__rotulo" htmlFor="obras-orgao">Órgão</label>
              <select id="obras-orgao" value={orgao ?? ""} onChange={e => trocarBusca({ orgao: e.target.value || null })}>
                <option value="">Todos</option>
                {orgao && !orgaos.includes(orgao) && <option value={orgao}>{orgao}</option>}
                {orgaos.map(o => <option key={o} value={o}>{o}</option>)}
              </select>
            </div>
            <div className="campo">
              <label className="campo__rotulo" htmlFor="obras-situacao">Situação</label>
              <select id="obras-situacao" value={todas ? "todas" : ""} onChange={e => trocarBusca({ situacao: e.target.value || null })}>
                <option value="">Sem as encerradas</option>
                <option value="todas">Todas, com as encerradas</option>
              </select>
            </div>
          </div>
        </div>
      )}
      {/* o "—" da empresa e dos avisos nao pode querer dizer "falhou": a falha e' dita aqui */}
      {lista && (empresas === null || avisos === null) && (
        <div className="cartao__corpo"><p className="campo__nota" role="alert">
          Não foi possível carregar {[empresas === null && "os nomes das empresas", avisos === null && "os avisos"].filter(Boolean).join(" nem ")};
          recarregue a página para tentar de novo.
        </p></div>
      )}
      {lista && filtradas.length === 0 && (
        <div className="vazio vazio--curto">
          {lista.length === 0 ? <p className="vazio__titulo">Nenhuma obra no cadastro.</p> : temFiltro ? (
            <><p className="vazio__titulo">Nenhuma obra com esses filtros.</p><p><Link para={aqui}>Limpar os filtros</Link></p></>
          ) : (
            <><p className="vazio__titulo">Nenhuma obra sem as encerradas.</p><p><Link para={aqui} busca={com({ situacao: "todas" })}>Mostrar as encerradas</Link></p></>
          )}
        </div>
      )}
      {lista && filtradas.length > 0 && (
        <Rolagem rotulo="Obras" alta>
          <table className="tabela obras-lista">
            <caption className="sr-only">Obras{termina ? `, que terminam em ${termina === 90 ? "90 dias" : "6 meses"}` : ""}</caption>
            <thead>
              <tr>
                <th scope="col">Obra</th><th scope="col">Órgão</th><th scope="col">Empresa</th><th scope="col">Status</th>
                <th scope="col" className="col-num">Valor vigente</th><th scope="col" className="col-data">Fim da execução</th>
                <th scope="col" className="col-data">Fim da vigência</th><th scope="col">Pedido de prorrogação</th><th scope="col" className="col-num">Avisos</th>
              </tr>
            </thead>
            <tbody>
              {filtradas.map((c, i) => {
                const s = STATUS[status(c)] ?? { rotulo: c.estado, classe: "" };
                const prazo = prazos.get(c.id) ?? prazoDaObra(c);
                const p = c.pedido_prorrogacao;
                return (
                  <tr key={c.id} className={`linha${i % 2 === 1 ? " par" : ""}`}>
                    <td>
                      <Link className="nome-link truncar-2l" title={nomeDaObra(c)} para={{ tela: "obra", id: c.id, aba: "medicoes" }} ir={ir}>{nomeDaObra(c)}</Link>
                      {c.nome_curto && <div className="campo__nota num">{c.numero_instrumento}</div>}
                    </td>
                    <td><span className="truncar-2l" title={c.orgao}>{c.orgao}</span></td>
                    <td>{c.entidade_id != null && empresas ? empresas.get(c.entidade_id) ?? "—" : "—"}</td>
                    <td><Selo classe={s.classe}>{s.rotulo}</Selo></td>
                    <td className="col-num dinheiro num">{c.valor_vigente_centavos != null ? brl(c.valor_vigente_centavos) : "—"}</td>
                    <td className="num">
                      <Fim fim={c.execucao_fim_vigente} dias={c.dias_execucao} nivel={prazo.execucao} aberta={status(c) === "ativo"}
                        paralisada={prazo.paralisada ? { desde: prazo.paralisadaDesde } : undefined} />
                    </td>
                    <td className="num"><Fim fim={c.vigencia_fim_vigente} dias={c.dias_vigencia} automatica={c.vigencia_automatica} nivel={prazo.vigencia}
                      aberta={status(c) === "ativo" && !c.vigencia_automatica} /></td>
                    <td className="pedido">{p ? (
                      <Link para={{ tela: "obra", id: c.id, aba: "prazos" }}>
                        <span className="sem-quebra">{p.numero_oficio ?? "ofício"}</span>{p.dias === null ? "" : p.dias === 0 ? ", hoje" : `, há\u00a0${fmtDias(p.dias)}`}
                      </Link>
                    ) : "—"}</td>
                    <td className="col-num num">{avisos === null || prazo.total === 0 ? "—" : <AvisosDaObra obra={c} prazo={prazo} />}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </Rolagem>
      )}
    </section>
  );
}
