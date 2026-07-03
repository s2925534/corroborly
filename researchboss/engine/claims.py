from __future__ import annotations

from pathlib import Path
from typing import Any

from researchboss.core.yamlio import read_yaml, write_yaml


CLAIM_STATUSES = {"active", "supported", "needs_evidence", "rejected", "needs_review"}


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
    claim = {
        "id": f"claim-{len(claims) + 1:03d}",
        "text": text,
        "linked_sources": linked_sources or [],
        "linked_research_questions": linked_research_questions or [],
        "status": "active",
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
