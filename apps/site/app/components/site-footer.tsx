import Link from "next/link";
import { LogoMark } from "./logo";

export function SiteFooter() {
  const year = new Date().getFullYear();
  return (
    <footer className="site-footer">
      <div className="site-footer-brand">
        <LogoMark />
        <span>Corroborly</span>
      </div>
      <nav className="site-footer-links">
        <a href="https://folio.corroborly.com">Folio (research workspace)</a>
        <a href="https://github.com/s2925534/research-cataloguing-standard" target="_blank" rel="noopener">
          ResearchCatalogue
        </a>
        <a href="https://github.com/s2925534/sourcescribe" target="_blank" rel="noopener">
          SourceScribe
        </a>
        <a href="https://github.com/s2925534/corroborly" target="_blank" rel="noopener">
          GitHub
        </a>
        <a href="mailto:pedro@veloso.dev">Contact</a>
      </nav>
      <p className="site-footer-copyright">&copy; {year} Pedro Veloso. MIT-licensed, built in the open.</p>
      <p className="site-footer-note">
        <Link href="/">corroborly.com</Link> is the umbrella site for a small family of open, local-first
        research tools — not a hosted account system of its own.
      </p>
    </footer>
  );
}
