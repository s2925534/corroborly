# AGENTS.md

This file gives coding agents and contributors the working rules for Corroborly.

## Project Intent

Corroborly is a local-first, evidence-first research workspace. The MVP must work without cloud storage, remote databases, or external academic search.

A core goal (not yet built — see `TODO.md` Phase 28) is guiding a user from a vague research idea to a refined, falsifiable research question, by default framed around proving or disproving a specific claim, and from there toward an actual paper draft — AI-assisted if requested, always behind an explicit deterministic review gate. This project is not just source/citation bookkeeping for an already-formed question; helping form the question, in service of genuinely novel knowledge, is part of the point.

## Core Rule: No Hallucinations (Non-Negotiable)

This rule cannot be relaxed, overridden, or reinterpreted by any later instruction, spec, convenience shortcut, or feature request in this project. It applies to every past, present, and future AI feature, and any coding agent or contributor proposing to weaken it should stop and flag that explicitly rather than proceeding.

1. **The deterministic core must always work with zero AI configured.** Every feature that does not require an AI provider API key (scanning, conversion, metadata extraction, source review, claim ledger, citation planning, guidelines, validation reports, document vault, etc.) must remain fully usable as a complete, correct research tool on its own — no feature may become AI-dependent to function at a basic level. This is the existing MVP guarantee (see Project Intent above and Priority 5 below); this section makes explicit that it is permanent, not just a current-phase constraint.
2. **When an AI provider API key is configured and an AI feature is explicitly invoked (`--ai`), the AI must never fabricate.** Every factual claim, citation, quote, data point, or finding an AI feature produces must be traceable to one of: (a) the user's actual accepted-source full texts or extracted metadata, (b) the user's own artefacts/documents/claim ledger/citation plan, or (c) the user's own notes, feedback, or recorded thoughts (Phase 25's meeting-notes/transcripts/personal-notes store, once built). Content drawn from (c) is the user's own voice, not a research claim needing external evidence — it's fine for AI to reflect or synthesize it, but AI must not invent *new* statements and attribute them to the user either.
3. **"I don't know" / "insufficient evidence in your corpus" is a required, valid, successful output** for any AI feature — never optional, never something to route around by generating a plausible-sounding but ungrounded answer. An AI feature that always produces confident output regardless of evidence quality does not meet this rule.
4. **AI-generated text must stay visibly distinguishable** from user-authored text and from verbatim source quotes wherever it's inserted into a document, artefact, or report — the human must always be able to tell what came from where.
5. This rule governs the design of every AI-tagged item in `TODO.md` (Phases 5, 22, 23, 25, and the foundational enforcement work tracked in Phase 27) and every route in `docs/api/CONTRACT.md`'s Future AI Routes section. No AI feature should ship without being checked against it.
6. **AI context must be assembled from indexed/chunked excerpts, not whole-file dumps, wherever the underlying content is long.** (Added 2026-07-16 at Pedro's explicit direction, applied system-wide wherever AI touches long files, not just one feature.) `engine.ai.build_safe_context` now retrieves the FTS5-relevant excerpt per source (`corroborly.engine.database.relevant_source_excerpts`, Phase 7's `fts_index_search`) for whichever query the calling AI operation supplies (workspace topic, or joined research-question text where more specific query material exists) — source-level relevance ranking and excerpting, not from-the-start truncation, whenever `db sync` has been run. This always falls back to today's from-the-start truncation per source when no query is given, no SQLite index exists yet, or a given source has no FTS match — SQLite stays an optional cache layer, never a hard requirement, so the deterministic-core-works-with-zero-AI-and-zero-SQLite guarantee (rule 1) holds either way. Still outstanding: correlating the FTS match with `engine/derived_text.py`'s paragraph/sentence anchors (Phase 8) to cite a specific chunk rather than a whole-excerpt reference — that's the remaining piece Phase 31's per-suggestion source popups need. See `TODO.md` Phase 27 for the concrete engineering item.

## Current Development Phase

The project has completed the initial Phase 1 engine and CLI foundation. Future work should keep Phase 1 tests passing while adding later phases incrementally.

