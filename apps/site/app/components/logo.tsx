export function LogoMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 64 64" width="28" height="28" className={className} aria-hidden>
      <rect width="64" height="64" rx="14" fill="#1d4ed8" />
      <text
        x="32"
        y="44"
        fontFamily="system-ui, Arial, sans-serif"
        fontSize="34"
        fontWeight="700"
        fill="#ffffff"
        textAnchor="middle"
      >
        C
      </text>
    </svg>
  );
}
