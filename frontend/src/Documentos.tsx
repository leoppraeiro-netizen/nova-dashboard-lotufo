import { Fragment, useEffect, useMemo, useRef, useState } from "react";
import { api, ApiErro, apiForm } from "./api";
import { IconeAlerta, IconeBaixar } from "./icones";
import type { Usuario } from "./Login";
import { focarPorId } from "./foco";
import { colunas, JANELA_DIAS, matriz, pendenciasDa, type EmpresaDoc, type LinhaCertidao } from "./matriz";
import { type Busca } from "./rota";
import { Link } from "./Link";
// emissao/validade sao DATAS PURAS do papel que o orgao emitiu: fmtDataPura nao passa por fuso.
import { fmtCompetencia as mesBR, fmtDataPura } from "./tempo";
import Rolagem from "./Rolagem";
import Selo from "./Selo";

/* Documentos de protocolo (bloco 4, spec §9 e §10.4; NAVEGACAO.md › Documentos). Duas gavetas por empresa:
 * CERTIDOES (validade; o sistema le o PDF arrastado e a pessoa confere) e REGULARIDADE MENSAL (o PDF do DP, por
 * competencia), numa matriz: empresas nas linhas (com pendencia primeiro), tipos de certidao e a regularidade do
 * mes nas colunas. O que e' exigido vem do cadastro do orgao; a tela so' mostra o que o servidor respondeu
 * (`documentos.painel`), sem recalcular regra. Filtro na URL: ?pendentes=1.
 */

type Linha = LinhaCertidao;
type Regularidade = NonNullable<EmpresaDoc["regularidade"]>;
type Painel = { hoje: string; empresas: EmpresaDoc[] };
type Lida = {
  tipo: string; tipo_nome: string; natureza: string; entidade_id: number; entidade: string;
  emissao: string; validade: string; numero: string | null; validade_calculada: boolean; ocr?: boolean;
};
// `lidos` (gate Sol S6, 10/10/2026): datas lidas fora do prazo normal; a digitacao abre ja' preenchida com elas.
type RespostaLer = { ok: true; leitura: Lida } | { ok: false; motivo: string; mensagem: string; digitavel: boolean;
  lidos?: { entidade_id: number; tipo: string; emissao: string; validade: string; natureza: string } };

type Manual = { entidade_id: string; tipo: string; emissao: string; validade: string; natureza: string };
type ItemFila = {
  chave: number; arquivo: File; estado: "lendo" | "conferir" | "digitar" | "recusada" | "gravada";
  leitura?: Lida; mensagem?: string; manual?: Manual;
};

const TIPOS: { chave: string; rotulo: string }[] = [
  { chave: "federal", rotulo: "Federal (RFB/PGFN)" }, { chave: "fgts", rotulo: "FGTS (CRF)" },
  { chave: "trabalhista", rotulo: "Trabalhista (CNDT)" }, { chave: "estadual", rotulo: "Estadual (SEFAZ/PGE-MT)" },
  { chave: "municipal", rotulo: "Municipal (Cuiabá)" }, { chave: "falencia", rotulo: "Falência (TJMT)" },
];
const ROTULO_TIPO = Object.fromEntries(TIPOS.map(t => [t.chave, t.rotulo]));
const NATUREZA: Record<string, string> = { negativa: "negativa", positiva_efeito_negativa: "positiva com efeito de negativa" };

function mensagem(e: unknown): string {
  return e instanceof ApiErro ? e.message : String(e);
}
function cnpjBR(c: string): string {
  return c.length === 14 ? `${c.slice(0, 2)}.${c.slice(2, 5)}.${c.slice(5, 8)}/${c.slice(8, 12)}-${c.slice(12)}` : c;
}
// "042026 - LOTUFO ENGENHARIA.pdf" -> "2026-04": o DP nomeia o PDF pela competencia.
export function competenciaDoNome(nome: string): string {
  const m = /^(0[1-9]|1[0-2])(\d{4})\b/.exec(nome.trim());
  return m ? `${m[2]}-${m[1]}` : "";
}

