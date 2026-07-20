import json
import sys
import types
from urllib.error import HTTPError
from urllib.request import Request

import pytest

from corroborly.engine.scholar_providers import (
    ScholarDataService,
    ScholarProviderError,
    _fetch_arxiv,
    _fetch_crossref,
    _fetch_openalex,
    _fetch_scholarapi_net,
    _fetch_scholarly,
    _fetch_semantic_scholar,
    _fetch_serpapi,
)


class FakeResponse:
    def __init__(self, data: object):
        self.data = json.dumps(data).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self) -> bytes:
        return self.data


def _opener(data: object):
    def _open(_request: Request):
        return FakeResponse(data)

    return _open


def _raising_opener(exc: Exception):
    def _open(_request: Request):
        raise exc

    return _open


class FakeXmlResponse:
    def __init__(self, xml_text: str):
        self.data = xml_text.encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self) -> bytes:
        return self.data


def _xml_opener(xml_text: str):
    def _open(_request: Request):
        return FakeXmlResponse(xml_text)

    return _open


# --------------------------------------------------------------------------
# Option 1: SerpApi
# --------------------------------------------------------------------------


def test_serpapi_raises_without_api_key(monkeypatch, tmp_path):
    monkeypatch.delenv("SERPAPI_API_KEY", raising=False)
    with pytest.raises(ScholarProviderError, match="SERPAPI_API_KEY"):
        _fetch_serpapi("container logistics", 5, workspace=tmp_path, opener=_opener({}))


def test_serpapi_parses_organic_results(monkeypatch, tmp_path):
    monkeypatch.setenv("SERPAPI_API_KEY", "test-key")
    data = {
        "organic_results": [
            {
                "title": "Container Terminal Efficiency",
                "link": "https://example.com/paper1",
                "snippet": "An abstract about terminals.",
                "publication_info": {
                    "summary": "A Author, B Author - 2021 - Journal of Ports",
                    "authors": [{"name": "A Author"}, {"name": "B Author"}],
                },
                "inline_links": {"cited_by": {"total": 42}},
            }
        ]
    }
    results = _fetch_serpapi("container logistics", 5, workspace=tmp_path, opener=_opener(data))
    assert len(results) == 1
    result = results[0]
    assert result.title == "Container Terminal Efficiency"
    assert result.authors == ["A Author", "B Author"]
    assert result.year == 2021
    assert result.citation_count == 42
    assert result.source_provider == "serpapi"


def test_serpapi_raises_on_api_error_payload(monkeypatch, tmp_path):
    monkeypatch.setenv("SERPAPI_API_KEY", "test-key")
    with pytest.raises(ScholarProviderError, match="SerpApi error"):
        _fetch_serpapi("q", 5, workspace=tmp_path, opener=_opener({"error": "Invalid API key."}))


def test_serpapi_raises_on_http_error(monkeypatch, tmp_path):
    monkeypatch.setenv("SERPAPI_API_KEY", "test-key")
    exc = HTTPError("url", 429, "Too Many Requests", None, None)
    with pytest.raises(ScholarProviderError, match="HTTP 429"):
        _fetch_serpapi("q", 5, workspace=tmp_path, opener=_raising_opener(exc))


# --------------------------------------------------------------------------
# Option 2: Semantic Scholar
# --------------------------------------------------------------------------


def test_semantic_scholar_works_without_api_key(monkeypatch, tmp_path):
    monkeypatch.delenv("SEMANTIC_SCHOLAR_API_KEY", raising=False)
    data = {
        "data": [
            {
                "title": "Evidence Tracking in Research Workflows",
                "authors": [{"name": "C Author"}],
                "year": 2022,
                "citationCount": 10,
                "abstract": "An abstract.",
                "venue": "Journal of Evidence",
                "url": "https://example.com/paper2",
            }
        ]
    }
    results = _fetch_semantic_scholar("evidence tracking", 5, workspace=tmp_path, opener=_opener(data))
    assert len(results) == 1
    result = results[0]
    assert result.title == "Evidence Tracking in Research Workflows"
    assert result.authors == ["C Author"]
    assert result.year == 2022
    assert result.citation_count == 10
    assert result.venue == "Journal of Evidence"
    assert result.source_provider == "semantic_scholar"


