import time
from pathlib import Path

from ledgerly.engine.claims import add_claim, set_claim_status
from ledgerly.engine.digest import last_visited_at, mark_visited, since_last_visit_digest
from ledgerly.engine.workspace import init_workspace


def test_last_visited_at_is_none_before_first_mark(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="")
    assert last_visited_at(workspace) is None


def test_mark_visited_persists_a_timestamp(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="")

    stamp = mark_visited(workspace)

    assert stamp == last_visited_at(workspace)
    assert "T" in stamp  # ISO datetime


def test_digest_is_first_visit_when_never_marked(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="")
    add_claim(workspace, text="A claim added before any visit was recorded.")

    digest = since_last_visit_digest(workspace)

    assert digest["is_first_visit"] is True
    assert digest["last_visited_at"] is None
    # On a first visit nothing has a confirmed "before" baseline to compare
    # against, so new/updated counts default to including everything that
    # exists -- never silently reported as zero when there's real content.
    assert digest["new_claim_count"] == 1


def test_digest_reports_claims_added_after_last_visit(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="")
    add_claim(workspace, text="Claim before the visit.")
    mark_visited(workspace)
    time.sleep(1.1)  # ISO-second timestamp resolution -- ensure strict ordering
    add_claim(workspace, text="Claim after the visit.")

    digest = since_last_visit_digest(workspace)

    assert digest["is_first_visit"] is False
    assert digest["new_claim_count"] == 1
    assert digest["new_claims"][0]["text"] == "Claim after the visit."


def test_digest_reports_claims_updated_after_last_visit(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="")
    claim = add_claim(workspace, text="Existing claim.")
    mark_visited(workspace)
    time.sleep(1.1)
    set_claim_status(workspace, claim["id"], "supported")

    digest = since_last_visit_digest(workspace)

    assert digest["new_claim_count"] == 0
    assert digest["updated_claim_count"] == 1
    assert digest["updated_claims"][0]["id"] == claim["id"]


def test_digest_includes_stale_open_claim_count(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="")
    add_claim(workspace, text="Old unsupported claim.")
    from ledgerly.core.yamlio import read_yaml, write_yaml
    from datetime import datetime, timedelta, timezone

    old_iso = (datetime.now(timezone.utc) - timedelta(days=30)).replace(microsecond=0).isoformat()
    ledger_path = workspace / "claims-ledger.yaml"
    ledger = read_yaml(ledger_path)
    ledger["claims"][0]["created_at"] = ledger["claims"][0]["updated_at"] = old_iso
    write_yaml(ledger_path, ledger)

    digest = since_last_visit_digest(workspace)

    assert digest["stale_open_claim_count"] == 1


def test_digest_includes_timeline_activity_since_last_visit(tmp_path: Path) -> None:
    from ledgerly.engine.project_log import add_decision

    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="")
    mark_visited(workspace)
    time.sleep(1.1)
    add_decision(workspace, "Switched to a new methodology.")

    digest = since_last_visit_digest(workspace)

    assert digest["activity_event_count"] >= 1
    assert any(event.get("kind") == "decision" for event in digest["activity_events"])
