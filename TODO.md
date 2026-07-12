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
- [x] **Done** - **Deterministic** - derived text snapshots, section maps, paragraph IDs, claim IDs, reference IDs, and citation insertion anchors for each editable document version to support repeatable AI-assisted editing (`researchboss.engine.derived_text`, `researchboss doc derive-text`, `POST /api/v1/doc/derive-text/{version_id}`). Section maps only work for `.md` targets (recovered by matching raw `#`-heading text against extracted paragraphs in order — `extract_text()` already strips markdown heading syntax, and `.txt`/`.docx`/`.pdf` have no structural marker to detect at all, so those get `section_id: None` throughout rather than a guessed section map). Anchors are derived fresh per version, not correlated across versions, but deterministic and stable across repeated calls for the same version. Along the way, found and fixed a real pre-existing bug in `conversion._markdown_to_text`: its heading/blockquote/list-stripping regexes used `\s` (which matches newlines) for leading same-line indentation, letting a match starting at a preceding blank line reach forward across it and silently merge that block into the previous paragraph — fixed to `[ \t]`, with a dedicated regression test.
- [ ] **AI** - structured AI edit sessions as reviewable operations before applying proposed changes to Markdown, TXT, DOCX, or derived editable outputs. The paragraph/sentence anchor infrastructure this needs now exists (item above) — remaining work is entirely the AI opt-in/privacy-boundary design, not anchoring.
- [x] **Done** - **Deterministic** - version-conscious citation application so each citation insertion creates a new document version linked to the evidence sources, confidence report, and references generated for that run.
- [x] **Done** - **Deterministic** - version comparison reports that show how document strengths, weaknesses, unsupported claims, and references changed between two versions.
- [x] **Done** - **Deterministic** - document vault versions, manifests, and SQLite metadata into local backups without copying Zotero-owned originals into the workspace unless explicitly requested.
- [x] **Done** - **Deterministic** - an uploaded-artefact intake path in the document vault for externally created artefacts, storing the original uploaded file, a sanitized renamed vault copy, and the mapping between them without modifying the uploaded file in place (`researchboss doc upload/uploads`, `vault.intake_uploaded_artefact`).
- [x] **Done** - **Deterministic** - deterministic renamed-copy generation for uploaded artefacts reusing the existing title/author/year/source-id filename-suggestion pattern (moved into shared `researchboss.engine.filenames`), with collision-safe suffixes for the original-copy directory and an embedded upload ID guaranteeing uniqueness for the renamed copy.

## Phase 9: FastAPI Local Backend

