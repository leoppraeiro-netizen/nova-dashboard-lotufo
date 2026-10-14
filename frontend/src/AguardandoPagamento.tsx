import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api";
import { brl, contar } from "./formato";
import { IconeAlerta, IconeDocumento } from "./icones";
import { mensagem } from "./NotasAEnviar";
import { Link } from "./Link";
import { nivelParada, textoParada } from "./resumoMedicoes";
import Selo from "./Selo";
import { diaLocal, fmtDataPura, hojeLocal } from "./tempo";
import "./aguardandoPagamento.css";

// Aguardando pagamento (redesenho #158, prototipo aprovado pelo Leo em 14/10/2026, opcao D): as notas ja' enviadas
// ao contratante (medicao `protocolada`), pelo sistema ou registradas por fora, em tres faixas pelo atraso
// (Atrasadas 45+, Atencao 30 a 44, Em dia), com o painel da nota escolhida ao lado. Na MTPAR o numero do protocolo
// SIGA e' registrado no painel (D10); sem ele, a marca.

type Linha = {
  medicao_id: number; contrato_id: number; obra: string; orgao: string; descricao: string; valor_centavos: number;
  enviada_em: string | null; numero_orgao: string | null; familia: string; origem: string;
};

const PURA = /^\d{4}-\d{2}-\d{2}$/;
const diaDe = (iso: string | null): string | null => (iso === null ? null : PURA.test(iso) ? iso : diaLocal(iso));

function data(iso: string | null): string {
  const dia = diaDe(iso);
  return dia ? fmtDataPura(dia) : "—";
}

/** Dias corridos entre o envio e `hoje` (os dois "AAAA-MM-DD"); sem data de envio, nulo. */
function diasParada(enviada: string | null, hoje: string): number | null {
  const dia = diaDe(enviada);
  if (dia === null) return null;
  const [a, m, d] = dia.split("-").map(Number);
  const [ha, hm, hd] = hoje.split("-").map(Number);
  return Math.round((Date.UTC(ha, hm - 1, hd) - Date.UTC(a, m - 1, d)) / 86_400_000);
}

type Faixa = { id: "acao" | "atencao" | "ok"; rotulo: string };
const FAIXAS: Faixa[] = [
  { id: "acao", rotulo: "Atrasadas (45 dias ou mais)" },
  { id: "atencao", rotulo: "Atenção (30 a 44 dias)" },
  { id: "ok", rotulo: "Em dia" },
];

type Item = Linha & { dias: number | null; nivel: "acao" | "atencao" | null };
const faixaDe = (i: Item): Faixa["id"] => i.nivel ?? "ok";
const semSiga = (l: Linha) => l.familia === "mtpar" && !l.numero_orgao;

function Parada({ i }: { i: Item }) {
  if (i.dias === null) return <span className="ap__traco" title="Sem a data de envio desta nota">—</span>;
  return (
    <span className="ap__parada-caixa">
      {i.nivel && <i className={`ap__ponto ap__ponto--${i.nivel}`} aria-hidden="true" />}
      <span className={i.nivel ? `ap__parada ap__parada--${i.nivel}` : "ap__parada"}>{textoParada(i.dias).replace(" ", " ")}</span>
      {i.nivel && <span className="sr-only">{i.nivel === "acao" ? ", atrasada" : ", atenção"}</span>}
    </span>
  );
}

function Painel({ l, podeEditar, aoMudar }: { l: Item; podeEditar: boolean; aoMudar: () => void }) {
  const [numero, setNumero] = useState(l.numero_orgao ?? "");
  const [ocupado, setOcupado] = useState(false);
  const [erro, setErro] = useState("");
  // B-07 (10/10/2026): registrar nao dizia nada (so' o selo sumia); "Número gravado." por alguns segundos
  const [gravado, setGravado] = useState("");
  const relogio = useRef<number | undefined>(undefined);
  useEffect(() => () => window.clearTimeout(relogio.current), []);
  async function registrar(ev: React.FormEvent) {
    ev.preventDefault();
    setOcupado(true); setErro(""); setGravado("");
    try {
      await api(`/api/notas/${l.medicao_id}/numero-orgao`, { method: "POST", body: JSON.stringify({ numero: numero.trim() }) });
      setGravado("Número gravado.");
      window.clearTimeout(relogio.current);
      relogio.current = window.setTimeout(() => setGravado(""), 4000);
      aoMudar();
    } catch (e) { setErro(mensagem(e)); } finally { setOcupado(false); }
  }
  const mtpar = l.familia === "mtpar";
  const rotulo = mtpar ? "Nº do protocolo no SIGA" : "Nº do protocolo no órgão";
  return (
    <aside className="ap__painel" aria-label="Detalhe da nota">
      <h2>{l.obra} · {l.descricao}</h2>
      <div className="ap__painel-orgao">{l.orgao}</div>
      <div className="ap__painel-valor">{brl(l.valor_centavos)}</div>
      <div className="ap__painel-envio">Enviada em <span className="num">{data(l.enviada_em)}</span> ·{" "}
        <span className="ap__fraco">{l.origem === "externo" ? "por fora" : "pelo sistema"}</span></div>
      {mtpar && !l.numero_orgao && <div><Selo classe="selo--atencao">sem protocolo SIGA</Selo></div>}
      {/* B-09 (10/10/2026): quem so' consulta ve o numero, sem o formulario (que dava 403) */}
      {podeEditar ? (
        <form className="ap__campo" onSubmit={registrar}>
          <label htmlFor={`prot-${l.medicao_id}`}>{rotulo}</label>
          <div className="ap__form">
            <input id={`prot-${l.medicao_id}`} className="ap__entrada" name="numero_orgao" autoComplete="off" spellCheck={false} maxLength={100}
              value={numero} onChange={e => setNumero(e.target.value)} />
            <button type="submit" className="btn btn--primario" disabled={ocupado || !numero.trim() || numero.trim() === (l.numero_orgao ?? "")}>
              {ocupado ? "Registrando…" : "Registrar"}</button>
          </div>
          <p className={gravado ? "ap__gravado" : "ap__gravado sr-only"} role="status">{gravado}</p>
          {erro && <p className="erro" role="alert"><IconeAlerta className="icone icone--p" />{erro}</p>}
        </form>
      ) : (
        <div className="ap__campo"><span className="ap__rotulo">{rotulo}</span><div>{l.numero_orgao ?? "—"}</div></div>
      )}
      <div className="ap__links">
        <Link className="ap__link" para={{ tela: "medicao", obra: l.contrato_id, id: l.medicao_id }}>Abrir a medição →</Link>
        <Link className="ap__link" para={{ tela: "obra", id: l.contrato_id, aba: "medicoes" }}>Abrir a obra</Link>
      </div>
    </aside>
  );
}