def test_semantic_scholar_raises_on_url_error(monkeypatch, tmp_path):
    from urllib.error import URLError

    exc = URLError("no network")
    with pytest.raises(ScholarProviderError, match="Semantic Scholar request failed"):
        _fetch_semantic_scholar("q", 5, workspace=tmp_path, opener=_raising_opener(exc))


# --------------------------------------------------------------------------
# Option 3: scholarly
# --------------------------------------------------------------------------


def test_scholarly_raises_when_package_missing(monkeypatch, tmp_path):
    monkeypatch.setitem(sys.modules, "scholarly", None)
    with pytest.raises(ScholarProviderError, match="scholarly"):
        _fetch_scholarly("q", 5, workspace=tmp_path, opener=None)


def test_scholarly_parses_search_pubs_results(monkeypatch, tmp_path):
    fake_module = types.ModuleType("scholarly")

    class _FakeScholarly:
        @staticmethod
        def search_pubs(_query):
            yield {
                "bib": {
                    "title": "Smart Port Digital Twins",
                    "author": ["D Author", "E Author"],
                    "pub_year": "2020",
                    "venue": "Port Systems Review",
                },
                "num_citations": 5,
                "pub_url": "https://example.com/paper3",
            }

    fake_module.scholarly = _FakeScholarly()
    monkeypatch.setitem(sys.modules, "scholarly", fake_module)

    results = _fetch_scholarly("smart port", 5, workspace=tmp_path, opener=None)
    assert len(results) == 1
    result = results[0]
    assert result.title == "Smart Port Digital Twins"
    assert result.authors == ["D Author", "E Author"]
    assert result.year == 2020
    assert result.citation_count == 5
    assert result.source_provider == "scholarly"


def test_scholarly_wraps_unexpected_errors(monkeypatch, tmp_path):
    fake_module = types.ModuleType("scholarly")

    class _FakeScholarly:
        @staticmethod
        def search_pubs(_query):
            raise RuntimeError("blocked by Google")

    fake_module.scholarly = _FakeScholarly()
    monkeypatch.setitem(sys.modules, "scholarly", fake_module)

    with pytest.raises(ScholarProviderError, match="blocked by Google"):
        _fetch_scholarly("q", 5, workspace=tmp_path, opener=None)


# --------------------------------------------------------------------------
# Option 4: ScholarAPI (scholarapi.net) stub
# --------------------------------------------------------------------------


def test_scholarapi_net_is_a_stub_that_always_raises(monkeypatch, tmp_path):
    monkeypatch.delenv("SCHOLARAPI_NET_API_KEY", raising=False)
    with pytest.raises(ScholarProviderError, match="SCHOLARAPI_NET_API_KEY"):
        _fetch_scholarapi_net("q", 5, workspace=tmp_path, opener=None)

    monkeypatch.setenv("SCHOLARAPI_NET_API_KEY", "some-key")
    with pytest.raises(ScholarProviderError, match="stub"):
        _fetch_scholarapi_net("q", 5, workspace=tmp_path, opener=None)


# --------------------------------------------------------------------------
# Option 5: OpenAlex
# --------------------------------------------------------------------------


