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

- [ ] <span style="color: #00897b; font-weight: 600;">Add</span> optional PyMuPDF/PyPDF2-backed PDF extraction for more reliable page text while preserving the current conservative parser as the fallback.
- [ ] <span style="color: #00897b; font-weight: 600;">Add</span> local OCR readiness checks and an explicit opt-in OCR fallback for scanned PDFs.
- [ ] <span style="color: #00897b; font-weight: 600;">Add</span> deterministic sidecar metadata parsing for CSL JSON, BibTeX, and RIS files.
- [ ] <span style="color: #00897b; font-weight: 600;">Add</span> deterministic abstract, keyword, publication-title, year, and author extraction from sidecar files and PDF metadata without filling unknown fields.
- [ ] <span style="color: #00897b; font-weight: 600;">Add</span> accepted-source text corpus export with per-source headers, source IDs, titles, authors, and separators.
- [ ] <span style="color: #00897b; font-weight: 600;">Add</span> optional PDF merge artefacts for accepted source PDFs, with library-wide and batch merge modes that never rename or move originals.
- [ ] <span style="color: #00897b; font-weight: 600;">Add</span> merge manifests and CSV reports that record which source IDs were included, skipped, failed, or batched.
- [ ] <span style="color: #00897b; font-weight: 600;">Add</span> deterministic filename suggestion helpers based on title, author token, year, and source ID without renaming original files.
- [ ] <span style="color: #00897b; font-weight: 600;">Add</span> local abstract-folder import and screening for pre-collected abstracts.
- [ ] <span style="color: #00897b; font-weight: 600;">Add</span> local abstract-file parsing for legacy Scopus abstract text files with fields such as title, authors, publication, year, DOI, cited-by count, abstract, API URL, and Scopus view URL.
- [ ] <span style="color: #00897b; font-weight: 600;">Add</span> an abstract candidate register that separates imported abstracts into candidate, filtered, not relevant, skipped, and selected-for-review groups without moving or deleting original files.
- [ ] <span style="color: #00897b; font-weight: 600;">Add</span> accepted-source text corpus export that can write one combined file plus a manifest while preserving individual converted text files.
- [ ] <span style="color: #00897b; font-weight: 600;">Add</span> PDF merge dry-run and manifest-first mode before generating merged artefact PDFs.
- [ ] <span style="color: #00897b; font-weight: 600;">Add</span> skipped and failed processing reports for protected PDFs, corrupt PDFs, OCR-needed PDFs, missing metadata, and unsupported formats without moving originals.

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
- [ ] <span style="color: #ef6c00; font-weight: 600;">Add</span> explicit per-run full-file AI opt-in flags with warning output and tests before any original or converted full document can be sent to an AI provider.
- [ ] <span style="color: #ef6c00; font-weight: 600;">Add</span> explicit per-run directory AI opt-in flags with warning output and tests before any folder-level content can be sent to an AI provider.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add AI source relevance recommendations that cite source IDs and never modify source statuses automatically through `researchboss ai source-relevance --ai`.
- [ ] <span style="color: #ef6c00; font-weight: 600;">Add</span> AI-assisted screening for locally imported abstracts, writing recommendations only and never changing abstract candidate statuses automatically.

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
- [ ] <span style="color: #00897b; font-weight: 600;">Add</span> local Zotero matching for external candidate full-text availability detection using only workspace metadata, read-only Zotero metadata, DOI, title, year, and storage-key signals.
- [ ] <span style="color: #00897b; font-weight: 600;">Add</span> reviewed import commands that copy user-approved external candidate metadata into the source register as metadata-only pending-review sources.
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
- [ ] <span style="color: #ef6c00; font-weight: 600;">Add</span> optional AI-assisted paper relevance, research-question validation, idea validation, and novelty validation using candidate metadata or abstracts first, with full-text modes requiring explicit per-run opt-in.

