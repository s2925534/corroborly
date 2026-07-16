# Ledgerly Local API Contract

This document defines the FastAPI boundary for Ledgerly.

Contract status: implementation started in project version `0.7.0`; every route documented below is implemented in `ledgerly.api` (run with `ledgerly serve`), including the AI Routes section (added 2026-07-16, per Pedro's explicit go-ahead — `POST /api/v1/ai/{test,review,novelty,rqs/assess,corpus-summary,claim-check,citation-gaps,artefact-cross-reference,source-relevance,abstract-screening}` and `POST /api/v1/search/{ai-query-plan,ai-candidate-review}`) and the Transcription Routes section (added 2026-07-16, per Pedro's explicit go-ahead on the subprocess integration mechanism — `/api/v1/transcription/{readiness,upload,upload/limits,jobs,jobs/{id},jobs/{id}/start}`). Novelty assessment has no deterministic engine path (`ledgerly.engine.ai.ai_novelty_assessment` is AI-only) — it lives at `POST /api/v1/ai/novelty` under the same AI opt-in and privacy-boundary rules as the rest of that section, not as a separate `/api/v1/novelty` route implying a deterministic path that doesn't exist.

The API must be local-first, workspace-scoped, and a thin transport layer over `ledgerly.engine` functions. It must not duplicate business logic already implemented in the engine.

## Non-Negotiable Boundaries

- API routes must not modify original source files.
- API routes must not write inside the local Zotero directory.
- API routes must not require cloud storage or a remote database for MVP operation.
- Zotero Web API routes must be read-only.
- Zotero write routes are forbidden.
- AI routes are future/disabled until privacy-boundary tests exist.
- API keys must not be returned, printed, or logged.
- Whole PDFs, CSV files, SQLite databases, or original documents must not be sent to AI by default.
- AI routes must never fabricate content not grounded in the user's actual accepted-source text, artefacts, claims, or own notes — see AGENTS.md's "Core Rule: No Hallucinations" (non-negotiable, applies to every AI route in this document, present and future). Insufficient evidence must produce an explicit low/no-confidence response, never a plausible-sounding guess.
- Every `/api/v1` route except `/api/v1/auth/login` must fail closed (`503 auth_not_configured`) when no login password is configured, rather than silently allowing unauthenticated access.
- The login password must never be returned, printed, or logged, and session tokens are held in server memory only — never written to YAML, SQLite, or git.
- Upload routes must reject a batch that exceeds its configured file-count limit before writing anything, never silently process a truncated subset. Individual oversized files must be reported as rejected, not silently dropped or partially written without limit.
- Upload routes must stream uploaded bytes to a bounded-size location rather than buffering an entire (potentially oversized) file in memory, and must always clean up temporary upload storage, including on failure.

## Authentication

`ledgerly serve` is a single-user local tool, not a multi-tenant service (see `TODO.md`'s multi-tenant item for the separate, larger feature that would change this for commercial deployments). Set both `LEDGERLY_API_USERNAME` and `LEDGERLY_API_PASSWORD` (env vars, or `.env` in the server's working directory) before starting the server; every `/api/v1` route except `/api/v1/auth/login` requires a valid session. `GET /health` never requires a session, so deploy/update health checks keep working regardless of login state.

### `POST /api/v1/auth/login` (implemented)

Accepts `{"username": "...", "password": "..."}`. Returns `503 auth_not_configured` if either isn't set, `401 invalid_credentials` on a wrong username or password (the two aren't distinguished in the response, to avoid confirming which one was wrong), or `200` with a session token (also set as an httponly `ledgerly_session` cookie) on success. Sessions expire after `LEDGERLY_API_SESSION_HOURS` hours (default 12) and live in server memory only, so a server restart invalidates all sessions. This is still one shared credential pair, not a per-user account system — the username field matches the login UX of a real account without implying multi-tenancy exists yet.

Engine source:

- `ledgerly.api.auth` (server-local, not a `ledgerly.engine` module — there is no workspace-scoped concept of a login)

### `POST /api/v1/auth/logout` (implemented)

Invalidates the session named by the `Authorization: Bearer <token>` header or the `ledgerly_session` cookie, and clears the cookie. No public self-registration route exists.

Callers may authenticate with either the cookie set by `/login` or an `Authorization: Bearer <token>` header carrying the same token.

## Common Conventions

Base path:

```text
/api/v1
```

Workspace selection:

- All workspace-scoped routes accept a `workspace` query parameter or a configured workspace ID later.
- Initial MVP may use absolute local workspace paths.
- Future UI layers should pass opaque workspace IDs once a project registry exists.
- When `LEDGERLY_WORKSPACE_ROOT` is set (e.g. a deployed instance pointed at a mounted NAS volume), `workspace` may be a relative path joined to that root, and every resolved workspace must fall inside it — absolute paths outside the root are rejected with `400 workspace_outside_root` rather than accepted. Without it, any path reachable by the server process is accepted, matching local-first single-user CLI behavior.

Response shape:

```json
{
  "ok": true,
  "data": {},
  "warnings": [],
  "errors": []
}
```

Error shape:

```json
{
  "ok": false,
  "data": null,
  "warnings": [],
  "errors": [
    {
      "code": "workspace_not_found",
      "message": "Workspace does not exist."
    }
  ]
}
```

## Health

### `GET /health` (implemented)

Liveness check outside `/api/v1`, with no workspace or auth dependency, so NAS deploy/update health checks succeed independently of login state.

## Projects And Workspace Routes

### `GET /api/v1/projects/status` (implemented)

Returns workspace status and source counts.

Engine source:

- `ledgerly.engine.sources.source_counts`

### `POST /api/v1/projects/init` (implemented)

Creates a local workspace. Returns `409 workspace_already_exists` if the target already contains `research-context.yaml`, rather than silently overwriting it.

Engine source:

- `ledgerly.engine.workspace.init_workspace`

Body fields mirror the CLI init fields, including project type, topic, source mode, citation style, output type, AI preference metadata, and privacy preferences.

### `GET /api/v1/projects/health` (implemented)

Returns deterministic workspace health checks.

Engine source:

- `ledgerly.engine.health.workspace_health_report`

### `GET /api/v1/projects/dashboard` (implemented)

