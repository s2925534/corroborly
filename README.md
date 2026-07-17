# Corroborly

The umbrella marketing site for `corroborly.com` — the parent brand for a small family of open, local-first research tools. The flagship product (the evidence-first research workspace, née Ledgerly/ResearchBoss) lives at `folio.corroborly.com`, a separate repo (`../ResearchBoss`); this site is `corroborly.com` root, introducing the brand and linking out to each product. Structure mirrors `../zqx` (`apps/site` pattern, deploy workflow, docker-compose) so the same NAS/Traefik/Cloudflare Tunnel deployment approach can be reused.

## What's here

- `apps/site/` — Next.js marketing homepage: hero, "how it works" (deterministic-by-default / AI-opt-in philosophy, matching the flagship product's own AGENTS.md rules), and a Products section linking to Folio, ResearchCatalogue, and SourceScribe. Real content as of 2026-07-17 (previously an "under construction" placeholder). Same theme-toggle/health-check pattern as `zqx`'s site.
- `.github/workflows/deploy-site.yml` — build-and-push-to-GHCR workflow, mirroring `zqx`'s.

## Verified locally (2026-07-17)

`npm run build` and `npm run lint` both pass clean under Node 20 (via `nvm use 20` — this machine's default Node is 18, which Next.js 16.2.10 doesn't support; the Dockerfile already targets `node:20-alpine` so the Docker build path was never affected). Also ran the actual production server (`node .next/standalone/server.js`, matching the Dockerfile's final stage exactly, not just `next dev`) and confirmed `/`, `/health`, `/robots.txt`, `/sitemap.xml`, and `/icon.svg` all serve correctly.

## What's NOT done yet (needs manual action, not something achievable via available tooling)

1. **DNS/Cloudflare Tunnel routing isn't configured for `corroborly.com` itself.** `corroborly.com` is now registered (as of 2026-07-17), but no Tunnel route/NAS container exists for it yet — matching `zqx.io` / `systemsnotsilos.com`'s pattern once wired up.
2. **GHCR namespace is a placeholder.** `docker-compose.yml` and the workflow currently push to `ghcr.io/s2925534/corroborly-site` (Pedro's personal GitHub account, inferred from other repos) — swap this for a dedicated org (like `zqxio` was created for `zqx`) if this product should ship under its own GitHub org.
3. **No self-hosted GitHub Actions runner wired to this repo yet** — the `deploy` job assumes one, same as `zqx`'s and the flagship product's own `../ResearchBoss` repo (also still pending as of 2026-07-17).

Once 1–3 are done, pushing to `main` should deploy this exactly the way `zqx.io` deploys today.
