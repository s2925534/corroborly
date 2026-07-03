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
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Validate scan provider values such as `local_folder` and `zotero_storage`.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add a workspace health command for config, folders, source counts, failed conversions, citation gaps, RQ readiness, and unsupported files.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add local backup restore dry-run reporting without restoring files.

## Future Zotero Work

- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add read-only Zotero API collection listing and selection only if needed after offline workflows are stable.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add richer local SQLite coverage for notes, tags, relations, and item links.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add more complete BibTeX item-type and field mapping.

## Phase 2: Conversion and Metadata

- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add TXT and MD conversion first.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add DOCX conversion.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add PDF conversion with page markers.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add conversion cache keyed by file hash.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add failed conversion handling and conversion statuses.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add DOI detection.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add basic citation metadata extraction without inventing missing metadata.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add deterministic DOI syntax and resolver-link validation to flag malformed or suspicious DOI links without rewriting metadata.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add citation consistency checks for missing DOI, year, title, author, or mismatched DOI URL formats.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add duplicate filename, title, and DOI reports beyond content-hash duplicates.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Build a local keyword index over converted text in `sources_text/`.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add tests for all conversion paths.


## Future PDF/Text Processing Learned From `../pdf-merge`

- [ ] <span style="color: #2e7d32; font-weight: 600;">Add</span> optional PyMuPDF/PyPDF2-backed PDF extraction for more reliable page text than the current conservative parser.
- [ ] <span style="color: #2e7d32; font-weight: 600;">Add</span> OCR readiness checks and optional OCR fallback for scanned PDFs, keeping OCR local and opt-in.
- [ ] <span style="color: #2e7d32; font-weight: 600;">Add</span> deterministic sidecar metadata parsing for CSL JSON, BibTeX, and RIS files.
- [ ] <span style="color: #2e7d32; font-weight: 600;">Add</span> deterministic abstract, keyword, publication-title, year, and author extraction from sidecar files and PDF metadata.
- [ ] <span style="color: #2e7d32; font-weight: 600;">Add</span> accepted-source text corpus export with per-source headers, source IDs, titles, authors, and separators.
- [ ] <span style="color: #2e7d32; font-weight: 600;">Add</span> optional PDF merge artefacts for accepted source PDFs, with library-wide and batch merge modes.
- [ ] <span style="color: #2e7d32; font-weight: 600;">Add</span> merge manifests and CSV reports that record which source IDs were included, skipped, failed, or batched.
- [ ] <span style="color: #2e7d32; font-weight: 600;">Add</span> deterministic filename normalization helpers based on title, author token, year, and source ID without renaming original files.
- [ ] <span style="color: #2e7d32; font-weight: 600;">Add</span> local abstract-folder import and screening workflow for pre-collected abstracts.
- [ ] <span style="color: #2e7d32; font-weight: 600;">Add</span> local abstract-file parser for old Scopus abstract text files with fields such as title, authors, publication, year, DOI, cited-by count, abstract, API URL, and Scopus view URL.
- [ ] <span style="color: #2e7d32; font-weight: 600;">Add</span> abstract candidate register that separates imported abstracts into candidate, filtered, not relevant, skipped, and selected-for-review groups without moving or deleting original files.
- [ ] <span style="color: #2e7d32; font-weight: 600;">Add</span> accepted-source text corpus export that can write one combined file plus a manifest, while preserving the individual converted text files.
- [ ] <span style="color: #2e7d32; font-weight: 600;">Add</span> PDF merge dry-run and manifest-first mode before generating merged artefact PDFs.
- [ ] <span style="color: #2e7d32; font-weight: 600;">Add</span> skipped/failed processing reports for protected PDFs, corrupt PDFs, OCR-needed PDFs, missing metadata, and unsupported formats without moving originals.

## Phase 3: Data and Artefacts

- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add CSV profiling: rows, columns, missing values, and inferred types.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add SQLite profiling: tables, columns, and row counts where practical.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add JSON source registration and profiling.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add data profile reports under `outputs/data-profiles`.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Expand artefact registry records with linked sources and metadata.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add evidence bundle export for accepted source metadata, claims, RQs, artefacts, and data profiles.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add artefact review statuses such as reviewed, needs revision, and accepted.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add artefact dependency checks against existing accepted sources and approved RQs.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add tests for data profiling and artefact registry behavior.

## Phase 4: Research Questions and Stages

- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add richer research question templates for M.Phil, PhD, Other academic research, Industry research, and Custom.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add M.Phil and PhD stage templates.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add stage statuses.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add research question candidate, approval, rejection, and archive workflows beyond init-time capture.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add deterministic research question readiness checks without claiming novelty or contribution strength.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add warning thresholds without hard limits by default.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add source notes commands for local per-source notes.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add manual source tags for deterministic review categories.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add claim status workflow for supported, needs evidence, rejected, and needs review.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add claim-source validation to ensure claims link only to accepted sources.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add source review reports for pending, accepted, maybe, ignored, duplicates, and failed files.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add decision log commands for structured project decisions.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add terminology glossary commands.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add supervisor or stakeholder feedback commands.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add context changelog commands.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add local timeline report from logs, decisions, scans, conversions, and RQ changes.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add tests for research question and stage workflows.

## Phase 5: Optional OpenAI Features

- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add `researchboss ai test`.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Read `OPENAI_API_KEY` from the environment or local `.env` without printing or logging it.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Keep OpenAI disabled unless explicitly requested with `--ai`.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Keep Anthropic, Claude, and local LLM providers as future flags only.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add a safe context preview builder that never sends whole PDFs, CSVs, SQLite databases, or original files by default.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add optional AI-assisted review through `researchboss ai review --ai`.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add optional novelty assessment backed by `novelty-ledger.yaml` through `researchboss assess-novelty --ai`.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add AI-assisted research question strength, novelty, field usefulness, and evidence-quality review through `researchboss rqs assess --ai`.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add tests for missing API key behavior, key non-disclosure, explicit `--ai`, and safe-context privacy boundaries.

