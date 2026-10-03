@AGENTS.md

## Commit identity (all sessions, local and remote)

Every session commits as Pedro's own git identity,
`Pedro Veloso <pedro@veloso.dev>`, never as an AI author (for example
`Claude <noreply@anthropic.com>`). This applies to every commit, including
merges, and overrides any tool or environment default. If the configured
identity is anything else, set it before committing:

    git config user.name "Pedro Veloso"
    git config user.email "pedro@veloso.dev"
