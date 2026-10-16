import { useEffect, useRef, useState } from "react";
import { contagem, type Aviso } from "./Alertas";
import { api, mensagemDeErro } from "./api";
import { ABAS_CARTEIRA, motivosDaLinha, obrasComProblema, porFarol, type Motivo } from "./carteira";
import { contar, fmtDias, fmtPercentual } from "./formato";
import { IconeAlerta, IconeBaixar } from "./icones";
import { filtrarObras, type ObraLista } from "./listaObras";
import { brl } from "./Medicoes";
import { type AbaCarteira, type Ir } from "./rota";
import { Link } from "./Link";
import { fmtCompetencia, fmtDataPura, fmtMesCurto as mesCurto } from "./tempo";
import Rolagem from "./Rolagem";
import Selo from "./Selo";
import { Abas } from "./Topo";

// Carteira (NAVEGACAO.md › Carteira; bloco 8, spec §10.5), a entrada da diretoria, em abas na URL: Resumo (a
// padrao), QDOP e Producao. Tudo na COTA da Lotufo, com o vocabulario fixo: medido, faturado, protocolado,
// recebido. As regras moram em `app/diretoria.py`; o total a receber so' mostra valor depois de conciliado
// (geral.yaml: diretoria.total_a_receber_liberado). O a receber (por obra, previsto e recebido) mora
// em A receber; os reajustes esperando apostilamento, na aba Reajuste da obra; a lista de avisos, na tela de Avisos; o que termina, em Obras.

type Grupo = { quantidade: number; valor_centavos: number | null };
type PorOrgao = Grupo & { orgao: string; maior_dias: number | null };
type Dinheiro = {
  medido_esperando_nota: Grupo; nota_esperando_protocolo: Grupo; recebido_mes: Grupo;
  protocolado: Grupo & { faixas: Record<"ate_30" | "de_31_a_60" | "mais_60", Grupo>; por_orgao: PorOrgao[] };
  reajustes_apostilamento: { quantidade: number; maior_dias: number | null };
};
type MesAno = {
  mes: string; medido_mes_centavos: number; previsto_mes_centavos: number; mesmo_mes_ano_anterior_centavos: number;
  acumulado_ano_centavos: number; previsto_ano_centavos: number;
  serie: { competencia: string; medido_centavos: number; previsto_centavos: number }[];
};
type Proximo = { competencia: string; faturamento_previsto_centavos: number; recebimento_previsto_centavos: number | null };
type Carteira = {
  saldo_centavos: number; ritmo_mensal_centavos: number; meses_de_producao: number | null;
  por_orgao: { orgao: string; saldo_centavos: number; fracao: number }[];
};
type Obra = {
  contrato_id: number; seq: number; obra: string; contratante: string; empreita: string; direito: number;
  pi_va: number; faturados: number; saldo: number; pct_recebido: number; status: string; termino: string | null;
  vigencia?: string | null; farol: "verde" | "atencao" | "acao" | "vermelho"; motivo: string; motivos?: Motivo[];
};
type ResumoMes = { mes: string; obras_protocoladas: number; obras_ativas: number };
type Painel = {
  hoje: string; total_a_receber_liberado: boolean; dinheiro: Dinheiro; mes_ano: MesAno; proximos: Proximo[];
  carteira: Carteira; obras: Obra[]; obras_base: ObrasBase; avisos: Aviso[];
};
type ObrasBase = { ativas: number; encerramento: number; suspensas: number; encerradas: number };

/** A-21 (10/10/2026): o farol conta tudo que nao e' rescindido; a dica diz a base ("19 ativas, 2 em encerramento,
 *  1 suspensa"), porque "obras ativas" no resto da tela e' so' ativo sem encerramento iniciado. */
function baseObras(b: ObrasBase): string {
  return [b.ativas && contar(b.ativas, "ativa", "ativas"), b.encerramento && `${b.encerramento} em encerramento`,
    b.suspensas && contar(b.suspensas, "suspensa", "suspensas"), b.encerradas && contar(b.encerradas, "encerrada", "encerradas")]
    .filter(Boolean).join(", ");
}

