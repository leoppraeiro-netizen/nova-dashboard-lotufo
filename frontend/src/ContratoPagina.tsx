import { useEffect, useState } from "react";
import Alertas, { avisosDaObra, type Aviso } from "./Alertas";
import { api, ApiErro } from "./api";
import { IconeAlerta } from "./icones";
import type { Usuario } from "./Login";
import Espelho from "./Espelho";
import Medicoes, { brl, NovaMedicaoManual } from "./Medicoes";
import { ContratoObra, DocumentosObra } from "./ObraAbas";
import Prazos from "./Prazos";
import Reajuste from "./Reajuste";
import { NovoProtocolo } from "./Protocolo";
import { ir, Link, type AbaObra as Aba, type Busca, type Origem } from "./rota";
import { Abas, Migalhas, VoltarOrigem } from "./Topo";
// Validade e' DATA PURA do papel que o orgao emitiu, nao carimbo de instante:
// fmtData a leria como UTC e a traduziria para Cuiaba (UTC-4), deslocando um dia —
// exatamente na tela que existe para dizer se da' para protocolar hoje.
import { fmtDataPura } from "./tempo";
import { fmtPercentual, baseDosValores } from "./formato";
import Selo from "./Selo";

// Bloco 6 (spec §10.3): cabecalho da obra, montado no servidor (`contratos.cabecalho`).
type Cabecalho = {
  id: number; obra: string; orgao: string; instrumento: string;
  valor_vigente_centavos: number; cota_vigente_centavos: number | null; percentual_lotufo_bp: number;
  execucao_fim: string | null; dias_execucao: number | null; vigencia_fim: string | null; dias_vigencia: number | null;
  status: StatusObra;
  // A3: em valor cheio; o a receber e' nulo enquanto o total nao esta' liberado (a conciliar)
  faturado_centavos?: number; a_receber_centavos?: number | null;
};
// O saldo da obra e' o do cronograma (NAVEGACAO.md, principio 7): vigente − medido de execucao atestado.
type Saldo = { vigente_centavos: number; atestado_execucao_centavos: number; saldo_centavos: number; formula: string };

export type StatusObra = "ativo" | "suspenso" | "em_encerramento" | "encerrado" | "rescindido";

export const STATUS: Record<StatusObra, { rotulo: string; classe: string }> = {
  // Ativo e' o normal da carteira: neutro. Verde e' "concluido/recebido" (DESIGN.md › Colors) e 19
  // selos verdes abafavam os poucos que pedem atencao.
  ativo: { rotulo: "Ativo", classe: "" }, suspenso: { rotulo: "Suspenso", classe: "selo--atencao" },
  em_encerramento: { rotulo: "Em encerramento", classe: "selo--atencao" },
  encerrado: { rotulo: "Encerrado", classe: "" }, rescindido: { rotulo: "Rescindido", classe: "" },
};

function prazo(fim: string | null, dias: number | null): string {
  if (!fim) return "—";
  const n = (d: number) => `${d} ${d === 1 ? "dia" : "dias"}`;
  const quando = dias === null ? "" : dias < 0 ? ` (vencida há ${n(-dias)})` : ` (${n(dias)})`;
  return `${fmtDataPura(fim)}${quando}`;
}

// N04-11 / N08-01: prazo vencido em vermelho, com a mesma regra da lista de Obras: so' em obra ativa fora do
// encerramento (nos outros casos o backend nao avisa de proposito)
function vencido(status: StatusObra, dias: number | null): string {
  return status === "ativo" && dias !== null && dias < 0 ? " negativo" : "";
}

function percentual(bp: number): string {
  return fmtPercentual(bp / 10000);
}

// A ORDEM da faixa mora aqui, e nao no JSX: e' a do NAVEGACAO.md (Medicoes · Prazos · Reajuste ·
// Documentos exigidos · Contrato). As notas moram na pagina de cada medicao e na coluna Notas.
const ABAS: { id: Aba; rotulo: string }[] = [
  { id: "medicoes", rotulo: "Medições" },
  { id: "prazos", rotulo: "Prazos" },
  { id: "reajuste", rotulo: "Reajuste" },
  { id: "documentos", rotulo: "Documentos exigidos" },
  { id: "contrato", rotulo: "Contrato" },
];

