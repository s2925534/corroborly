# Changelog

All notable changes to ResearchBoss will be documented in this file.

## Unreleased

- Added `POST /api/v1/artefacts/cross-reference/apply`, resolving the open design question from the candidates route: reviewed links (`review_status: accepted`/`approved` in the persisted report) are written as metadata on the *upload* record (`cross_references`, mirroring `linked_sources`), never as text inserted into artefact/source/claim documents — a keyword-overlap match is weaker evidence than a validated missing-citation match, so auto-inserting text would be a worse default than reviewable metadata. Idempotent on re-apply. New `vault.add_cross_references_to_upload` engine function. Verified live over real HTTP end to end (upload, get candidates, hand-approve, apply, confirm the artefact record itself was untouched).
- Bumped project version to 0.9.4.
- Added `Dockerfile`, `docker-compose.yml`, and `docs/DEPLOY.md` for deploying the local API to a NAS via `../synology-site-deployer` (unmodified) as `research.veloso.dev`. Single-process by design (session state is in-memory, so multiple workers/replicas would randomly fail logins); bind-mounts a workspace root matching `RESEARCHBOSS_WORKSPACE_ROOT`; extended the existing `.env.example` rather than inventing a second env-file convention. Verified the Python packaging and exact container `CMD` in a clean venv (serves `/health` successfully); the container build itself was not verified — no Docker available in this environment — and the docs say so rather than implying otherwise. Nothing has actually been deployed; that step needs real NAS/Cloudflare credentials.
- Bumped project version to 0.9.3.
- Added `docs/PACKAGING.md` (Phase 11 plan): distribution approaches, a PyInstaller recipe with known uvicorn/`python-multipart` hidden-import gotchas, conditional Flutter desktop sidecar notes (only relevant if Phase 10 picks Flutter), and platform considerations. No packaged build produced or tested yet — planning only.
- Fixed a real gap found while writing the platform-considerations section: `workspace.zotero_storage_candidates()` had no Linux branch at all (`researchboss init` could never auto-detect a Linux Zotero install). Added native (`~/Zotero/storage`, `~/.zotero/zotero/*/zotero/storage`) and Flatpak (`~/.var/app/org.zotero.Zotero/data/zotero/storage`) candidates.
- Bumped project version to 0.9.2.
- Added `GET /api/v1/artefacts/cross-reference` (new `researchboss.engine.cross_reference` module): proposes deterministic links between an uploaded artefact and existing artefacts, sources, and claims by keyword overlap in titles/filenames (claim matches require a stronger overlap). Read-only — writes a candidate report but never an artefact, source, or claim record. The `apply` (write-back) route is deliberately not built yet: whether "write the link" means artefact-registry metadata or literal document-content insertion is a real design decision, not inferable from the citation-plan precedent.
- Bumped project version to 0.9.1.
- Added `POST /api/v1/artefacts/upload` for batch artefact uploads: multipart file bytes streamed to a bounded-size temp location (never buffered whole in memory), rejecting the whole batch with `400 upload_batch_too_large` before writing anything if it exceeds `RESEARCHBOSS_UPLOAD_MAX_FILES` (default 25), per-file `RESEARCHBOSS_UPLOAD_MAX_FILE_SIZE_MB` (default 50) and extension allow-list enforcement, content-hash duplicate detection, and a per-batch report persisted to `outputs/validation/upload-batch-report.yaml`. Backed by a new `vault.intake_uploaded_artefact_batch` engine function shared with (but not yet exposed by) the CLI.
- Bumped project version to 0.9.0.
- Added `RESEARCHBOSS_WORKSPACE_ROOT` so a deployed API instance can be pointed at a mounted volume (e.g. a NAS bind-mount): every `workspace` value must then resolve inside that root, closing a path-traversal gap where any absolute path reachable by the server process was previously accepted as a "workspace." Unset, behavior is unchanged (local-first, any absolute path).
- Bumped project version to 0.8.4.
- Added uploaded-artefact intake to the document vault through `researchboss doc upload/uploads`: copies an externally created file into `document_vault/uploads/{originals,renamed}` without ever modifying the upload itself, using a shared `researchboss.engine.filenames` module (extracted from the existing source filename-suggestion logic) for the renamed copy's author/year/title tokens, plus an embedded upload ID that keeps renamed copies collision-free and a numeric-suffix fallback for same-named original copies.
- Bumped project version to 0.8.3.
- Added `POST /api/v1/validation/run`, `POST /api/v1/citations/plan|apply`, `GET/POST /api/v1/guidelines/*`, and `GET/POST /api/v1/db/*` routes to the local FastAPI backend — every route in `docs/api/CONTRACT.md` is now implemented except the disabled Future AI Routes section and novelty assessment (which has no deterministic engine path and needs explicit AI opt-in rules, not just a contract addition).
- Bumped project version to 0.8.2.
- Added single-user login protection to the local FastAPI backend: `POST /api/v1/auth/login`/`logout`, an in-memory expiring session store, and a `require_session` dependency guarding every `/api/v1` route except login itself. Fails closed (`503 auth_not_configured`) rather than allowing unauthenticated access when `RESEARCHBOSS_API_PASSWORD` is unset. Sessions support both cookie and `Authorization: Bearer` token auth and are never persisted to YAML, SQLite, or git.
- Bumped project version to 0.8.1.
- Completed every route documented in `docs/api/CONTRACT.md` (except the disabled Future AI Routes section): conversion, metadata, data, claims, artefact creation, Zotero (read-only local and Web API, with collection selection written only to the workspace), reports, evidence export, backup, and project log routes.
- Moved Zotero workspace-config resolution (`resolve_zotero_paths`, `configured_source_root`, `configured_zotero`, `write_zotero_config`) from private `cli.py` helpers into `researchboss.engine.zotero` so the CLI and the new Zotero API routes share the same logic instead of duplicating it.
- Bumped project version to 0.8.0.
- Added `GET/POST /api/v1/sources/*`, `GET/POST /api/v1/artefacts/*`, and `GET/POST /api/v1/rqs/*` routes to the local FastAPI backend, all reusing existing tested engine functions with 404s for unknown source/artefact/RQ IDs rather than generic 400s.
- Bumped project version to 0.7.2.
- Started Phase 9 local FastAPI backend (`researchboss.api`, run with `researchboss serve`): app factory with a shared response envelope and error handling, plus `GET /health` (no workspace/auth dependency), `GET/POST /api/v1/projects/*`, and the `POST/GET /api/v1/doc/*` document-versioning routes, all reusing existing tested engine functions.
- Bumped project version to 0.7.1.
- Added Phase 8 local document vault, versioning, and restoration through `researchboss doc version/versions/diff/restore/compare`, with a `document-vault.yaml` ledger and a `document_vault/` folder for originals, versions, diffs, and manifests.
- Added automatic pre/post-change document version snapshots to `researchboss cite apply`, linking each applied citation copy to its source snapshot, validation report ID, and citation plan ID.
- Added `document_versions` SQLite sync so `researchboss db sync` indexes document vault version history.
- Bumped project version to 0.7.0.
- Added explicit SQLite tables for validation runs, evidence matches, citation plans, guideline registrations, search query history, and document version metadata.
- Bumped project version to 0.6.1.
- Added Phase 7 workspace SQLite memory, indexing, and sync through `researchboss db init/sync/status/rebuild`.
- Added reviewed SQLite-to-YAML/Markdown pending-change commands through `researchboss db apply-pending --review` and `researchboss db apply-pending --apply`.
- Added SQLite memory defaults, document aliases, bounded FTS indexes, integrity/rebuild checks, and database privacy checks.
- Bumped project version to 0.6.0.
- Added AI-assisted citation planning through `researchboss cite ai-plan --ai`, with an explicit `--full-target-document-ai` opt-in for whole-document AI use, and safe AI guideline context preparation through `researchboss guidelines ai-context --ai`.
- Added Scopus metric provenance to quality-scored external candidate reports.
- Added AI candidate validation review through `researchboss search ai-candidate-review --ai --external-search` and AI external query planning through `researchboss search ai-query-plan --ai --external-search`.
- Added AI abstract-screening reports through `researchboss ai abstract-screening --ai`, alongside explicit full-context AI opt-in gates for whole-document and whole-source-document AI use.
- Added local processing-issue reports through `researchboss processing-issues` and local abstract candidate import through `researchboss abstracts import`.
- Added local PDF merge manifests through `researchboss merge-pdfs`, deterministic sidecar metadata import through `researchboss metadata sidecars`, an explicit local OCR fallback for scanned PDFs through `researchboss convert --ocr`, optional local PDF text extractors, and deterministic filename suggestions through `researchboss metadata filename-suggestions`.
- Added accepted-source corpus export through `researchboss export-corpus`, local Zotero candidate matching, and reviewed external candidate imports through `researchboss search import-candidates`.
- Added deterministic citation plans and reviewed citation-plan application through `researchboss cite plan` and `researchboss cite apply`, expanded citation application formats, and citation candidate safety gates that require `--allow-candidate-citations` before suggesting citations from non-accepted sources.
- Added report schema guidance through `researchboss report-schemas`.
- Added guideline conflict reports through `researchboss guidelines conflicts` and guideline defaults/precedence through `researchboss guidelines defaults`.
- Added deterministic document target resolution and `researchboss validate <target>` reports with strengths, weaknesses, unsupported or weakly supported sentences, citation gaps, confidence factors, confidence scores, and APA7 references.
- Added guideline registration through `researchboss guidelines add/list`, with workspace-local snapshots, extracted text, and validated scopes.
- Bumped project version to 0.5.4.
- Added structured external-search query plans with legacy params-file import, broad/balanced/strict strategy modes, query group labels, and research-question links.
- Bumped project version to 0.5.3.
- Added Scopus quality scoring, threshold filtering, query validation reports, external-paper candidate registers, metadata-only full-text availability signals, and no-result or low-result query logs.
- Bumped project version to 0.5.2.
- Added explicit Scopus external-search foundation with query planning, query history, readiness checks, response snapshots, no-results logs, and `--external-search` opt-in.
- Added safe AI workspace reports for corpus summaries, claim-check assistance, citation-gap recommendations, artefact cross-reference, and source-relevance recommendations.
- Bumped project version to 0.5.1.
- Added AI-assisted review, novelty assessment, and research-question assessment commands behind explicit `--ai` opt-in, with local report outputs and mocked privacy-boundary tests.
- Added TODO and roadmap lists for future AI work that still makes sense to implement.
- Bumped project version to 0.5.0.
- Added Phase 5 OpenAI foundation: `researchboss ai test`, environment/`.env` key loading, explicit `--ai` live-check opt-in, safe context preview generation, and privacy-boundary tests.
- Bumped project version to 0.4.1.
- Added `docs/api/CONTRACT.md` with the planned local FastAPI boundary, endpoint groups, shared-engine expectations, read-only Zotero constraints, and disabled future AI route rules.
- Bumped project version to 0.4.0.
- Added optional read-only Zotero Web API support for credential testing, collection listing, and workspace collection selection.
- Added `ZOTERO_API_KEY` and `ZOTERO_USER_ID` placeholders to `.env.example`.
- Bumped project version to 0.3.9.
- Completed current Phase 4 offline deterministic TODO items that do not require AI or API implementation.
- Added research question templates for all project types, warning thresholds, source notes/tags, source review reports, claim status workflow, claim-source validation, structured decisions, terminology, feedback, context changelog, and local timeline reports.
- Kept pending AI/API TODO items color-marked separately.
- Bumped project version to 0.3.8.
- Completed current Phase 1, Phase 2, and Phase 3 offline deterministic TODO items that do not require AI or API implementation.
- Added scan provider validation, workspace health reports, backup dry-run inspection, DOI/citation consistency validation, metadata duplicate reports, converted-text keyword indexing, evidence bundle export, artefact review statuses, and artefact dependency checks.
- Color-marked pending TODO items that require AI implementation or API development.
- Bumped project version to 0.3.7.
- Added richer read-only local Zotero SQLite coverage for notes, tags, relations, linked items, and extra metadata fields.
- Expanded deterministic Zotero search, snapshots, metadata-quality reports, and BibTeX export to use the richer offline metadata.
- Bumped project version to 0.3.6.
- Added offline deterministic roadmap/TODO items for DOI validation, citation consistency, duplicate metadata reports, source review reports, source notes/tags, claim validation, artefact review, evidence bundle export, project-log commands, workspace health, and backup restore dry-run.
- Bumped project version to 0.3.5.
- Added deterministic `researchboss rqs check` readiness checks with local validation reports and per-question readiness metadata.
- Documented that novelty, contribution strength, field usefulness, and evidence-quality certainty remain human-review or future AI-assisted concerns.
- Bumped project version to 0.3.4.
- Added the roadmap rule that anything not safely deterministic belongs to the later AI implementation phase with explicit opt-in and privacy-boundary tests.
- Bumped project version to 0.3.3.
- Added deterministic `researchboss artefacts create` workflows for source summaries, literature review matrices, claim-evidence tables, research question briefs, and data profile summaries.
- Ensured generated artefacts are non-AI, workspace-only, exclude ignored sources by default, and require user review.
- Bumped project version to 0.3.2.
- Added strict one-way Zotero-to-ResearchBoss config flags and guards that block writes inside the local Zotero directory.
- Added roadmap notes for future explicit AI options to read whole files or directories for full-paper reasoning and artefact cross-reference workflows.
- Bumped project version to 0.3.1.
- Changed init citation style wording to Zotero-style titles, including explicit `American Psychological Association 7th edition`.
- Added read-only CSL style title parsing for local Zotero/CSL style files.
- Documented the hard rule that ResearchBoss and any future AI feature must never modify the local Zotero directory.
- Bumped project version to 0.3.0.
- Added deterministic conversion for TXT, MD, DOCX, and simple page-marked PDF text extraction.
- Added conversion cache keyed by source hash and failed conversion records under `sources_failed/`.
- Added deterministic citation metadata extraction with DOI/year/title handling and no invented metadata.
- Added local CSV, SQLite, and JSON data profiling with reports under `outputs/data-profiles/`.
- Added M.Phil and PhD research stage templates.
- Added research question list, approve, reject, and archive workflows.
- Added artefact registry commands with linked source IDs, linked research question IDs, review flags, and AI-generated flags.
- Added manual claim ledger commands and citation gap reports.
- Added local Markdown workspace report generation.
- Added one-shot source watch candidate reports for unregistered files.
- Added local workspace zip backups with original sources excluded by default.
- Added workspace config migration and schema versioning.
- Bumped project version to 0.2.0.
- Added offline Zotero SQLite metadata support through read-only immutable local database connections.
- Added Zotero parent-root config when a `storage/` folder is selected.
- Added local Zotero collection listing, selected-collection configuration, one-off collection scans, and entire-library mode.
- Added local Zotero metadata quality, attachment health, full-text cache, duplicate candidate, metadata snapshot, and BibTeX export commands.
- Enriched Zotero source records with local metadata when available.
- Extended deterministic Zotero search to score title, creators, abstract, collection paths, and DOI from local SQLite metadata.
- Bumped project version to 0.1.1.
- Added `DETAILED_ROADMAP.md` as the living 17-section implementation roadmap.
- Added an explicit current version line to the README.
- Added read-only local Zotero storage search over filenames and `.zotero-ft-cache` text without AI or Zotero API use.
- Added Zotero storage metadata to scanned source records: storage key, relative path, and full-text-cache presence.
- Updated `researchboss scan` to inherit `zotero_storage` provider mode from workspace config when `--kind` is omitted.
- Phase 2 work is planned next: TXT/MD conversion, conversion caching, and citation metadata extraction.

