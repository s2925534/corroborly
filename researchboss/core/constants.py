from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class WorkspaceFiles:
    research_context: str = "research-context.yaml"
    research_state: str = "research-state.yaml"
    research_stages: str = "research-stages.yaml"
    research_questions: str = "research-questions.yaml"
    research_question_candidates: str = "research-question-candidates.yaml"
    rejected_research_questions: str = "rejected-research-questions.yaml"

    source_register: str = "source-register.yaml"
    accepted_sources: str = "accepted-sources.yaml"
    ignored_sources: str = "ignored-sources.yaml"
    maybe_sources: str = "maybe-sources.yaml"

    claims_ledger: str = "claims-ledger.yaml"
    novelty_ledger: str = "novelty-ledger.yaml"
    terminology: str = "terminology.yaml"
    supervisor_feedback: str = "supervisor-feedback.yaml"
    artefact_registry: str = "artefact-registry.yaml"

    decisions_md: str = "decisions.md"
    memory_md: str = "memory.md"
    context_changelog_md: str = "context-changelog.md"

    app_settings_local: str = "app-settings.local.yaml"
    gitignore: str = ".gitignore"

    document_vault_ledger: str = "document-vault.yaml"


WORKSPACE_FILES = WorkspaceFiles()


WORKSPACE_DIRS: list[str] = [
    "sources_original",
    "sources_original/academic",
    "sources_original/data",
    "sources_original/notes",
    "sources_original/images",
    "sources_original/manual",
    "sources_text",
    "sources_metadata",
    "sources_failed",
    "artefacts",
    "artefacts/thesis",
    "artefacts/papers",
    "artefacts/diagrams",
    "artefacts/images",
    "artefacts/tables",
    "artefacts/presentations",
    "artefacts/reports",
    "artefacts/notes",
    "outputs",
    "outputs/reports",
    "outputs/validation",
    "outputs/citation-plans",
    "outputs/novelty",
    "outputs/recommendations",
    "outputs/data-profiles",
    "outputs/logs",
    "outputs/logs/run-summaries",
    "guidelines",
    "guidelines/snapshots",
    "guidelines/text",
    "context_versions",
    "document_vault",
    "document_vault/originals",
    "document_vault/versions",
    "document_vault/derived_text",
    "document_vault/diffs",
    "document_vault/manifests",
    "document_vault/ai_edit_sessions",
    "document_vault/uploads",
    "document_vault/uploads/originals",
    "document_vault/uploads/renamed",
]


def required_workspace_paths(workspace: Path) -> dict[str, Path]:
    return {
        "research_context": workspace / WORKSPACE_FILES.research_context,
        "source_register": workspace / WORKSPACE_FILES.source_register,
        "outputs_logs": workspace / "outputs" / "logs",
    }


def ensure_workspace_dirs(workspace: Path) -> None:
    for d in WORKSPACE_DIRS:
        (workspace / d).mkdir(parents=True, exist_ok=True)