// O selo diz a palavra do nivel (D12, D10), a mesma do Selo dos avisos: Critico, Acao e Atencao. Acao e Atencao
// dividem o ambar e se separam pela forma (contorno cheio na Acao), como em Alertas. So' o QDOP EXPORTADO
// (arquivo) segue com o vocabulario oficial (verde, amarelo, vermelho).
const FAROL: Record<Obra["farol"], { rotulo: string; classe: string; forte?: boolean }> = {
  verde: { rotulo: "Em dia", classe: "selo--ok" },
  acao: { rotulo: "Ação", classe: "selo--atencao", forte: true },
  atencao: { rotulo: "Atenção", classe: "selo--atencao" },
  vermelho: { rotulo: "Crítico", classe: "selo--acao" },
};

function valor(v: number | null): string {
  return v === null ? "a conciliar" : brl(v);
}
function pct(f: number): string {
  return fmtPercentual(f, 1);
}
function data(iso: string | null | undefined): string {
  return iso ? fmtDataPura(iso.slice(0, 10)) : "—";
}

// Escala e unidade repetidas do Cronograma de proposito (a linguagem visual mora no tokens.css).
function escala(maxCentavos: number): { topo: number; passo: number } {
  const max = Math.max(1, maxCentavos);
  const alvo = max / 4;
  const mag = Math.pow(10, Math.floor(Math.log10(alvo)));
  const passo = Math.max(1, [1, 2, 2.5, 5, 10].map(m => m * mag).find(p => p >= alvo) ?? mag * 10);
  return { topo: Math.ceil(max / passo) * passo, passo };
}
function unidade(topo: number): { divisor: number; rotulo: string } {
  const reais = topo / 100;
  if (reais >= 1_000_000) return { divisor: 100_000_000, rotulo: "R$ mi" };
  if (reais >= 10_000) return { divisor: 100_000, rotulo: "R$ mil" };
  return { divisor: 100, rotulo: "R$" };
}