// A celula da matriz: a situacao num selo curto e, embaixo, a validade (a matriz tem 7 colunas: o selo longo, com a
// data dentro, nao cabia nem a 1920).
// O selo segue a mesma janela da pendencia (decisao 5): certidao exigida que vence em ate' 30 dias diz "vence em
// N dias", mesmo que o servidor ainda a chame de em dia (o limiar do aviso e' menor). A que nao e' exigida fica neutra.
function situacaoTexto(l: Linha): { texto: string; data?: string; nivel: "ok" | "atencao" | "acao" | "neutro" } {
  const validade = l.certidao ? fmtDataPura(l.certidao.validade) : "";
  const vence = (d: number) => d <= 0 ? "vence hoje" : d === 1 ? "vence amanhã" : `vence em ${d} dias`;
  if (l.situacao === "nao_se_aplica") return { texto: "não se aplica", data: "declarado", nivel: "neutro" };
  if (!l.exigida) {
    return { texto: "não exigida", nivel: "neutro",
             data: !l.certidao ? undefined : l.situacao === "vencida" ? `vencida em ${validade}` : `até ${validade}` };
  }
  switch (l.situacao) {
    case "ok":
      return l.dias !== null && l.dias <= JANELA_DIAS ? { texto: vence(l.dias), data: `até ${validade}`, nivel: "atencao" }
        : { texto: "em dia", data: `até ${validade}`, nivel: "ok" };
    case "vencendo": return { texto: vence(l.dias ?? 0), data: `até ${validade}`, nivel: "atencao" };
    case "vencida": return { texto: "vencida", data: `em ${validade}`, nivel: "acao" };
    default: return { texto: "falta", nivel: "acao" };
  }
}

const REG_TEXTO: Record<Regularidade["situacao"], string> = {
  ok: "em dia", atrasada: "atrasada", faltando: "nenhuma anexada",
};

// "Emitir" so' onde vence ou falta: a certidao exigida vencida, faltando ou vencendo (a janela da decisao 5)
function emitir(l: Linha): boolean {
  if (!l.link_emissao || !l.exigida) return false;
  return l.situacao === "vencida" || l.situacao === "faltando" || l.situacao === "vencendo"
    || (l.situacao === "ok" && l.dias !== null && l.dias <= JANELA_DIAS);
}

// D15: "em dia" e' o estado normal e vira ponto e palavra, sem fundo; o selo com fundo fica para Atencao e Critico.
// A maiuscula inicial do selo vem do CSS; o `.estado` nao a poe, entao ela sai daqui.
function EmDia({ texto }: { texto: string }) {
  return (
    <span className="estado estado--ok">
      <span className="estado__ponto" aria-hidden="true" />{texto.charAt(0).toUpperCase() + texto.slice(1)}
    </span>
  );
}

function Celula({ l, empresa }: { l: Linha; empresa: string }) {
  const s = situacaoTexto(l);
  return (
    <>
      {s.nivel === "ok" ? <EmDia texto={s.texto} />
        : <Selo classe={s.nivel === "neutro" ? "" : `selo--${s.nivel}`}>{s.texto}</Selo>}
      {/* A-19 (10/10/2026): a data digitada a mao nao veio do documento; o selo diz isso a quem confere */}
      {s.data && <div className="campo__nota num">{s.data}{l.certidao?.leitura === "manual" && <> <Selo classe="">digitada</Selo></>}</div>}
      {l.certidao?.natureza === "positiva_efeito_negativa" && l.situacao !== "vencida" && (
        <div className="campo__nota">positiva c/ efeito de negativa</div>
      )}
      {(l.certidao && l.situacao !== "vencida") || emitir(l) ? (
        <div className="matriz__acoes">
          {/* aria-label: o nome comeca pela palavra que se ve e diz de que certidao e' (a coluna nao entra no nome) */}
          {l.certidao && l.situacao !== "vencida" && <a href={`/api/certidoes/${l.certidao.id}/arquivo`} aria-label={`PDF da certidão ${l.tipo} de ${empresa}`}>PDF</a>}
          {emitir(l) && <a href={l.link_emissao!} target="_blank" rel="noreferrer" aria-label={`Emitir ${l.tipo} de ${empresa} (abre o site do órgão)`}>Emitir</a>}
        </div>
      ) : null}
    </>
  );
}

