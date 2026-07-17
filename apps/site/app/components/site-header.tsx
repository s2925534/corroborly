import Link from "next/link";
import { LogoMark } from "./logo";

export function SiteHeader() {
  return (
    <header className="site-header">
      <Link href="/" className="site-header-brand">
        <LogoMark />
        <span>Corroborly</span>
      </Link>
      <nav className="site-header-nav">
        <a href="#products">Products</a>
        <a href="#philosophy">How it works</a>
        <a href="https://github.com/s2925534/corroborly" target="_blank" rel="noopener">
          GitHub
        </a>
      </nav>
      <a href="https://folio.corroborly.com" className="site-header-cta">
        Open Folio
      </a>
    </header>
  );
}
