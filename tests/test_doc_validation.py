from pathlib import Path

from researchboss.core.yamlio import read_yaml, write_yaml
from researchboss.engine.doc_validation import validate_document
from researchboss.engine.workspace import init_workspace


def test_validate_document_compares_target_to_accepted_and_explicit_sources(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test Project", project_type="M.Phil", topic="")
    target = workspace / "artefacts" / "papers" / "draft.md"
    target.write_text(
        "# Draft\n\nContainer terminal automation depends on berth planning and crane scheduling evidence.\n",
        encoding="utf-8",
    )
    accepted_text = workspace / "sources_text" / "source-001.txt"
    accepted_text.write_text(
        "Automation in container terminals often studies berth planning and quay crane scheduling.",
        encoding="utf-8",
    )
    explicit_source = tmp_path / "external-source.txt"
    explicit_source.write_text("Crane scheduling can be evaluated with deterministic planning metrics.", encoding="utf-8")
    write_yaml(
        workspace / "source-register.yaml",
        {
            "version": 1,
            "sources": [
                {
                    "source_id": "source-001",
                    "status": "accepted",
                    "provider": "zotero_storage",
                    "file_name": "accepted.pdf",
                    "conversion": {"status": "converted", "output_path": str(accepted_text)},
                    "citation_metadata": {
                        "title": "Accepted Source",
                        "authors": ["A. Author"],
                        "year": 2024,
                        "doi": "10.1234/example",
                        "publication_title": "Journal of Testing",
                        "document_type": "article",
                    },
                    "citation_count": 12,
                },
                {
                    "source_id": "source-002",
                    "status": "pending_review",
                    "provider": "local_folder",
                    "file_name": "pending.pdf",
                },
            ],
        },
    )

    result = validate_document(workspace, str(target), source_paths=[explicit_source])

    assert result.yaml_path.is_file()
    assert result.markdown_path.is_file()
    report = read_yaml(result.yaml_path)
    assert report["ai_used"] is False
    assert report["summary"]["source_count"] == 2
    assert report["summary"]["sources_with_overlap"] == 2
    assert report["strengths"]
    assert report["weaknesses"] == []
    assert report["unsupported_claims"] == []
    assert report["weakly_supported_claims"] == []
    assert report["possible_contradictions"][0]["kind"] == "not_assessed"
    assert report["missing_citations"]
    assert report["candidate_supporting_sources"][0]["source_id"] == "source-001"
    assert report["evidence_confidence"][0]["claim_relevance"]["value"] == "high"
    assert report["evidence_confidence"][0]["source_credibility"]["value"] == "accepted_workspace_source"
    assert report["evidence_confidence"][0]["metadata_completeness"]["value"] == "complete"
    assert report["evidence_confidence"][0]["recency"]["value"] == "recent"
    assert report["evidence_confidence"][0]["citation_strength"]["value"] == "moderate"
    assert report["evidence_confidence"][0]["confidence_score"]["score"] == 97
    assert report["evidence_confidence"][0]["confidence_score"]["unknown_component_count"] == 0
    assert report["evidence_confidence"][1]["metadata_completeness"]["value"] == "partial"
    assert report["evidence_confidence"][1]["confidence_score"]["unknown_component_count"] > 0
    assert "citation_strength" in report["evidence_confidence"][1]["confidence_score"]["unknown_components"]
    assert "publication_venue" in report["evidence_confidence"][1]["metadata_completeness"]["unknown_fields"]
    assert report["references"]["accepted_workspace_evidence"][0]["reference"].startswith("A. Author")
    assert "https://doi.org/10.1234/example" in report["references"]["accepted_workspace_evidence"][0]["reference"]
    assert report["references"]["candidate_or_explicit_sources"][0]["reference"].startswith("Unknown author")
    assert report["human_review_checklist"]
    assert [source["source_id"] for source in report["sources"]] == ["source-001", "explicit-source-001"]
    assert report["sources"][0]["provider"] == "zotero_storage"
    markdown = result.markdown_path.read_text(encoding="utf-8")
    assert "## Strengths" in markdown
    assert "## Evidence Confidence Factors" in markdown
    assert "## References" in markdown
    assert "### Accepted Workspace Evidence" in markdown
    assert "## Human Review Checklist" in markdown
    assert "pending" not in markdown
