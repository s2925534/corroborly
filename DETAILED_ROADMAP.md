# ResearchBoss Detailed Roadmap

Project version: 0.3.5

Last updated: 2026-07-03

This roadmap tracks implementation progress for ResearchBoss. Update this file whenever development changes feature status, project scope, version, or recommended next steps.

## 1. Executive Summary

ResearchBoss is currently past the local deterministic Phase 2-4 foundation and still before AI, FastAPI, UI, and packaging.

Implemented:

- Python package structure.
- Typer CLI foundation.
- Local workspace initialization.
- Local YAML and Markdown workspace state files.
- Source folder scanning.
- Read-only local Zotero storage scanning.
- Read-only local Zotero SQLite metadata lookup.
- Offline Zotero collection listing and selected-collection scan modes.
- Deterministic local Zotero search over filenames, `.zotero-ft-cache`, and local SQLite metadata.
- Offline Zotero metadata reports, attachment health checks, full-text cache reports, metadata snapshots, duplicate checks, and BibTeX export.
- Source hashing and duplicate detection.
- TXT, MD, DOCX, and page-marked PDF conversion.
- Conversion cache and failed conversion records.
- Deterministic citation metadata extraction.
- CSV, SQLite, and JSON data profiling.
- Artefact registry with linked sources, linked research questions, review flags, and AI flags.
- Deterministic artefact creation for source summaries, literature review matrices, claim-evidence tables, research question briefs, and data profile summaries.
- M.Phil and PhD stage templates.
- Research question list, approve, reject, archive, and deterministic readiness-check workflows.
- Manual claim ledger and citation gap detection.
- Local Markdown workspace reports.
- One-shot watch reports for unregistered source files.
- Local workspace backups.
- Config migration and workspace schema versioning.
- Zotero-style citation style wording, including explicit `American Psychological Association 7th edition`.
- Strict one-way Zotero-to-ResearchBoss blocker config that prevents writes inside the local Zotero directory.
- Source review statuses: `pending_review`, `accepted`, `maybe`, `ignored`.
- Workspace discovery, selection, and local default workspace memory.
- JSONL logs and YAML run summaries.
- README, AGENTS.md, architecture notes, TODO, changelog, and tests.

Partially implemented:

- Zotero support: local storage-folder and read-only SQLite support exist; Zotero API integration is not implemented.
- AI setup: local preference metadata exists; AI behavior is not implemented.

Not implemented:

- Optional OpenAI workflows.
- FastAPI backend.
- Cross-platform UI.
- Packaging.

Current repository state: coherent and test-covered for local deterministic engine and CLI workflows through conversion, metadata, data profiling, Zotero offline support, research questions, claims, reports, backup, and migration.

Deterministic boundary:

- Current non-AI workflows may extract, count, list, copy metadata, link explicit IDs, profile files, and create fixed templates from workspace state.
- Current non-AI workflows must not interpret meaning, judge usefulness, assess novelty, infer evidence strength, synthesize arguments, rank relevance beyond explicit rule-based matching, or create conclusions from source content.
- Anything not safely deterministic belongs to the later AI implementation phase, behind explicit user opt-in, privacy-boundary tests, and workspace-only output rules.

## 2. Repository Structure Review

Current important structure:

```text
researchboss/
  core/
    constants.py
    runlog.py
    yamlio.py
  engine/
    sources.py
    workspace.py
    zotero.py
    conversion.py
    metadata.py
    data.py
    artefact_creation.py
    artefacts.py
    research_questions.py
    claims.py
    reports.py
    watch.py
    backup.py
    migrations.py
  cli.py
  __init__.py
  __main__.py

tests/
  test_cli.py
  test_sources.py
  test_workspace.py
  test_zotero.py
  test_conversion.py
  test_metadata.py
  test_data.py
  test_artefacts.py
  test_research_questions.py
  test_claims.py
  test_reports.py
  test_watch.py
  test_backup.py
  test_migrations.py

docs/
  ARCHITECTURE.md

AGENTS.md
CHANGELOG.md
DETAILED_ROADMAP.md
LICENSE
README.md
TODO.md
pyproject.toml
```

Important folders:

- `researchboss/core`: low-level constants, YAML I/O, logging, and run summaries.
- `researchboss/engine`: reusable business logic for workspace creation, source scanning, source review, and local Zotero storage helpers.
- `researchboss/cli.py`: Typer command layer.
- `tests`: pytest coverage for CLI and engine behavior.
- `docs`: architecture and planning notes.
- `workspaces`: ignored generated local workspaces.