/** Resumo da obra, na aba Medicoes (a que abre): quanto vale, quanto ja' se mediu e quanto falta, quanto
 *  se faturou e quanto os orgaos devem, e os prazos. Valores cheios, com a cota ao lado quando a Lotufo nao
 *  tem 100%. */
function ResumoObra({ c, contratoId }: { c: Cabecalho; contratoId: number }) {
  const [saldo, setSaldo] = useState<Saldo | null>(null);
  // N04-12: a falha da curva nao e' o mesmo que valor nulo; sem isto, o "—" mentia que nao havia medido
  const [falhou, setFalhou] = useState(false);
  useEffect(() => {
    let vivo = true;
    setFalhou(false);
    api<{ saldo: Saldo }>(`/api/contratos/${contratoId}/curva`).then(d => { if (vivo) setSaldo(d.saldo); }).catch(() => { if (vivo) setFalhou(true); });
    return () => { vivo = false; };
  }, [contratoId]);
  const cota = c.percentual_lotufo_bp !== 10000;
  return (
    <section className="cartao" aria-label="Resumo da obra">
      {/* grade de 4 colunas, um par por coluna (NAVEGACAO.md): as colunas nao mudam de lugar entre obras */}
      <div className="cartao__corpo resumo-grade">
        <div className="resumo-grade__par">
          <div className="dado"><span className="resumo__rotulo">Valor vigente</span>
            <span className="dado__valor num">{brl(c.valor_vigente_centavos)}</span>
            {cota && <span className="campo__nota num">cota da Lotufo ({percentual(c.percentual_lotufo_bp)}): <span className="dinheiro">{brl(c.cota_vigente_centavos)}</span></span>}</div>
        </div>
        {/* os mesmos rotulos do cronograma, o lar deles: la' mora a formula do saldo. O saldo e' o valor principal da tela (Display) */}
        <div className="resumo-grade__par">
          <div className="dado"><span className="resumo__rotulo">Medido (execução)</span>
            <span className={`dado__valor num${falhou ? " dado__valor--indisponivel" : ""}`}>{saldo ? brl(saldo.atestado_execucao_centavos) : falhou ? "indisponível" : "—"}</span></div>
          <div className="dado"><Link className="resumo__rotulo" para={{ tela: "obra", id: contratoId, aba: "contrato" }} secao="cronograma">Saldo do cronograma</Link>
            <span className={falhou && !saldo ? "dado__valor dado__valor--indisponivel num" : `dado__valor dado__valor--principal num${saldo && saldo.saldo_centavos < 0 ? " negativo" : ""}`}>{saldo ? brl(saldo.saldo_centavos) : falhou ? "indisponível" : "—"}</span>
            {falhou && !saldo && <span className="campo__nota" role="alert">não foi possível ler o cronograma agora</span>}</div>
        </div>
        <div className="resumo-grade__par">
          <div className="dado"><span className="resumo__rotulo">Faturado</span>
            <span className="dado__valor num">{c.faturado_centavos === undefined ? "—" : brl(c.faturado_centavos)}</span></div>
          <div className="dado"><span className="resumo__rotulo">A receber</span>
            <span className="dado__valor num">{c.a_receber_centavos === undefined || c.a_receber_centavos === null ? "—" : brl(c.a_receber_centavos)}</span>
            {c.a_receber_centavos === null && <span className="campo__nota">a conciliar</span>}</div>
        </div>
        <div className="resumo-grade__par">
          <div className="dado"><span className="resumo__rotulo">Execução até</span>
            {/* D16: obra paralisada nao conta o vencimento da execucao (Lei 14.133, art. 115, par. 5o) */}
            <span className={`dado__valor num${vencido(c.status, c.dias_execucao)}`}>
              {c.status === "suspenso" && c.execucao_fim ? `${fmtDataPura(c.execucao_fim)} (paralisada)` : prazo(c.execucao_fim, c.dias_execucao)}</span></div>
          <div className="dado"><span className="resumo__rotulo">Vigência até</span>
            <span className={`dado__valor num${vencido(c.status, c.dias_vigencia)}`}>{prazo(c.vigencia_fim, c.dias_vigencia)}</span></div>
        </div>
      </div>
    </section>
  );
}

