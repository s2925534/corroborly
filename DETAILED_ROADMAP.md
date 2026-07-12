# ResearchBoss Detailed Roadmap

Project version: 0.5.4

Last updated: 2026-07-04

This roadmap tracks implementation progress for ResearchBoss. Update this file whenever development changes feature status, project scope, version, or recommended next steps.

## 1. Executive Summary

ResearchBoss is currently past the local deterministic Phase 2-6 foundation for core workspace, source, artefact, external-search, document-validation, and guideline-registration workflows. SQLite memory, document vault/versioning, FastAPI, UI, and packaging remain future phases.

Implemented:

- Python package structure.
- Typer CLI foundation.
- Local workspace initialization.
- Local YAML and Markdown workspace state files.
- Source folder scanning.
- Read-only local Zotero storage scanning.
- Read-only local Zotero SQLite metadata lookup.
- Offline Zotero collection listing and selected-collection scan modes.
- Optional read-only Zotero Web API credential test, collection listing, and selected-collection configuration.
- Offline Zotero notes, tags, relations, linked-item metadata, and richer BibTeX mapping.
- Deterministic local Zotero search over filenames, `.zotero-ft-cache`, and local SQLite metadata.
- Offline Zotero metadata reports, attachment health checks, full-text cache reports, metadata snapshots, duplicate checks, and BibTeX export.
- Source hashing and duplicate detection.
- TXT, MD, DOCX, and page-marked PDF conversion.
- Conversion cache and failed conversion records.
- Deterministic citation metadata extraction.
- DOI validation, citation consistency reports, metadata duplicate reports, and converted-text keyword indexing.
- CSV, SQLite, and JSON data profiling.
- Artefact registry with linked sources, linked research questions, review flags, and AI flags.
- Deterministic artefact creation for source summaries, literature review matrices, claim-evidence tables, research question briefs, and data profile summaries.
- Artefact review status, artefact dependency validation, and evidence bundle export.
- M.Phil and PhD stage templates.
- Research question templates, list, approve, reject, archive, and deterministic readiness-check workflows.
- Source notes, manual source tags, and source review reports.
- Manual claim ledger, claim statuses, claim-source validation, and citation gap detection.
- Structured decision log, terminology glossary, supervisor/stakeholder feedback, context changelog, and local timeline reports.
- Local Markdown workspace reports.
- One-shot watch reports for unregistered source files.
- Local workspace backups.
- Workspace health reports and backup restore dry-run inspection.
- Config migration and workspace schema versioning.
- Zotero-style citation style wording, including explicit `American Psychological Association 7th edition`.
- Strict one-way Zotero-to-ResearchBoss blocker config that prevents writes inside the local Zotero directory.
- Source review statuses: `pending_review`, `accepted`, `maybe`, `ignored`.
- Workspace discovery, selection, and local default workspace memory.
- JSONL logs and YAML run summaries.
- OpenAI readiness checks through `researchboss ai test`, with live requests requiring explicit `--ai`.
- Safe AI context preview generation that excludes original files, whole documents, whole CSVs, and whole SQLite databases by default.
- AI-assisted review, novelty assessment, and research-question assessment behind explicit `--ai`.
- Document target resolution for file paths, artefact IDs, artefact titles, primary aliases, and deterministic artefact types.
- Deterministic `researchboss validate <target>` reports with source comparison, strengths, weaknesses, unsupported or weakly supported sentences, missing citations, evidence confidence factors, conservative confidence scores, and APA7 references.
- Guideline registration with workspace-local snapshots, extracted text, and validated scopes.
- README, AGENTS.md, architecture notes, TODO, changelog, detailed roadmap, and tests.
- Planned local FastAPI API contract in `docs/api/CONTRACT.md`.

Partially implemented:

- Zotero support: local storage-folder, read-only SQLite support, and read-only Zotero Web API collection listing/selection exist.
- AI setup: OpenAI readiness, safe context preview, AI-assisted review, novelty assessment, and research-question assessment exist.

Not implemented:

- Future explicit full-file/directory AI opt-ins, AI-assisted abstract screening, citation insertion, SQLite memory, document vault/versioning, FastAPI, UI, and packaging.
- Workspace SQLite memory and sync.
- Document vault and versioning.
- FastAPI backend.
- Cross-platform UI.
- Packaging.

Current repository state: coherent and test-covered for local deterministic engine and CLI workflows through conversion, metadata, data profiling, Zotero offline support, external search, document validation, guideline registration, research questions, claims, reports, backup, and migration.

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
  api/
    CONTRACT.md

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

- `frontend` or equivalent UI planning folder.

Now exist (this section was written before Phase 9/11 started and was not kept current — see the phase-by-phase audit below for actual status):

