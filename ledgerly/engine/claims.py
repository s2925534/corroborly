from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ledgerly.core.yamlio import read_yaml, write_yaml


CLAIM_STATUSES = {"active", "supported", "needs_evidence", "rejected", "needs_review"}

# Claims in these statuses are considered settled/closed and are excluded from
# the stale-work report below — a "supported" or "rejected" claim not being
# touched further is expected, not neglect.
_OPEN_CLAIM_STATUSES = {"active", "needs_evidence", "needs_review"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def list_claims(workspace: Path) -> list[dict[str, Any]]:
    ledger = read_yaml(workspace / "claims-ledger.yaml")
    return [claim for claim in ledger.get("claims", []) if isinstance(claim, dict)]


def add_claim(
    workspace: Path,
    *,
    text: str,
    linked_sources: list[str] | None = None,
    linked_research_questions: list[str] | None = None,
) -> dict[str, Any]:
    ledger_path = workspace / "claims-ledger.yaml"
    ledger = read_yaml(ledger_path)
    claims = list_claims(workspace)
    now = _utc_now()
    claim = {
        "id": f"claim-{len(claims) + 1:03d}",
        "text": text,
        "linked_sources": linked_sources or [],
        "linked_research_questions": linked_research_questions or [],
        "status": "active",
        "created_at": now,
        "updated_at": now,
    }
    claims.append(claim)
    ledger["claims"] = claims
    write_yaml(ledger_path, ledger)
    return claim


def citation_gap_claims(workspace: Path) -> list[dict[str, Any]]:
    return [claim for claim in list_claims(workspace) if not claim.get("linked_sources")]


def set_claim_status(workspace: Path, claim_id: str, status: str) -> None:
    if status not in CLAIM_STATUSES:
        allowed = ", ".join(sorted(CLAIM_STATUSES))
        raise ValueError(f"Invalid claim status: {status!r}. Expected one of: {allowed}")
    ledger_path = workspace / "claims-ledger.yaml"
    ledger = read_yaml(ledger_path)
    claims = [claim for claim in ledger.get("claims", []) if isinstance(claim, dict)]
    for claim in claims:
        if claim.get("id") == claim_id:
            claim["status"] = status
            claim["updated_at"] = _utc_now()
            ledger["claims"] = claims
            write_yaml(ledger_path, ledger)
            return
    raise ValueError(f"Unknown claim_id: {claim_id}")


def claim_source_validation_report(workspace: Path) -> dict[str, Any]:
    register = read_yaml(workspace / "source-register.yaml")
    sources = {source.get("source_id"): source for source in register.get("sources", []) if isinstance(source, dict)}
    rows = []
    for claim in list_claims(workspace):
        issues = []
        for source_id in claim.get("linked_sources", []):
            source = sources.get(source_id)
            if not source:
                issues.append({"kind": "missing_source", "source_id": source_id})
            elif source.get("status") != "accepted":
                issues.append({"kind": "source_not_accepted", "source_id": source_id, "status": source.get("status")})
        rows.append({"claim_id": claim.get("id"), "status": "ok" if not issues else "needs_review", "issues": issues})
    report = {"version": 1, "claims": rows}
    write_yaml(workspace / "outputs" / "validation" / "claim-source-validation.yaml", report)
    return report


def write_citation_gap_report(workspace: Path) -> Path:
    gaps = citation_gap_claims(workspace)
    output_path = workspace / "outputs" / "validation" / "citation-gaps.yaml"
    write_yaml(output_path, {"version": 1, "gap_count": len(gaps), "claims": gaps})
    return output_path


def stale_claims(workspace: Path, *, days: int = 14) -> list[dict[str, Any]]:
    """Open claims (active/needs_evidence/needs_review) not updated in `days` days.

    Claims from workspaces created before `created_at`/`updated_at` tracking
    existed have neither field; their age can't be confirmed, so they're
    always included rather than silently assumed fresh.
    """
    now = datetime.now(timezone.utc)
    stale = []
    for claim in list_claims(workspace):
        if claim.get("status") not in _OPEN_CLAIM_STATUSES:
            continue
        last_touched = claim.get("updated_at") or claim.get("created_at")
        age_days: int | None = None
        if last_touched:
            try:
                touched_at = datetime.fromisoformat(last_touched)
                if touched_at.tzinfo is None:
                    touched_at = touched_at.replace(tzinfo=timezone.utc)
                age_days = (now - touched_at).days
            except ValueError:
                age_days = None
        if age_days is None or age_days >= days:
            stale.append(
                {
                    **claim,
                    "age_days": age_days,
                    "is_citation_gap": not claim.get("linked_sources"),
                }
            )
    return stale


def write_stale_claims_report(workspace: Path, *, days: int = 14) -> Path:
    claims = stale_claims(workspace, days=days)
    output_path = workspace / "outputs" / "validation" / "stale-claims.yaml"
    write_yaml(
        output_path,
        {
            "version": 1,
            "days_threshold": days,
            "generated_at": _utc_now(),
            "stale_count": len(claims),
            "citation_gap_count": sum(1 for claim in claims if claim["is_citation_gap"]),
            "claims": claims,
        },
    )
    return output_path