## Phase 6: Document Validation, Guidelines, and Citation Assistance

- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add APA7 as the default project citation style unless the workspace explicitly configures another style.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Add document target resolution for future commands such as `researchboss validate <target>`, supporting file paths, artefact IDs, artefact titles, primary output aliases such as `thesis`, `paper`, `report`, `presentation`, and `notes`, and deterministic artefact type names.
- [ ] <span style="color: #00897b; font-weight: 600;">Add</span> reusable document validation commands that compare a target document against accepted workspace sources, Zotero-derived workspace sources, and explicitly supplied source paths, with `--workspace` remaining optional when a single/default workspace can be resolved.
- [ ] <span style="color: #ef6c00; font-weight: 600;">Add</span> explicit full-target-document AI opt-in flags with warning output and tests before any command sends a whole thesis, paper, report, or other target document to an AI provider.
- [ ] <span style="color: #ef6c00; font-weight: 600;">Add</span> explicit full-source-document AI opt-in flags with warning output and tests before any command sends whole backing papers, Zotero-derived documents, or user-supplied source files to an AI provider.
- [ ] <span style="color: #00897b; font-weight: 600;">Add</span> validation reports that show strengths, weaknesses, unsupported claims, weakly supported claims, possible contradictions, missing citations, candidate supporting sources, and human-review checklists.
- [ ] <span style="color: #00897b; font-weight: 600;">Add</span> evidence confidence with separate claim relevance, source credibility, metadata completeness, recency, citation strength, author signals, publication venue signals, paper type, contradiction risk, and accepted-vs-candidate status.
- [ ] <span style="color: #00897b; font-weight: 600;">Add</span> confidence scores while preserving unknown metadata as unknown rather than inventing author h-index, journal index, venue quality, source type, or credibility claims.
- [ ] <span style="color: #1565c0; font-weight: 600;">Add</span> Scopus author and venue metrics only under explicit `--external-search` budgets, including author IDs, affiliation IDs, h-index where available, source title, CiteScore/SJR/SNIP/quartile where available, and provenance for each metric.
- [ ] <span style="color: #00897b; font-weight: 600;">Add</span> APA7 references sections in validation and external-search reports, separating accepted workspace evidence from not-yet-accepted external candidate sources.
- [ ] <span style="color: #00897b; font-weight: 600;">Add</span> local or remote guideline files, including TXT, Markdown, DOCX, PDF, HTML files, web page links, and remote PDF links, with snapshots and converted text written only inside the workspace.
- [ ] <span style="color: #00897b; font-weight: 600;">Add</span> guideline scopes such as validation, citation, structure, style, journal submission rules, thesis rules, supervisor rules, rubric rules, and all-purpose rules.
- [ ] <span style="color: #00897b; font-weight: 600;">Add</span> guideline defaults and priorities in workspace settings, allowing commands to use default guidelines automatically while supporting `--guidelines`, `--no-default-guidelines`, and guideline precedence.
- [ ] <span style="color: #ef6c00; font-weight: 600;">Add</span> safe AI guideline handling that uses extracted guideline excerpts by default and requires explicit full-guidelines opt-in before sending full converted guideline text to AI providers.
- [ ] <span style="color: #00897b; font-weight: 600;">Add</span> guideline conflicts when APA7, faculty rules, journal rules, supervisor guidance, or other configured guidelines disagree, marking each conflict for human review.
- [ ] <span style="color: #00897b; font-weight: 600;">Add</span> citation insertion through commands such as `researchboss cite plan <target>`, producing a reviewable citation-insertion plan without editing the original document.
- [ ] <span style="color: #ef6c00; font-weight: 600;">Add</span> AI-assisted citation insertion only with explicit target-document opt-in, proposing inline citation locations, linking each insertion to evidence sources, explaining confidence, and writing a local plan for review.
- [ ] <span style="color: #00897b; font-weight: 600;">Add</span> reviewed citation-plan application through commands such as `researchboss cite apply <target>`, creating revised output files by default, updating inline citations, and updating or appending an APA7 references section.
- [ ] <span style="color: #00897b; font-weight: 600;">Add</span> direct citation application for editable formats such as Markdown, TXT, DOCX, and later ODT, RTF, and LaTeX, while creating editable derivatives such as DOCX or Markdown for PDF, scanned PDF, Pages, or other formats that cannot be safely edited directly.
- [ ] <span style="color: #00897b; font-weight: 600;">Add</span> citation safety gates so accepted workspace sources are preferred by default and not-yet-accepted external candidate citations require an explicit flag such as `--allow-candidate-citations`.
- [ ] <span style="color: #00897b; font-weight: 600;">Add</span> citation and validation output schemas, templates, and report guidelines for document-validation reports, citation-insertion plans, evidence-confidence reports, guideline-conflict reports, and APA7 references sections.