def test_openalex_parses_results_and_reconstructs_abstract(tmp_path):
    data = {
        "results": [
            {
                "title": "Container Terminal Digital Twins",
                "publication_year": 2023,
                "cited_by_count": 7,
                "id": "https://openalex.org/W123",
                "doi": "https://doi.org/10.1234/abc",
                "authorships": [
                    {"author": {"display_name": "F Author"}},
                    {"author": {"display_name": "G Author"}},
                ],
                "primary_location": {
                    "landing_page_url": "https://example.com/paper5",
                    "source": {"display_name": "Journal of Smart Ports"},
                },
                "abstract_inverted_index": {"Digital": [0], "twins": [1], "for": [2], "ports": [3]},
            }
        ]
    }
    results = _fetch_openalex("digital twin ports", 5, workspace=tmp_path, opener=_opener(data))
    assert len(results) == 1
    result = results[0]
    assert result.title == "Container Terminal Digital Twins"
    assert result.authors == ["F Author", "G Author"]
    assert result.year == 2023
    assert result.citation_count == 7
    assert result.url == "https://example.com/paper5"
    assert result.venue == "Journal of Smart Ports"
    assert result.abstract == "Digital twins for ports"
    assert result.doi == "https://doi.org/10.1234/abc"
    assert result.source_provider == "openalex"


def test_openalex_returns_empty_list_on_missing_results_key(tmp_path):
    assert _fetch_openalex("q", 5, workspace=tmp_path, opener=_opener({"not_results": []})) == []


def test_openalex_raises_on_http_error(tmp_path):
    exc = HTTPError("url", 500, "Server Error", None, None)
    with pytest.raises(ScholarProviderError, match="HTTP 500"):
        _fetch_openalex("q", 5, workspace=tmp_path, opener=_raising_opener(exc))


# --------------------------------------------------------------------------
# Option 6: Crossref
# --------------------------------------------------------------------------


def test_crossref_parses_items(tmp_path):
    data = {
        "message": {
            "items": [
                {
                    "title": ["Predictive Container Flow Models"],
                    "author": [{"given": "H", "family": "Author"}],
                    "published": {"date-parts": [[2019, 6]]},
                    "is-referenced-by-count": 15,
                    "URL": "https://example.com/paper6",
                    "container-title": ["Logistics Research Quarterly"],
                    "abstract": "<jats:p>An abstract with tags.</jats:p>",
                    "DOI": "10.5678/def",
                }
            ]
        }
    }
    results = _fetch_crossref("container flow prediction", 5, workspace=tmp_path, opener=_opener(data))
    assert len(results) == 1
    result = results[0]
    assert result.title == "Predictive Container Flow Models"
    assert result.authors == ["H Author"]
    assert result.year == 2019
    assert result.citation_count == 15
    assert result.venue == "Logistics Research Quarterly"
    assert result.abstract == "An abstract with tags."
    assert result.doi == "10.5678/def"
    assert result.source_provider == "crossref"


def test_crossref_returns_empty_list_on_missing_items_key(tmp_path):
    assert _fetch_crossref("q", 5, workspace=tmp_path, opener=_opener({"message": {}})) == []


def test_crossref_raises_on_url_error(tmp_path):
    from urllib.error import URLError

    exc = URLError("no network")
    with pytest.raises(ScholarProviderError, match="Crossref request failed"):
        _fetch_crossref("q", 5, workspace=tmp_path, opener=_raising_opener(exc))


# --------------------------------------------------------------------------
# Option 7: arXiv
# --------------------------------------------------------------------------

_ARXIV_FEED = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/2101.00001v1</id>
    <title>Deep Learning for Container Terminal Scheduling</title>
    <summary>We study scheduling with deep learning methods.</summary>
    <published>2021-01-05T00:00:00Z</published>
    <author><name>I Author</name></author>
    <author><name>J Author</name></author>
    <arxiv:doi>10.9999/xyz</arxiv:doi>
  </entry>
</feed>
"""

_ARXIV_ERROR_FEED = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/api/errors#incorrect_id_format_for_test</id>
    <title>Error</title>
  </entry>
</feed>
"""


