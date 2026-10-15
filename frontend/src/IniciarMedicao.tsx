import { useEffect, useRef, useState } from "react";
import CampoCompetencia from "./CampoCompetencia";
import { IconeAlerta } from "./icones";
import { filtrarObras, porContratante, type ObraResumo, type SerieObra } from "./resumoMedicoes";
import { ir } from "./rota";
import { fmtCompetencia } from "./tempo";

// "Iniciar processo de medição" (redesenho #151, protótipo aprovado em 15/10/2026, prototipos/iniciar/): escolher a
// obra e ver o que cabe a ela. Obra com medição em andamento só abre a medição; com medição `prevista` (criada pelo
// cronograma) começa por ela, sem criar outra com o mesmo número; as outras sugerem a próxima (número e competência
// editáveis) e vão para a etapa 1, o espelho. Tipo da medição: execução (o reajuste nasce no espelho); só a obra com
// série de Projeto escolhe "Execução / Projeto".
//
// <dialog> nativo com showModal(): o navegador prende o foco dentro dela (o resto da pagina fica inerte), o Esc
// fecha e o foco volta para o botão que a abriu. O fechar, por qualquer caminho, passa pelo evento `close`.

type Tipo = "execucao" | "projeto";

const MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"];

/** "2026-08" -> "agosto de 2026". */
function porExtenso(aaaaMm: string | null): string {
  const m = /^(\d{4})-(\d{2})$/.exec(aaaaMm ?? "");
  const nome = m ? MESES[Number(m[2]) - 1] : undefined;
  return m && nome ? `${nome} de ${m[1]}` : fmtCompetencia(aaaaMm);
}

/** "2026-12" -> "2027-01". */
function mesSeguinte(aaaaMm: string): string {
  const m = /^(\d{4})-(\d{2})$/.exec(aaaaMm);
  if (!m) return "";
  const mes = Number(m[2]);
  return mes === 12 ? `${Number(m[1]) + 1}-01` : `${m[1]}-${String(mes + 1).padStart(2, "0")}`;
}

const lerSerie = (o: ObraResumo, tipo: Tipo): SerieObra | null => (tipo === "projeto" ? o.projeto : o);

function Icone({ d, className = "icone icone--p" }: { d: string; className?: string }) {
  return <svg className={className} width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"
    strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={d} /></svg>;
}

function SubObra({ o }: { o: ObraResumo }) {
  const partes: React.ReactNode[] = [];
  if (o.orgao_sub) partes.push(o.orgao_sub);
  if (o.aberta_numero !== null) {
    partes.push(<span key="a" className="iniciar__sub--andamento">{o.aberta_numero}ª em andamento: {o.aberta_passo}</span>);
  } else if (o.prevista_id !== null) {
    partes.push(<span key="p" className="iniciar__sub--prevista">
      Prevista pelo cronograma: {o.prevista_numero}ª · {fmtCompetencia(o.prevista_competencia)}</span>);
  } else if (o.aberta) {
    // aberta so' no Projeto ou sem numero conhecido: o servidor sempre manda o numero; texto de reserva
    partes.push(<span key="a" className="iniciar__sub--andamento">já tem medição em andamento</span>);
  }
  if (o.projeto) {
    partes.push(o.projeto.aberta_numero !== null
      ? <span key="j" className="iniciar__sub--andamento">{o.projeto.aberta_numero}ª de Projeto em andamento</span>
      : "tem série de Projeto");
  }
  return (
    <span className="iniciar__obra-sub">
      {partes.map((p, i) => <span key={i}>{i > 0 && " · "}{p}</span>)}
    </span>
  );
}

