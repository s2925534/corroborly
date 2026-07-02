# ResearchBoss

ResearchBoss is a local-first, evidence-first research workspace for managing research context, source files, review state, and project memory without requiring cloud services for the MVP.

The project is currently in Phase 1. The core engine and CLI foundation are now importable and covered by an initial pytest suite.

## Project Goals

- Create reproducible local research workspaces.
- Keep source registers, review decisions, context, memory, logs, and generated artefact metadata in project files.
- Support local folder and Zotero storage scanning without modifying original source files.
- Track accepted, ignored, maybe, and pending sources per project.
- Build toward conversion, metadata extraction, data profiling, research question workflows, optional OpenAI assistance, a local FastAPI backend, and future cross-platform UI.

## Current Status

Implemented or started:

- Python package structure under `researchboss/`
- Typer CLI command definitions
- Workspace creation engine
- Default YAML and Markdown workspace files
- Source folder constants
- Source scanning engine for selected file extensions
- SHA-256 file hashing
- Duplicate detection by content hash
- Source register records with `pending_review`
- Accept, ignore, and maybe source status helpers
- JSONL logs and YAML run summary helpers
- Local-first and no external search flags in generated config

Known gaps:

- Conversion, metadata extraction, data profiling, research question workflows, OpenAI features, FastAPI, UI, and packaging are planned but not implemented yet.
- Zotero support is currently storage-folder scanning only; Zotero API collection selection is not implemented yet.
- The source review workflow is implemented for local workspace state, but no downstream research tasks consume accepted sources yet.

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
    sources.py        # source scanning, hashing, status updates
    workspace.py      # workspace initialization
  cli.py              # Typer CLI, currently needs syntax fixes
  __main__.py         # python -m researchboss entry point

README.md
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
- `.env.example`
- `.gitignore`

It is also intended to create source, artefact, output, log, and context version folders.

## Development Setup

Requires Python 3.11 or newer.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

## CLI Commands

Phase 1 currently provides:

```bash
researchboss init
researchboss status --workspace <path>
researchboss config validate --workspace <path>
researchboss scan --workspace <path> --source <source-folder>
researchboss sources list --workspace <path>
researchboss sources status --workspace <path>
researchboss sources review --workspace <path>
researchboss sources accept <source-id> --workspace <path>
researchboss sources maybe <source-id> --workspace <path>
researchboss sources ignore <source-id> --reason "Reason" --workspace <path>
```

Source statuses are currently limited to:

- `pending_review`
- `accepted`
- `maybe`
- `ignored`

The source review commands only update local workspace YAML files. Later phases will use accepted sources for conversion, validation, research question support, and reports.

## Validation

Run these checks before committing:

```bash
python -m py_compile researchboss/cli.py researchboss/engine/sources.py researchboss/engine/workspace.py researchboss/core/runlog.py researchboss/core/yamlio.py researchboss/core/constants.py
python -m pytest
```

## Roadmap

1. Finish Phase 1 engine and CLI foundation.
2. Add conversion and citation metadata extraction.
3. Add CSV and SQLite profiling plus artefact metadata.
4. Add research question templates, stages, and approval workflows.
5. Add optional OpenAI features with strict privacy boundaries.
6. Add a local FastAPI backend.
7. Prepare a cross-platform UI.
8. Add packaging plans for desktop distribution.

## Repository Hygiene

Editor settings and local environments are intentionally ignored. `.idea/`, `.venv/`, `.env`, Python caches, pytest caches, and build outputs should stay out of source control.
