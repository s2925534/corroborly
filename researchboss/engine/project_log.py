from __future__ import annotations

from pathlib import Path
from typing import Any

from researchboss.core.yamlio import read_yaml, write_yaml


def add_decision(workspace: Path, text: str, *, reason: str = "") -> dict[str, str]:
    path = workspace / "decisions.md"
    existing = path.read_text(encoding="utf-8") if path.exists() else "# Decisions\n"
    decision_id = f"decision-{existing.count('## decision-') + 1:03d}"
    block = f"\n## {decision_id}\n\n- Decision: {text}\n- Reason: {reason or 'Not recorded'}\n"
    path.write_text(existing.rstrip() + block + "\n", encoding="utf-8")
    return {"id": decision_id, "decision": text, "reason": reason}


def list_decisions(workspace: Path) -> list[str]:
    path = workspace / "decisions.md"
    if not path.exists():
        return []
    return [line.strip("# ").strip() for line in path.read_text(encoding="utf-8").splitlines() if line.startswith("## ")]


def add_terminology(workspace: Path, term: str, definition: str) -> dict[str, str]:
    path = workspace / "terminology.yaml"
    doc = read_yaml(path)
    items = [item for item in doc.get("terms", []) if isinstance(item, dict)]
    record = {"term": term, "definition": definition}
    items = [item for item in items if item.get("term") != term]
    items.append(record)
    doc["terms"] = items
    write_yaml(path, doc)
    return record


def add_feedback(workspace: Path, text: str, *, source: str = "") -> dict[str, str]:
    path = workspace / "supervisor-feedback.yaml"
    doc = read_yaml(path)
    items = [item for item in doc.get("items", []) if isinstance(item, dict)]
    record = {"id": f"feedback-{len(items) + 1:03d}", "source": source, "text": text, "status": "open"}
    items.append(record)
    doc["items"] = items
    write_yaml(path, doc)
    return record


def add_context_change(workspace: Path, text: str) -> dict[str, str]:
    path = workspace / "context-changelog.md"
    existing = path.read_text(encoding="utf-8") if path.exists() else "# Context changelog\n"
    change_id = f"change-{existing.count('## change-') + 1:03d}"
    path.write_text(existing.rstrip() + f"\n\n## {change_id}\n\n{text}\n", encoding="utf-8")
    return {"id": change_id, "text": text}


def timeline_report(workspace: Path) -> dict[str, Any]:
    events = []
    for path in sorted((workspace / "outputs" / "logs" / "run-summaries").glob("*.yaml")):
        data = read_yaml(path)
        events.append({"kind": "run_summary", "path": str(path), "command": data.get("command"), "status": data.get("status")})
    for decision in list_decisions(workspace):
        events.append({"kind": "decision", "id": decision})
    feedback = read_yaml(workspace / "supervisor-feedback.yaml") if (workspace / "supervisor-feedback.yaml").exists() else {}
    for item in feedback.get("items", []):
        if isinstance(item, dict):
            events.append({"kind": "feedback", "id": item.get("id"), "status": item.get("status")})
    report = {"version": 1, "event_count": len(events), "events": events}
    write_yaml(workspace / "outputs" / "reports" / "timeline.yaml", report)
    return report