- [x] **Done** - **API** - a local FastAPI app (app factory, response envelope, workspace-resolution dependency, error handling, `researchboss serve`) after engine contracts for validation, citation, SQLite sync, and document versioning were tested.
- [x] **Done** - **API** - `GET /health`, `GET/POST /api/v1/projects/*`, and `POST/GET /api/v1/doc/*` document-versioning routes.
- [x] **Done** - **API** - `GET/POST /api/v1/sources/*`, `GET/POST /api/v1/artefacts/*`, and `GET/POST /api/v1/rqs/*` routes.
- [x] **Done** - **API** - `POST /api/v1/conversion/run`, `GET/POST /api/v1/metadata/*`, and `GET/POST /api/v1/data/*` routes.
- [x] **Done** - **API** - `GET/POST /api/v1/claims/*`, `POST /api/v1/artefacts/create`, `GET/POST /api/v1/zotero/*` (read-only local and Web API, workspace-only collection selection), `GET /api/v1/reports/*`, `POST /api/v1/export/evidence`, `GET/POST /api/v1/backup*`, and `POST /api/v1/decisions|terminology|feedback|context/changelog` routes. Every route documented in `docs/api/CONTRACT.md` is now implemented except the disabled Future AI Routes section.
- [x] **Done** - **API** - `POST /api/v1/validation/run`, `POST /api/v1/citations/plan|apply`, `GET/POST /api/v1/guidelines/*`, and `GET/POST /api/v1/db/*` (init/sync/status/rebuild/pending/apply-pending/privacy) routes.
- [ ] **AI** - novelty assessment has no deterministic engine path (`ai_novelty_assessment` is AI-only) — belongs at `POST /api/v1/ai/novelty`, not a separate `/api/v1/novelty` route implying a deterministic path that doesn't exist. The request/response shape and side-effect (novelty-ledger append) are now sketched in `docs/api/CONTRACT.md`'s Future AI Routes section; still not implemented — needs the actual AI opt-in/cost-awareness/privacy-boundary decision and tests before it can be built and registered.
- [x] **Done** - **API** - API implementation that reuses engine logic rather than duplicating business logic.
- [x] **Done** - **API** - API route tests proving workspace-scoped writes and no original-file modification for the routes built so far; no-Zotero-write, no-secret-logging, and explicit-AI-opt-in boundary tests remain as those route groups are added.
- [x] **Done** - **API** - Add `POST /api/v1/artefacts/upload` for batch artefact uploads, reusing `vault.intake_uploaded_artefact_batch` rather than duplicating upload handling in the API layer. Streams each file to a bounded-size temp location (never buffers a whole oversized upload in memory) before handing local paths to the same engine function the CLI's `doc upload` uses.
- [x] **Done** - **API** - Add configurable batch-upload limits (`RESEARCHBOSS_UPLOAD_MAX_FILES` default 25, `RESEARCHBOSS_UPLOAD_MAX_FILE_SIZE_MB` default 50, allowed extensions reused from `sources.ALLOWED_EXTENSIONS`) with a `400 upload_batch_too_large` rejection for the whole batch when the file-count limit is exceeded, rather than silently truncating it.
- [x] **Done** - **API** - Add a per-batch upload report (`processed`/`accepted`/`duplicate`/`rejected`/`failed` counts plus per-file rows) persisted to `outputs/validation/upload-batch-report.yaml`, mirroring the existing source review report pattern. Duplicate detection is by content hash against artefacts already uploaded in the workspace.
- [x] **Done** - **API** - Add `GET /api/v1/artefacts/cross-reference` to return proposed links between an uploaded artefact and existing artefacts, sources, or claims, based on deterministic title/filename/keyword overlap (`researchboss.engine.cross_reference`), without writing any links. Never modifies an artefact, source, or claim record — only persists a candidate report.
- [x] **Done** - **API** - Add `POST /api/v1/artefacts/cross-reference/apply` to write reviewed artefact cross-reference links. Resolved the open design question: links are written as metadata on the *upload* record (a `cross_references` list, mirroring how artefacts already track `linked_sources`), not inserted into any artefact/source/claim document's content — chosen because a keyword-overlap match is weaker evidence than a validated missing-citation match, so auto-inserting text on that basis would be a worse default than recording it as reviewable metadata. Only candidates hand-edited to `review_status: accepted`/`approved` in the persisted report are applied, mirroring citation plans; re-applying is idempotent (deduplicated by target).
- [x] **Done** - **Deterministic** - Add `researchboss doc cross-reference <upload_id>` and `researchboss doc cross-reference-apply <upload_id>` CLI commands. Found via a full API-route/CLI-command parity audit: `engine.cross_reference`'s deterministic candidate/apply functions had API routes but no CLI equivalent (the only CLI command matching "cross-reference" was an unrelated older `--ai`-gated command). Verified end-to-end with a live CLI smoke test (upload an artefact, register a matching artefact, generate candidates, hand-edit `review_status` to `accepted`, apply, confirm the link lands in `document-vault.yaml`) plus unknown-`upload_id` error-path checks.
- [ ] **AI** - Add optional AI-assisted cross-reference suggestions between uploaded artefacts and existing artefacts, methodology documents, and claims from safe context only, gated by `--ai`, proposing additional candidate links for review rather than writing them automatically.
- [x] **Done** - **API** - Add single-user login protection (`RESEARCHBOSS_API_PASSWORD`-configured, expiring in-memory session) guarding every `/api/v1` route except login itself, failing closed with `503 auth_not_configured` rather than allowing unauthenticated access when no password is set.
- [x] **Done** - **API** - Add `POST /api/v1/auth/login` and `POST /api/v1/auth/logout` routes with secure, expiring session handling (cookie or `Authorization: Bearer` token) and no public self-registration route.
- [x] **Done** - **Deterministic** - Add login credential handling that keeps the password, session secrets, and tokens out of git, logs, and the SQLite database, consistent with the existing `OPENAI_API_KEY` non-disclosure rules.
- [x] **Done** - **API** - Add a `GET /health` route with no workspace or auth dependency so NAS deploy/update health checks succeed independently of login state.
- [x] **Done** - **API** - Add a `RESEARCHBOSS_WORKSPACE_ROOT` environment setting so a deployed instance resolves workspaces from a mounted NAS volume path instead of a container-local path. When set, every workspace must resolve inside that root (relative paths joined to it, absolute paths outside it rejected with `400 workspace_outside_root`) rather than accepting any path reachable by the server process; unset, behavior matches today's local-first flexibility.

