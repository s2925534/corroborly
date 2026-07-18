const SIGNATURE_TEXT = "solved.voe";
const SIGNATURE_HREF = "https://s.reslk.com/8GQJDb";

// Each character's 8-bit ASCII code becomes its own column of 8 dots
// (filled = 1, hollow = 0).
function charToBits(char: string): number[] {
  const code = char.charCodeAt(0);
  return Array.from({ length: 8 }, (_, i) => (code >> (7 - i)) & 1);
}

export function SiteSignature() {
  return (
    <a
      className="site-signature"
      href={SIGNATURE_HREF}
      target="_blank"
      rel="noopener noreferrer"
      aria-label="Site signature"
    >
      {Array.from(SIGNATURE_TEXT).map((char, ci) => (
        <span className="site-signature__byte" key={ci} aria-hidden="true">
          {charToBits(char).map((bit, bi) => (
            <span
              key={bi}
              className={bit ? "site-signature__dot site-signature__dot--one" : "site-signature__dot"}
            />
          ))}
        </span>
      ))}
    </a>
  );
}
