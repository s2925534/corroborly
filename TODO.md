# TODO

## Status Guide

- **Done** - Completed and already implemented. Completed items keep `Done` and add a second category flag after it.
- **Deterministic** - Local, rule-based, non-AI work that can usually be implemented and tested now.
- **AI** - Requires explicit AI design, opt-in flags, privacy warnings, and tests before implementation.
- **API** - Requires external API, backend API, UI/API contract, or integration-boundary work.

## Phase 1: Engine and CLI Foundation

- [x] **Done** - **Deterministic** - Fix `researchboss/cli.py` indentation errors so the package imports.
- [x] **Done** - **Deterministic** - Import or remove the `ScanResult` annotation in the scan command.
- [x] **Done** - **Deterministic** - Install and verify development dependencies from `pyproject.toml`.
- [x] **Done** - **Deterministic** - Add a `tests/` folder with pytest coverage for workspace initialization.
- [x] **Done** - **Deterministic** - Add tests for source scanning, hashing, duplicate detection, and allowed extensions.
- [x] **Done** - **Deterministic** - Add tests for source status transitions: accepted, ignored, and maybe.
- [x] **Done** - **Deterministic** - Add Typer CLI smoke tests for `init`, `status`, `config validate`, `scan`, and `sources` commands.
- [x] **Done** - **Deterministic** - Validate source status values instead of accepting arbitrary strings.
- [x] **Done** - **Deterministic** - Add `AGENTS.md` with project instructions and development rules.
- [x] **Done** - **Deterministic** - Remove or replace the unused PyCharm sample `main.py`.
- [x] **Done** - **Deterministic** - Decide whether `.idea/` should stay out of source control.
- [x] **Done** - **Deterministic** - Expand README setup, testing, and architecture notes after the CLI is fixed.
- [x] **Done** - **Deterministic** - Add numbered init prompts with retry validation instead of raw Click errors.
- [x] **Done** - **Deterministic** - Capture optional research questions, draft status, and subquestions during init.
- [x] **Done** - **Deterministic** - Capture init setup context: stakeholders, citation style, output type, data expectations, source review default, AI preference, and privacy preference.
- [x] **Done** - **Deterministic** - Print concrete next-step commands after successful init.
- [x] **Done** - **Deterministic** - Resolve omitted `--workspace` interactively across workspace-aware commands.
- [x] **Done** - **Deterministic** - Auto-select a single discovered workspace and remember a default when several workspaces exist.
- [x] **Done** - **Deterministic** - Add `researchboss version`.
- [x] **Done** - **Deterministic** - Add `researchboss doctor` runtime checks and run the same preflight before `researchboss init`.
- [x] **Done** - **Deterministic** - Add coverage for `python -m researchboss`.
- [x] **Done** - **Deterministic** - Mark Phase 1 complete in README roadmap and add a Quick Start.
- [x] **Done** - **Deterministic** - Record `zotero_storage` as the scan provider from workspace config when `--kind` is omitted.
- [x] **Done** - **Deterministic** - Capture Zotero storage item keys and `.zotero-ft-cache` presence during storage scans.
- [x] **Done** - **Deterministic** - Add read-only deterministic Zotero storage keyword search without AI or Zotero API use.
- [x] **Done** - **Deterministic** - Store the Zotero parent root automatically when `storage/` is selected.
- [x] **Done** - **Deterministic** - Add read-only `zotero.sqlite` metadata lookup using immutable SQLite connections.
- [x] **Done** - **Deterministic** - Link Zotero storage files to parent Zotero items.
- [x] **Done** - **Deterministic** - Add offline collection listing from local SQLite.
- [x] **Done** - **Deterministic** - Add selected-collections and entire-library scan modes.
- [x] **Done** - **Deterministic** - Add include/exclude subcollections support.
- [x] **Done** - **Deterministic** - Add local metadata quality checks.
- [x] **Done** - **Deterministic** - Add attachment health checks.
- [x] **Done** - **Deterministic** - Add local full-text cache availability report.
- [x] **Done** - **Deterministic** - Score deterministic Zotero search against local metadata.
- [x] **Done** - **Deterministic** - Add local Zotero metadata snapshots.
- [x] **Done** - **Deterministic** - Enrich source-register entries with Zotero metadata.
- [x] **Done** - **Deterministic** - Add duplicate detection across Zotero metadata.
- [x] **Done** - **Deterministic** - Add conservative offline BibTeX export from local metadata.
- [x] **Done** - **Deterministic** - Validate scan provider values such as `local_folder` and `zotero_storage`.
- [x] **Done** - **Deterministic** - Add a workspace health command for config, folders, source counts, failed conversions, citation gaps, RQ readiness, and unsupported files.
- [x] **Done** - **Deterministic** - Add local backup restore dry-run reporting without restoring files.

