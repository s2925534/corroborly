# Changelog

All notable changes to ResearchBoss will be documented in this file.

## Unreleased

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