// F-83: o passo de cada mes vem da largura do conteiner (minimo de 64px; abaixo disso o grafico rola). O texto do
// eixo nao escala: so' o vao entre os meses e a largura das barras crescem.
const PASSO_MIN = 64;
function GraficoAno({ serie }: { serie: MesAno["serie"] }) {
  const medida = useRef<HTMLDivElement>(null);
  const [larg, setLarg] = useState(0);
  useEffect(() => {
    const el = medida.current;
    if (!el) return;
    const medir = () => setLarg(el.clientWidth);
    medir();
    // jsdom (testes) nao tem ResizeObserver: la' a medicao unica basta
    if (typeof ResizeObserver === "undefined") return;
    const observador = new ResizeObserver(medir);
    observador.observe(el);
    return () => observador.disconnect();
  }, []);
  const MARGEM_E = 66, MARGEM_D = 14, VAO = 4, TOPO = 24, ALTURA = 180;
  const PASSO = Math.max(PASSO_MIN, Math.floor((larg - MARGEM_E - MARGEM_D) / Math.max(1, serie.length)));
  const LARG = Math.min(32, Math.max(16, Math.round(PASSO / 4)));
  const BASE = TOPO + ALTURA, H = BASE + 28, W = MARGEM_E + serie.length * PASSO + MARGEM_D;
  const { topo, passo } = escala(Math.max(...serie.map(m => Math.max(m.medido_centavos, m.previsto_centavos))));
  const { divisor, rotulo } = unidade(topo);
  const y = (v: number) => BASE - (v / topo) * ALTURA;
  const alt = (v: number) => (v <= 0 ? 0 : Math.max(2, (v / topo) * ALTURA));
  const grade: number[] = [];
  for (let v = 0; v <= topo + passo / 2; v += passo) grade.push(v);
  return (
    <div ref={medida} className="grafico__medida">
    <svg className="grafico__svg" width={W} height={H} viewBox={`0 0 ${W} ${H}`} role="img"
      aria-label={`Medido e previsto nos últimos 12 meses, na cota da Lotufo, em ${rotulo}. `
        + "Os mesmos números estão na “Tabela por competência”, recolhida logo abaixo."}>
      <text className="g-eixo num" x={MARGEM_E - 8} y={TOPO - 9} textAnchor="end">{rotulo}</text>
      {grade.map(v => (
        <g key={v}>
          <line className={v === 0 ? "g-base" : "g-grade"} x1={MARGEM_E} y1={y(v)} x2={W - MARGEM_D} y2={y(v)} />
          <text className="g-eixo num" x={MARGEM_E - 8} y={y(v) + 4} textAnchor="end">
            {(v / divisor).toLocaleString("pt-BR", { maximumFractionDigits: 1 })}
          </text>
        </g>
      ))}
      {serie.map((m, i) => {
        const cx = MARGEM_E + i * PASSO + PASSO / 2;
        const hp = alt(m.previsto_centavos), hm = alt(m.medido_centavos);
        return (
          <g key={m.competencia}>
            <title>{`${fmtCompetencia(m.competencia)} — previsto ${brl(m.previsto_centavos)} · medido ${brl(m.medido_centavos)}`}</title>
            {hp > 0 ? <rect className="g-previsto" x={cx - VAO / 2 - LARG} y={BASE - hp} width={LARG} height={hp} rx={2.5} />
              : <rect className="g-talo" x={cx - VAO / 2 - LARG} y={BASE - 4} width={LARG} height={4} rx={2} />}
            {hm > 0 ? <rect className="g-execucao" x={cx + VAO / 2} y={BASE - hm} width={LARG} height={hm} rx={2.5} />
              : <rect className="g-talo" x={cx + VAO / 2} y={BASE - 4} width={LARG} height={4} rx={2} />}
            <text className="g-eixo-x" x={cx} y={BASE + 18} textAnchor="middle">{mesCurto(m.competencia)}</text>
          </g>
        );
      })}
    </svg>
    </div>
  );
}

// KPI de uma faixa (D13): valor em Display e rotulo embaixo; a comparacao (D8) entra como linha dentro do KPI.
function Kpi({ valorTexto, rotulo, dinheiro = true, comparacoes = [] }:
    { valorTexto: string; rotulo: string; dinheiro?: boolean; comparacoes?: { rotulo: string; valor: string }[] }) {
  return (
    <li className={`kpi${dinheiro ? " kpi--dinheiro" : ""}`}>
      <span className="kpi__valor num">{valorTexto}</span>
      <span className="kpi__rotulo">{rotulo}</span>
      {comparacoes.map(c => <span key={c.rotulo} className="kpi__comparacao num">{c.rotulo}: {c.valor}</span>)}
    </li>
  );
}

function Secao({ id, titulo, dica, acoes, children }:
    { id: string; titulo: string; dica?: string; acoes?: React.ReactNode; children: React.ReactNode }) {
  return (
    <section className="cartao" aria-labelledby={id}>
      <div className="cartao__cabeca">
        <h2 className="cartao__titulo" id={id}>{titulo}</h2>
        {dica && <span className="cartao__dica">{dica}</span>}
        {acoes && <div className="cartao__acoes">{acoes}</div>}
      </div>
      {children}
    </section>
  );
}

// O que termina, pela regra da lista de Obras (`listaObras.ts`), com o link para ela filtrada.
const PRAZOS = [{ dias: 90, busca: "90", quando: `em ${fmtDias(90)}` }, { dias: 180, busca: "180", quando: "em 6\u00a0meses" }];