## Future Zotero Work

- [x] **Done** - **API** - Add read-only Zotero API collection listing and selection only if needed after offline workflows are stable.
- [x] **Done** - **Deterministic** - Add richer local SQLite coverage for notes, tags, relations, and item links.
- [x] **Done** - **Deterministic** - Add more complete BibTeX item-type and field mapping.

## Phase 2: Conversion and Metadata

- [x] **Done** - **Deterministic** - Add TXT and MD conversion first.
- [x] **Done** - **Deterministic** - Add DOCX conversion.
- [x] **Done** - **Deterministic** - Add PDF conversion with page markers.
- [x] **Done** - **Deterministic** - Add conversion cache keyed by file hash.
- [x] **Done** - **Deterministic** - Add failed conversion handling and conversion statuses.
- [x] **Done** - **Deterministic** - Add DOI detection.
- [x] **Done** - **Deterministic** - Add basic citation metadata extraction without inventing missing metadata.
- [x] **Done** - **Deterministic** - Add deterministic DOI syntax and resolver-link validation to flag malformed or suspicious DOI links without rewriting metadata.
- [x] **Done** - **Deterministic** - Add citation consistency checks for missing DOI, year, title, author, or mismatched DOI URL formats.
- [x] **Done** - **Deterministic** - Add duplicate filename, title, and DOI reports beyond content-hash duplicates.
- [x] **Done** - **Deterministic** - Build a local keyword index over converted text in `sources_text/`.
- [x] **Done** - **Deterministic** - Add tests for all conversion paths.


## Future PDF/Text Processing Learned From `../pdf-merge`

- [x] **Done** - **Deterministic** - Add optional PyMuPDF/PyPDF2-backed PDF extraction for more reliable page text while preserving the current conservative parser as the fallback.
- [x] **Done** - **Deterministic** - Add local OCR readiness checks and an explicit opt-in OCR fallback for scanned PDFs.
- [x] **Done** - **Deterministic** - Add deterministic sidecar metadata parsing for CSL JSON, BibTeX, and RIS files.
- [x] **Done** - **Deterministic** - Add deterministic abstract, keyword, publication-title, year, and author extraction from sidecar files and PDF metadata without filling unknown fields.
- [x] **Done** - **Deterministic** - Add accepted-source text corpus export with per-source headers, source IDs, titles, authors, and separators.
- [x] **Done** - **Deterministic** - Add optional PDF merge artefacts for accepted source PDFs, with library-wide and batch merge modes that never rename or move originals.
- [x] **Done** - **Deterministic** - Add merge manifests and CSV reports that record which source IDs were included, skipped, failed, or batched.
- [x] **Done** - **Deterministic** - Add deterministic filename suggestion helpers based on title, author token, year, and source ID without renaming original files.
- [x] **Done** - **Deterministic** - Add local abstract-folder import and screening for pre-collected abstracts.
- [x] **Done** - **Deterministic** - Add local abstract-file parsing for legacy Scopus abstract text files with fields such as title, authors, publication, year, DOI, cited-by count, abstract, API URL, and Scopus view URL.
- [x] **Done** - **Deterministic** - Add an abstract candidate register that separates imported abstracts into candidate, filtered, not relevant, skipped, and selected-for-review groups without moving or deleting original files.
- [x] **Done** - **Deterministic** - Add accepted-source text corpus export that can write one combined file plus a manifest while preserving individual converted text files.
- [x] **Done** - **Deterministic** - Add PDF merge dry-run and manifest-first mode before generating merged artefact PDFs.
- [x] **Done** - **Deterministic** - Add skipped and failed processing reports for protected PDFs, corrupt PDFs, OCR-needed PDFs, missing metadata, and unsupported formats without moving originals.

