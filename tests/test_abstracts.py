from pathlib import Path

from researchboss.core.yamlio import read_yaml
from researchboss.engine.abstracts import import_abstract_folder, parse_legacy_scopus_abstract
from researchboss.engine.workspace import init_workspace


def test_parse_legacy_scopus_abstract_extracts_known_fields(tmp_path: Path) -> None:
    path = tmp_path / "abstract.txt"
    path.write_text(
        """
Title: Container port evidence
Authors: Smith, A.; Jones, B.
Publication: Journal of Ports
Year: 2024
DOI: 10.1000/example
Cited by: 12
Abstract: This paper discusses container port evidence.
API URL: https://api.example.test
Scopus view URL: https://scopus.example.test
""",
        encoding="utf-8",
    )

    record = parse_legacy_scopus_abstract(path)

    assert record["title"] == "Container port evidence"
    assert record["authors"] == ["Smith, A.", "Jones, B."]
    assert record["publication_title"] == "Journal of Ports"
    assert record["year"] == "2024"
    assert record["cited_by_count"] == 12
    assert record["abstract"] == "This paper discusses container port evidence."


def test_import_abstract_folder_groups_candidates_filtered_and_skipped(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    folder = tmp_path / "abstracts"
    folder.mkdir()
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="")
    (folder / "good.txt").write_text("Title: Good\nYear: 2024\nAbstract: Useful abstract.\n", encoding="utf-8")
    (folder / "filtered.txt").write_text("Title: Missing abstract\n", encoding="utf-8")
    (folder / "ignored.pdf").write_bytes(b"pdf")

    result = import_abstract_folder(workspace, folder)

    register = read_yaml(result.register_path)
    assert result.processed == 3
    assert register["candidate_count"] == 1
    assert register["filtered_count"] == 1
    assert register["skipped_count"] == 1
    assert register["candidates"][0]["status"] == "candidate"
    assert register["filtered"][0]["filter_reasons"] == ["missing_abstract"]
