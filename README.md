# ResearchBoss

Current version: 0.9.3

ResearchBoss is a local-first, evidence-first research workspace for managing research context, source files, review state, and project memory without requiring cloud services for the MVP.

Phase 1 engine and CLI foundation are complete. The core engine and CLI are importable, tested, and usable for local workspace setup, local source scanning, and source review.

## Author

Pedro Veloso

Email: pedro@veloso.dev

## Project Goals

- Create reproducible local research workspaces.
- Keep source registers, review decisions, context, memory, logs, and generated artefact metadata in project files.
- Support local folder and Zotero storage scanning without modifying original source files.
- Track accepted, ignored, maybe, and pending sources per project.
- Build toward conversion, metadata extraction, data profiling, research question workflows, optional OpenAI assistance, a local FastAPI backend, and future cross-platform UI.

## Current Status

Phase 1 complete:

- Python package structure under `researchboss/`
- Typer CLI command definitions
- Runtime preflight checks through `researchboss doctor` and before `researchboss init`
- Version output through `researchboss version`
- Workspace creation engine
- Default YAML and Markdown workspace files
- Source folder constants
- Source scanning engine for selected file extensions
- Read-only Zotero storage scanning with Zotero storage-key metadata
- Deterministic Zotero storage keyword search over filenames and `.zotero-ft-cache` text
- Read-only local Zotero SQLite metadata lookup without Zotero API use
- Offline Zotero collection listing, selected-collection mode, notes/tags/relations metadata, metadata reports, health reports, snapshots, duplicate checks, and BibTeX export
- Optional read-only Zotero Web API credential test, collection listing, and collection selection
- Local FastAPI boundary documented in `docs/api/CONTRACT.md`, with every documented route implemented through `researchboss serve` except the disabled Future AI Routes section
- TXT, MD, DOCX, and page-marked PDF conversion into `sources_text/`
- Conversion cache keyed by source hash and failed conversion records under `sources_failed/`
- Deterministic citation metadata extraction without inventing missing fields
- DOI syntax and resolver-link validation, citation consistency reports, metadata duplicate reports, and local keyword indexing
- CSV, SQLite, and JSON data profiling under `outputs/data-profiles/`
- M.Phil and PhD research stage templates
- Research question approve, reject, archive, list, and deterministic readiness-check workflows
- Research question templates for all project types and local warning thresholds
- Manual claim ledger, claim status workflow, claim-source validation, and citation gap reports
- Source notes, manual tags, and source review reports
- Structured decisions, terminology, supervisor/stakeholder feedback, context changelog, and local timeline reports
- Artefact registry records with linked sources, linked research questions, and review flags
- Deterministic artefact creation for source summaries, literature review matrices, claim-evidence tables, research question briefs, and data profile summaries
- Artefact review statuses, artefact dependency validation, and offline evidence bundle export
- Local Markdown report generation, one-shot source watch reports, workspace backups, and config migration
- Workspace health reports and backup restore dry-run inspection
- OpenAI readiness checks through `researchboss ai test`, with live requests requiring explicit `--ai`
- Safe local AI context previews through `researchboss ai context-preview --ai`, excluding original files and whole documents or datasets by default
- AI-assisted review, novelty assessment, research-question assessment, corpus summary, claim-checking, citation-gap, artefact cross-reference, and source-relevance commands, all requiring explicit `--ai`
- Explicit Scopus external-search runs with structured query plans, legacy params-file import, query strategy modes, local snapshots, query validation, quality-scored candidate registers, threshold filters, no-result or low-result logs, saved refine plans, and local candidate reports
- Deterministic document target resolution and `researchboss validate <target>` reports with strengths, weaknesses, unsupported or weakly supported sentences, citation gaps, confidence factors, confidence scores, and APA7 references
- Guideline registration through `researchboss guidelines add`, with local or remote snapshots and extracted text stored inside the workspace, plus validated guideline scopes
- Optional workspace SQLite index and memory layer through `researchboss db init/sync/status/rebuild`, preserving YAML and Markdown as the source of truth
- Reviewed SQLite-to-YAML/Markdown pending-change flow through `researchboss db apply-pending --review` and `researchboss db apply-pending --apply`
- SQLite memory defaults, explicit research index tables, document aliases, bounded FTS indexes, repair checks, and database privacy checks through `researchboss db privacy`
- Zotero-style citation wording during init, including explicit `American Psychological Association 7th edition`
- Strict one-way Zotero-to-ResearchBoss blocker config that prevents writes inside the local Zotero directory
- SHA-256 file hashing
- Duplicate detection by content hash
- Source register records with `pending_review`
- Accept, ignore, and maybe source status helpers
- JSONL logs and YAML run summary helpers
- Local-first and no external search flags in generated config
- Numbered init prompts for research level, citation style, output type, data expectations, source review defaults, and AI preference metadata
- Optional research questions and subquestions captured during init
- Draft research questions stored separately from approved research questions
- Optional supervisor or stakeholder context captured during init
- Workspace discovery and selection when `--workspace` is omitted
- Local default workspace selection stored in ignored local YAML under `workspaces/`
- Concrete next-step command examples after successful init
- Detailed implementation roadmap in `DETAILED_ROADMAP.md`