## Phase 7: Workspace SQLite Memory, Indexing, and Sync

- [ ] <span style="color: #00897b; font-weight: 600;">Add</span> an optional local `researchboss.sqlite` database inside each workspace for indexed memory, fast lookup, search history, validation runs, evidence matches, citation plans, guideline registrations, and document version metadata.
- [ ] <span style="color: #00897b; font-weight: 600;">Add</span> a SQLite sync policy that preserves YAML and Markdown files as the human-readable workspace source of truth while using SQLite as an index, cache, memory layer, and controlled sync layer.
- [ ] <span style="color: #00897b; font-weight: 600;">Add</span> SQLite initialization, rebuild, status, and sync commands such as `researchboss db init`, `researchboss db sync`, `researchboss db status`, and `researchboss db rebuild`.
- [ ] <span style="color: #00897b; font-weight: 600;">Add</span> sync state with file hashes, last synced timestamps, database revisions, file revisions, dirty flags, and conflict status for every YAML or Markdown workspace file mirrored into SQLite.
- [ ] <span style="color: #00897b; font-weight: 600;">Add</span> SQLite-to-YAML write-back through reviewed pending-change tables rather than allowing silent database edits to overwrite workspace files.
- [ ] <span style="color: #00897b; font-weight: 600;">Add</span> pending-change review commands such as `researchboss db apply-pending --review` and `researchboss db apply-pending --apply`.
- [ ] <span style="color: #00897b; font-weight: 600;">Add</span> memory tables for old search queries, successful and weak query patterns, user preferences, guideline decisions, citation decisions, validation notes, claim-to-source links, and previous AI-safe context choices.
- [ ] <span style="color: #00897b; font-weight: 600;">Add</span> document aliases so names such as `thesis`, `chapter 1`, `paper draft`, artefact titles, and file paths resolve consistently across validation, citation, and versioning commands.
- [ ] <span style="color: #00897b; font-weight: 600;">Add</span> SQLite FTS indexes over converted source text, artefact text, guideline text, claims, references, and document sections for faster local evidence matching before any AI review.
- [ ] <span style="color: #00897b; font-weight: 600;">Add</span> migration and repair checks for the workspace SQLite database, including rebuild-from-YAML behavior and corruption-safe recovery that does not destroy source-of-truth files.
- [ ] <span style="color: #00897b; font-weight: 600;">Add</span> database privacy checks to ensure API keys, full original documents, Zotero-owned files, and opted-out full-text content are not stored in SQLite unintentionally.

## Phase 8: Document Vault, Versioning, and Restoration