export default function AguardandoPagamento({ podeEditar, hoje }: { podeEditar: boolean; hoje?: string }) {
  const [linhas, setLinhas] = useState<Linha[] | null>(null);
  const [erro, setErro] = useState("");
  const [escolhida, setEscolhida] = useState<number | null>(null);
  const carregar = useCallback(async () => {
    try { setLinhas(await api<Linha[]>("/api/notas/aguardando-pagamento")); setErro(""); } catch (e) { setErro(mensagem(e)); }
  }, []);
  useEffect(() => { void carregar(); }, [carregar]);

  if (!linhas) {
    return erro
      ? <div className="form-inline"><p className="erro" role="alert"><IconeAlerta className="icone icone--p" />Não foi possível ler as notas: {erro}</p>
          <button type="button" className="btn btn--pequeno" onClick={() => void carregar()}>Tentar de novo</button></div>
      : <p className="campo__nota">Carregando as notas…</p>;
  }
  if (linhas.length === 0) {
    return (
      <section className="ap__quadro"><div className="ap__vazio">
        <IconeDocumento className="icone" /><p>Nenhuma nota esperando pagamento.</p></div></section>
    );
  }

  const dia = hoje ?? hojeLocal();
  const itens: Item[] = linhas.map(l => {
    const dias = diasParada(l.enviada_em, dia);
    return { ...l, dias, nivel: nivelParada(dias, "aguardando-pagamento") };
  });
  // a mais parada primeiro dentro da faixa; sem data de envio, por ultimo
  const ordenar = (a: Item, b: Item) => (b.dias ?? -1) - (a.dias ?? -1);
  const grupos = FAIXAS.map(f => ({ f, itens: itens.filter(i => faixaDe(i) === f.id).sort(ordenar) })).filter(g => g.itens.length > 0);
  const atual = itens.find(i => i.medicao_id === escolhida) ?? grupos[0].itens[0];
  const total = itens.reduce((s, i) => s + i.valor_centavos, 0);

  return (
    <>
      <p className="ap__total"><span className="dinheiro">{brl(total)}</span> aguardando pagamento · {contar(itens.length, "nota", "notas")}</p>
      <div className="ap">
        <section className="ap__quadro" aria-label="Notas aguardando pagamento">
          <table className="ap__tabela" role="grid">
            <caption className="sr-only">Notas enviadas ao órgão, por faixa de atraso. Escolha uma para ver o detalhe.</caption>
            <colgroup><col className="ap__c-obra" /><col className="ap__c-org" /><col className="ap__c-val" /><col className="ap__c-env" /><col className="ap__c-par" /></colgroup>
            <thead>
              <tr>
                <th scope="col">Obra · Medição</th><th scope="col">Órgão</th><th scope="col" className="col-num">Valor</th>
                <th scope="col">Enviada em</th><th scope="col">Parada há</th>
              </tr>
            </thead>
            {grupos.map(g => (
              <tbody key={g.f.id}>
                <tr className="ap__faixa">
                  <td colSpan={5}>
                    <span className="ap__faixa-rotulo">
                      <i className={`ap__ponto ap__ponto--${g.f.id}`} aria-hidden="true" />
                      {g.f.rotulo} · {g.itens.length} · <span className="dinheiro">{brl(g.itens.reduce((s, i) => s + i.valor_centavos, 0))}</span>
                    </span>
                  </td>
                </tr>
                {g.itens.map(i => {
                  const sel = i.medicao_id === atual.medicao_id;
                  return (
                    <tr key={i.medicao_id} className="ap__linha" tabIndex={0} aria-selected={sel}
                      aria-label={`${i.obra} · ${i.descricao}`}
                      onClick={() => setEscolhida(i.medicao_id)}
                      onKeyDown={ev => { if (ev.target === ev.currentTarget && (ev.key === "Enter" || ev.key === " ")) { ev.preventDefault(); setEscolhida(i.medicao_id); } }}>
                      <td><span className="ap__obra">{i.obra}</span> · {i.descricao}</td>
                      <td>{i.orgao}{semSiga(i) && <> <Selo classe="selo--atencao">sem protocolo SIGA</Selo></>}</td>
                      <td className="col-num dinheiro" data-rotulo="Valor">{brl(i.valor_centavos)}</td>
                      <td className="num" data-rotulo="Enviada em">{data(i.enviada_em)}{i.origem === "externo" && <span className="ap__origem">por fora</span>}</td>
                      <td data-rotulo="Parada há"><Parada i={i} /></td>
                    </tr>
                  );
                })}
              </tbody>
            ))}
          </table>
        </section>
        <Painel key={atual.medicao_id} l={atual} podeEditar={podeEditar} aoMudar={() => void carregar()} />
      </div>
    </>
  );
}
