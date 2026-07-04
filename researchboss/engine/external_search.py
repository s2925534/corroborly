from __future__ import annotations

import json
import os
import re
import hashlib
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from itertools import product
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from researchboss.core.yamlio import read_yaml, write_yaml
from researchboss.engine.ai import load_dotenv_values
from researchboss.engine.references import apa7_reference


SCOPUS_SEARCH_URL = "https://api.elsevier.com/content/search/scopus"
QUOTE_TRANSLATION = str.maketrans({"“": '"', "”": '"', "‘": "'", "’": "'"})
QUERY_STRATEGIES = {"broad", "balanced", "strict"}
DOMAIN_TERM_MAP = {
    "container": ["container logistics", "container terminal", "container operations", "container flow"],
    "port": ["port logistics", "maritime logistics", "terminal operations", "smart port"],
    "zotero": ["reference management", "research workflow", "citation management"],
    "evidence": ["evidence tracking", "claim validation", "source validation"],
    "interoperability": ["data interoperability", "semantic interoperability", "data harmonization"],
    "prediction": ["predictive analytics", "forecasting", "prediction model"],
    "scoring": ["scoring model", "performance evaluation", "KPI"],
    "routing": ["routing optimization", "resource allocation", "scheduling"],
    "traceability": ["traceability", "event tracking", "supply chain visibility"],
    "digital": ["digital twin", "IoT", "cyber physical system", "blockchain"],
    "ai": ["artificial intelligence", "machine learning", "deep learning"],
    "sustainability": ["sustainability", "carbon efficiency", "circular economy"],
}
FALLBACK_ANCHORS = ["research workflow", "evidence tracking", "source validation", "citation management"]
FALLBACK_METHODS = ["performance evaluation", "decision support", "quality assessment", "validation"]
FALLBACK_QUALIFIERS = ["systematic review", "case study", "framework", "methodology"]


@dataclass(frozen=True)
class ScopusCredentials:
    api_key: str
    inst_token: str | None = None


class ExternalSearchError(RuntimeError):
    pass


@dataclass(frozen=True)
class SearchThresholds:
    min_citations: int = 0
    year_from: int | None = None
    year_to: int | None = None
    open_access_only: bool = False
    max_results_per_query: int = 25
    low_result_threshold: int = 3

    @classmethod
    def from_options(
        cls,
        *,
        min_citations: int = 0,
        year_from: int | None = None,
        year_to: int | None = None,
        open_access_only: bool = False,
        max_results_per_query: int = 25,
        low_result_threshold: int = 3,
    ) -> "SearchThresholds":
        return cls(
            min_citations=max(0, min_citations),
            year_from=year_from,
            year_to=year_to,
            open_access_only=open_access_only,
            max_results_per_query=max(1, min(max_results_per_query, 200)),
            low_result_threshold=max(0, low_result_threshold),
        )


@dataclass(frozen=True)
class SearchBudgets:
    max_api_calls: int = 1
    max_generated_queries: int = 20
    max_refinement_rounds: int = 1
    max_result_pages: int = 1
    max_result_count: int = 200
    max_elapsed_seconds: int = 300

    @classmethod
    def from_options(
        cls,
        *,
        max_api_calls: int = 1,
        max_generated_queries: int = 20,
        max_refinement_rounds: int = 1,
        max_result_pages: int = 1,
        max_result_count: int = 200,
        max_elapsed_seconds: int = 300,
    ) -> "SearchBudgets":
        return cls(
            max_api_calls=max(0, max_api_calls),
            max_generated_queries=max(0, max_generated_queries),
            max_refinement_rounds=max(0, max_refinement_rounds),
            max_result_pages=max(0, max_result_pages),
            max_result_count=max(0, max_result_count),
            max_elapsed_seconds=max(0, max_elapsed_seconds),
        )

    def as_dict(self) -> dict[str, int]:
        return {
            "max_api_calls": self.max_api_calls,
            "max_generated_queries": self.max_generated_queries,
            "max_refinement_rounds": self.max_refinement_rounds,
            "max_result_pages": self.max_result_pages,
            "max_result_count": self.max_result_count,
            "max_elapsed_seconds": self.max_elapsed_seconds,
        }


def require_external_search_flag(enabled: bool) -> None:
    if not enabled:
        raise ExternalSearchError("Pass --external-search to explicitly allow this external academic search action.")


def scopus_credentials(workspace: Path | None = None) -> ScopusCredentials:
    env_values = load_dotenv_values(Path.cwd() / ".env")
    if workspace is not None:
        env_values = {**env_values, **load_dotenv_values(workspace / ".env")}
    api_key = os.environ.get("SCOPUS_API_KEY") or env_values.get("SCOPUS_API_KEY") or ""
    inst_token = os.environ.get("INST_TOKEN") or env_values.get("INST_TOKEN") or None
    if not api_key:
        raise ExternalSearchError("Missing SCOPUS_API_KEY")
    return ScopusCredentials(api_key=api_key, inst_token=inst_token)


def normalize_query_line(line: str) -> str:
    line = line.translate(QUOTE_TRANSLATION).strip()
    if line.startswith("(") and line.endswith(")"):
        line = line[1:-1].strip()
    return re.sub(r"\s+", " ", line)


def query_history_key(query: str) -> str:
    return normalize_query_line(query).lower()


def _quote(term: str) -> str:
    return f'"{term}"'


def _dedupe(items: list[str]) -> list[str]:
    out = []
    seen = set()
    for item in items:
        normalized = normalize_query_line(item)
        key = normalized.lower()
        if normalized and key not in seen:
            seen.add(key)
            out.append(normalized)
    return out


def _dedupe_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    seen = set()
    for record in records:
        query = normalize_query_line(str(record.get("query") or ""))
        key = query.lower()
        if not query or key in seen:
            continue
        seen.add(key)
        out.append({**record, "query": query})
    return out


def _context_text(workspace: Path) -> str:
    context = read_yaml(workspace / "research-context.yaml")
    project = context.get("project", {}) if isinstance(context.get("project"), dict) else {}
    parts = [str(project.get("topic") or ""), str(project.get("type") or "")]
    for path in (workspace / "research-questions.yaml", workspace / "research-question-candidates.yaml"):
        data = read_yaml(path)
        for key in ("research_questions", "candidates"):
            for item in data.get(key, []):
                if isinstance(item, dict):
                    parts.append(str(item.get("question") or ""))
                    parts.extend(str(sub) for sub in item.get("subquestions", []) if sub)
    return " ".join(parts)


def _research_question_records(workspace: Path) -> list[dict[str, Any]]:
    records = []
    for path, key in (
        (workspace / "research-questions.yaml", "research_questions"),
        (workspace / "research-question-candidates.yaml", "candidates"),
    ):
        data = read_yaml(path)
        for index, item in enumerate(data.get(key, []), start=1):
            if not isinstance(item, dict):
                continue
            question = str(item.get("question") or "")
            rq_id = str(item.get("id") or item.get("rq_id") or f"{key}-{index}")
            records.append(
                {
                    "id": rq_id,
                    "question": question,
                    "status": item.get("status") or ("candidate" if key == "candidates" else "approved"),
                    "terms": set(re.findall(r"[A-Za-z][A-Za-z0-9-]{3,}", question.lower())),
                }
            )
    return records


def _terms_from_context(text: str) -> list[str]:
    words = re.findall(r"[A-Za-z][A-Za-z0-9-]{3,}", text.lower())
    stop = {
        "research",
        "question",
        "questions",
        "within",
        "using",
        "does",
        "what",
        "which",
        "this",
        "that",
        "with",
        "from",
        "into",
        "quality",
        "effect",
        "affect",
    }
    counts: dict[str, int] = {}
    for word in words:
        if word not in stop:
            counts[word] = counts.get(word, 0) + 1
    ranked = sorted(counts, key=lambda word: (-counts[word], word))
    return ranked[:12] or ["evidence", "research", "workflow"]