## 0.1.0 - 2026-07-03

Phase 1 engine and CLI foundation completed.

Added:

- Local-first workspace initialization.
- Default YAML and Markdown workspace state files.
- Source folder skeletons for original files, converted text, metadata, failed sources, artefacts, outputs, logs, and context versions.
- Typer CLI command layer with `init`, `doctor`, `version`, `status`, `config validate`, `scan`, and `sources` commands.
- Runtime readiness checks before `researchboss init` and through `researchboss doctor`.
- `python -m researchboss` entrypoint coverage.
- Local source scanning for PDF, DOCX, TXT, MD, CSV, SQLite, and DB files.
- SHA-256 hashing and duplicate detection by content hash.
- Source review states: `pending_review`, `accepted`, `maybe`, and `ignored`.
- Convenience YAML files for accepted, maybe, and ignored source IDs.
- JSONL command logs and YAML run summaries.
- Richer init wizard for research level, topic, research questions, subquestions, stakeholders, citation style, output type, data expectations, AI preference metadata, evidence/privacy preferences, and source review defaults.
- Workspace discovery when `--workspace` is omitted.
- Automatic selection when exactly one workspace is discovered.
- Numbered workspace selection and local default workspace memory when several workspaces exist.
- Concrete next-step command examples after successful init.
- MIT license and author metadata.
- README, TODO, architecture, and validation documentation for the Phase 1 baseline.

Notes:

- AI behavior is not implemented in Phase 1. Init records local AI preference metadata only and keeps AI disabled.
- Zotero support is storage-folder scanning only. Zotero API collection selection is planned for later work.
- Accepted sources are tracked locally, but downstream conversion and research workflows are planned for Phase 2 and later.
