# ResearchBoss Local API Contract

This document defines the FastAPI boundary for ResearchBoss.

Contract status: implementation started in project version `0.7.0`; every route documented below is now implemented in `researchboss.api` (run with `researchboss serve`) except the disabled Future AI Routes section. New route groups (validation, citation plans, guidelines, SQLite sync status, novelty, AI) need to be added to this contract before they can be implemented, consistent with the reuse-not-duplicate rule below.

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

## Future AI Routes

AI routes are contract placeholders only and must remain disabled until explicit implementation and privacy-boundary tests exist.

Future routes:

- `POST /api/v1/ai/test`
- `POST /api/v1/ai/review`
- `POST /api/v1/ai/novelty`
- `POST /api/v1/ai/rqs/assess`

Rules:

- Disabled by default.
- Must require explicit AI enablement.
- Must never log API keys.
- Must never upload whole PDFs, CSVs, SQLite databases, or original documents unless the user has explicitly opted into that scope.
- Must preserve the Zotero no-write boundary.

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
