import { useCallback, useEffect, useRef, useState } from "react";
import CaixaAviso from "./CaixaAviso";
import { baseDosValores } from "./formato";
import { api, mensagemDeErro } from "./api";
import Espelho from "./Espelho";
import { BarraEtapas, Etapa, EnvioDaMedicao, etapaDe, situacaoDa } from "./Etapas";
import { FrcConsorcio } from "./Frc";
import { IconeAlerta } from "./icones";
import type { Usuario } from "./Login";
import { eventosDaMedicao, EXCECOES, FINAIS, metadeQueEspera, passoDe, PROXIMOS, resumoDoPar, rotuloDoBloco,
         rotuloDoValor, tituloMedicao, type EspelhoResumo, type MedicaoBase, type ParDaMedicao } from "./medicao";
import { FormDesmarcarFinal, FormEstado, FormFinal, FormProtocoloManual, FormRecebimento, FormSemAOutra, FormValor,
         notaDoEspelho, valorEditavel, type Agir } from "./MedicaoAtos";
import { brl, Estado, type Medicao } from "./Medicoes";
import { Notas } from "./Notas";
import { ProtocolosDaMedicao, useProtocolos } from "./Protocolo";
import { type Origem, type Rota } from "./rota";
import { Link } from "./Link";
import { fmtCompetencia, fmtDataHora, fmtDataPura } from "./tempo";
import { Migalhas, VoltarOrigem } from "./Topo";

// Pagina da medicao: o fluxo inteiro em 5 etapas (opcao A, 2026-10-09) -- Espelho, Faturamento, Nota fiscal,
// Envio ao orgao e Pagamento --, com a linha do tempo ao lado. Cada etapa tem ancora (#etapa-N): quem chega
// pela fila ou por Notas a enviar cai na etapa da vez.

type Cabecalho = { obra: string; orgao: string; instrumento: string; percentual_lotufo_bp: number };
type LinhaAndamento = { id: number; proximo_passo: string; desde: string };
type Painel = "protocolado" | "atestado" | "fora" | "recebimento" | "cancelada" | "desistida" | "final" | "desfinal"
  | "sozinha" | null;

function quando(iso: string): string {
  return iso.length > 10 ? fmtDataHora(iso) : fmtDataPura(iso);
}

