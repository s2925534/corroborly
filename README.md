# ResearchBoss

ResearchBoss is a local-first, evidence-first research workspace for managing research context, source files, review state, and project memory without requiring cloud services for the MVP.

The project is currently in Phase 1. The core engine and CLI foundation are importable, tested, and usable for local workspace setup, local source scanning, and source review.

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
- Numbered init prompts for research level, citation style, output type, data expectations, source review defaults, and AI preference metadata
- Optional research questions and subquestions captured during init
- Draft research questions stored separately from approved research questions
- Optional supervisor or stakeholder context captured during init
- Workspace discovery and selection when `--workspace` is omitted
- Local default workspace selection stored in ignored local YAML under `workspaces/`
- Concrete next-step command examples after successful init

Known gaps:

- Conversion, metadata extraction, data profiling, research stage workflows, OpenAI behavior, FastAPI, UI, and packaging are planned but not implemented yet.
- Zotero support is currently storage-folder scanning only; Zotero API collection selection is not implemented yet.
- The source review workflow is implemented for local workspace state, but no downstream research tasks consume accepted sources yet.
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
    sources.py        # source scanning, hashing, status updates
    workspace.py      # workspace initialization
  cli.py              # Typer CLI command layer
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

## CLI Commands

Phase 1 currently provides:

```bash
researchboss init
researchboss status [--workspace <path>]
researchboss config validate [--workspace <path>]
researchboss scan [--workspace <path>] [--source <source-folder>]
researchboss sources list [--workspace <path>]
researchboss sources status [--workspace <path>]
researchboss sources review [--workspace <path>]
researchboss sources accept <source-id> --workspace <path>
researchboss sources maybe <source-id> --workspace <path>
researchboss sources ignore <source-id> --reason "Reason" --workspace <path>
```

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
