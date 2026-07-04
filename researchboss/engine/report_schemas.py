from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from researchboss.core.yamlio import write_yaml


@dataclass(frozen=True)
class ReportSchemaExport:
    yaml_path: Path
    markdown_path: Path
    schema_count: int


REPORT_SCHEMAS: dict[str, dict[str, Any]] = {
    "document_validation": {
        "path_pattern": "outputs/validation/document-validation-{target-stem}.yaml",
        "required_top_level_keys": [
            "version",
            "target",
            "validation_method",
            "summary",
            "sources",
            "strengths",
            "weaknesses",
            "unsupported_claims",
            "weakly_supported_claims",
            "possible_contradictions",
            "missing_citations",
            "candidate_supporting_sources",
            "evidence_confidence",
            "references",
            "guidelines",
            "human_review_checklist",
        ],
        "human_review_guidelines": [
            "Treat deterministic term overlap as a screening signal, not proof of correctness.",
            "Do not accept a claim as supported unless the cited source has been reviewed.",
            "Preserve unknown metadata as unknown.",
        ],
    },
    "citation_insertion_plan": {
        "path_pattern": "outputs/citation-plans/citation-plan-{target-stem}.yaml",
        "required_top_level_keys": [
            "version",
            "target",
            "validation_report",
            "ai_used",
            "original_document_modified",
            "plan_status",
            "allow_candidate_citations",
            "insertions",
            "blocked_candidate_citations",
            "references",
            "guidelines",
            "limitations",
        ],
        "human_review_guidelines": [
            "Apply only insertions whose review_status is accepted or approved.",
            "Prefer accepted workspace sources over candidate or explicit one-off sources.",
            "Keep the original target document unmodified unless an explicit overwrite workflow exists.",
        ],
    },
    "evidence_confidence": {
        "path_pattern": "embedded in document validation reports under evidence_confidence",
        "required_item_keys": [
            "source_id",
            "claim_relevance",
            "source_credibility",
            "metadata_completeness",
            "recency",
            "citation_strength",
            "author_signals",
            "publication_venue_signals",
            "paper_type",
            "contradiction_risk",
            "accepted_vs_candidate_status",
            "confidence_score",
        ],
        "human_review_guidelines": [
            "Use the numeric score as a triage aid only.",
            "Check unknown_components before trusting a high-looking score.",
            "Do not infer author h-index, venue rank, or citation quality without recorded metadata.",
        ],
    },
    "guideline_conflicts": {
        "path_pattern": "outputs/validation/guideline-conflicts.yaml",
        "required_top_level_keys": [
            "version",
            "conflict_count",
            "conflicts",
            "human_review_required",
        ],
        "human_review_guidelines": [
            "Resolve faculty, supervisor, journal, and citation-style conflicts before final submission.",
            "Record the chosen precedence in workspace guideline defaults when it should persist.",
        ],
    },
    "apa7_references": {
        "path_pattern": "embedded in validation, citation, and external-search reports under references",
        "required_top_level_keys": [
            "citation_style",
            "accepted_workspace_sources",
            "candidate_or_explicit_sources",
        ],
        "human_review_guidelines": [
            "APA7 is the default unless the workspace explicitly configures another citation style.",
            "Separate accepted evidence from candidate or explicit one-off sources.",
            "Do not fill missing authors, years, titles, or venues with invented values.",
        ],
    },
}


def export_report_schemas(workspace: Path) -> ReportSchemaExport:
    output_dir = workspace / "outputs" / "reports"
    output_dir.mkdir(parents=True, exist_ok=True)
    yaml_path = output_dir / "report-schemas.yaml"
    markdown_path = output_dir / "report-schemas.md"
    payload = {"version": 1, "schemas": REPORT_SCHEMAS}
    write_yaml(yaml_path, payload)
    markdown_path.write_text(_markdown(payload), encoding="utf-8")
    return ReportSchemaExport(yaml_path=yaml_path, markdown_path=markdown_path, schema_count=len(REPORT_SCHEMAS))


def _markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# ResearchBoss Report Schemas",
        "",
        "These schemas document deterministic report contracts for validation, citation, confidence, guideline conflict, and APA7 reference outputs.",
        "",
    ]
    for name, schema in payload["schemas"].items():
        lines.extend([f"## {name.replace('_', ' ').title()}", "", f"- Path: `{schema['path_pattern']}`"])
        keys = schema.get("required_top_level_keys") or schema.get("required_item_keys") or []
        if keys:
            lines.append("- Required keys:")
            lines.extend(f"  - `{key}`" for key in keys)
        guidelines = schema.get("human_review_guidelines") or []
        if guidelines:
            lines.append("- Human review guidelines:")
            lines.extend(f"  - {item}" for item in guidelines)
        lines.append("")
    return "\n".join(lines)