Expected future folders:

- `researchboss/api` for FastAPI.
- `frontend` or equivalent UI planning folder.
- `docs/api` for API contracts.
- `docs/packaging` for desktop packaging notes.

## 3. Implemented Features

| Feature | Status | Evidence | Notes |
| --- | --- | --- | --- |
| Python package structure | Implemented | `researchboss/`, `pyproject.toml` | Package installs as `researchboss`. |
| Typer CLI | Implemented | `researchboss/cli.py` | CLI commands are tested. |
| `researchboss init` | Implemented | `researchboss/cli.py`, `researchboss/engine/workspace.py` | Creates local workspace skeleton. |
| Workspace files | Implemented | `researchboss/core/constants.py`, `workspace.py` | YAML and Markdown state files are created. |
| Local scan | Implemented | `researchboss/engine/sources.py` | Scans supported source files. |
| Zotero storage scan | Implemented | `sources.py`, `zotero.py` | Reads local `storage/`; no API use. |
| Zotero SQLite metadata | Implemented | `researchboss/engine/zotero.py` | Uses read-only immutable SQLite connections. |
| Zotero collection workflows | Implemented | `researchboss/cli.py`, `zotero.py` | Local collection listing, selection, and collection scans. |
| Zotero storage search | Implemented | `researchboss/engine/zotero.py`, `cli.py` | Searches filenames, `.zotero-ft-cache`, and SQLite metadata. |
| Zotero offline reports | Implemented | `researchboss/engine/zotero.py`, `cli.py` | Metadata, attachment, full-text, duplicates, snapshots, BibTeX. |
| Conversion | Implemented | `researchboss/engine/conversion.py`, `cli.py` | TXT, MD, DOCX, simple page-marked PDF, cache, failures. |
| Citation metadata | Implemented | `researchboss/engine/metadata.py`, `cli.py` | DOI/year/title extraction without invented fields. |
| Data profiling | Implemented | `researchboss/engine/data.py`, `cli.py` | CSV, SQLite, JSON profiles. |
| Deterministic artefact creation | Implemented | `researchboss/engine/artefact_creation.py`, `cli.py` | Non-AI workspace reports/tables requiring user review. |
| Artefact registry | Implemented | `researchboss/engine/artefacts.py`, `cli.py` | Linked sources/RQs, review and AI flags. |
| Research stages/questions | Implemented | `workspace.py`, `research_questions.py`, `cli.py` | M.Phil/PhD stages, RQ workflow commands, and deterministic readiness checks. |
| Claims and citation gaps | Implemented | `researchboss/engine/claims.py`, `cli.py` | Manual claims and gap report. |
| Reports/watch/backup/migration | Implemented | `reports.py`, `watch.py`, `backup.py`, `migrations.py` | Local deterministic utility workflows. |
| Hashing | Implemented | `sha256_file` in `sources.py` | SHA-256 content hash. |
| Duplicate detection | Implemented | `scan_sources` in `sources.py` | Duplicate by content hash. |
| Source statuses | Implemented | `SOURCE_STATUSES` in `sources.py` | Pending, accepted, maybe, ignored. |
| Source review workflow | Implemented | `set_source_status`, CLI source commands | Local YAML-only state updates. |
| Logs and summaries | Implemented | `researchboss/core/runlog.py` | JSONL logs and YAML summaries. |
| Progress bars | Implemented | `scan` in `cli.py` | Rich progress display. |
| Tests | Implemented | `tests/` | Current suite covers Phase 1 and Zotero storage helpers. |
| README and AGENTS.md | Implemented | `README.md`, `AGENTS.md` | Contributor and user docs exist. |

## 4. Phase-by-Phase Audit

### Phase 1: Engine and CLI Foundation

Status: complete, with extra local Zotero storage improvements.

Implemented:

- Package structure, CLI, init, workspace files, source scanning, source review, logging, run summaries, progress bars, tests, README, AGENTS.md.
- Workspace discovery and default workspace memory.
- Runtime checks through `doctor` and before `init`.
- Local Zotero storage scan/search without AI or API use.

Remaining Phase 1 refinements:

- Consider validating `--kind` values instead of accepting arbitrary provider strings.

### Phase 2: Conversion and Metadata

Status: implemented for deterministic local MVP paths.