## Phase 3: Data and Artefacts

- [x] **Done** - **Deterministic** - Add CSV profiling: rows, columns, missing values, and inferred types.
- [x] **Done** - **Deterministic** - Add SQLite profiling: tables, columns, and row counts where practical.
- [x] **Done** - **Deterministic** - Add JSON source registration and profiling.
- [x] **Done** - **Deterministic** - Add data profile reports under `outputs/data-profiles`.
- [x] **Done** - **Deterministic** - Expand artefact registry records with linked sources and metadata.
- [x] **Done** - **Deterministic** - Add evidence bundle export for accepted source metadata, claims, RQs, artefacts, and data profiles.
- [x] **Done** - **Deterministic** - Add artefact review statuses such as reviewed, needs revision, and accepted.
- [x] **Done** - **Deterministic** - Add artefact dependency checks against existing accepted sources and approved RQs.
- [x] **Done** - **Deterministic** - Add tests for data profiling and artefact registry behavior.

## Phase 4: Research Questions and Stages

- [x] **Done** - **Deterministic** - Add richer research question templates for M.Phil, PhD, Other academic research, Industry research, and Custom.
- [x] **Done** - **Deterministic** - Add M.Phil and PhD stage templates.
- [x] **Done** - **Deterministic** - Add stage statuses.
- [x] **Done** - **Deterministic** - Add research question candidate, approval, rejection, and archive workflows beyond init-time capture.
- [x] **Done** - **Deterministic** - Add deterministic research question readiness checks without claiming novelty or contribution strength.
- [x] **Done** - **Deterministic** - Add warning thresholds without hard limits by default.
- [x] **Done** - **Deterministic** - Add source notes commands for local per-source notes.
- [x] **Done** - **Deterministic** - Add manual source tags for deterministic review categories.
- [x] **Done** - **Deterministic** - Add claim status workflow for supported, needs evidence, rejected, and needs review.
- [x] **Done** - **Deterministic** - Add claim-source validation to ensure claims link only to accepted sources.
- [x] **Done** - **Deterministic** - Add source review reports for pending, accepted, maybe, ignored, duplicates, and failed files.
- [x] **Done** - **Deterministic** - Add decision log commands for structured project decisions.
- [x] **Done** - **Deterministic** - Add terminology glossary commands.
- [x] **Done** - **Deterministic** - Add supervisor or stakeholder feedback commands.
- [x] **Done** - **Deterministic** - Add context changelog commands.
- [x] **Done** - **Deterministic** - Add local timeline report from logs, decisions, scans, conversions, and RQ changes.
- [x] **Done** - **Deterministic** - Add tests for research question and stage workflows.

## Phase 5: Optional OpenAI Features

- [x] **Done** - **AI** - Add `researchboss ai test`.
- [x] **Done** - **AI** - Read `OPENAI_API_KEY` from the environment or local `.env` without printing or logging it.
- [x] **Done** - **AI** - Keep OpenAI disabled unless explicitly requested with `--ai`.
- [x] **Done** - **AI** - Keep Anthropic, Claude, and local LLM providers as future flags only.
- [x] **Done** - **AI** - Add a safe context preview builder that never sends whole PDFs, CSVs, SQLite databases, or original files by default.
- [x] **Done** - **AI** - Add optional AI-assisted review through `researchboss ai review --ai`.
- [x] **Done** - **AI** - Add optional novelty assessment backed by `novelty-ledger.yaml` through `researchboss assess-novelty --ai`.
- [x] **Done** - **AI** - Add AI-assisted research question strength, novelty, field usefulness, and evidence-quality review through `researchboss rqs assess --ai`.
- [x] **Done** - **AI** - Add tests for missing API key behavior, key non-disclosure, explicit `--ai`, and safe-context privacy boundaries.

## Future AI Work That Makes Sense To Implement

