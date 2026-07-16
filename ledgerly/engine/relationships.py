from __future__ import annotations

from pathlib import Path
from typing import Any

from ledgerly.engine.artefacts import list_artefacts
from ledgerly.engine.claims import list_claims
from ledgerly.engine.research_questions import list_research_questions
from ledgerly.engine.sources import list_sources


def citation_relationship_map(workspace: Path) -> dict[str, Any]:
    """A simple local view of how sources, claims, and artefacts reference each
    other — which sources support which claims, and which sources/research
    questions each artefact is built on. No external graph service required.

    Claims don't currently have a direct link to artefacts in the data model
    (only sources and research questions do), so no claim-artefact edge is
    reported here; adding one would be a schema change, not a view change.
    """
    sources = {source.get("source_id"): source for source in list_sources(workspace) if source.get("source_id")}
    claims = list_claims(workspace)
    artefacts = list_artefacts(workspace)
    rq_groups = list_research_questions(workspace)
    research_questions = {
        rq.get("id"): rq
        for group in (rq_groups.get("candidates", []), rq_groups.get("approved", []), rq_groups.get("rejected", []))
        for rq in group
        if isinstance(rq, dict) and rq.get("id")
    }

    def _source_ref(source_id: str) -> dict[str, Any]:
        source = sources.get(source_id)
        return {"source_id": source_id, "file_name": source.get("file_name") if source else None, "known": source is not None}

    def _rq_ref(rq_id: str) -> dict[str, Any]:
        rq = research_questions.get(rq_id)
        return {"id": rq_id, "question": rq.get("question") if rq else None, "known": rq is not None}

    claim_rows = [
        {
            "id": claim.get("id"),
            "text": claim.get("text"),
            "status": claim.get("status"),
            "sources": [_source_ref(source_id) for source_id in claim.get("linked_sources", [])],
        }
        for claim in claims
    ]

    artefact_rows = [
        {
            "id": artefact.get("id"),
            "title": artefact.get("title"),
            "type": artefact.get("type"),
            "sources": [_source_ref(source_id) for source_id in artefact.get("linked_sources", [])],
            "research_questions": [_rq_ref(rq_id) for rq_id in artefact.get("linked_research_questions", [])],
        }
        for artefact in artefacts
    ]

    claims_by_source: dict[str, list[dict[str, Any]]] = {}
    for claim in claims:
        for source_id in claim.get("linked_sources", []):
            claims_by_source.setdefault(source_id, []).append({"id": claim.get("id"), "text": claim.get("text")})

    artefacts_by_source: dict[str, list[dict[str, Any]]] = {}
    for artefact in artefacts:
        for source_id in artefact.get("linked_sources", []):
            artefacts_by_source.setdefault(source_id, []).append({"id": artefact.get("id"), "title": artefact.get("title")})

    source_rows = [
        {
            "source_id": source_id,
            "file_name": source.get("file_name"),
            "status": source.get("status"),
            "claims": claims_by_source.get(source_id, []),
            "artefacts": artefacts_by_source.get(source_id, []),
        }
        for source_id, source in sources.items()
        if claims_by_source.get(source_id) or artefacts_by_source.get(source_id)
    ]

    return {
        "version": 1,
        "sources": source_rows,
        "claims": claim_rows,
        "artefacts": artefact_rows,
    }