Implemented:

- TXT, MD, DOCX, and simple PDF conversion with page markers.
- Conversion cache by file hash.
- Failed conversion handling.
- DOI detection and basic citation metadata extraction without invented metadata.

### Phase 3: Data and Artefacts

Status: implemented for deterministic local MVP paths.

Implemented:

- CSV profiling.
- SQLite profiling.
- JSON source registration and profiling.
- Data profile reports.
- Rich artefact registry records.

### Phase 4: Research Questions and Stages

Status: implemented for deterministic local MVP paths.

Implemented:

- Init-time research questions.
- Draft and approved separation.
- Optional subquestions.
- M.Phil and PhD stage templates.
- Stage statuses.
- RQ list, approve, reject, and archive commands.
- Deterministic RQ readiness checks for question form, scope signals, vague wording, possible multiple questions, context markers, subquestion alignment, and project-level hints.
- Local RQ readiness reports under `outputs/validation/research-question-readiness.yaml`.

Future:

- Richer RQ templates for all project types.
- Warning thresholds.
- AI-assisted RQ strength, novelty, field usefulness, contribution, and evidence-quality review after privacy-boundary tests exist.

### Phase 5: Optional OpenAI Features

Status: not implemented.

Implemented:

- Local AI preference metadata only.
- AI disabled in generated app settings.

Next work:

- `researchboss ai test`.
- Environment-based `OPENAI_API_KEY` handling.
- Safe context builder.
- Optional review and novelty flows.
- Tests for privacy boundaries.

### Phase 6: FastAPI Local Backend

Status: not started.

Next work:

- Define engine contracts first.
- Add local API routes after core behavior is tested.

### Phase 7: Cross-Platform UI Preparation

Status: not started.

Next work:

- Document UI strategy.
- Define API contract.
- Keep UI logic outside engine/core.

### Phase 8: Packaging

Status: not started.

Next work:

- Packaging plan.
- PyInstaller or equivalent notes.
- Windows, macOS, Linux distribution notes.

## 5. CLI Audit

| Command | Status | Notes |
| --- | --- | --- |
| `researchboss init` | Implemented | Creates workspace and prompts for initial context. |
| `researchboss status` | Implemented | Shows source counts. |
| `researchboss config validate` | Implemented | Checks required workspace paths and YAML readability. |
| `researchboss config migrate` | Implemented | Fills missing deterministic workspace config fields. |
| `researchboss scan` | Implemented | Scans configured or provided source root. |
| `researchboss convert` | Implemented | Converts TXT, MD, DOCX, and simple PDFs. |
| `researchboss metadata extract` | Implemented | Extracts deterministic citation metadata. |
| `researchboss data profile` | Implemented | Profiles CSV, SQLite, and JSON sources. |
| `researchboss data list` | Implemented | Lists data sources. |
| `researchboss data status` | Implemented | Shows data profile counts. |
| `researchboss report` | Implemented | Generates local Markdown workspace report. |
| `researchboss watch` | Implemented | Writes unregistered source candidate report. |
| `researchboss backup` | Implemented | Creates local workspace zip backup. |
| `researchboss sources list` | Implemented | Lists source register records. |
| `researchboss sources review` | Implemented | Interactive pending source review. |
| `researchboss sources accept` | Implemented | Marks source accepted. |
| `researchboss sources ignore` | Implemented | Marks source ignored with reason. |
| `researchboss sources maybe` | Implemented | Marks source maybe. |
| `researchboss sources status` | Implemented | Shows source status counts. |
| `researchboss zotero search` | Implemented | Local storage and metadata keyword search; no AI/API. |
| `researchboss zotero collections` | Implemented | Lists collections from local SQLite. |
| `researchboss zotero select-collections` | Implemented | Stores selected collection config locally. |
| `researchboss zotero use-entire-library` | Implemented | Restores entire-library mode. |
| `researchboss zotero scan-collection` | Implemented | One-off scan of a local collection. |
| `researchboss zotero metadata-report` | Implemented | Writes metadata quality report. |
| `researchboss zotero attachment-health` | Implemented | Writes attachment/storage health report. |
| `researchboss zotero fulltext-report` | Implemented | Writes `.zotero-ft-cache` availability report. |
| `researchboss zotero duplicates` | Implemented | Writes DOI/title-year duplicate candidates. |
| `researchboss zotero snapshot` | Implemented | Writes local metadata snapshot. |
| `researchboss zotero export-bibtex` | Implemented | Writes conservative BibTeX from local metadata. |
| `researchboss zotero test` | Implemented | Validates local storage, SQLite, and cache availability. |
| `researchboss rqs list` | Implemented | Lists RQ groups. |
| `researchboss rqs check` | Implemented | Deterministic readiness checks only; no novelty or contribution-strength claims. |
| `researchboss rqs suggest` | Missing | Phase 4 or Phase 5 depending on AI use. |
| `researchboss rqs approve` | Implemented | Approves draft RQs. |
| `researchboss rqs reject` | Implemented | Rejects RQs. |
| `researchboss rqs archive` | Implemented | Archives RQs. |
| `researchboss claims add/list/gaps` | Implemented | Manual claim ledger and citation gaps. |
| `researchboss artefacts register/list` | Implemented | Artefact registry workflow. |
| `researchboss artefacts create` | Implemented | Deterministic non-AI artefact creation from existing workspace state. |
| `researchboss review` | Missing | Later integrated review workflow. |
| `researchboss assess-novelty` | Missing | Phase 5. |
| `researchboss ai test` | Missing | Phase 5. |

