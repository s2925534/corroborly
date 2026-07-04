import json
from pathlib import Path
from urllib.request import Request

import pytest

from researchboss.core.yamlio import read_yaml, write_yaml
from researchboss.engine.external_search import (
    ExternalSearchError,
    SearchBudgets,
    SearchThresholds,
    ScopusCredentials,
    external_candidate_register_path,
    filter_unused_queries,
    generate_auto_refine_plan,
    generate_search_query_plan,
    import_external_candidates,
    parse_legacy_params_file,
    query_history_key,
    record_queries_used,
    require_external_search_flag,
    score_scopus_entry,
    scopus_readiness,
    scopus_search,
)
from researchboss.engine.workspace import init_workspace


class FakeResponse:
    def __init__(self, data: object):
        self.data = json.dumps(data).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self) -> bytes:
        return self.data


def test_require_external_search_flag_blocks_live_search_without_opt_in() -> None:
    with pytest.raises(ExternalSearchError, match="--external-search"):
        require_external_search_flag(False)


def test_generate_search_query_plan_uses_workspace_context_without_external_call(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(
        workspace,
        project_name="Test",
        project_type="PhD",
        topic="container port evidence tracking",
        research_questions=[{"question": "How does container tracking affect port review quality?", "status": "approved"}],
    )

    plan = generate_search_query_plan(workspace, max_queries=5)

    assert plan["external_search_performed"] is False
    assert plan["strategy"] == "balanced"
    assert plan["query_records"]
    assert 1 <= len(plan["queries"]) <= 5
    assert (workspace / "outputs" / "recommendations" / "external-search-query-plan.yaml").is_file()


def test_generate_search_query_plan_supports_strategies_and_rq_links(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(
        workspace,
        project_name="Test",
        project_type="PhD",
        topic="container port evidence tracking",
        research_questions=[{"id": "rq1", "question": "How does container tracking affect port evidence quality?", "status": "approved"}],
    )

    broad = generate_search_query_plan(workspace, max_queries=5, strategy="broad")
    strict = generate_search_query_plan(workspace, max_queries=5, strategy="strict")

    assert broad["strategy"] == "broad"
    assert strict["strategy"] == "strict"
    assert all(record["strategy"] == "strict" for record in strict["query_records"])
    assert any(record["linked_research_questions"] for record in broad["query_records"])


def test_parse_legacy_params_file_preserves_groups(tmp_path: Path) -> None:
    params = tmp_path / "params.txt"
    params.write_text(
        """
Search Parameters - RQ1: Container Readiness

"container handling" AND "performance metric"
"port logistics" AND "container scoring"

Search Parameters - RQ2: Data Mapping
"data harmonization" AND "logistics"
""",
        encoding="utf-8",
    )

    records = parse_legacy_params_file(params)

    assert len(records) == 3
    assert records[0]["group_label"] == "RQ1: Container Readiness"
    assert records[0]["source"] == "legacy_params_file"
    assert records[-1]["group_label"] == "RQ2: Data Mapping"


def test_generate_search_query_plan_imports_legacy_params_first(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    params = tmp_path / "params.txt"
    params.write_text('Search Parameters - RQ1\n"container handling" AND "performance metric"\n', encoding="utf-8")
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="container performance")

    plan = generate_search_query_plan(workspace, max_queries=5, params_file=params)

    assert plan["imported_query_count"] == 1
    assert plan["queries"][0] == '"container handling" AND "performance metric"'
    assert plan["query_records"][0]["source"] == "legacy_params_file"


def test_query_history_records_and_filters_used_queries(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")
    query = '"container" AND "port"'

    history = record_queries_used(workspace, [query], [{"query": query, "processed": 3}])

    assert query_history_key(query) in history["queries"]
    assert filter_unused_queries(workspace, [query, '"new" AND "query"']) == ['"new" AND "query"']


def test_scopus_readiness_does_not_expose_credentials() -> None:
    def opener(request: Request):
        assert request.get_method() == "GET"
        assert request.headers["X-els-apikey"] == "scopus-secret"
        assert request.headers["X-els-insttoken"] == "inst-secret"
        return FakeResponse({"search-results": {"opensearch:totalResults": "10", "entry": []}})

    report = scopus_readiness(
        ScopusCredentials(api_key="scopus-secret", inst_token="inst-secret"),
        opener=opener,
    )

    assert report["key_loaded"] is True
    assert report["inst_token_loaded"] is True
    assert report["key_exposed"] is False
    assert "scopus-secret" not in str(report)
    assert "inst-secret" not in str(report)


def test_scopus_search_writes_snapshot_and_history(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")

    def opener(request: Request):
        assert "container" in request.full_url
        return FakeResponse(
            {
                "search-results": {
                    "entry": [
                        {
                            "dc:title": "Container port evidence paper",
                            "citedby-count": "25",
                            "prism:coverDate": "2024-01-01",
                            "prism:publicationName": "Journal of Ports",
                            "prism:doi": "10.1000/example",
                            "eid": "2-s2.0-123",
                            "openaccess": "1",
                            "author": [{"authname": "Veloso, P.", "authid": "123"}],
                        }
                    ]
                }
            }
        )

    report = scopus_search(
        workspace,
        ScopusCredentials(api_key="scopus-secret"),
        query='"container"',
        count=1,
        thresholds=SearchThresholds.from_options(min_citations=10, year_from=2020, open_access_only=True),
        opener=opener,
    )

    assert report["metrics"]["processed"] == 1
    assert report["metrics"]["candidate_count"] == 1
    assert Path(report["snapshot_path"]).is_file()
    assert read_yaml(workspace / "outputs" / "recommendations" / "external-search-query-history.yaml")["queries"]
    register = read_yaml(workspace / "outputs" / "recommendations" / "external-paper-candidates.yaml")
    assert register["candidates"][0]["quality_score"] > 0
    assert register["candidates"][0]["metadata_only"] is True
    validation = read_yaml(workspace / "outputs" / "validation" / "external-search-query-validation.yaml")
    assert validation["validation"]["threshold_pass_rate"] == 1.0
    assert Path(report["metrics"]["batch_summary_path"]).is_file()


def test_import_external_candidates_adds_metadata_only_pending_sources(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")
    candidate_id = "ext-scopus-example"
    write_candidate_register(
        workspace,
        [
            {
                "candidate_id": candidate_id,
                "provider": "scopus",
                "title": "Container port evidence paper",
                "year": 2024,
                "doi": "10.1000/example",
                "source_title": "Journal of Ports",
                "document_type": "Article",
                "citation_count": 25,
                "quality_score": 80,
                "authors": [{"name": "Veloso, P.", "authid": "123"}],
                "full_text_availability": {"doi_present": True},
            }
        ],
    )

    report = import_external_candidates(workspace, [candidate_id, candidate_id])
    repeated = import_external_candidates(workspace, [candidate_id])

    source_register = read_yaml(workspace / "source-register.yaml")
    source = source_register["sources"][0]
    candidate_register = read_yaml(external_candidate_register_path(workspace))
    candidate = candidate_register["candidates"][0]
    assert report["imported_count"] == 1
    assert repeated["skipped_count"] == 1
    assert len(source_register["sources"]) == 1
    assert source["source_id"] == candidate_id
    assert source["status"] == "pending_review"
    assert source["metadata_only"] is True
    assert source["citation_metadata"]["doi"] == "10.1000/example"
    assert candidate["review_status"] == "imported_pending_review"
    assert candidate["imported_source_id"] == candidate_id


def test_scopus_search_updates_batch_summary_across_queries(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")
    payloads = [
        {
            "search-results": {
                "entry": [
                    {
                        "dc:title": "Strong evidence paper",
                        "citedby-count": "20",
                        "prism:coverDate": "2024-01-01",
                        "eid": "2-s2.0-strong",
                    },
                    {
                        "dc:title": "Strong evidence paper",
                        "citedby-count": "20",
                        "prism:coverDate": "2024-01-01",
                        "eid": "2-s2.0-strong",
                    },
                    {
                        "dc:title": "Filtered evidence paper",
                        "citedby-count": "1",
                        "prism:coverDate": "2024-01-01",
                        "eid": "2-s2.0-filtered",
                    },
                    "malformed result",
                ]
            }
        },
        {"search-results": {"entry": []}},
    ]

    def opener(_request: Request):
        return FakeResponse(payloads.pop(0))

    thresholds = SearchThresholds.from_options(min_citations=10, low_result_threshold=4)
    scopus_search(
        workspace,
        ScopusCredentials(api_key="scopus-secret"),
        query='"evidence"',
        count=4,
        thresholds=thresholds,
        opener=opener,
    )
    second = scopus_search(
        workspace,
        ScopusCredentials(api_key="scopus-secret"),
        query='"missing"',
        count=4,
        thresholds=thresholds,
        opener=opener,
    )

    summary = read_yaml(Path(second["metrics"]["batch_summary_path"]))
    assert summary["totals"] == {
        "query_count": 2,
        "processed_count": 4,
        "candidate_count": 2,
        "filtered_count": 1,
        "skipped_count": 1,
        "duplicate_count": 1,
        "no_result_count": 1,
        "low_result_count": 1,
    }
    assert [run["query"] for run in summary["runs"]] == ['"evidence"', '"missing"']


def test_scopus_search_enforces_search_budgets_before_request(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")

    def opener(_request: Request):
        raise AssertionError("request should not be made after budget exhaustion")

    with pytest.raises(ExternalSearchError, match="result_count_budget_exhausted"):
        scopus_search(
            workspace,
            ScopusCredentials(api_key="scopus-secret"),
            query='"container"',
            count=5,
            thresholds=SearchThresholds.from_options(max_results_per_query=5),
            budgets=SearchBudgets.from_options(max_result_count=3),
            opener=opener,
        )


def test_scopus_search_writes_filtered_logs_and_external_reports(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(
        workspace,
        project_name="Test",
        project_type="M.Phil",
        topic="container evidence",
        research_questions=[{"id": "rq1", "question": "How does container evidence support claims?", "status": "approved"}],
    )
    (workspace / "source-register.yaml").write_text(
        """
version: 1
sources:
  - source_id: source-001
    provider: zotero_storage
    status: accepted
    citation_metadata:
      title: Local evidence paper
      year: "2024"
      doi: 10.1000/strong
""",
        encoding="utf-8",
    )
    (workspace / "accepted-sources.yaml").write_text("version: 1\nsource_ids:\n  - source-001\n", encoding="utf-8")
    (workspace / "claims-ledger.yaml").write_text(
        "version: 1\nclaims:\n  - id: claim-001\n    text: Container evidence supports claim review.\n    linked_sources: []\n",
        encoding="utf-8",
    )

    def opener(_request: Request):
        return FakeResponse(
            {
                "search-results": {
                    "entry": [
                        {
                            "dc:title": "Container evidence supports claim review",
                            "citedby-count": "30",
                            "prism:coverDate": "2024-01-01",
                            "prism:publicationName": "Journal of Evidence",
                            "prism:doi": "10.1000/strong",
                            "eid": "2-s2.0-strong",
                            "author": [{"authname": "Researcher, A.", "authid": "123"}],
                        },
                        {
                            "dc:title": "Old filtered paper",
                            "citedby-count": "1",
                            "prism:coverDate": "2010-01-01",
                            "eid": "2-s2.0-filtered",
                        },
                    ]
                }
            }
        )

    report = scopus_search(
        workspace,
        ScopusCredentials(api_key="scopus-secret"),
        query='"container" AND "evidence"',
        count=2,
        thresholds=SearchThresholds.from_options(min_citations=10, year_from=2020),
        opener=opener,
    )

    filtered = read_yaml(Path(report["metrics"]["filtered_candidate_log_path"]))
    assert filtered["candidates"][0]["failure_reasons"][0]["kind"] == "below_min_citations"
    assert filtered["candidates"][0]["metadata_flags"][0]["kind"] == "missing_doi"
    high_signal = read_yaml(Path(report["metrics"]["high_signal_report_path"]))
    assert high_signal["candidates"][0]["rq_coverage_count"] == 1
    assert high_signal["references"]["accepted_workspace_evidence"] == []
    assert high_signal["references"]["external_candidate_sources"][0]["reference"].startswith("Researcher, A.")
    assert "https://doi.org/10.1000/strong" in high_signal["references"]["external_candidate_sources"][0]["reference"]
    duplicates = read_yaml(Path(report["metrics"]["candidate_duplicates_path"]))
    assert duplicates["source_match_count"] == 1
    evidence = read_yaml(Path(report["metrics"]["evidence_validation_path"]))
    assert evidence["candidates"][0]["claim_matches"][0]["claim_id"] == "claim-001"
    comparison = read_yaml(Path(report["metrics"]["run_comparison_path"]))
    assert comparison["runs"][0]["candidate_count"] == 1


def test_generate_auto_refine_plan_uses_issue_logs_and_budgets(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")
    issue_log = workspace / "outputs" / "external-search" / "scopus-no-results.yaml"
    issue_log.parent.mkdir(parents=True, exist_ok=True)
    issue_log.write_text(
        """
version: 1
queries:
  - query: '"container" AND "port" AND "evidence"'
    refinement_suggestions:
      - Broaden the query.
""",
        encoding="utf-8",
    )

    plan = generate_auto_refine_plan(
        workspace,
        budgets=SearchBudgets.from_options(
            max_api_calls=0,
            max_generated_queries=1,
            max_refinement_rounds=1,
            max_result_pages=1,
            max_result_count=25,
        ),
        max_queries=5,
        max_refinement_rounds=1,
        max_results_per_query=25,
    )

    assert plan["approval_required"] is True
    assert plan["external_search_performed"] is False
    assert plan["queries"] == ['"port" AND "evidence"']
    assert "query_budget_reached" in plan["budget_status"]["exhaustion_reasons"]
    assert (workspace / "outputs" / "recommendations" / "external-search-refine-plan.yaml").is_file()


def test_score_scopus_entry_uses_only_returned_metadata() -> None:
    candidate = score_scopus_entry(
        {
            "dc:title": "Evidence validation",
            "citedby-count": "40",
            "prism:coverDate": "2023-05-01",
            "prism:publicationName": "Research Methods",
            "prism:doi": "10.1000/test",
            "eid": "2-s2.0-test",
            "openaccess": "0",
            "author": [{"authname": "Researcher, A.", "authid": "42"}],
        },
        current_year=2026,
    )

    assert candidate["citation_count"] == 40
    assert candidate["year"] == 2023
    assert candidate["open_access"] is False
    assert candidate["quality_score"] > 0
    assert candidate["metadata_only"] is True
    assert candidate["full_text_availability"]["full_text_retrieved"] is False


def test_scopus_search_logs_no_result_queries_with_refinement_suggestions(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")

    def opener(_request: Request):
        return FakeResponse({"search-results": {"entry": []}})

    report = scopus_search(
        workspace,
        ScopusCredentials(api_key="scopus-secret"),
        query='"unlikelyterm" AND "missingterm"',
        count=1,
        opener=opener,
    )

    assert report["metrics"]["no_results"] is True
    no_results = read_yaml(workspace / "outputs" / "external-search" / "scopus-no-results.yaml")
    assert no_results["queries"][0]["refinement_suggestions"]


def test_scopus_search_logs_low_result_queries(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")

    def opener(_request: Request):
        return FakeResponse({"search-results": {"entry": [{"dc:title": "One result", "citedby-count": "0"}]}})

    report = scopus_search(
        workspace,
        ScopusCredentials(api_key="scopus-secret"),
        query='"one"',
        count=1,
        thresholds=SearchThresholds.from_options(low_result_threshold=3),
        opener=opener,
    )

    assert report["metrics"]["low_results"] is True
    low_results = read_yaml(workspace / "outputs" / "external-search" / "scopus-low-results.yaml")
    assert low_results["queries"][0]["processed"] == 1


def write_candidate_register(workspace: Path, candidates: list[dict[str, object]]) -> None:
    path = external_candidate_register_path(workspace)
    path.parent.mkdir(parents=True, exist_ok=True)
    write_yaml(path, {"version": 1, "candidates": candidates, "runs": []})
