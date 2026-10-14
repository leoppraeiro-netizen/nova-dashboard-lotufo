import { useCallback, useEffect, useState } from "react";
import { api } from "./api";
import EnviarNota from "./EnviarNota";
import { IconeAlerta } from "./icones";
import { iniciarEnvio, IconeCheck, mensagem, notasDe, type Envio, type ListaEnvios } from "./NotasAEnviar";
import "./etapas.css";

// Fluxo da medicao numa pagina so' (opcao A, 2026-10-09): Espelho, Faturamento, Nota fiscal, Envio ao orgao e
// Pagamento. A etapa da vez vem do estado da medicao; as feitas ficam recolhidas, as seguintes bloqueadas.

export const ETAPAS = ["Espelho", "Faturamento", "Nota fiscal", "Envio ao órgão", "Pagamento"] as const;

/** 1..5 = a etapa da vez; 6 = tudo feito (recebida); 0 = medicao encerrada por excecao (cancelada, desistida). */
export function etapaDe(estado: string): number {
  switch (estado) {
    case "prevista": return 1;
    case "espelho_gerado": return 2;
    case "espelho_enviado": return 3;
    case "nota_emitida": return 4;
    case "protocolada": case "nf_emitida": return 5;
    case "recebida": return 6;
    default: return 0;
  }
}

export type SituacaoEtapa = "feita" | "atual" | "futura";
export function situacaoDa(n: number, atual: number): SituacaoEtapa {
  return atual === 0 || n < atual ? "feita" : n === atual ? "atual" : "futura";
}

/** A barra no alto: cada etapa e' um link para o cartao dela. */
export function BarraEtapas({ atual }: { atual: number }) {
  return (
    <nav className="etapas-barra" aria-label="Etapas da medição">
      <ol>
        {ETAPAS.map((t, i) => {
          const n = i + 1;
          const s = situacaoDa(n, atual);
          return (
            <li key={t} className={`etapas-barra__item etapas-barra__item--${s}`} aria-current={s === "atual" ? "step" : undefined}>
              <a href={`#etapa-${n}`}>
                <span className="etapas-barra__n" aria-hidden="true">{s === "feita" ? <IconeCheck /> : n}</span>
                <span>{t}</span>
              </a>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

/** O cartao de uma etapa. Feita: recolhida (abre no clique; `aberta` a abre quando ainda ha' o que fazer nela, como
 *  a FRC do consorcio na etapa 3). Futura: so' o titulo e o que a libera. */
export function Etapa({ n, situacao, resumo, aberta, children }: {
  n: number; situacao: SituacaoEtapa; resumo?: React.ReactNode; aberta?: boolean; children?: React.ReactNode;
}) {
  const titulo = ETAPAS[n - 1];
  const marca = <span className={`etapa__n etapa__n--${situacao}`} aria-hidden="true">{situacao === "feita" ? <IconeCheck /> : n}</span>;
  if (situacao === "feita") {
    return (
      <details className="etapa etapa--feita" id={`etapa-${n}`} open={aberta || undefined}>
        <summary className="etapa__cabeca">{marca}<span className="etapa__titulo">{titulo}</span>
          {resumo && <span className="etapa__resumo">{resumo}</span>}</summary>
        <div className="etapa__corpo">{children}</div>
      </details>
    );
  }
  if (situacao === "futura") {
    return (
      <section className="etapa etapa--futura" id={`etapa-${n}`} aria-label={`Etapa ${n}: ${titulo}`}>
        <div className="etapa__cabeca">{marca}<span className="etapa__titulo">{titulo}</span>
          <span className="etapa__resumo">libera depois da etapa {n - 1}</span></div>
      </section>
    );
  }
  return (
    <section className="etapa etapa--atual" id={`etapa-${n}`} aria-labelledby={`etapa-${n}-titulo`}>
      <div className="etapa__cabeca">{marca}<h2 className="etapa__titulo" id={`etapa-${n}-titulo`}>{titulo}</h2>
        {resumo && <span className="etapa__resumo">{resumo}</span>}</div>
      <div className="etapa__corpo">{children}</div>
    </section>
  );
}

/** Etapa 4 na pagina da medicao: o envio de Notas a enviar que contem esta medicao (medicao e reajuste juntos
 *  quando o orgao junta). Sem protocolo ainda, um botao o inicia; com protocolo, o envio aparece aqui mesmo. */
export function EnvioDaMedicao({ medicaoId, podeEditar, aoMudar, versaoDocs = 0, aoAnexarItem }: {
  medicaoId: number; podeEditar: boolean; aoMudar: (aviso?: string) => void; versaoDocs?: number;
  aoAnexarItem?: () => void;   // issue #148: FRC assinada anexada aqui fecha a etapa 3
}) {
  const [envio, setEnvio] = useState<Envio | null | undefined>(undefined);
  const [pid, setPid] = useState<number | null>(null);
  const [erro, setErro] = useState("");
  const [ocupado, setOcupado] = useState(false);

  const carregar = useCallback(async () => {
    try {
      const l = await api<ListaEnvios>("/api/notas/a-enviar");
      const e = l.envios.find(x => x.medicao_ids.includes(medicaoId)) ?? null;
      setEnvio(e); setPid(e?.protocolo_id ?? null); setErro("");
    } catch (x) { setErro(mensagem(x)); setEnvio(null); }
  }, [medicaoId]);
  useEffect(() => { void carregar(); }, [carregar]);

  if (envio === undefined) return <p className="campo__nota">Conferindo o envio…</p>;
  if (erro) return <p className="erro" role="alert"><IconeAlerta className="icone icone--p" />Não foi possível ler o envio: {erro}</p>;
  if (!envio) {
    return <p className="campo__nota">Esta medição não aparece em Notas a enviar: confira se a obra tem o órgão no cadastro.</p>;
  }
  if (pid) {
    // issue #100: NF ou FRC anexada na etapa 3 com o envio aberto faz o envio ler os anexos de novo
    return <EnviarNota key={pid} protocoloId={pid} podeEditar={podeEditar} versao={versaoDocs}
      embutido={{ aoConcluir: aoMudar, aoTrocar: setPid, aoAnexarItem }} />;
  }
  const outras = envio.medicao_ids.length > 1;
  return (
    <div className="pilha">
      <p>{envio.descricao} · {notasDe(envio)}{outras ? " · vão no mesmo e-mail, como o órgão pede" : ""}.</p>
      {envio.aviso && <p className="campo__nota">{envio.aviso}</p>}
      {podeEditar && (
        <div className="form-inline">
          <button type="button" className="btn btn--primario btn--grande" disabled={ocupado || envio.situacao === "bloqueado"}
            onClick={async () => {
              setOcupado(true); setErro("");
              try { setPid(await iniciarEnvio(envio.contrato_id, envio.medicao_ids, envio.familia)); }
              catch (x) { setErro(mensagem(x)); }
              finally { setOcupado(false); }
            }}>{ocupado ? "Abrindo…" : "Começar o envio"}</button>
          {envio.situacao === "bloqueado" && <span className="campo__nota">Envio bloqueado: veja os documentos em Notas a enviar.</span>}
        </div>
      )}
    </div>
  );
}