- [x] **Done** - **AI** - Add AI corpus summary reports from safe context only through `researchboss ai corpus-summary --ai`.
- [x] **Done** - **AI** - Add AI claim-checking assistance against accepted sources and `claims-ledger.yaml` through `researchboss ai claim-check --ai`.
- [x] **Done** - **AI** - Add AI citation gap recommendations using accepted sources, claims, and research questions through `researchboss ai citation-gaps --ai`.
- [x] **Done** - **AI** - Add AI artefact cross-reference review against in-progress artefacts through `researchboss ai artefact-cross-reference --ai`.
- [x] **Done** - **AI** - Add explicit per-run full-file AI opt-in flags with warning output and tests before any original or converted full document can be sent to an AI provider.
- [x] **Done** - **AI** - Add explicit per-run directory AI opt-in flags with warning output and tests before any folder-level content can be sent to an AI provider.
- [x] **Done** - **AI** - Add AI source relevance recommendations that cite source IDs and never modify source statuses automatically through `researchboss ai source-relevance --ai`.
- [x] **Done** - **AI** - Add AI-assisted screening for locally imported abstracts, writing recommendations only and never changing abstract candidate statuses automatically.

## Future External Search Work After MVP

- [x] **Done** - **API** - Add deterministic search query plan generation from research context and approved RQs through `researchboss search plan`.
- [x] **Done** - **API** - Add search query history so repeated query combinations can be skipped or intentionally rerun.
- [x] **Done** - **API** - Add explicit Scopus integration with `--external-search` opt-in.
- [x] **Done** - **API** - Add API response snapshots and no-results logs for external search reproducibility.
- [x] **Done** - **API** - Add Scopus quality-scoring rules that rank candidate papers by citation count, publication year, source title, document type, open-access status, and identifier completeness without inventing quality.
- [x] **Done** - **API** - Add author-quality signals from available Scopus metadata, such as author IDs and affiliation IDs when the API response provides them.
- [x] **Done** - **API** - Add configurable search thresholds for minimum citation count, publication year range, open-access preference, maximum results per query, and low-result logging.
- [x] **Done** - **API** - Add query validation reports that compare result counts, duplicate rate, threshold pass rate, and topical keyword coverage for each query.
- [x] **Done** - **API** - Add no-result and low-result query logging with retry suggestions, without automatically entering infinite query-generation loops.
- [x] **Done** - **API** - Add deterministic query refinement candidates based on failed query terms and observed candidate metadata.
- [x] **Done** - **API** - Add expanded hard search budgets per run covering API calls, generated queries, refinement rounds, result pages, and elapsed time.
- [x] **Done** - **API** - Add an external-paper candidate register that stores scored Scopus results separately from accepted local sources until reviewed.
- [x] **Done** - **API** - Add full-text availability detection from Scopus metadata, DOI links, and open-access links without downloading or scraping paywalled files.
- [x] **Done** - **Deterministic** - Add local Zotero matching for external candidate full-text availability detection using only workspace metadata, read-only Zotero metadata, DOI, title, year, and storage-key signals.
- [x] **Done** - **Deterministic** - Add reviewed import commands that copy user-approved external candidate metadata into the source register as metadata-only pending-review sources.
- [x] **Done** - **API** - Add evidence validation reports that compare external candidates against approved RQs, claims, novelty ledger entries, and current source gaps.
- [x] **Done** - **API** - Add local reproducibility files for every external search run: thresholds, raw response snapshot, scored candidates, skipped results, no-result or low-result queries, and query validation output.
- [x] **Done** - **API** - Add import of legacy params files so curated query groups like RQ1/RQ2/RQ3 can seed `researchboss search plan`.
- [x] **Done** - **API** - Add query strategy modes: broad, balanced, and strict, with deterministic term expansion and saved strategy metadata.
- [x] **Done** - **API** - Add query group labels and RQ links so each external search query can be tied to one or more approved research questions.
- [x] **Done** - **API** - Add batch search run summaries that aggregate processed, candidate, filtered, skipped, duplicate, no-result, and low-result counts across many queries.
- [x] **Done** - **API** - Add deterministic auto-refine planning that produces broader follow-up queries only as a saved plan, requiring explicit user approval before execution.
- [x] **Done** - **API** - Add query exhaustion protection that stops refinement after configured query, page, result, and time budgets.
- [x] **Done** - **API** - Add filtered-candidate logs that record exactly why a paper failed thresholds, such as year, citation count, document type, source type, missing DOI, or duplicate EID.
- [x] **Done** - **API** - Add high-signal candidate reports sorted by quality score, RQ coverage, citation count, recency, open-access flag, and metadata completeness.
- [x] **Done** - **API** - Add candidate deduplication across Scopus runs, local Zotero metadata, source register entries, DOI, EID, title, and year.
- [x] **Done** - **API** - Add external-search run comparison reports showing which query strategies produced the strongest accepted candidate yield.
- [x] **Done** - **AI** - Add optional AI-assisted query generation and query refinement from safe context only, gated by both `--ai` and `--external-search`.
- [x] **Done** - **AI** - Add optional AI-assisted paper relevance, research-question validation, idea validation, and novelty validation using candidate metadata or abstracts first, with full-text modes requiring explicit per-run opt-in.