- `researchboss/api` for FastAPI (Phase 9).
- `docs/PACKAGING.md` for desktop packaging notes (Phase 11; a single file, not a `docs/packaging/` folder).

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
| Zotero offline reports | Implemented | `researchboss/engine/zotero.py`, `cli.py` | Metadata, notes, tags, relations, attachment, full-text, duplicates, snapshots, BibTeX. |
| Conversion | Implemented | `researchboss/engine/conversion.py`, `cli.py` | TXT, MD, DOCX, simple page-marked PDF, cache, failures. |
| Citation metadata | Implemented | `researchboss/engine/metadata.py`, `researchboss/engine/metadata_quality.py`, `cli.py` | DOI/year/title extraction, DOI validation, citation consistency, duplicate metadata reports, keyword index. |
| Data profiling | Implemented | `researchboss/engine/data.py`, `cli.py` | CSV, SQLite, JSON profiles. |
| Deterministic artefact creation | Implemented | `researchboss/engine/artefact_creation.py`, `cli.py` | Non-AI workspace reports/tables requiring user review. |
| Artefact registry | Implemented | `researchboss/engine/artefacts.py`, `researchboss/engine/export.py`, `cli.py` | Linked sources/RQs, review and AI flags, dependency checks, evidence bundle export. |
| Research stages/questions | Implemented | `workspace.py`, `research_questions.py`, `cli.py` | M.Phil/PhD stages, RQ workflow commands, and deterministic readiness checks. |
| Claims and citation gaps | Implemented | `researchboss/engine/claims.py`, `cli.py` | Manual claims and gap report. |
| Document validation | Implemented | `researchboss/engine/document_targets.py`, `researchboss/engine/doc_validation.py`, `cli.py` | Resolves target documents and writes deterministic validation reports with confidence factors, scores, citation gaps, and APA7 references. |
| Guideline registration | Implemented | `researchboss/engine/guidelines.py`, `cli.py` | Snapshots local or remote guideline sources inside the workspace, extracts text, and stores validated scopes. |
| Reports/watch/backup/migration | Implemented | `reports.py`, `watch.py`, `backup.py`, `health.py`, `migrations.py` | Local deterministic utility workflows, workspace health, backup dry-run inspection. |
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
- Read-only local Zotero SQLite notes, tags, relations, linked-item metadata, extra metadata fields, and richer BibTeX mapping.

Remaining Phase 1 refinements:

- Consider validating `--kind` values instead of accepting arbitrary provider strings.

### Phase 2: Conversion and Metadata

Status: implemented for deterministic local MVP paths.

Implemented:

- TXT, MD, DOCX, and simple PDF conversion with page markers.
- Conversion cache by file hash.
- Failed conversion handling.
- DOI detection and basic citation metadata extraction without invented metadata.
- Deterministic DOI syntax and resolver-link validation to flag malformed DOI values or suspicious DOI URLs without rewriting metadata.
- Citation consistency reports for missing DOI, title, year, author, and mismatched DOI URL formats.
- Duplicate reports by filename, title, and DOI in addition to content hashes.
- Local keyword index over converted text in `sources_text/`.

Useful future enhancements learned from `../pdf-merge`:

- Add optional PyMuPDF/PyPDF2 PDF extraction for better page text coverage than the current conservative parser.
- Add local OCR readiness checks and optional OCR fallback for scanned PDFs.
- Add CSL JSON, BibTeX, and RIS sidecar metadata parsing.
- Add abstract, keyword, publication-title, author, and year detection from sidecar files and PDF metadata.
- Add deterministic source filename normalization helpers without renaming original files.

### Phase 3: Data and Artefacts

Status: implemented for deterministic local MVP paths.

Useful future enhancements learned from `../pdf-merge`:

- Add accepted-source text corpus exports with per-source headers, source IDs, titles, authors, and separators.
- Add optional PDF merge artefacts for accepted source PDFs.
- Add library-wide and batch merge modes as artefacts, never as source mutations.
- Add merge manifests and CSV reports recording included, skipped, failed, and batched source IDs.

Implemented:

- CSV profiling.
- SQLite profiling.
- JSON source registration and profiling.
- Data profile reports.
- Rich artefact registry records.
- Evidence bundle export containing accepted source metadata, claims, research questions, artefacts, and data profiles.
- Artefact review workflow with reviewed, needs revision, and accepted states.
- Artefact dependency checks against existing accepted sources and approved research questions.

### Phase 4: Research Questions and Stages

Status: implemented for deterministic local MVP paths.

Implemented:

- Init-time research questions.
- Draft and approved separation.
- Optional subquestions.
- Research question templates for all project types.
- M.Phil and PhD stage templates.
- Stage statuses.
- RQ list, approve, reject, and archive commands.
- Deterministic RQ readiness checks for question form, scope signals, vague wording, possible multiple questions, context markers, subquestion alignment, and project-level hints.
- Local RQ readiness reports under `outputs/validation/research-question-readiness.yaml`.
- Warning thresholds.
- Source notes, manual source tags, source review reports, and claim status workflows.
- Decision log, terminology glossary, supervisor/stakeholder feedback, context changelog, and local timeline commands.

Future:

- AI-assisted RQ strength, novelty, field usefulness, contribution, and evidence-quality review after privacy-boundary tests exist.

### Phase 5: Optional OpenAI Features

Status: implemented for current safe-context MVP workflows.

Implemented:

- Local AI preference metadata only.
- AI disabled in generated app settings.
- `researchboss ai test`.
- `OPENAI_API_KEY` loading from environment or local `.env` without printing or logging the key.
- Explicit `--ai` opt-in for live OpenAI credential checks.
- `researchboss ai context-preview --ai` for local safe-context preview generation.
- `researchboss ai review --ai` for AI-assisted source/corpus review.
- `researchboss assess-novelty --ai` with `novelty-ledger.yaml` updates.
- `researchboss rqs assess --ai` for AI-assisted research question strength, novelty, field usefulness, and evidence-quality review.
- `researchboss ai corpus-summary --ai` for safe-context corpus summary reports.
- `researchboss ai claim-check --ai` for safe-context claim-checking recommendations.
- `researchboss ai citation-gaps --ai` for safe-context citation-gap recommendations.
- `researchboss ai artefact-cross-reference --ai` for safe-context artefact cross-reference review.
- `researchboss ai source-relevance --ai` for safe-context source relevance recommendations.
- Privacy-boundary tests for missing keys, key non-disclosure, explicit `--ai`, and whole-document/dataset exclusion.