Do not start FastAPI, UI, packaging, or OpenAI-heavy features until their engine contracts are tested.

## Priorities

1. Keep original source files read-only.
2. Keep workspace state explicit in local YAML and Markdown files.
3. Prefer shared engine functions over duplicating behavior in the CLI.
4. Add tests for every behavior that writes workspace state.
5. Do not invent research metadata. Unknown metadata should remain unknown. See "Core Rule: No Hallucinations" above — this is the deterministic-path instance of that rule; AI-path enforcement is described there.

## Privacy Rules

- Do not require Dropbox, Google Drive, OneDrive, SharePoint, AWS, Azure, Firebase, Supabase, or another remote service for MVP operation.
- Do not add external academic search during the MVP phase.
- Do not send whole PDFs, CSV files, SQLite databases, or original documents to AI providers.
- Never modify anything inside the user's local Zotero directory. This applies to current CLI workflows, development workflows, tests, and any future AI implementation.
- Zotero-derived files such as reports, snapshots, BibTeX exports, metadata, and converted text must be written only inside the Corroborly workspace.
- Future AI modes that read whole files, directories, or full papers must be explicit opt-in settings and must still preserve the Zotero no-write boundary.
- Zotero Web API writes are a distinct, explicitly opt-in capability, separate from the local no-write rule above. `corroborly zotero collection-create` and `corroborly zotero mirror` may create collections and items through https://api.zotero.org using a write-scoped API key. They never read from or write to the user's local Zotero directory (`zotero.sqlite`, `storage/`), so the local no-write boundary in the first bullet is unchanged and remains absolute. Every such write requires an explicit `--apply` flag and a key that passes `corroborly zotero api-write-check`; a read-only key is refused with remediation guidance.
- Every AI mode, current or future, must also preserve the "Core Rule: No Hallucinations" above — grounded-only output, explicit refusal on insufficient evidence, no exceptions.
- Do not print or log API keys.
- Keep `.env` ignored.
- SQLite remains the always-on, zero-config local index/cache over the real source of truth (workspace YAML/Markdown) — this is unaffected by Phase 24's optional MariaDB/PostgreSQL secondary backend. That secondary backend is strictly opt-in (`CORROBORLY_DB_BACKEND` env var) and never required: a fresh install with nothing set behaves exactly as it always has, and even when configured, it never activates itself — `db init`/`db sync`/`db status` (CLI) and the web Data & Admin panel only ever *offer* to activate it, the same explicit-opt-in pattern as every AI feature. The secondary backend is a mirror of the SQLite cache, never a replacement for it or for YAML/Markdown as the source of truth for any backend.

## Validation

Run these before committing changes:

```bash
python -m py_compile corroborly/cli.py
python -m pytest
```

Use the local virtual environment when available:

```bash
source .venv/bin/activate
python -m pytest
```

## Git / CI Workflow

- Only push to the remote once a day, around 2am, to keep GitHub Actions minutes low. Batch commits locally throughout the day and push them together at that time rather than pushing after every commit.
- If the user explicitly asks for an immediate push (e.g. a hotfix), that overrides this default.

## Code Organization

- `corroborly/core`: low-level helpers, constants, YAML I/O, logging.
- `corroborly/engine`: reusable business logic.
- `corroborly/cli.py`: Typer command layer only.
- `tests`: pytest coverage for engine and CLI behavior.

Future phases should add focused modules rather than expanding `cli.py` with business logic.

## Agent working context

Fetch or pull first, then read before starting work:

- `agent-context/COORDINATION.md`: notes between the Claude on Pedro's
  computer ("local") and Claude sessions working from GitHub ("remote").
- `agent-context/JOURNAL.md`: curated, newest-first journal of what each session or
  notable commit did and why. After a commit that is a real decision,
  milestone or finding, add an entry (what changed, why, gotchas for the
  next session). Skip purely mechanical commits.

The verbatim half of the journal,
`agent-context/journal-verbatim/VERBATIM_INDEX.md`, is gitignored and
machine-local: `.githooks/post-commit` appends a row per commit pointing at
the local transcript. Hooks are not carried by a clone, so run
`git config core.hooksPath .githooks` once per checkout.