def _expanded_terms_from_context(text: str) -> list[str]:
    text_lower = text.lower()
    terms = []
    for marker, values in DOMAIN_TERM_MAP.items():
        if marker in text_lower or any(value.lower() in text_lower for value in values):
            terms.extend(values)
    terms.extend(_terms_from_context(text))
    return _dedupe(terms)


def _linked_rqs_for_query(query: str, rq_records: list[dict[str, Any]]) -> list[str]:
    query_terms = set(re.findall(r"[A-Za-z][A-Za-z0-9-]{3,}", query.lower()))
    linked = []
    for rq in rq_records:
        overlap = query_terms.intersection(rq.get("terms") or set())
        if len(overlap) >= 1:
            linked.append(str(rq["id"]))
    return linked


def _query_group_from_heading(line: str) -> str | None:
    cleaned = normalize_query_line(line).strip(":- ")
    if not cleaned:
        return None
    if cleaned.lower().startswith("search parameters"):
        cleaned = re.sub(r"^search parameters\s*[-:–—]?\s*", "", cleaned, flags=re.IGNORECASE).strip()
    return cleaned or None


def parse_legacy_params_file(path: Path) -> list[dict[str, Any]]:
    records = []
    current_group: str | None = None
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = normalize_query_line(raw)
        if not line:
            continue
        lower = line.lower()
        looks_like_query = '"' in line or " and " in lower or " or " in lower or "title-abs-key" in lower
        if lower.startswith("search parameters") or (line.endswith(":") and not looks_like_query):
            current_group = _query_group_from_heading(line)
            continue
        if looks_like_query:
            records.append(
                {
                    "query": line,
                    "source": "legacy_params_file",
                    "source_path": str(path),
                    "group_label": current_group,
                    "strategy": "imported",
                }
            )
    return _dedupe_records(records)