## 6. Config and Workspace Audit

Workspace creation currently generates the Phase 1 file and folder skeleton, including research context/state files, source registers, review lists, ledgers, terminology, feedback, memory files, artefact registry, app settings, `.gitignore`, source folders, artefact folders, output folders, logs, run summaries, and context versions.

Zotero config now stores both the selected `storage/` path and the parent Zotero directory when `sources.mode` is `zotero_storage`.

## 7. Source Workflow Audit

Implemented:

- Discover local source files.
- Hash files.
- Detect duplicates by hash.
- Create source IDs.
- Mark new sources as `pending_review` or `maybe`.
- Accept, ignore, and maybe source workflow.
- Exclude ignored/accepted/maybe state per workspace.

Missing or future:

- Metadata-only source status.
- Failed conversion status.
- Conversion outputs and metadata.
- Data profile statuses.
- Manual review required status beyond current config flag.
- Downstream enforcement that only accepted sources are used for research tasks.

## 8. Zotero Audit

Implemented:

- Detect default Zotero `storage/` path on macOS and Windows.
- Scan local Zotero storage folders.
- Store Zotero parent root automatically.
- Record Zotero storage key and relative storage path.
- Detect `.zotero-ft-cache`.
- Read local `zotero.sqlite` through immutable read-only SQLite connections.
- Link storage files to parent Zotero items.
- List local collections.
- Select one or more local collections for future scans.
- Include or exclude subcollections.
- Switch between entire-library and selected-collections mode.
- Search filenames, `.zotero-ft-cache`, title, creators, abstract, DOI, and collection paths deterministically.
- Generate metadata quality, attachment health, and full-text availability reports.
- Create local metadata snapshots.
- Enrich source-register entries with local Zotero metadata.
- Detect possible metadata duplicates by DOI or title/year.
- Export conservative BibTeX from local metadata.
- Avoid modifying Zotero files.
- Avoid writing into Zotero storage.
- Enforce the hard project rule that no CLI workflow, development workflow, or future AI feature may modify anything inside the local Zotero directory.
- Workspace config stores `strict_one_way_from_zotero_to_researchboss: true` and `block_writes_to_zotero_directory: true`.

Missing:

- Zotero local API.
- Richer local metadata coverage for tags, notes, relations, and item links.
- More complete BibTeX item-type mapping.

## 9. Data Source Audit

Status: implemented for deterministic local MVP paths.

Implemented:

- CSV profiling.
- SQLite profiling.
- JSON source registration.
- Data source statuses.
- Data profile reports.
- No AI dataset upload behavior exists.

## 10. Artefact Audit

Status: implemented for deterministic local MVP paths.

Implemented:

- Artefact folders.
- `artefact-registry.yaml` shell.
- Artefact metadata records.
- Linked sources and research questions.
- AI-generated flag.
- `requires_user_review` flag.

## 11. AI and OpenAI Audit

Status: not implemented.

Implemented:

- AI preference metadata.
- `ai.enabled: false` in local app settings.
- `.env` ignored.
- `.env.example` exists.

Missing:

- OpenAI provider setup command.
- API key validation.
- Safe context builder.
- Novelty assessment.
- Corpus summary behavior.
- Privacy-boundary tests.

Planned AI options:

