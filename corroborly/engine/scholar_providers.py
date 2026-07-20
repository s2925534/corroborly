"""Academic-search data provider layer with a sequential fallback pipeline.

`ScholarDataService.search()` tries a sequence of backends in order and
returns the first one that completes without raising:

  1. SerpApi's Google Scholar engine (structured JSON, needs SERPAPI_API_KEY)
  2. Semantic Scholar's official Graph API (free, works without a key)
  3. the open-source `scholarly` package (optional dependency, scrapes
     Google Scholar directly and can be IP-blocked/rate-limited)
  4. ScholarAPI (scholarapi.net) -- currently a stub, see
     `_fetch_scholarapi_net` for why
  5. OpenAlex's Works API (free, no key required)
  6. Crossref's Works API (free, no key required, strong DOI metadata)
  7. arXiv's Atom-feed API (free, no key required, preprints)

Options 5-7 are keyless, unrestricted, and highly available, so they act as
the last-resort fallback tier: if every paid/scraped/stubbed option above
fails or lacks credentials, the pipeline still returns real results instead
of an empty response.

This module is intentionally self-contained: it does not import from, or
get imported by, `corroborly.engine.external_search` (the existing
Scopus-based provider, which has its own heavier candidate-register
pipeline) or any CLI/router code beyond the `search scholar` CLI command,
so it cannot regress Scopus's separate behavior.
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from xml.etree import ElementTree

from corroborly.engine.ai import load_dotenv_values

logger = logging.getLogger(__name__)

SERPAPI_URL = "https://serpapi.com/search"
SEMANTIC_SCHOLAR_SEARCH_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
SEMANTIC_SCHOLAR_FIELDS = "title,authors,year,citationCount,abstract,venue,url"
OPENALEX_WORKS_URL = "https://api.openalex.org/works"
CROSSREF_WORKS_URL = "https://api.crossref.org/works"
ARXIV_API_URL = "http://export.arxiv.org/api/query"
ARXIV_ATOM_NS = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}

Opener = Callable[[Request], Any]


class ScholarProviderError(RuntimeError):
    """Raised by a single provider when it cannot serve a request.

    `ScholarDataService.search()` catches this (and only this, plus a
    belt-and-braces catch-all for genuinely unexpected errors) and moves on
    to the next provider in the pipeline.
    """


@dataclass(frozen=True)
class ScholarResult:
    title: str
    authors: list[str]
    year: int | None
    citation_count: int | None
    url: str | None
    abstract: str | None
    venue: str | None
    source_provider: str
    doi: str | None = None


@dataclass(frozen=True)
class ProviderAttempt:
    provider: str
    status: str  # "ok" | "error"
    detail: str


@dataclass(frozen=True)
class ScholarSearchResponse:
    query: str
    provider_used: str | None
    results: list[ScholarResult]
    attempts: list[ProviderAttempt]

    @property
    def succeeded(self) -> bool:
        return self.provider_used is not None

    def as_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "succeeded": self.succeeded,
            "result_count": len(self.results),
        }


def _env_value(key: str, *, workspace: Path | None) -> str:
    env_values = load_dotenv_values(Path.cwd() / ".env")
    if workspace is not None:
        env_values = {**env_values, **load_dotenv_values(workspace / ".env")}
    return os.environ.get(key) or env_values.get(key) or ""


def _extract_year(text: Any) -> int | None:
    match = re.search(r"\b(19|20)\d{2}\b", str(text or ""))
    return int(match.group(0)) if match else None


def _safe_int_or_none(value: Any) -> int | None:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _http_get_json(request: Request, *, opener: Opener | None, provider_label: str) -> Any:
    fetch = opener or urlopen
    try:
        with fetch(request) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise ScholarProviderError(f"{provider_label} request failed with HTTP {exc.code}") from exc
    except URLError as exc:
        raise ScholarProviderError(f"{provider_label} request failed: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise ScholarProviderError(f"{provider_label} returned invalid JSON") from exc


# --------------------------------------------------------------------------
# Option 1: SerpApi (Google Scholar engine)
# --------------------------------------------------------------------------


def _fetch_serpapi(
    query: str,
    max_results: int,
    *,
    workspace: Path | None,
    opener: Opener | None,
) -> list[ScholarResult]:
    api_key = _env_value("SERPAPI_API_KEY", workspace=workspace)
    if not api_key:
        raise ScholarProviderError("Missing SERPAPI_API_KEY")

    params = {"engine": "google_scholar", "q": query, "api_key": api_key, "num": max_results}
    request = Request(f"{SERPAPI_URL}?{urlencode(params)}", headers={"Accept": "application/json"}, method="GET")
    data = _http_get_json(request, opener=opener, provider_label="SerpApi")

    if isinstance(data, dict) and data.get("error"):
        raise ScholarProviderError(f"SerpApi error: {data['error']}")

    organic = data.get("organic_results") if isinstance(data, dict) else None
    organic = organic if isinstance(organic, list) else []

    results = []
    for entry in organic[:max_results]:
        if not isinstance(entry, dict):
            continue
        publication_info = entry.get("publication_info") if isinstance(entry.get("publication_info"), dict) else {}
        authors_list = publication_info.get("authors") if isinstance(publication_info.get("authors"), list) else []
        inline_links = entry.get("inline_links") if isinstance(entry.get("inline_links"), dict) else {}
        cited_by = inline_links.get("cited_by") if isinstance(inline_links.get("cited_by"), dict) else {}
        results.append(
            ScholarResult(
                title=str(entry.get("title") or "Untitled"),
                authors=[str(author["name"]) for author in authors_list if isinstance(author, dict) and author.get("name")],
                year=_extract_year(publication_info.get("summary")),
                citation_count=_safe_int_or_none(cited_by.get("total")),
                url=entry.get("link"),
                abstract=entry.get("snippet"),
                venue=None,
                source_provider="serpapi",
            )
        )
    return results


# --------------------------------------------------------------------------
# Option 2: Semantic Scholar API (free, official, no key required)
# --------------------------------------------------------------------------


def _fetch_semantic_scholar(
    query: str,
    max_results: int,
    *,
    workspace: Path | None,
    opener: Opener | None,
) -> list[ScholarResult]:
    params = {"query": query, "limit": max_results, "fields": SEMANTIC_SCHOLAR_FIELDS}
    headers = {"Accept": "application/json"}
    api_key = _env_value("SEMANTIC_SCHOLAR_API_KEY", workspace=workspace)
    if api_key:
        headers["x-api-key"] = api_key

    request = Request(f"{SEMANTIC_SCHOLAR_SEARCH_URL}?{urlencode(params)}", headers=headers, method="GET")
    data = _http_get_json(request, opener=opener, provider_label="Semantic Scholar")

    papers = data.get("data") if isinstance(data, dict) else None
    papers = papers if isinstance(papers, list) else []

    results = []
    for entry in papers[:max_results]:
        if not isinstance(entry, dict):
            continue
        authors_list = entry.get("authors") if isinstance(entry.get("authors"), list) else []
        results.append(
            ScholarResult(
                title=str(entry.get("title") or "Untitled"),
                authors=[str(author["name"]) for author in authors_list if isinstance(author, dict) and author.get("name")],
                year=_safe_int_or_none(entry.get("year")),
                citation_count=_safe_int_or_none(entry.get("citationCount")),
                url=entry.get("url"),
                abstract=entry.get("abstract"),
                venue=entry.get("venue") or None,
                source_provider="semantic_scholar",
            )
        )
    return results


# --------------------------------------------------------------------------
# Option 3: `scholarly` library (open-source Google Scholar scraper)
# --------------------------------------------------------------------------


def _split_author_field(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if item]
    if isinstance(value, str) and value.strip():
        return [part.strip() for part in re.split(r",| and ", value) if part.strip()]
    return []


def _fetch_scholarly(
    query: str,
    max_results: int,
    *,
    workspace: Path | None,
    opener: Opener | None,
) -> list[ScholarResult]:
    try:
        from scholarly import scholarly  # type: ignore[import-not-found]
    except ImportError as exc:
        raise ScholarProviderError(
            "The optional 'scholarly' package is not installed. Install with: pip install 'corroborly[scholar]'"
        ) from exc

    try:
        search_iterator = scholarly.search_pubs(query)
        results = []
        for _ in range(max_results):
            try:
                entry = next(search_iterator)
            except StopIteration:
                break
            if not isinstance(entry, dict):
                continue
            bib = entry.get("bib") if isinstance(entry.get("bib"), dict) else {}
            results.append(
                ScholarResult(
                    title=str(bib.get("title") or "Untitled"),
                    authors=_split_author_field(bib.get("author")),
                    year=_safe_int_or_none(bib.get("pub_year")),
                    citation_count=_safe_int_or_none(entry.get("num_citations")),
                    url=entry.get("pub_url") or entry.get("eprint_url"),
                    abstract=bib.get("abstract"),
                    venue=bib.get("venue") or bib.get("journal"),
                    source_provider="scholarly",
                )
            )
        return results
    except ScholarProviderError:
        raise
    except Exception as exc:
        # scholarly raises a mix of its own exceptions and requests/urllib
        # errors for rate limits and IP blocks; normalize all of them so the
        # pipeline can fall through uniformly.
        raise ScholarProviderError(f"scholarly library search failed: {exc}") from exc


# --------------------------------------------------------------------------
# Option 4: ScholarAPI (scholarapi.net) -- STUB, not implemented
# --------------------------------------------------------------------------


def _fetch_scholarapi_net(
    query: str,
    max_results: int,
    *,
    workspace: Path | None,
    opener: Opener | None,
) -> list[ScholarResult]:
    """Placeholder for the ScholarAPI (scholarapi.net) gateway.

    Not implemented: I could not verify this service's endpoint URL,
    authentication scheme, or response schema against documentation I can
    confirm is accurate. Guessing at a request/response contract here would
    silently produce wrong data instead of an honest failure, so this stub
    always raises `ScholarProviderError` -- the pipeline logs it and falls
    through cleanly, same as a real outage would.

    To finish this option: confirm the real base URL and auth header from
    an actual account/API docs, then mirror `_fetch_serpapi` /
    `_fetch_semantic_scholar` above (build a `Request`, call
    `_http_get_json(..., opener=opener, ...)` so tests can inject a fake
    opener, and map the response into `ScholarResult`).
    """
    api_key = _env_value("SCHOLARAPI_NET_API_KEY", workspace=workspace)
    if not api_key:
        raise ScholarProviderError("Missing SCHOLARAPI_NET_API_KEY (also: this provider is a stub, see docstring)")
    raise ScholarProviderError("ScholarAPI (scholarapi.net) provider is a stub; endpoint/response contract not yet implemented")


# --------------------------------------------------------------------------
# Option 5: OpenAlex Works API (free, no key required)
# --------------------------------------------------------------------------


def _reconstruct_openalex_abstract(inverted_index: Any) -> str | None:
    """OpenAlex ships abstracts as {word: [position, ...]} instead of plain
    text (a licensing workaround). Rebuild the original word order from it."""
    if not isinstance(inverted_index, dict) or not inverted_index:
        return None
    positions: dict[int, str] = {}
    for word, idxs in inverted_index.items():
        if not isinstance(idxs, list):
            continue
        for idx in idxs:
            if isinstance(idx, int):
                positions[idx] = str(word)
    if not positions:
        return None
    return " ".join(positions[i] for i in sorted(positions))


def _fetch_openalex(
    query: str,
    max_results: int,
    *,
    workspace: Path | None,
    opener: Opener | None,
) -> list[ScholarResult]:
    params: dict[str, Any] = {"search": query, "per_page": max_results}
    mailto = _env_value("OPENALEX_MAILTO", workspace=workspace)
    if mailto:
        params["mailto"] = mailto

    request = Request(f"{OPENALEX_WORKS_URL}?{urlencode(params)}", headers={"Accept": "application/json"}, method="GET")
    data = _http_get_json(request, opener=opener, provider_label="OpenAlex")

    entries = data.get("results") if isinstance(data, dict) else None
    entries = entries if isinstance(entries, list) else []

    results = []
    for entry in entries[:max_results]:
        if not isinstance(entry, dict):
            continue
        authorships = entry.get("authorships") if isinstance(entry.get("authorships"), list) else []
        authors = []
        for authorship in authorships:
            if not isinstance(authorship, dict):
                continue
            author = authorship.get("author") if isinstance(authorship.get("author"), dict) else {}
            if author.get("display_name"):
                authors.append(str(author["display_name"]))
        primary_location = entry.get("primary_location") if isinstance(entry.get("primary_location"), dict) else {}
        source = primary_location.get("source") if isinstance(primary_location.get("source"), dict) else {}
        doi = entry.get("doi")
        results.append(
            ScholarResult(
                title=str(entry.get("title") or entry.get("display_name") or "Untitled"),
                authors=authors,
                year=_safe_int_or_none(entry.get("publication_year")),
                citation_count=_safe_int_or_none(entry.get("cited_by_count")),
                url=primary_location.get("landing_page_url") or entry.get("id"),
                abstract=_reconstruct_openalex_abstract(entry.get("abstract_inverted_index")),
                venue=source.get("display_name") or None,
                source_provider="openalex",
                doi=str(doi) if doi else None,
            )
        )
    return results


# --------------------------------------------------------------------------
# Option 6: Crossref Works API (free, no key required, strong DOI metadata)
# --------------------------------------------------------------------------

_JATS_TAG_RE = re.compile(r"<[^>]+>")


def _fetch_crossref(
    query: str,
    max_results: int,
    *,
    workspace: Path | None,
    opener: Opener | None,
) -> list[ScholarResult]:
    params: dict[str, Any] = {"query": query, "rows": max_results}
    mailto = _env_value("CROSSREF_MAILTO", workspace=workspace)
    if mailto:
        params["mailto"] = mailto

    request = Request(f"{CROSSREF_WORKS_URL}?{urlencode(params)}", headers={"Accept": "application/json"}, method="GET")
    data = _http_get_json(request, opener=opener, provider_label="Crossref")

    message = data.get("message") if isinstance(data, dict) else None
    items = message.get("items") if isinstance(message, dict) else None
    items = items if isinstance(items, list) else []

    results = []
    for item in items[:max_results]:
        if not isinstance(item, dict):
            continue
        titles = item.get("title") if isinstance(item.get("title"), list) else []
        author_entries = item.get("author") if isinstance(item.get("author"), list) else []
        authors = [
            " ".join(part for part in (author.get("given"), author.get("family")) if part)
            for author in author_entries
            if isinstance(author, dict) and (author.get("given") or author.get("family"))
        ]
        year = None
        for date_key in ("published", "published-print", "published-online", "issued"):
            date_field = item.get(date_key) if isinstance(item.get(date_key), dict) else {}
            date_parts_list = date_field.get("date-parts") if isinstance(date_field.get("date-parts"), list) else []
            first_parts = date_parts_list[0] if date_parts_list else []
            if first_parts:
                year = _safe_int_or_none(first_parts[0])
                break
        container_titles = item.get("container-title") if isinstance(item.get("container-title"), list) else []
        abstract = item.get("abstract")
        if isinstance(abstract, str) and abstract.strip():
            abstract = _JATS_TAG_RE.sub("", abstract).strip()
        else:
            abstract = None
        results.append(
            ScholarResult(
                title=str(titles[0]) if titles else "Untitled",
                authors=authors,
                year=year,
                citation_count=_safe_int_or_none(item.get("is-referenced-by-count")),
                url=item.get("URL"),
                abstract=abstract,
                venue=str(container_titles[0]) if container_titles else None,
                source_provider="crossref",
                doi=str(item["DOI"]) if item.get("DOI") else None,
            )
        )
    return results


# --------------------------------------------------------------------------
# Option 7: arXiv API (free, no key required, preprints, Atom/XML response)
# --------------------------------------------------------------------------


def _fetch_arxiv(
    query: str,
    max_results: int,
    *,
    workspace: Path | None,
    opener: Opener | None,
) -> list[ScholarResult]:
    params = {"search_query": f"all:{query}", "max_results": max_results}
    request = Request(f"{ARXIV_API_URL}?{urlencode(params)}", headers={"Accept": "application/atom+xml"}, method="GET")

    fetch = opener or urlopen
    try:
        with fetch(request) as response:
            raw = response.read()
    except HTTPError as exc:
        raise ScholarProviderError(f"arXiv request failed with HTTP {exc.code}") from exc
    except URLError as exc:
        raise ScholarProviderError(f"arXiv request failed: {exc.reason}") from exc

    try:
        root = ElementTree.fromstring(raw)
    except ElementTree.ParseError as exc:
        raise ScholarProviderError("arXiv returned invalid XML") from exc

    entries = root.findall("atom:entry", ARXIV_ATOM_NS)

    # arXiv returns HTTP 200 even on query errors, embedding a single
    # synthetic entry whose id starts with the errors namespace instead of
    # a real arxiv.org/abs/... URL.
    if len(entries) == 1:
        id_el = entries[0].find("atom:id", ARXIV_ATOM_NS)
        if id_el is not None and id_el.text and "api/errors" in id_el.text:
            title_el = entries[0].find("atom:title", ARXIV_ATOM_NS)
            detail = title_el.text.strip() if title_el is not None and title_el.text else "unknown error"
            raise ScholarProviderError(f"arXiv API error: {detail}")

    results = []
    for entry in entries[:max_results]:
        title_el = entry.find("atom:title", ARXIV_ATOM_NS)
        title = " ".join((title_el.text or "").split()) if title_el is not None and title_el.text else "Untitled"

        authors = []
        for author_el in entry.findall("atom:author", ARXIV_ATOM_NS):
            name_el = author_el.find("atom:name", ARXIV_ATOM_NS)
            if name_el is not None and name_el.text:
                authors.append(name_el.text.strip())

        published_el = entry.find("atom:published", ARXIV_ATOM_NS)
        year = _extract_year(published_el.text) if published_el is not None and published_el.text else None

        summary_el = entry.find("atom:summary", ARXIV_ATOM_NS)
        abstract = " ".join((summary_el.text or "").split()) if summary_el is not None and summary_el.text else None

        id_el = entry.find("atom:id", ARXIV_ATOM_NS)
        url = id_el.text.strip() if id_el is not None and id_el.text else None

        doi_el = entry.find("arxiv:doi", ARXIV_ATOM_NS)
        doi = doi_el.text.strip() if doi_el is not None and doi_el.text else None

        results.append(
            ScholarResult(
                title=title,
                authors=authors,
                year=year,
                citation_count=None,
                url=url,
                abstract=abstract or None,
                venue="arXiv",
                source_provider="arxiv",
                doi=doi,
            )
        )
    return results


# --------------------------------------------------------------------------
# Unified interface
# --------------------------------------------------------------------------

_ProviderFn = Callable[..., list[ScholarResult]]

_PROVIDER_PIPELINE: list[tuple[str, _ProviderFn]] = [
    ("serpapi", _fetch_serpapi),
    ("semantic_scholar", _fetch_semantic_scholar),
    ("scholarly", _fetch_scholarly),
    ("scholarapi_net", _fetch_scholarapi_net),
    ("openalex", _fetch_openalex),
    ("crossref", _fetch_crossref),
    ("arxiv", _fetch_arxiv),
]


class ScholarDataService:
    """Single entry point the rest of the app should call for Scholar data.

    Tries each backend in `_PROVIDER_PIPELINE` order and returns the first
    one that completes without raising -- including a provider that
    legitimately returns zero results, which is treated as a valid answer,
    not a failure. Only exceptions (missing keys, HTTP errors, rate limits,
    blocks, an uninstalled optional package) trigger a fallback to the next
    option. Every attempt, successful or not, is recorded on the returned
    `ScholarSearchResponse.attempts` for observability.
    """

    def __init__(self, *, workspace: Path | None = None, opener: Opener | None = None) -> None:
        self._workspace = workspace
        self._opener = opener

    def search(self, query: str, *, max_results: int = 10) -> ScholarSearchResponse:
        normalized_query = query.strip()
        if not normalized_query:
            raise ValueError("query must not be empty")

        attempts: list[ProviderAttempt] = []
        for name, provider_fn in _PROVIDER_PIPELINE:
            try:
                results = provider_fn(
                    normalized_query,
                    max_results,
                    workspace=self._workspace,
                    opener=self._opener,
                )
            except ScholarProviderError as exc:
                logger.warning("Scholar provider '%s' failed, falling back: %s", name, exc)
                attempts.append(ProviderAttempt(provider=name, status="error", detail=str(exc)))
                continue
            except Exception as exc:  # belt-and-braces: one backend must never crash the pipeline
                logger.exception("Scholar provider '%s' raised an unexpected error", name)
                attempts.append(ProviderAttempt(provider=name, status="error", detail=f"unexpected error: {exc}"))
                continue

            attempts.append(ProviderAttempt(provider=name, status="ok", detail=f"{len(results)} result(s)"))
            return ScholarSearchResponse(
                query=normalized_query,
                provider_used=name,
                results=results,
                attempts=attempts,
            )

        logger.error("All Scholar providers failed for query: %s", normalized_query)
        return ScholarSearchResponse(query=normalized_query, provider_used=None, results=[], attempts=attempts)