export default function IniciarMedicao({ obras, aoFechar }: { obras: ObraResumo[]; aoFechar: () => void }) {
  const janela = useRef<HTMLDialogElement>(null);
  const [termo, setTermo] = useState("");
  const [escolhida, setEscolhida] = useState<number | null>(null);
  const [tipo, setTipo] = useState<Tipo>("execucao");
  // sugestão editável da obra sem medição aberta nem prevista: [número, competência AAAA-MM]
  const [numero, setNumero] = useState("");
  const [competencia, setCompetencia] = useState("");

  useEffect(() => {
    const d = janela.current;
    if (!d) return;
    // jsdom (testes) nao implementa showModal: la' a janela so' abre. Sem `close()` na limpeza: tirar o <dialog> do
    // DOM ja' o fecha, e o `close` disparado na limpeza dupla do StrictMode (dev) fechava a janela recem-aberta.
    if (d.open) return;
    if (typeof d.showModal === "function") d.showModal(); else d.setAttribute("open", "");
  }, []);

  const grupos = porContratante(filtrarObras(obras, termo));
  // jsdom (testes) nao implementa close(): la' o fechar avisa direto quem abriu
  const fechar = () => { const d = janela.current; if (d && typeof d.close === "function") d.close(); else aoFechar(); };
  const obra = obras.find(o => o.contrato_id === escolhida) ?? null;

  function sugerir(o: ObraResumo, t: Tipo) {
    const u = lerSerie(o, t)?.ultima ?? null;
    setNumero(u ? String(u.numero + 1) : "");
    setCompetencia(u ? mesSeguinte(u.competencia) : "");
  }
  function escolher(o: ObraResumo) {
    setEscolhida(o.contrato_id); setTipo("execucao"); sugerir(o, "execucao");
  }
  function trocarTipo(o: ObraResumo, t: Tipo) {
    setTipo(t); sugerir(o, t);
  }
  const ir_ = (destino: Parameters<typeof ir>[0], busca?: Record<string, string>) => { fechar(); ir(destino, { busca }); };

  // chamada como funcao (nao como componente): um componente declarado aqui seria outro a cada digito e tiraria o foco do campo
  function rodape(o: ObraResumo) {
    const serie = lerSerie(o, tipo) ?? o;
    const de = tipo === "projeto" ? " de Projeto" : "";
    const cancelar = <button type="button" className="btn" onClick={fechar}>Cancelar</button>;
    const escolhaTipo = o.projeto && (
      <fieldset className="iniciar__tipo-grupo">
        <legend className="iniciar__nota">Esta obra tem duas séries de medição</legend>
        <div className="iniciar__tipo">
          {([["execucao", "Execução"], ["projeto", "Projeto"]] as const).map(([v, rotulo]) => (
            <label key={v}><input type="radio" name="iniciar-tipo" value={v} checked={tipo === v} onChange={() => trocarTipo(o, v)} />{rotulo}</label>
          ))}
        </div>
      </fieldset>
    );

    if (serie.aberta_id !== null) {
      return <>{escolhaTipo}
        <div className="iniciar__aviso iniciar__aviso--atencao" role="status"><IconeAlerta className="icone icone--p" />
          <span>{o.obra} já tem a {serie.aberta_numero}ª{de} em andamento ({(serie.aberta_passo ?? "").toLowerCase()}). Continue nela em vez de começar outra.</span></div>
        <div className="iniciar__botoes">{cancelar}
          <button type="button" className="btn btn--primario" onClick={() => ir_({ tela: "medicao", obra: o.contrato_id, id: serie.aberta_id as number })}>
            Abrir a {serie.aberta_numero}ª medição{de}</button></div></>;
    }
    if (tipo === "execucao" && o.prevista_id !== null) {
      return <>{escolhaTipo}
        <div className="iniciar__aviso iniciar__aviso--info" role="status"><Icone d="M12 11v5M12 8h.01M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0z" />
          <span>{o.obra} tem a {o.prevista_numero}ª prevista pelo cronograma ({fmtCompetencia(o.prevista_competencia)}). O processo começa por ela, sem criar outra medição.</span></div>
        <div className="iniciar__campos">
          <label className="iniciar__campo"><span>Nº da medição</span><input value={o.prevista_numero ?? ""} readOnly /></label>
          <label className="iniciar__campo"><span>Competência</span><input value={porExtenso(o.prevista_competencia)} readOnly /></label>
        </div>
        <div className="iniciar__botoes">{cancelar}
          <button type="button" className="btn btn--primario" onClick={() => ir_({ tela: "medicao", obra: o.contrato_id, id: o.prevista_id as number })}>
            Começar a {o.prevista_numero}ª pelo espelho</button></div></>;
    }
    const u = serie.ultima;
    const pronto = /^[0-9]{1,3}$/.test(numero) && competencia !== "";
    return <>{escolhaTipo}
      <p className="iniciar__nota">{u
        ? <>Sugestão: a próxima depois da {u.numero}ª{de} ({fmtCompetencia(u.competencia)}). Mude se precisar.</>
        : <>Esta obra ainda não tem medição{de} lançada. Informe o número e a competência.</>}</p>
      <div className="iniciar__campos">
        <label className="iniciar__campo" htmlFor="iniciar-numero"><span>Nº da medição{de}</span>
          <input id="iniciar-numero" inputMode="numeric" autoComplete="off" value={numero}
            onChange={ev => setNumero(ev.target.value.replace(/\D/g, "").slice(0, 3))} /></label>
        <div className="iniciar__campo"><label htmlFor="iniciar-competencia"><span>Competência</span></label>
          <CampoCompetencia id="iniciar-competencia" value={competencia} onChange={setCompetencia} /></div>
      </div>
      <div className="iniciar__botoes">{cancelar}
        <button type="button" className="btn btn--primario" disabled={!pronto}
          onClick={() => ir_({ tela: "nova-medicao", obra: o.contrato_id }, { numero, competencia })}>
          {numero ? `Começar a ${numero}ª${de} pelo espelho` : "Informe o número"}</button></div></>;
  }

  return (
    <dialog ref={janela} className="iniciar" aria-labelledby="iniciar-titulo" aria-describedby="iniciar-dica" onClose={aoFechar}
      // clique no fundo (fora da caixa) fecha, como numa janela comum
      onClick={ev => { if (ev.target === ev.currentTarget) fechar(); }}>
      <div className="iniciar__caixa">
        <div className="iniciar__cabeca">
          <div>
            <h2 id="iniciar-titulo" className="iniciar__titulo">Iniciar processo de medição</h2>
            <p id="iniciar-dica" className="iniciar__dica">Escolha a obra. A medição começa pelo espelho.</p>
          </div>
          <button type="button" className="iniciar__fechar" aria-label="Fechar" onClick={fechar}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
              strokeLinecap="round" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18" /></svg>
          </button>
        </div>
        <input type="search" className="iniciar__busca" placeholder="Buscar obra ou contratante…" aria-label="Buscar obra ou contratante"
          autoComplete="off" autoFocus value={termo} onChange={ev => setTermo(ev.target.value)} />
        <div className="iniciar__lista" role="radiogroup" aria-label="Obras ativas, por contratante">
          {grupos.length === 0 && <p className="iniciar__vazio" role="status">Nenhuma obra ativa com “{termo.trim()}”.</p>}
          {grupos.map(g => (
            <section key={g.contratante} className="iniciar__grupo" aria-label={g.contratante}>
              <h3 className="iniciar__contratante">{g.contratante}</h3>
              {g.obras.map(o => (
                <label key={o.contrato_id} className="iniciar__obra">
                  <input type="radio" name="iniciar-obra" checked={escolhida === o.contrato_id} onChange={() => escolher(o)} />
                  <span>
                    <span className="iniciar__obra-nome">{o.obra}</span>
                    {o.ultima && <span className="iniciar__obra-ult"> · última: {o.ultima.numero}ª · {fmtCompetencia(o.ultima.competencia)}</span>}
                    <SubObra o={o} />
                  </span>
                </label>
              ))}
            </section>
          ))}
        </div>
        <div className="iniciar__rodape" aria-live="polite">
          {obra ? rodape(obra) : <>
            <p className="iniciar__nota">Obra com medição em andamento abre a medição; com medição prevista, começa por ela.</p>
            <div className="iniciar__botoes"><button type="button" className="btn" onClick={fechar}>Cancelar</button>
              <button type="button" className="btn btn--primario" disabled>Escolha uma obra</button></div></>}
        </div>
      </div>
    </dialog>
  );
}