## Phase 6: Document Validation, Guidelines, and Citation Assistance

- [x] **Done** - **Deterministic** - Add APA7 as the default project citation style unless the workspace explicitly configures another style.
- [x] **Done** - **Deterministic** - Add document target resolution for future commands such as `researchboss validate <target>`, supporting file paths, artefact IDs, artefact titles, primary output aliases such as `thesis`, `paper`, `report`, `presentation`, and `notes`, and deterministic artefact type names.
- [x] **Done** - **Deterministic** - Add reusable document validation commands that compare a target document against accepted workspace sources, Zotero-derived workspace sources, and explicitly supplied source paths, with `--workspace` remaining optional when a single/default workspace can be resolved.
- [x] **Done** - **AI** - Add explicit full-target-document AI opt-in flags with warning output and tests before any command sends a whole thesis, paper, report, or other target document to an AI provider.
- [x] **Done** - **AI** - Add explicit full-source-document AI opt-in flags with warning output and tests before any command sends whole backing papers, Zotero-derived documents, or user-supplied source files to an AI provider.
- [x] **Done** - **Deterministic** - Add validation reports that show strengths, weaknesses, unsupported claims, weakly supported claims, possible contradictions, missing citations, candidate supporting sources, and human-review checklists.
- [x] **Done** - **Deterministic** - Add evidence confidence with separate claim relevance, source credibility, metadata completeness, recency, citation strength, author signals, publication venue signals, paper type, contradiction risk, and accepted-vs-candidate status.
- [x] **Done** - **Deterministic** - Add confidence scores while preserving unknown metadata as unknown rather than inventing author h-index, journal index, venue quality, source type, or credibility claims.
- [x] **Done** - **API** - Add Scopus author and venue metrics only under explicit `--external-search` budgets, including author IDs, affiliation IDs, h-index where available, source title, CiteScore/SJR/SNIP/quartile where available, and provenance for each metric.
- [x] **Done** - **API** - Add APA7 references sections in validation and external-search reports, separating accepted workspace evidence from not-yet-accepted external candidate sources.
- [x] **Done** - **Deterministic** - Add local or remote guideline files, including TXT, Markdown, DOCX, PDF, HTML files, web page links, and remote PDF links, with snapshots and converted text written only inside the workspace.
- [x] **Done** - **Deterministic** - Add guideline scopes such as validation, citation, structure, style, journal submission rules, thesis rules, supervisor rules, rubric rules, and all-purpose rules.
- [x] **Done** - **Deterministic** - Add guideline defaults and priorities in workspace settings, allowing commands to use default guidelines automatically while supporting `--guidelines`, `--no-default-guidelines`, and guideline precedence.
- [x] **Done** - **AI** - Add safe AI guideline handling that uses extracted guideline excerpts by default and requires explicit full-guidelines opt-in before sending full converted guideline text to AI providers.
- [x] **Done** - **Deterministic** - Add guideline conflicts when APA7, faculty rules, journal rules, supervisor guidance, or other configured guidelines disagree, marking each conflict for human review.
- [x] **Done** - **Deterministic** - Add citation insertion through commands such as `researchboss cite plan <target>`, producing a reviewable citation-insertion plan without editing the original document.
- [x] **Done** - **AI** - Add AI-assisted citation insertion only with explicit target-document opt-in, proposing inline citation locations, linking each insertion to evidence sources, explaining confidence, and writing a local plan for review.
- [x] **Done** - **Deterministic** - Add reviewed citation-plan application through commands such as `researchboss cite apply <target>`, creating revised output files by default, updating inline citations, and updating or appending an APA7 references section.
- [x] **Done** - **Deterministic** - Add direct citation application for editable formats such as Markdown, TXT, and DOCX, while creating editable Markdown derivatives for PDF targets that cannot be safely edited directly.
- [x] **Done** - **Deterministic** - Add citation safety gates so accepted workspace sources are preferred by default and not-yet-accepted external candidate citations require an explicit flag such as `--allow-candidate-citations`.
- [x] **Done** - **Deterministic** - Add citation and validation output schemas, templates, and report guidelines for document-validation reports, citation-insertion plans, evidence-confidence reports, guideline-conflict reports, and APA7 references sections.