/** Avisos desta obra (NAVEGACAO.md › Obra): os tres mais graves, do mais atrasado ao menos, e "ver todos" leva a
 *  tela de Avisos filtrada pela obra. O servidor ja' filtra pelo perfil: na diretoria, sao os motivos do farol. */
function AvisosDaObra({ contratoId, itens }: { contratoId: number; itens: Aviso[] | null | undefined }) {
  const n = itens?.length ?? 0;
  return <Alertas itens={itens} ir={ir} titulo="Avisos desta obra" limite={3} id="titulo-avisos-obra"
    vazio="Nenhum aviso nesta obra."
    verTodos={{ para: { tela: "avisos" }, busca: { obra: String(contratoId) }, rotulo: `Ver todos os ${n} avisos da obra` }} />;
}

/* ------------------------------------------------------------------- pagina */

// A aba vem da URL (rota.tsx): cada aba tem endereco proprio ("/obras/7/prazos") e e' um link de
// verdade, entao F5, o link do e-mail e o "abrir em nova aba" abrem a secao certa.
export default function ContratoPagina({ contratoId, usuario, aba, origem, busca }:
    { contratoId: number; usuario: Usuario; aba: Aba; origem: Origem | null; busca: Busca }) {
  const [c, setC] = useState<Cabecalho | null>(null);
  const [erro, setErro] = useState("");
  const podeEditar = usuario.perfil === "engenharia" || usuario.perfil === "admin";
  // Bloco 2: o espelho cria/avanca medicoes por fora da tela de medicoes. Em vez de um
  // canal entre os cartoes, gerar/criar incrementa esta chave e a lista de medicoes e o
  // cartao de novo protocolo leem de novo.
  const [versaoMedicoes, setVersaoMedicoes] = useState(0);
  // os avisos da obra: o cartao da aba Medicoes e o numero na linha do cabecalho das outras abas
  const [avisos, setAvisos] = useState<Aviso[] | null | undefined>(undefined);

  useEffect(() => {
    // `vigente` corta o setState de uma resposta que chega depois de a tela ja ter
    // trocado de contrato (ou saido). Sem ele, um A lento respondendo depois de um B
    // rapido montava uma pagina HIBRIDA: cabecalho, objeto e valor do contrato A com
    // as abas de medicoes/cronograma do B — e nada na tela denunciava a mistura.
    let vigente = true;
    setC(null); setErro("");
    api<Cabecalho>(`/api/contratos/${contratoId}/cabecalho`)
      .then(d => { if (vigente) setC(d); })
      .catch(e => { if (vigente) setErro(e instanceof ApiErro ? e.message : String(e)); });
    return () => { vigente = false; };
  }, [contratoId]);

  useEffect(() => {
    let vivo = true;
    setAvisos(undefined);
    api<{ avisos: Aviso[] }>("/api/inicio")
      .then(d => { if (vivo) setAvisos(avisosDaObra(d.avisos, contratoId)); })
      .catch(() => { if (vivo) setAvisos(null); });
    return () => { vivo = false; };
  }, [contratoId]);

  // Titulo da aba do navegador: a obra e a aba, como o historico e o favorito precisam para distinguir.
  useEffect(() => {
    const rotulo = ABAS.find(a => a.id === aba)?.rotulo ?? "";
    document.title = `${c ? c.obra : "Obra"} · ${rotulo} · grupolotufo`;
  }, [c, aba]);

  return (
    <>
      <header className="topbar topbar--detalhe">
        <div className="topbar__trilha">
          <VoltarOrigem origem={origem} alemDe={["obras"]} />
          <Migalhas origem={origem} itens={[{ rotulo: "Obras", para: { tela: "obras" } }, { rotulo: c?.obra ?? "Obra" }]} />
          {/* fora da aba Medicoes (onde mora o resumo), o essencial da obra numa linha */}
          {c && aba !== "medicoes" && (() => {
            const linha = `valor vigente ${brl(c.valor_vigente_centavos)} · execução até ${prazo(c.execucao_fim, c.dias_execucao)}`;
            return <span className="topbar__meta topbar__resumo num" title={linha}>{linha}</span>;
          })()}
          {/* o numero de avisos leva a tela de Avisos filtrada pela obra; nunca corta, ao contrario da linha acima */}
          {c && aba !== "medicoes" && avisos && (avisos.length === 0
            ? <span className="topbar__meta topbar__avisos">nenhum aviso</span>
            : <Link className="topbar__meta topbar__avisos" para={{ tela: "avisos" }} busca={{ obra: String(contratoId) }}>
                {avisos.length === 1 ? "1 aviso" : `${avisos.length} avisos`}</Link>)}
        </div>
        <div className="topbar__linha">
          <h1 className="topbar__titulo" title={c?.obra}>{c ? c.obra : "Obra"}</h1>
          {c && <span className="topbar__meta" title={`${c.orgao} · ${c.instrumento}`}>{c.orgao} · {c.instrumento}</span>}
          {/* principio 7: a pagina da obra e' toda em valor cheio; a cota vai ao lado onde a Lotufo nao tem 100% */}
          {c && (() => {
            const base = baseDosValores(c.percentual_lotufo_bp);
            return <span className="topbar__meta topbar__base" title={base}>{base}</span>;
          })()}
          {c && <Selo classe={STATUS[c.status]?.classe ?? ""}>{STATUS[c.status]?.rotulo ?? c.status}</Selo>}
        </div>
      </header>

      <div className="pagina">
        {erro && <p className="erro" role="alert"><IconeAlerta className="icone icone--p" />{erro}</p>}

        {!c && !erro && (
          <section className="cartao">
            <div className="vazio"><p>Carregando a obra…</p></div>
          </section>
        )}

        {/* So depois que o contrato existe: se o GET falhou (404/403), abrir as abas
            faria as filhas repetirem o mesmo erro em cascata. */}
        {c && <>
          <Abas rotulo="Seções da obra" atual={aba}
            itens={ABAS.map(a => ({ id: a.id, rotulo: a.rotulo, para: { tela: "obra" as const, id: contratoId, aba: a.id } }))} />

          {aba === "medicoes" && (
            <div className="pilha">
              <ResumoObra c={c} contratoId={contratoId} />
              <AvisosDaObra contratoId={contratoId} itens={avisos} />
              {/* a medicao nasce do espelho (ou, no fluxo antigo, a mao); gerar recarrega a lista */}
              {podeEditar && (
                <Espelho contratoId={contratoId} podeEditar={podeEditar} aoMudar={() => setVersaoMedicoes(v => v + 1)}
                  aoGerar={id => ir({ tela: "medicao", obra: contratoId, id }, { secao: "etapa-2", forcar: true })}
                  semRegra={<NovaMedicaoManual contratoId={contratoId} aoCriar={() => setVersaoMedicoes(v => v + 1)} />} />
              )}
              <Medicoes contratoId={contratoId} busca={busca} versao={versaoMedicoes} />
              {podeEditar && <NovoProtocolo contratoId={contratoId} versao={versaoMedicoes} aoMudar={() => setVersaoMedicoes(v => v + 1)} />}
            </div>
          )}
          {/* um quadro por natureza (medicao, reajuste): o veredito de hoje e empresa x documento */}
          {aba === "documentos" && <DocumentosObra contratoId={contratoId} />}
          {aba === "reajuste" && <Reajuste contratoId={contratoId} podeEditar={podeEditar} />}
          {aba === "prazos" && <Prazos contratoId={contratoId} podeEditar={podeEditar} />}
          {aba === "contrato" && <ContratoObra contratoId={contratoId} />}
        </>}
      </div>
    </>
  );
}
