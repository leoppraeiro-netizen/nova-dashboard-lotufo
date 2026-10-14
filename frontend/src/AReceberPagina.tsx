import { Fragment, useEffect, useState, type ReactNode } from "react";
import { api, mensagemDeErro } from "./api";
import { brl, contar, fmtDias } from "./formato";
import { IconeAlerta, IconeSeta } from "./icones";
import { Link, trocarBusca, type Busca } from "./rota";
import { fmtCompetencia } from "./tempo";
import Rolagem from "./Rolagem";

// A receber (NAVEGACAO.md › A receber; na cota da Lotufo): quanto os orgaos devem e ha' quanto tempo, por orgao e
// por faixa de dias, com o prazo normal de cada orgao (A4); a linha do orgao abre as obras dele (?orgao=N). Cada
// cobranca e' uma medicao protocolada ou uma nota em aberto no RM (A14 diz quantas de cada; os dias contam do
// protocolo ou da emissao da nota). A obra leva as medicoes em andamento dela ou, se so' tem nota do RM, ao resumo
// (A-99). Embaixo, os reajustes esperando apostilamento, um por ciclo (A13), que levam a data-base (A10). As regras
// moram em `app/diretoria.py`; o valor so' aparece com o total liberado (conciliado com a controladoria), como o atraso.

type Grupo = { quantidade: number; valor_centavos: number | null; notas_rm?: number };
type Faixas = Record<"ate_30" | "de_31_a_60" | "mais_60", Grupo>;
type ObraDoOrgao = Grupo & { contrato_id: number; obra: string; maior_dias: number | null };
type PorOrgao = Grupo & { orgao_id?: number | null; orgao: string; maior_dias: number | null; faixas?: Faixas;
  prazo_normal_dias?: number | null; obras?: ObraDoOrgao[] };
type Painel = {
  total_a_receber_liberado: boolean;
  dinheiro: { protocolado: Grupo & { faixas: Faixas; por_orgao: PorOrgao[] };
              reajustes_apostilamento: { quantidade: number; maior_dias: number | null; itens?: Reajuste[] } };
};

type Reajuste = { contrato_id: number; obra: string; data_base_mes: string; dias: number | null };

const FAIXAS: [keyof Faixas, string][] = [["ate_30", "Até 30 dias"], ["de_31_a_60", "31 a 60 dias"], ["mais_60", "Mais de 60 dias"]];

// antes da conciliacao o valor e' "—" em toda celula: o "a conciliar" aparece uma vez so', no bloco do total (F-97)
function valor(v: number | null | undefined): string {
  return v === null || v === undefined ? "\u2014" : brl(v);
}
function nDias(n: number | null | undefined): string {
  return n === null || n === undefined ? "—" : fmtDias(n);
}
/** "2 medições · 1 nota do RM" (A14); sem a divisao do servidor, "3 cobranças". */
function nCobrancas(g: Grupo): string {
  if (g.notas_rm === undefined) return contar(g.quantidade, "cobrança", "cobranças");
  const medicoes = g.quantidade - g.notas_rm;
  return [medicoes > 0 && contar(medicoes, "medição", "medições"), g.notas_rm > 0 && contar(g.notas_rm, "nota do RM", "notas do RM")]
    .filter(Boolean).join(" · ");
}

/** Linha de apoio do total: o que passa de 60 dias e a divisao em medicoes e notas (os mesmos numeros do rodape);
 *  o valor em dinheiro leva a classe `dinheiro` (cor principal). */
function apoioTotal(pr: Grupo & { faixas: Faixas }): ReactNode {
  const m = pr.faixas.mais_60;
  const antigo: ReactNode = m.quantidade === 0 ? "nada há mais de 60 dias"
    : m.valor_centavos === null ? `${nCobrancas(m)} há mais de 60 dias`
      : <><span className="dinheiro">{brl(m.valor_centavos)}</span> há mais de 60 dias</>;
  return pr.quantidade === 0 ? antigo : <>{antigo} · {nCobrancas(pr)}</>;
}

/** Dias do mais antigo; acima do prazo normal do orgao, a nota "acima do prazo" fica visivel sob o numero (F-97),
 *  sem depender do title do icone. Sem dias (obra sem cobranca contada), a celula fica vazia. */
function CelulaDias({ dias, atrasado }: { dias: number | null | undefined; atrasado: boolean }) {
  if (dias === null || dias === undefined) return <>{nDias(dias)}</>;
  return (
    <>
      {atrasado && <IconeAlerta className="icone icone--p" />}{nDias(dias)}
      {atrasado && <div className="campo__nota negativo">acima do prazo</div>}
    </>
  );
}