Known gaps:

- OpenAI readiness, safe context preview, AI-assisted review, novelty assessment, and research-question assessment are implemented with explicit `--ai` opt-in and local report outputs.
- FastAPI requires `RESEARCHBOSS_API_PASSWORD` to be set; every `/api/v1` route fails closed (`503`) until it is configured, and login sessions are in-memory only. UI is not implemented yet; packaging has a written plan (`docs/PACKAGING.md`) but no built/tested package yet.
- Zotero support defaults to local filesystem and read-only SQLite. Optional read-only Zotero Web API collection listing and selection are implemented.
- The source review workflow is implemented for local workspace state. Deterministic artefact creation can consume accepted sources, and AI-assisted review/novelty/RQ assessment can use safe accepted-source context when explicitly enabled with `--ai`.
- Init stores AI preference metadata and keeps AI disabled by default.

## Intended MVP Scope

ResearchBoss should not require Dropbox, Google Drive, OneDrive, SharePoint, AWS, Azure, Firebase, Supabase, or any remote database for the MVP.

The MVP should also avoid external academic search. Source discovery should begin with local folders and Zotero storage folders. Optional Zotero Web API support is limited to read-only collection listing and selection.

## Repository Layout

```text
researchboss/
  core/
    constants.py      # workspace file and folder names
    runlog.py         # JSONL logging and run summary helpers
    yamlio.py         # YAML read/write helpers
  engine/
    artefact_creation.py # deterministic artefact creation helpers
    artefacts.py      # artefact registry helpers
    backup.py         # local workspace backup helpers
    claims.py         # manual claim ledger and citation gap helpers
    conversion.py     # TXT, MD, DOCX, and PDF-to-text conversion
    data.py           # CSV, SQLite, and JSON profiling
    database.py       # optional workspace SQLite index, memory, sync, and privacy checks
    metadata.py       # deterministic citation metadata extraction
    migrations.py     # workspace config migrations
    reports.py        # local Markdown report generation
    research_questions.py # research question workflows
    sources.py        # source scanning, hashing, status updates
    watch.py          # one-shot unregistered source detection
    zotero.py         # read-only Zotero storage, SQLite metadata, reports, and keyword search
    workspace.py      # workspace initialization
  cli.py              # Typer CLI command layer
  __main__.py         # python -m researchboss entry point

README.md
CHANGELOG.md
TODO.md
AGENTS.md
docs/ARCHITECTURE.md
docs/api/CONTRACT.md
pyproject.toml
```

## Planned Workspace Files

`researchboss init` is intended to create files such as:

- `research-context.yaml`
- `research-state.yaml`
- `research-stages.yaml`
- `research-questions.yaml`
- `research-question-candidates.yaml`
- `rejected-research-questions.yaml`
- `source-register.yaml`
- `accepted-sources.yaml`
- `ignored-sources.yaml`
- `maybe-sources.yaml`
- `claims-ledger.yaml`
- `novelty-ledger.yaml`
- `terminology.yaml`
- `supervisor-feedback.yaml`
- `decisions.md`
- `memory.md`
- `context-changelog.md`
- `artefact-registry.yaml`
- `app-settings.local.yaml`
- `.gitignore`

It is also intended to create source, artefact, output, log, and context version folders.

By default, new ResearchBoss project workspaces are created under:

```text
workspaces/<project-name>
```

