from __future__ import annotations

from pathlib import Path
from typing import Any

from ledgerly.core.constants import WORKSPACE_FILES
from ledgerly.core.runlog import utc_now_iso
from ledgerly.core.yamlio import read_yaml, write_yaml
from ledgerly.engine.claims import list_claims, stale_claims
from ledgerly.engine.project_log import timeline_report


def _read_settings(workspace: Path) -> dict[str, Any]:
    path = workspace / WORKSPACE_FILES.app_settings_local
    return read_yaml(path) if path.exists() else {}


def last_visited_at(workspace: Path) -> str | None:
    return _read_settings(workspace).get("last_visited_at")


def mark_visited(workspace: Path) -> str:
    """Record "now" as this workspace's last-visited timestamp. A deliberate,
    separate action from computing the digest -- callers decide whether
    viewing the digest counts as a visit, rather than every read silently
    resetting the baseline.
    """
    now = utc_now_iso()
    path = workspace / WORKSPACE_FILES.app_settings_local
    settings = read_yaml(path) if path.exists() else {}
    settings["last_visited_at"] = now
    write_yaml(path, settings)
    return now


def since_last_visit_digest(workspace: Path) -> dict[str, Any]:
    """A proactive "what changed since you were last here" summary
    (TODO.md Phase 32), complementing the on-demand research-progress log
    and stale-claims report with something computed automatically. Built
    entirely from data this project already timestamps -- the claim ledger
    (`created_at`/`updated_at`) and the project timeline (run summaries,
    decisions, terminology, feedback, context changes). Honestly scoped:
    sources and personal notes have no timestamp field anywhere in this
    codebase today, so new-source/new-note activity isn't reflected here --
    a real, separate gap, not silently claimed as covered.
    """
    since = last_visited_at(workspace)
    timeline = timeline_report(workspace)
    activity_events = [
        event for event in timeline.get("events", []) if since is None or (event.get("at") or "") > since
    ]

    claims = list_claims(workspace)
    new_claims = [claim for claim in claims if since is None or (claim.get("created_at") or "") > since]
    new_claim_ids = {claim.get("id") for claim in new_claims}
    updated_claims = [
        claim
        for claim in claims
        if claim.get("id") not in new_claim_ids and since is not None and (claim.get("updated_at") or "") > since
    ]
    stale = stale_claims(workspace)

    return {
        "version": 1,
        "is_first_visit": since is None,
        "last_visited_at": since,
        "generated_at": utc_now_iso(),
        "activity_event_count": len(activity_events),
        "activity_events": activity_events,
        "new_claim_count": len(new_claims),
        "new_claims": new_claims,
        "updated_claim_count": len(updated_claims),
        "updated_claims": updated_claims,
        "stale_open_claim_count": len(stale),
    }