Next work:

- Explicit full-file and full-directory opt-in modes with warning output and tests.
- AI-assisted abstract screening for locally imported abstracts.

### Phase 6: Document Validation, Guidelines, and Citation Assistance

Status: partially implemented for deterministic validation and guideline registration.

Implemented:

- APA7 is the default workspace citation style unless configured otherwise.
- Document target resolution for paths, artefact IDs, artefact titles, primary aliases, and deterministic artefact type names.
- `researchboss validate <target>` compares a target document against accepted workspace sources and explicitly supplied source paths.
- Validation reports include strengths, weaknesses, unsupported and weakly supported sentences, missing citations, candidate supporting sources, evidence confidence factors, conservative confidence scores, and APA7 references.
- Guideline registration writes snapshots and extracted text inside the workspace.
- Guideline scopes are validated for validation, citation, structure, style, journal submission, thesis, supervisor, rubric, and all-purpose rules.

Next deterministic work:

- Guideline defaults, priorities, and command integration.
- Guideline conflict reports.
- Reviewable citation insertion plans and deterministic citation-plan application.
- Citation safety gates and validation/citation output schemas.

### Phase 7: Workspace SQLite Memory, Indexing, and Sync

Status: implemented for deterministic local MVP paths.

Implemented:

- Optional local `researchboss.sqlite` inside each workspace.
- YAML and Markdown remain the human-readable source of truth.
- SQLite is a rebuildable index, cache, memory layer, and controlled sync layer.
- `researchboss db init`, `researchboss db sync`, `researchboss db status`, and `researchboss db rebuild`.
- Sync metadata with file hashes, last synced timestamps, database revisions, file revisions, dirty flags, and conflict status.
- Reviewed pending-change write-back through `researchboss db apply-pending --review` and `researchboss db apply-pending --apply`.
- Memory tables for query patterns, user preferences, guideline decisions, citation decisions, validation notes, claim-source links, and AI-safe context choices.
- Explicit research index tables for validation runs, evidence matches, citation plans, guideline registrations, search query history, and document version metadata.
- Document aliases for primary outputs and artefact registry IDs/titles.
- Bounded SQLite FTS indexes for converted source text, artefact text, guideline text, claims, references, and document sections.
- SQLite integrity/repair status and rebuild-from-YAML behavior.
- Database privacy checks for secrets, full original documents, Zotero-owned file boundaries, and unintended large/original content storage.

### Phase 8: Document Vault, Versioning, and Restoration

Status: deterministic MVP paths complete.

Done:

- Local document vault layout (`document_vault/originals`, `versions`, `derived_text`, `diffs`, `manifests`, `ai_edit_sessions`, `uploads/originals`, `uploads/renamed`) created at workspace init.
- Document version records (version ID, parent version ID, content hash, creation reason, source command, model metadata, guideline IDs, validation report ID, citation plan ID) through `researchboss doc version`/`doc versions`.
- Text diff (`doc diff`) and validation-based version comparison (`doc compare`) reports.
- Restore-as-copy behavior (`doc restore`) that never overwrites the current document or deletes newer versions.
- Automatic pre/post-change snapshots wired into `cite apply`, the only current command that creates a modified document copy.
- `document_versions` SQLite sync and document vault inclusion in local backups.
- Uploaded-artefact intake (`doc upload`/`doc uploads`, `vault.intake_uploaded_artefact`): copies an externally created file into `uploads/originals` (collision-safe suffix) and a renamed `uploads/renamed` copy (author/year/title tokens plus an embedded upload ID for guaranteed uniqueness) without ever touching the uploaded file. The author/year/title tokenizing helpers moved out of `metadata_quality.py` into a shared `researchboss.engine.filenames` module so both source filename suggestions and upload renaming use the same logic.
- Derived text snapshots with paragraph/sentence anchors (`researchboss.engine.derived_text`, `doc derive-text`, `POST /api/v1/doc/derive-text/{version_id}`): paragraphs with character offsets, sentences with a `citation_insertion_anchor` (matching `citations._insert_citation`'s actual "before final punctuation" behavior), `claim_ids` (claims whose text appears in the sentence), and `reference_ids` (source IDs from a linked validation report's `sentence_checks`, joined by exact normalized sentence text rather than positional index — more robust to reordering). Section maps only work for `.md` targets: headings are recovered by scanning the *raw* source for `#`-prefixed lines (since `extract_text()` strips heading syntax entirely) and matching each heading's surviving text against extracted paragraphs in order; `.txt`/`.docx`/`.pdf` get no section detection rather than a guessed one, since DOCX heading styles aren't preserved by `_extract_docx_text` and plain text/PDF text has no structural marker at all. `text_analysis.py` extracted from `doc_validation.py`'s private `_sentences`/`_has_inline_citation` (mirroring the `filenames.py` extraction pattern) so both modules share one sentence-splitting/citation-detection implementation.
- Found and fixed a real pre-existing bug in `conversion._markdown_to_text` while building the above (not something the new feature caused — it affects all markdown conversion): the heading/blockquote/list-stripping regexes used `\s` for leading same-line indentation, which also matches newlines. A match could therefore start at a preceding *blank* line's own line-start position and reach forward across it into the marker, silently deleting the blank line and merging that block into the previous paragraph in every downstream blank-line-based paragraph split. Fixed to `[ \t]` (same-line indentation only); added a dedicated regression test covering all four affected patterns (heading, blockquote, bullet list, numbered list). Full existing test suite re-run to confirm nothing depended on the buggy behavior — it didn't.