The repository tracks only `workspaces/.keep`; generated workspace contents are ignored.

When commands need a workspace and `--workspace` is omitted, ResearchBoss discovers valid workspaces from the current folder and `./workspaces/*`. If one workspace is found, it is used automatically. If several are found, ResearchBoss shows a numbered list. The first selected workspace can be saved as the local default in:

```text
workspaces/.researchboss-cli.local.yaml
```

That file is ignored with generated workspace contents.

## Development Setup

Requires Python 3.11 or newer.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

## Quick Start

Install the project before running the first ResearchBoss command:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
researchboss doctor
researchboss init
```

After `researchboss init`, follow the concrete commands printed by the CLI. A typical first workflow is:

```bash
researchboss scan
researchboss sources review
researchboss sources status
```

`researchboss init` runs a runtime preflight before asking setup questions. If required runtime libraries are missing or the Python version is unsupported, it stops and prints the install command before proceeding.

## CLI Commands

Current CLI commands include:

```bash
researchboss version
researchboss doctor
researchboss init
researchboss status [--workspace <path>]
researchboss config validate [--workspace <path>]
researchboss config migrate [--workspace <path>]
researchboss scan [--workspace <path>] [--source <source-folder>] [--kind local_folder|zotero_storage]
researchboss convert [--workspace <path>] [--status accepted] [--ocr]
researchboss validate <target> [--workspace <path>] [--source-path <path>] [--guidelines <guideline-id>] [--no-default-guidelines]
researchboss metadata extract [--workspace <path>]
researchboss metadata sidecars [--workspace <path>]
researchboss metadata filename-suggestions [--workspace <path>]
researchboss data profile [--workspace <path>]
researchboss data list [--workspace <path>]
researchboss data status [--workspace <path>]
researchboss report [--workspace <path>]
researchboss report-schemas [--workspace <path>]
researchboss watch [--workspace <path>]
researchboss health [--workspace <path>]
researchboss timeline [--workspace <path>]
researchboss backup [--workspace <path>] [--include-originals]
researchboss backup-inspect <backup.zip> [--workspace <path>]
researchboss export-evidence [--workspace <path>]
researchboss export-corpus [--workspace <path>]
researchboss merge-pdfs [--workspace <path>] [--write] [--output <path>]
researchboss ocr-readiness [--workspace <path>]
researchboss processing-issues [--workspace <path>]
researchboss guidelines add <path-or-url> [--workspace <path>]
researchboss guidelines list [--workspace <path>]
researchboss guidelines defaults <guideline-id>... [--workspace <path>]
researchboss guidelines conflicts [--workspace <path>]
researchboss guidelines ai-context --ai [--workspace <path>] [--full-guidelines-ai] [--max-excerpt-chars <n>]
researchboss cite plan <target> [--workspace <path>] [--source-path <path>] [--guidelines <guideline-id>] [--no-default-guidelines] [--allow-candidate-citations]
researchboss cite ai-plan <target> --ai [--workspace <path>] [--full-target-document-ai] [--source-path <path>] [--allow-candidate-citations]
researchboss cite apply <target> [--plan <plan.yaml>] [--workspace <path>]
researchboss ai test [--workspace <path>] [--ai]
researchboss ai context-preview --ai [--workspace <path>]
researchboss ai review --ai [--workspace <path>]
researchboss assess-novelty --ai [--workspace <path>]
researchboss rqs assess --ai [--workspace <path>] [--rq <rq-id>]
researchboss ai corpus-summary --ai [--workspace <path>]
researchboss ai claim-check --ai [--workspace <path>]
researchboss ai citation-gaps --ai [--workspace <path>]
researchboss ai artefact-cross-reference --ai [--workspace <path>]
researchboss ai source-relevance --ai [--workspace <path>]
researchboss ai abstract-screening --ai [--workspace <path>] [--max-sources <n>] [--max-excerpt-chars <n>]
researchboss abstracts import <folder> [--workspace <path>]
researchboss search plan [--workspace <path>] [--strategy broad|balanced|strict] [--params-file <path>]
researchboss search ai-query-plan --ai --external-search [--workspace <path>] [--max-sources <n>] [--max-excerpt-chars <n>]
researchboss search ai-candidate-review --ai --external-search [--workspace <path>] [--full-source-document-ai] [--max-sources <n>] [--max-excerpt-chars <n>]
researchboss search import-candidates --candidate-id <id> [--workspace <path>]
researchboss search refine-plan [--workspace <path>]
researchboss search reports [--workspace <path>]
researchboss search scopus-test --external-search [--workspace <path>]
researchboss search scopus --external-search "query" [--workspace <path>]
researchboss zotero search "keyword terms" [--workspace <path>] [--storage <zotero-storage-folder>]
researchboss zotero collections [--workspace <path>]
researchboss zotero test [--workspace <path>]
researchboss zotero api-test [--workspace <path>]
researchboss zotero api-collections [--workspace <path>]
researchboss zotero api-select-collections <collection-key>... [--workspace <path>]
researchboss zotero select-collections <collection-key>... [--workspace <path>]
researchboss zotero use-entire-library [--workspace <path>]
researchboss zotero scan-collection <collection-key> [--workspace <path>]
researchboss zotero metadata-report [--workspace <path>]
researchboss zotero attachment-health [--workspace <path>]
researchboss zotero fulltext-report [--workspace <path>]
researchboss zotero duplicates [--workspace <path>]
researchboss zotero snapshot [--workspace <path>]
researchboss zotero export-bibtex [--workspace <path>]
researchboss metadata validate [--workspace <path>]
researchboss metadata duplicates [--workspace <path>]
researchboss metadata index [--workspace <path>]
researchboss sources list [--workspace <path>]
researchboss sources status [--workspace <path>]
researchboss sources review [--workspace <path>]
researchboss sources accept <source-id> --workspace <path>
researchboss sources maybe <source-id> --workspace <path>
researchboss sources ignore <source-id> --reason "Reason" --workspace <path>
researchboss sources note <source-id> "Note" [--workspace <path>]
researchboss sources tag <source-id> <tag> [--workspace <path>]
researchboss sources report [--workspace <path>]
researchboss rqs list [--workspace <path>]
researchboss rqs check [<rq-id>] [--workspace <path>]
researchboss rqs approve <rq-id> [--workspace <path>]
researchboss rqs reject <rq-id> --reason "Reason" [--workspace <path>]
researchboss rqs archive <rq-id> --reason "Reason" [--workspace <path>]
researchboss claims add "Claim text" [--source <source-id>] [--workspace <path>]
researchboss claims list [--workspace <path>]
researchboss claims gaps [--workspace <path>]
researchboss claims status <claim-id> <status> [--workspace <path>]
researchboss claims validate [--workspace <path>]
researchboss decisions add "Decision" [--reason "Reason"] [--workspace <path>]
researchboss terminology add <term> "Definition" [--workspace <path>]
researchboss feedback add "Feedback" [--source "Name"] [--workspace <path>]
researchboss context add "Change note" [--workspace <path>]
researchboss artefacts register "Title" --path <path> [--type report] [--workspace <path>]
researchboss artefacts create source-summary-report [--workspace <path>]
researchboss artefacts create literature-review-matrix [--workspace <path>] [--rq <rq-id>]
researchboss artefacts create claim-evidence-table [--workspace <path>]
researchboss artefacts create research-question-brief [--workspace <path>] [--rq <rq-id>]
researchboss artefacts create data-profile-summary [--workspace <path>]
researchboss artefacts list [--workspace <path>]
researchboss artefacts review <artefact-id> <status> [--workspace <path>]
researchboss artefacts dependencies [--workspace <path>]
```

`researchboss artefacts create` is deterministic and non-AI. It only extracts and arranges existing workspace state, excludes ignored sources, writes generated artefacts inside the workspace, marks them as requiring user review, and records `ai_generated: false`.

`researchboss rqs check` is also deterministic and non-AI. It checks question form, scope signals, vague terms, possible multiple-question wording, basic context markers, subquestion alignment, and level-specific readiness hints. It does not validate novelty, contribution strength, field usefulness, or evidence quality; those require human review or later AI-assisted workflows.

For commands that mutate a specific source by ID, passing `--workspace` is still recommended in scripts. In interactive use, omitting `--workspace` triggers the same workspace discovery and default-selection flow.

During `researchboss init`, ResearchBoss looks for a default Zotero storage directory on macOS, Windows, and Linux (native and Flatpak installs). If found, the source prompt defaults to that storage path, for example:

```text
Where are your source files? [/Users/<user>/Zotero/storage]:
```

If Zotero storage is not found, the prompt falls back to:

```text
Where are your source files? [configure_later]:
```

The destination artefact root defaults to the current user's `Documents` directory.

For Zotero storage projects, `researchboss init` stores both the selected `storage/` folder and the parent Zotero directory. `researchboss scan` records the provider as `zotero_storage` from workspace config when `--kind` is omitted. Registered Zotero sources include the storage item key, relative path inside `storage/`, whether Zotero's `.zotero-ft-cache` full-text cache exists, and read-only SQLite metadata when available.

You can search local Zotero storage without AI or the Zotero API:

```bash
researchboss zotero search "evidence synthesis" --workspace <workspace>
researchboss zotero search "local first" --workspace <workspace> --storage /Users/<user>/Zotero/storage
```

These Zotero commands only read supported source files, Zotero `.zotero-ft-cache` text, and `zotero.sqlite` through a read-only immutable SQLite connection. They do not modify Zotero files, write into Zotero storage, call the Zotero local API, or send content to AI services.

ResearchBoss has a hard Zotero safety rule: no development workflow, CLI command, or future AI feature may modify anything inside the local Zotero directory. Derived reports, snapshots, BibTeX files, metadata, and converted text must be written only inside the ResearchBoss workspace.

Optional Zotero Web API support uses `ZOTERO_API_KEY` and `ZOTERO_USER_ID` from `.env` or the process environment. Use a Zotero key with library/notes read access only; do not enable Zotero write access for ResearchBoss.

When Zotero storage is configured, the workspace config includes:

```yaml
zotero:
  strict_one_way_from_zotero_to_researchboss: true
  block_writes_to_zotero_directory: true