function CelulaGrupo({ g }: { g: Grupo | undefined }) {
  if (!g || g.quantidade === 0) return <>—</>;
  return <><span className="dinheiro">{valor(g.valor_centavos)}</span><div className="campo__nota">{nCobrancas(g)}</div></>;
}

export default function AReceberPagina({ busca }: { busca: Busca }) {
  const [p, setP] = useState<Painel | null>(null);
  const [erro, setErro] = useState("");

  useEffect(() => {
    let vivo = true;
    api<Painel>("/api/diretoria").then(d => { if (vivo) setP(d); })
      .catch(e => { if (vivo) setErro(mensagemDeErro(e)); });
    return () => { vivo = false; };
  }, []);

  if (erro) return <p className="erro" role="alert"><IconeAlerta className="icone icone--p" />{erro} Recarregue a página para tentar de novo.</p>;
  if (!p) return <section className="cartao"><div className="vazio"><p>Carregando…</p></div></section>;
  const pr = p.dinheiro.protocolado;
  const aberto = busca.orgao ?? null;
  const reaj = p.dinheiro.reajustes_apostilamento;
  const pleitos = reaj.itens ?? [];

  return (
    <div className="pilha">
      <section className="cartao" aria-labelledby="titulo-por-orgao">
        <div className="cartao__cabeca">
          <h2 className="cartao__titulo" id="titulo-por-orgao">Por órgão</h2>
          {/* a nota dos dias vai para a dica da cabeca (antes ocupava uma faixa no bloco do total) */}
          <span className="cartao__dica">Os dias contam do protocolo da medição ou da emissão da nota do RM.</span>
        </div>
        {/* o total a receber e' o numero principal da tela (Display 22/600): fica na cabeca do cartao, com o que o rodape
            da tabela ja' diz (o que passa de 60 dias, quantas medicoes e notas); antes da conciliacao vale "a conciliar" */}
        <div className="cartao__corpo total-receber">
          {/* antes da conciliacao nao ha' numero: o Display mostra o tracinho e a frase em corpo diz o motivo */}
          <div className="total-receber__valor num">{pr.valor_centavos === null ? "\u2014" : brl(pr.valor_centavos)}</div>
          {(pr.valor_centavos === null || !p.total_a_receber_liberado) && (
            <div className="total-receber__conciliar">valores a conciliar com a controladoria</div>
          )}
          <div className="total-receber__rotulo">a receber, na cota</div>
          <div className="total-receber__apoio num">{apoioTotal(pr)}</div>
        </div>
        {pr.por_orgao.length === 0 ? (
          <div className="vazio vazio--curto"><p className="vazio__titulo">Nenhuma medição protocolada esperando pagamento.</p></div>
        ) : (
          <Rolagem rotulo="A receber por órgão">
            <table className="tabela a-receber">
              <caption className="sr-only">A receber por órgão, na cota da Lotufo, pelos dias desde o protocolo da medição ou a emissão da nota</caption>
              <thead>
                <tr>
                  <th scope="col">Órgão</th>
                  {FAIXAS.map(([k, rotulo]) => <th scope="col" className="col-num" key={k}>{rotulo}</th>)}
                  <th scope="col" className="col-num">Total</th><th scope="col" className="col-num">Mais antigo</th>
                  <th scope="col" className="col-num">Prazo normal do órgão</th>
                </tr>
              </thead>
              <tbody>
                {pr.por_orgao.map(o => {
                  const chave = o.orgao_id != null ? String(o.orgao_id) : o.orgao;
                  // o id do DOM nao pode ter espaco ("sem órgão" partiria o aria-controls em dois)
                  const dom = o.orgao_id != null ? String(o.orgao_id) : "sem-orgao";
                  const estaAberto = aberto === chave;
                  const obras = o.obras ?? [];
                  // cada obra e' uma linha-filha com id proprio; o botao aponta para elas so' enquanto existem (aberto)
                  const idsObras = obras.map(ob => `obras-${dom}-${ob.contrato_id}`);
                  // acima do prazo normal do orgao, o mais antigo aparece como atraso; antes da conciliacao, nao (o
                  // servidor tambem nao avisa: o historico ainda tem "protocoladas" que ja' foram pagas)
                  const atrasado = p.total_a_receber_liberado && o.prazo_normal_dias != null && o.maior_dias != null
                    && o.maior_dias > o.prazo_normal_dias;
                  return (
                    <Fragment key={chave}>
                      <tr id={`orgao-${dom}`}>
                        <th scope="row" className="col-orgao">
                          {/* o nome do orgao abre (e fecha) as obras dele; o orgao aberto fica na URL (?orgao=) */}
                          {obras.length > 0 ? (
                            <button type="button" className="nome-btn" aria-expanded={estaAberto}
                              aria-controls={estaAberto ? idsObras.join(" ") : undefined}
                              onClick={() => trocarBusca({ orgao: estaAberto ? null : chave })}>
                              <IconeSeta className="icone icone--p seta" /><span className="truncar-2l" title={o.orgao}>{o.orgao}</span>
                            </button>
                          ) : <span className="truncar-2l" title={o.orgao}>{o.orgao}</span>}
                          {obras.length > 0 && <div className="campo__nota">{obras.length === 1 ? "1 obra" : `${obras.length} obras`}</div>}
                        </th>
                        {FAIXAS.map(([k]) => <td className="col-num num" key={k}><CelulaGrupo g={o.faixas?.[k]} /></td>)}
                        <td className="col-num num"><CelulaGrupo g={o} /></td>
                        <td className={`col-num num${atrasado ? " negativo" : ""}`}>
                          <CelulaDias dias={o.maior_dias} atrasado={atrasado} />
                        </td>
                        <td className="col-num num">{nDias(o.prazo_normal_dias)}</td>
                      </tr>
                      {estaAberto && obras.map(ob => (
                        <tr className="obra-filha" id={`obras-${dom}-${ob.contrato_id}`} key={ob.contrato_id}>
                          <th scope="row" className="col-orgao col-obra">
                            {/* a obra leva as medicoes em andamento dela, onde estao as que aguardam o orgao; so' com
                                nota do RM, ao resumo dela, com o a receber (A-99) */}
                            <Link para={{ tela: "obra", id: ob.contrato_id, aba: "medicoes" }}
                              secao={ob.notas_rm !== undefined && ob.notas_rm === ob.quantidade ? undefined : "em-andamento"}
                              className="nome-link">{ob.obra}</Link>
                          </th>
                          {FAIXAS.map(([k]) => <td key={k} />)}
                          <td className="col-num num"><CelulaGrupo g={ob} /></td>
                          {/* o mesmo atraso da linha do orgao: os dias da obra contra o prazo normal do orgao pai */}
                          {(() => {
                            const obraAtrasada = p.total_a_receber_liberado && o.prazo_normal_dias != null && ob.maior_dias != null
                              && ob.maior_dias > o.prazo_normal_dias;
                            return (
                              <td className={`col-num num${obraAtrasada ? " negativo" : ""}`}>
                                {ob.maior_dias != null && <CelulaDias dias={ob.maior_dias} atrasado={obraAtrasada} />}
                              </td>
                            );
                          })()}
                          <td />
                        </tr>
                      ))}
                    </Fragment>
                  );
                })}
              </tbody>
              <tfoot>
                <tr>
                  <th scope="row">Todos os órgãos</th>
                  {FAIXAS.map(([k]) => <td className="col-num num" key={k}><CelulaGrupo g={pr.faixas[k]} /></td>)}
                  <td className="col-num num"><CelulaGrupo g={pr} /></td><td /><td />
                </tr>
              </tfoot>
            </table>
          </Rolagem>
        )}
      </section>

      <section className="cartao" id="reajustes" aria-labelledby="titulo-reajustes-apostilamento">
        <div className="cartao__cabeca">
          <h2 className="cartao__titulo" id="titulo-reajustes-apostilamento">Reajustes esperando apostilamento</h2>
          <span className="cartao__dica num">
            {reaj.quantidade === 0 ? "nenhum" : `${reaj.quantidade} ${reaj.quantidade === 1 ? "ciclo" : "ciclos"}`}
            {reaj.maior_dias !== null && ` · o mais antigo há ${nDias(reaj.maior_dias)}`}
          </span>
        </div>
        {pleitos.length === 0 ? (
          <div className="vazio vazio--curto"><p>Nenhum reajuste esperando apostilamento.</p></div>
        ) : (
          <ul className="lista-simples cartao__corpo">
            {pleitos.map(x => (
              <li key={`${x.contrato_id}-${x.data_base_mes}`}>
                <Link para={{ tela: "obra", id: x.contrato_id, aba: "reajuste" }} secao={`db-${x.data_base_mes}`}>
                  {x.obra}, data-base {fmtCompetencia(x.data_base_mes)}
                </Link>
                {x.dias !== null && <span className="num">{` · pleito enviado há ${nDias(x.dias)}`}</span>}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
