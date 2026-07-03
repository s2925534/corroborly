from __future__ import annotations

from pathlib import Path

from researchboss.core.yamlio import read_yaml
from researchboss.engine.artefacts import list_artefacts
from researchboss.engine.claims import citation_gap_claims, list_claims
from researchboss.engine.data import data_source_counts
from researchboss.engine.research_questions import list_research_questions
from researchboss.engine.sources import source_counts


def generate_workspace_report(workspace: Path) -> Path:
    context = read_yaml(workspace / "research-context.yaml")
    project = context.get("project", {})
    counts = source_counts(workspace)
    data_counts = data_source_counts(workspace)
    rq_groups = list_research_questions(workspace)
    claims = list_claims(workspace)
    gaps = citation_gap_claims(workspace)
    artefacts = list_artefacts(workspace)

    lines = [
        f"# ResearchBoss Report: {project.get('name', 'Untitled')}",
        "",
        "## Project",
        "",
        f"- Type: {project.get('type')}",
        f"- Topic: {project.get('topic')}",
        f"- Strict evidence mode: {project.get('strict_evidence_mode')}",
        "",
        "## Sources",
        "",
    ]
    for key in sorted(counts):
        lines.append(f"- {key}: {counts[key]}")
    lines.extend(["", "## Data Sources", ""])
    for key in sorted(data_counts):
        lines.append(f"- {key}: {data_counts[key]}")
    lines.extend(
        [
            "",
            "## Research Questions",
            "",
            f"- Approved: {len(rq_groups['approved'])}",
            f"- Candidates: {len(rq_groups['candidates'])}",
            f"- Rejected or archived: {len(rq_groups['rejected'])}",
            "",
            "## Claims",
            "",
            f"- Claims: {len(claims)}",
            f"- Citation gaps: {len(gaps)}",
            "",
            "## Artefacts",
            "",
            f"- Registered artefacts: {len(artefacts)}",
            "",
        ]
    )
    output_path = workspace / "outputs" / "reports" / "workspace-report.md"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path
