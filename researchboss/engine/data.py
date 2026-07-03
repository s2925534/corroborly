from __future__ import annotations

import csv
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from researchboss.core.yamlio import read_yaml, write_yaml


DATA_EXTENSIONS = {"csv", "sqlite", "db", "json"}


@dataclass(frozen=True)
class DataProfileRunResult:
    processed: int
    profiled: int
    skipped: int


def _infer_value_type(values: list[str]) -> str:
    non_empty = [value for value in values if value not in ("", None)]
    if not non_empty:
        return "empty"
    for parser, name in ((int, "integer"), (float, "number")):
        try:
            for value in non_empty:
                parser(value)
            return name
        except ValueError:
            pass
    lowered = {value.lower() for value in non_empty}
    if lowered <= {"true", "false", "yes", "no", "0", "1"}:
        return "boolean"
    return "text"


def profile_csv(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8", errors="replace", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    columns = reader.fieldnames or []
    return {
        "type": "csv",
        "file_path": str(path),
        "row_count": len(rows),
        "column_count": len(columns),
        "columns": [
            {
                "name": column,
                "missing_values": sum(1 for row in rows if row.get(column) in ("", None)),
                "inferred_type": _infer_value_type([row.get(column, "") for row in rows]),
            }
            for column in columns
        ],
    }


def profile_sqlite(path: Path) -> dict[str, Any]:
    uri = f"file:{path.resolve()}?mode=ro&immutable=1"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    try:
        tables = [
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            ).fetchall()
        ]
        table_profiles = []
        for table in tables:
            quoted = '"' + table.replace('"', '""') + '"'
            columns = [
                {"name": row["name"], "type": row["type"]}
                for row in conn.execute(f"PRAGMA table_info({quoted})").fetchall()
            ]
            try:
                row_count = int(conn.execute(f"SELECT COUNT(*) AS count FROM {quoted}").fetchone()["count"])
            except sqlite3.Error:
                row_count = None
            table_profiles.append({"name": table, "columns": columns, "row_count": row_count})
    finally:
        conn.close()
    return {"type": "sqlite", "file_path": str(path), "table_count": len(tables), "tables": table_profiles}


def profile_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    profile: dict[str, Any] = {"type": "json", "file_path": str(path), "json_type": type(data).__name__}
    if isinstance(data, list):
        profile["item_count"] = len(data)
        keys = sorted({key for item in data if isinstance(item, dict) for key in item.keys()})
        profile["object_keys"] = keys
    elif isinstance(data, dict):
        profile["key_count"] = len(data)
        profile["object_keys"] = sorted(data.keys())
    return profile


def profile_data_file(path: Path) -> Optional[dict[str, Any]]:
    extension = path.suffix.lower().lstrip(".")
    if extension == "csv":
        return profile_csv(path)
    if extension in {"sqlite", "db"}:
        return profile_sqlite(path)
    if extension == "json":
        return profile_json(path)
    return None


def profile_data_sources(workspace: Path, *, status: Optional[str] = None) -> DataProfileRunResult:
    register = read_yaml(workspace / "source-register.yaml")
    sources = [source for source in register.get("sources", []) if isinstance(source, dict)]
    selected = [
        source
        for source in sources
        if (status is None or source.get("status") == status) and source.get("file_ext") in DATA_EXTENSIONS
    ]

    profiled = skipped = 0
    for source in selected:
        profile = profile_data_file(Path(str(source.get("file_path"))))
        if profile is None:
            skipped += 1
            continue
        source_id = str(source.get("source_id"))
        output_path = workspace / "outputs" / "data-profiles" / f"{source_id}.yaml"
        write_yaml(output_path, {"version": 1, "source_id": source_id, "profile": profile})
        source["data_profile"] = {"status": "profiled", "output_path": str(output_path)}
        profiled += 1

    register["sources"] = sources
    write_yaml(workspace / "source-register.yaml", register)
    return DataProfileRunResult(processed=len(selected), profiled=profiled, skipped=skipped)


def list_data_sources(workspace: Path) -> list[dict[str, Any]]:
    register = read_yaml(workspace / "source-register.yaml")
    return [
        source
        for source in register.get("sources", [])
        if isinstance(source, dict) and source.get("file_ext") in DATA_EXTENSIONS
    ]


def data_source_counts(workspace: Path) -> dict[str, int]:
    counts = {"total": 0, "profiled": 0, "unprofiled": 0}
    for source in list_data_sources(workspace):
        counts["total"] += 1
        if isinstance(source.get("data_profile"), dict) and source["data_profile"].get("status") == "profiled":
            counts["profiled"] += 1
        else:
            counts["unprofiled"] += 1
    return counts