## Phase 7: Workspace SQLite Memory, Indexing, and Sync

- [x] **Done** - **Deterministic** - Add an optional local `researchboss.sqlite` database inside each workspace for indexed memory, fast lookup, search history, validation runs, evidence matches, citation plans, guideline registrations, and document version metadata.
- [x] **Done** - **Deterministic** - Add a SQLite sync policy that preserves YAML and Markdown files as the human-readable workspace source of truth while using SQLite as an index, cache, memory layer, and controlled sync layer.
- [x] **Done** - **Deterministic** - Add SQLite initialization, rebuild, status, and sync commands: `researchboss db init`, `researchboss db sync`, `researchboss db status`, and `researchboss db rebuild`.
- [x] **Done** - **Deterministic** - Add sync state with file hashes, last synced timestamps, database revisions, file revisions, dirty flags, and conflict status for every YAML or Markdown workspace file mirrored into SQLite.
- [x] **Done** - **Deterministic** - Add SQLite-to-YAML write-back through reviewed pending-change tables rather than allowing silent database edits to overwrite workspace files.
- [x] **Done** - **Deterministic** - Add pending-change review commands: `researchboss db apply-pending --review` and `researchboss db apply-pending --apply`.
- [x] **Done** - **Deterministic** - Add memory tables for old search queries, successful and weak query patterns, user preferences, guideline decisions, citation decisions, validation notes, claim-to-source links, and previous AI-safe context choices.
- [x] **Done** - **Deterministic** - Add document aliases so names such as `thesis`, `paper`, artefact titles, artefact IDs, and file paths resolve consistently across validation, citation, and versioning commands.
- [x] **Done** - **Deterministic** - Add SQLite FTS indexes over converted source text, artefact text, guideline text, claims, references, and document sections for faster local evidence matching before any AI review.
- [x] **Done** - **Deterministic** - Add migration and repair checks for the workspace SQLite database, including rebuild-from-YAML behavior and corruption-safe recovery that does not destroy source-of-truth files.
- [x] **Done** - **Deterministic** - Add database privacy checks to ensure API keys, full original documents, Zotero-owned files, and opted-out full-text content are not stored in SQLite unintentionally.

## Phase 8: Document Vault, Versioning, and Restoration

- [x] **Done** - **Deterministic** - a local document vault layout for originals, generated documents, derived text, document versions, diffs, manifests, and AI edit sessions without modifying original user files by default.
- [x] **Done** - **Deterministic** - document versions for generated artefacts and user-selected target documents, storing version IDs, parent version IDs, file paths, content hashes, creation reason, source command, model metadata, guideline IDs, validation report IDs, and citation plan IDs.
- [x] **Done** - **Deterministic** - automatic document snapshots before AI citation insertion, AI rewriting, deterministic overwrite, restoration, or any other command that creates a modified document copy.
- [x] **Done** - **Deterministic** - document version commands such as `researchboss doc version`, `researchboss doc versions`, `researchboss doc diff`, and `researchboss doc restore`.
- [x] **Done** - **Deterministic** - restoration behavior that creates a restored copy by default rather than deleting newer versions or overwriting the current document without explicit approval.
- [ ] **Deterministic** - derived text snapshots, section maps, paragraph IDs, claim IDs, reference IDs, and citation insertion anchors for each editable document version to support repeatable AI-assisted editing.
- [ ] **AI** - structured AI edit sessions as reviewable operations before applying proposed changes to Markdown, TXT, DOCX, or derived editable outputs.
- [x] **Done** - **Deterministic** - version-conscious citation application so each citation insertion creates a new document version linked to the evidence sources, confidence report, and references generated for that run.
- [x] **Done** - **Deterministic** - version comparison reports that show how document strengths, weaknesses, unsupported claims, and references changed between two versions.
- [x] **Done** - **Deterministic** - document vault versions, manifests, and SQLite metadata into local backups without copying Zotero-owned originals into the workspace unless explicitly requested.
- [ ] **Deterministic** - an uploaded-artefact intake path in the document vault for externally created artefacts, storing the original uploaded file, a sanitized renamed vault copy, and the mapping between them without modifying the uploaded file in place.
- [ ] **Deterministic** - deterministic renamed-copy generation for uploaded artefacts reusing the existing title/author/year/source-id filename-suggestion pattern, with collision-safe suffixes when two uploads would otherwise produce the same name.