/** Resumo (a aba padrao): cada bloco com o caminho para o lar dele (A receber, QDOP, Obras filtrada, Avisos). */
function Resumo({ p, ir }: { p: Painel; ir: Ir }) {
  const d = p.dinheiro, m = p.mes_ano;
  // "N de M obras protocolaram" vem do /api/inicio; o que termina, da lista de Obras (/api/contratos).
  // undefined = carregando; null = nao carregou.
  const [mes, setMes] = useState<ResumoMes | null | undefined>(undefined);
  const [obras, setObras] = useState<ObraLista[] | null | undefined>(undefined);
  useEffect(() => {
    let vivo = true;
    api<{ resumo: ResumoMes }>("/api/inicio").then(r => { if (vivo) setMes(r.resumo); }).catch(() => { if (vivo) setMes(null); });
    api<ObraLista[]>("/api/contratos").then(l => { if (vivo) setObras(l); }).catch(() => { if (vivo) setObras(null); });
    return () => { vivo = false; };
  }, []);
  const problema = obrasComProblema(p.obras);
  // "N de M obras ativas protocolaram" e' um KPI do mes (F-64): carregando "…", sem dado "—" com o aviso no rotulo
  const protocolos = mes === undefined ? { v: "…", r: "contando os protocolos do mês…" }
    : mes === null ? { v: "—", r: "não foi possível contar os protocolos do mês" }
    : { v: `${mes.obras_protocoladas} de ${mes.obras_ativas}`, r: "obras ativas protocolaram" };

  return (
    <>
      <Secao id="dir-dinheiro" titulo="Onde está o dinheiro"
        dica={p.total_a_receber_liberado ? undefined : "Valores do protocolado a conciliar com a controladoria."}>
        <ul className="kpis" aria-label="Onde está o dinheiro">
          <Kpi valorTexto={brl(d.medido_esperando_nota.valor_centavos)} rotulo={`medido esperando nota (${d.medido_esperando_nota.quantidade})`} />
          <Kpi valorTexto={brl(d.nota_esperando_protocolo.valor_centavos)} rotulo={`nota emitida esperando protocolo (${d.nota_esperando_protocolo.quantidade})`} />
          <Kpi valorTexto={valor(d.protocolado.valor_centavos)} rotulo={`protocolado esperando pagamento (${d.protocolado.quantidade})`} />
          <Kpi valorTexto={brl(d.recebido_mes.valor_centavos)} rotulo={`recebido no mês (${d.recebido_mes.quantidade})`} />
        </ul>
      </Secao>

      <Secao id="dir-mes" titulo="O mês" dica={`Competência ${fmtCompetencia(m.mes)}`}>
        <ul className="kpis" aria-label="O mês">
          <Kpi valorTexto={brl(m.medido_mes_centavos)} rotulo="medido no mês"
            comparacoes={[{ rotulo: "previsto no mês", valor: brl(m.previsto_mes_centavos) },
              { rotulo: "mesmo mês do ano anterior", valor: brl(m.mesmo_mes_ano_anterior_centavos) }]} />
          <Kpi valorTexto={brl(m.acumulado_ano_centavos)} rotulo="acumulado do ano"
            comparacoes={[{ rotulo: "previsto do ano", valor: brl(m.previsto_ano_centavos) }]} />
          <Kpi valorTexto={protocolos.v} rotulo={protocolos.r} dinheiro={false} />
        </ul>
      </Secao>

      <Secao id="dir-problema" titulo="Obras com problema" dica={`${problema.total} de ${p.obras.length} obras (${baseObras(p.obras_base)}) com farol em Ação, Atenção ou Crítico`}>
        {problema.total === 0 ? (
          <div className="vazio vazio--curto"><p>Nenhuma obra com farol em Ação, Atenção ou Crítico.</p></div>
        ) : (
          <ul className="lista-simples cartao__corpo obras-problema">
            {problema.itens.map(o => {
              // o primeiro motivo na linha; os outros sao os avisos da obra (o farol vem deles)
              const { visiveis, mais } = motivosDaLinha(o.motivos, 1);
              return (
                <li key={o.contrato_id}>
                  <Selo classe={(FAROL[o.farol] ?? FAROL.atencao).classe} forte={(FAROL[o.farol] ?? FAROL.atencao).forte}>{(FAROL[o.farol] ?? FAROL.atencao).rotulo}</Selo>
                  <span className="obras-problema__texto">
                    <Link className="nome-link" para={{ tela: "obra", id: o.contrato_id, aba: "medicoes" }} ir={ir}>{o.obra}</Link>
                    <span>{visiveis[0]?.texto ?? o.motivo}</span>
                    {mais > 0 && (
                      <Link para={{ tela: "avisos" }} busca={{ obra: String(o.contrato_id) }} ir={ir}>
                        mais {mais}<span className="sr-only"> {mais === 1 ? "motivo" : "motivos"} de {o.obra}</span>
                      </Link>
                    )}
                  </span>
                </li>
              );
            })}
          </ul>
        )}
        <div className="cartao__corpo">
          <Link para={{ tela: "carteira", aba: "qdop" }} ir={ir}>
            {problema.total > problema.itens.length ? `Ver as ${problema.total} no QDOP` : `Ver o QDOP (${p.obras.length} obras)`}
          </Link>
        </div>
      </Secao>

      <div className="cartoes-lado">
        <Secao id="dir-terminam" titulo="Terminam" dica="A execução ou a vigência, como na lista de Obras; incluídas as vencidas, que vêm primeiro.">
          <ul className="lista-simples cartao__corpo">
            {PRAZOS.map(x => {
              const n = obras ? filtrarObras(obras, { termina: x.dias }).length : null;
              return (
                <li key={x.busca}>
                  <Link para={{ tela: "obras" }} busca={{ termina: x.busca }} ir={ir}>
                    {n === null ? `Obras que terminam ${x.quando}` : n === 1 ? `1 obra termina ${x.quando}` : `${n} obras terminam ${x.quando}`}
                  </Link>
                </li>
              );
            })}
          </ul>
          {obras === null && <p className="cartao__corpo campo__nota">Não foi possível contar as obras; os links abrem a lista.</p>}
        </Secao>
        <Secao id="dir-avisos" titulo="Avisos da diretoria">
          <div className="cartao__corpo pilha">
            <p>{p.avisos.length === 0 ? "Nenhum aviso."
              : <><strong className="num">{p.avisos.length}</strong> {p.avisos.length === 1 ? "aviso" : "avisos"}: {contagem(p.avisos)}.</>}</p>
            <p><Link para={{ tela: "avisos" }} ir={ir}>Ver os avisos</Link></p>
          </div>
        </Secao>
      </div>
    </>
  );
}

