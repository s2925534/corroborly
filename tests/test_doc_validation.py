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
                    "citation_metadata": {"title": "Accepted Source", "year": 2024},
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
    assert [source["source_id"] for source in report["sources"]] == ["source-001", "explicit-source-001"]
    assert report["sources"][0]["provider"] == "zotero_storage"
    assert "pending" not in result.markdown_path.read_text(encoding="utf-8")