export default function MedicaoPagina({ contratoId, medicaoId, usuario, origem }:
    { contratoId: number; medicaoId: number; usuario: Usuario; origem: Origem | null }) {
  const podeEditar = usuario.perfil === "engenharia" || usuario.perfil === "admin";
  const [cab, setCab] = useState<Cabecalho | null>(null);
  const [medicoes, setMedicoes] = useState<Medicao[] | null>(null);
  const [andamento, setAndamento] = useState<LinhaAndamento[]>([]);
  const [espelhos, setEspelhos] = useState<EspelhoResumo[]>([]);
  // issue #188: a execucao e o reajuste da mesma competencia (as notas dos dois, a espera e a liberacao)
  const [par, setPar] = useState<ParDaMedicao | null>(null);
  const [erro, setErro] = useState("");
  const [feito, setFeito] = useState("");
  const [salvando, setSalvando] = useState(false);
  const [painel, setPainel] = useState<Painel>(null);
  // id do botao que abriu o painel: quando ele fecha, o foco volta ali (e nao cai no <body>)
  const disparador = useRef<string | null>(null);
  const protocolos = useProtocolos(contratoId);
  const geracao = useRef(0);
  // Notas e FRC leem o mesmo anexo: o que um anexa, o outro recarrega
  const [versaoNotas, setVersaoNotas] = useState(0);
  const [versaoFrc, setVersaoFrc] = useState(0);
  const [frcPendente, setFrcPendente] = useState(false);

  const m = medicoes?.find(x => x.id === medicaoId) ?? null;

  // Tudo o que a pagina le alem dos cartoes que se leem sozinhos (espelho, notas, protocolos).
  const carregar = useCallback(async () => {
    const g = geracao.current;
    const [lista, abertas, esp, duas] = await Promise.all([
      api<Medicao[]>(`/api/contratos/${contratoId}/medicoes`),
      api<LinhaAndamento[]>(`/api/medicoes/andamento?contrato_id=${contratoId}`).catch(() => []),
      api<{ espelhos: EspelhoResumo[] }>(`/api/contratos/${contratoId}/espelho`).catch(() => ({ espelhos: [] })),
      // sem o par a pagina fica como antes (um bloco so'): a falha aqui nao derruba a medicao
      api<ParDaMedicao>(`/api/medicoes/${medicaoId}/par`).catch(() => null),
    ]);
    if (g !== geracao.current) return;
    setMedicoes(lista); setAndamento(abertas); setEspelhos(esp.espelhos ?? []);
    setPar(duas && Array.isArray(duas.metades) ? duas : null);
  }, [contratoId, medicaoId]);

  useEffect(() => {
    geracao.current += 1;
    const g = geracao.current;
    setCab(null); setMedicoes(null); setPar(null); setErro(""); setFeito(""); setPainel(null);
    api<Cabecalho>(`/api/contratos/${contratoId}/cabecalho`).then(c => { if (g === geracao.current) setCab(c); }).catch(() => {});
    carregar().catch(e => { if (g === geracao.current) setErro(mensagemDeErro(e)); });
    return () => { geracao.current += 1; };
  }, [contratoId, medicaoId, carregar]);

  useEffect(() => {
    if (painel !== null || !disparador.current) return;
    document.getElementById(disparador.current)?.focus();
    disparador.current = null;
  }, [painel]);

  // Titulo da aba do navegador: a obra e a medicao.
  useEffect(() => {
    document.title = `${cab?.obra ?? "Obra"} · ${m ? tituloMedicao(m) : "Medição"} · grupolotufo`;
  }, [cab, m]);

  // Toda acao recarrega a pagina inteira (a medicao, a fila e os protocolos): o estado de uma secao muda o
  // que falta nas outras. Devolve se a GRAVACAO foi aceita, como na tabela da obra.
  const recarregar = () => { void carregar().catch(() => {}); void protocolos.carregar(); };
  const agir: Agir = async (fn, mensagemFeito) => {
    setErro(""); setFeito(""); setSalvando(true);
    let gravou = false;
    try {
      await fn();
      gravou = true;
      if (mensagemFeito) setFeito(mensagemFeito);
      await carregar();
      await protocolos.carregar();
    } catch (e) {
      setErro(gravou ? "Gravado, mas a página não recarregou — recarregue para ver o resultado."
        : mensagemDeErro(e));
    } finally { setSalvando(false); }
    return gravou;
  };

  const titulo = m ? tituloMedicao(m) : "Medição";
  const obra = cab?.obra ?? "Obra";
  const linha = andamento.find(x => x.id === medicaoId);
  // issue #188: a metade pronta que espera a outra (orgao que junta); nesta pagina o passo da vez e' a espera
  const pronta = metadeQueEspera(par);
  const esperaAqui = pronta?.medicao_id === medicaoId ? pronta.espera : null;
  const passo = esperaAqui ? { rotulo: esperaAqui.texto.charAt(0).toUpperCase() + esperaAqui.texto.slice(1), secao: "etapa-3" }
    : passoDe(linha?.proximo_passo);
  const aqui: Rota = { tela: "medicao", obra: contratoId, id: medicaoId };

  const cabeca = (
    <header className="topbar topbar--detalhe">
      <div className="topbar__trilha">
        <VoltarOrigem origem={origem} alemDe={["obras"]} />
        <Migalhas origem={origem} itens={[{ rotulo: "Obras", para: { tela: "obras" } },
          { rotulo: obra, para: { tela: "obra", id: contratoId, aba: "medicoes" } }, { rotulo: titulo }]} />
      </div>
      <div className="topbar__linha topbar__linha--quebra">
        <h1 className="topbar__titulo" title={`${obra} · ${titulo}`}>{obra} · {titulo}</h1>
        {cab && <span className="topbar__meta" title={`${cab.orgao} · ${cab.instrumento}`}>{cab.orgao} · {cab.instrumento}</span>}
        {/* a medicao declara a base dos valores, como a obra (principio 7) */}
        {cab && <span className="topbar__meta topbar__base" title={baseDosValores(cab.percentual_lotufo_bp)}>{baseDosValores(cab.percentual_lotufo_bp)}</span>}
      </div>
    </header>
  );

  if (erro && !medicoes) {
    return (
      <>{cabeca}<div className="pagina">
        <div className="form-inline">
          <p className="erro" role="alert"><IconeAlerta className="icone icone--p" />Não foi possível abrir a medição: {erro}</p>
          <button type="button" className="btn" onClick={() => { setErro(""); void carregar().catch(e => setErro(mensagemDeErro(e))); }}>Tentar de novo</button>
        </div>
      </div></>
    );
  }
  if (!medicoes) {
    return <>{cabeca}<div className="pagina"><section className="cartao"><div className="vazio"><p>Carregando a medição…</p></div></section></div></>;
  }
  if (!m) {
    return (
      <>{cabeca}<div className="pagina">
        <section className="cartao"><div className="vazio">
          <p className="vazio__titulo">Esta medição não é desta obra</p>
          <p><Link className="link" para={{ tela: "obra", id: contratoId, aba: "medicoes" }}>Ver as medições de {obra}</Link></p>
        </div></section>
      </div></>
    );
  }

  // issue #188: pronta e esperando a outra metade, a medicao fica na etapa 3 (Nota fiscal) em espera
  const atual = esperaAqui ? 3 : etapaDe(m.estado);
  const sit = (n: number) => situacaoDa(n, atual);
  const metades = par?.metades.length === 2 ? par.metades : [];
  const medicaoDa = (id: number) => medicoes.find(x => x.id === id);
  const umaCompleta = metades.some(x => x.completa) && !metades.every(x => x.completa);
  const minha = metades.find(x => x.medicao_id === m.id);
  const espVigente = espelhos.find(e => e.situacao === "vigente" && e.medicoes.some(x => x.id === m.id));
  const valor = m.valor_protocolado_centavos;
  const abrir = (p: Painel, id: string) => { disparador.current = id; setErro(""); setFeito(""); setPainel(p); };
  const fechar = () => setPainel(null);
  const irmas = medicoes.filter(x => x.numero === m.numero && x.id !== m.id);
  const lib = minha?.liberacao;
  // a liberacao vem da auditoria, como as edicoes de valor (mesmo formato de data): entra na linha do tempo junto delas
  const base: MedicaoBase = m;
  const comLiberacao: MedicaoBase = lib ? { ...base, edicoes_valor: [...(base.edicoes_valor ?? []), { data: lib.em,
    texto: `Envio liberado sem ${m.tipo === "execucao" ? "o reajuste" : "a medição"}${lib.por ? ` por ${lib.por}` : ""}. `
      + `Justificativa: “${lib.justificativa ?? ""}”` }] } : m;
  const eventos = eventosDaMedicao(comLiberacao, espelhos, protocolos.dados?.protocolos ?? []);
  const registrados = m.protocolos.filter(p => !p.protocolo_id);
  const ultimo = eventos.at(-1);
  const listaEventos = eventos.length === 0
    ? <p className="campo__nota">Nada registrado ainda.</p>
    : <ol className="linha-tempo">{eventos.map((e, i) => <li key={i}><span className="num linha-tempo__data">{quando(e.data)}</span> {e.texto}</li>)}</ol>;
  const listaIrmas = irmas.map((x, i) => (
    <span key={x.id}>{i > 0 && " · "}
      <Link para={{ tela: "medicao", obra: contratoId, id: x.id }}>{tituloMedicao(x)}</Link> (<Estado m={x} />)
    </span>
  ));

  return (
    <>
      {cabeca}
      <div className="pagina">
        {/* com um painel aberto, o erro aparece dentro dele, perto de onde se agiu */}
        {erro && painel === null && <p className="erro" role="alert"><IconeAlerta className="icone icone--p" />{erro}</p>}
        {/* regiao viva sempre montada: o leitor de tela so' anuncia o texto que CHEGA numa regiao ja' existente */}
        <p className={feito ? "notas__ok" : "sr-only"} role="status">{feito}</p>
        <div className="com-lateral">
          <div className="pilha">
            {/* orgao que separa (MTPAR, SES): uma trilha por metade; onde junta, a barra da medicao com a espera */}
            {metades.length > 0 && !par?.junta
              ? metades.map(x => <BarraEtapas key={x.medicao_id} atual={etapaDe(x.estado)}
                  rotulo={x.tipo === "execucao" ? "Execução" : "Reajuste"}
                  pagina={x.medicao_id === m.id ? undefined : { tela: "medicao", obra: contratoId, id: x.medicao_id }} />)
              : atual > 0 && <BarraEtapas atual={atual} espera={!!esperaAqui} />}
            {/* Cabecalho da medicao: estado, proximo passo, valor e os atos que nao sao de uma etapa */}
            <section className="cartao" aria-label="Resumo da medição">
              <div className="cartao__corpo">
              {/* grade de 4 colunas: competencia, estado, proximo passo e o valor (o principal da tela, em Display) */}
              <div className="resumo-grade resumo-grade--medicao">
                <div className="resumo-grade__par">
                  <div className="dado"><span className="resumo__rotulo">Competência</span>
                    <span className="dado__valor num">{fmtCompetencia(m.competencia)}</span></div>
                </div>
                <div className="resumo-grade__par">
                  <div className="dado"><span className="resumo__rotulo">Estado</span>
                    <span className="dado__valor"><Estado m={m} /></span></div>
                </div>
                <div className="resumo-grade__par">
                  {passo && (
                    <div className="dado"><span className="resumo__rotulo">Próximo passo</span>
                      <span className="dado__valor">
                        {passo.secao
                          ? <Link className="link forte" para={aqui} secao={passo.secao}>{passo.rotulo}</Link>
                          : passo.rotulo}
                      </span>
                      {linha?.desde && <span className="campo__nota">desde {fmtDataPura(linha.desde)}</span>}
                    </div>
                  )}
                </div>
                <div className="resumo-grade__par resumo-grade__par--valor">
                  <div className="dado">
                    <div className="dado__cabeca">
                      <span className="resumo__rotulo">{rotuloDoValor(m.estado) === "protocolado" ? "Protocolado" : "Valor da medição"}</span>
                      {valorEditavel(m, "protocolado", podeEditar) && (
                        <button type="button" id="ato-protocolado" className="btn btn--pequeno" disabled={salvando} onClick={() => abrir("protocolado", "ato-protocolado")}>
                          {valor === null ? "Definir o valor" : "Editar o valor"}
                        </button>
                      )}
                      {/* A-16 (10/10/2026): no lugar do botao, diz de onde o valor vem e por que nao se edita */}
                      {podeEditar && notaDoEspelho(m) && <span className="campo__nota">{notaDoEspelho(m)}</span>}
                    </div>
                    <span className="dado__valor dado__valor--principal num">{brl(valor)}</span>
                  </div>
                  {(m.valor_atestado_centavos !== null || valorEditavel(m, "atestado", podeEditar)) && (
                    <div className="dado">
                      <div className="dado__cabeca">
                        <span className="resumo__rotulo">Atestado</span>
                        {valorEditavel(m, "atestado", podeEditar) && (
                          <button type="button" id="ato-atestado" className="btn btn--pequeno" disabled={salvando} onClick={() => abrir("atestado", "ato-atestado")}>
                            {m.valor_atestado_centavos === null ? "Definir o atestado" : "Editar o atestado"}
                          </button>
                        )}
                      </div>
                      <span className="dado__valor num">{brl(m.valor_atestado_centavos)}</span>
                    </div>
                  )}
                </div>
                {podeEditar && (
                  <div className="form-inline resumo-medicao__atos">
                    {m.final !== 1 && !EXCECOES.includes(m.estado) && (
                      <button type="button" id="ato-final" className="btn btn--pequeno" disabled={salvando}
                        title="Marcar como a última medição do contrato: o contrato entra em encerramento"
                        onClick={() => abrir("final", "ato-final")}>Marcar como medição final</button>
                    )}
                    {m.final === 1 && (
                      <button type="button" id="ato-desfinal" className="btn btn--pequeno" disabled={salvando}
                        title="Desfazer a marcação de medição final (pede o motivo)"
                        onClick={() => abrir("desfinal", "ato-desfinal")}>Desmarcar a medição final</button>
                    )}
                    {(PROXIMOS[m.estado] ?? []).filter(e => e !== "recebida").map(e => (
                      <button key={e} type="button" id={`ato-${e}`} className="btn btn--pequeno" disabled={salvando}
                        onClick={() => abrir(e as "cancelada" | "desistida", `ato-${e}`)}>
                        {e === "cancelada" ? "Cancelar a medição" : "Registrar desistência"}
                      </button>
                    ))}
                  </div>
                )}
              </div>
              </div>
              {(painel === "protocolado" || painel === "atestado") && (
                <div className="cartao__corpo">
                  <FormValor m={m} campo={painel} salvando={salvando} agir={agir} aoFechar={fechar} erro={erro} />
                </div>
              )}
              {(painel === "cancelada" || painel === "desistida") && (
                <div className="cartao__corpo">
                  <FormEstado m={m} estado={painel} salvando={salvando} agir={agir} aoFechar={fechar} erro={erro} />
                </div>
              )}
              {/* F-92: medicao final (e desfazer) por formulario em linha, no lugar de confirm/prompt do navegador */}
              {painel === "final" && (
                <div className="cartao__corpo">
                  <FormFinal m={m} salvando={salvando} agir={agir} aoFechar={fechar} erro={erro} />
                </div>
              )}
              {painel === "desfinal" && (
                <div className="cartao__corpo">
                  <FormDesmarcarFinal m={m} salvando={salvando} agir={agir} aoFechar={fechar} erro={erro} />
                </div>
              )}
            </section>

            {/* Tela estreita: a lateral desce, e a linha do tempo vem logo depois do que falta, recolhida,
                com o ultimo acontecimento a vista (a pergunta da pagina e' tambem "o que ja aconteceu") */}
            <section className="cartao so-estreito" aria-labelledby="titulo-linha-tempo-curta">
              <div className="cartao__cabeca">
                <h2 className="cartao__titulo" id="titulo-linha-tempo-curta">Linha do tempo</h2>
                <span className="cartao__dica">{ultimo ? `o último em ${quando(ultimo.data)}: ${ultimo.texto}` : "nada registrado ainda"}</span>
              </div>
              {eventos.length > 0 && (
                <details className="cartao__corpo detalhes">
                  <summary>{eventos.length === 1 ? "Ver o acontecimento" : `Ver os ${eventos.length} acontecimentos`}</summary>
                  {listaEventos}
                </details>
              )}
              {irmas.length > 0 && <p className="cartao__corpo campo__nota">Da mesma competência: {listaIrmas}</p>}
            </section>

            <Etapa n={1} situacao={sit(1)} resumo={espVigente
              ? `nº ${espVigente.numero} · versão ${espVigente.versao} · gerado em ${fmtDataHora(espVigente.criado_em)}${espVigente.criado_por_nome ? ` por ${espVigente.criado_por_nome}` : ""}`
              : m.espelho_em ? `gerado em ${quando(m.espelho_em)}` : "medição sem espelho pelo sistema"}>
              <p className="campo__nota">O espelho, os arquivos e "Gerar de novo" ficam na etapa 2.</p>
            </Etapa>

            <Etapa n={2} situacao={sit(2)} resumo={espVigente?.envio ? `enviado ao faturamento em ${fmtDataHora(espVigente.envio.enviado_em)}` : undefined}>
              <Espelho contratoId={contratoId} podeEditar={podeEditar} aoMudar={recarregar} medicao={{ id: m.id, tipo: m.tipo }} />
            </Etapa>

            {/* consorcio com a FRC ainda por fazer: a etapa 3 fica aberta mesmo depois da nota da Lotufo, e (issue #148)
                depois de gerada, ate' a assinada estar anexada: e' dali que se baixa a FRC para assinar. Medicao
                encerrada (recebida, cancelada, desistida) nao tem mais o que fazer ali */}
            <Etapa n={3} situacao={sit(3)} aberta={frcPendente && !FINAIS.includes(m.estado)} resumo={metades.length > 0
              ? resumoDoPar(metades)
              : m.nota_emitida_em ? `nota emitida em ${fmtDataPura(m.nota_emitida_em.slice(0, 10))}` : undefined}>
              {sit(3) === "atual" && <p className="campo__nota">O sistema lê o RM a cada 1 hora e liga a nota sozinho. Se ela não aparecer, anexe o PDF aqui.</p>}
              <div id="notas">
                {/* issue #188: a execucao e o reajuste da mesma competencia lado a lado; a nota anexada num bloco vai
                    para a medicao daquele bloco */}
                {metades.length > 0 ? (
                  <div className="notas-blocos">
                    {metades.map(x => {
                      const mx = medicaoDa(x.medicao_id);
                      return mx ? (
                        <section key={`${x.medicao_id}-${versaoNotas}`} className="notas-bloco" aria-label={rotuloDoBloco(mx)}>
                          <Notas medicao={mx} rotulo={rotuloDoBloco(mx)} podeEditar={podeEditar && !FINAIS.includes(mx.estado)}
                            podeDesfazer={usuario.perfil === "admin"}
                            aoMudar={() => { recarregar(); setVersaoFrc(v => v + 1); }} />
                        </section>
                      ) : null;
                    })}
                  </div>
                ) : (
                  <Notas key={versaoNotas} medicao={m} podeEditar={podeEditar && !FINAIS.includes(m.estado)}
                    podeDesfazer={usuario.perfil === "admin"}
                    aoMudar={() => { recarregar(); setVersaoFrc(v => v + 1); }} />
                )}
              </div>
              {pronta && (
                <CaixaAviso nivel="atencao">
                  {par?.orgao ? `Na ${par.orgao}` : "Neste órgão"} a medição e o reajuste vão no mesmo e-mail. O envio ao
                  órgão abre quando chegarem as notas {pronta.tipo === "execucao" ? "do reajuste" : "da medição"}.
                </CaixaAviso>
              )}
              {metades.length > 0 && !par?.junta && umaCompleta && (
                <p className="campo__nota">Neste órgão a medição e o reajuste vão em ofícios e e-mails separados: cada um segue quando as suas notas chegam.</p>
              )}
              {podeEditar && pronta && painel !== "sozinha" && (
                <div>
                  <button type="button" id="ato-sozinha" className="btn btn--pequeno" disabled={salvando}
                    onClick={() => abrir("sozinha", "ato-sozinha")}>
                    {pronta.tipo === "execucao" ? "Enviar a medição sem o reajuste…" : "Enviar o reajuste sem a medição…"}
                  </button>
                </div>
              )}
              {painel === "sozinha" && pronta && (
                <FormSemAOutra pronta={pronta} orgao={par?.orgao ?? null} salvando={salvando} agir={agir} aoFechar={fechar} erro={erro} />
              )}
              <FrcConsorcio medicaoId={m.id} podeEditar={podeEditar && !FINAIS.includes(m.estado)} versao={versaoFrc}
                aoMudar={() => { recarregar(); setVersaoNotas(v => v + 1); }}
                aoLer={f => setFrcPendente(f.disponivel && (!f.frc || f.frc.desatualizada || !f.assinada))} />
            </Etapa>

            <Etapa n={4} situacao={sit(4)} resumo={m.protocolos.length > 0 ? `enviada em ${fmtDataPura(m.protocolos[m.protocolos.length - 1].data)}` : undefined}>
              {sit(4) === "atual" && <EnvioDaMedicao medicaoId={m.id} podeEditar={podeEditar} versaoDocs={versaoNotas + versaoFrc}
                aoAnexarItem={() => setVersaoFrc(v => v + 1)}
                aoMudar={aviso => { setErro(""); setFeito(aviso ?? ""); recarregar(); }} />}
              {/* o historico dos envios so' depois de enviada: na etapa da vez, o envio acima ja' e' o caminho */}
              {sit(4) === "feita" && <ProtocolosDaMedicao contratoId={contratoId} medicaoId={m.id} dados={protocolos.dados} erro={protocolos.erro}
                carregar={protocolos.carregar} podeEditar={podeEditar} aoMudar={() => void carregar().catch(() => {})}
                vazio={registrados.length > 0 ? "Nenhum envio pelo sistema." : "Nenhum envio desta medição ainda."}>
              {registrados.map(p => (
                <p key={`reg-${p.id}`}>
                  Protocolada em <span className="num">{fmtDataPura(p.data)}</span>
                  {p.numero_oficio ? ` · ofício ${p.numero_oficio}` : ""}{p.numero_processo ? ` · processo ${p.numero_processo}` : ""}
                  <span className="campo__nota"> · registrado fora do sistema</span>
                </p>
              ))}
              {podeEditar && !FINAIS.includes(m.estado) && painel !== "fora" && (
                <div>
                  <button type="button" id="ato-fora" className="btn btn--pequeno" disabled={salvando} onClick={() => abrir("fora", "ato-fora")}>
                    Registrar protocolo feito fora
                  </button>
                </div>
              )}
              {painel === "fora" && <FormProtocoloManual contratoId={contratoId} m={m} salvando={salvando} agir={agir} aoFechar={fechar} erro={erro} />}
              </ProtocolosDaMedicao>}
            </Etapa>

            <Etapa n={5} situacao={sit(5)} resumo={m.estado === "recebida" ? `recebida em ${m.recebida_em ? fmtDataPura(m.recebida_em) : "data não registrada"}` : undefined}>
              <div className="cartao__corpo pilha">
                {m.estado === "recebida" && <p>Recebida em <span className="num">{m.recebida_em ? fmtDataPura(m.recebida_em) : "data não registrada"}</span>.</p>}
                {["protocolada", "nf_emitida"].includes(m.estado) && (
                  <p>Aguardando o órgão{linha?.desde ? <> desde <span className="num">{fmtDataPura(linha.desde)}</span></> : ""}. O RM marca a baixa sozinho.</p>
                )}
                {["cancelada", "desistida"].includes(m.estado) && <p className="campo__nota">Medição {m.estado}: não há recebimento.</p>}
                {!FINAIS.includes(m.estado) && !["protocolada", "nf_emitida"].includes(m.estado) && (
                  <p className="campo__nota">Depois do protocolo.</p>
                )}
                {(m.notas ?? []).filter(n => n.recebido_centavos > 0).map(n => (
                  <p key={n.nota_id} className="num">
                    NF {Number(n.numero) || n.numero}: recebido {brl(n.recebido_centavos)}{n.recebido_em ? ` em ${fmtDataPura(n.recebido_em)}` : ""}
                  </p>
                ))}
                {podeEditar && (PROXIMOS[m.estado] ?? []).includes("recebida") && painel !== "recebimento" && (
                  <div>
                    <button type="button" id="ato-recebimento" className="btn btn--pequeno" disabled={salvando} onClick={() => abrir("recebimento", "ato-recebimento")}>
                      Registrar recebimento
                    </button>
                  </div>
                )}
                {painel === "recebimento" && <FormRecebimento m={m} salvando={salvando} agir={agir} aoFechar={fechar} erro={erro} />}
              </div>
            </Etapa>
          </div>

          <aside className="lateral pilha so-largo" aria-label="Linha do tempo e medições da mesma competência">
            <section className="cartao" aria-labelledby="titulo-linha-tempo">
              <div className="cartao__cabeca"><h2 className="cartao__titulo" id="titulo-linha-tempo">Linha do tempo</h2></div>
              <div className="cartao__corpo">{listaEventos}</div>
            </section>
            {irmas.length > 0 && (
              <section className="cartao" aria-labelledby="titulo-mesma-competencia">
                <div className="cartao__cabeca"><h2 className="cartao__titulo" id="titulo-mesma-competencia">Da mesma competência</h2></div>
                <ul className="cartao__corpo lista-simples">
                  {irmas.map(x => (
                    <li key={x.id}>
                      <Link className="link" para={{ tela: "medicao", obra: contratoId, id: x.id }}>{tituloMedicao(x)}</Link>
                      {" · "}<Estado m={x} />
                    </li>
                  ))}
                </ul>
              </section>
            )}
          </aside>
        </div>
      </div>
    </>
  );
}
