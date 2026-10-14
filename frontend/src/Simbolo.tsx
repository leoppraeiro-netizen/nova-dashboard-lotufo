// Simbolo da marca (docs/identidade-visual.md): a letra L em quatro quadrados arredondados numa grade 2x3 —
// a coluna esquerda cheia e a celula de baixo a' direita; as outras duas ficam vazias. Cor por currentColor.
export default function Simbolo({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 22 34" fill="currentColor" aria-hidden="true">
      <rect x="0" y="0" width="10" height="10" rx="2" />
      <rect x="0" y="12" width="10" height="10" rx="2" />
      <rect x="0" y="24" width="10" height="10" rx="2" />
      <rect x="12" y="24" width="10" height="10" rx="2" />
    </svg>
  );
}
