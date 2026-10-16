import { ApiErro } from "./api";
import Janela from "./Janela";

// Issue #213 (decisao do Leo de 16/10/2026): documento faltando no envio nao bloqueia; antes de sair, a janela
// "ATENCAO: <o que falta>. Deseja continuar com o envio?" lista tudo o que falta. Ela substitui a justificativa
// escrita. "Cancelar" nao manda nada; "Continuar" manda a lista confirmada, que o servidor confere de novo: se mudou,
// ele recusa com a lista de agora (`pendenciasDoErro`) e a janela abre outra vez, com o aviso de que mudou.

/** A lista nova quando o servidor recusou por falta de confirmacao (ou por confirmacao de outra lista). */
export function pendenciasDoErro(e: unknown): string[] | null {
  if (e instanceof ApiErro && e.status === 422 && e.corpo?.codigo === "CONFIRMAR_PENDENCIAS"
    && Array.isArray(e.corpo.pendencias)) return e.corpo.pendencias as string[];
  return null;
}

export default function ConfirmarPendencias({ pendencias, mudou = false, ocupado = false, aoContinuar, aoCancelar,
  pergunta = "Deseja continuar com o envio?", rotuloContinuar = "Continuar com o envio" }: {
  pendencias: string[]; mudou?: boolean; ocupado?: boolean; aoContinuar: () => void; aoCancelar: () => void;
  pergunta?: string; rotuloContinuar?: string;
}) {
  return (
    <Janela titulo="Confirmar o envio" id="confirmar-pendencias-titulo" aoFechar={aoCancelar}>
      {mudou && <p className="campo__nota" role="status">O que falta mudou desde a sua confirmação: confira a lista de agora.</p>}
      {pendencias.length === 1 ? (
        <p><strong>ATENÇÃO:</strong> {pendencias[0]}.</p>
      ) : (
        <div>
          <p><strong>ATENÇÃO:</strong> faltam {pendencias.length} itens neste envio:</p>
          <ul className="lista-simples">{pendencias.map((p, i) => <li key={i} className="notas__diverge">{p}</li>)}</ul>
        </div>
      )}
      <p>{pergunta}</p>
      <div className="iniciar__rodape">
        <button type="button" className="btn btn--primario" disabled={ocupado} onClick={aoContinuar}>{rotuloContinuar}</button>
        <button type="button" className="btn" autoFocus onClick={aoCancelar}>Cancelar</button>
      </div>
    </Janela>
  );
}
