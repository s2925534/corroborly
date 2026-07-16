# Flag & Opt-In Catalog

Ledgerly has accumulated a real number of explicit opt-in flags and environment
variables across phases, each documented individually near its own feature
(AGENTS.md's Privacy Rules, `docs/api/CONTRACT.md`, `.env.example`). This page
is a single index — nothing here is a new behavior, it just collects what
already exists in one place so a user or contributor can scan it.

The unifying rule (AGENTS.md): every flag that sends workspace content
somewhere beyond the local deterministic engine — to an AI provider, to an
external search API, or to a non-default database backend — requires an
**explicit, per-request opt-in**. None of these are workspace-level or
session-level toggles that silently apply to later commands; each invocation
re-states its own opt-ins.

## Per-request AI opt-ins (CLI flags / API request fields)

| Flag | Meaning | Where it applies |
| --- | --- | --- |
| `--ai` / `"ai": true` | Required on every AI-powered command/route. Without it, the command is rejected before any AI provider is contacted (`engine.ai.require_ai_flag`). | All `ledgerly ai *`, `rqs assess --ai`, `assess-novelty --ai`, `cite ai-plan`, `search ai-*`, and every `/api/v1/ai/*` + `/api/v1/search/ai-*` route. |
| `--full-file-ai` | Explicit additional opt-in for a future command that would send an entire file's content (not just a bounded excerpt) to an AI provider. | Reserved for future full-file AI commands (`engine.ai.require_full_file_ai_opt_in`); no shipped command uses it yet. |
| `--directory-ai` | Explicit additional opt-in for a future command that would send folder-level AI context (multiple files at once). | Reserved for future directory-level AI commands (`engine.ai.require_directory_ai_opt_in`); no shipped command uses it yet. |
| `--full-target-document-ai` | Explicit additional opt-in to send the *whole* target document's text (not an excerpt) to an AI provider. | `ledgerly cite ai-plan` (citation insertion review needs full sentence-level context of the target document). |
| `--full-source-document-ai` | Explicit additional opt-in that changes a response's `full_text_mode` field; the underlying context sent is candidate metadata/abstracts either way today. | `search ai-candidate-review` / `POST /api/v1/search/ai-candidate-review`. |
| `--external-search` / `"external_search": true` | Required **in addition to** `--ai` for any AI feature that also touches external search (Scopus). Two separate opt-ins because "use AI" and "call an external API" are two separate privacy/cost boundaries. | `search ai-query-plan`, `search ai-candidate-review`, and their API equivalents. |
| `--ai` on `ledgerly transcribe start` | Opts a single transcription job into SourceScribe's OpenAI speech-to-text backend instead of the default local-Whisper backend. Never a silent fallback — local Whisper is always the default. | `ledgerly transcribe start --ai`, `POST /api/v1/transcription/jobs/{id}/start` (`"ai": true`). |

## Per-request non-AI opt-ins

| Flag | Meaning | Where it applies |
| --- | --- | --- |
| `--allow-candidate-citations` | Allows a citation plan to suggest citations from explicit-but-not-yet-accepted sources, not just `accepted` ones. | `ledgerly cite plan` / `cite ai-plan`. |

## Environment variables / config-level flags

These are set once (`.env` or the process environment), not per request — but every one of them only ever *offers* a capability; none activates itself automatically.

| Variable | Meaning | Notes |
| --- | --- | --- |
| `OPENAI_API_KEY` | Enables AI features to be available at all (resolved server-side only, never accepted from a request body). Absent = every `--ai`/`"ai": true` command returns `openai_not_configured`/`insufficient_evidence`, never a crash. | See AGENTS.md Core Rule 1: the deterministic core works with zero AI configured. |
| `SCOPUS_API_KEY` | Enables external academic search (Phase 23). Absent = external-search commands/routes are unavailable, not silently skipped. | |
| `LEDGERLY_DB_BACKEND` (+ `LEDGERLY_POSTGRES_*` / `LEDGERLY_MARIADB_*`) | Names an optional secondary database backend to mirror the always-on SQLite cache into. Setting the var does **not** activate anything — `db init`/`db sync`/`db status` (CLI) or the web Data & Admin panel only ever *offer* to activate it. | Phase 24. SQLite itself is never optional and is not affected by this. |
| `LEDGERLY_SOURCESCRIBE_PATH` | Points at a local sibling SourceScribe checkout for audio/video transcription. Absent = `ledgerly transcribe *` reports "not available" rather than failing unexpectedly. Invoked as a subprocess, never imported. | Phase 30. |
| `LEDGERLY_TRANSCRIBE_MAX_FILE_SIZE_MB` | Caps a single transcription upload's size. | Phase 30, default 500MB. |
| `LEDGERLY_UPLOAD_MAX_FILES` / `LEDGERLY_UPLOAD_MAX_FILE_SIZE_MB` | Caps batch artefact upload count/size (Phase 10). | Unrelated to AI/privacy — a resource-limit control. |
| `LEDGERLY_API_USERNAME` / `LEDGERLY_API_PASSWORD` / `LEDGERLY_API_SESSION_HOURS` | The API/web server's single shared-credential login (Phase 9) — not a multi-account system (see TODO.md Phase 29 for that still-unbuilt idea). | |
| `LEDGERLY_WORKSPACE_ROOT` | Confines which directories the API/web server may treat as a workspace. | Containment boundary, not an opt-in per se. |
| `LEDGERLY_TEMPLATES_ROOT` | Where `ledgerly templates save/list` and `init --template` store/read saved workspace templates (project setup + guidelines). Default `~/.ledgerly/templates`. | Phase 32. Deliberately outside any single workspace, since a template seeds *future* workspaces. |

## What is never a flag

Some things are architectural guarantees, not settings, and deliberately have
no override:

- No flag sends an original source file, whole PDF/CSV/SQLite database, or a
  full document to an AI provider by default — only `build_safe_context`
  excerpts, always capped, always logged in the response's `limits` field.
- No flag ever writes into a linked Zotero directory (read-only, always).
- No flag makes an AI feature skip the `insufficient_evidence` guard or the
  `grounding` check (`ledgerly.engine.grounding`, Phase 27) — these run
  unconditionally whenever AI is used, not opt-in behavior themselves.

## See also

- AGENTS.md's "Core Rule: No Hallucinations" and "Privacy Rules" sections —
  the policy these flags implement.
- `docs/api/CONTRACT.md`'s "AI Routes" section — the concrete request/response
  shape for every AI route's opt-in fields.
- `.env.example` — every environment variable with its default/placeholder.
