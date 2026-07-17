import { SiteHeader } from "./components/site-header";
import { SiteFooter } from "./components/site-footer";

const PHILOSOPHY_POINTS = [
  {
    title: "Deterministic by default",
    body: "Every core workflow — source review, claim tracking, citation planning, validation reports — runs fully offline with zero AI configured. Nothing about the tool depends on a model being available.",
  },
  {
    title: "AI is explicit, opt-in, per request",
    body: "AI features are never a silent default. Every AI action is a deliberate, separately-flagged choice, and every AI-generated claim is grounded back to a real source, claim, or note — or it says so, rather than inventing an answer.",
  },
  {
    title: "Local-first, your data stays yours",
    body: "No cloud storage or remote database is required for the core workspace. Research context, source registers, and claim ledgers live in plain YAML/Markdown files you control.",
  },
];

const PRODUCTS = [
  {
    name: "Folio",
    tagline: "The research workspace",
    description:
      "Corroborly's flagship product: a CLI and web UI for managing sources, claims, citations, artefacts, research questions, and project memory — from a vague topic through a refined research question to a reviewed paper draft.",
    href: "https://folio.corroborly.com",
    linkLabel: "Open Folio",
  },
  {
    name: "ResearchCatalogue",
    tagline: "Deterministic file cataloguing",
    description:
      "A config-driven engine for creating auditable, deterministic catalogues of research source files — literature, standards, operational evidence, data exports — for any research project, not just one thesis.",
    href: "https://github.com/s2925534/research-cataloguing-standard",
    linkLabel: "View on GitHub",
  },
  {
    name: "SourceScribe",
    tagline: "Local-first transcription",
    description:
      "A CLI for transcribing meeting recordings and paper-feedback audio/video, so it can be reviewed and folded back into your research context. Local Whisper by default, no API key required.",
    href: "https://github.com/s2925534/sourcescribe",
    linkLabel: "View on GitHub",
  },
];

export default function Home() {
  return (
    <div className="site-shell">
      <SiteHeader />
      <main>
        <section className="hero">
          <h1>Evidence, corroborated.</h1>
          <p className="hero-lede">
            Corroborly is a small family of open, local-first research tools, built around one idea:
            every claim you write should trace back to real evidence — and a tool should never fill
            that gap with an invented answer.
          </p>
          <div className="hero-actions">
            <a href="https://folio.corroborly.com" className="btn btn-primary">
              Open Folio
            </a>
            <a href="#products" className="btn btn-secondary">
              See the products
            </a>
          </div>
        </section>

        <section id="philosophy" className="philosophy">
          <h2>How it works</h2>
          <div className="philosophy-grid">
            {PHILOSOPHY_POINTS.map((point) => (
              <div key={point.title} className="philosophy-card">
                <h3>{point.title}</h3>
                <p>{point.body}</p>
              </div>
            ))}
          </div>
        </section>

        <section id="products" className="products">
          <h2>Products</h2>
          <p className="products-lede">Each tool works standalone — Folio drives the others as optional, per-user integrations, never a hard requirement.</p>
          <div className="products-grid">
            {PRODUCTS.map((product) => (
              <a key={product.name} href={product.href} className="product-card" target={product.href.startsWith("http") ? "_blank" : undefined} rel={product.href.startsWith("http") ? "noopener" : undefined}>
                <h3>{product.name}</h3>
                <p className="product-tagline">{product.tagline}</p>
                <p className="product-description">{product.description}</p>
                <span className="product-link">{product.linkLabel} &rarr;</span>
              </a>
            ))}
          </div>
        </section>
      </main>
      <SiteFooter />
    </div>
  );
}
