# ResearchBoss

Current version: 0.3.9

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

- OpenAI behavior, FastAPI, UI, and packaging are planned but not implemented yet.
- Zotero support is local filesystem and read-only SQLite based only; Zotero API integration is not implemented yet.
- The source review workflow is implemented for local workspace state. Deterministic artefact creation can consume accepted sources, but AI-assisted research tasks are not implemented yet.
- AI is not implemented. Init stores AI preference metadata only and keeps AI disabled.

## Intended MVP Scope

ResearchBoss should not require Dropbox, Google Drive, OneDrive, SharePoint, AWS, Azure, Firebase, Supabase, or any remote database for the MVP.

The MVP should also avoid external academic search. Source discovery should begin with local folders and Zotero storage folders. Future Zotero API support may add collection selection while still preserving local-first behavior.

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
researchboss scan [--workspace <path>] [--source <source-folder>]
researchboss convert [--workspace <path>] [--status accepted]
researchboss metadata extract [--workspace <path>]
researchboss data profile [--workspace <path>]
researchboss data list [--workspace <path>]
researchboss data status [--workspace <path>]
researchboss report [--workspace <path>]
researchboss watch [--workspace <path>]
researchboss health [--workspace <path>]
researchboss timeline [--workspace <path>]
researchboss backup [--workspace <path>] [--include-originals]
researchboss backup-inspect <backup.zip> [--workspace <path>]
researchboss export-evidence [--workspace <path>]
researchboss zotero search "keyword terms" [--workspace <path>] [--storage <zotero-storage-folder>]
researchboss zotero collections [--workspace <path>]
researchboss zotero test [--workspace <path>]
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

During `researchboss init`, ResearchBoss looks for a default Zotero storage directory on macOS and Windows. If found, the source prompt defaults to that storage path, for example:

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

Source statuses are currently limited to:

- `pending_review`
- `accepted`
- `maybe`
- `ignored`

The source review commands update local workspace YAML files. Conversion, metadata extraction, data profiling, claim checks, and reports are local deterministic workflows and can be filtered by source status where supported.

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
6. Add a local FastAPI backend.
7. Prepare a cross-platform UI.
8. Add packaging plans for desktop distribution.

## Repository Hygiene

Editor settings and local environments are intentionally ignored. `.idea/`, `.venv/`, `.env`, Python caches, pytest caches, and build outputs should stay out of source control.

## License

ResearchBoss is released under the MIT License.

Copyright (c) 2026 Pedro Veloso

This software is provided free of charge and without warranty of any kind. See `LICENSE` for the full license text.
