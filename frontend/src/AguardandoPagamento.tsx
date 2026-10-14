import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api";
import { brl } from "./formato";
import { IconeAlerta } from "./icones";
import { mensagem } from "./NotasAEnviar";
import Rolagem from "./Rolagem";
import { Link } from "./Link";
import Selo from "./Selo";
import { fmtData, fmtDataPura } from "./tempo";
import "./notas.css";

// Aguardando pagamento (2026-10-09): as notas ja' enviadas ao contratante (medicao `protocolada`), pelo sistema
// ou registradas por fora. Na MTPAR o numero do protocolo SIGA e' registrado aqui (D10); sem ele, a marca.

type Linha = {
  medicao_id: number; contrato_id: number; obra: string; orgao: string; descricao: string; valor_centavos: number;
  enviada_em: string | null; numero_orgao: string | null; familia: string; origem: string;
};

function data(iso: string | null): string {
  if (!iso) return "—";
  return /^\d{4}-\d{2}-\d{2}$/.test(iso) ? fmtDataPura(iso) : fmtData(iso);
}

// B-07 (10/10/2026): a coluna fala do orgao; o SIGA e' so' da MTPAR, entao a dica vai so' na linha dela
const DICA_SIGA = <span className="campo__nota">(SIGA, na MTPAR)</span>;

function NumeroSiga({ l, aoMudar }: { l: Linha; aoMudar: () => void }) {
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
  return (
    <form className="form-inline" onSubmit={registrar}>
      <input className="entrada--media" aria-label={`Nº do protocolo de ${l.obra} · ${l.descricao}`} name="numero_orgao" autoComplete="off" spellCheck={false} maxLength={100}
        value={numero} onChange={e => setNumero(e.target.value)} />
      <button type="submit" className="btn btn--pequeno" disabled={ocupado || !numero.trim() || numero.trim() === (l.numero_orgao ?? "")}>{ocupado ? "Registrando…" : "Registrar"}</button>
      {l.familia === "mtpar" && DICA_SIGA}
      {l.familia === "mtpar" && !l.numero_orgao && <Selo classe="selo--atencao">sem protocolo SIGA</Selo>}
      <span className={gravado ? "notas__ok" : "sr-only"} role="status">{gravado}</span>
      {erro && <span className="notas__diverge">{erro}</span>}
    </form>
  );
}

export default function AguardandoPagamento({ podeEditar }: { podeEditar: boolean }) {
  const [linhas, setLinhas] = useState<Linha[] | null>(null);
  const [erro, setErro] = useState("");
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

  return (
    <section className="cartao notas-v3 nota-aguardando" aria-labelledby="titulo-aguardando">
      <div className="cartao__cabeca">
        <h2 className="cartao__titulo" id="titulo-aguardando">Enviadas ao contratante</h2>
        <span className="cartao__dica num">{linhas.length === 1 ? "1 nota" : `${linhas.length} notas`}</span>
      </div>
      {linhas.length === 0 ? <div className="vazio vazio--curto"><p>Nenhuma nota aguardando pagamento.</p></div> : (
        <Rolagem rotulo="Notas aguardando pagamento" alta>
          <table className="tabela">
            <thead>
              <tr>
                <th scope="col">Obra</th><th scope="col">Descrição</th><th scope="col">Órgão</th>
                <th scope="col" className="col-num">Valor</th><th scope="col">Enviada em</th><th scope="col">Origem</th>
                <th scope="col">Nº do protocolo no órgão</th>
              </tr>
            </thead>
            <tbody>
              {linhas.map(l => (
                <tr key={l.medicao_id}>
                  <td><Link className="nome-link truncar" title={l.obra} para={{ tela: "obra", id: l.contrato_id, aba: "medicoes" }}>{l.obra}</Link></td>
                  <td><Link para={{ tela: "medicao", obra: l.contrato_id, id: l.medicao_id }}>{l.descricao}</Link></td>
                  <td>{l.orgao}</td>
                  <td className="col-num dinheiro num nota-mono">{brl(l.valor_centavos)}</td>
                  <td className="num">{data(l.enviada_em)}</td>
                  <td>{l.origem === "externo" ? "Por fora" : "Sistema"}</td>
                  {/* B-09 (10/10/2026): quem so' consulta ve o numero, sem o formulario (que dava 403) */}
                  <td>{podeEditar ? <NumeroSiga l={l} aoMudar={() => void carregar()} />
                    : <>{l.numero_orgao ?? "—"}{l.familia === "mtpar" && <> {DICA_SIGA}</>}</>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Rolagem>
      )}
    </section>
  );
}