## Phase 10: Cross-Platform UI Preparation

- [x] **Done** - **API** - a desktop, web, and mobile UI strategy around local workspaces, validation reports, citation review plans, document versions, and guideline management. Decision: FastAPI + Jinja2 server-rendered shell + vanilla JavaScript, no build toolchain, no third-party JS/CSS dependency (no React/Vue/Svelte/Flutter, no Node/npm, no CDN assets) — see `researchboss/web/`. The web UI is a pure client of the already-tested `/api/v1/*` JSON API (session-cookie auth, same as any other client); it has zero engine access of its own. "Desktop"/"mobile" beyond a responsive web page are not separately addressed — out of scope until there's a concrete need, consistent with not designing for hypothetical requirements. `docs/PACKAGING.md`'s conditional Flutter desktop-sidecar section is now moot and should be read as historical.
- [x] **Done** - **API** - Define a clear API contract in `docs/api/CONTRACT.md`.
- [x] **Done** - **API** - a frontend folder or explicit planned UI structure once the backend boundary is stable. `researchboss/web/{app.py,templates/,static/}`, mounted onto the same FastAPI app `researchboss serve` already runs (`mount_web()` in `api/app.py`) — no separate process, port, or deployment step.
- [x] **Done** - **API** - UI architecture guidance that keeps UI logic out of the core engine and routes all workspace mutations through tested engine/API contracts. Enforced structurally, not just by convention: `researchboss/web/app.py` imports only from `researchboss.api.auth` (session-cookie helpers) and Jinja2/Starlette — it has no import path to `researchboss.engine` at all. Every data operation in `static/app.js` is a `fetch()` call to an existing, tested `/api/v1/*` route.
- [x] **Done** - **API** - Add a minimal web UI login page with no public sign-up flow, gating access to workspace data before any other view loads. `GET /login` (public) and `GET /` (session-gated). Gating is server-side, not just client-side: `GET /` reads the session cookie directly and 303-redirects to `/login?next=<url>` before rendering anything if there's no valid session — verified with a live HTTP smoke test and `tests/test_web.py`.
- [x] **Done** - **Deterministic** - Add the MIT license notice, no-warranty statement, and this project's existing developer/contact information (matching the README) to a footer or About page in the web UI. "About / License" footer link opens a modal with the full MIT notice and `pedro@veloso.dev`, sourced verbatim from `LICENSE`/`README.md`.
- [x] **Done** - **API** - Add a web upload view supporting drag-and-drop and multi-select batch selection of externally created artefact files, surfacing batch-size and file-type limits before submission rather than after failure. Added `GET /api/v1/artefacts/upload/limits` (new, server-wide config: max files, max size, allowed extensions) specifically so the UI can display limits before the user picks files, not just react to a 400 after. Drop zone + browse button both call the same `uploadFiles()` path.
- [x] **Done** - **API** - Add a batch-upload progress and results view showing accepted, renamed, duplicate, and rejected files per upload run, linking each entry back to its vault copy and original filename. Renders `POST /api/v1/artefacts/upload`'s existing per-file report (already had everything needed) immediately after each batch.
- [x] **Done** - **API** - Add a popup overlay (modal) file preview for uploaded artefacts supporting PDF, image, text, and Markdown previews, dismissible by escape key, close control, or click-outside, without navigating away from the artefact list. PDF via `<iframe>` (browser-native viewer), images via `<img>` (though `sources.ALLOWED_EXTENSIONS` still has no image extensions, so this path isn't reachable through the upload pipeline yet — noted, not fixed, since expanding that allow-list is a separate scoped decision shared with source scanning), text/Markdown/CSV/JSON fetched and shown in `<pre>`, everything else gets a "no inline preview, open in a new tab" fallback rather than a broken embed. Escape/close-button/click-outside dismissal is shared plumbing (`setupModals()`) reused by every modal in the app, not preview-specific code.
- [x] **Done** - **API** - Add `GET /api/v1/artefacts/uploads` (list previously uploaded artefacts) and `GET /api/v1/artefacts/uploads/{upload_id}/file` (serve an uploaded artefact's renamed vault copy inline for browser preview). Found both missing during a Phase 10 UI-readiness check: every other route returns the JSON envelope, and nothing served raw file bytes at all, which would have blocked the popup preview view regardless of UI framework. New `vault.resolve_uploaded_artefact_file` engine function re-validates the resolved path stays inside `document_vault/` after resolving, so a hand-edited ledger record can't be used to read an arbitrary file off disk. Verified with a live HTTP smoke test (login, upload, list, fetch file, confirm `Content-Disposition: inline` and correct `text/markdown` content-type, confirm 404 for an unknown upload_id).
- [x] **Done** - **API** - Add an overlay review view for proposed cross-reference links and suggested renamed filenames, requiring explicit per-item approval before artefacts are cross-referenced into methodology or other artefact documents. Renders `GET /api/v1/artefacts/cross-reference` candidates with per-candidate Accept/Reject buttons calling `POST .../candidate-review`, and an "Apply accepted links" button calling `POST .../apply` — no filesystem hand-editing anywhere in the flow. "Suggested renamed filenames" review (a distinct idea from cross-reference candidates) was not separately built: the current upload flow doesn't propose alternate filenames for approval, only the deterministic rename `intake_uploaded_artefact` already applies, so there was nothing here to add a review step for.
- [x] **Done** - **API** - Add `POST /api/v1/citations/plan/insertion-review` (and `researchboss cite review` CLI equivalent) to set one citation-plan insertion's review_status via API/CLI, closing the identical hand-edit-then-apply gap flagged in the cross-reference entry above. New `citations.set_citation_plan_insertion_review_status` engine function, keyed by `(sentence_index, source_id)` — the same pair `create_citation_plan` builds each insertion from — so it only touches the one matched insertion. No route-collision risk here (this router has no dynamic-segment routes), but verified the OpenAPI schema and a live HTTP smoke test of the full plan → insertion-review → apply flow anyway, given the collision bug the cross-reference version of this ticket just caught.
- [x] **Done** - **API** - Add `POST /api/v1/artefacts/cross-reference/candidate-review` (and `researchboss doc cross-reference-review` CLI equivalent) to set one cross-reference candidate's review_status via the API/CLI instead of requiring a human to hand-edit the persisted YAML report — the missing piece for a browser-based reviewer, found during the same Phase 10 UI-readiness check as the upload-listing/file-preview routes above. New `cross_reference.set_cross_reference_candidate_review_status` engine function only touches the one matched candidate (by `target_kind`+`target_id`), leaving every sibling candidate's decision untouched. Caught and fixed a real routing bug while building this: the route was initially named `.../cross-reference/review`, which exactly matched the pre-existing `POST /api/v1/artefacts/{artefact_id}/review` path pattern (`artefact_id="cross-reference"`) — since that route registers first, FastAPI validated against the wrong request body and returned an unexpected 422. Found via a live HTTP smoke test, not the unit tests (which used the same in-process TestClient routing and also caught it once written correctly). Renamed to `candidate-review` to avoid the collision outright rather than depend on route registration order. Verified with unit tests (engine + API + CLI) and a live HTTP smoke test of the full candidates → candidate-review → apply flow with zero filesystem hand-editing.
- [x] **Done** - **Deterministic** - Fixed a real circular-import bug found while verifying the new `researchboss/web/` package against a clean `pip install` (not just the source-tree test suite, which never hit it): `researchboss/api/__init__.py` eagerly did `from researchboss.api.app import create_app`, and `api/app.py` imports `researchboss.web.app` (for `mount_web`), which imports `researchboss.api.auth`. If anything imported `researchboss.web.app` *before* `researchboss.api` had been initialized via another path, `researchboss.api.app`'s own import of `web.app` would find it already present in `sys.modules` but only partially executed (not yet past its own `api.auth` import), so `mount_web` wasn't defined yet and the import failed. Every test and smoke script in this repo happened to always import `researchboss.api.app` first, which sidesteps the failing order — masking it entirely until a genuinely fresh `pip install` + import was tried. Fixed by emptying `api/__init__.py`: nothing else in the codebase relied on `from researchboss.api import create_app` (everywhere already used `from researchboss.api.app import create_app`), so the eager re-export was both unused and the actual root cause. Verified by building a real wheel, installing it into a throwaway venv, and importing `researchboss.web.app` as the very first import (the exact failing case) — confirmed fixed, plus `researchboss.api.app`, the CLI entry point, and `researchboss doctor` (now also checking for `jinja2`) all still work from that clean install.
- [x] **Done** - **Deterministic** - Package the new `researchboss/web/` templates and static assets (`.html`/`.js`/`.css`) so they ship in a real `pip install`, not just the source checkout tests run against. `pyproject.toml`'s `[tool.setuptools.packages.find]` only includes `.py` files by default; added `[tool.setuptools.package-data]` for `researchboss.web`. Verified the same way as the circular-import fix above: built a wheel, listed its contents, confirmed `templates/*.html` and `static/*.{js,css}` are actually present, and confirmed a clean-venv install could resolve them at runtime — this is exactly the kind of gap that passes every test in this repo (which run from the source tree) while silently breaking for an actual installed package.

## Phase 11: Packaging

- [x] **Done** - **Deterministic** - a packaging plan that accounts for the CLI, local API, workspace SQLite, document vault files, and optional desktop UI (`docs/PACKAGING.md`).
- [x] **Done** - **Deterministic** - PyInstaller or equivalent packaging notes for the Python engine and local API, including known uvicorn/`python-multipart` hidden-import gotchas and a "verify the actual binary, not just a clean exit code" step (`docs/PACKAGING.md`).
- [x] **Done** - **Deterministic** - future Flutter desktop packaging notes if the cross-platform UI plan keeps Flutter as the preferred shell — written as explicitly conditional on that not-yet-made Phase 10 decision, not a commitment to it (`docs/PACKAGING.md`).
- [x] **Done** - **Deterministic** - Windows, macOS, and Linux considerations for Zotero paths, local file permissions, document conversion, OCR dependencies, SQLite, and backups (`docs/PACKAGING.md`). Found and fixed a real gap while researching this: `zotero_storage_candidates()` had no Linux support at all (returned an empty list); added native and Flatpak default paths. Also found that OCR fallback depends on system-installed `tesseract`/`pdftoppm`, which PyInstaller cannot bundle — documented as an explicit end-user prerequisite rather than left implicit.

## Phase 12: NAS Deployment (research.veloso.dev)

- [x] **Done** - **API** - Add a Dockerfile and `docker-compose.yml` for the ResearchBoss FastAPI backend so `../synology-site-deployer`'s existing `deploy` command can upload and start it as-is, with no changes to that project. No web UI yet to include (Phase 10 not started). The Dockerfile's `pip install .` and exact `CMD` (single-worker `uvicorn`, required since session state is an in-memory dict — see the Dockerfile's own comment) were verified in a genuinely clean venv, serving `/health` successfully; the container build itself was not verified (no Docker available in this environment) — that step is documented as the user's first move in `docs/DEPLOY.md`, not claimed as done.
- [x] **Done** - **API** - Add a persistent NAS volume/bind-mount for the workspace root directory (`docker-compose.yml` bind-mounts `./data/workspaces` to `/data/workspaces`, matching `RESEARCHBOSS_WORKSPACE_ROOT`) so per-research workspace YAML, Markdown, SQLite, and document vault files survive container restarts and image updates, and are never baked into the deployed image.
- [x] **Done** - **Deterministic** - Add NAS deployment setup notes for running `researchboss init` (via `POST /api/v1/projects/init`, already implemented) once per research project against the mounted workspace volume, so each research setup gets its own isolated workspace folder on the NAS (`docs/DEPLOY.md`).
- [ ] **API** - Deploy the ResearchBoss backend and web UI to the NAS as `research.veloso.dev` using `synology-site deploy research.veloso.dev --compose-file ... --port ...` from `../synology-site-deployer`, without modifying that project. Not done: requires real NAS/Cloudflare credentials and infrastructure access this environment does not have — `docs/DEPLOY.md` documents the exact command to run.
- [x] **Done** - **Deterministic** - Add deploy documentation covering the Compose file, required `.env` values, the mounted workspace volume path, login credential setup, and update/rollback steps via `synology-site update research.veloso.dev` (`docs/DEPLOY.md`).
- [ ] **Deterministic** - Confirm the MIT license, no-warranty statement, and developer/contact information stay consistent between this project's README and the publicly reachable `research.veloso.dev` deployment. Blocked on the actual deployment above (item 282) and on Phase 10 producing a page for a human to load — nothing on the API itself is a place for a license notice; see `docs/DEPLOY.md`'s note on this.

## Phase 13: Web UI Shell — Navigation and Workspace Dashboard

Phase 10 shipped a single upload-focused page. Everything below this point is a brainstormed inventory of the rest of the CLI's functionality that has no web UI yet, organized into phases by feature area — not strictly ordered, and not all equally valuable; Phase 13 is genuinely foundational (real navigation has to exist before more views make sense to add), the rest can be tackled in whatever order matches actual need. Each item names the API route it would use if one already exists, or says explicitly that a new route is needed first. None of this is started.

- [ ] **API** - Add a persistent navigation shell (sidebar or tabs) to `researchboss/web/` replacing the current single-view layout, so each feature area below can be its own page/section without every future phase re-inventing navigation.
- [ ] **API** - Add a "Create workspace" view calling `POST /api/v1/projects/init`, so a new workspace can be created from the browser instead of only via `researchboss init`'s interactive CLI wizard.
- [ ] **API** - Add a workspace dashboard view showing `GET /api/v1/projects/status` and `GET /api/v1/projects/health` output (source counts, health check results) as the landing page after loading a workspace.
- [ ] **API** - Add a workspace report view rendering `GET /api/v1/reports/workspace` and `GET /api/v1/reports/timeline` output.
- [ ] **Deterministic** - Persist the last-used workspace path in browser `localStorage` (not server-side session state — every API route already takes an explicit `workspace` param, and that shouldn't change) so returning to `/` doesn't require re-typing the path every time.

## Phase 14: Web UI — Source Management

The source inbox/review workflow (`sources accept/maybe/ignore/note/tag`) is one of the most-used CLI command groups and currently has zero web UI coverage.

- [ ] **API** - Add a source inbox list view (`GET /api/v1/sources`), filterable by `pending_review`/`accepted`/`maybe`/`ignored`.
- [ ] **API** - Add accept/maybe/ignore review actions per source (`POST /api/v1/sources/{source_id}/status`).
- [ ] **API** - Add note and tag editing per source (`POST /api/v1/sources/{source_id}/note`, `POST /api/v1/sources/{source_id}/tags`).
- [ ] **API** - Add a "Scan" action triggering `POST /api/v1/sources/scan` against a configured local folder or Zotero storage path, with the resulting scan summary shown inline.
- [ ] **API** - Add a source review report view (`GET /api/v1/sources/report`).

## Phase 15: Web UI — Artefact Registry and Research Questions

- [ ] **API** - Add an artefact registry list view (`GET /api/v1/artefacts`) — distinct from the existing "uploaded artefacts" table, which only shows document-vault uploads. The full registered-artefact list has no web view at all today.
- [ ] **API** - Add a manual artefact registration form (`POST /api/v1/artefacts`) and a deterministic artefact creation action (`POST /api/v1/artefacts/create`).
- [ ] **API** - Add artefact review-status controls (`POST /api/v1/artefacts/{artefact_id}/review`) and a dependency-check view (`GET /api/v1/artefacts/dependencies`).
- [ ] **API** - Add a research questions view (`GET /api/v1/rqs`) with approve/reject/archive actions (`POST /api/v1/rqs/{rq_id}/approve|reject|archive`) and a readiness-check action (`POST /api/v1/rqs/check`).

## Phase 16: Web UI — Claims and Citation Planning

- [ ] **API** - Add a claims ledger view (`GET /api/v1/claims`) with an add-claim form (`POST /api/v1/claims`), status controls (`POST /api/v1/claims/{claim_id}/status`), and citation-gap (`GET /api/v1/claims/gaps`) and validation (`GET /api/v1/claims/validate`) reports.
- [ ] **API** - Add a citation planning view: create a plan against a document target (`POST /api/v1/citations/plan`), review each proposed insertion (`POST /api/v1/citations/plan/insertion-review` — API and CLI already support this; only the web view is missing), and apply accepted insertions (`POST /api/v1/citations/apply`). This is the citation half of Phase 10's originally-scoped review-overlay work — only the cross-reference half got a web view built.

## Phase 17: Web UI — Guidelines and Project Log

- [ ] **API** - Add a guidelines view (`GET /api/v1/guidelines`) with a registration form (`POST /api/v1/guidelines`), default/precedence configuration (`POST /api/v1/guidelines/defaults`), and a conflict report (`GET /api/v1/guidelines/conflicts`).
- [ ] **API** - Add a project log view combining decisions (`POST /api/v1/decisions`), terminology/glossary entries (`POST /api/v1/terminology`), supervisor/stakeholder feedback (`POST /api/v1/feedback`), and the context changelog (`POST /api/v1/context/changelog`). Note: all four routes are POST-only today with no corresponding GET/list route — a browsable project-log view needs new list routes added first, not just UI work.

## Phase 18: Web UI — Document Vault and Version History

- [ ] **API** - Add a document version history view per artefact/target: list versions (`GET /api/v1/doc/versions`), diff two versions (`GET /api/v1/doc/diff`), compare validation-report-derived strengths/weaknesses (`GET /api/v1/doc/compare`), and restore a version as a new copy (`POST /api/v1/doc/restore`).
- [ ] **API** - Add a "Snapshot this document" action (`POST /api/v1/doc/version`) reachable from the artefact registry view (Phase 15).
- [ ] **API** - Add a derived-text/anchor viewer (`POST /api/v1/doc/derive-text/{version_id}`) for inspecting paragraph/sentence anchors. Lower priority than the rest of this phase — it's mainly prep infrastructure for future AI edit sessions, not a standalone researcher-facing feature yet.

## Phase 19: Web UI — Zotero Integration

- [ ] **API** - Add a Zotero connection/settings view: local storage readiness (`GET /api/v1/zotero/local/collections`), Web API credential test (`GET /api/v1/zotero/api/test`), and Web API collection listing/selection (`GET`/`POST /api/v1/zotero/api/collections[/select]`).
- [ ] **API** - Add local Zotero storage search (`GET /api/v1/zotero/local/search`) as a browsable view.
- [ ] **API** - Add local Zotero collection selection (`researchboss zotero select-collections`/`use-entire-library`) as an API route — currently CLI-only, writing workspace config directly. The Web API variant already has `POST /api/v1/zotero/api/collections/select`; the local-storage variant has no equivalent route yet, so this needs API work before a web view is possible.
- [ ] **Deterministic** - Add API routes (currently none) for the remaining read-only Zotero reporting commands, if/when their web views are prioritized: `metadata-report`, `attachment-health`, `fulltext-report`, `duplicates`, `snapshot`, `export-bibtex`. Lower priority than the rest of this phase — diagnostic/export tools, not core review workflow.

## Phase 20: Web UI — Data Sources, Metadata, Conversion, and Workspace Admin

- [ ] **API** - Add a data sources view: list (`GET /api/v1/data`), status counts (`GET /api/v1/data/status`), and a profile-trigger action (`POST /api/v1/data/profile`).
- [ ] **API** - Add a metadata quality view: extraction (`POST /api/v1/metadata/extract`), validation (`GET /api/v1/metadata/validate`), and duplicate detection (`GET /api/v1/metadata/duplicates`) reports, plus an index-build action (`POST /api/v1/metadata/index`).
- [ ] **API** - Add a conversion status view/action (`POST /api/v1/conversion/run`) showing which sources converted, were skipped, or failed.
- [ ] **API** - Add a backup management view: create a backup (`POST /api/v1/backup`) and inspect an existing backup zip without restoring it (`GET /api/v1/backup/inspect`).
- [ ] **API** - Add a SQLite index admin view: init/sync/rebuild actions (`POST /api/v1/db/init|sync|rebuild`), status (`GET /api/v1/db/status`), pending-change review (`GET /api/v1/db/pending`, `POST /api/v1/db/apply-pending`), and the privacy self-check (`GET /api/v1/db/privacy`). Lower priority than the rest of this phase — a power-user/admin surface, not a typical researcher workflow.

## Phase 21: Web UI — Export and Reporting Tools

- [ ] **API** - Add an evidence export action (`POST /api/v1/export/evidence`) with a download link for the resulting bundle.
- [ ] **API** - Add an accepted-source corpus export action. No API route exists yet for `export-corpus`; needs a new `POST /api/v1/export/corpus` route before a web view is possible.
- [ ] **Deterministic** - Add API routes (currently none) for `merge-pdfs`, `report-schemas`, `ocr-readiness`, `processing-issues`, and `watch` (unregistered-file detection), if/when their web views are prioritized. All are CLI-only today with no corresponding route.

## Phase 22: Web UI — AI-Assisted Features (blocked on the AI opt-in/cost decision)

Every item here mirrors an existing `--ai`-gated CLI command or a Future AI Route sketch (`docs/api/CONTRACT.md`). None of this should be built until the same AI opt-in/cost-awareness/privacy-boundary product decision already deferred elsewhere in this file (novelty assessment, AI edit sessions, AI-assisted cross-reference) is actually made — a web "send this to OpenAI" button is a bigger UX commitment to get right than the CLI's `--ai` flag, not a smaller one, since a browser user can't see the request the way a CLI user reading `--help` output can.

- [ ] **AI** - AI-assisted review, corpus summary, claim-checking, citation-gap recommendations, artefact cross-reference, and source-relevance views (mirroring `researchboss ai review|corpus-summary|claim-check|citation-gaps|artefact-cross-reference|source-relevance`) — CLI/engine functions already exist; each needs both an API route (none of these are in `docs/api/CONTRACT.md` today, only the CLI reaches them) and the same per-request opt-in UX as everything else in this phase.
- [ ] **AI** - Novelty assessment and research-question assessment views, once `POST /api/v1/ai/novelty` and the `rqs/assess` route (currently shape-sketched only in `docs/api/CONTRACT.md`'s Future AI Routes section, not implemented) actually exist.
- [ ] **AI** - AI-assisted citation planning (`cite ai-plan`) and AI edit sessions (Phase 8's still-open item) as web views, once their respective engine/API work is done.

## Phase 23: Web UI — External Search and Abstract Screening (blocked / lower priority)

External search involves real API costs (Scopus) and is already gated behind explicit `--external-search`/`--ai` flags in the CLI; abstract import/screening is a less-used secondary workflow. Both are lower priority than Phases 13-21, and the AI-assisted parts are blocked on the same decision as Phase 22.

- [ ] **Deterministic** - Add API routes (currently none) for deterministic external-search query planning (`search plan`), report regeneration (`search reports`), and reviewed-candidate import (`search import-candidates`), if/when this workflow is prioritized for the web UI.
- [ ] **AI** - AI-assisted query planning and candidate relevance/novelty review (`search ai-query-plan`, `search ai-candidate-review`) — blocked on the AI opt-in decision, same as Phase 22.
- [ ] **Deterministic** - Add an API route (currently none) for `abstracts import`, then a web view for the resulting reviewable candidate register.
- [ ] **AI** - Abstract-screening AI recommendations (`ai abstract-screening`) as a web view, once the import route above exists and the AI opt-in decision is made.
