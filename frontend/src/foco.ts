/** Leva o foco a um elemento pelo id, quando ele ja' existe: o botao que abriu um formulario (ao cancelar) ou o
 *  cartao que acabou de nascer (ao criar), para o teclado e o leitor de tela nao cairem no <body>. Secao ganha
 *  `tabindex=-1` para receber o foco; controle que ja' e' focavel fica como esta' (sem sair da ordem do Tab). */
export function focarPorId(id: string): boolean {
  const el = document.getElementById(id);
  if (!el) return false;
  if (!el.matches("a[href], button, input, select, textarea, summary, [tabindex]")) el.setAttribute("tabindex", "-1");
  el.focus({ preventScroll: true });
  el.scrollIntoView({ block: "nearest" });
  return true;
}
