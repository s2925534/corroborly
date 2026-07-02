# AGENTS.md

This file gives coding agents and contributors the working rules for ResearchBoss.

## Project Intent

ResearchBoss is a local-first, evidence-first research workspace. The MVP must work without cloud storage, remote databases, or external academic search.

## Current Development Phase

The project has completed the initial Phase 1 engine and CLI foundation. Future work should keep Phase 1 tests passing while adding later phases incrementally.

Do not start FastAPI, UI, packaging, or OpenAI-heavy features until their engine contracts are tested.

## Priorities

1. Keep original source files read-only.
2. Keep workspace state explicit in local YAML and Markdown files.
3. Prefer shared engine functions over duplicating behavior in the CLI.
4. Add tests for every behavior that writes workspace state.
5. Do not invent research metadata. Unknown metadata should remain unknown.

## Privacy Rules

- Do not require Dropbox, Google Drive, OneDrive, SharePoint, AWS, Azure, Firebase, Supabase, or another remote service for MVP operation.
- Do not add external academic search during the MVP phase.
- Do not send whole PDFs, CSV files, SQLite databases, or original documents to AI providers.
- Do not print or log API keys.
- Keep `.env` ignored.

## Validation

Run these before committing changes:

```bash
python -m py_compile researchboss/cli.py
python -m pytest
```

Use the local virtual environment when available:

```bash
source .venv/bin/activate
python -m pytest
```

## Code Organization

- `researchboss/core`: low-level helpers, constants, YAML I/O, logging.
- `researchboss/engine`: reusable business logic.
- `researchboss/cli.py`: Typer command layer only.
- `tests`: pytest coverage for engine and CLI behavior.

Future phases should add focused modules rather than expanding `cli.py` with business logic.
