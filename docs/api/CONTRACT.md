# ResearchBoss Local API Contract

This document defines the FastAPI boundary for ResearchBoss.

Contract status: implementation started in project version `0.7.0`; every route documented below is now implemented in `researchboss.api` (run with `researchboss serve`) except the disabled Future AI Routes section, which is a shape-only planning sketch (see that section) covering `POST /api/v1/ai/{test,review,novelty,rqs/assess}`. Novelty assessment has no deterministic engine path (`researchboss.engine.ai.ai_novelty_assessment` is AI-only) — it belongs at `POST /api/v1/ai/novelty` under the same AI opt-in and privacy-boundary rules as the rest of that section, not as a separate `/api/v1/novelty` route implying a deterministic path that doesn't exist.

The API must be local-first, workspace-scoped, and a thin transport layer over `researchboss.engine` functions. It must not duplicate business logic already implemented in the engine.

## Non-Negotiable Boundaries

- API routes must not modify original source files.
- API routes must not write inside the local Zotero directory.
- API routes must not require cloud storage or a remote database for MVP operation.
- Zotero Web API routes must be read-only.
- Zotero write routes are forbidden.
- AI routes are future/disabled until privacy-boundary tests exist.
- API keys must not be returned, printed, or logged.
- Whole PDFs, CSV files, SQLite databases, or original documents must not be sent to AI by default.
- Every `/api/v1` route except `/api/v1/auth/login` must fail closed (`503 auth_not_configured`) when no login password is configured, rather than silently allowing unauthenticated access.
- The login password must never be returned, printed, or logged, and session tokens are held in server memory only — never written to YAML, SQLite, or git.
- Upload routes must reject a batch that exceeds its configured file-count limit before writing anything, never silently process a truncated subset. Individual oversized files must be reported as rejected, not silently dropped or partially written without limit.
- Upload routes must stream uploaded bytes to a bounded-size location rather than buffering an entire (potentially oversized) file in memory, and must always clean up temporary upload storage, including on failure.

## Authentication

