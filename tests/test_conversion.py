from pathlib import Path

from researchboss.core.yamlio import read_yaml
from researchboss.engine.conversion import convert_sources
from researchboss.engine.sources import scan_sources, set_source_status
from researchboss.engine.workspace import init_workspace


def make_workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test Project", project_type="M.Phil", topic="")
    return workspace


def test_convert_sources_converts_txt_to_sources_text(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    source_root = tmp_path / "sources"
    source_root.mkdir()
    source_file = source_root / "notes.txt"
    source_file.write_text("line one\r\nline two\r", encoding="utf-8")
    scan_sources(workspace, source_root)
    source_id = read_yaml(workspace / "source-register.yaml")["sources"][0]["source_id"]
    set_source_status(workspace, source_id=source_id, new_status="accepted")

    result = convert_sources(workspace, status="accepted")

    assert result.processed == 1
    assert result.converted == 1
    output_path = workspace / "sources_text" / f"{source_id}.txt"
    assert output_path.read_text(encoding="utf-8") == "line one\nline two\n"
    source = read_yaml(workspace / "source-register.yaml")["sources"][0]
    assert source["conversion"]["status"] == "converted"
    assert source["conversion"]["output_path"] == str(output_path)
