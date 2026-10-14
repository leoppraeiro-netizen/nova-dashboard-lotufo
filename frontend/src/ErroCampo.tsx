import { IconeAlerta } from "./icones";

/** O erro de validação junto do campo que o causou (issue #11): o campo aponta para ele por `aria-describedby`
 *  e marca `aria-invalid`; some sozinho quando `erro` fica vazio. */
export default function ErroCampo({ id, erro }: { id: string; erro?: string }) {
  return erro ? <p className="erro" id={id} role="alert"><IconeAlerta className="icone icone--p" />{erro}</p> : null;
}