```

The init wizard also prompts for optional local context:

- research level / project type using numbered options
- research questions, draft/approved status, and optional subquestions
- supervisor or stakeholder names
- citation style
- primary output type
- whether CSV or SQLite data files are expected
- default status for newly scanned sources, `pending_review` or `maybe`
- AI preference metadata, while keeping AI disabled
- strict evidence mode
- whether to prevent workflows that upload full documents or datasets
- workspace path confirmation when the path is inferred

After init, ResearchBoss prints concrete next-step commands using the actual workspace path and configured source folder when available.

Environment variables are read from the repository root `.env` file during local development. Workspaces do not create their own `.env` files.

## OpenAI Foundation

OpenAI support is optional and disabled by default. `researchboss ai test` checks whether `OPENAI_API_KEY` is available from the process environment, repository `.env`, or workspace `.env` without printing or logging the key. It does not make a live OpenAI request unless `--ai` is passed.

`researchboss ai context-preview --ai` writes a local preview file at `outputs/validation/openai-safe-context.yaml`. It uses accepted source metadata and bounded converted-text excerpts only. It excludes original files, whole PDFs, whole CSV files, whole SQLite databases, and Zotero directory writes by default. It does not call OpenAI.

`researchboss ai review --ai`, `researchboss assess-novelty --ai`, `researchboss rqs assess --ai`, `researchboss ai corpus-summary --ai`, `researchboss ai claim-check --ai`, `researchboss ai citation-gaps --ai`, `researchboss ai artefact-cross-reference --ai`, and `researchboss ai source-relevance --ai` use the same safe context boundary and write local reports. They are AI-assisted outputs, not proof. Human review is required before using their conclusions. External search commands use `--external-search` and write local snapshots/history only inside the workspace.

Source statuses are currently limited to:

- `pending_review`
- `accepted`
- `maybe`
- `ignored`

The source review commands update local workspace YAML files. Conversion, metadata extraction, data profiling, claim checks, and reports are local deterministic workflows and can be filtered by source status where supported.

## Workspace SQLite

`researchboss.sqlite` is optional and local to each workspace. YAML and Markdown files remain the human-readable source of truth. The database is a rebuildable index, cache, memory layer, and controlled sync layer.

Useful commands:

```bash
researchboss db init --workspace workspaces/<workspace-name>
researchboss db sync --workspace workspaces/<workspace-name>
researchboss db status --workspace workspaces/<workspace-name>
researchboss db privacy --workspace workspaces/<workspace-name>
researchboss db apply-pending --review --workspace workspaces/<workspace-name>
researchboss db rebuild --workspace workspaces/<workspace-name>
```

SQLite-to-file write-back is never silent. Proposed database-originated changes must be in the pending-change table and reviewed before `researchboss db apply-pending --apply` writes to YAML or Markdown.

## Document Validation, Guidelines, and Citation Planning

`researchboss validate <target>` deterministically checks a document (by path, artefact ID/title, alias, or artefact type) against accepted sources and any `--source-path` values you pass explicitly. It writes a local report with strengths, weaknesses, unsupported or weakly supported sentences, citation gaps, confidence scores, and APA7 references. Nothing is sent to AI and the original document is never modified.

Guidelines (style guides, supervisor requirements, formatting rules) are registered locally and applied during validation and citation planning:

```bash
researchboss guidelines add <path-or-url> --workspace <workspace>
researchboss guidelines list --workspace <workspace>
researchboss guidelines defaults <guideline-id>... --workspace <workspace>
researchboss guidelines conflicts --workspace <workspace>
```

`guidelines defaults` sets the workspace default guideline IDs and their precedence order, applied automatically by `validate` and `cite plan` unless `--no-default-guidelines` or explicit `--guidelines <id>` overrides are passed. `guidelines conflicts` writes a deterministic report of contradictory guideline requirements to `outputs/validation/guideline-conflicts.yaml` for human review. `guidelines ai-context --ai` is the explicit AI opt-in for guideline reasoning; it sends bounded excerpts by default and only includes full guideline text with `--full-guidelines-ai`.

Citation planning turns a validation report's missing-citation findings into a reviewable, non-destructive plan:

```bash
researchboss cite plan <target> --workspace <workspace>
researchboss cite ai-plan <target> --ai --workspace <workspace>
researchboss cite apply <target> --workspace <workspace>
```

`cite plan` is deterministic and writes `outputs/citation-plans/citation-plan-<target>.yaml` and `.md`. `cite ai-plan` is the AI-assisted equivalent behind explicit `--ai`, and only sends the full target document text with an additional `--full-target-document-ai` opt-in. Both plan commands only suggest citations from `accepted` sources unless `--allow-candidate-citations` is passed. `cite apply` reads a reviewed plan (from `--plan` or the default plan path) and writes the accepted insertions to a revised output copy — it never edits the original document in place.

## Document Vault

`document-vault.yaml` tracks version history for generated artefacts and user-selected target documents inside a local `document_vault/` folder (`originals/`, `versions/`, `diffs/`, `manifests/`, `uploads/originals/`, `uploads/renamed/`). Original files are never modified in place; every command that creates a modified document copy — including `cite apply` — automatically snapshots the document before and after the change.

```bash
researchboss doc version <target> --workspace <workspace>
researchboss doc versions <target> --workspace <workspace>
researchboss doc diff <version-id-a> <version-id-b> --workspace <workspace>
researchboss doc compare <version-id-a> <version-id-b> --workspace <workspace>
researchboss doc restore <version-id> --workspace <workspace>
researchboss doc upload <path> [--title <title>] [--author <author>] [--year <year>] --workspace <workspace>
researchboss doc uploads --workspace <workspace>
```

`doc version` snapshots a target (path, artefact ID/title, alias, or artefact type) into the vault, recording its content hash, parent version, creation reason, source command, and — when applicable — the linked validation report and citation plan IDs. `doc diff` shows a unified text diff between two versions (Markdown/TXT only; other formats report `diff_supported: false` rather than guessing). `doc compare` shows how a target's validation strengths, weaknesses, unsupported claims, and references changed between two versions, when both carry a linked validation report. `doc restore` always writes a new, separate copy rather than overwriting the current document or deleting newer versions.

`doc upload` copies an externally created artefact into the vault: an untouched copy under its original filename (collision-safe suffixed if that name was already used) plus a renamed working copy following the same author/year/title filename-suggestion pattern as source filename suggestions, with the upload ID embedded to keep the renamed copy collision-free. The uploaded file itself is never modified or moved. `doc uploads` lists everything brought in this way.

## Local API

`researchboss serve` runs a local FastAPI app (`researchboss.api`) that is a thin transport layer over the same `researchboss.engine` functions the CLI uses — no route duplicates business logic. It binds to `127.0.0.1` by default; use `0.0.0.0` only behind a reverse proxy and auth layer.

```bash
researchboss serve --host 127.0.0.1 --port 8000
```

Every route documented in `docs/api/CONTRACT.md` is implemented except the disabled Future AI Routes section: `GET /health` (no workspace or auth dependency, for deploy/update health checks), `POST /api/v1/auth/login` and `/logout`, plus projects, sources, conversion, metadata, data, research questions, claims, artefacts (including deterministic creation and batch upload), Zotero (read-only local and Web API, with collection selection written only to the workspace, never to Zotero), document vault, validation, citation plans, guidelines, SQLite sync status, reports, evidence export, backup, and project log (decisions, terminology, feedback, context changelog) routes. Every response uses the envelope `{"ok", "data", "warnings", "errors"}`. Novelty assessment has no deterministic engine path (it's AI-only) and stays out of the contract until it can be added under explicit AI opt-in and privacy-boundary rules, not just a contract addition.

`POST /api/v1/artefacts/upload` accepts multipart form data (field name `files`) for batch artefact uploads. It rejects the whole batch with `400 upload_batch_too_large` if it exceeds `RESEARCHBOSS_UPLOAD_MAX_FILES` (default 25) before writing anything, caps each file at `RESEARCHBOSS_UPLOAD_MAX_FILE_SIZE_MB` (default 50), and only accepts extensions from the same allow-list source scanning uses. Uploaded bytes are streamed to a bounded-size temporary file rather than buffered in memory, and the temp directory is always cleaned up. The response is a per-batch report (accepted/duplicate/rejected/failed counts and per-file rows, duplicates detected by content hash), also persisted to `outputs/validation/upload-batch-report.yaml`.

`GET /api/v1/artefacts/cross-reference?upload_id=<id>` proposes deterministic links between an uploaded artefact and existing artefacts, sources, and claims, based on shared keyword tokens in titles and filenames. It only ever writes a candidate report (`outputs/recommendations/cross-reference-<upload_id>.yaml`) — never an artefact, source, or claim record. There is no `apply` route yet: whether "write the link" means artefact-registry metadata or literal document-content insertion is a real design decision, documented as open in `docs/api/CONTRACT.md`.

Set `RESEARCHBOSS_API_PASSWORD` (env var or `.env` in the server's working directory) before starting the server. Every `/api/v1` route except `/api/v1/auth/login` requires a valid session and fails closed with `503 auth_not_configured` if no password is set — it never falls back to open access. Log in with `POST /api/v1/auth/login {"password": "..."}` to receive a session (an httponly cookie, and the same token usable as `Authorization: Bearer <token>`); sessions live in server memory only (default 12-hour expiry, `RESEARCHBOSS_API_SESSION_HOURS` to override) and are cleared on server restart. `POST /api/v1/auth/logout` invalidates the current session. There is no public self-registration route.

Set `RESEARCHBOSS_WORKSPACE_ROOT` when deploying against a mounted volume (e.g. a NAS bind-mount): every `workspace` query value must then resolve inside that root — relative paths are joined to it, absolute paths outside it are rejected with `400 workspace_outside_root` — rather than accepting any path reachable by the server process. Leave it unset for local-first single-user CLI-equivalent use, where any absolute path works exactly as it does today.

A `Dockerfile` and `docker-compose.yml` at the repo root package this API for deployment; see `docs/DEPLOY.md` for local testing, the deploy command, per-project workspace setup, and update/rollback steps.

## Abstract Screening and External Candidate Import

Legacy or externally sourced abstracts can be imported into a reviewable local candidate register before they become workspace sources:

```bash
researchboss abstracts import <folder> --workspace <workspace>
researchboss ai abstract-screening --ai --workspace <workspace>
researchboss search import-candidates --candidate-id <id> --workspace <workspace>
```

`abstracts import` reads local abstract text files from `<folder>` and writes a candidate register; it does not register sources by itself. `ai abstract-screening --ai` generates AI-assisted screening recommendations from accepted-source metadata and bounded excerpts without changing any abstract's status. `search import-candidates` promotes reviewed external search candidates (see below) into the source register as metadata-only `pending_review` sources.

External-search query and candidate assistance follow the same `--ai` plus `--external-search` double opt-in as other external-search commands:

```bash
researchboss search ai-query-plan --ai --external-search --workspace <workspace>
researchboss search ai-candidate-review --ai --external-search --workspace <workspace>
```

`ai-query-plan` suggests external-search queries without executing them. `ai-candidate-review` reviews external candidates for relevance and novelty from metadata and abstracts first; sending full source documents requires the additional `--full-source-document-ai` opt-in.

## Metadata and Document Processing Utilities

```bash
researchboss metadata sidecars --workspace <workspace>
researchboss metadata filename-suggestions --workspace <workspace>
researchboss export-corpus --workspace <workspace>
researchboss merge-pdfs --workspace <workspace> [--write] [--output <path>]
researchboss ocr-readiness --workspace <workspace>
researchboss processing-issues --workspace <workspace>
researchboss report-schemas --workspace <workspace>
```

`metadata sidecars` parses local CSL JSON, BibTeX, and RIS sidecar files to fill in registered source metadata without inventing fields. `metadata filename-suggestions` writes deterministic renaming suggestions under `outputs/recommendations/filename-suggestions.yaml` without renaming original files. `convert --ocr` explicitly allows a local OCR fallback for scanned PDFs; `ocr-readiness` reports whether local OCR tooling is available without processing any documents, and `processing-issues` reports skipped or failed conversions without modifying originals.

`export-corpus` writes accepted sources' converted text into a single local corpus file plus a manifest under `outputs/`. `merge-pdfs` writes a merge manifest by default (dry run); pass `--write` to also produce a merged PDF artefact, optionally at a custom `--output` path. `report-schemas` writes the documented schema contracts for validation, citation, confidence, guideline-conflict, and APA7-reference reports to `outputs/reports/report-schemas.yaml` and `.md`.

## Validation

Run these checks before committing:

```bash
python -m py_compile researchboss/cli.py researchboss/engine/*.py researchboss/core/*.py
python -m pytest
```

## Roadmap

The detailed living roadmap is maintained in `DETAILED_ROADMAP.md`. Update that file, this README version line, and the changelog whenever development changes project behavior.

1. Phase 1 engine and CLI foundation complete.
2. Conversion and citation metadata extraction complete for deterministic local MVP paths.
3. CSV, SQLite, JSON profiling plus artefact metadata complete for deterministic local MVP paths.
4. Research stages and research question approval workflows complete for deterministic local MVP paths.
5. Add optional OpenAI features with strict privacy boundaries.
6. Add deterministic document validation, guideline handling, citation assistance, and later explicit AI opt-ins for whole-document workflows.
7. Optional workspace SQLite memory, indexing, and sync complete for deterministic local MVP paths.
8. Document vault, versioning, restoration, and uploaded-artefact intake complete for deterministic local MVP paths (`researchboss doc version/versions/diff/restore/compare/upload/uploads`); derived-text anchoring and AI edit sessions remain future work.
9. Local FastAPI backend: every route in `docs/api/CONTRACT.md` implemented via `researchboss serve`, including single-user login protection, validation, citation plans, guidelines, SQLite sync status, `RESEARCHBOSS_WORKSPACE_ROOT` containment, batch artefact upload, and deterministic cross-reference candidates, except the disabled Future AI Routes section. Cross-reference apply (writing reviewed links) needs a design decision — registry metadata vs. document-content insertion — before it can be built. Novelty assessment and AI-assisted cross-reference stay out until they can be added under explicit AI opt-in and privacy-boundary rules.
10. Prepare a cross-platform UI.
11. Packaging plan complete (`docs/PACKAGING.md`): PyInstaller recipe with known uvicorn/`python-multipart` gotchas, conditional Flutter sidecar notes, and platform considerations. No packaged build produced or tested yet.
12. NAS deployment (`research.veloso.dev`): `Dockerfile`, `docker-compose.yml`, and `docs/DEPLOY.md` written, using `../synology-site-deployer` unmodified. Nothing has actually been deployed yet — that step needs real NAS/Cloudflare infrastructure access.

## Repository Hygiene

Editor settings and local environments are intentionally ignored. `.idea/`, `.venv/`, `.env`, Python caches, pytest caches, and build outputs should stay out of source control.

## License

ResearchBoss is released under the MIT License.

Copyright © 2026 Pedro Veloso

This software is provided free of charge and without warranty of any kind. See `LICENSE` for the full license text.