- Workflows marked as not safely deterministic will be implemented only in the AI phase, not in the current deterministic engine.
- Research question strength, novelty, contribution certainty, field usefulness, and evidence-quality reasoning will be AI-assisted or human-review workflows, not deterministic validators.
- Explicit user-controlled options to allow AI to read an entire file when the user approves that level of context.
- Explicit user-controlled options to allow AI to read a directory of files when the user approves that level of context.
- Optional full-paper reasoning mode for consuming entire papers.
- Optional cross-reference mode where AI can compare full papers against in-progress artefacts.
- These modes must be disabled by default, must never modify Zotero, and must keep outputs inside the ResearchBoss workspace.

## 12. Tests Audit

Framework: pytest.

Current tested areas:

- CLI smoke tests.
- Workspace initialization.
- Source scanning and review.
- Workspace selection.
- Runtime checks.
- Local Zotero storage helpers, SQLite metadata, collection filtering, reports, snapshots, duplicate checks, BibTeX export, and CLI search.
- Conversion, metadata extraction, data profiling, artefact registry, research questions, claims, reports, watch, backup, and migration.

Current expected validation:

```bash
python -m py_compile researchboss/cli.py researchboss/engine/*.py researchboss/core/*.py
python -m pytest
```

Recommended next tests:

- Integrated review workflow tests once review commands are added.
- Future AI privacy-boundary tests before any AI implementation.

## 13. Security and Privacy Audit

Current privacy posture:

- MVP does not require cloud services.
- No external academic search.
- No AI document upload behavior exists.
- Source files are read-only inputs.
- Zotero storage is read-only.
- The local Zotero directory is a hard no-write boundary for current and future non-AI or AI workflows.
- Future AI whole-file, whole-directory, full-paper, and artefact cross-reference modes must be explicit opt-in settings and must preserve the Zotero no-write boundary.
- `.env` is ignored.

Known follow-up:

- Add tests for future AI privacy boundaries before implementing AI-assisted flows.

## 14. Documentation Audit

Implemented:

- `README.md`
- `AGENTS.md`
- `docs/ARCHITECTURE.md`
- `TODO.md`
- `CHANGELOG.md`
- `DETAILED_ROADMAP.md`
- Setup and test instructions.
- Initial OpenAI and Zotero notes.
- Local-first privacy boundaries.

Missing:

- Full API contract.
- Desktop/web/mobile strategy.
- Packaging documentation.

## 15. Immediate Next Steps

1. Validate scan provider values.
   - Why: prevent accidental unknown provider strings in source records.
   - Likely files: `sources.py`, `cli.py`, tests.
   - Tests: invalid `--kind`.
   - Complexity: low.
   - Phase: 1 refinement.

2. Add richer local Zotero metadata coverage.
    - Why: tags, notes, item links, and relations can improve offline review without AI/API.
    - Likely files: `zotero.py`, tests, docs.
    - Tests: SQLite fixture for notes/tags/relations.
    - Complexity: medium.
    - Phase: 1 refinement / Phase 2 support.

3. Add integrated source review/report workflow.
   - Why: ties source review, conversion, metadata, claims, and reports into one deterministic command.
   - Likely files: `cli.py`, new engine module, tests.
   - Tests: end-to-end local workspace workflow.
   - Complexity: medium.
   - Phase: 4 refinement.

4. Add richer PDF extraction using an optional local dependency.
   - Why: current PDF support is intentionally conservative for simple uncompressed streams.
   - Likely files: conversion engine, docs, tests.
   - Tests: realistic PDF fixture.
   - Complexity: medium.
   - Phase: 2 refinement.

5. Start FastAPI local backend contracts.
   - Why: deterministic engine contracts now exist for CLI reuse.
   - Likely files: `researchboss/api`, tests, docs.
   - Tests: API route tests.
   - Complexity: high.
   - Phase: 6.

## 16. Recommended Resume Point

Resume with either one final Phase 1 refinement, scan provider validation, or begin Phase 6 FastAPI local backend contracts. AI remains intentionally out of scope until explicit privacy-boundary tests and safe context contracts are designed.

## 17. Maintenance Rule

Whenever development changes ResearchBoss behavior:

- Update this roadmap.
- Update `README.md` project version.
- Update package version in `pyproject.toml` and `researchboss/__init__.py` when releasing or committing user-visible feature work.
- Update `CHANGELOG.md`.
- Keep tests passing before commit or push.