- [ ] <span style="color: #00897b; font-weight: 600;">Add</span> a local document vault layout for originals, generated documents, derived text, document versions, diffs, manifests, and AI edit sessions without modifying original user files by default.
- [ ] <span style="color: #00897b; font-weight: 600;">Add</span> document versions for generated artefacts and user-selected target documents, storing version IDs, parent version IDs, file paths, content hashes, creation reason, source command, model metadata, guideline IDs, validation report IDs, and citation plan IDs.
- [ ] <span style="color: #00897b; font-weight: 600;">Add</span> automatic document snapshots before AI citation insertion, AI rewriting, deterministic overwrite, restoration, or any other command that creates a modified document copy.
- [ ] <span style="color: #00897b; font-weight: 600;">Add</span> document version commands such as `researchboss doc version`, `researchboss doc versions`, `researchboss doc diff`, and `researchboss doc restore`.
- [ ] <span style="color: #00897b; font-weight: 600;">Add</span> restoration behavior that creates a restored copy by default rather than deleting newer versions or overwriting the current document without explicit approval.
- [ ] <span style="color: #00897b; font-weight: 600;">Add</span> derived text snapshots, section maps, paragraph IDs, claim IDs, reference IDs, and citation insertion anchors for each editable document version to support repeatable AI-assisted editing.
- [ ] <span style="color: #ef6c00; font-weight: 600;">Add</span> structured AI edit sessions as reviewable operations before applying proposed changes to Markdown, TXT, DOCX, or derived editable outputs.
- [ ] <span style="color: #00897b; font-weight: 600;">Add</span> version-conscious citation application so each citation insertion creates a new document version linked to the evidence sources, confidence report, and references generated for that run.
- [ ] <span style="color: #00897b; font-weight: 600;">Add</span> version comparison reports that show how document strengths, weaknesses, unsupported claims, and references changed between two versions.
- [ ] <span style="color: #00897b; font-weight: 600;">Add</span> document vault versions, manifests, and SQLite metadata into local backups without copying Zotero-owned originals into the workspace unless explicitly requested.

## Phase 9: FastAPI Local Backend

- [ ] <span style="color: #1565c0; font-weight: 600;">Add</span> a local FastAPI app after engine contracts for validation, citation, SQLite sync, and document versioning are tested.
- [ ] <span style="color: #1565c0; font-weight: 600;">Add</span> routes for projects, sources, artefacts, research questions, reports, settings, logs, AI, novelty, validation, citation plans, guidelines, SQLite sync status, and document versions.
- [ ] <span style="color: #1565c0; font-weight: 600;">Add</span> API implementation that reuses engine logic rather than duplicating business logic.
- [ ] <span style="color: #1565c0; font-weight: 600;">Add</span> API route tests that preserve local-first, no-Zotero-write, no-secret-logging, and explicit-AI-opt-in boundaries.

## Phase 10: Cross-Platform UI Preparation

- [ ] <span style="color: #1565c0; font-weight: 600;">Add</span> a desktop, web, and mobile UI strategy around local workspaces, validation reports, citation review plans, document versions, and guideline management.
- [x] <span style="color: #2e7d32; font-weight: 600;">Done</span> - Define a clear API contract in `docs/api/CONTRACT.md`.
- [ ] <span style="color: #1565c0; font-weight: 600;">Add</span> a frontend folder or explicit planned UI structure once the backend boundary is stable.
- [ ] <span style="color: #1565c0; font-weight: 600;">Add</span> UI architecture guidance that keeps UI logic out of the core engine and routes all workspace mutations through tested engine/API contracts.

## Phase 11: Packaging

- [ ] <span style="color: #00897b; font-weight: 600;">Add</span> a packaging plan that accounts for the CLI, local API, workspace SQLite, document vault files, and optional desktop UI.
- [ ] <span style="color: #00897b; font-weight: 600;">Add</span> PyInstaller or equivalent packaging notes for the Python engine and local API.
- [ ] <span style="color: #00897b; font-weight: 600;">Add</span> future Flutter desktop packaging notes if the cross-platform UI plan keeps Flutter as the preferred shell.
- [ ] <span style="color: #00897b; font-weight: 600;">Add</span> Windows, macOS, and Linux considerations for Zotero paths, local file permissions, document conversion, OCR dependencies, SQLite, and backups.