Next work:

- AI edit sessions as reviewable operations (AI-tagged; needs explicit opt-in and privacy-boundary tests first — the anchor infrastructure they need now exists).

### Phase 9: FastAPI Local Backend

Status: every route currently documented in `docs/api/CONTRACT.md` is implemented, except the disabled Future AI Routes section and novelty assessment (AI-only, intentionally excluded from the contract until AI opt-in rules apply).

Done:

- App factory (`researchboss/api/app.py`) with the documented `{ok, data, warnings, errors}` response envelope and `ApiError`-to-JSON exception handling.
- Workspace-resolution dependency requiring an explicit `workspace` query parameter (no interactive discovery, unlike the CLI).
- `GET /health` outside `/api/v1`, with no workspace or auth dependency.
- Projects (`status`, `init` with a 409 rather than silently overwriting, `health`).
- Sources (`list`, `scan`, `status`, `note`, `tags`, `report`), all with 404s for unknown source IDs rather than a generic 400.
- Conversion (`run`), metadata (`extract`, `validate`, `duplicates`, `index`), and data (`profile`, `list`, `status`).
- Research questions (`list`, `check`, `approve`, `reject`, `archive`), 404s for unknown RQ IDs.
- Claims (`list`, `add`, `status`, `gaps`, `validate`), 404s for unknown claim IDs.
- Artefacts (`list`, `register`, `create`, `review`, `dependencies`); `create` returns 409 when the deterministic artefact file already exists.
- Zotero: read-only local (`collections`, `search`) and Web API (`test`, `collections`) routes, plus a collection-selection route that writes only to the workspace's `research-context.yaml`, never to Zotero.
- Document vault (`version`, `versions`, `diff`, `compare`, `restore`).
- Reports (`workspace`, `timeline`), evidence export, backup (`create`, `inspect`), and project log (`decisions`, `terminology`, `feedback`, `context/changelog`).
- `researchboss serve` to run the app with uvicorn; route tests via `fastapi.testclient.TestClient`, plus live-HTTP smoke tests during development.
- Moved `resolve_zotero_paths`/`configured_source_root`/`configured_zotero`/`write_zotero_config` out of private `cli.py` helpers into `researchboss.engine.zotero` so the CLI and the API share one implementation instead of duplicating Zotero config resolution.
- Single-user login protection: `RESEARCHBOSS_API_PASSWORD`-configured, `POST /api/v1/auth/login`/`logout`, an in-memory expiring session store (`researchboss/api/auth.py`), and a `require_session` dependency applied via `dependencies=[...]` on every protected router's `include_router()` call rather than touching each route handler. Fails closed with `503 auth_not_configured` when no password is set — never silently open. Accepts either the httponly session cookie or an `Authorization: Bearer` token. Password/tokens never logged or persisted to YAML/SQLite/git.
- Validation (`POST /api/v1/validation/run`), citation plans (`POST /api/v1/citations/plan|apply`), guidelines (`GET/POST /api/v1/guidelines`, `.../defaults`, `.../conflicts`), and SQLite sync status (`POST /api/v1/db/init|sync|rebuild|apply-pending`, `GET /api/v1/db/status|pending|privacy`) — added the route shapes to `docs/api/CONTRACT.md` and implemented them in the same pass, since each mapped 1:1 to an already-tested engine function.
- `RESEARCHBOSS_WORKSPACE_ROOT`: when set, `resolve_workspace` (`researchboss/api/deps.py`) requires every workspace to resolve inside that root — relative paths joined to it, absolute paths outside it rejected with `400 workspace_outside_root` — closing a path-traversal gap that existed before (any absolute path reachable by the server process was accepted as a "workspace"). Unset, behavior is unchanged. This is the NAS-mounted-volume prerequisite for Phase 12.
- `POST /api/v1/artefacts/upload`: real multipart batch upload (`researchboss/api/routers/artefacts.py`), backed by a new `vault.intake_uploaded_artefact_batch` engine function. Rejects the whole batch (`400 upload_batch_too_large`) before writing anything if it exceeds `RESEARCHBOSS_UPLOAD_MAX_FILES`; each file capped at `RESEARCHBOSS_UPLOAD_MAX_FILE_SIZE_MB` and checked against `sources.ALLOWED_EXTENSIONS`. Uploaded bytes are streamed to a bounded-size temp file (capped at roughly `max_size + 1 chunk`, never buffered whole in memory) in a per-file temp subdirectory — nesting rather than filename-prefixing was needed after an initial version leaked an internal `000-`-style prefix into the reported filename and the renamed vault copy's title, caught by a live-HTTP smoke test rather than the unit tests. Temp directory always removed via `finally`. Content-hash duplicate detection against prior uploads in the workspace. Report persisted to `outputs/validation/upload-batch-report.yaml`, mirroring `source_review_report`.
- `GET /api/v1/artefacts/cross-reference`: new `researchboss.engine.cross_reference` module. Proposes candidates by shared keyword tokens (title/filename, stop-word-filtered) between an uploaded artefact and existing artefacts, sources, and claims — claim matches require ≥2 shared keywords rather than 1, since claim text is long and generic enough that a single shared word is weak evidence. Read-only: writes a candidate report to `outputs/recommendations/cross-reference-<upload_id>.yaml` but never touches an artefact, source, or claim record.
- `POST /api/v1/artefacts/cross-reference/apply`: resolved the registry-metadata-vs-document-editing question left open above. Chose registry metadata — `vault.add_cross_references_to_upload` appends to a `cross_references` list on the *upload* record (mirroring `linked_sources`/`linked_research_questions` on artefact records), deduplicated by `(target_kind, target_id)` so re-applying is idempotent. `apply_cross_reference_links` re-reads the persisted candidates report and only applies rows hand-edited to `review_status: accepted`/`approved`, exactly mirroring `create_citation_plan`/`apply_citation_plan`'s convention. Rationale for not choosing document-content insertion: a keyword-overlap match is meaningfully weaker evidence than `cite apply`'s validated missing-citation match, so auto-inserting text into a document on that basis would be a worse default than recording it as reviewable metadata — and nothing forecloses adding a content-insertion mode later if reviewable metadata turns out to be insufficient. Verified live over real HTTP end to end.