`researchboss serve` is a single-user local tool, not a multi-tenant service. Set `RESEARCHBOSS_API_PASSWORD` (env var, or `.env` in the server's working directory) before starting the server; every `/api/v1` route except `/api/v1/auth/login` requires a valid session. `GET /health` never requires a session, so deploy/update health checks keep working regardless of login state.

### `POST /api/v1/auth/login` (implemented)

Accepts `{"password": "..."}`. Returns `503 auth_not_configured` if no password is set, `401 invalid_credentials` on a wrong password, or `200` with a session token (also set as an httponly `researchboss_session` cookie) on success. Sessions expire after `RESEARCHBOSS_API_SESSION_HOURS` hours (default 12) and live in server memory only, so a server restart invalidates all sessions.

Engine source:

- `researchboss.api.auth` (server-local, not a `researchboss.engine` module — there is no workspace-scoped concept of a login)

### `POST /api/v1/auth/logout` (implemented)

Invalidates the session named by the `Authorization: Bearer <token>` header or the `researchboss_session` cookie, and clears the cookie. No public self-registration route exists.

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
- When `RESEARCHBOSS_WORKSPACE_ROOT` is set (e.g. a deployed instance pointed at a mounted NAS volume), `workspace` may be a relative path joined to that root, and every resolved workspace must fall inside it — absolute paths outside the root are rejected with `400 workspace_outside_root` rather than accepted. Without it, any path reachable by the server process is accepted, matching local-first single-user CLI behavior.

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

- `researchboss.engine.sources.source_counts`

### `POST /api/v1/projects/init` (implemented)

Creates a local workspace. Returns `409 workspace_already_exists` if the target already contains `research-context.yaml`, rather than silently overwriting it.

Engine source:

- `researchboss.engine.workspace.init_workspace`

Body fields mirror the CLI init fields, including project type, topic, source mode, citation style, output type, AI preference metadata, and privacy preferences.

### `GET /api/v1/projects/health` (implemented)

Returns deterministic workspace health checks.

Engine source:

- `researchboss.engine.health.workspace_health_report`

## Source Routes

### `GET /api/v1/sources` (implemented)

Lists sources, optionally filtered by status.

Engine source:

- `researchboss.engine.sources.list_sources`

### `POST /api/v1/sources/scan` (implemented)

Scans local folders or Zotero storage.

Engine source:

- `researchboss.engine.sources.scan_sources`

Allowed providers:

- `local_folder`
- `zotero_storage`

### `POST /api/v1/sources/{source_id}/status` (implemented)

Sets source review status.

Engine source:

- `researchboss.engine.sources.set_source_status`

Allowed statuses:

- `accepted`
- `ignored`
- `maybe`

### `POST /api/v1/sources/{source_id}/note` (implemented)

Sets a local note for a source.

Engine source:

- `researchboss.engine.sources.set_source_note`

### `POST /api/v1/sources/{source_id}/tags` (implemented)

Adds a manual tag to a source.

Engine source:

- `researchboss.engine.sources.add_source_tag`

### `GET /api/v1/sources/report` (implemented)

Returns source review report data.

Engine source:

- `researchboss.engine.sources.source_review_report`

## Conversion And Metadata Routes

### `POST /api/v1/conversion/run` (implemented)

Converts registered sources to local text.

Engine source:

- `researchboss.engine.conversion.convert_sources`

### `POST /api/v1/metadata/extract` (implemented)

Extracts deterministic citation metadata.

Engine source:

- `researchboss.engine.metadata.extract_citation_metadata`

### `GET /api/v1/metadata/validate` (implemented)

Returns citation consistency and DOI validation results.

Engine source:

- `researchboss.engine.metadata_quality.citation_consistency_report`

### `GET /api/v1/metadata/duplicates` (implemented)

Returns duplicate metadata candidates.

Engine source:

- `researchboss.engine.metadata_quality.duplicate_metadata_report`

### `POST /api/v1/metadata/index` (implemented)

Builds a local keyword index over converted text.

Engine source:

- `researchboss.engine.metadata_quality.build_keyword_index`

## Data Routes

### `POST /api/v1/data/profile` (implemented)

Profiles local CSV, SQLite, DB, and JSON sources.

Engine source:

- `researchboss.engine.data.profile_data_sources`

### `GET /api/v1/data` (implemented)

Lists local data sources.

Engine source:

- `researchboss.engine.data.list_data_sources`

### `GET /api/v1/data/status` (implemented)

Returns data profile counts.

Engine source:

- `researchboss.engine.data.data_source_counts`

## Research Question Routes

### `GET /api/v1/rqs` (implemented)

Lists approved, candidate, and rejected research questions.

Engine source:

- `researchboss.engine.research_questions.list_research_questions`

### `POST /api/v1/rqs/check` (implemented)

Runs deterministic research question readiness checks.

Engine source:

- `researchboss.engine.research_questions.check_research_question_readiness`

### `POST /api/v1/rqs/{rq_id}/approve` (implemented)

Approves a candidate research question.

Engine source:

- `researchboss.engine.research_questions.approve_research_question`

### `POST /api/v1/rqs/{rq_id}/reject` (implemented)

Rejects a research question.

Engine source:

- `researchboss.engine.research_questions.reject_research_question`

### `POST /api/v1/rqs/{rq_id}/archive` (implemented)

Archives a research question.

Engine source:

- `researchboss.engine.research_questions.archive_research_question`

## Claim Routes

### `GET /api/v1/claims` (implemented)

Lists claims.

Engine source:

- `researchboss.engine.claims.list_claims`

### `POST /api/v1/claims` (implemented)

Adds a manual claim.

Engine source:

- `researchboss.engine.claims.add_claim`

### `POST /api/v1/claims/{claim_id}/status` (implemented)

Sets claim review status.

Engine source:

- `researchboss.engine.claims.set_claim_status`

### `GET /api/v1/claims/gaps` (implemented)

Returns citation gap report data.

Engine source:

- `researchboss.engine.claims.write_citation_gap_report`

### `GET /api/v1/claims/validate` (implemented)

Validates that claims link only to existing accepted sources.

Engine source:

- `researchboss.engine.claims.claim_source_validation_report`

## Artefact Routes

### `GET /api/v1/artefacts` (implemented)

Lists artefacts.

Engine source:

- `researchboss.engine.artefacts.list_artefacts`

### `POST /api/v1/artefacts` (implemented)

Registers a local artefact.

Engine source:

- `researchboss.engine.artefacts.register_artefact`

### `POST /api/v1/artefacts/create` (implemented)

Creates deterministic non-AI artefacts.

Engine source:

- `researchboss.engine.artefact_creation.create_deterministic_artefact`

### `POST /api/v1/artefacts/{artefact_id}/review` (implemented)

Sets artefact review status.

Engine source:

- `researchboss.engine.artefacts.set_artefact_review_status`

### `GET /api/v1/artefacts/dependencies` (implemented)

Checks artefact links against accepted sources and approved research questions.

Engine source:

- `researchboss.engine.artefacts.artefact_dependency_report`

### `POST /api/v1/artefacts/upload` (implemented)

Batch-uploads externally created artefact files (multipart form data, field name `files`) into the document vault. Rejects the whole batch with `400 upload_batch_too_large` if it exceeds `RESEARCHBOSS_UPLOAD_MAX_FILES` (default 25) before writing anything; each file is capped at `RESEARCHBOSS_UPLOAD_MAX_FILE_SIZE_MB` (default 50) and must have an extension from `researchboss.engine.sources.ALLOWED_EXTENSIONS`. Returns a per-batch report (`processed`/`accepted`/`duplicate`/`rejected`/`failed` counts and per-file rows), also persisted to `outputs/validation/upload-batch-report.yaml`. Duplicate detection is by content hash against artefacts already uploaded in the workspace. Uploaded bytes are streamed to a size-bounded temporary file and the temp directory is always removed after the request, whether it succeeds or fails.

Engine source:

- `researchboss.engine.vault.intake_uploaded_artefact_batch`

### `GET /api/v1/artefacts/cross-reference` (implemented)

Proposes deterministic links between an uploaded artefact (by `upload_id`) and existing artefacts, sources, and claims, based on shared keyword tokens from titles and filenames (claim matches require a stronger overlap, since claim text is long and generic). Read-only: writes a candidate report to `outputs/recommendations/cross-reference-<upload_id>.yaml` but never modifies any artefact, source, or claim record.

Engine source:

- `researchboss.engine.cross_reference.cross_reference_candidates`

CLI equivalent: `researchboss doc cross-reference <upload_id>`.

### `POST /api/v1/artefacts/cross-reference/candidate-review` (implemented)

Sets one candidate's `review_status` (`needs_human_review`/`accepted`/`approved`/`rejected`, identified by `target_kind`+`target_id` in the JSON body, `upload_id` as a query param) in the persisted candidates report. `cross_reference_candidates`/`apply_cross_reference_links` were designed around a human hand-editing the report YAML on disk, which a browser-based reviewer has no way to do — found missing during Phase 10 UI planning for the cross-reference review overlay (see the Phase 10 TODO items). Citation plans had the identical gap; see `POST /api/v1/citations/plan/insertion-review` below, added the same way. `404 cross_reference_review_failed` for an unknown `upload_id` or an unmatched candidate; `400 cross_reference_review_failed` for an invalid `review_status` value.

Named `candidate-review`, not `review` — `POST /api/v1/artefacts/cross-reference/review` would have satisfied `POST /api/v1/artefacts/{artefact_id}/review`'s path pattern (`artefact_id` literally `"cross-reference"`), and since that route is registered first, FastAPI would validate against the wrong request body (`ArtefactReviewRequest`) and never reach this handler. Caught by a live smoke test returning an unexpected `422`, not by a naming preference.

Engine source:

- `researchboss.engine.cross_reference.set_cross_reference_candidate_review_status`

CLI equivalent: `researchboss doc cross-reference-review <upload_id> <target_kind> <target_id> <review_status>`.

### `POST /api/v1/artefacts/cross-reference/apply` (implemented)

Writes reviewed cross-reference candidates as metadata on the *upload* record — a `cross_references` list, mirroring how artefact records already track `linked_sources`/`linked_research_questions` — following the same review-before-apply pattern citation plans use: only candidates whose `review_status` in the persisted candidates report has been set to `accepted`/`approved` (via `candidate-review` above, or by hand-editing the report file directly) are applied. Deliberately does not insert text into any artefact, source, or claim document's content (the other reading of "write the link" this contract previously left open): a keyword-overlap match is weaker evidence than a validated missing-citation match, so auto-inserting text on that basis would be a worse default than recording it as reviewable metadata. Content insertion analogous to `cite apply` (needing per-format `.md`/`.docx`/`.pdf` handling) was considered and deliberately not chosen. Idempotent — re-applying does not duplicate already-recorded links.

CLI equivalent: `researchboss doc cross-reference-apply <upload_id>`.

Engine source:

- `researchboss.engine.cross_reference.apply_cross_reference_links`

### `GET /api/v1/artefacts/uploads` (implemented)

Lists artefacts previously uploaded into the document vault. Found missing during Phase 10 UI planning: `POST /api/v1/artefacts/upload` returns a batch report at upload time, but nothing let a web client re-list uploads after that (e.g. on a page reload) — the CLI already had this via `researchboss doc uploads`.

Engine source:

- `researchboss.engine.vault.list_uploaded_artefacts`

CLI equivalent: `researchboss doc uploads`.

### `GET /api/v1/artefacts/uploads/{upload_id}/file` (implemented)

Serves the raw bytes of an uploaded artefact's renamed vault copy, for a browser preview (modal/`<iframe>`/`<img>`), not download — `Content-Disposition: inline` is set explicitly. Found missing alongside the route above: no route in this contract served raw file bytes at all (everything else returns the JSON envelope), which would have blocked the popup preview view (see the Phase 10 TODO items) regardless of which UI framework Phase 10 picks. Media type is resolved from a fixed extension map matching `sources.ALLOWED_EXTENSIONS` rather than `mimetypes.guess_type` (platform-dependent, notably for `.md`). `404 upload_file_unavailable` for an unknown `upload_id`; `400 upload_file_unavailable` if the ledger's recorded path has gone missing or no longer resolves inside `document_vault/` (defense against a hand-edited ledger pointing outside the vault — see `vault.resolve_uploaded_artefact_file`'s docstring). Read-only; never modifies the file. Note: `sources.ALLOWED_EXTENSIONS` (shared with source-folder scanning) does not currently include image extensions, so an image-file preview is not yet reachable through the upload pipeline this route serves — that gap belongs to the upload extension allow-list, not this route.

Engine source:

- `researchboss.engine.vault.resolve_uploaded_artefact_file`

No CLI equivalent — the CLI already has direct filesystem access to `vault_renamed_path` from `researchboss doc uploads`; this route exists only because a browser client cannot read the local filesystem directly.

## Zotero Routes

### `GET /api/v1/zotero/local/collections` (implemented)

Lists collections from local `zotero.sqlite`.

Engine source:

- `researchboss.engine.zotero.list_zotero_collections`

### `GET /api/v1/zotero/local/search` (implemented)

Searches local Zotero storage and local metadata.

Engine source:

- `researchboss.engine.zotero.search_zotero_storage`

### `GET /api/v1/zotero/api/test` (implemented)

Tests Zotero Web API credentials without exposing the key.

Engine source:

- `researchboss.engine.zotero_api.zotero_api_readiness`

### `GET /api/v1/zotero/api/collections` (implemented)

Lists Zotero Web API collections using read-only credentials.

Engine source:

- `researchboss.engine.zotero_api.zotero_api_collections`

### `POST /api/v1/zotero/api/collections/select` (implemented)

Stores selected Zotero Web API collection keys in workspace config.

Rules:

- This route writes only to the ResearchBoss workspace.
- It must not modify Zotero.
- It must not call Zotero write endpoints.

## Document Vault Routes

### `POST /api/v1/doc/version` (implemented)

Snapshots a target document into the local document vault.

Engine source:

- `researchboss.engine.vault.create_document_version`

### `GET /api/v1/doc/versions` (implemented)

Lists document vault versions, optionally filtered by target.

Engine source:

- `researchboss.engine.vault.list_document_versions`

### `GET /api/v1/doc/diff` (implemented)

Compares two document vault versions.

Engine source:

- `researchboss.engine.vault.diff_document_versions`

### `POST /api/v1/doc/restore` (implemented)

Restores a document vault version as a new copy without overwriting the current document.

Engine source:

- `researchboss.engine.vault.restore_document_version`

### `GET /api/v1/doc/compare` (implemented)

Compares how document strengths, weaknesses, unsupported claims, and references changed between two versions, when both versions have a linked validation report.

Engine source:

- `researchboss.engine.vault.compare_document_versions`

### `POST /api/v1/doc/derive-text/{version_id}` (implemented)

Builds (or rebuilds) a derived text snapshot for a document version: sections (from `.md` heading structure only — see engine source docstring for why `.txt`/`.docx`/`.pdf` get no section detection rather than a guessed one), paragraphs with character offsets, and sentences with a `citation_insertion_anchor`, `claim_ids` (claims whose text appears in the sentence), and `reference_ids` (source IDs from this version's linked validation report, when one exists). Anchors are derived fresh from this version's content and are not correlated with any other version's anchors, but are deterministic and stable across repeated calls for the same version. Written to `document_vault/derived_text/<version_id>.yaml`.

Engine source:

- `researchboss.engine.derived_text.build_derived_text_snapshot`

## Validation Routes

### `POST /api/v1/validation/run` (implemented)

Deterministically validates a document target against accepted sources, Zotero-derived sources, and explicitly supplied source paths. Never sends anything to AI and never modifies the target document.

Engine source:

- `researchboss.engine.doc_validation.validate_document`

## Citation Plan Routes

### `POST /api/v1/citations/plan` (implemented)

Creates a reviewable, non-destructive citation insertion plan from a validation run's missing-citation findings. Only suggests citations from `accepted` sources unless `allow_candidate_citations` is set.

Engine source:

- `researchboss.engine.citations.create_citation_plan`

CLI equivalent: `researchboss cite plan <target>`.

### `POST /api/v1/citations/plan/insertion-review` (implemented)

Sets one citation-plan insertion's `review_status` (`needs_human_review`/`accepted`/`approved`/`rejected`, identified by `sentence_index`+`source_id` — the same pair `create_citation_plan` builds each insertion from) in the persisted plan file, without hand-editing it. Mirrors `POST /api/v1/artefacts/cross-reference/candidate-review` — same gap (a browser-based reviewer has no filesystem access to hand-edit the plan YAML), same fix. `404 citation_insertion_review_failed` for an unknown target/plan or an unmatched insertion; `400 citation_insertion_review_failed` for an invalid `review_status` value.

Engine source:

- `researchboss.engine.citations.set_citation_plan_insertion_review_status`

CLI equivalent: `researchboss cite review <target> <sentence_index> <source_id> <review_status>`.

### `POST /api/v1/citations/apply` (implemented)

Applies a reviewed citation plan's accepted insertions to a revised output copy — never edits the original document in place. Automatically snapshots the pre-apply document and the applied copy into the document vault (see Document Vault Routes), linking the applied version to its validation report and citation plan IDs.

Engine source:

- `researchboss.engine.citations.apply_citation_plan`

## Guideline Routes

### `GET /api/v1/guidelines` (implemented)

Lists registered guidelines.

Engine source:

- `researchboss.engine.guidelines.list_guidelines`

### `POST /api/v1/guidelines` (implemented)

Registers a local file or remote URL guideline, snapshotting it and extracting text inside the workspace only.

Engine source:

- `researchboss.engine.guidelines.register_guideline`

### `POST /api/v1/guidelines/defaults` (implemented)

Sets the workspace's default guideline IDs and their precedence order, applied automatically by validation and citation planning unless overridden.

Engine source:

- `researchboss.engine.guidelines.set_default_guidelines`

### `GET /api/v1/guidelines/conflicts` (implemented)

Returns a deterministic report of contradictory guideline requirements for human review.

Engine source:

- `researchboss.engine.guidelines.guideline_conflict_report`

## SQLite Sync Status Routes

### `POST /api/v1/db/init` (implemented)

Initializes the optional workspace SQLite index database.

Engine source:

- `researchboss.engine.database.init_database`

### `POST /api/v1/db/sync` (implemented)

Syncs workspace YAML/Markdown metadata into the local SQLite index. YAML and Markdown remain the source of truth.

Engine source:

- `researchboss.engine.database.sync_database`

### `GET /api/v1/db/status` (implemented)

Returns SQLite index health, sync counts, and repair guidance.

Engine source:

- `researchboss.engine.database.database_status`

### `POST /api/v1/db/rebuild` (implemented)

Rebuilds the SQLite index from workspace YAML/Markdown source-of-truth files.

Engine source:

- `researchboss.engine.database.rebuild_database`

### `GET /api/v1/db/pending` (implemented)

Returns SQLite-to-file pending changes for review, without applying them.

Engine source:

- `researchboss.engine.database.pending_changes_report`

### `POST /api/v1/db/apply-pending` (implemented)

Reviews (`apply: false`) or applies (`apply: true`) reviewed SQLite-to-YAML/Markdown pending changes. SQLite-to-file write-back is never silent.

Engine source:

- `researchboss.engine.database.apply_pending_changes`

### `GET /api/v1/db/privacy` (implemented)

Checks that the SQLite database does not intentionally store secrets or original documents.

Engine source:

- `researchboss.engine.database.database_privacy_report`

## Report And Export Routes

### `GET /api/v1/reports/workspace` (implemented)

Generates local Markdown workspace report.

Engine source:

- `researchboss.engine.reports.generate_workspace_report`

### `GET /api/v1/reports/timeline` (implemented)

Generates a local timeline report.

Engine source:

- `researchboss.engine.project_log.timeline_report`

### `POST /api/v1/export/evidence` (implemented)

Creates an offline evidence bundle without original source files by default.

Engine source:

- `researchboss.engine.export.export_evidence_bundle`

### `POST /api/v1/backup` (implemented)

Creates a local backup.

Engine source:

- `researchboss.engine.backup.create_workspace_backup`

### `GET /api/v1/backup/inspect` (implemented)

Inspects a backup zip without restoring it.

Engine source:

- `researchboss.engine.backup.inspect_backup`

## Project Log Routes

### `POST /api/v1/decisions` (implemented)

Adds a structured local decision.

Engine source:

- `researchboss.engine.project_log.add_decision`

### `POST /api/v1/terminology` (implemented)

Adds or updates a glossary term.

Engine source:

- `researchboss.engine.project_log.add_terminology`

### `POST /api/v1/feedback` (implemented)

Adds supervisor or stakeholder feedback.

Engine source:

- `researchboss.engine.project_log.add_feedback`

### `POST /api/v1/context/changelog` (implemented)

Adds a context changelog item.

Engine source:

- `researchboss.engine.project_log.add_context_change`

## Web UI Routes (implemented)

`researchboss/web/` mounts a server-rendered HTML shell onto the same FastAPI app as everything above — same process, same `researchboss serve`, no separate deployment step. These routes serve HTML (or static files), not the `{"ok","data","warnings","errors"}` envelope, and are outside `/api/v1`, but the Non-Negotiable Boundaries above still apply in full: the web layer has no import path to `researchboss.engine` at all (`researchboss/web/app.py` only imports session-cookie helpers from `researchboss.api.auth`, plus Jinja2/Starlette), and every data operation happens client-side via `fetch()` calls to the `/api/v1/*` routes documented above — the web UI is architecturally just another API client, enforced by import structure rather than convention.

- `GET /login` — public, no session required. Serves the login form; the form itself posts to `POST /api/v1/auth/login`.
- `GET /` — the app shell. Session-gated *server-side*: reads the session cookie directly and issues a `303` redirect to `/login?next=<url>` before rendering anything if there's no valid session, rather than sending an empty shell that discovers it's unauthenticated only after a client-side API call. Workspace selection is a `?workspace=` query param, mirroring how every `/api/v1/*` route already takes an explicit `workspace` — there is no server-side session-scoped "current workspace."
- `GET /static/*` — `app.js` (vanilla JS, no framework, no bundler) and `styles.css` (hand-written, no CSS framework). No CDN dependency anywhere, consistent with this project staying usable offline.

## Future AI Routes

**Not implemented.** The route shapes below are a planning sketch only, modeled directly on the equivalent CLI commands and their `researchboss.engine.ai` functions (which already exist and are exercised by the CLI today) so that a future implementation has no ambiguity to resolve at build time. Adding these routes for real still requires: (1) an explicit product decision on how a *web* client performs the CLI's per-invocation `--ai` opt-in (sketched below as a required `"ai": true` request-body field, mirroring the CLI rather than introducing a session-wide or workspace-wide AI toggle), and (2) the privacy-boundary tests listed under "Required Tests Before Implementation." Until both exist, these routes must stay disabled/unregistered — do not wire them into `researchboss/api/app.py`.

Every route in this section shares the same server-side credential rule: the OpenAI API key is resolved server-side only, the same way the CLI resolves it (`OPENAI_API_KEY` env var, or `.env` in the workspace via `engine.ai.openai_credentials`). **No route may accept an API key in the request body or from the client** — that would hand a browser client the ability to exfiltrate or misuse server-side credentials, which is a straight OWASP-relevant boundary violation, not just a style preference. If the key is missing, the route must return the same "not configured" failure the CLI raises (`OpenAiError("Missing OPENAI_API_KEY")`), not a generic 500.

Every route also shares the same safe-context boundary already enforced by `engine.ai.build_safe_context`: original files, whole PDFs/CSVs/SQLite databases, and full documents are excluded by construction — only per-source excerpts capped at `max_excerpt_chars` are sent. None of the four sketched routes needs a `--full-file-ai`/`--directory-ai`-style extra opt-in, because none of their CLI equivalents (`ai test`, `ai review`, `assess-novelty`, `rqs assess`) use one; a future route that *did* need whole-file or directory context (there is none planned) would need the matching extra opt-in field, not just `ai: true`.

Common response envelope fields all four routes would share (already returned by every `engine.ai` function): `version`, `kind`, `provider` (`"openai"`), `model`, `ai_used: true`, `requires_user_review: true`, `safe_context_policy` (echoes `build_safe_context`'s `policy` block), `limits` (echoes `max_sources`/`max_excerpt_chars` actually applied), `source_count`, `response_id` (the OpenAI response id, for audit trail — never the raw response body). None of these routes modify any artefact, source, or claim document; where the CLI equivalent writes a side-effect file (novelty ledger), the sketch below says so explicitly.

### `POST /api/v1/ai/test` (not implemented — shape only)

CLI equivalent: `researchboss ai test`. Engine source: `engine.ai.openai_readiness`.

Request body: `{"ai": bool = false}` — `ai: true` additionally performs a live `GET /models` credential check against OpenAI (mirrors the CLI's `--ai` flag meaning "allow a live check", not "allow AI use" in this one case, since checking readiness doesn't send any workspace content). `ai: false` (or omitted) checks key/config presence only, with no outbound request.

Response `data`: `{key_loaded, key_exposed: false, workspace_ai_enabled, openai_provider_enabled, default_model, live_request_performed, policy: "explicit_ai_flag_required"}`, plus `api_reachable` and `model_count` when `live_request_performed` is true.

### `POST /api/v1/ai/review` (not implemented — shape only)

CLI equivalent: `researchboss ai review --ai`. Engine source: `engine.ai.ai_assisted_review`.

Request body: `{"ai": true, "max_sources": int = 10, "max_excerpt_chars": int = 1200}`. `400 ai_not_enabled` if `ai` is not `true`.

Response `data`: common envelope fields above, plus `review` (markdown text with sections Scope, Useful Signals, Evidence Gaps, Source Follow-up, Human Review Required). No side-effect file — the CLI writes `outputs/validation/openai-review.yaml`; an API caller receives the same content in the response body and decides whether to persist it.

### `POST /api/v1/ai/novelty` (not implemented — shape only)

CLI equivalent: `researchboss assess-novelty --ai`. Engine source: `engine.ai.ai_novelty_assessment`. This is the route that resolves the "novelty assessment has no deterministic engine path" note at the top of this document — `ai_novelty_assessment` is AI-only, so novelty assessment belongs under `/api/v1/ai/`, not as a separate `/api/v1/novelty` route implying a deterministic engine path that doesn't exist.

Request body: `{"ai": true, "max_sources": int = 10, "max_excerpt_chars": int = 1200}`. `400 ai_not_enabled` if `ai` is not `true`.

Response `data`: common envelope fields, plus `novelty_not_proven: true` (the assessment must never be presented as proof of novelty), `research_question_count`, `assessment` (markdown text). Side effect: like the CLI, appends a record to `novelty-ledger.yaml` (`id`, `kind`, `provider`, `model`, `response_id`, `requires_user_review`, `novelty_not_proven`, `source_count`, `research_question_count`, `assessment`) — this is a workspace-state write and must be covered by the same workspace-scoped-write test every other mutating route has.

### `POST /api/v1/ai/rqs/assess` (not implemented — shape only)

CLI equivalent: `researchboss rqs assess --ai [--rq <id>]`. Engine source: `engine.ai.ai_research_question_assessment`.

Request body: `{"ai": true, "rq_id": Optional[str] = None, "max_sources": int = 10, "max_excerpt_chars": int = 1200}`. `400 ai_not_enabled` if `ai` is not `true`. `404 unknown_research_question` if `rq_id` is supplied but matches no approved or candidate research question (mirrors `OpenAiError(f"Unknown research question: {rq_id}")`).

Response `data`: common envelope fields, plus `novelty_not_proven: true`, `research_question_count` (count actually assessed — all approved+candidate questions when `rq_id` is omitted, else the one matched question), `rq_id` (echoes the request), `assessment` (markdown text, one section per assessed research question plus a final Human Review Required section).

Rules (all four routes):

- Disabled by default — not registered in `researchboss/api/app.py` until implemented.
- Must require the per-request `ai: true` opt-in described above; there is no workspace-level or session-level AI toggle that bypasses it.
- Must never log or echo the API key.
- Must never upload whole PDFs, CSVs, SQLite databases, or original documents — only `build_safe_context` excerpts, capped at the requested `max_excerpt_chars`.
- Must preserve the Zotero no-write boundary.
- Must return the response's `requires_user_review: true` field on every success response — these are advisory outputs, never auto-applied.

## Forbidden Routes

The following route classes must not be added:

- Zotero write routes.
- Routes that write into Zotero storage.
- Routes that delete original source files.
- Routes that require a remote database for MVP operation.
- Routes that sync to Dropbox, Google Drive, OneDrive, SharePoint, AWS, Azure, Firebase, Supabase, or similar services for MVP operation.

## Required Tests Before Implementation

Before a route group is marked implemented, tests must prove that:

- The route calls shared `researchboss.engine` behavior instead of duplicating business logic in the API layer.
- Workspace writes are limited to ResearchBoss workspace files.
- Original source files are not modified.
- Local Zotero directories are never modified.
- Zotero Web API routes use read-only operations only.
- Missing or invalid API keys are handled without printing or logging secrets.
- Future AI routes stay disabled until explicit AI implementation and privacy-boundary tests exist.
