from pathlib import Path
import sqlite3

from researchboss.core.yamlio import read_yaml
from researchboss.engine.data import data_source_counts, list_data_sources, profile_data_sources
from researchboss.engine.sources import iter_source_files, scan_sources
from researchboss.engine.workspace import init_workspace


def make_workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test Project", project_type="M.Phil", topic="")
    return workspace


def test_json_files_are_registered_as_sources(tmp_path: Path) -> None:
    source_root = tmp_path / "sources"
    source_root.mkdir()
    (source_root / "data.json").write_text('{"name": "example"}', encoding="utf-8")

    assert [path.name for path in iter_source_files(source_root)] == ["data.json"]


def test_profile_data_sources_profiles_csv_sqlite_and_json(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    source_root = tmp_path / "sources"
    source_root.mkdir()
    (source_root / "sample.csv").write_text("name,age\nAda,36\nBob,\n", encoding="utf-8")
    (source_root / "sample.json").write_text('[{"name": "Ada"}, {"age": 36}]', encoding="utf-8")
    db_path = source_root / "sample.sqlite"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE people (name TEXT, age INTEGER)")
    conn.execute("INSERT INTO people VALUES ('Ada', 36)")
    conn.commit()
    conn.close()
    scan_sources(workspace, source_root)

    result = profile_data_sources(workspace)

    assert result.processed == 3
    assert result.profiled == 3
    assert len(list_data_sources(workspace)) == 3
    assert data_source_counts(workspace) == {"total": 3, "profiled": 3, "unprofiled": 0}
    profiles = list((workspace / "outputs" / "data-profiles").glob("*.yaml"))
    assert len(profiles) == 3
    csv_profile = next(read_yaml(path)["profile"] for path in profiles if read_yaml(path)["profile"]["type"] == "csv")
    assert csv_profile["row_count"] == 2
    assert csv_profile["column_count"] == 2
    assert csv_profile["columns"][1]["missing_values"] == 1
    sqlite_profile = next(read_yaml(path)["profile"] for path in profiles if read_yaml(path)["profile"]["type"] == "sqlite")
    assert sqlite_profile["tables"][0]["name"] == "people"
    assert sqlite_profile["tables"][0]["row_count"] == 1
    json_profile = next(read_yaml(path)["profile"] for path in profiles if read_yaml(path)["profile"]["type"] == "json")
    assert json_profile["item_count"] == 2
