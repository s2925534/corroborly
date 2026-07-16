from pathlib import Path
from zipfile import ZipFile

from ledgerly.core.yamlio import write_yaml
from ledgerly.engine.claims import add_claim
from ledgerly.engine.export import (
    build_supervisor_bundle,
    build_supervisor_bundle_html,
    export_accepted_source_corpus,
    export_evidence_bundle,
)
from ledgerly.engine.workspace import init_workspace


def test_export_evidence_bundle_excludes_original_files(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test Project", project_type="M.Phil", topic="")
    (workspace / "sources_original" / "manual" / "paper.txt").write_text("full text", encoding="utf-8")
    write_yaml(workspace / "accepted-sources.yaml", {"version": 1, "source_ids": ["source-001"]})
    write_yaml(
        workspace / "source-register.yaml",
        {
            "version": 1,
            "sources": [
                {"source_id": "source-001", "status": "accepted", "file_name": "paper.txt"},
                {"source_id": "source-002", "status": "ignored", "file_name": "ignored.txt"},
            ],
        },
    )

    output_path = export_evidence_bundle(workspace)

    with ZipFile(output_path) as zf:
        names = set(zf.namelist())
        accepted = zf.read("accepted-source-records.yaml").decode("utf-8")
    assert "manifest.yaml" in names
    assert "sources_original/manual/paper.txt" not in names
    assert "source-001" in accepted
    assert "source-002" not in accepted


def test_export_accepted_source_corpus_writes_combined_text_and_manifest(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test Project", project_type="M.Phil", topic="")
    source_text = workspace / "sources_text" / "source-001.txt"
    source_text.write_text("Accepted converted source text.", encoding="utf-8")
    write_yaml(workspace / "accepted-sources.yaml", {"version": 1, "source_ids": ["source-001", "source-002"]})
    write_yaml(
        workspace / "source-register.yaml",
        {
            "version": 1,
            "sources": [
                {
                    "source_id": "source-001",
                    "status": "accepted",
                    "file_name": "paper.txt",
                    "conversion": {"status": "converted", "output_path": str(source_text)},
                    "citation_metadata": {"title": "Accepted Paper", "authors": ["Smith, A."], "year": 2024},
                },
                {"source_id": "source-002", "status": "accepted", "file_name": "missing.txt"},
            ],
        },
    )

    result = export_accepted_source_corpus(workspace)

    corpus = result.corpus_path.read_text(encoding="utf-8")
    manifest = result.manifest_path.read_text(encoding="utf-8")
    assert "Source ID: source-001" in corpus
    assert "Title: Accepted Paper" in corpus
    assert "Accepted converted source text." in corpus
    assert result.included_count == 1
    assert result.skipped_count == 1
    assert "converted_text_missing" in manifest


def test_build_supervisor_bundle_writes_digest_and_zip(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test Project", project_type="M.Phil", topic="")
    add_claim(workspace, text="Container automation reduces turnaround time.", linked_sources=["source-001"])
    add_claim(workspace, text="Unsupported claim with no source.")

    bundle_path = build_supervisor_bundle(workspace)
    digest_path = workspace / "outputs" / "reports" / "supervisor-bundle.md"

    assert bundle_path.name == "supervisor-bundle.zip"
    assert digest_path.is_file()
    digest = digest_path.read_text(encoding="utf-8")
    assert "# Supervisor Review Bundle" in digest
    assert "Container automation reduces turnaround time." in digest
    assert "No citation plans created yet." in digest
    assert "## Workspace Review Report" in digest
    assert "## AI Usage Disclosure" in digest
    assert "No AI features have been used in this workspace." in digest

    with ZipFile(bundle_path) as zf:
        names = set(zf.namelist())
    assert "supervisor-bundle.md" in names
    assert "supervisor-bundle.html" in names
    assert "workspace-report.md" in names
    assert "claims-ledger.yaml" in names
    assert "ai-usage-ledger.yaml" in names


def test_build_supervisor_bundle_includes_ai_usage_disclosure_summary(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test Project", project_type="M.Phil", topic="Topic")

    from ledgerly.engine.ai import (
        OpenAiCredentials,
        ai_assisted_review,
    )

    def opener(request):
        raise AssertionError("no evidence configured -- must not reach the AI provider")

    ai_assisted_review(workspace, OpenAiCredentials(api_key="sk-secret"), opener=opener)

    bundle_path = build_supervisor_bundle(workspace)
    digest = (workspace / "outputs" / "reports" / "supervisor-bundle.md").read_text(encoding="utf-8")

    assert "## AI Usage Disclosure" in digest
    assert "1 AI call(s) recorded" in digest
    assert "0 actually used an AI provider" in digest
    assert "1 correctly refused with insufficient evidence" in digest
    assert "ai_assisted_review" in digest

    with ZipFile(bundle_path) as zf:
        ledger_yaml = zf.read("ai-usage-ledger.yaml").decode("utf-8")
    assert "ai_assisted_review" in ledger_yaml


def test_build_supervisor_bundle_handles_no_claims(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test Project", project_type="M.Phil", topic="")

    bundle_path = build_supervisor_bundle(workspace)
    digest = (workspace / "outputs" / "reports" / "supervisor-bundle.md").read_text(encoding="utf-8")

    assert bundle_path.is_file()
    assert "_none recorded yet_" in digest


def test_build_supervisor_bundle_html_is_self_contained_and_escapes_content(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test Project", project_type="M.Phil", topic="")
    add_claim(workspace, text="Claim with <script>alert('x')</script> in it.", linked_sources=["source-001"])

    html_path = build_supervisor_bundle_html(workspace)
    html_text = html_path.read_text(encoding="utf-8")

    assert html_path.name == "supervisor-bundle.html"
    assert html_text.startswith("<!doctype html>")
    assert "<style>" in html_text  # inline CSS, no external stylesheet link
    assert "<link " not in html_text
    assert "<script>alert" not in html_text  # claim text must be escaped, not injected raw
    assert "&lt;script&gt;" in html_text
    assert "Supervisor Review Bundle" in html_text
    assert "AI Usage Disclosure" in html_text


def test_build_supervisor_bundle_html_handles_no_claims_or_ai_usage(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test Project", project_type="M.Phil", topic="")

    html_path = build_supervisor_bundle_html(workspace)
    html_text = html_path.read_text(encoding="utf-8")

    assert "None recorded yet." in html_text
    assert "No AI features have been used in this workspace." in html_text
    assert "No citation plans created yet." in html_text