export default function Documentos({ usuario, busca = {} }: { usuario: Usuario; busca?: Busca }) {
  const soPendentes = busca.pendentes === "1";
  const empresaId = /^[1-9][0-9]*$/.test(busca.empresa ?? "") ? Number(busca.empresa) : null;
  const podeEditar = usuario.perfil !== "diretoria";
  const [painel, setPainel] = useState<Painel | null>(null);
  const [erro, setErro] = useState("");
  const [fila, setFila] = useState<ItemFila[]>([]);
  const [ocupado, setOcupado] = useState(false);
  const [dataZip, setDataZip] = useState("");
  const [reg, setReg] = useState<{ entidade_id: number; arquivo: File | null; competencia: string } | null>(null);
  const [erroReg, setErroReg] = useState("");
  const [gravada, setGravada] = useState("");     // "Regularidade de 08/2026 gravada para X", anunciada
  const [anuncio, setAnuncio] = useState("");     // o ultimo acontecimento da fila de anexar ou da copia do CNPJ
  const [copia, setCopia] = useState<{ entidade_id: number; ok: boolean } | null>(null); // a ultima copia do CNPJ: a nota ao lado do botao
  // o foco volta ao "Anexar" da empresa quando o formulario da regularidade fecha (voltar ou gravar)
  const [foco, setFoco] = useState<string | null>(null);
  useEffect(() => { if (foco && focarPorId(foco)) setFoco(null); }, [foco, painel, reg]);
  const seq = useRef(0);
  const ultimaCopia = useRef<{ id: number; n: number } | null>(null);   // a mesma empresa copiada de novo muda o texto anunciado

  const carregar = async () => {
    const p = await api<Painel>("/api/documentos");
    setPainel(p);
    setDataZip(d => d || p.hoje);
  };
  useEffect(() => { carregar().catch(e => setErro(mensagem(e))); }, []);

  const atualizar = (chave: number, mudanca: Partial<ItemFila>) =>
    setFila(f => f.map(i => (i.chave === chave ? { ...i, ...mudanca } : i)));

  const receber = async (input: HTMLInputElement) => {
    const arquivos = Array.from(input.files ?? []);
    input.value = "";
    if (arquivos.length === 0) return;
    setErro("");
    const novos = arquivos.map(arquivo => ({ chave: ++seq.current, arquivo, estado: "lendo" as const }));
    setFila(f => [...novos, ...f]);
    // Um por vez, na ordem: a leitura roda em subprocesso no servidor com vagas limitadas.
    for (const item of novos) {
      const fd = new FormData();
      fd.append("arquivo", item.arquivo);
      try {
        const r = await apiForm<RespostaLer>("/api/documentos/certidoes/ler", fd);
        if (r.ok) { atualizar(item.chave, { estado: "conferir", leitura: r.leitura }); setAnuncio(`${item.arquivo.name}: lida, confira e grave.`); }
        else if (r.digitavel) {
          atualizar(item.chave, {
            estado: "digitar", mensagem: r.mensagem,
            manual: r.lidos
              ? { entidade_id: String(r.lidos.entidade_id), tipo: r.lidos.tipo, emissao: r.lidos.emissao,
                  validade: r.lidos.validade, natureza: r.lidos.natureza }
              : { entidade_id: "", tipo: "", emissao: "", validade: "", natureza: "negativa" },
          });
          setAnuncio(`${item.arquivo.name}: não deu para ler; digite os dados.`);
        }
        else { atualizar(item.chave, { estado: "recusada", mensagem: r.mensagem }); setAnuncio(`${item.arquivo.name}: recusada. ${r.mensagem}`); }
      } catch (e) {
        atualizar(item.chave, { estado: "recusada", mensagem: mensagem(e) });
        setAnuncio(`${item.arquivo.name}: recusada. ${mensagem(e)}`);
      }
    }
  };

  const gravar = async (item: ItemFila) => {
    setOcupado(true);
    const fd = new FormData();
    fd.append("arquivo", item.arquivo);
    if (item.estado === "digitar" && item.manual) {
      for (const [k, v] of Object.entries(item.manual)) if (v) fd.append(k, v);
    }
    try {
      const r = await apiForm<{ entidade: string; tipo: string; validade: string }>("/api/documentos/certidoes", fd);
      const texto = `${r.entidade} · ${ROTULO_TIPO[r.tipo] ?? r.tipo} · válida até ${fmtDataPura(r.validade)}`;
      atualizar(item.chave, { estado: "gravada", mensagem: texto });
      setAnuncio(`Gravada: ${texto}.`);
      await carregar();
    } catch (e) {
      atualizar(item.chave, { mensagem: mensagem(e), ...(item.estado === "conferir" ? { estado: "recusada" as const } : {}) });
    } finally { setOcupado(false); }
  };

  const enviarRegularidade = async (ev: React.FormEvent) => {
    ev.preventDefault();
    if (!reg?.arquivo) return;
    setOcupado(true); setErroReg(""); setGravada("");
    const fd = new FormData();
    fd.append("arquivo", reg.arquivo);
    fd.append("entidade_id", String(reg.entidade_id));
    fd.append("competencia", reg.competencia);
    const nome = painel?.empresas.find(x => x.entidade_id === reg.entidade_id)?.entidade ?? "a empresa";
    try {
      await apiForm("/api/documentos/regularidades", fd);
      setGravada(`Regularidade de ${mesBR(reg.competencia)} gravada para ${nome}.`);
      setFoco(`reg-anexar-${reg.entidade_id}`);
      setReg(null);
      await carregar();
    } catch (e) { setErroReg(mensagem(e)); } finally { setOcupado(false); }
  };

  // `navigator.clipboard` so' existe em contexto seguro, e a producao roda em http: sem ele, a copia antiga
  // (textarea + execCommand). O resultado e' anunciado; se nada funcionar, a pessoa seleciona o numero.
  const copiar = async (id: number, cnpj: string, nome: string) => {
    let ok = false;
    try { if (navigator.clipboard) { await navigator.clipboard.writeText(cnpj); ok = true; } } catch { ok = false; }
    if (!ok) {
      const area = document.createElement("textarea");
      area.value = cnpj; area.setAttribute("readonly", ""); area.style.position = "fixed"; area.style.opacity = "0";
      document.body.appendChild(area); area.select();
      try { ok = document.execCommand("copy"); } catch { ok = false; }
      area.remove();
    }
    // A regiao viva so' fala quando o texto muda: a 2a copia do mesmo CNPJ alterna a frase (N05-09).
    const n = ultimaCopia.current?.id === id ? ultimaCopia.current.n + 1 : 1;
    ultimaCopia.current = { id, n };
    const de = n === 1 ? "" : n % 2 === 0 ? " de novo" : " outra vez";
    setAnuncio(ok ? `CNPJ de ${nome} copiado${de}.` : `Não deu para copiar o CNPJ de ${nome}${de}: selecione o número.`);
    setCopia({ entidade_id: id, ok });
  };

  // A ordem (e, com ?pendentes=1, quem aparece) e' a da carga e a de cada troca de filtro; o que muda depois de
  // gravar fica no lugar ate' a pagina recarregar, para a pessoa ver o resultado na linha em que estava.
  const carregado = painel !== null;
  const ordem = useMemo(() => painel ? matriz(painel.empresas, soPendentes).map(e => e.entidade_id) : [],
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [carregado, soPendentes]);

  return (
    <div className="documentos">
      {erro && <p className="erro" role="alert"><IconeAlerta className="icone icone--p" />{erro}</p>}
      {/* sempre montada, fora do bloco de edicao: o Copiar aparece para todos os perfis e anuncia aqui */}
      <p className="sr-only" role="status">{anuncio}</p>

      {podeEditar && (
        <section className="cartao" aria-labelledby="titulo-arrastar">
          <div className="cartao__cabeca">
            <h2 className="cartao__titulo" id="titulo-arrastar">Anexar certidões</h2>
            <span className="cartao__dica">Arraste os PDFs até o botão ou escolha. O sistema lê tipo, empresa e validade; confira e grave.</span>
          </div>
          <div className="cartao__corpo">
            <label className="btn btn--primario espelho__anexar">
              Escolher PDFs<span className="sr-only"> de certidões para anexar</span>
              <input type="file" accept="application/pdf" multiple className="espelho__arquivo"
                onChange={ev => receber(ev.currentTarget)} />
            </label>
            {fila.length > 0 && (
              <ul className="documentos__fila">
                {fila.map(item => (
                  <li key={item.chave} className="documentos__item">
                    <span className="documentos__arquivo">{item.arquivo.name}</span>
                    {item.estado === "lendo" && <span className="campo__nota">lendo…</span>}
                    {item.estado === "conferir" && item.leitura && (
                      <>
                        <span>
                          {item.leitura.entidade} · {ROTULO_TIPO[item.leitura.tipo] ?? item.leitura.tipo_nome} · {NATUREZA[item.leitura.natureza]}
                          {" "}· emitida em {fmtDataPura(item.leitura.emissao)} · válida até {fmtDataPura(item.leitura.validade)}
                          {item.leitura.validade_calculada ? " (30 dias úteis)" : ""}
                          {item.leitura.numero ? ` · nº ${item.leitura.numero}` : ""}
                        </span>
                        {item.leitura.ocr && (
                          <span className="campo__nota">PDF sem texto, lido por OCR: confira empresa e datas com o PDF antes de gravar.</span>
                        )}
                        <span className="form-inline">
                          {/* botao comum: o unico primario do cartao e' o "Escolher PDFs" (F-88) */}
                          <button type="button" className="btn btn--pequeno" disabled={ocupado}
                            onClick={() => gravar(item)}>Gravar certidão<span className="sr-only"> de {item.arquivo.name}</span></button>
                          <button type="button" className="btn btn--pequeno"
                            onClick={() => setFila(f => f.filter(i => i.chave !== item.chave))}>Descartar</button>
                        </span>
                      </>
                    )}
                    {item.estado === "recusada" && <span className="notas__diverge">{item.mensagem}</span>}
                    {item.estado === "gravada" && <span className="notas__ok">gravada: {item.mensagem}</span>}
                    {item.estado === "digitar" && item.manual && (
                      <form className="form-inline" onSubmit={ev => { ev.preventDefault(); gravar(item); }}>
                        <span className="campo__nota">{item.mensagem}</span>
                        <div className="campo">
                          <label className="campo__rotulo" htmlFor={`d-ent-${item.chave}`}>Empresa</label>
                          <select id={`d-ent-${item.chave}`} required value={item.manual.entidade_id}
                            onChange={ev => atualizar(item.chave, { manual: { ...item.manual!, entidade_id: ev.target.value } })}>
                            <option value="">—</option>
                            {(painel?.empresas ?? []).map(e => <option key={e.entidade_id} value={e.entidade_id}>{e.entidade}</option>)}
                          </select>
                        </div>
                        <div className="campo">
                          <label className="campo__rotulo" htmlFor={`d-tipo-${item.chave}`}>Tipo</label>
                          <select id={`d-tipo-${item.chave}`} required value={item.manual.tipo}
                            onChange={ev => atualizar(item.chave, { manual: { ...item.manual!, tipo: ev.target.value } })}>
                            <option value="">—</option>
                            {TIPOS.map(t => <option key={t.chave} value={t.chave}>{t.rotulo}</option>)}
                          </select>
                        </div>
                        <div className="campo">
                          <label className="campo__rotulo" htmlFor={`d-em-${item.chave}`}>Emissão</label>
                          <input id={`d-em-${item.chave}`} type="date" required value={item.manual.emissao}
                            onChange={ev => atualizar(item.chave, { manual: { ...item.manual!, emissao: ev.target.value } })} />
                        </div>
                        <div className="campo">
                          <label className="campo__rotulo" htmlFor={`d-val-${item.chave}`}>
                            Validade{item.manual.tipo === "falencia" ? " (vazia: 30 dias úteis)" : ""}
                          </label>
                          <input id={`d-val-${item.chave}`} type="date" required={item.manual.tipo !== "falencia"}
                            value={item.manual.validade}
                            onChange={ev => atualizar(item.chave, { manual: { ...item.manual!, validade: ev.target.value } })} />
                        </div>
                        <div className="campo">
                          <label className="campo__rotulo" htmlFor={`d-nat-${item.chave}`}>Natureza</label>
                          <select id={`d-nat-${item.chave}`} value={item.manual.natureza}
                            onChange={ev => atualizar(item.chave, { manual: { ...item.manual!, natureza: ev.target.value } })}>
                            <option value="negativa">negativa</option>
                            <option value="positiva_efeito_negativa">positiva com efeito de negativa</option>
                          </select>
                        </div>
                        <button type="submit" className="btn btn--pequeno" disabled={ocupado}>Gravar certidão<span className="sr-only"> de {item.arquivo.name}</span></button>
                        <button type="button" className="btn btn--pequeno"
                          onClick={() => setFila(f => f.filter(i => i.chave !== item.chave))}>Descartar</button>
                      </form>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </section>
      )}

      {!painel && !erro && <p className="campo__nota">Carregando…</p>}
      {painel && painel.empresas.length === 0 && (
        <div className="vazio"><p className="vazio__titulo">Nenhuma empresa com documento exigido</p></div>
      )}

      {painel && painel.empresas.length > 0 && (() => {
        const porId = new Map(painel.empresas.map(e => [e.entidade_id, e]));
        const estaveis = ordem.map(id => porId.get(id)).filter((e): e is EmpresaDoc => e !== undefined);
        const lista = empresaId !== null ? painel.empresas.filter(e => e.entidade_id === empresaId) : estaveis;
        const nomeFiltrada = empresaId !== null ? porId.get(empresaId)?.entidade ?? "a empresa filtrada" : null;
        const cols = colunas(painel.empresas, TIPOS.map(t => t.chave));
        const comReg = painel.empresas.some(e => e.regularidade_exigida || e.regularidade);
        const pendentes = painel.empresas.filter(e => pendenciasDa(e) > 0).length;
        const qtdEmpresas = painel.empresas.length === 1 ? "1 empresa" : `${painel.empresas.length} empresas`;
        const largura = 1 + cols.length + (comReg ? 1 : 0);
        return (
          <section className="cartao" aria-labelledby="titulo-matriz">
            <div className="cartao__cabeca cartao__cabeca--quebra">
              <h2 className="cartao__titulo" id="titulo-matriz">Certidões e regularidade do mês</h2>
              {/* o recorte em vigor: todas, as com pendencia ou uma empresa so' */}
              <span className="cartao__dica num" role="status">
                {empresaId !== null ? `Só ${nomeFiltrada}, de ${qtdEmpresas}`
                  : soPendentes ? `Mostrando ${pendentes === 1 ? "a única" : `as ${pendentes}`} com pendência, de ${qtdEmpresas}`
                  : `${qtdEmpresas} · ${pendentes === 1 ? "1 com pendência" : `${pendentes} com pendência`}`}
                {" "}(pendência: vencida, falta ou vence em até {JANELA_DIAS}{"\u00a0"}dias)
              </span>
              <div className="cartao__acoes">
                {/* a data do ZIP vale para o botao de cada empresa, na linha dela; ficou na cabeca do cartao (F-88) */}
                <div className="campo campo--linha">
                  <label className="campo__rotulo" htmlFor="data-zip">ZIP: certidões vigentes em</label>
                  <input id="data-zip" type="date" value={dataZip} onChange={ev => setDataZip(ev.target.value)}
                    title="O ZIP de cada empresa junta as certidões vigentes nessa data (para licitação ou protocolo)." />
                </div>
                <Link className="btn btn--pequeno" para={{ tela: "documentos" }} busca={soPendentes || empresaId !== null ? {} : { pendentes: "1" }}>
                  {soPendentes || empresaId !== null ? "Ver todas as empresas" : "Só as com pendência"}
                </Link>
              </div>
            </div>
            {/* regiao viva sempre montada (o anuncio falha quando ela nasce ja' com o texto) */}
            <p className={gravada ? "cartao__corpo notas__ok" : "sr-only"} role="status">{gravada}</p>
            {nomeFiltrada !== null && (
              <p className="cartao__corpo">Só {nomeFiltrada} · <Link para={{ tela: "documentos" }}>ver todas as empresas</Link></p>
            )}
            {lista.length === 0 ? (
              <div className="vazio vazio--curto"><p className="vazio__titulo">{empresaId !== null ? "Essa empresa não tem documento exigido." : "Nenhuma empresa com pendência."}</p></div>
            ) : (
              <Rolagem rotulo="Certidões e regularidade por empresa" alta>
                <table className="tabela matriz">
                  <thead>
                    <tr>
                      <th scope="col">Empresa</th>
                      {cols.map(c => <th scope="col" key={c}>{ROTULO_TIPO[c] ?? c}</th>)}
                      {comReg && <th scope="col">Regularidade mensal (DP)</th>}
                    </tr>
                  </thead>
                  <tbody>
                    {lista.map((e, i) => (
                      <Fragment key={e.entidade_id}>
                        {/* zebra por empresa (F-59): cada bloco fecha com a faixa alternada */}
                        <tr className={i % 2 === 1 ? "par" : undefined}>
                          {/* a ancora da empresa: o aviso de documentos e o "Ver documentos" da obra caem aqui */}
                          <th scope="row" id={`emp-${e.entidade_id}`} className="matriz__empresa" aria-labelledby={`emp-nome-${e.entidade_id}`}>
                            <span className="forte" id={`emp-nome-${e.entidade_id}`}>{e.entidade}</span>
                            {/* CNPJ, copiar e o ZIP numa linha: a linha da empresa fica mais baixa */}
                            <div className="matriz__cnpj">
                              <span className="campo__nota num">{cnpjBR(e.cnpj)}</span>
                              <button type="button" className="btn btn--pequeno" onClick={() => void copiar(e.entidade_id, e.cnpj, e.entidade)} aria-label={`Copiar o CNPJ de ${e.entidade}`}>Copiar</button>
                              <a className="btn btn--pequeno" href={`/api/documentos/zip?entidade_id=${e.entidade_id}&data=${dataZip || painel.hoje}`}
                                aria-label={`Baixar o ZIP das certidões vigentes de ${e.entidade}`} title="ZIP das certidões vigentes">
                                <IconeBaixar className="icone icone--p" />
                              </a>
                              {/* retorno visivel da copia: some quando outra empresa e' copiada (o anuncio falado e' o status do topo) */}
                              {copia?.entidade_id === e.entidade_id && (
                                <span className="campo__nota" aria-hidden="true">{copia.ok ? "CNPJ copiado" : "Não copiou: selecione o número"}</span>
                              )}
                            </div>
                            {/* as obras que exigem a empresa (A7); com muitas, a lista fica recolhida, com a contagem a vista */}
                            {e.obras && e.obras.length > 0 && (() => {
                              const links = e.obras.map((o, i) => (
                                <Fragment key={o.contrato_id}>{i > 0 && ", "}<Link para={{ tela: "obra", id: o.contrato_id, aba: "documentos" }}>{o.obra}</Link></Fragment>
                              ));
                              return e.obras.length <= 3 ? <div className="campo__nota">exigida em {links}</div> : (
                                <details className="detalhes campo__nota"><summary>exigida em {e.obras.length} obras</summary>{links}</details>
                              );
                            })()}
                          </th>
                          {cols.map(c => {
                            const l = e.certidoes.find(x => x.chave === c);
                            return <td key={c}>{l ? <Celula l={l} empresa={e.entidade} /> : <Selo classe="">não exigida</Selo>}</td>;
                          })}
                          {comReg && (
                            <td>
                              {e.regularidade ? (
                                <>
                                  {/* fora do dia, a regularidade e' de acao (como o aviso dela) */}
                                  {e.regularidade.situacao === "ok" ? <EmDia texto={REG_TEXTO.ok} />
                                    : <Selo classe="selo--atencao" forte>{REG_TEXTO[e.regularidade.situacao]}</Selo>}
                                  {/* uma data por linha: a 1366 a nota comprida quebrava no meio de "competencia 06/2026" (F-77) */}
                                  {e.regularidade.competencia && <div className="campo__nota num">competência {mesBR(e.regularidade.competencia)}</div>}
                                  <div className="campo__nota num">esperada {mesBR(e.regularidade.esperada)}</div>
                                  {podeEditar && reg?.entidade_id !== e.entidade_id && (
                                    <button type="button" className="btn btn--pequeno" disabled={ocupado} aria-label={`Anexar regularidade de ${e.entidade}`}
                                      id={`reg-anexar-${e.entidade_id}`}
                                      onClick={() => setReg({ entidade_id: e.entidade_id, arquivo: null, competencia: e.regularidade!.esperada })}>
                                      {/* a coluna ja' diz "Regularidade": o botao mostra so' "Anexar" e diz o resto ao leitor de tela */}
                                      Anexar
                                    </button>
                                  )}
                                </>
                              ) : <Selo classe="">não exigida</Selo>}
                            </td>
                          )}
                        </tr>
                        {podeEditar && reg?.entidade_id === e.entidade_id && (
                          <tr>
                            <td colSpan={largura}>
                              <form className="form-inline" onSubmit={enviarRegularidade} aria-label={`Regularidade de ${e.entidade}`}>
                                {erroReg && <p className="erro" role="alert"><IconeAlerta className="icone icone--p" />{erroReg}</p>}
                                <label className="btn btn--pequeno espelho__anexar">
                                  <span className="arquivo-nome" title={reg.arquivo?.name}>{reg.arquivo ? reg.arquivo.name : "Escolher PDF"}</span>
                                  <span className="sr-only"> da regularidade de {e.entidade}</span>
                                  <input type="file" accept="application/pdf" className="espelho__arquivo" autoFocus
                                    onChange={ev => {
                                      const f = ev.currentTarget.files?.[0] ?? null;
                                      setReg({ ...reg, arquivo: f, competencia: (f && competenciaDoNome(f.name)) || reg.competencia });
                                    }} />
                                </label>
                                <div className="campo">
                                  <label className="campo__rotulo" htmlFor={`reg-comp-${e.entidade_id}`}>Competência</label>
                                  <input id={`reg-comp-${e.entidade_id}`} type="month" required value={reg.competencia}
                                    onChange={ev => setReg({ ...reg, competencia: ev.target.value })} />
                                </div>
                                <button type="submit" className="btn btn--primario btn--pequeno" disabled={ocupado || !reg.arquivo}>Gravar regularidade</button>
                                <button type="button" className="btn btn--pequeno"
                                  onClick={() => { setFoco(`reg-anexar-${e.entidade_id}`); setReg(null); setErroReg(""); }}>Voltar</button>
                              </form>
                            </td>
                          </tr>
                        )}
                      </Fragment>
                    ))}
                  </tbody>
                </table>
              </Rolagem>
            )}
          </section>
        );
      })()}
    </div>
  );
}
