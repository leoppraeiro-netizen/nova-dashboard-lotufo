import { useState } from "react";

// Issue #28 (backlog G5-05): remover e' destrutivo, entao o primeiro clique so' abre a confirmacao no proprio
// lugar (o mesmo jeito do "Desativar" em Usuarios) e o pedido sai so' no segundo clique. O foco vai para o
// Cancelar, para um Enter a mais nao apagar nada. `alvo` completa o nome acessivel ("Remover o link X").
// `aviso`: o que mais se perde ao remover (ex.: o texto editado do e-mail, que e' montado de novo).
export default function ConfirmarRemocao({ alvo, ocupado, aoConfirmar, classe = "btn btn--pequeno", aviso }: {
  alvo: string; ocupado: boolean; aoConfirmar: () => void; classe?: string; aviso?: string;
}) {
  const [aberta, setAberta] = useState(false);
  if (!aberta) {
    return (
      <button type="button" className={classe} disabled={ocupado} aria-label={`Remover ${alvo}`} onClick={() => setAberta(true)}>
        Remover
      </button>
    );
  }
  return (
    <span className="form-inline">
      {aviso && <span className="campo__nota" aria-live="polite">{aviso}</span>}
      <button type="button" className={`${classe} btn--destrutivo`} disabled={ocupado}
        onClick={() => { setAberta(false); aoConfirmar(); }}>
        Confirmar a remoção<span className="sr-only">: {alvo}</span>
      </button>
      <button type="button" className={classe} autoFocus onClick={() => setAberta(false)}>Cancelar</button>
    </span>
  );
}
