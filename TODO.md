# TODO

## Phase 1: Engine and CLI Foundation

- [x] Fix `researchboss/cli.py` indentation errors so the package imports.
- [x] Import or remove the `ScanResult` annotation in the scan command.
- [x] Install and verify development dependencies from `pyproject.toml`.
- [x] Add a `tests/` folder with pytest coverage for workspace initialization.
- [x] Add tests for source scanning, hashing, duplicate detection, and allowed extensions.
- [x] Add tests for source status transitions: accepted, ignored, and maybe.
- [x] Add Typer CLI smoke tests for `init`, `status`, `config validate`, `scan`, and `sources` commands.
- [x] Validate source status values instead of accepting arbitrary strings.
- [x] Add `AGENTS.md` with project instructions and development rules.
- [x] Remove or replace the unused PyCharm sample `main.py`.
- [x] Decide whether `.idea/` should stay out of source control.
- [x] Expand README setup, testing, and architecture notes after the CLI is fixed.

## Phase 2: Conversion and Metadata

- [ ] Add TXT and MD conversion first.
- [ ] Add DOCX conversion.
- [ ] Add PDF conversion with page markers.
- [ ] Add conversion cache keyed by file hash.
- [ ] Add failed conversion handling and conversion statuses.
- [ ] Add DOI detection.
- [ ] Add basic citation metadata extraction without inventing missing metadata.
- [ ] Add tests for all conversion paths.

## Phase 3: Data and Artefacts

- [ ] Add CSV profiling: rows, columns, missing values, and inferred types.
- [ ] Add SQLite profiling: tables, columns, and row counts where practical.
- [ ] Add data profile reports under `outputs/data-profiles`.
- [ ] Expand artefact registry records with linked sources and metadata.
- [ ] Add tests for data profiling and artefact registry behavior.

## Phase 4: Research Questions and Stages

- [ ] Add research question templates for M.Phil, PhD, Other academic research, Industry research, and Custom.
- [ ] Add M.Phil and PhD stage templates.
- [ ] Add stage statuses.
- [ ] Add research question candidate, approval, rejection, and archive workflows.
- [ ] Add warning thresholds without hard limits by default.
- [ ] Add tests for research question and stage workflows.

## Phase 5: Optional OpenAI Features

- [ ] Add `researchboss ai test`.
- [ ] Read `OPENAI_API_KEY` from the environment without printing or logging it.
- [ ] Keep OpenAI disabled unless explicitly enabled.
- [ ] Keep Anthropic, Claude, and local LLM providers as future flags only.
- [ ] Add a safe context builder that never sends whole PDFs, CSVs, or SQLite databases.
- [ ] Add optional AI-assisted review.
- [ ] Add optional novelty assessment backed by `novelty-ledger.yaml`.
- [ ] Add tests for missing API key behavior and privacy boundaries.

## Phase 6: FastAPI Local Backend

- [ ] Add a local FastAPI app.
- [ ] Add routes for projects, sources, artefacts, research questions, reports, settings, logs, AI, and novelty.
- [ ] Reuse engine logic rather than duplicating business logic.
- [ ] Add API tests.

## Phase 7: Cross-Platform UI Preparation

- [ ] Document the desktop, web, and mobile UI strategy.
- [ ] Define a clear API contract.
- [ ] Add a frontend folder or explicit planned UI structure.
- [ ] Keep UI logic out of the core engine.

## Phase 8: Packaging

- [ ] Add packaging plan.
- [ ] Add PyInstaller or equivalent notes for the Python engine.
- [ ] Add future Flutter desktop packaging notes.
- [ ] Document Windows, macOS, and Linux considerations.