def test_arxiv_parses_atom_feed(tmp_path):
    results = _fetch_arxiv("container scheduling", 5, workspace=tmp_path, opener=_xml_opener(_ARXIV_FEED))
    assert len(results) == 1
    result = results[0]
    assert result.title == "Deep Learning for Container Terminal Scheduling"
    assert result.authors == ["I Author", "J Author"]
    assert result.year == 2021
    assert result.citation_count is None
    assert result.url == "http://arxiv.org/abs/2101.00001v1"
    assert result.venue == "arXiv"
    assert result.doi == "10.9999/xyz"
    assert result.source_provider == "arxiv"


def test_arxiv_raises_on_error_feed(tmp_path):
    with pytest.raises(ScholarProviderError, match="arXiv API error"):
        _fetch_arxiv("q", 5, workspace=tmp_path, opener=_xml_opener(_ARXIV_ERROR_FEED))


def test_arxiv_raises_on_http_error(tmp_path):
    exc = HTTPError("url", 503, "Service Unavailable", None, None)
    with pytest.raises(ScholarProviderError, match="HTTP 503"):
        _fetch_arxiv("q", 5, workspace=tmp_path, opener=_raising_opener(exc))


def test_arxiv_raises_on_invalid_xml(tmp_path):
    with pytest.raises(ScholarProviderError, match="invalid XML"):
        _fetch_arxiv("q", 5, workspace=tmp_path, opener=_xml_opener("not xml"))


# --------------------------------------------------------------------------
# Unified pipeline (ScholarDataService)
# --------------------------------------------------------------------------


def test_service_falls_through_to_semantic_scholar_when_serpapi_key_missing(monkeypatch, tmp_path):
    monkeypatch.delenv("SERPAPI_API_KEY", raising=False)
    monkeypatch.delenv("SEMANTIC_SCHOLAR_API_KEY", raising=False)
    monkeypatch.setitem(sys.modules, "scholarly", None)

    data = {
        "data": [
            {
                "title": "Fallback Result",
                "authors": [],
                "year": 2023,
                "citationCount": 1,
                "abstract": None,
                "venue": None,
                "url": "https://example.com/paper4",
            }
        ]
    }
    service = ScholarDataService(workspace=tmp_path, opener=_opener(data))
    response = service.search("container logistics", max_results=3)

    assert response.succeeded is True
    assert response.provider_used == "semantic_scholar"
    assert len(response.results) == 1
    assert response.results[0].title == "Fallback Result"

    statuses = {attempt.provider: attempt.status for attempt in response.attempts}
    assert statuses["serpapi"] == "error"
    assert statuses["semantic_scholar"] == "ok"


def test_service_stops_at_first_successful_provider_even_with_zero_results(monkeypatch, tmp_path):
    monkeypatch.delenv("SERPAPI_API_KEY", raising=False)
    monkeypatch.delenv("SEMANTIC_SCHOLAR_API_KEY", raising=False)

    service = ScholarDataService(workspace=tmp_path, opener=_opener({"data": []}))
    response = service.search("no results query")

    assert response.succeeded is True
    assert response.provider_used == "semantic_scholar"
    assert response.results == []


def test_service_reports_failure_when_every_option_fails(monkeypatch, tmp_path):
    monkeypatch.delenv("SERPAPI_API_KEY", raising=False)
    monkeypatch.delenv("SEMANTIC_SCHOLAR_API_KEY", raising=False)
    monkeypatch.delenv("SCHOLARAPI_NET_API_KEY", raising=False)
    monkeypatch.setitem(sys.modules, "scholarly", None)

    from urllib.error import URLError

    service = ScholarDataService(workspace=tmp_path, opener=_raising_opener(URLError("offline")))
    response = service.search("container logistics")

    assert response.succeeded is False
    assert response.provider_used is None
    assert response.results == []
    assert len(response.attempts) == 7
    assert all(attempt.status == "error" for attempt in response.attempts)


def test_service_rejects_empty_query():
    service = ScholarDataService()
    with pytest.raises(ValueError):
        service.search("   ")