Returns at-a-glance corpus stats for the web UI landing page: source counts by status, claim counts by status, artefact count, open (candidate + approved) research question count, and `days_since_last_activity` (derived from the newest mtime among the workspace's core YAML/Markdown files, or `null` if none exist yet).

Engine source:

- `ledgerly.engine.health.corpus_dashboard_summary`

### `GET /api/v1/projects/compare?workspaces=path1&workspaces=path2` (implemented)

Dashboard summaries (same shape as `/dashboard`, plus `workspace` and `project_name`) for two or more workspaces side by side, for anyone running more than one research project at once. Requires at least two paths (`400 too_few_workspaces` otherwise). Each path goes through the same `LEDGERLY_WORKSPACE_ROOT` sandbox validation as every other workspace route — no relaxed handling just because there are several of them.

Engine source:

- `ledgerly.engine.health.corpus_dashboard_summary` (called once per workspace)

## Source Routes

### `GET /api/v1/sources` (implemented)

Lists sources, optionally filtered by status.

Engine source:

- `ledgerly.engine.sources.list_sources`

### `POST /api/v1/sources/scan` (implemented)

Scans local folders or Zotero storage.

Engine source:

- `ledgerly.engine.sources.scan_sources`

Allowed providers:

- `local_folder`
- `zotero_storage`

### `POST /api/v1/sources/{source_id}/status` (implemented)

Sets source review status.

Engine source:

- `ledgerly.engine.sources.set_source_status`

Allowed statuses:

- `accepted`
- `ignored`
- `maybe`

### `POST /api/v1/sources/{source_id}/note` (implemented)

Sets a local note for a source.

Engine source:

- `ledgerly.engine.sources.set_source_note`

### `POST /api/v1/sources/{source_id}/tags` (implemented)

Adds a manual tag to a source.

Engine source:

- `ledgerly.engine.sources.add_source_tag`

### `GET /api/v1/sources/report` (implemented)

Returns source review report data.

Engine source:

- `ledgerly.engine.sources.source_review_report`

### `GET /api/v1/sources/watch` (implemented)

Detects unregistered files in the configured source folder without registering them — run `POST /api/v1/sources/scan` afterwards to register any candidates found.

Engine source:

- `ledgerly.engine.watch.write_watch_report`

## Conversion And Metadata Routes

### `POST /api/v1/conversion/run` (implemented)

Converts registered sources to local text.

Engine source:

- `ledgerly.engine.conversion.convert_sources`

### `GET /api/v1/conversion/ocr-readiness` (implemented)

Checks local OCR tool (`tesseract`/`pdftoppm`) availability without processing any document.

Engine source:

- `ledgerly.engine.conversion.ocr_readiness_report`

### `GET /api/v1/conversion/processing-issues` (implemented)

Returns skipped/failed conversion issues without modifying original files.

Engine source:

- `ledgerly.engine.conversion.processing_issue_report`

### `POST /api/v1/metadata/extract` (implemented)

Extracts deterministic citation metadata.

Engine source:

- `ledgerly.engine.metadata.extract_citation_metadata`

### `GET /api/v1/metadata/validate` (implemented)

Returns citation consistency and DOI validation results.

Engine source:

- `ledgerly.engine.metadata_quality.citation_consistency_report`

### `GET /api/v1/metadata/duplicates` (implemented)

Returns duplicate metadata candidates.

Engine source:

- `ledgerly.engine.metadata_quality.duplicate_metadata_report`

### `POST /api/v1/metadata/index` (implemented)

Builds a local keyword index over converted text.

Engine source:

- `ledgerly.engine.metadata_quality.build_keyword_index`

## Data Routes

### `POST /api/v1/data/profile` (implemented)

Profiles local CSV, SQLite, DB, and JSON sources.

Engine source:

- `ledgerly.engine.data.profile_data_sources`

### `GET /api/v1/data` (implemented)

Lists local data sources.

Engine source:

- `ledgerly.engine.data.list_data_sources`

### `GET /api/v1/data/status` (implemented)

Returns data profile counts.

Engine source:

- `ledgerly.engine.data.data_source_counts`

## Research Question Routes

### `GET /api/v1/rqs` (implemented)

Lists approved, candidate, and rejected research questions.

Engine source:

- `ledgerly.engine.research_questions.list_research_questions`

### `POST /api/v1/rqs/check` (implemented)

Runs deterministic research question readiness checks.

Engine source:

- `ledgerly.engine.research_questions.check_research_question_readiness`

### `POST /api/v1/rqs/{rq_id}/approve` (implemented)

Approves a candidate research question.

Engine source:

- `ledgerly.engine.research_questions.approve_research_question`

### `POST /api/v1/rqs/{rq_id}/reject` (implemented)

Rejects a research question.

Engine source:

- `ledgerly.engine.research_questions.reject_research_question`

### `POST /api/v1/rqs/{rq_id}/archive` (implemented)

Archives a research question.

Engine source:

- `ledgerly.engine.research_questions.archive_research_question`

## Stage Routes (implemented, 2026-07-17)

### `GET /api/v1/stages` (implemented)

Lists research stages (from the project-type template written at `init`) with their `status` and optional `target_date`.

Engine source: `ledgerly.engine.research_stages.list_stages`.

### `POST /api/v1/stages/{stage_id}/status` (implemented)

Sets a stage's status. `400 invalid_stage_status` for an unrecognized value (`not_started`/`in_progress`/`blocked`/`done`); `404 invalid_stage_status` for an unknown `stage_id`.

Engine source: `ledgerly.engine.research_stages.set_stage_status`.

### `POST /api/v1/stages/{stage_id}/target-date` (implemented)

Sets (or, with `target_date: null`, clears) a stage's optional target completion date (`YYYY-MM-DD`). `400 invalid_stage_target_date` for an invalid date string or unknown `stage_id` (404 for the latter).

Engine source: `ledgerly.engine.research_stages.set_stage_target_date`.

### `GET /api/v1/stages/ics` (implemented)

Returns a `text/calendar` (RFC 5545 `.ics`) document with one all-day `VEVENT` per stage that has a `target_date` set — a standard file format a user's own calendar app can import or subscribe to, no new external service. Stages without a target date are omitted, never guessed at. Hand-written generation (stdlib only, no new dependency).

Engine source: `ledgerly.engine.research_stages.stages_ics`.

CLI equivalents: `ledgerly stages list/status/target-date/ics`.

## Claim Routes

### `GET /api/v1/claims` (implemented)

Lists claims.

Engine source:

- `ledgerly.engine.claims.list_claims`

### `POST /api/v1/claims` (implemented)

Adds a manual claim.

Engine source:

- `ledgerly.engine.claims.add_claim`

### `POST /api/v1/claims/{claim_id}/status` (implemented)

Sets claim review status.

Engine source:

- `ledgerly.engine.claims.set_claim_status`

### `GET /api/v1/claims/gaps` (implemented)

Returns citation gap report data.

Engine source:

- `ledgerly.engine.claims.write_citation_gap_report`

### `GET /api/v1/claims/validate` (implemented)

Validates that claims link only to existing accepted sources.

Engine source:

- `ledgerly.engine.claims.claim_source_validation_report`

### `GET /api/v1/claims/stale?days=14` (implemented)

Returns open claims (`active`/`needs_evidence`/`needs_review`) not updated in at least `days` days, each flagged with `age_days` and whether it's also a citation gap (`is_citation_gap`). Claims from before `created_at`/`updated_at` tracking existed have no confirmed age and are always included rather than assumed fresh.

Engine source:

- `ledgerly.engine.claims.write_stale_claims_report`

### `GET /api/v1/claims/duplicates?threshold=0.85` (implemented, 2026-07-17)

Deterministic (non-AI) near-duplicate claim detection: every pair of claims whose text similarity ratio (`difflib.SequenceMatcher`, stdlib) meets or exceeds `threshold` (0 exclusive to 1 inclusive; `400 invalid_duplicate_threshold` outside that range). Flags pairs for human merge/dismiss review only — never merges, edits, or changes any claim itself.

Response `data`: `{version, threshold, generated_at, duplicate_pair_count, pairs: [{claim_id_a, claim_id_b, similarity, text_a, text_b}]}`, highest similarity first.

Engine source:

- `ledgerly.engine.claims.write_duplicate_claims_report`

CLI equivalent: `ledgerly claims duplicates --threshold`.

## Artefact Routes

### `GET /api/v1/artefacts` (implemented)

Lists artefacts.

Engine source:

- `ledgerly.engine.artefacts.list_artefacts`

### `POST /api/v1/artefacts` (implemented)

Registers a local artefact.

Engine source:

- `ledgerly.engine.artefacts.register_artefact`

### `POST /api/v1/artefacts/create` (implemented)

Creates deterministic non-AI artefacts. `artefact_type` is one of `source-summary-report`, `literature-review-matrix`, `claim-evidence-table`, `research-question-brief`, `data-profile-summary`, `paper-draft`. `paper-draft` (Phase 28) requires `rq_id` — a deterministic, AI-free paper skeleton scoped to one research question (hypothesis statement, background/literature review from accepted sources, evidence assembled from claims linked to that RQ, and an explicitly unfinished conclusion placeholder — claims are never auto-classified as supporting/refuting the hypothesis, since that's a judgment call, not deterministic extraction).

Engine source:

- `ledgerly.engine.artefact_creation.create_deterministic_artefact`

### `POST /api/v1/artefacts/{artefact_id}/review` (implemented)

Sets artefact review status.

Engine source:

- `ledgerly.engine.artefacts.set_artefact_review_status`

### `GET /api/v1/artefacts/dependencies` (implemented)

Checks artefact links against accepted sources and approved research questions.

Engine source:

- `ledgerly.engine.artefacts.artefact_dependency_report`

### `POST /api/v1/artefacts/upload` (implemented)

Batch-uploads externally created artefact files (multipart form data, field name `files`) into the document vault. Rejects the whole batch with `400 upload_batch_too_large` if it exceeds `LEDGERLY_UPLOAD_MAX_FILES` (default 25) before writing anything; each file is capped at `LEDGERLY_UPLOAD_MAX_FILE_SIZE_MB` (default 50) and must have an extension from `ledgerly.engine.sources.ALLOWED_EXTENSIONS`. Returns a per-batch report (`processed`/`accepted`/`duplicate`/`rejected`/`failed` counts and per-file rows), also persisted to `outputs/validation/upload-batch-report.yaml`. Duplicate detection is by content hash against artefacts already uploaded in the workspace. Uploaded bytes are streamed to a size-bounded temporary file and the temp directory is always removed after the request, whether it succeeds or fails.

Engine source:

- `ledgerly.engine.vault.intake_uploaded_artefact_batch`

### `GET /api/v1/artefacts/cross-reference` (implemented)

Proposes deterministic links between an uploaded artefact (by `upload_id`) and existing artefacts, sources, and claims, based on shared keyword tokens from titles and filenames (claim matches require a stronger overlap, since claim text is long and generic). Read-only: writes a candidate report to `outputs/recommendations/cross-reference-<upload_id>.yaml` but never modifies any artefact, source, or claim record.

Engine source:

- `ledgerly.engine.cross_reference.cross_reference_candidates`

CLI equivalent: `ledgerly doc cross-reference <upload_id>`.

### `POST /api/v1/artefacts/cross-reference/candidate-review` (implemented)

Sets one candidate's `review_status` (`needs_human_review`/`accepted`/`approved`/`rejected`, identified by `target_kind`+`target_id` in the JSON body, `upload_id` as a query param) in the persisted candidates report. `cross_reference_candidates`/`apply_cross_reference_links` were designed around a human hand-editing the report YAML on disk, which a browser-based reviewer has no way to do — found missing during Phase 10 UI planning for the cross-reference review overlay (see the Phase 10 TODO items). Citation plans had the identical gap; see `POST /api/v1/citations/plan/insertion-review` below, added the same way. `404 cross_reference_review_failed` for an unknown `upload_id` or an unmatched candidate; `400 cross_reference_review_failed` for an invalid `review_status` value.

Named `candidate-review`, not `review` — `POST /api/v1/artefacts/cross-reference/review` would have satisfied `POST /api/v1/artefacts/{artefact_id}/review`'s path pattern (`artefact_id` literally `"cross-reference"`), and since that route is registered first, FastAPI would validate against the wrong request body (`ArtefactReviewRequest`) and never reach this handler. Caught by a live smoke test returning an unexpected `422`, not by a naming preference.

Engine source:

- `ledgerly.engine.cross_reference.set_cross_reference_candidate_review_status`

CLI equivalent: `ledgerly doc cross-reference-review <upload_id> <target_kind> <target_id> <review_status>`.

### `POST /api/v1/artefacts/cross-reference/apply` (implemented)

Writes reviewed cross-reference candidates as metadata on the *upload* record — a `cross_references` list, mirroring how artefact records already track `linked_sources`/`linked_research_questions` — following the same review-before-apply pattern citation plans use: only candidates whose `review_status` in the persisted candidates report has been set to `accepted`/`approved` (via `candidate-review` above, or by hand-editing the report file directly) are applied. Deliberately does not insert text into any artefact, source, or claim document's content (the other reading of "write the link" this contract previously left open): a keyword-overlap match is weaker evidence than a validated missing-citation match, so auto-inserting text on that basis would be a worse default than recording it as reviewable metadata. Content insertion analogous to `cite apply` (needing per-format `.md`/`.docx`/`.pdf` handling) was considered and deliberately not chosen. Idempotent — re-applying does not duplicate already-recorded links.

CLI equivalent: `ledgerly doc cross-reference-apply <upload_id>`.

Engine source:

- `ledgerly.engine.cross_reference.apply_cross_reference_links`

### `GET /api/v1/artefacts/uploads` (implemented)

Lists artefacts previously uploaded into the document vault. Found missing during Phase 10 UI planning: `POST /api/v1/artefacts/upload` returns a batch report at upload time, but nothing let a web client re-list uploads after that (e.g. on a page reload) — the CLI already had this via `ledgerly doc uploads`.

Engine source:

- `ledgerly.engine.vault.list_uploaded_artefacts`

CLI equivalent: `ledgerly doc uploads`.

### `GET /api/v1/artefacts/uploads/{upload_id}/file` (implemented)

Serves the raw bytes of an uploaded artefact's renamed vault copy, for a browser preview (modal/`<iframe>`/`<img>`), not download — `Content-Disposition: inline` is set explicitly. Found missing alongside the route above: no route in this contract served raw file bytes at all (everything else returns the JSON envelope), which would have blocked the popup preview view (see the Phase 10 TODO items) regardless of which UI framework Phase 10 picks. Media type is resolved from a fixed extension map matching `sources.ALLOWED_EXTENSIONS` rather than `mimetypes.guess_type` (platform-dependent, notably for `.md`). `404 upload_file_unavailable` for an unknown `upload_id`; `400 upload_file_unavailable` if the ledger's recorded path has gone missing or no longer resolves inside `document_vault/` (defense against a hand-edited ledger pointing outside the vault — see `vault.resolve_uploaded_artefact_file`'s docstring). Read-only; never modifies the file. Note: `sources.ALLOWED_EXTENSIONS` (shared with source-folder scanning) does not currently include image extensions, so an image-file preview is not yet reachable through the upload pipeline this route serves — that gap belongs to the upload extension allow-list, not this route.

Engine source:

- `ledgerly.engine.vault.resolve_uploaded_artefact_file`

No CLI equivalent — the CLI already has direct filesystem access to `vault_renamed_path` from `ledgerly doc uploads`; this route exists only because a browser client cannot read the local filesystem directly.

## Zotero Routes

### `GET /api/v1/zotero/local/collections` (implemented)

Lists collections from local `zotero.sqlite`.

Engine source:

- `ledgerly.engine.zotero.list_zotero_collections`

### `GET /api/v1/zotero/local/search` (implemented)

Searches local Zotero storage and local metadata.

Engine source:

- `ledgerly.engine.zotero.search_zotero_storage`

### `POST /api/v1/zotero/local/collections/select` (implemented)

Configures selected local Zotero collections for future scans — the local-storage equivalent of `POST /api/v1/zotero/api/collections/select` below. Rejects unknown collection keys with `404 unknown_collection_keys` (validated against `list_zotero_collections`) rather than silently accepting them. Mirrors `ledgerly zotero select-collections` exactly.

Engine source:

- `ledgerly.engine.zotero.write_zotero_config`, `list_zotero_collections`

### `POST /api/v1/zotero/local/use-entire-library` (implemented)

Configures local Zotero scans to use the entire storage library. Mirrors `ledgerly zotero use-entire-library`.

Engine source:

- `ledgerly.engine.zotero.write_zotero_config`

### `GET /api/v1/zotero/local/metadata-report` (implemented)

Reports missing local Zotero metadata fields (title/year/DOI/creators) from read-only `zotero.sqlite`.

Engine source:

- `ledgerly.engine.zotero.metadata_quality_report`

### `GET /api/v1/zotero/local/attachment-health` (implemented)

Compares local Zotero storage files against attachment records in `zotero.sqlite` — missing files, unlinked storage files.

Engine source:

- `ledgerly.engine.zotero.attachment_health_report`

### `GET /api/v1/zotero/local/fulltext-report` (implemented)

Reports which local Zotero storage files have `.zotero-ft-cache` available.

Engine source:

- `ledgerly.engine.zotero.fulltext_availability_report`

### `GET /api/v1/zotero/local/duplicates` (implemented)

Finds possible local Zotero metadata duplicates by DOI or title/year.

Engine source:

- `ledgerly.engine.zotero.duplicate_metadata_candidates`

### `GET /api/v1/zotero/local/snapshot` (implemented)

Writes a reproducible local Zotero metadata snapshot into the workspace (`sources_metadata/zotero-snapshot.yaml`) and returns it.

Engine source:

- `ledgerly.engine.zotero.zotero_metadata_snapshot`

### `GET /api/v1/zotero/local/export-bibtex` (implemented)

Exports conservative BibTeX from local Zotero SQLite metadata to `outputs/reports/zotero-references.bib`.

Engine source:

- `ledgerly.engine.zotero.export_bibtex_from_metadata`

### `POST /api/v1/zotero/api/credentials` (implemented)

Links a Zotero Web API account by saving `api_key`/`user_id` (request body) into the workspace's local `.env`, replacing hand-editing that file. Added 2026-07-16 so the web UI can link an account the same way the CLI's new `ledgerly zotero api-link` does.

Request body: `{"api_key": string, "user_id": string}`.

Response `data`: `{"configured": true}` only — the submitted key and user ID are never echoed back, logged, or returned by this or any other route. Call `GET /api/v1/zotero/api/test` afterwards to verify the saved credentials actually work.

Engine source:

- `ledgerly.engine.zotero_api.save_zotero_api_credentials`

### `DELETE /api/v1/zotero/api/credentials` (implemented)

Unlinks a Zotero Web API account by removing `ZOTERO_API_KEY`/`ZOTERO_USER_ID` from the workspace's local `.env`, leaving every other line untouched.

Response `data`: `{"configured": false}`.

Engine source:

- `ledgerly.engine.zotero_api.clear_zotero_api_credentials`

### `GET /api/v1/zotero/api/test` (implemented)

Tests Zotero Web API credentials without exposing the key.

Engine source:

- `ledgerly.engine.zotero_api.zotero_api_readiness`

### `GET /api/v1/zotero/api/collections` (implemented)

Lists Zotero Web API collections using read-only credentials.

Engine source:

- `ledgerly.engine.zotero_api.zotero_api_collections`

### `POST /api/v1/zotero/api/collections/select` (implemented)

Stores selected Zotero Web API collection keys in workspace config.

Rules:

- This route writes only to the Ledgerly workspace.
- It must not modify Zotero.
- It must not call Zotero write endpoints.

## Document Vault Routes

### `POST /api/v1/doc/version` (implemented)

Snapshots a target document into the local document vault.

Engine source:

- `ledgerly.engine.vault.create_document_version`

### `GET /api/v1/doc/versions` (implemented)

Lists document vault versions, optionally filtered by target.

Engine source:

- `ledgerly.engine.vault.list_document_versions`

### `GET /api/v1/doc/diff` (implemented)

Compares two document vault versions.

Engine source:

- `ledgerly.engine.vault.diff_document_versions`

### `POST /api/v1/doc/restore` (implemented)

Restores a document vault version as a new copy without overwriting the current document.

Engine source:

- `ledgerly.engine.vault.restore_document_version`

### `GET /api/v1/doc/compare` (implemented)

Compares how document strengths, weaknesses, unsupported claims, and references changed between two versions, when both versions have a linked validation report.

Engine source:

- `ledgerly.engine.vault.compare_document_versions`

### `POST /api/v1/doc/derive-text/{version_id}` (implemented)

Builds (or rebuilds) a derived text snapshot for a document version: sections (from `.md` heading structure only — see engine source docstring for why `.txt`/`.docx`/`.pdf` get no section detection rather than a guessed one), paragraphs with character offsets, and sentences with a `citation_insertion_anchor`, `claim_ids` (claims whose text appears in the sentence), and `reference_ids` (source IDs from this version's linked validation report, when one exists). Anchors are derived fresh from this version's content and are not correlated with any other version's anchors, but are deterministic and stable across repeated calls for the same version. Written to `document_vault/derived_text/<version_id>.yaml`.

Engine source:

- `ledgerly.engine.derived_text.build_derived_text_snapshot`

## Validation Routes

### `POST /api/v1/validation/run` (implemented)

Deterministically validates a document target against accepted sources, Zotero-derived sources, and explicitly supplied source paths. Never sends anything to AI and never modifies the target document.

Engine source:

- `ledgerly.engine.doc_validation.validate_document`

## Citation Plan Routes

### `POST /api/v1/citations/plan` (implemented)

Creates a reviewable, non-destructive citation insertion plan from a validation run's missing-citation findings. Only suggests citations from `accepted` sources unless `allow_candidate_citations` is set.

Request body accepts an optional `citation_style` (`"apa7"` default, or `"mla"`/`"chicago"`/`"ieee"`, added 2026-07-17) controlling both the plan's `suggested_inline_citation` markers and its `references` reference-list formatting. `400 invalid_citation_style` for any other value. `apa7` output is byte-identical to before this field existed; the other three styles are deliberately simplified, common approximations (`ledgerly.engine.references`), not full style-guide-compliant implementations — the plan's `limitations` list says so explicitly for any non-`apa7` style, matching this project's practice of never presenting output as more authoritative than it is. `ieee` assigns running reference numbers (`[1]`, `[2]`, ...) by order of first appearance in the document, stable per plan generation.

Engine source:

- `ledgerly.engine.citations.create_citation_plan`

CLI equivalent: `ledgerly cite plan <target>`.

### `POST /api/v1/citations/plan/insertion-review` (implemented)

Sets one citation-plan insertion's `review_status` (`needs_human_review`/`accepted`/`approved`/`rejected`, identified by `sentence_index`+`source_id` — the same pair `create_citation_plan` builds each insertion from) in the persisted plan file, without hand-editing it. Mirrors `POST /api/v1/artefacts/cross-reference/candidate-review` — same gap (a browser-based reviewer has no filesystem access to hand-edit the plan YAML), same fix. `404 citation_insertion_review_failed` for an unknown target/plan or an unmatched insertion; `400 citation_insertion_review_failed` for an invalid `review_status` value.

Engine source:

- `ledgerly.engine.citations.set_citation_plan_insertion_review_status`

CLI equivalent: `ledgerly cite review <target> <sentence_index> <source_id> <review_status>`.

### `POST /api/v1/citations/apply` (implemented)

Applies a reviewed citation plan's accepted insertions to a revised output copy — never edits the original document in place. Automatically snapshots the pre-apply document and the applied copy into the document vault (see Document Vault Routes), linking the applied version to its validation report and citation plan IDs.

Engine source:

- `ledgerly.engine.citations.apply_citation_plan`

## Guideline Routes

### `GET /api/v1/guidelines` (implemented)

Lists registered guidelines.

Engine source:

- `ledgerly.engine.guidelines.list_guidelines`

### `POST /api/v1/guidelines` (implemented)

Registers a local file or remote URL guideline, snapshotting it and extracting text inside the workspace only.

Engine source:

- `ledgerly.engine.guidelines.register_guideline`

### `POST /api/v1/guidelines/defaults` (implemented)

Sets the workspace's default guideline IDs and their precedence order, applied automatically by validation and citation planning unless overridden.

Engine source:

- `ledgerly.engine.guidelines.set_default_guidelines`

### `GET /api/v1/guidelines/conflicts` (implemented)

Returns a deterministic report of contradictory guideline requirements for human review.

Engine source:

- `ledgerly.engine.guidelines.guideline_conflict_report`

## SQLite Sync Status Routes

### `POST /api/v1/db/init` (implemented)

Initializes the optional workspace SQLite index database.

Engine source:

- `ledgerly.engine.database.init_database`

### `POST /api/v1/db/sync` (implemented)

Syncs workspace YAML/Markdown metadata into the local SQLite index. YAML and Markdown remain the source of truth.

Engine source:

- `ledgerly.engine.database.sync_database`

### `GET /api/v1/db/status` (implemented)

Returns SQLite index health, sync counts, and repair guidance.

Engine source:

- `ledgerly.engine.database.database_status`

### `POST /api/v1/db/rebuild` (implemented)

Rebuilds the SQLite index from workspace YAML/Markdown source-of-truth files.

Engine source:

- `ledgerly.engine.database.rebuild_database`

### `GET /api/v1/db/pending` (implemented)

Returns SQLite-to-file pending changes for review, without applying them.

Engine source:

- `ledgerly.engine.database.pending_changes_report`

### `POST /api/v1/db/apply-pending` (implemented)

Reviews (`apply: false`) or applies (`apply: true`) reviewed SQLite-to-YAML/Markdown pending changes. SQLite-to-file write-back is never silent.

Engine source:

- `ledgerly.engine.database.apply_pending_changes`

### `GET /api/v1/db/privacy` (implemented)

Checks that the SQLite database does not intentionally store secrets or original documents.

Engine source:

- `ledgerly.engine.database.database_privacy_report`

### `GET /api/v1/db/search?query=...&limit=20` (implemented)

Full-text keyword search across the whole corpus (converted source text, artefact text, guideline text, claims, accepted-source references, research questions, personal notes/meeting notes/transcripts) using SQLite FTS5 (`fts_index_search`, Phase 7). The index itself was built by Phase 7 but never queried anywhere until now; personal notes were also missing from the indexed document set entirely and are now included. Each whitespace-separated word in `query` is quoted as a literal phrase token internally, so ordinary words containing FTS5 operator characters (`-`, `:`, unbalanced `"`) behave like plain keyword search instead of raising an FTS5 syntax error — this is a keyword search box for researchers, not an FTS5 query language exposed to end users. Never auto-creates or activates the SQLite index — if it doesn't exist yet, returns `status: "not_indexed"` with a hint to run `db sync` first, per AGENTS.md's opt-in-cache rule for SQLite. The `status: "invalid_query"` path is a defensive fallback for cases the term-quoting doesn't cover, not something ordinary input should trigger.

Engine source:

- `ledgerly.engine.database.search_corpus`

### Secondary database backend routes (implemented, Phase 24)

Optional MariaDB/PostgreSQL backend mirroring the SQLite cache, per Pedro's explicit 2026-07-16 go-ahead. SQLite stays the always-on, zero-config default; these routes only matter when `LEDGERLY_DB_BACKEND` is configured, and even then nothing activates automatically — see AGENTS.md's Privacy Rules. `ledgerly.engine.db_backends/` holds the abstraction (`base.py` for the shared mirror/repopulate row-copy logic, `postgres.py`/`mariadb.py` for connection + schema DDL, `config.py` for env var resolution). Ten tables are mirrored (`sync_files`, `pending_changes`, `memory_entries`, `search_queries`, `validation_runs`, `evidence_matches`, `citation_plans`, `guideline_registrations`, `document_versions`, `document_aliases`) — deliberately excludes SQLite's FTS5 virtual table (`fts_index`/`fts_index_search`), which has no direct cross-engine equivalent and is trivially rebuilt via `db sync` regardless of which backend is primary.

- `GET /api/v1/db/backend-status` — whether a secondary backend is configured (env vars present), active (opted in), and currently reachable. Read-only; never activates anything.
- `POST /api/v1/db/activate-backend` — explicit opt-in: creates the schema on the configured backend and mirrors the current SQLite cache into it. `400 secondary_backend_activation_failed` if nothing is configured, or if a *different* backend is already active (at most one at a time — deactivate first).
- `POST /api/v1/db/deactivate-backend` — stops mirroring. Does not delete data already written to either side.
- `POST /api/v1/db/repair-sqlite` — bidirectional repair, direction 1: the local SQLite file went missing. Recreates it and repopulates from the active secondary backend. `400 sqlite_repair_failed` if no backend is active.
- `POST /api/v1/db/repair-backend` — bidirectional repair, direction 2: the active backend was unreachable or lost data. Re-mirrors it from the current SQLite cache (reuses the same row-copy logic `db sync` already calls, not a second sync engine). `400 secondary_backend_repair_failed` if no backend is active.

`db sync`/`db rebuild` also mirror to the active secondary backend automatically as their last step (`report.secondary_backend: {backend, status: "mirrored"|"unreachable", ...}` in the response) — an unreachable secondary backend is reported, not a `db sync` failure, since the real source of truth (workspace YAML/Markdown → SQLite) already succeeded by that point.

Engine source:

- `ledgerly.engine.database.secondary_backend_status`
- `ledgerly.engine.database.activate_secondary_backend`
- `ledgerly.engine.database.deactivate_secondary_backend`
- `ledgerly.engine.database.repair_sqlite_from_secondary`
- `ledgerly.engine.database.repair_secondary_from_sqlite`

## Notes Routes

Personal notes, meeting notes, and transcripts — the user's own working material, distinct from per-source notes (`POST /api/v1/sources/{source_id}/note`) and supervisor/stakeholder feedback (`POST /api/v1/feedback`). Stored as plain workspace YAML (`personal-notes.yaml`) like everything else; never sent anywhere until a future AI feature explicitly opts this note type in (see AGENTS.md's "Core Rule: No Hallucinations" and `TODO.md` Phase 25 — the AI-assisted review half of that phase is not implemented). Added 2026-07-16.

### `GET /api/v1/notes` (implemented)

Lists notes, optionally filtered by `kind` (`note`/`meeting`/`transcript`) and/or `tag`.

Engine source:

- `ledgerly.engine.notes.list_notes`

### `POST /api/v1/notes` (implemented)

Adds a note. Body: `{"text": string, "kind": "note"|"meeting"|"transcript" = "note", "tags": string[] = [], "source_label": string = ""}`.

Engine source:

- `ledgerly.engine.notes.add_note`

### `POST /api/v1/notes/{note_id}/tags` (implemented)

Adds a tag to an existing note.

Engine source:

- `ledgerly.engine.notes.add_note_tag`

### `GET /api/v1/notes/search` (implemented)

Deterministic keyword search across note text, tags, and source label — plain substring matching, no AI.

Engine source:

- `ledgerly.engine.notes.search_notes`

### `POST /api/v1/notes/import-transcript` (implemented)

Deterministically imports a transcript export (plain text, VTT, or SRT) from a server-local file path into the note store — strips WebVTT/SRT cue numbers and timestamp lines only, no AI processing at import time.

Engine source:

- `ledgerly.engine.notes.import_transcript`

## Transcription Routes (implemented, Phase 30)

Audio/video transcription via a sibling SourceScribe checkout, invoked as a subprocess (never imported — `LEDGERLY_SOURCESCRIBE_PATH` points at the checkout). Local Whisper is the default backend; SourceScribe's own optional OpenAI backend is only ever used when a job explicitly sets `"ai": true`, matching AGENTS.md's "Core Rule: No Hallucinations" opt-in requirement. Synchronous only — `POST .../jobs/{job_id}/start` blocks until SourceScribe finishes; no background-job model exists yet. On completion, the transcript is imported into the Phase 25 notes store via `ledgerly.engine.notes.import_transcript` (no AI processing on the transcript text itself). Added 2026-07-16.

### `GET /api/v1/transcription/readiness` (implemented)

Reports whether a SourceScribe checkout is configured and reachable, without starting any job.

Engine source:

- `ledgerly.engine.transcription.sourcescribe_readiness_report`

### `GET /api/v1/transcription/upload/limits` (implemented)

Reports the configured single-file upload size limit (`LEDGERLY_TRANSCRIBE_MAX_FILE_SIZE_MB`, default 500MB) and the allowed audio/video extensions.

### `GET /api/v1/transcription/jobs` (implemented)

Lists all transcription jobs for the workspace.

Engine source:

- `ledgerly.engine.transcription.list_transcription_jobs`

### `GET /api/v1/transcription/jobs/{job_id}` (implemented)

Returns a single transcription job's current status and details. 404 if unknown.

Engine source:

- `ledgerly.engine.transcription.get_transcription_job`

### `POST /api/v1/transcription/upload` (implemented)

Uploads a single audio/video file (multipart, field name `file`) and registers a new `pending` transcription job. Rejects unsupported extensions or oversized files with 400. A single-file route, not a batch like the artefact upload route — each transcription job runs its own subprocess and produces its own note.

Engine source:

- `ledgerly.engine.transcription.upload_transcription_source`

### `POST /api/v1/transcription/jobs/{job_id}/start` (implemented)

Synchronously runs SourceScribe on an uploaded job. Body: `{"language": string | null, "ai": bool = false, "prompt": string | null}`. Returns the updated job record (`status` becomes `completed` or `failed`; `note_id` set on success). 404 for an unknown or non-startable job; 503 if SourceScribe is not configured/reachable.

Engine source:

- `ledgerly.engine.transcription.start_transcription`

## External Search Routes

Deterministic external-search query planning, report regeneration, and reviewed-candidate import. These never call an external API themselves — they operate on local candidate registers already populated by the CLI's `search scopus`/`search scopus-test` commands (which require the explicit `--external-search` opt-in and aren't exposed as web routes). AI-assisted query planning/candidate review (`search ai-query-plan`, `search ai-candidate-review`) stay CLI-only, blocked on the same AI opt-in decision as Phase 22. Added 2026-07-16.

### `POST /api/v1/search/plan` (implemented)

Generates a deterministic external-search query plan from workspace context (topic, approved research questions) without calling any external API. Body: `{"max_queries": int = 20, "strategy": "broad"|"balanced"|"strict" = "balanced", "params_file": string|null = null, "unused_only": bool = false}`.

Engine source:

- `ledgerly.engine.external_search.generate_search_query_plan`
- `ledgerly.engine.external_search.filter_unused_queries` (when `unused_only: true`)

### `GET /api/v1/search/reports?limit=50` (implemented)

Regenerates the five deterministic external-search reports (high-signal candidates, duplicates, Zotero matches, evidence validation, run comparison) from local candidate registers. `limit` caps the high-signal candidate count.

Engine source:

- `ledgerly.engine.external_search.write_high_signal_candidate_report`
- `ledgerly.engine.external_search.external_candidate_deduplication_report`
- `ledgerly.engine.external_search.external_candidate_zotero_match_report`
- `ledgerly.engine.external_search.external_search_evidence_validation_report`
- `ledgerly.engine.external_search.external_search_run_comparison_report`

### `POST /api/v1/search/import-candidates` (implemented)

Imports reviewed external candidates into the source register as metadata-only pending-review sources. Body: `{"candidate_ids": string[]}`. Returns `400 search_import_candidates_failed` if the candidate register doesn't exist yet or no IDs were given.

Engine source:

- `ledgerly.engine.external_search.import_external_candidates`

## Abstracts Routes

### `POST /api/v1/abstracts/import` (implemented)

Imports local legacy Scopus-export abstract text files (`.txt`) from a server-local folder into a reviewable candidate register. Body: `{"folder": string}`. Returns `404 abstracts_folder_not_found` if the folder doesn't exist.

Engine source:

- `ledgerly.engine.abstracts.import_abstract_folder`

## Report And Export Routes

### `GET /api/v1/reports/workspace` (implemented)

Generates local Markdown workspace report.

Engine source:

- `ledgerly.engine.reports.generate_workspace_report`

### `GET /api/v1/reports/timeline` (implemented)

Generates a local, chronologically sorted timeline report merging run summaries, decisions, terminology changes, feedback, and context-changelog entries — each event carries an `at` timestamp. Events from before per-record timestamps existed (older workspaces) have no confirmed time (`at: null`) and sort last rather than being guessed at.

Engine source:

- `ledgerly.engine.project_log.timeline_report`

### `GET /api/v1/reports/schemas` (implemented)

Writes report schema and human-review guideline documentation (YAML + Markdown).

Engine source:

- `ledgerly.engine.report_schemas.export_report_schemas`

### `GET /api/v1/reports/citation-relationships` (implemented)

Local citation-relationship view: which sources support which claims, and which sources/research questions each artefact draws on. No claim-artefact edge is reported since claims don't currently link to artefacts in the data model (only sources and research questions do) — that would be a schema change, not a view change.

Engine source:

- `ledgerly.engine.relationships.citation_relationship_map`

### `GET /api/v1/reports/research-progress` (implemented)

A lightweight, honest local record of research question / artefact activity over time (approvals, rejections, archiving, artefact registration, artefact review-status changes) — not a gamified streak feature, just what happened and when. Backed by an append-only `research-progress-log.yaml` written by the research-question and artefact lifecycle functions themselves, not derived after the fact from data that was never timestamped.

Engine source:

- `ledgerly.engine.progress_log.research_progress_report`

### `GET /api/v1/reports/digest?mark_seen=true` (implemented, 2026-07-17)

A proactive "what changed since you were last here" summary: new/updated claims (via the claim ledger's `created_at`/`updated_at`) and project-log activity (run summaries, decisions, terminology, feedback, context changes, via the same data `/timeline` already aggregates) since the workspace's stored `last_visited_at`, plus the current stale-open-claims count. `is_first_visit: true` (with `last_visited_at: null`) when the workspace has never been visited before. By default, computing the digest also marks the workspace visited now (`mark_seen=false` computes without updating the timestamp, a read-only peek). Honestly scoped: sources and personal notes have no timestamp field anywhere in this codebase, so new-source/new-note activity isn't reflected here.

Engine source:

- `ledgerly.engine.digest.since_last_visit_digest`
- `ledgerly.engine.digest.mark_visited`

CLI equivalent: `ledgerly digest [--no-mark-visited]`.

### `POST /api/v1/export/evidence` (implemented)

Creates an offline evidence bundle without original source files by default.

Engine source:

- `ledgerly.engine.export.export_evidence_bundle`

### `POST /api/v1/export/corpus` (implemented)

Exports accepted converted source text as a combined local corpus with a manifest.

Engine source:

- `ledgerly.engine.export.export_accepted_source_corpus`

### `POST /api/v1/export/supervisor-bundle` (implemented)

Builds a single "hand this to my supervisor" bundle: a claim-ledger table (with citation-gap and claim-source-validation flags per claim), every citation plan created so far, the workspace review report, and (added 2026-07-17) an "AI Usage Disclosure" section built from the AI-usage audit ledger (`ledgerly.engine.ai.list_ai_usage`) — a factual summary of which AI features were invoked, whether each actually called a provider or correctly refused with insufficient evidence, and grounding pass/fail counts — as one readable Markdown digest (`supervisor-bundle.md`) plus a zip (`supervisor-bundle.zip`) also containing the raw claims YAML, the raw AI-usage ledger YAML, per-plan Markdown, and (added 2026-07-17) a fully self-contained `supervisor-bundle.html` (inline CSS only, no external assets or JS) with the same content, openable by double-click with no Ledgerly install or Markdown renderer needed. Markdown + zip rather than PDF: no PDF-generation dependency exists in this project, and the digest converts to PDF trivially with any tool the user already has.

Engine source:

- `ledgerly.engine.export.build_supervisor_bundle`

### `POST /api/v1/export/merge-pdfs` (implemented)

Creates accepted-source PDF merge manifests and, when `write: true` is passed (mirroring the CLI's `--write` flag), a merged PDF artefact. Defaults to `write: false` (manifest reports only, no PDF written).

Engine source:

- `ledgerly.engine.pdf_merge.pdf_merge_report`

### `POST /api/v1/backup` (implemented)

Creates a local backup.

Engine source:

- `ledgerly.engine.backup.create_workspace_backup`

### `GET /api/v1/backup/inspect` (implemented)

Inspects a backup zip without restoring it.

Engine source:

- `ledgerly.engine.backup.inspect_backup`

## Project Log Routes

Every category here has both a `GET` list route and a `POST` add route. The `GET` routes were added 2026-07-16, alongside the web UI's Project Log panel — until then this area was POST-only with no way to read anything back via the API (the CLI had the same gap; `decisions list`/`terminology list`/`feedback list`/`context list` were added at the same time).

### `GET /api/v1/decisions` (implemented)

Lists recorded decisions as structured `{id, decision, reason}` records, parsed from `decisions.md`.

Engine source:

- `ledgerly.engine.project_log.list_decisions`

### `POST /api/v1/decisions` (implemented)

Adds a structured local decision.

Engine source:

- `ledgerly.engine.project_log.add_decision`

### `GET /api/v1/terminology` (implemented)

Lists glossary terms as `{term, definition}` records.

Engine source:

- `ledgerly.engine.project_log.list_terminology`

### `POST /api/v1/terminology` (implemented)

Adds or updates a glossary term.

Engine source:

- `ledgerly.engine.project_log.add_terminology`

### `GET /api/v1/feedback` (implemented)

Lists supervisor/stakeholder feedback as `{id, source, text, status}` records.

Engine source:

- `ledgerly.engine.project_log.list_feedback`

### `POST /api/v1/feedback` (implemented)

Adds supervisor or stakeholder feedback.

Engine source:

- `ledgerly.engine.project_log.add_feedback`

### `GET /api/v1/context/changelog` (implemented)

Lists context changelog items as `{id, text}` records, parsed from `context-changelog.md`.

Engine source:

- `ledgerly.engine.project_log.list_context_changes`

### `POST /api/v1/context/changelog` (implemented)

Adds a context changelog item.

Engine source:

- `ledgerly.engine.project_log.add_context_change`

## Web UI Routes (implemented)

`ledgerly/web/` mounts a server-rendered HTML shell onto the same FastAPI app as everything above — same process, same `ledgerly serve`, no separate deployment step. These routes serve HTML (or static files), not the `{"ok","data","warnings","errors"}` envelope, and are outside `/api/v1`, but the Non-Negotiable Boundaries above still apply in full: the web layer has no import path to `ledgerly.engine` at all (`ledgerly/web/app.py` only imports session-cookie helpers from `ledgerly.api.auth`, plus Jinja2/Starlette), and every data operation happens client-side via `fetch()` calls to the `/api/v1/*` routes documented above — the web UI is architecturally just another API client, enforced by import structure rather than convention.

- `GET /login` — public, no session required. Serves the login form; the form itself posts to `POST /api/v1/auth/login`.
- `GET /` — the app shell. Session-gated *server-side*: reads the session cookie directly and issues a `303` redirect to `/login?next=<url>` before rendering anything if there's no valid session, rather than sending an empty shell that discovers it's unauthenticated only after a client-side API call. Workspace selection is a `?workspace=` query param, mirroring how every `/api/v1/*` route already takes an explicit `workspace` — there is no server-side session-scoped "current workspace."
- `GET /static/*` — `app.js` (vanilla JS, no framework, no bundler) and `styles.css` (hand-written, no CSS framework). No CDN dependency anywhere, consistent with this project staying usable offline.

## AI Routes

**Implemented** (2026-07-16, per Pedro's explicit go-ahead to build the web/API opt-in layer). Modeled directly on the equivalent CLI commands and their `ledgerly.engine.ai` functions — a thin pass-through, no new business logic. Every route requires the per-request `"ai": true` opt-in described below; there is no workspace-level or session-level AI toggle that bypasses it, mirroring the CLI's per-invocation `--ai` flag exactly.

Every route in this section shares the same server-side credential rule: the OpenAI API key is resolved server-side only, the same way the CLI resolves it (`OPENAI_API_KEY` env var, or `.env` in the workspace via `engine.ai.openai_credentials`). **No route accepts an API key in the request body or from the client** — that would hand a browser client the ability to exfiltrate or misuse server-side credentials, a straight OWASP-relevant boundary violation, not just a style preference. If the key is missing, the route returns `503 openai_not_configured` rather than a generic 500 or a raw exception message.

Every route also shares the same safe-context boundary already enforced by `engine.ai.build_safe_context`: original files, whole PDFs/CSVs/SQLite databases, and full documents are excluded by construction — only per-source excerpts capped at `max_excerpt_chars` are sent. None of these routes needs a `--full-file-ai`/`--directory-ai`-style extra opt-in, because none of their CLI equivalents use one, with two explicit exceptions below (`ai-query-plan`, `ai-candidate-review`) that need an *additional* `external_search: true` opt-in, matching their CLI's `--ai --external-search`.

Common response envelope fields most routes share (already returned by every `engine.ai` function): `version`, `kind`, `provider` (`"openai"`), `model`, `ai_used`, `requires_user_review`, `safe_context_policy` (echoes `build_safe_context`'s `policy` block), `limits` (echoes `max_sources`/`max_excerpt_chars` actually applied), `source_count`, `response_id` (the OpenAI response id, for audit trail — never the raw response body), `grounding` (see below). None of these routes modify any artefact, source, or claim document; where the CLI equivalent writes a side-effect file (novelty ledger), the route below says so explicitly. Unlike the CLI, no route writes an `outputs/` YAML file — the caller receives the same content in the response body and decides whether to persist it.

Per AGENTS.md's "Core Rule: No Hallucinations," every `engine.ai` function also returns `insufficient_evidence: bool` and, when true, `insufficient_evidence_reason: string`: when the safe context has no source with a usable excerpt (or, for the workspace-report routes, when the whole payload — sources, claims, artefacts, and abstract/external candidates — is empty), the function returns this immediately with `ai_used: false`, `response_id: null`, and `grounding: null` **without calling OpenAI at all**. Every route below inherits this for free.

**Grounding-check mechanism** (implemented 2026-07-16, `ledgerly.engine.grounding`, TODO.md Phase 27): every prompt built by `engine.ai` (review, novelty, RQ assessment, all 8 workspace-report kinds, citation-plan review) appends a fixed instruction requiring the model to mark every factual assertion with an inline citation of the exact form `[[source:<id>]]`, `[[claim:<id>]]`, `[[artefact:<id>]]`, or `[[note:<id>]]`, using only IDs that were actually present in the context sent to it. After the response comes back, `validate_grounding` deterministically (no second AI call) checks every marker found against the real IDs that were genuinely available for that request and returns:

```json
{
  "version": 1,
  "citations_found": 2,
  "grounded_citations": [{"type": "source", "id": "src-001"}],
  "ungrounded_citations": [{"type": "source", "id": "src-999"}],
  "fully_grounded": false,
  "uncited_paragraph_count": 1,
  "uncited_paragraphs": ["A sentence with no citation marker at all."]
}
```

`fully_grounded: false` means at least one citation marker referenced an ID the model was never actually given — the concrete, auditable signal that a claim traces back to real workspace state rather than being self-asserted (AGENTS.md Core Rule item 2). `uncited_paragraph_count` is a softer coverage signal (content with no citation marker at all, excluding markdown headings) surfaced for human review, not a hard failure. `grounding` is `null` only when `insufficient_evidence: true` (no text was generated to check). Clients should treat a non-`fully_grounded` or non-zero-`uncited_paragraph_count` response the same way the CLI does: print/display a visible warning alongside `requires_user_review`, never silently accept the text. Still not implemented: chunk-level (paragraph/sentence anchor, not whole-excerpt) citation precision — that's a larger, separate piece (`engine/derived_text.py` anchors, AGENTS.md Core Rule item 6) tracked for Phase 31's per-suggestion source popups, not claimed here.

### `POST /api/v1/ai/test` (implemented)

CLI equivalent: `ledgerly ai test`. Engine source: `engine.ai.openai_readiness`.

Request body: `{"ai": bool = false}` — `ai: true` additionally performs a live `GET /models` credential check against OpenAI (mirrors the CLI's `--ai` flag meaning "allow a live check", not "allow AI use" in this one case, since checking readiness doesn't send any workspace content). `ai: false` (or omitted) checks key/config presence only, with no outbound request.

Response `data`: `{key_loaded, key_exposed: false, workspace_ai_enabled, openai_provider_enabled, default_model, live_request_performed, policy: "explicit_ai_flag_required"}`, plus `api_reachable` and `model_count` when `live_request_performed` is true.

### `POST /api/v1/ai/review` (implemented)

CLI equivalent: `ledgerly ai review --ai`. Engine source: `engine.ai.ai_assisted_review`.

Request body: `{"ai": true, "max_sources": int = 10, "max_excerpt_chars": int = 1200}`. `400 ai_not_enabled` if `ai` is not `true`.

Response `data`: common envelope fields above, plus `review` (markdown text with sections Scope, Useful Signals, Evidence Gaps, Source Follow-up, Human Review Required).

### `POST /api/v1/ai/novelty` (implemented)

CLI equivalent: `ledgerly assess-novelty --ai`. Engine source: `engine.ai.ai_novelty_assessment`. This is the route that resolves the "novelty assessment has no deterministic engine path" note at the top of this document — `ai_novelty_assessment` is AI-only, so novelty assessment lives under `/api/v1/ai/`, not as a separate `/api/v1/novelty` route implying a deterministic engine path that doesn't exist.

Request body: `{"ai": true, "max_sources": int = 10, "max_excerpt_chars": int = 1200}`. `400 ai_not_enabled` if `ai` is not `true`.

Response `data`: common envelope fields, plus `novelty_not_proven: true` (the assessment must never be presented as proof of novelty), `research_question_count`, `assessment` (markdown text). Side effect: like the CLI, appends a record to `novelty-ledger.yaml` (`id`, `kind`, `provider`, `model`, `response_id`, `requires_user_review`, `novelty_not_proven`, `source_count`, `research_question_count`, `assessment`) — skipped when the response is `insufficient_evidence`.

### `POST /api/v1/ai/rqs/assess` (implemented)

CLI equivalent: `ledgerly rqs assess --ai [--rq <id>]`. Engine source: `engine.ai.ai_research_question_assessment`.

Request body: `{"ai": true, "rq_id": Optional[str] = None, "max_sources": int = 10, "max_excerpt_chars": int = 1200}`. `400 ai_not_enabled` if `ai` is not `true`. `404 ai_rq_assessment_failed` if `rq_id` is supplied but matches no approved or candidate research question (mirrors `OpenAiError(f"Unknown research question: {rq_id}")`).

Response `data`: common envelope fields, plus `novelty_not_proven: true`, `research_question_count` (count actually assessed — all approved+candidate questions when `rq_id` is omitted, else the one matched question), `rq_id` (echoes the request), `assessment` (markdown text, one section per assessed research question plus a final Human Review Required section).

### Workspace-report routes (implemented)

Six thin wrappers around `engine.ai.ai_workspace_report` with a fixed `kind`, one per `ledgerly ai <name>` CLI command. Request body for all six: `{"ai": true, "max_sources": int = 10, "max_excerpt_chars": int = 1200}`. Response `data`: common envelope fields, plus `report` (markdown text) and the same claim/artefact/candidate counts the CLI's own report carries.

- `POST /api/v1/ai/corpus-summary` — CLI: `ledgerly ai corpus-summary --ai`.
- `POST /api/v1/ai/claim-check` — CLI: `ledgerly ai claim-check --ai`.
- `POST /api/v1/ai/citation-gaps` — CLI: `ledgerly ai citation-gaps --ai`.
- `POST /api/v1/ai/artefact-cross-reference` — CLI: `ledgerly ai artefact-cross-reference --ai`.
- `POST /api/v1/ai/source-relevance` — CLI: `ledgerly ai source-relevance --ai`.
- `POST /api/v1/ai/abstract-screening` — CLI: `ledgerly ai abstract-screening --ai`.

### `GET /api/v1/ai/usage-log` (implemented, 2026-07-17)

CLI equivalent: `ledgerly ai usage-log`. Engine source: `engine.ai.list_ai_usage`. The AI-usage audit ledger (TODO.md Phase 32): every call any `engine.ai` function makes gets one entry (`_record_ai_usage`), including calls that correctly refused via `insufficient_evidence` — a single place to answer "when was AI used on this workspace, and was it grounded" without needing to know which individual feature happens to persist its own side-effect file. **Requires no `ai: true` opt-in** — unlike every other route in this section, this one never calls an AI provider itself; it only reads an already-local YAML file.

Response `data`: a list of `{id, timestamp, kind, ai_used, insufficient_evidence, model, response_id, requires_user_review, grounding_fully_grounded}` entries, oldest first. `grounding_fully_grounded` is `null` for `insufficient_evidence` entries (no text was generated to check).

### `POST /api/v1/search/ai-query-plan` (implemented)

CLI equivalent: `ledgerly search ai-query-plan --ai --external-search`. Engine source: `engine.ai.ai_workspace_report` (`kind="query_generation"`). Lives under `/api/v1/search/`, not `/api/v1/ai/`, matching the CLI's own `search` command group.

Request body: `{"ai": true, "external_search": true, "max_sources": int = 10, "max_excerpt_chars": int = 1200}`. Requires **both** opt-ins: `400 ai_not_enabled` if `ai` is not `true`, `400 external_search_not_enabled` if `external_search` is not `true` (checked after `ai`).

Response `data`: common envelope fields, plus `report` (markdown text: suggested queries, refinement rationale, excluded unsafe context, search budget notes). Never executes any external search itself.

### `POST /api/v1/search/ai-candidate-review` (implemented)

CLI equivalent: `ledgerly search ai-candidate-review --ai --external-search [--full-source-document-ai]`. Engine source: `engine.ai.ai_workspace_report` (`kind="candidate_validation"`).

Request body: `{"ai": true, "external_search": true, "full_source_document_ai": bool = false, "max_sources": int = 10, "max_excerpt_chars": int = 1200}`. Requires both `ai` and `external_search`; `full_source_document_ai` is a separate, optional third opt-in that only changes the response's `full_text_mode` field — the underlying context is candidate metadata/abstracts either way (no CLI or engine path today actually sends full source documents for this kind).

Response `data`: common envelope fields, plus `report`, `full_source_document_ai_opt_in` (echoes the request), `full_text_mode` (`"explicit_opt_in"` or `"metadata_and_abstracts_only"`).

Rules (all AI routes):

- Must require the per-request `ai: true` opt-in described above; there is no workspace-level or session-level AI toggle that bypasses it.
- Must never log or echo the API key.
- Must never upload whole PDFs, CSVs, SQLite databases, or original documents — only `build_safe_context` excerpts, capped at the requested `max_excerpt_chars`.
- Must preserve the Zotero no-write boundary.
- Must return the response's `requires_user_review: true` field on every success response that isn't `insufficient_evidence` — these are advisory outputs, never auto-applied.
- Must return the `grounding` field described above on every response and must never silently drop a non-`fully_grounded` result — clients must be able to detect and surface an ungrounded/fabricated citation.

## Forbidden Routes

The following route classes must not be added:

- Zotero write routes.
- Routes that write into Zotero storage.
- Routes that delete original source files.
- Routes that require a remote database for MVP operation.
- Routes that sync to Dropbox, Google Drive, OneDrive, SharePoint, AWS, Azure, Firebase, Supabase, or similar services for MVP operation.

## Required Tests Before Implementation

Before a route group is marked implemented, tests must prove that:

- The route calls shared `ledgerly.engine` behavior instead of duplicating business logic in the API layer.
- Workspace writes are limited to Ledgerly workspace files.
- Original source files are not modified.
- Local Zotero directories are never modified.
- Zotero Web API routes use read-only operations only.
- Missing or invalid API keys are handled without printing or logging secrets.
- Any AI route requires the per-request `ai: true` opt-in and never calls the AI provider when the safe context has no usable evidence (`insufficient_evidence: true` instead).