Next work:

- Novelty assessment has no deterministic engine path (`ai_novelty_assessment` in `researchboss/engine/ai.py` is AI-only) — a route needs the same explicit AI opt-in, cost-awareness, and privacy-boundary rules as the Future AI Routes section, not just a contract addition.
- AI-assisted cross-reference suggestions (AI-tagged, needs the same opt-in/privacy-boundary treatment as novelty).

### Phase 10: Cross-Platform UI Preparation

Status: complete. UI strategy decided and implemented.

Decision: FastAPI + Jinja2 server-rendered shell + vanilla JavaScript (`researchboss/web/`), no build toolchain, no third-party JS/CSS dependency, no CDN assets. Mounted onto the same FastAPI app `researchboss serve` already runs — no separate process, port, or deployment step. The web layer has no import path to `researchboss.engine`: it only imports session-cookie helpers from `researchboss.api.auth`, and every data operation happens client-side via `fetch()` calls to the existing, tested `/api/v1/*` routes — the web UI is architecturally just another API client. React/Vue/Svelte/Flutter were considered and passed on; `docs/PACKAGING.md`'s conditional Flutter desktop-sidecar section is now historical.

Built: `GET /login` (public) and `GET /` (server-side session-gated — redirects to `/login` before rendering anything, not just after a failed client-side call) shell pages; drag-and-drop batch upload with pre-submission limits (new `GET /api/v1/artefacts/upload/limits` route); a batch-upload results view; a popup preview modal (PDF via `<iframe>`, text/Markdown/CSV/JSON fetched into `<pre>`, download-fallback for unsupported types); a cross-reference review overlay (accept/reject per candidate, then apply); an About/License footer modal. Two new API routes were needed and added along the way: `GET /api/v1/artefacts/uploads` (list) and `GET /api/v1/artefacts/uploads/{upload_id}/file` (inline file bytes for preview) — nothing previously served raw file bytes at all.

Found and fixed two real bugs while verifying this against an actual `pip install` rather than just the source-tree test suite: (1) a circular import (`api/__init__.py` eagerly re-exported `create_app`, which round-tripped through `web/app.py` back into `api.auth`; fixed by emptying the unused re-export) that only manifested if `researchboss.web.app` was imported before `researchboss.api`, which every test/smoke script in this repo happened never to do; and (2) missing `package-data` in `pyproject.toml`, so a real wheel install wouldn't have shipped the `templates/`/`static/` files at all. Both confirmed fixed by building a real wheel and installing it into a throwaway venv — not just re-running pytest.

Not built, and not needed yet: a separate desktop or mobile shell (the responsive web page covers the stated use case; nothing currently asks for one). Citation-plan-specific review UI beyond the cross-reference overlay (citations already have their own `POST /api/v1/citations/plan/insertion-review` API route and CLI command, just no dedicated web view yet) — a reasonable next increment if it's ever asked for, not added speculatively here.

### Phase 11: Packaging

Status: planning complete (`docs/PACKAGING.md`); no actual packaged build has been produced or tested yet.

Done:

- Packaging plan covering CLI, local API, workspace SQLite (stdlib `sqlite3`, nothing to bundle), document vault files (plain workspace files, not a packaging concern), and the web UI (Phase 10 decided against Flutter; `researchboss/web/` ships as part of the same package via `[tool.setuptools.package-data]`, verified against a real wheel install — no separate packaging concern).
- PyInstaller recipe plus two gotchas identified from known uvicorn/PyInstaller interaction patterns rather than verified against a real build yet: uvicorn's dynamic loop/protocol imports and `python-multipart` (only imported at upload-request time) both need explicit `--hidden-import`/`--collect-all` treatment or the packaged binary will fail specifically at `researchboss serve` / file-upload time despite a clean `pyinstaller` exit code.
- Flutter desktop sidecar notes: now historical/moot — Phase 10 chose a Jinja2 + vanilla-JS web UI mounted directly on the existing FastAPI app instead, with no separate shell process for this section's sidecar model to apply to.
- Fixed a real, concrete gap found while researching platform coverage: `workspace.zotero_storage_candidates()` had no Linux branch at all (fell through to an empty list — `researchboss init` could never auto-detect Zotero on Linux). Added native (`~/Zotero/storage`, `~/.zotero/zotero/*/zotero/storage`) and Flatpak (`~/.var/app/org.zotero.Zotero/data/zotero/storage`) candidates, matching the existing macOS/Windows "first existing candidate wins" pattern. Snap-packaged Zotero left as an explicit known gap rather than guessed at.
- Confirmed (by reading `ocr_readiness_report()`, not assuming) that OCR fallback depends on system-installed `tesseract`/`pdftoppm` located via `shutil.which()` — external CLI tools PyInstaller cannot bundle. Documented as an explicit end-user prerequisite for packaged builds rather than left to silently report "unavailable."