def _generated_query_records(
    workspace: Path,
    *,
    max_queries: int,
    strategy: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    strategy = strategy.lower().strip()
    if strategy not in QUERY_STRATEGIES:
        raise ExternalSearchError(f"Unsupported query strategy: {strategy}")
    terms = _expanded_terms_from_context(_context_text(workspace))
    anchor_terms = [
        term
        for term in terms
        if any(marker in term for marker in ("port", "container", "research", "evidence", "source", "citation"))
    ] or terms[:4] or FALLBACK_ANCHORS
    method_terms = [term for term in terms if term not in anchor_terms] or FALLBACK_METHODS
    qualifier_terms = [term for term in method_terms if term not in FALLBACK_METHODS] or FALLBACK_QUALIFIERS

    queries = []
    if strategy == "broad":
        for anchor, method in product(anchor_terms[:8], method_terms[:10]):
            if anchor != method:
                queries.append(f"{_quote(anchor)} AND {_quote(method)}")
    elif strategy == "strict":
        for anchor, method, qualifier in product(anchor_terms[:5], method_terms[:8], qualifier_terms[:6]):
            if len({anchor, method, qualifier}) == 3:
                queries.append(f"{_quote(anchor)} AND {_quote(method)} AND {_quote(qualifier)}")
    else:
        for anchor, method in product(anchor_terms[:6], method_terms[:8]):
            if anchor != method:
                queries.append(f"{_quote(anchor)} AND {_quote(method)}")
        for anchor, method, qualifier in product(anchor_terms[:4], method_terms[:6], FALLBACK_QUALIFIERS[:3]):
            if len({anchor, method, qualifier}) == 3:
                queries.append(f"{_quote(anchor)} AND {_quote(method)} AND {_quote(qualifier)}")

    records = [
        {
            "query": query,
            "source": "research_context_and_research_questions",
            "group_label": f"generated:{strategy}",
            "strategy": strategy,
        }
        for query in _dedupe(queries)
    ][: max(1, max_queries)]
    return records, {
        "strategy": strategy,
        "anchors": anchor_terms[:8],
        "methods": method_terms[:10],
        "qualifiers": qualifier_terms[:8],
    }


def generate_search_query_plan(
    workspace: Path,
    *,
    max_queries: int = 20,
    strategy: str = "balanced",
    params_file: Path | None = None,
) -> dict[str, Any]:
    generated_records, term_metadata = _generated_query_records(workspace, max_queries=max_queries, strategy=strategy)
    imported_records = parse_legacy_params_file(params_file) if params_file else []
    rq_records = _research_question_records(workspace)
    query_records = _dedupe_records([*imported_records, *generated_records])[: max(1, max_queries)]
    query_records = [
        {
            **record,
            "linked_research_questions": _linked_rqs_for_query(str(record.get("query") or ""), rq_records),
            "external_search_performed": False,
        }
        for record in query_records
    ]
    queries = [record["query"] for record in query_records]
    plan = {
        "version": 2,
        "source": "legacy_params_file_and_research_context" if imported_records else "research_context_and_research_questions",
        "external_search_performed": False,
        "strategy": strategy,
        "term_metadata": term_metadata,
        "imported_query_count": len(imported_records),
        "generated_query_count": len(generated_records),
        "queries": queries,
        "query_records": query_records,
    }
    write_yaml(workspace / "outputs" / "recommendations" / "external-search-query-plan.yaml", plan)
    return plan


def query_history_path(workspace: Path) -> Path:
    return workspace / "outputs" / "recommendations" / "external-search-query-history.yaml"


def load_query_history(workspace: Path) -> dict[str, Any]:
    path = query_history_path(workspace)
    if not path.is_file():
        return {"version": 1, "queries": {}}
    data = read_yaml(path)
    if isinstance(data.get("queries"), dict):
        return data
    return {"version": 1, "queries": {}}


def record_queries_used(workspace: Path, queries: list[str], metrics: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    history = load_query_history(workspace)
    records = history.setdefault("queries", {})
    metrics_by_query = {query_history_key(str(item.get("query") or "")): item for item in metrics or []}
    now = datetime.now(timezone.utc).isoformat()
    for query in _dedupe(queries):
        key = query_history_key(query)
        previous = records.get(key, {})
        records[key] = {
            "query": normalize_query_line(query),
            "first_used_at": previous.get("first_used_at") or now,
            "last_used_at": now,
            "runs": int(previous.get("runs", 0)) + 1,
            "last_metrics": metrics_by_query.get(key, {}),
        }
    write_yaml(query_history_path(workspace), history)
    return history


def filter_unused_queries(workspace: Path, queries: list[str]) -> list[str]:
    history = load_query_history(workspace)
    used = set(history.get("queries", {}).keys())
    return [query for query in _dedupe(queries) if query_history_key(query) not in used]


def external_candidate_register_path(workspace: Path) -> Path:
    return workspace / "outputs" / "recommendations" / "external-paper-candidates.yaml"


def query_validation_path(workspace: Path) -> Path:
    return workspace / "outputs" / "validation" / "external-search-query-validation.yaml"


def batch_search_summary_path(workspace: Path) -> Path:
    return workspace / "outputs" / "external-search" / "scopus-batch-run-summary.yaml"


def auto_refine_plan_path(workspace: Path) -> Path:
    return workspace / "outputs" / "recommendations" / "external-search-refine-plan.yaml"


def filtered_candidate_log_path(workspace: Path) -> Path:
    return workspace / "outputs" / "external-search" / "scopus-filtered-candidates.yaml"


def high_signal_candidate_report_path(workspace: Path) -> Path:
    return workspace / "outputs" / "recommendations" / "external-high-signal-candidates.yaml"


def external_candidate_import_report_path(workspace: Path) -> Path:
    return workspace / "outputs" / "recommendations" / "external-candidate-import.yaml"


def external_candidate_duplicates_path(workspace: Path) -> Path:
    return workspace / "outputs" / "validation" / "external-candidate-duplicates.yaml"


def external_evidence_validation_path(workspace: Path) -> Path:
    return workspace / "outputs" / "validation" / "external-search-evidence-validation.yaml"


def external_run_comparison_path(workspace: Path) -> Path:
    return workspace / "outputs" / "validation" / "external-search-run-comparison.yaml"


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def _year_from_entry(entry: dict[str, Any]) -> int | None:
    cover_date = str(entry.get("prism:coverDate") or entry.get("coverDate") or "")
    match = re.search(r"\b(19|20)\d{2}\b", cover_date)
    return int(match.group(0)) if match else None


def _truthy_open_access(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "open", "openaccess"}


def _normalize_doi(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip().lower()
    if not text:
        return None
    text = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", text)
    text = re.sub(r"^doi:\s*", "", text)
    match = re.search(r"10\.\d{4,9}/[-._;()/:a-z0-9]+", text, flags=re.IGNORECASE)
    return match.group(0).rstrip(".,; )").lower() if match else None


def _normalize_title(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def _text_terms(value: Any) -> set[str]:
    stop = {
        "about",
        "against",
        "among",
        "and",
        "from",
        "into",
        "paper",
        "research",
        "that",
        "this",
        "with",
        "without",
    }
    return {
        term
        for term in re.findall(r"[A-Za-z][A-Za-z0-9-]{3,}", str(value or "").lower())
        if term not in stop
    }


def _authors_from_entry(entry: dict[str, Any]) -> list[dict[str, Any]]:
    authors = entry.get("author")
    if not isinstance(authors, list):
        return []
    out = []
    for author in authors:
        if not isinstance(author, dict):
            continue
        preferred = author.get("preferred-name")
        preferred = preferred if isinstance(preferred, dict) else {}
        out.append(
            {
                "name": author.get("authname") or author.get("ce:indexed-name") or preferred.get("surname"),
                "authid": author.get("authid"),
                "affiliation_id": author.get("afid"),
            }
        )
    return out


def _links_from_entry(entry: dict[str, Any]) -> list[dict[str, str]]:
    links = entry.get("link")
    if not isinstance(links, list):
        return []
    out = []
    for link in links:
        if isinstance(link, dict) and link.get("@href"):
            out.append({"ref": str(link.get("@ref") or ""), "href": str(link["@href"])})
    return out


def full_text_availability(entry: dict[str, Any]) -> dict[str, Any]:
    links = _links_from_entry(entry)
    doi = entry.get("prism:doi") or entry.get("doi")
    open_access = _truthy_open_access(entry.get("openaccess") or entry.get("openaccessFlag"))
    has_full_text_link = any("scopus" not in link["href"].lower() for link in links)
    return {
        "open_access_flag": open_access,
        "doi_present": bool(doi),
        "link_count": len(links),
        "possible_full_text_link": has_full_text_link,
        "full_text_retrieved": False,
        "notes": "Availability is inferred from metadata only; ResearchBoss does not download or scrape full text here.",
    }


def score_scopus_entry(entry: dict[str, Any], *, current_year: int | None = None) -> dict[str, Any]:
    current_year = current_year or datetime.now(timezone.utc).year
    citation_count = _safe_int(entry.get("citedby-count"))
    year = _year_from_entry(entry)
    doi = entry.get("prism:doi") or entry.get("doi")
    eid = entry.get("eid")
    pii = entry.get("pii")
    title = entry.get("dc:title") or entry.get("title") or "Untitled"
    source_title = entry.get("prism:publicationName") or entry.get("source-title")
    document_type = entry.get("subtypeDescription") or entry.get("subtype")
    open_access = _truthy_open_access(entry.get("openaccess") or entry.get("openaccessFlag"))
    authors = _authors_from_entry(entry)
    author_ids = [author["authid"] for author in authors if author.get("authid")]

    citation_score = min(40, citation_count // 5)
    recency_score = 0
    if year:
        age = max(0, current_year - year)
        recency_score = max(0, 20 - min(age, 20))
    identifier_score = 5 * sum(1 for value in (doi, eid, pii) if value)
    source_score = 10 if source_title else 0
    author_score = min(10, len(author_ids) * 2)
    open_access_score = 5 if open_access else 0
    score = min(100, citation_score + recency_score + identifier_score + source_score + author_score + open_access_score)

    reasons = []
    if citation_count:
        reasons.append(f"{citation_count} citations")
    if year:
        reasons.append(f"published in {year}")
    if source_title:
        reasons.append("source title available")
    if author_ids:
        reasons.append("indexed author IDs available")
    if doi:
        reasons.append("DOI available")
    if open_access:
        reasons.append("open-access flag present")

    return {
        "candidate_id": external_candidate_id(entry),
        "title": str(title),
        "year": year,
        "citation_count": citation_count,
        "source_title": source_title,
        "document_type": document_type,
        "doi": doi,
        "eid": eid,
        "pii": pii,
        "open_access": open_access,
        "authors": authors,
        "quality_score": score,
        "quality_reasons": reasons,
        "full_text_availability": full_text_availability(entry),
        "metadata_only": True,
        "review_status": "external_candidate",
    }


def external_candidate_id(entry: dict[str, Any]) -> str:
    basis = "|".join(
        str(entry.get(key) or "")
        for key in ("eid", "prism:doi", "doi", "dc:title", "prism:coverDate")
    )
    digest = hashlib.sha256(basis.encode("utf-8")).hexdigest()[:12]
    return f"ext-scopus-{digest}"


def candidate_passes_thresholds(candidate: dict[str, Any], thresholds: SearchThresholds) -> bool:
    if int(candidate.get("citation_count") or 0) < thresholds.min_citations:
        return False
    year = candidate.get("year")
    if thresholds.year_from is not None and (not year or int(year) < thresholds.year_from):
        return False
    if thresholds.year_to is not None and (not year or int(year) > thresholds.year_to):
        return False
    if thresholds.open_access_only and not candidate.get("open_access"):
        return False
    return True


def threshold_failure_reasons(candidate: dict[str, Any], thresholds: SearchThresholds) -> list[dict[str, Any]]:
    reasons = []
    citation_count = int(candidate.get("citation_count") or 0)
    if citation_count < thresholds.min_citations:
        reasons.append(
            {
                "kind": "below_min_citations",
                "field": "citation_count",
                "observed": citation_count,
                "threshold": thresholds.min_citations,
            }
        )
    year = candidate.get("year")
    if thresholds.year_from is not None and not year:
        reasons.append(
            {
                "kind": "missing_year",
                "field": "year",
                "observed": None,
                "threshold": f">={thresholds.year_from}",
            }
        )
    elif thresholds.year_from is not None and int(year) < thresholds.year_from:
        reasons.append(
            {
                "kind": "before_year_from",
                "field": "year",
                "observed": int(year),
                "threshold": thresholds.year_from,
            }
        )
    if thresholds.year_to is not None and not year:
        reasons.append(
            {
                "kind": "missing_year",
                "field": "year",
                "observed": None,
                "threshold": f"<={thresholds.year_to}",
            }
        )
    elif thresholds.year_to is not None and int(year) > thresholds.year_to:
        reasons.append(
            {
                "kind": "after_year_to",
                "field": "year",
                "observed": int(year),
                "threshold": thresholds.year_to,
            }
        )
    if thresholds.open_access_only and not candidate.get("open_access"):
        reasons.append(
            {
                "kind": "not_open_access",
                "field": "open_access",
                "observed": bool(candidate.get("open_access")),
                "threshold": True,
            }
        )
    return reasons


def score_scopus_entries(entries: list[dict[str, Any]], thresholds: SearchThresholds) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    scored = [score_scopus_entry(entry) for entry in entries if isinstance(entry, dict)]
    accepted = [candidate for candidate in scored if candidate_passes_thresholds(candidate, thresholds)]
    accepted.sort(key=lambda item: (-int(item.get("quality_score") or 0), -int(item.get("citation_count") or 0), str(item.get("title") or "")))
    skipped = [candidate for candidate in scored if not candidate_passes_thresholds(candidate, thresholds)]
    return accepted, skipped


def _keyword_coverage(query: str, candidates: list[dict[str, Any]]) -> dict[str, Any]:
    terms = [term.lower() for term in re.findall(r"[A-Za-z][A-Za-z0-9-]{3,}", query)]
    title_text = " ".join(str(candidate.get("title") or "").lower() for candidate in candidates)
    covered = sorted({term for term in terms if term in title_text})
    missing = sorted({term for term in terms if term not in title_text})
    return {
        "terms": sorted(set(terms)),
        "covered_terms": covered,
        "missing_terms": missing,
        "coverage_ratio": round(len(covered) / len(set(terms)), 3) if terms else 0,
    }


def query_refinement_suggestions(query: str, candidates: list[dict[str, Any]], *, no_results: bool) -> list[str]:
    suggestions = []
    normalized = normalize_query_line(query)
    coverage = _keyword_coverage(normalized, candidates)
    if no_results:
        suggestions.append("Broaden the query by removing the least essential quoted term.")
        suggestions.append("Try synonyms from approved research questions or accepted-source keywords.")
    if coverage["missing_terms"]:
        suggestions.append(f"Review missing title terms: {', '.join(coverage['missing_terms'][:5])}.")
    if candidates and not any(candidate.get("open_access") for candidate in candidates):
        suggestions.append("Consider a separate open-access-focused search if full text is required.")
    return suggestions


def query_validation_report(
    *,
    query: str,
    entries: list[dict[str, Any]],
    accepted_candidates: list[dict[str, Any]],
    skipped_candidates: list[dict[str, Any]],
    thresholds: SearchThresholds,
) -> dict[str, Any]:
    processed = len(entries)
    scored_entries = [entry for entry in entries if isinstance(entry, dict)]
    accepted = len(accepted_candidates)
    duplicate_ids = len(scored_entries) - len({external_candidate_id(entry) for entry in scored_entries})
    skipped_results = processed - len(scored_entries)
    no_results = processed == 0
    low_results = processed <= thresholds.low_result_threshold
    return {
        "query": normalize_query_line(query),
        "processed": processed,
        "accepted_candidates": accepted,
        "filtered_candidates": len(skipped_candidates),
        "skipped_candidates": len(skipped_candidates),
        "skipped_results": skipped_results,
        "duplicate_count": duplicate_ids,
        "duplicate_rate": round(duplicate_ids / processed, 3) if processed else 0,
        "threshold_pass_rate": round(accepted / processed, 3) if processed else 0,
        "keyword_coverage": _keyword_coverage(query, accepted_candidates),
        "no_results": no_results,
        "low_results": low_results,
        "refinement_suggestions": query_refinement_suggestions(query, accepted_candidates, no_results=no_results),
        "thresholds": {
            "min_citations": thresholds.min_citations,
            "year_from": thresholds.year_from,
            "year_to": thresholds.year_to,
            "open_access_only": thresholds.open_access_only,
            "max_results_per_query": thresholds.max_results_per_query,
            "low_result_threshold": thresholds.low_result_threshold,
        },
    }


def update_external_candidate_register(
    workspace: Path,
    *,
    provider: str,
    query: str,
    candidates: list[dict[str, Any]],
    skipped_candidates: list[dict[str, Any]],
    validation: dict[str, Any],
    snapshot_path: str,
) -> dict[str, Any]:
    path = external_candidate_register_path(workspace)
    register = read_yaml(path) if path.exists() else {"version": 1, "candidates": [], "runs": []}
    existing = {
        str(candidate.get("candidate_id")): candidate
        for candidate in register.get("candidates", [])
        if isinstance(candidate, dict) and candidate.get("candidate_id")
    }
    now = datetime.now(timezone.utc).isoformat()
    for candidate in candidates:
        candidate_id = str(candidate["candidate_id"])
        previous = existing.get(candidate_id, {})
        existing[candidate_id] = {
            **previous,
            **candidate,
            "provider": provider,
            "first_seen_at": previous.get("first_seen_at") or now,
            "last_seen_at": now,
            "queries": _dedupe([*(previous.get("queries") or []), query]),
        }
    register["candidates"] = sorted(existing.values(), key=lambda item: (-int(item.get("quality_score") or 0), str(item.get("title") or "")))
    register.setdefault("runs", []).append(
        {
            "provider": provider,
            "query": normalize_query_line(query),
            "created_at": now,
            "snapshot_path": snapshot_path,
            "candidate_count": len(candidates),
            "skipped_count": len(skipped_candidates),
            "no_results": validation["no_results"],
            "low_results": validation["low_results"],
        }
    )
    write_yaml(path, register)
    return register


def import_external_candidates(workspace: Path, candidate_ids: list[str]) -> dict[str, Any]:
    if not candidate_ids:
        raise ExternalSearchError("At least one --candidate-id is required.")
    candidate_path = external_candidate_register_path(workspace)
    if not candidate_path.exists():
        raise ExternalSearchError(f"External candidate register does not exist: {candidate_path}")

    register = read_yaml(candidate_path)
    candidates = [candidate for candidate in register.get("candidates", []) if isinstance(candidate, dict)]
    candidate_map = {str(candidate.get("candidate_id")): candidate for candidate in candidates if candidate.get("candidate_id")}

    source_path = workspace / "source-register.yaml"
    source_register = read_yaml(source_path) if source_path.exists() else {"version": 1, "sources": []}
    source_register.setdefault("version", 1)
    source_register.setdefault("sources", [])
    existing_source_ids = {
        str(source.get("source_id"))
        for source in source_register.get("sources", [])
        if isinstance(source, dict) and source.get("source_id")
    }

    now = datetime.now(timezone.utc).isoformat()
    imported = []
    skipped = []
    missing = []
    for candidate_id in _dedupe([str(value) for value in candidate_ids]):
        candidate = candidate_map.get(candidate_id)
        if not candidate:
            missing.append({"candidate_id": candidate_id, "reason": "candidate_not_found"})
            continue
        source_id = candidate.get("imported_source_id") or _candidate_source_id(candidate)
        if source_id in existing_source_ids:
            candidate["review_status"] = "imported_pending_review"
            candidate["imported_source_id"] = source_id
            candidate["imported_at"] = candidate.get("imported_at") or now
            skipped.append({"candidate_id": candidate_id, "source_id": source_id, "reason": "source_already_exists"})
            continue

        source_record = _source_record_from_external_candidate(candidate, source_id=str(source_id), imported_at=now)
        source_register["sources"].append(source_record)
        existing_source_ids.add(str(source_id))
        candidate["review_status"] = "imported_pending_review"
        candidate["imported_source_id"] = source_id
        candidate["imported_at"] = now
        imported.append({"candidate_id": candidate_id, "source_id": source_id})

    write_yaml(source_path, source_register)
    register["candidates"] = candidates
    write_yaml(candidate_path, register)

    report = {
        "version": 1,
        "created_at": now,
        "requested_candidate_ids": _dedupe([str(value) for value in candidate_ids]),
        "imported_count": len(imported),
        "skipped_count": len(skipped),
        "missing_count": len(missing),
        "imported": imported,
        "skipped": skipped,
        "missing": missing,
        "notes": "Imported candidates are metadata-only pending-review sources; they are not accepted evidence until reviewed.",
    }
    write_yaml(external_candidate_import_report_path(workspace), report)
    return report


def _candidate_source_id(candidate: dict[str, Any]) -> str:
    candidate_id = str(candidate.get("candidate_id") or "")
    if candidate_id:
        return candidate_id
    digest = hashlib.sha256(json.dumps(candidate, sort_keys=True).encode("utf-8")).hexdigest()[:12]
    return f"external-candidate-{digest}"


def _source_record_from_external_candidate(candidate: dict[str, Any], *, source_id: str, imported_at: str) -> dict[str, Any]:
    return {
        "source_id": source_id,
        "provider": f"external_search:{candidate.get('provider') or 'unknown'}",
        "file_path": None,
        "file_name": candidate.get("title") or source_id,
        "file_ext": "metadata",
        "content_hash": None,
        "status": "pending_review",
        "discovered_at": imported_at,
        "notes": "Metadata-only source imported from reviewed external candidate register.",
        "metadata_only": True,
        "external_candidate_id": candidate.get("candidate_id"),
        "citation_metadata": {
            "title": candidate.get("title"),
            "authors": candidate.get("authors") or [],
            "year": candidate.get("year"),
            "doi": candidate.get("doi"),
            "publication_title": candidate.get("source_title"),
            "item_type": candidate.get("document_type"),
            "eid": candidate.get("eid"),
            "pii": candidate.get("pii"),
        },
        "external_search": {
            "quality_score": candidate.get("quality_score"),
            "quality_reasons": candidate.get("quality_reasons") or [],
            "citation_count": candidate.get("citation_count"),
            "open_access": bool(candidate.get("open_access")),
            "queries": candidate.get("queries") or [],
            "full_text_availability": candidate.get("full_text_availability") or {},
        },
    }


def _budget_exhaustion_reasons(budgets: SearchBudgets, used: dict[str, int], elapsed_seconds: float) -> list[str]:
    checks = {
        "api_calls": ("max_api_calls", budgets.max_api_calls),
        "generated_queries": ("max_generated_queries", budgets.max_generated_queries),
        "refinement_rounds": ("max_refinement_rounds", budgets.max_refinement_rounds),
        "result_pages": ("max_result_pages", budgets.max_result_pages),
        "result_count": ("max_result_count", budgets.max_result_count),
    }
    reasons = [
        f"{used_key}_budget_exhausted"
        for used_key, (_limit_key, limit) in checks.items()
        if int(used.get(used_key) or 0) > limit
    ]
    if elapsed_seconds > budgets.max_elapsed_seconds:
        reasons.append("elapsed_time_budget_exhausted")
    return reasons


def budget_status_report(budgets: SearchBudgets, used: dict[str, int], elapsed_seconds: float) -> dict[str, Any]:
    reasons = _budget_exhaustion_reasons(budgets, used, elapsed_seconds)
    return {
        "limits": budgets.as_dict(),
        "used": {
            "api_calls": int(used.get("api_calls") or 0),
            "generated_queries": int(used.get("generated_queries") or 0),
            "refinement_rounds": int(used.get("refinement_rounds") or 0),
            "result_pages": int(used.get("result_pages") or 0),
            "result_count": int(used.get("result_count") or 0),
            "elapsed_seconds": round(elapsed_seconds, 3),
        },
        "within_budget": not reasons,
        "exhausted": bool(reasons),
        "exhaustion_reasons": reasons,
    }


def _ensure_scopus_budget_available(budgets: SearchBudgets, thresholds: SearchThresholds) -> None:
    requested = {
        "api_calls": 1,
        "generated_queries": 0,
        "refinement_rounds": 0,
        "result_pages": 1,
        "result_count": thresholds.max_results_per_query,
    }
    reasons = _budget_exhaustion_reasons(budgets, requested, 0)
    if reasons:
        raise ExternalSearchError(f"Search budget exhausted before Scopus request: {', '.join(reasons)}")


def update_filtered_candidate_log(
    workspace: Path,
    *,
    provider: str,
    query: str,
    skipped_candidates: list[dict[str, Any]],
    entries: list[Any],
    thresholds: SearchThresholds,
    snapshot_path: str,
) -> dict[str, Any]:
    path = filtered_candidate_log_path(workspace)
    log = read_yaml(path) if path.exists() else {"version": 1, "provider": provider, "candidates": []}
    eid_counts: dict[str, int] = {}
    for entry in entries:
        if isinstance(entry, dict) and entry.get("eid"):
            eid = str(entry["eid"])
            eid_counts[eid] = eid_counts.get(eid, 0) + 1
    now = datetime.now(timezone.utc).isoformat()
    rows = []
    for candidate in skipped_candidates:
        reasons = threshold_failure_reasons(candidate, thresholds)
        metadata_flags = []
        if not candidate.get("doi"):
            metadata_flags.append({"kind": "missing_doi", "field": "doi", "observed": None})
        eid = candidate.get("eid")
        if eid and eid_counts.get(str(eid), 0) > 1:
            metadata_flags.append({"kind": "duplicate_eid_in_query", "field": "eid", "observed": eid})
        row = {
            "provider": provider,
            "query": normalize_query_line(query),
            "created_at": now,
            "candidate_id": candidate.get("candidate_id"),
            "title": candidate.get("title"),
            "doi": candidate.get("doi"),
            "eid": candidate.get("eid"),
            "year": candidate.get("year"),
            "citation_count": candidate.get("citation_count"),
            "failure_reasons": reasons,
            "metadata_flags": metadata_flags,
            "snapshot_path": snapshot_path,
        }
        rows.append(row)
    log["provider"] = provider
    log.setdefault("candidates", []).extend(rows)
    log["filtered_count"] = len(log.get("candidates", []))
    write_yaml(path, log)
    return log


def update_batch_search_run_summary(
    workspace: Path,
    *,
    provider: str,
    metrics: dict[str, Any],
    validation: dict[str, Any],
) -> dict[str, Any]:
    path = batch_search_summary_path(workspace)
    summary = read_yaml(path) if path.exists() else {"version": 1, "provider": provider, "runs": []}
    now = datetime.now(timezone.utc).isoformat()
    no_results = bool(metrics.get("no_results"))
    low_results = bool(metrics.get("low_results")) and not no_results
    run = {
        "query": normalize_query_line(str(metrics.get("query") or "")),
        "created_at": now,
        "processed_count": int(metrics.get("processed") or 0),
        "candidate_count": int(metrics.get("candidate_count") or 0),
        "filtered_count": int(metrics.get("filtered_count") or validation.get("filtered_candidates") or 0),
        "skipped_count": int(metrics.get("skipped_count") or validation.get("skipped_results") or 0),
        "duplicate_count": int(metrics.get("duplicate_count") or validation.get("duplicate_count") or 0),
        "no_result_count": 1 if no_results else 0,
        "low_result_count": 1 if low_results else 0,
        "snapshot_path": metrics.get("snapshot_path"),
        "query_validation_path": metrics.get("query_validation_path"),
    }
    summary["provider"] = provider
    summary["updated_at"] = now
    summary.setdefault("runs", []).append(run)
    count_keys = [
        "processed_count",
        "candidate_count",
        "filtered_count",
        "skipped_count",
        "duplicate_count",
        "no_result_count",
        "low_result_count",
    ]
    runs = [item for item in summary.get("runs", []) if isinstance(item, dict)]
    summary["totals"] = {
        "query_count": len(runs),
        **{key: sum(int(item.get(key) or 0) for item in runs) for key in count_keys},
    }
    write_yaml(path, summary)
    return summary


def _candidate_metadata_completeness(candidate: dict[str, Any]) -> dict[str, Any]:
    checks = {
        "title": bool(candidate.get("title")),
        "year": bool(candidate.get("year")),
        "doi": bool(candidate.get("doi")),
        "eid": bool(candidate.get("eid")),
        "source_title": bool(candidate.get("source_title")),
        "authors": bool(candidate.get("authors")),
    }
    present = [key for key, value in checks.items() if value]
    missing = [key for key, value in checks.items() if not value]
    return {"present": present, "missing": missing, "score": len(present), "possible": len(checks)}


def _rq_links_for_candidate(candidate: dict[str, Any], rq_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidate_terms = _text_terms(" ".join(str(candidate.get(key) or "") for key in ("title", "source_title")))
    links = []
    for rq in rq_records:
        overlap = sorted(candidate_terms.intersection(rq.get("terms") or set()))
        if overlap:
            links.append({"rq_id": rq["id"], "status": rq.get("status"), "matched_terms": overlap})
    return links


def write_high_signal_candidate_report(workspace: Path, *, limit: int = 50) -> dict[str, Any]:
    register = read_yaml(external_candidate_register_path(workspace)) if external_candidate_register_path(workspace).exists() else {"candidates": []}
    rq_records = _research_question_records(workspace)
    rows = []
    for candidate in register.get("candidates", []):
        if not isinstance(candidate, dict):
            continue
        rq_links = _rq_links_for_candidate(candidate, rq_records)
        completeness = _candidate_metadata_completeness(candidate)
        rows.append(
            {
                "candidate_id": candidate.get("candidate_id"),
                "title": candidate.get("title"),
                "year": candidate.get("year"),
                "citation_count": int(candidate.get("citation_count") or 0),
                "quality_score": int(candidate.get("quality_score") or 0),
                "open_access": bool(candidate.get("open_access")),
                "metadata_completeness": completeness,
                "rq_coverage_count": len(rq_links),
                "linked_research_questions": rq_links,
                "doi": candidate.get("doi"),
                "eid": candidate.get("eid"),
                "authors": candidate.get("authors") or [],
                "source_title": candidate.get("source_title"),
                "document_type": candidate.get("document_type"),
                "queries": candidate.get("queries") or [],
            }
        )
    rows.sort(
        key=lambda item: (
            -int(item["quality_score"]),
            -int(item["rq_coverage_count"]),
            -int(item["citation_count"]),
            -int(item.get("year") or 0),
            not bool(item["open_access"]),
            -int(item["metadata_completeness"]["score"]),
            str(item.get("title") or ""),
        )
    )
    report = {
        "version": 1,
        "candidate_count": len(rows),
        "reported_count": min(len(rows), max(0, limit)),
        "sort_order": [
            "quality_score_desc",
            "rq_coverage_count_desc",
            "citation_count_desc",
            "year_desc",
            "open_access_true_first",
            "metadata_completeness_desc",
        ],
        "candidates": rows[: max(0, limit)],
        "references": {
            "accepted_workspace_evidence": [],
            "external_candidate_sources": [
                {
                    "candidate_id": candidate.get("candidate_id"),
                    "reference": apa7_reference(
                        {
                            "authors": candidate.get("authors") or [],
                            "year": candidate.get("year"),
                            "title": candidate.get("title"),
                            "source_title": candidate.get("source_title"),
                            "doi": candidate.get("doi"),
                        }
                    ),
                }
                for candidate in rows[: max(0, limit)]
            ],
        },
    }
    write_yaml(high_signal_candidate_report_path(workspace), report)
    return report


def _source_metadata_for_matching(source: dict[str, Any]) -> dict[str, Any]:
    metadata = source.get("citation_metadata") if isinstance(source.get("citation_metadata"), dict) else {}
    return {
        "source_id": source.get("source_id"),
        "title": metadata.get("title") or source.get("zotero_title"),
        "year": metadata.get("year") or source.get("zotero_year"),
        "doi": metadata.get("doi") or source.get("zotero_doi"),
        "eid": source.get("eid") or metadata.get("eid"),
        "provider": source.get("provider"),
        "status": source.get("status"),
    }


def external_candidate_deduplication_report(workspace: Path) -> dict[str, Any]:
    register = read_yaml(external_candidate_register_path(workspace)) if external_candidate_register_path(workspace).exists() else {"candidates": []}
    candidates = [candidate for candidate in register.get("candidates", []) if isinstance(candidate, dict)]
    source_register = read_yaml(workspace / "source-register.yaml") if (workspace / "source-register.yaml").exists() else {"sources": []}
    sources = [_source_metadata_for_matching(source) for source in source_register.get("sources", []) if isinstance(source, dict)]

    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for candidate in candidates:
        keys = []
        doi = _normalize_doi(candidate.get("doi"))
        if doi:
            keys.append(("doi", doi))
        if candidate.get("eid"):
            keys.append(("eid", str(candidate["eid"]).lower()))
        title = _normalize_title(candidate.get("title"))
        if title and candidate.get("year"):
            keys.append(("title_year", f"{title}::{candidate.get('year')}"))
        for key in keys:
            groups.setdefault(key, []).append(candidate)

    duplicate_groups = []
    for (key_type, key_value), items in sorted(groups.items()):
        ids = sorted({str(item.get("candidate_id")) for item in items if item.get("candidate_id")})
        if len(ids) > 1:
            duplicate_groups.append({"match_type": key_type, "match_key": key_value, "candidate_ids": ids})

    source_matches = []
    for candidate in candidates:
        candidate_doi = _normalize_doi(candidate.get("doi"))
        candidate_title = _normalize_title(candidate.get("title"))
        candidate_year = str(candidate.get("year") or "")
        matches = []
        for source in sources:
            source_doi = _normalize_doi(source.get("doi"))
            source_title = _normalize_title(source.get("title"))
            source_year = str(source.get("year") or "")
            match_types = []
            if candidate_doi and source_doi and candidate_doi == source_doi:
                match_types.append("doi")
            if candidate.get("eid") and source.get("eid") and str(candidate.get("eid")).lower() == str(source.get("eid")).lower():
                match_types.append("eid")
            if candidate_title and source_title and candidate_year and source_year and candidate_title == source_title and candidate_year == source_year:
                match_types.append("title_year")
            if match_types:
                matches.append(
                    {
                        "source_id": source.get("source_id"),
                        "status": source.get("status"),
                        "provider": source.get("provider"),
                        "match_types": match_types,
                    }
                )
        if matches:
            source_matches.append({"candidate_id": candidate.get("candidate_id"), "matches": matches})

    report = {
        "version": 1,
        "candidate_count": len(candidates),
        "duplicate_group_count": len(duplicate_groups),
        "source_match_count": len(source_matches),
        "duplicate_groups": duplicate_groups,
        "source_matches": source_matches,
        "matching_fields": ["doi", "eid", "title_year"],
        "notes": "Source matches include local source-register metadata, including Zotero-derived fields when present.",
    }
    write_yaml(external_candidate_duplicates_path(workspace), report)
    return report


def external_search_evidence_validation_report(workspace: Path) -> dict[str, Any]:
    register = read_yaml(external_candidate_register_path(workspace)) if external_candidate_register_path(workspace).exists() else {"candidates": []}
    candidates = [candidate for candidate in register.get("candidates", []) if isinstance(candidate, dict)]
    approved_rqs = [rq for rq in _research_question_records(workspace) if rq.get("status") != "candidate"]
    claims_doc = read_yaml(workspace / "claims-ledger.yaml") if (workspace / "claims-ledger.yaml").exists() else {"claims": []}
    claims = [claim for claim in claims_doc.get("claims", []) if isinstance(claim, dict)]
    novelty_doc = read_yaml(workspace / "novelty-ledger.yaml") if (workspace / "novelty-ledger.yaml").exists() else {"assessments": []}
    novelty_terms = _text_terms(json.dumps(novelty_doc, sort_keys=True))
    accepted_source_ids = set(read_yaml(workspace / "accepted-sources.yaml").get("source_ids", [])) if (workspace / "accepted-sources.yaml").exists() else set()
    source_register = read_yaml(workspace / "source-register.yaml") if (workspace / "source-register.yaml").exists() else {"sources": []}
    accepted_sources = [source for source in source_register.get("sources", []) if isinstance(source, dict) and source.get("source_id") in accepted_source_ids]
    accepted_terms = _text_terms(json.dumps(accepted_sources, sort_keys=True))

    rows = []
    for candidate in candidates:
        candidate_terms = _text_terms(" ".join(str(candidate.get(key) or "") for key in ("title", "source_title")))
        rq_matches = []
        for rq in approved_rqs:
            overlap = sorted(candidate_terms.intersection(rq.get("terms") or set()))
            if overlap:
                rq_matches.append({"rq_id": rq["id"], "matched_terms": overlap})
        claim_matches = []
        for claim in claims:
            overlap = sorted(candidate_terms.intersection(_text_terms(claim.get("text"))))
            if overlap:
                claim_matches.append({"claim_id": claim.get("id"), "matched_terms": overlap})
        source_gap_terms = sorted(candidate_terms.difference(accepted_terms))[:10]
        rows.append(
            {
                "candidate_id": candidate.get("candidate_id"),
                "title": candidate.get("title"),
                "quality_score": candidate.get("quality_score"),
                "rq_matches": rq_matches,
                "claim_matches": claim_matches,
                "novelty_term_matches": sorted(candidate_terms.intersection(novelty_terms))[:10],
                "source_gap_terms": source_gap_terms,
                "needs_review": not rq_matches or bool(source_gap_terms),
            }
        )
    report = {
        "version": 1,
        "candidate_count": len(rows),
        "approved_research_question_count": len(approved_rqs),
        "claim_count": len(claims),
        "accepted_source_count": len(accepted_sources),
        "candidates": rows,
        "human_review_required": True,
    }
    write_yaml(external_evidence_validation_path(workspace), report)
    return report


def external_search_run_comparison_report(workspace: Path) -> dict[str, Any]:
    register = read_yaml(external_candidate_register_path(workspace)) if external_candidate_register_path(workspace).exists() else {"runs": []}
    summary = read_yaml(batch_search_summary_path(workspace)) if batch_search_summary_path(workspace).exists() else {"runs": []}
    plan_path = workspace / "outputs" / "recommendations" / "external-search-query-plan.yaml"
    plan = read_yaml(plan_path) if plan_path.exists() else {"query_records": []}
    records_by_query = {
        query_history_key(str(record.get("query") or "")): record
        for record in plan.get("query_records", [])
        if isinstance(record, dict)
    }
    summary_by_query = {
        query_history_key(str(run.get("query") or "")): run
        for run in summary.get("runs", [])
        if isinstance(run, dict)
    }
    rows = []
    aggregates: dict[str, dict[str, Any]] = {}
    for run in register.get("runs", []):
        if not isinstance(run, dict):
            continue
        key = query_history_key(str(run.get("query") or ""))
        plan_record = records_by_query.get(key, {})
        summary_run = summary_by_query.get(key, {})
        strategy = str(plan_record.get("strategy") or "unknown")
        processed = int(summary_run.get("processed_count") or 0)
        candidates = int(run.get("candidate_count") or 0)
        filtered = int(summary_run.get("filtered_count") or run.get("skipped_count") or 0)
        row = {
            "query": run.get("query"),
            "strategy": strategy,
            "group_label": plan_record.get("group_label"),
            "processed_count": processed,
            "candidate_count": candidates,
            "filtered_count": filtered,
            "no_results": bool(run.get("no_results")),
            "low_results": bool(run.get("low_results")),
            "yield_rate": round(candidates / processed, 3) if processed else 0,
            "snapshot_path": run.get("snapshot_path"),
        }
        rows.append(row)
        bucket = aggregates.setdefault(
            strategy,
            {"strategy": strategy, "run_count": 0, "processed_count": 0, "candidate_count": 0, "filtered_count": 0},
        )
        bucket["run_count"] += 1
        bucket["processed_count"] += processed
        bucket["candidate_count"] += candidates
        bucket["filtered_count"] += filtered
    strategy_rows = []
    for bucket in aggregates.values():
        processed = int(bucket["processed_count"])
        candidates = int(bucket["candidate_count"])
        strategy_rows.append({**bucket, "yield_rate": round(candidates / processed, 3) if processed else 0})
    strategy_rows.sort(key=lambda item: (-int(item["candidate_count"]), -float(item["yield_rate"]), str(item["strategy"])))
    rows.sort(key=lambda item: (-int(item["candidate_count"]), -float(item["yield_rate"]), str(item.get("query") or "")))
    report = {"version": 1, "strategies": strategy_rows, "runs": rows}
    write_yaml(external_run_comparison_path(workspace), report)
    return report


def _issue_queries_from_logs(workspace: Path) -> list[dict[str, Any]]:
    records = []
    for path, issue in (
        (workspace / "outputs" / "external-search" / "scopus-no-results.yaml", "no_results"),
        (workspace / "outputs" / "external-search" / "scopus-low-results.yaml", "low_results"),
    ):
        if not path.exists():
            continue
        data = read_yaml(path)
        for item in data.get("queries", []):
            if isinstance(item, dict) and item.get("query"):
                records.append({"query": normalize_query_line(str(item["query"])), "issue": issue, "source_path": str(path)})
    if batch_search_summary_path(workspace).exists():
        summary = read_yaml(batch_search_summary_path(workspace))
        for run in summary.get("runs", []):
            if not isinstance(run, dict) or not run.get("query"):
                continue
            if int(run.get("no_result_count") or 0):
                records.append({"query": normalize_query_line(str(run["query"])), "issue": "no_results", "source_path": str(batch_search_summary_path(workspace))})
            elif int(run.get("low_result_count") or 0):
                records.append({"query": normalize_query_line(str(run["query"])), "issue": "low_results", "source_path": str(batch_search_summary_path(workspace))})
    out = []
    seen = set()
    for record in records:
        key = (record["query"].lower(), record["issue"])
        if key not in seen:
            seen.add(key)
            out.append(record)
    return out


def _broadened_query_candidates(query: str) -> list[str]:
    quoted = [term.strip() for term in re.findall(r'"([^"]+)"', query) if term.strip()]
    candidates = []
    if len(quoted) >= 2:
        for index in range(len(quoted)):
            remaining = [term for pos, term in enumerate(quoted) if pos != index]
            candidates.append(" AND ".join(_quote(term) for term in remaining))
    if " AND " in query.upper() and not candidates:
        parts = [part.strip(" ()") for part in re.split(r"\s+AND\s+", query, flags=re.IGNORECASE) if part.strip(" ()")]
        if len(parts) >= 2:
            for index in range(len(parts)):
                candidates.append(" AND ".join(part for pos, part in enumerate(parts) if pos != index))
    return [candidate for candidate in _dedupe(candidates) if query_history_key(candidate) != query_history_key(query)]


def generate_auto_refine_plan(
    workspace: Path,
    *,
    budgets: SearchBudgets | None = None,
    max_queries: int = 20,
    max_refinement_rounds: int = 1,
    max_results_per_query: int = 25,
) -> dict[str, Any]:
    start = time.monotonic()
    budgets = budgets or SearchBudgets.from_options(
        max_generated_queries=max_queries,
        max_refinement_rounds=max_refinement_rounds,
        max_result_count=max_queries * max_results_per_query,
        max_result_pages=max_queries,
    )
    configured_query_limit = max(0, max_queries)
    result_count_limit = budgets.max_result_count // max(1, max_results_per_query)
    allowed_queries = min(configured_query_limit, budgets.max_generated_queries, budgets.max_result_pages, result_count_limit)
    allowed_rounds = min(max(0, max_refinement_rounds), budgets.max_refinement_rounds)
    issue_queries = _issue_queries_from_logs(workspace)
    query_records = []
    seen = set()
    for issue in issue_queries:
        if len(query_records) >= allowed_queries or allowed_rounds <= 0:
            break
        for candidate in _broadened_query_candidates(issue["query"]):
            if len(query_records) >= allowed_queries:
                break
            key = query_history_key(candidate)
            if key in seen:
                continue
            seen.add(key)
            query_records.append(
                {
                    "query": candidate,
                    "source_query": issue["query"],
                    "source_issue": issue["issue"],
                    "source_path": issue["source_path"],
                    "strategy": "deterministic_auto_refine",
                    "refinement_round": 1,
                    "external_search_performed": False,
                }
            )
    elapsed = time.monotonic() - start
    used = {
        "api_calls": 0,
        "generated_queries": len(query_records),
        "refinement_rounds": 1 if query_records else 0,
        "result_pages": len(query_records),
        "result_count": len(query_records) * max(1, max_results_per_query),
    }
    budget_status = budget_status_report(budgets, used, elapsed)
    exhaustion_reasons = list(budget_status["exhaustion_reasons"])
    if issue_queries and len(query_records) >= allowed_queries:
        exhaustion_reasons.append("query_budget_reached")
    if issue_queries and allowed_rounds <= 0:
        exhaustion_reasons.append("refinement_round_budget_reached")
    if exhaustion_reasons:
        budget_status = {**budget_status, "exhausted": True, "within_budget": False, "exhaustion_reasons": _dedupe(exhaustion_reasons)}
    plan = {
        "version": 1,
        "source": "no_result_and_low_result_logs",
        "external_search_performed": False,
        "approval_required": True,
        "issue_query_count": len(issue_queries),
        "query_count": len(query_records),
        "max_results_per_query": max(1, max_results_per_query),
        "budget_status": budget_status,
        "queries": [record["query"] for record in query_records],
        "query_records": query_records,
    }
    write_yaml(auto_refine_plan_path(workspace), plan)
    return plan


def scopus_get(
    credentials: ScopusCredentials,
    params: dict[str, Any],
    *,
    opener: Callable[[Request], Any] | None = None,
) -> Any:
    query_string = urlencode(params)
    request = Request(
        f"{SCOPUS_SEARCH_URL}?{query_string}",
        headers={
            "X-ELS-APIKey": credentials.api_key,
            "Accept": "application/json",
            **({"X-ELS-Insttoken": credentials.inst_token} if credentials.inst_token else {}),
        },
        method="GET",
    )
    fetch = opener or urlopen
    try:
        with fetch(request) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise ExternalSearchError(f"Scopus request failed with HTTP {exc.code}") from exc
    except URLError as exc:
        raise ExternalSearchError(f"Scopus request failed: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise ExternalSearchError("Scopus returned invalid JSON") from exc


def scopus_readiness(credentials: ScopusCredentials, *, opener: Callable[[Request], Any] | None = None) -> dict[str, Any]:
    data = scopus_get(credentials, {"query": "TITLE-ABS-KEY(research)", "count": 1, "view": "STANDARD"}, opener=opener)
    results = data.get("search-results") if isinstance(data, dict) else {}
    return {
        "version": 1,
        "provider": "scopus",
        "key_loaded": bool(credentials.api_key),
        "inst_token_loaded": bool(credentials.inst_token),
        "key_exposed": False,
        "api_reachable": True,
        "opensearch_total_results": results.get("opensearch:totalResults"),
    }


def scopus_search(
    workspace: Path,
    credentials: ScopusCredentials,
    *,
    query: str,
    count: int = 25,
    thresholds: SearchThresholds | None = None,
    budgets: SearchBudgets | None = None,
    opener: Callable[[Request], Any] | None = None,
) -> dict[str, Any]:
    start = time.monotonic()
    normalized_query = normalize_query_line(query)
    thresholds = thresholds or SearchThresholds.from_options(max_results_per_query=count)
    budgets = budgets or SearchBudgets.from_options(max_result_count=thresholds.max_results_per_query)
    _ensure_scopus_budget_available(budgets, thresholds)
    data = scopus_get(
        credentials,
        {"query": normalized_query, "count": thresholds.max_results_per_query, "view": "STANDARD"},
        opener=opener,
    )
    output_dir = workspace / "outputs" / "external-search"
    output_dir.mkdir(parents=True, exist_ok=True)
    snapshot_digest = hashlib.sha256(f"{normalized_query}|{datetime.now(timezone.utc).isoformat()}".encode("utf-8")).hexdigest()[:16]
    snapshot_path = output_dir / f"scopus-response-{snapshot_digest}.json"
    snapshot_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    results = data.get("search-results") if isinstance(data, dict) else {}
    entries = results.get("entry") if isinstance(results, dict) else []
    entries = entries if isinstance(entries, list) else []
    accepted_candidates, skipped_candidates = score_scopus_entries(entries, thresholds)
    validation = query_validation_report(
        query=normalized_query,
        entries=entries,
        accepted_candidates=accepted_candidates,
        skipped_candidates=skipped_candidates,
        thresholds=thresholds,
    )
    filtered_log = update_filtered_candidate_log(
        workspace,
        provider="scopus",
        query=normalized_query,
        skipped_candidates=skipped_candidates,
        entries=entries,
        thresholds=thresholds,
        snapshot_path=str(snapshot_path),
    )
    write_yaml(query_validation_path(workspace), {"version": 1, "provider": "scopus", "validation": validation})
    register = update_external_candidate_register(
        workspace,
        provider="scopus",
        query=normalized_query,
        candidates=accepted_candidates,
        skipped_candidates=skipped_candidates,
        validation=validation,
        snapshot_path=str(snapshot_path),
    )
    elapsed = time.monotonic() - start
    budget_status = budget_status_report(
        budgets,
        {
            "api_calls": 1,
            "generated_queries": 0,
            "refinement_rounds": 0,
            "result_pages": 1,
            "result_count": len(entries),
        },
        elapsed,
    )
    metrics = {
        "query": normalized_query,
        "processed": len(entries),
        "candidate_count": len(accepted_candidates),
        "filtered_count": len(skipped_candidates),
        "skipped_count": validation["skipped_results"],
        "duplicate_count": validation["duplicate_count"],
        "no_results": validation["no_results"],
        "low_results": validation["low_results"],
        "snapshot_path": str(snapshot_path),
        "candidate_register_path": str(external_candidate_register_path(workspace)),
        "query_validation_path": str(query_validation_path(workspace)),
        "filtered_candidate_log_path": str(filtered_candidate_log_path(workspace)),
        "budget_status": budget_status,
    }
    summary = update_batch_search_run_summary(workspace, provider="scopus", metrics=metrics, validation=validation)
    metrics["batch_summary_path"] = str(batch_search_summary_path(workspace))
    if metrics["no_results"]:
        no_results_path = output_dir / "scopus-no-results.yaml"
        current = read_yaml(no_results_path) if no_results_path.exists() else {"version": 1, "queries": []}
        current.setdefault("queries", []).append(
            {
                "query": normalized_query,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "refinement_suggestions": validation["refinement_suggestions"],
            }
        )
        write_yaml(no_results_path, current)
    if metrics["low_results"] and not metrics["no_results"]:
        low_results_path = output_dir / "scopus-low-results.yaml"
        current = read_yaml(low_results_path) if low_results_path.exists() else {"version": 1, "queries": []}
        current.setdefault("queries", []).append(
            {
                "query": normalized_query,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "processed": metrics["processed"],
                "refinement_suggestions": validation["refinement_suggestions"],
            }
        )
        write_yaml(low_results_path, current)
    record_queries_used(workspace, [normalized_query], [metrics])
    high_signal = write_high_signal_candidate_report(workspace)
    duplicates = external_candidate_deduplication_report(workspace)
    evidence_validation = external_search_evidence_validation_report(workspace)
    run_comparison = external_search_run_comparison_report(workspace)
    metrics["high_signal_report_path"] = str(high_signal_candidate_report_path(workspace))
    metrics["candidate_duplicates_path"] = str(external_candidate_duplicates_path(workspace))
    metrics["evidence_validation_path"] = str(external_evidence_validation_path(workspace))
    metrics["run_comparison_path"] = str(external_run_comparison_path(workspace))
    return {
        "version": 1,
        "provider": "scopus",
        "metrics": metrics,
        "snapshot_path": str(snapshot_path),
        "validation": validation,
        "batch_summary": summary,
        "filtered_candidate_log": filtered_log,
        "high_signal_report": high_signal,
        "candidate_duplicates": duplicates,
        "evidence_validation": evidence_validation,
        "run_comparison": run_comparison,
        "candidate_count_total": len(register.get("candidates", [])),
    }