## Future AI Work That Makes Sense To Implement

- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add AI corpus summary reports from safe context only through `researchboss ai corpus-summary --ai`.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add AI claim-checking assistance against accepted sources and `claims-ledger.yaml` through `researchboss ai claim-check --ai`.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add AI citation gap recommendations using accepted sources, claims, and research questions through `researchboss ai citation-gaps --ai`.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add AI artefact cross-reference review against in-progress artefacts through `researchboss ai artefact-cross-reference --ai`.
- [ ] <span style="color: #ef6c00; font-weight: 600;">Add</span> explicit per-run full-file AI opt-in flags with warning output and tests.
- [ ] <span style="color: #ef6c00; font-weight: 600;">Add</span> explicit per-run directory AI opt-in flags with warning output and tests.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add AI source relevance recommendations that cite source IDs and never modify source statuses automatically through `researchboss ai source-relevance --ai`.
- [ ] <span style="color: #ef6c00; font-weight: 600;">Add</span> AI-assisted abstract screening for locally imported abstracts, writing recommendations only.

## Future External Search Work After MVP

- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add deterministic search query plan generation from research context and approved RQs through `researchboss search plan`.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add search query history so repeated query combinations can be skipped or intentionally rerun.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add explicit Scopus integration with `--external-search` opt-in.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add API response snapshots and no-results logs for external search reproducibility.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add Scopus quality-scoring rules that rank candidate papers by citation count, publication year, source title, document type, open-access status, and identifier completeness without inventing quality.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add author-quality signals from available Scopus metadata, such as author IDs and affiliation IDs when the API response provides them.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add configurable search thresholds for minimum citation count, publication year range, open-access preference, maximum results per query, and low-result logging.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add query validation reports that compare result counts, duplicate rate, threshold pass rate, and topical keyword coverage for each query.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add no-result and low-result query logging with retry suggestions, without automatically entering infinite query-generation loops.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add deterministic query refinement candidates based on failed query terms and observed candidate metadata.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add expanded hard search budgets per run covering API calls, generated queries, refinement rounds, result pages, and elapsed time.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add an external-paper candidate register that stores scored Scopus results separately from accepted local sources until reviewed.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add full-text availability detection from Scopus metadata, DOI links, and open-access links without downloading or scraping paywalled files.
- [ ] <span style="color: #1565c0; font-weight: 600;">Add</span> local Zotero matching for external candidate full-text availability detection.
- [ ] <span style="color: #1565c0; font-weight: 600;">Add</span> commands to import user-approved candidate metadata into the source register as metadata-only pending-review sources.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add evidence validation reports that compare external candidates against approved RQs, claims, novelty ledger entries, and current source gaps.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add local reproducibility files for every external search run: thresholds, raw response snapshot, scored candidates, skipped results, no-result or low-result queries, and query validation output.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add import of legacy params files so curated query groups like RQ1/RQ2/RQ3 can seed `researchboss search plan`.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add query strategy modes: broad, balanced, and strict, with deterministic term expansion and saved strategy metadata.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add query group labels and RQ links so each external search query can be tied to one or more approved research questions.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add batch search run summaries that aggregate processed, candidate, filtered, skipped, duplicate, no-result, and low-result counts across many queries.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add deterministic auto-refine planning that produces broader follow-up queries only as a saved plan, requiring explicit user approval before execution.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add query exhaustion protection that stops refinement after configured query, page, result, and time budgets.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add filtered-candidate logs that record exactly why a paper failed thresholds, such as year, citation count, document type, source type, missing DOI, or duplicate EID.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add high-signal candidate reports sorted by quality score, RQ coverage, citation count, recency, open-access flag, and metadata completeness.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add candidate deduplication across Scopus runs, local Zotero metadata, source register entries, DOI, EID, title, and year.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add external-search run comparison reports showing which query strategies produced the strongest accepted candidate yield.
- [ ] <span style="color: #ef6c00; font-weight: 600;">Add</span> optional AI-assisted query generation and query refinement from safe context only, gated by both `--ai` and `--external-search`.
- [ ] <span style="color: #ef6c00; font-weight: 600;">Add</span> optional AI-assisted paper relevance, research-question validation, idea validation, and novelty validation using candidate metadata/abstracts first, with full-text modes only by explicit opt-in.

## Phase 6: FastAPI Local Backend

- [ ] <span style="color: #1565c0; font-weight: 600;">Add</span> a local FastAPI app.
- [ ] <span style="color: #1565c0; font-weight: 600;">Add</span> routes for projects, sources, artefacts, research questions, reports, settings, logs, AI, and novelty.
- [ ] <span style="color: #1565c0; font-weight: 600;">Reuse</span> engine logic rather than duplicating business logic.
- [ ] <span style="color: #1565c0; font-weight: 600;">Add</span> API tests.

## Phase 7: Cross-Platform UI Preparation

- [ ] Document the desktop, web, and mobile UI strategy.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Define a clear API contract in `docs/api/CONTRACT.md`.
- [ ] Add a frontend folder or explicit planned UI structure.
- [ ] Keep UI logic out of the core engine.

## Phase 8: Packaging

- [ ] Add packaging plan.
- [ ] Add PyInstaller or equivalent notes for the Python engine.
- [ ] Add future Flutter desktop packaging notes.
- [ ] Document Windows, macOS, and Linux considerations.