Next work:

- Produce and test an actual PyInstaller build against the two identified gotchas — the plan is unverified against a real binary.

### Phase 12: NAS Deployment (research.veloso.dev)

Status: Dockerfile, Compose file, and deploy documentation written; nothing has actually been deployed.

Done:

- `Dockerfile`: `python:3.11-slim`, `pip install .`, single-process `uvicorn researchboss.api.app:app` (no `--workers` — see the file's own comment: session state in `researchboss/api/auth.py` is an in-memory dict, so more than one process/replica would randomly fail logins depending which one handled a given request), a `HEALTHCHECK` hitting `/health`, and `tesseract`/`poppler-utils` installed so the deployed instance can actually use the `--ocr` conversion fallback (unlike a PyInstaller desktop build, a container can bundle these).
- `docker-compose.yml`: bind-mounts `./data/workspaces` to `/data/workspaces` (matching `RESEARCHBOSS_WORKSPACE_ROOT`) rather than an opaque named volume, so workspace files stay directly inspectable/backupable on the NAS's own filesystem; `RESEARCHBOSS_API_PASSWORD` required via Compose's `:?` syntax (refuses to start rather than silently running without one, consistent with the API's own fail-closed behavior); other `RESEARCHBOSS_*` env vars optional with the same defaults the app itself uses.
- Extended the existing `.env.example` (already the file `researchboss/api/auth.py`, `zotero_api.py`, and `ai.py` all read via the shared `Path.cwd()/.env` convention) with the new deployment-related variables, rather than inventing a second env-file mechanism.
- `docs/DEPLOY.md`: local test-before-deploy steps, the exact `synology-site deploy` invocation (`--source-dir` to build on the NAS without needing a registry, `--port 8000` for automatic Cloudflare routing, `--health-path /health`), setting up a workspace per research project via `POST /api/v1/projects/init` against the mounted root, `update`/rollback behavior (session invalidation on restart is expected, not a bug), and why license/developer-info consistency (the last Phase 12 TODO item) is blocked on an actual deployment — Phase 10 now has a page to check (the About/License footer modal in `researchboss/web/`), so that half of the earlier blocker is resolved.
- Verified what could be verified without Docker (not available in this environment): a genuinely clean-venv `pip install .` followed by running the Dockerfile's exact `CMD` served `/health` successfully, and separately, a real wheel build+install confirmed the web UI's templates/static assets ship correctly and both import orderings resolve (see the Phase 10 circular-import fix). The container build itself (base image, `apt-get` layer, healthcheck) was not verified and is documented as the reader's first step, not claimed as done.

Next work:

- Actually run the `synology-site deploy research.veloso.dev` command above — needs real NAS SSH access and Cloudflare credentials neither this environment nor an unattended session should have.
- Confirm license/developer-info consistency on the live site once it exists — the content itself (`researchboss/web/templates/index.html`'s About modal) is already in place and matches the README/LICENSE; this step is purely "check it renders correctly once actually deployed."

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
| `researchboss validate` | Implemented | Resolves target documents and writes deterministic validation reports. |
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
| `researchboss rqs suggest` | Missing | Future AI or template workflow. |
| `researchboss rqs approve` | Implemented | Approves draft RQs. |
| `researchboss rqs reject` | Implemented | Rejects RQs. |
| `researchboss rqs archive` | Implemented | Archives RQs. |
| `researchboss claims add/list/gaps` | Implemented | Manual claim ledger and citation gaps. |
| `researchboss artefacts register/list` | Implemented | Artefact registry workflow. |
| `researchboss artefacts create` | Implemented | Deterministic non-AI artefact creation from existing workspace state. |
| `researchboss guidelines add/list` | Implemented | Registers guideline snapshots and extracted text inside the workspace with validated scopes. |
| `researchboss review` | Missing | Later integrated review workflow. |
| `researchboss rqs assess` | Implemented | AI-assisted RQ assessment; requires `--ai`. |
| `researchboss assess-novelty` | Implemented | AI-assisted novelty assessment; requires `--ai`; updates novelty ledger. |
| `researchboss ai test` | Implemented | Local readiness check; live OpenAI request requires explicit `--ai`. |

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

Status: implemented for current safe-context MVP workflows.

Implemented:

- AI preference metadata.
- `ai.enabled: false` in local app settings.
- `.env` ignored.
- `.env.example` exists.
- `OPENAI_API_KEY` loaded from environment or local `.env`.
- API key is not printed or logged.
- `researchboss ai test` writes a local readiness report.
- `researchboss ai context-preview --ai` writes a local safe context preview without making an OpenAI request.
- `researchboss ai review --ai` writes a local AI-assisted review report.
- `researchboss assess-novelty --ai` writes a local novelty report and appends `novelty-ledger.yaml`.
- `researchboss rqs assess --ai` writes a local AI-assisted research-question assessment report.
- Tests cover missing key behavior, key non-disclosure, explicit `--ai`, no default whole-document/dataset inclusion, mocked AI workflow outputs, and explicit external-search opt-in.

Missing:

- AI-assisted abstract screening for local abstract imports.
- Explicit full-file and directory opt-in modes.

Planned AI options:

- Workflows marked as not safely deterministic will be implemented only in the AI phase, not in the current deterministic engine.
- Research question strength, novelty, contribution certainty, field usefulness, and evidence-quality reasoning will be AI-assisted or human-review workflows, not deterministic validators.
- Explicit user-controlled options to allow AI to read an entire file when the user approves that level of context.
- Explicit user-controlled options to allow AI to read a directory of files when the user approves that level of context.
- Optional full-paper reasoning mode for consuming entire papers.
- Optional cross-reference mode where AI can compare full papers against in-progress artefacts.
- These modes must be disabled by default, must never modify Zotero, and must keep outputs inside the ResearchBoss workspace.

Future AI work that makes sense to implement next:

- AI-assisted abstract screening for locally imported abstracts, writing recommendations only.
- Explicit per-run full-file AI opt-in flags with warning output and tests.
- Explicit per-run directory AI opt-in flags with warning output and tests.
- Optional AI-assisted query generation, query refinement, paper relevance review, research-question validation, idea validation, and novelty validation using safe context first and full text only by explicit opt-in.

## 11.1 External Search Quality Roadmap

Goal: use external scholarly search as a controlled evidence-discovery workflow, not an unbounded automation loop.

Implemented baseline:

- `researchboss search plan` creates deterministic query plans from project context and research questions.
- `researchboss search scopus --external-search` runs explicit Scopus searches and stores response snapshots.
- `researchboss search scopus-test --external-search` checks credentials without printing keys.
- Search query history and no-result snapshots are written inside the ResearchBoss workspace.
- Scopus search runs now write quality-scored candidate registers, threshold-filtered candidate lists, query validation reports, low-result logs, and metadata-only full-text availability signals.
- Query planning now supports legacy params-file import, broad/balanced/strict strategy modes, structured query records, query group labels, and research-question links.

Planned deterministic work:

- Expand configurable thresholds to include document type, source type, maximum queries per run, maximum refinement rounds, and elapsed-time budget.
- Expand query validation reports to compare candidates against approved research questions, accepted source metadata, local keyword indexes, and citation gap reports.
- Expand deterministic query refinement candidates from approved RQs, inclusion/exclusion terms, local keyword indexes, accepted source metadata, and citation gap reports.
- Expand query group labels so queries can also be linked to claim gaps, source gaps, and manual search objectives.
- Add deterministic auto-refine planning that writes broader follow-up queries when search yield is weak, but requires explicit user approval before making another API run.
- Add query exhaustion protection: maximum API calls, maximum generated queries, maximum refinement rounds, maximum pages, maximum candidate records, and maximum elapsed time.
- Add filtered-candidate logs with explicit threshold-failure reasons such as year, citation count, document type, source type, missing DOI, missing abstract, duplicate DOI/EID, or incomplete metadata.
- Add batch search run summaries that aggregate processed, candidate, filtered, skipped, duplicate, no-result, and low-result counts across many queries.
- Add high-signal candidate reports sorted by quality score, RQ coverage, citation count, recency, open-access flag, metadata completeness, and duplicate status.
- Add candidate deduplication across Scopus runs, local Zotero metadata, source register records, DOI, EID, title, and year.
- Add external-search run comparison reports to identify which query strategies produced the strongest candidate yield.
- Add local Zotero matching to full-text availability detection. Do not download, scrape, or bypass access controls.
- Add user-approved candidate import so selected external results become metadata-only pending-review sources.
- Add evidence validation reports that compare candidate papers against RQs, claims, novelty ledger entries, artefacts, and known source gaps.
- Expand reproducibility files for every external search run with skipped candidate reason details, threshold set IDs, and run-level search budgets.

Planned AI-assisted work:

- Add optional AI-assisted query generation and refinement only when both `--ai` and `--external-search` are supplied.
- Add optional AI-assisted relevance, idea validation, RQ validation, and novelty validation using candidate metadata and abstracts first.
- Add explicit full-text AI modes later, with warnings and per-run opt-in, for cases where the user approves whole-paper reasoning.

## 11.2 Legacy Project Lessons

The old `../pdf-merge` project is useful as workflow evidence, but ResearchBoss should not inherit its ad hoc file movement, cloud sync assumptions, automatic full-text retrieval attempts, or deletion of intermediate text. The useful ideas should be rebuilt as local-first, manifest-driven engine workflows.

Useful patterns to bring forward:

- Params-file import for curated query groups such as RQ1/RQ2/RQ3.
- Query history with skip/re-run controls.
- Broad, balanced, and strict query strategy modes.
- Search quality thresholds and batch-level search summaries.
- No-result, low-result, filtered, skipped, and not-relevant logs.
- Abstract text-file import from old Scopus exports.
- Combined abstract/text corpus export with source headers and separators.
- PDF merge artefacts for accepted sources, always generated inside ResearchBoss artefact folders.
- OCR readiness checks and optional local OCR fallback for scanned PDFs.
- Manifest-first processing so every merge/export/search run records included, skipped, failed, and generated files.

Rules for adapting these ideas:

- Never move, rename, delete, or overwrite original source files.
- Never write into Zotero storage or another external library directory.
- Do not add Google Drive, cloud sync, or remote storage assumptions.
- Do not automatically retrieve full text from publisher APIs. Detect availability, then require explicit user action.
- Do not treat AI relevance labels as source status changes. AI can recommend; the user or deterministic commands must confirm.
- Preserve all intermediate text and metadata files unless the user explicitly runs a cleanup command.

## 12. Tests Audit

Framework: pytest.

Current tested areas:

- CLI smoke tests, including document validation and guideline registration commands.
- Workspace initialization.
- Source scanning and review.
- Workspace selection.
- Runtime checks.
- Local Zotero storage helpers, SQLite metadata, collection filtering, reports, snapshots, duplicate checks, BibTeX export, and CLI search.
- Conversion, metadata extraction, data profiling, artefact registry, research questions, claims, document validation, guidelines, reports, watch, backup, and migration.

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
- `docs/api/CONTRACT.md`
- `docs/PACKAGING.md`
- Setup and test instructions.
- Initial OpenAI and Zotero notes.
- Local-first privacy boundaries.

Missing:

- Desktop/web/mobile strategy.

## 15. Immediate Next Steps

Every deterministic item across Phases 8, 9, 10, and 11 that did not require either a live infrastructure credential or a product decision on AI cost/privacy tradeoffs is now complete: Phase 8 (document vault, versioning, restoration, uploaded-artefact intake, derived-text/anchor extraction), Phase 9 (every route in `docs/api/CONTRACT.md` except the disabled Future AI Routes section — including login protection, validation, citation plans, guidelines, SQLite sync status, `RESEARCHBOSS_WORKSPACE_ROOT` containment, batch artefact upload, cross-reference candidates/apply, and both review-status routes), Phase 10 (the web UI framework decision was made and the full UI built — see the Phase 10 section above), and Phase 11 planning (`docs/PACKAGING.md`) plus the Phase 12 deployment artifacts (`Dockerfile`, `docker-compose.yml`, `docs/DEPLOY.md` — written but not deployed, since that needs real NAS/Cloudflare credentials).

What's left is genuinely blocked, not just undone:

1. A novelty assessment route under explicit AI opt-in.
   - Why: unlike every other Phase 9 route group, novelty assessment has no deterministic engine path — `researchboss.engine.ai.ai_novelty_assessment` always calls OpenAI, so a route needs the same per-request AI opt-in, cost-awareness, and privacy-boundary rules as the Future AI Routes section, not just mechanical route-wrapping. The shape is already sketched (`docs/api/CONTRACT.md`'s Future AI Routes section) — what's missing is the actual opt-in/cost decision and implementation.
   - Likely files: new `researchboss/api/routers/ai.py`, tests proving the AI opt-in and safe-context boundaries.
   - Tests: route requires explicit opt-in, never sends whole documents by default, API key never returned/logged.
   - Complexity: medium — mostly gated by the explicit-AI-opt-in design already used elsewhere, not new design.
   - Phase: 9 (Future AI Routes).

2. AI edit sessions (Phase 8) and AI-assisted cross-reference suggestions (Phase 9).
   - Why: both are AI-tagged and need the same explicit opt-in/privacy-boundary treatment as novelty above. The anchor infrastructure AI edit sessions need (paragraph/sentence IDs, citation insertion anchors) is now built — this is purely an AI-design gate, not missing engine work.
   - Phase: 8/9.

3. Phase 12's actual `synology-site deploy` run, and a dedicated citation-plan review web view (the API/CLI side is done; only the cross-reference overlay has a web view so far).
   - Why: the deployment needs a real NAS/Cloudflare credential this environment does not have; the citation web view is a reasonable next increment, not something blocked on anything, just not built yet since nothing has asked for it specifically.
   - Phase: 10, 12.

## 15a. Useful Ideas Learned From `../pdf-merge`

The old project is useful as a reference for ResearchBoss, but its cloud-sync and external-search assumptions should not be copied into the MVP. Useful patterns to port or redesign:

- A richer local document-processing layer with optional PyMuPDF/PyPDF2 extraction and local OCR fallback.
- Sidecar metadata readers for CSL JSON, BibTeX, and RIS.
- Abstract and keyword extraction from sidecar files and early PDF pages.
- Accepted-source text corpus export with strong source headers and separators.
- PDF merge artefacts for accepted sources, including batch and library-wide outputs.
- Merge manifests, index files, and CSV reports for reproducible generated artefacts.
- Deterministic title/author/year filename normalization for generated outputs only.
- Local abstract import/screening workflows for already collected abstracts.
- Query-plan and query-history utilities for a later post-MVP external search phase.

Not suitable for MVP right now:

- Google Drive sync.
- External Scopus search.
- Any workflow that moves, renames, or modifies original source files.
- Any workflow that writes inside Zotero storage.

## 16. Recommended Resume Point

Phase 8 (document vault, versioning, restoration, uploaded-artefact intake, derived-text/anchor extraction) is complete. Phase 9 FastAPI implements every route in `docs/api/CONTRACT.md` except the disabled Future AI Routes section (now shape-sketched, not implemented). Phase 10 is complete: a Jinja2 + vanilla-JS web UI (`researchboss/web/`) is built, tested, and mounted onto the same FastAPI app, covering login, drag-and-drop upload, batch results, popup preview, cross-reference review, and an About/License footer. Phase 11 planning and Phase 12's deployment artifacts are written but not executed. Everything genuinely actionable without either an AI cost/privacy decision or live infrastructure credentials is done. Resume with: an explicitly AI-gated novelty route (Phase 9), AI edit sessions (Phase 8, anchor infrastructure already built), AI-assisted cross-reference suggestions (Phase 9), a dedicated citation-plan review web view (Phase 10, API/CLI side already done), or actually running the Phase 12 NAS deployment. AI work remains intentionally separated behind explicit opt-in and privacy-boundary tests.

## 17. Maintenance Rule

Whenever development changes ResearchBoss behavior:

- Update this roadmap.
- Update `README.md` project version.
- Update package version in `pyproject.toml` and `researchboss/__init__.py` when releasing or committing user-visible feature work.
- Update `CHANGELOG.md`.
- Keep tests passing before commit or push.
