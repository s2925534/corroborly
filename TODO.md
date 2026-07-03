# TODO

## Phase 1: Engine and CLI Foundation

- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Fix `researchboss/cli.py` indentation errors so the package imports.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Import or remove the `ScanResult` annotation in the scan command.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Install and verify development dependencies from `pyproject.toml`.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add a `tests/` folder with pytest coverage for workspace initialization.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add tests for source scanning, hashing, duplicate detection, and allowed extensions.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add tests for source status transitions: accepted, ignored, and maybe.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add Typer CLI smoke tests for `init`, `status`, `config validate`, `scan`, and `sources` commands.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Validate source status values instead of accepting arbitrary strings.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add `AGENTS.md` with project instructions and development rules.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Remove or replace the unused PyCharm sample `main.py`.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Decide whether `.idea/` should stay out of source control.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Expand README setup, testing, and architecture notes after the CLI is fixed.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add numbered init prompts with retry validation instead of raw Click errors.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Capture optional research questions, draft status, and subquestions during init.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Capture init setup context: stakeholders, citation style, output type, data expectations, source review default, AI preference, and privacy preference.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Print concrete next-step commands after successful init.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Resolve omitted `--workspace` interactively across workspace-aware commands.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Auto-select a single discovered workspace and remember a default when several workspaces exist.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add `researchboss version`.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add `researchboss doctor` runtime checks and run the same preflight before `researchboss init`.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add coverage for `python -m researchboss`.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Mark Phase 1 complete in README roadmap and add a Quick Start.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Record `zotero_storage` as the scan provider from workspace config when `--kind` is omitted.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Capture Zotero storage item keys and `.zotero-ft-cache` presence during storage scans.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add read-only deterministic Zotero storage keyword search without AI or Zotero API use.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Store the Zotero parent root automatically when `storage/` is selected.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add read-only `zotero.sqlite` metadata lookup using immutable SQLite connections.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Link Zotero storage files to parent Zotero items.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add offline collection listing from local SQLite.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add selected-collections and entire-library scan modes.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add include/exclude subcollections support.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add local metadata quality checks.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add attachment health checks.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add local full-text cache availability report.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Score deterministic Zotero search against local metadata.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add local Zotero metadata snapshots.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Enrich source-register entries with Zotero metadata.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add duplicate detection across Zotero metadata.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add conservative offline BibTeX export from local metadata.

## Future Zotero Work

- [ ] Add future Zotero API collection listing and selection only if needed after offline workflows are stable.
- [ ] Add richer local SQLite coverage for notes, tags, relations, and item links.
- [ ] Add more complete BibTeX item-type and field mapping.

## Phase 2: Conversion and Metadata

- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add TXT and MD conversion first.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add DOCX conversion.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add PDF conversion with page markers.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add conversion cache keyed by file hash.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add failed conversion handling and conversion statuses.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add DOI detection.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add basic citation metadata extraction without inventing missing metadata.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add tests for all conversion paths.

## Phase 3: Data and Artefacts

- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add CSV profiling: rows, columns, missing values, and inferred types.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add SQLite profiling: tables, columns, and row counts where practical.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add JSON source registration and profiling.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add data profile reports under `outputs/data-profiles`.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Expand artefact registry records with linked sources and metadata.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add tests for data profiling and artefact registry behavior.

## Phase 4: Research Questions and Stages

- [ ] Add richer research question templates for M.Phil, PhD, Other academic research, Industry research, and Custom.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add M.Phil and PhD stage templates.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add stage statuses.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add research question candidate, approval, rejection, and archive workflows beyond init-time capture.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add deterministic research question readiness checks without claiming novelty or contribution strength.
- [ ] Add warning thresholds without hard limits by default.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add tests for research question and stage workflows.

## Phase 5: Optional OpenAI Features

- [ ] Add `researchboss ai test`.
- [ ] Read `OPENAI_API_KEY` from the environment without printing or logging it.
- [ ] Keep OpenAI disabled unless explicitly enabled.
- [ ] Keep Anthropic, Claude, and local LLM providers as future flags only.
- [ ] Add a safe context builder that never sends whole PDFs, CSVs, or SQLite databases.
- [ ] Add optional AI-assisted review.
- [ ] Add optional novelty assessment backed by `novelty-ledger.yaml`.
- [ ] Add AI-assisted research question strength, novelty, field usefulness, and evidence-quality review after privacy-boundary tests exist.
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