## Phase 9: FastAPI Local Backend

- [x] **Done** - **API** - a local FastAPI app (app factory, response envelope, workspace-resolution dependency, error handling, `researchboss serve`) after engine contracts for validation, citation, SQLite sync, and document versioning were tested.
- [x] **Done** - **API** - `GET /health`, `GET/POST /api/v1/projects/*`, and `POST/GET /api/v1/doc/*` document-versioning routes.
- [x] **Done** - **API** - `GET/POST /api/v1/sources/*`, `GET/POST /api/v1/artefacts/*`, and `GET/POST /api/v1/rqs/*` routes.
- [x] **Done** - **API** - `POST /api/v1/conversion/run`, `GET/POST /api/v1/metadata/*`, and `GET/POST /api/v1/data/*` routes.
- [x] **Done** - **API** - `GET/POST /api/v1/claims/*`, `POST /api/v1/artefacts/create`, `GET/POST /api/v1/zotero/*` (read-only local and Web API, workspace-only collection selection), `GET /api/v1/reports/*`, `POST /api/v1/export/evidence`, `GET/POST /api/v1/backup*`, and `POST /api/v1/decisions|terminology|feedback|context/changelog` routes. Every route documented in `docs/api/CONTRACT.md` is now implemented except the disabled Future AI Routes section.
- [x] **Done** - **API** - `POST /api/v1/validation/run`, `POST /api/v1/citations/plan|apply`, `GET/POST /api/v1/guidelines/*`, and `GET/POST /api/v1/db/*` (init/sync/status/rebuild/pending/apply-pending/privacy) routes.
- [ ] **AI** - novelty assessment has no deterministic engine path (`ai_novelty_assessment` is AI-only) — a `/api/v1/novelty` route needs the same explicit AI opt-in, cost-awareness, and privacy-boundary rules as other AI routes, not just a contract addition.
- [x] **Done** - **API** - API implementation that reuses engine logic rather than duplicating business logic.
- [x] **Done** - **API** - API route tests proving workspace-scoped writes and no original-file modification for the routes built so far; no-Zotero-write, no-secret-logging, and explicit-AI-opt-in boundary tests remain as those route groups are added.
- [ ] **API** - Add `POST /api/v1/artefacts/upload` for batch artefact uploads, reusing document-vault and artefact-registration engine logic rather than duplicating upload handling in the API layer.
- [ ] **API** - Add configurable batch-upload limits (max files per batch, max file size, allowed extensions reused from source scanning) with a clear rejection response when a batch exceeds limits, rather than silently truncating it.
- [ ] **API** - Add a per-batch upload report (accepted, renamed, duplicate, rejected, failed) mirroring the existing source review report pattern.
- [ ] **API** - Add `GET /api/v1/artefacts/cross-reference` to return proposed links between an uploaded artefact and existing artefacts, methodology documents, sources, or claims, based on deterministic filename, title, source ID, and keyword matches, without writing the links until reviewed.
- [ ] **API** - Add `POST /api/v1/artefacts/cross-reference/apply` to write reviewed artefact cross-reference links into methodology or other artefact documents, following the same review-before-apply pattern used for citation plans.
- [ ] **AI** - Add optional AI-assisted cross-reference suggestions between uploaded artefacts and existing artefacts, methodology documents, and claims from safe context only, gated by `--ai`, proposing additional candidate links for review rather than writing them automatically.
- [x] **Done** - **API** - Add single-user login protection (`RESEARCHBOSS_API_PASSWORD`-configured, expiring in-memory session) guarding every `/api/v1` route except login itself, failing closed with `503 auth_not_configured` rather than allowing unauthenticated access when no password is set.
- [x] **Done** - **API** - Add `POST /api/v1/auth/login` and `POST /api/v1/auth/logout` routes with secure, expiring session handling (cookie or `Authorization: Bearer` token) and no public self-registration route.
- [x] **Done** - **Deterministic** - Add login credential handling that keeps the password, session secrets, and tokens out of git, logs, and the SQLite database, consistent with the existing `OPENAI_API_KEY` non-disclosure rules.
- [x] **Done** - **API** - Add a `GET /health` route with no workspace or auth dependency so NAS deploy/update health checks succeed independently of login state.
- [ ] **API** - Add a `RESEARCHBOSS_WORKSPACE_ROOT` environment setting so a deployed instance resolves workspaces from a mounted NAS volume path instead of a container-local path, preserving workspace-scoped rules in the deployed environment.