/** QDOP: a tabela no leiaute e no vocabulario do QDOP, pelo farol, com ate' 2 motivos (o resto nos avisos da obra). */
function Qdop({ p, ir }: { p: Painel; ir: Ir }) {
  const obras = porFarol(p.obras);
  return (
    <Secao id="dir-qdop" titulo="QDOP" dica={`${obras.length} obras, pelo farol · leiaute do QDOP`}
      acoes={<a className="btn" href="/api/diretoria/qdop.xlsx"><IconeBaixar className="icone icone--p" /> Exportar QDOP (.xlsx)</a>}>
      <Rolagem rotulo="QDOP" alta>
        <table className="tabela qdop">
          <caption className="sr-only">QDOP, na cota da Lotufo: as obras pelo farol</caption>
          <thead>
            <tr>
              <th scope="col">Obra</th><th scope="col">Empreita</th><th scope="col" className="col-num">Contratual (PI+VA)</th>
              <th scope="col" className="col-num">Faturado</th><th scope="col" className="col-num">Saldo (contratual − faturado)</th>
              <th scope="col">Término e vigência</th><th scope="col">Status</th>
              <th scope="col">Farol</th><th scope="col">Motivos</th>
            </tr>
          </thead>
          <tbody>
            {obras.map(o => {
              const { visiveis, mais } = motivosDaLinha(o.motivos);
              return (
                <tr key={o.contrato_id}>
                  <td><Link className="nome-link truncar truncar--nome" title={o.obra} para={{ tela: "obra", id: o.contrato_id, aba: "medicoes" }} ir={ir}>{o.obra}</Link></td>
                  <td>{o.empreita}{o.direito < 1 ? ` (${pct(o.direito)})` : ""}</td>
                  <td className="col-num dinheiro num">{brl(o.pi_va)}</td><td className="col-num dinheiro num">{brl(o.faturados)}</td>
                  <td className={`col-num dinheiro num${o.saldo < 0 ? " negativo" : ""}`}>{brl(o.saldo)}</td>
                  {/* as duas datas numa coluna so' (as colunas do QDOP cabem a 1366): o termino da execucao e,
                      embaixo, a vigencia */}
                  <td className="num">{data(o.termino)}<div className="campo__nota">vig. {data(o.vigencia)}</div></td>
                  <td className="sem-quebra">{o.status}</td>
                  <td><Selo classe={(FAROL[o.farol] ?? FAROL.atencao).classe} forte={(FAROL[o.farol] ?? FAROL.atencao).forte}>{(FAROL[o.farol] ?? FAROL.atencao).rotulo}</Selo></td>
                  <td>{!o.motivos ? (o.motivo || "—") : visiveis.length === 0 ? "—" : (
                    <ul className="motivos">
                      {visiveis.map(x => <li key={`${x.tipo}-${x.texto}`}>{x.texto}</li>)}
                      {mais > 0 && (
                        <li><Link para={{ tela: "avisos" }} busca={{ obra: String(o.contrato_id) }} ir={ir}>
                          mais {mais}<span className="sr-only"> {mais === 1 ? "motivo" : "motivos"} de {o.obra}</span>
                        </Link></li>
                      )}
                    </ul>
                  )}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </Rolagem>
    </Secao>
  );
}

/** Producao: o grafico de 12 meses, os proximos meses e o saldo a executar (vigente − medido, na cota). */
function Producao({ p, ir }: { p: Painel; ir: Ir }) {
  const m = p.mes_ano, k = p.carteira;
  return (
    <>
      <Secao id="dir-grafico" titulo="Os últimos 12 meses" dica={`Previsto e medido até ${fmtCompetencia(m.mes)}.`}>
        <div className="cartao__corpo pilha">
          <Rolagem rotulo="Gráfico de medido e previsto nos últimos 12 meses" className="grafico"><GraficoAno serie={m.serie} /></Rolagem>
          <div className="legenda">
            <span className="legenda__item"><span className="legenda__chave legenda__chave--previsto" aria-hidden="true" />previsto</span>
            <span className="legenda__item"><span className="legenda__chave legenda__chave--execucao" aria-hidden="true" />medido</span>
          </div>
          {/* os valores do grafico em texto, para teclado e leitor de tela (o SVG e' role="img") */}
          <details className="detalhes">
            <summary>Tabela por competência ({m.serie.length})</summary>
            <Rolagem rotulo="Previsto e medido nos últimos 12 meses">
              <table className="tabela">
                <caption className="sr-only">Previsto e medido nos últimos 12 meses, na cota da Lotufo</caption>
                <thead>
                  <tr>
                    <th scope="col">Competência</th>
                    <th scope="col" className="col-num">Previsto</th>
                    <th scope="col" className="col-num">Medido</th>
                  </tr>
                </thead>
                <tbody>
                  {m.serie.map((s, i) => (
                    <tr key={s.competencia} className={`linha${i % 2 === 1 ? " par" : ""}`}>
                      <td className="num">{fmtCompetencia(s.competencia)}</td>
                      <td className="col-num dinheiro num">{brl(s.previsto_centavos)}</td>
                      <td className="col-num dinheiro num">{brl(s.medido_centavos)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Rolagem>
          </details>
          <p className="campo__nota">Os números do mês estão no <Link para={{ tela: "carteira" }} ir={ir}>Resumo</Link>.</p>
        </div>
      </Secao>

      <Secao id="dir-proximos" titulo="Próximos meses" dica="Faturamento pelo cronograma; recebimento pela mediana de cada órgão.">
        <Rolagem rotulo="Próximos meses">
          <table className="tabela tabela--estreita">
            <thead><tr><th scope="col">Mês</th><th scope="col" className="col-num">Faturamento previsto</th>
              <th scope="col" className="col-num">Recebimento previsto</th></tr></thead>
            <tbody>
              {p.proximos.map(x => (
                <tr key={x.competencia}><td className="num">{fmtCompetencia(x.competencia)}</td>
                  <td className="col-num dinheiro num">{brl(x.faturamento_previsto_centavos)}</td>
                  <td className="col-num num">{valor(x.recebimento_previsto_centavos)}</td></tr>
              ))}
            </tbody>
          </table>
        </Rolagem>
      </Secao>

      <Secao id="dir-saldo" titulo="Saldo a executar" dica="Vigente − medido. O saldo do QDOP é outra conta: contratual − faturado.">
        <ul className="kpis" aria-label="Saldo a executar">
          <Kpi valorTexto={brl(k.saldo_centavos)} rotulo="saldo a executar" />
          <Kpi valorTexto={brl(k.ritmo_mensal_centavos)} rotulo="ritmo (média dos últimos 6 meses)" />
          <Kpi valorTexto={k.meses_de_producao === null ? "—" : `${k.meses_de_producao.toLocaleString("pt-BR")}\u00a0meses`}
            rotulo="de produção no ritmo atual" dinheiro={false} />
        </ul>
        <Rolagem rotulo="Saldo a executar por órgão">
          <table className="tabela tabela--estreita">
            <caption className="sr-only">Saldo a executar por órgão, na cota da Lotufo</caption>
            <thead><tr><th scope="col">Órgão</th><th scope="col" className="col-num">Saldo a executar</th>
              <th scope="col" className="col-num">Participação</th></tr></thead>
            <tbody>
              {k.por_orgao.map(o => (
                <tr key={o.orgao}><td>{o.orgao}</td><td className="col-num dinheiro num">{brl(o.saldo_centavos)}</td>
                  <td className="col-num num">{fmtPercentual(o.fracao, 1, true)}</td></tr>
              ))}
            </tbody>
          </table>
        </Rolagem>
      </Secao>
    </>
  );
}

export default function Diretoria({ ir, aba = "resumo" }: { ir: Ir; aba?: AbaCarteira }) {
  const [p, setP] = useState<Painel | null>(null);
  const [erro, setErro] = useState("");
  useEffect(() => {
    let vivo = true;
    api<Painel>("/api/diretoria")
      .then(d => { if (vivo) setP(d); })
      .catch(e => { if (vivo) setErro(mensagemDeErro(e)); });
    return () => { vivo = false; };
  }, []);

  // as abas sao links (NAVEGACAO.md › Subnavegacao): a aba fica na URL, e trocar de aba nao busca o painel de novo
  const abas = <Abas rotulo="Seções da Carteira" atual={aba}
    itens={ABAS_CARTEIRA.map(a => ({ ...a, para: { tela: "carteira" as const, aba: a.id } }))} />;
  if (erro) return <div className="pilha">{abas}<p className="erro" role="alert"><IconeAlerta className="icone icone--p" />{erro} Recarregue a página para tentar de novo.</p></div>;
  if (!p) return <div className="pilha">{abas}<section className="cartao"><div className="vazio"><p>Carregando…</p></div></section></div>;
  return (
    <div className="pilha">
      {abas}
      {aba === "resumo" && <Resumo p={p} ir={ir} />}
      {aba === "qdop" && <Qdop p={p} ir={ir} />}
      {aba === "producao" && <Producao p={p} ir={ir} />}
    </div>
  );
}