## Phase 10: Cross-Platform UI Preparation

- [ ] **API** - a desktop, web, and mobile UI strategy around local workspaces, validation reports, citation review plans, document versions, and guideline management.
- [x] **Done** - **API** - Define a clear API contract in `docs/api/CONTRACT.md`.
- [ ] **API** - a frontend folder or explicit planned UI structure once the backend boundary is stable.
- [ ] **API** - UI architecture guidance that keeps UI logic out of the core engine and routes all workspace mutations through tested engine/API contracts.
- [ ] **API** - Add a minimal web UI login page with no public sign-up flow, gating access to workspace data before any other view loads.
- [ ] **Deterministic** - Add the MIT license notice, no-warranty statement, and this project's existing developer/contact information (matching the README) to a footer or About page in the web UI.
- [ ] **API** - Add a web upload view supporting drag-and-drop and multi-select batch selection of externally created artefact files, surfacing batch-size and file-type limits before submission rather than after failure.
- [ ] **API** - Add a batch-upload progress and results view showing accepted, renamed, duplicate, and rejected files per upload run, linking each entry back to its vault copy and original filename.
- [ ] **API** - Add a popup overlay (modal) file preview for uploaded artefacts supporting PDF, image, text, and Markdown previews, dismissible by escape key, close control, or click-outside, without navigating away from the artefact list.
- [ ] **API** - Add an overlay review view for proposed cross-reference links and suggested renamed filenames, requiring explicit per-item approval before artefacts are cross-referenced into methodology or other artefact documents.

## Phase 11: Packaging

- [ ] **Deterministic** - a packaging plan that accounts for the CLI, local API, workspace SQLite, document vault files, and optional desktop UI.
- [ ] **Deterministic** - PyInstaller or equivalent packaging notes for the Python engine and local API.
- [ ] **Deterministic** - future Flutter desktop packaging notes if the cross-platform UI plan keeps Flutter as the preferred shell.
- [ ] **Deterministic** - Windows, macOS, and Linux considerations for Zotero paths, local file permissions, document conversion, OCR dependencies, SQLite, and backups.

## Phase 12: NAS Deployment (research.veloso.dev)

- [ ] **API** - Add a Dockerfile and `docker-compose.yml` for the ResearchBoss FastAPI backend and web UI so `../synology-site-deployer`'s existing `deploy` command can upload and start it as-is, with no changes to that project's functionality.
- [ ] **API** - Add a persistent NAS volume/bind-mount for the workspace root directory so per-research workspace YAML, Markdown, SQLite, and document vault files survive container restarts and image updates, and are never baked into the deployed image.
- [ ] **Deterministic** - Add NAS deployment setup notes for running `researchboss init` (or its future API equivalent) once per research project against the mounted workspace volume, so each research setup gets its own isolated workspace folder on the NAS, matching the project's existing per-workspace scoping rules.
- [ ] **API** - Deploy the ResearchBoss backend and web UI to the NAS as `research.veloso.dev` using `synology-site deploy research.veloso.dev --compose-file ... --port ...` from `../synology-site-deployer`, without modifying that project.
- [ ] **Deterministic** - Add deploy documentation covering the Compose file, required `.env` values, the mounted workspace volume path, login credential setup, and update/rollback steps via `synology-site update research.veloso.dev`.
- [ ] **Deterministic** - Confirm the MIT license, no-warranty statement, and developer/contact information stay consistent between this project's README and the publicly reachable `research.veloso.dev` deployment.
