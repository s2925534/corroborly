from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from researchboss.core.yamlio import read_yaml, write_yaml


OPENAI_API_BASE_URL = "https://api.openai.com/v1"


@dataclass(frozen=True)
class OpenAiCredentials:
    api_key: str


class OpenAiError(RuntimeError):
    pass


def load_dotenv_values(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    values = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def openai_credentials(workspace: Path | None = None) -> OpenAiCredentials:
    env_values = load_dotenv_values(Path.cwd() / ".env")
    if workspace is not None:
        env_values = {**env_values, **load_dotenv_values(workspace / ".env")}
    api_key = os.environ.get("OPENAI_API_KEY") or env_values.get("OPENAI_API_KEY") or ""
    if not api_key:
        raise OpenAiError("Missing OPENAI_API_KEY")
    return OpenAiCredentials(api_key=api_key)


def workspace_ai_settings(workspace: Path) -> dict[str, Any]:
    settings = read_yaml(workspace / "app-settings.local.yaml")
    ai_settings = settings.get("ai")
    return ai_settings if isinstance(ai_settings, dict) else {}


def require_ai_flag(ai: bool) -> None:
    if not ai:
        raise OpenAiError("Pass --ai to explicitly allow this OpenAI action.")


def require_full_file_ai_opt_in(*, ai: bool, full_file: bool) -> None:
    require_ai_flag(ai)
    if not full_file:
        raise OpenAiError("Pass --full-file-ai to explicitly allow sending a whole file to an AI provider.")


def require_directory_ai_opt_in(*, ai: bool, directory: bool) -> None:
    require_ai_flag(ai)
    if not directory:
        raise OpenAiError("Pass --directory-ai to explicitly allow folder-level AI context.")


def require_full_target_document_ai_opt_in(*, ai: bool, full_target_document: bool) -> None:
    require_ai_flag(ai)
    if not full_target_document:
        raise OpenAiError("Pass --full-target-document-ai to explicitly allow sending a whole target document to an AI provider.")


def require_full_source_document_ai_opt_in(*, ai: bool, full_source_document: bool) -> None:
    require_ai_flag(ai)
    if not full_source_document:
        raise OpenAiError("Pass --full-source-document-ai to explicitly allow sending whole backing/source documents to an AI provider.")


def openai_get(
    path: str,
    credentials: OpenAiCredentials,
    *,
    opener: Callable[[Request], Any] | None = None,
    base_url: str = OPENAI_API_BASE_URL,
) -> Any:
    url = f"{base_url.rstrip('/')}/{path.lstrip('/')}"
    request = Request(
        url,
        headers={
            "Authorization": f"Bearer {credentials.api_key}",
            "Accept": "application/json",
        },
        method="GET",
    )
    fetch = opener or urlopen
    try:
        with fetch(request) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise OpenAiError(f"OpenAI request failed with HTTP {exc.code}") from exc
    except URLError as exc:
        raise OpenAiError(f"OpenAI request failed: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise OpenAiError("OpenAI returned invalid JSON") from exc


def openai_post(
    path: str,
    credentials: OpenAiCredentials,
    body: dict[str, Any],
    *,
    opener: Callable[[Request], Any] | None = None,
    base_url: str = OPENAI_API_BASE_URL,
) -> Any:
    url = f"{base_url.rstrip('/')}/{path.lstrip('/')}"
    request = Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {credentials.api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    fetch = opener or urlopen
    try:
        with fetch(request) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise OpenAiError(f"OpenAI request failed with HTTP {exc.code}") from exc
    except URLError as exc:
        raise OpenAiError(f"OpenAI request failed: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise OpenAiError("OpenAI returned invalid JSON") from exc


def default_openai_model(workspace: Path) -> str:
    ai_settings = workspace_ai_settings(workspace)
    providers = ai_settings.get("providers") if isinstance(ai_settings.get("providers"), dict) else {}
    openai_settings = providers.get("openai") if isinstance(providers.get("openai"), dict) else {}
    return str(openai_settings.get("default_model") or "gpt-4o-mini")


def extract_response_text(data: Any) -> str:
    if not isinstance(data, dict):
        return ""
    output_text = data.get("output_text")
    if isinstance(output_text, str):
        return output_text

    parts: list[str] = []
    output = data.get("output")
    if isinstance(output, list):
        for item in output:
            if not isinstance(item, dict):
                continue
            content = item.get("content")
            if not isinstance(content, list):
                continue
            for content_item in content:
                if not isinstance(content_item, dict):
                    continue
                text = content_item.get("text")
                if isinstance(text, str):
                    parts.append(text)
    return "\n".join(parts)


def openai_readiness(
    workspace: Path,
    credentials: OpenAiCredentials,
    *,
    live: bool = False,
    opener: Callable[[Request], Any] | None = None,
) -> dict[str, Any]:
    ai_settings = workspace_ai_settings(workspace)
    openai_settings = {}
    providers = ai_settings.get("providers") if isinstance(ai_settings.get("providers"), dict) else {}
    if isinstance(providers.get("openai"), dict):
        openai_settings = providers["openai"]

    report: dict[str, Any] = {
        "version": 1,
        "provider": "openai",
        "key_loaded": bool(credentials.api_key),
        "key_exposed": False,
        "workspace_ai_enabled": bool(ai_settings.get("enabled")),
        "openai_provider_enabled": bool(openai_settings.get("enabled")),
        "default_model": openai_settings.get("default_model"),
        "live_request_performed": False,
        "policy": "explicit_ai_flag_required",
    }

    if live:
        data = openai_get("models", credentials, opener=opener)
        models = data.get("data") if isinstance(data, dict) else []
        report["live_request_performed"] = True
        report["api_reachable"] = True
        report["model_count"] = len(models) if isinstance(models, list) else 0

    return report


def _safe_source_metadata(source: dict[str, Any]) -> dict[str, Any]:
    allowed_fields = [
        "source_id",
        "provider",
        "file_name",
        "file_ext",
        "status",
        "content_hash",
        "title",
        "creators",
        "year",
        "doi",
        "item_type",
        "publication_title",
        "tags",
        "notes",
        "zotero_item_key",
        "zotero_storage_key",
        "has_zotero_fulltext_cache",
    ]
    return {field: source.get(field) for field in allowed_fields if field in source}


def _read_excerpt(path: Path, max_chars: int) -> tuple[str, bool]:
    text = path.read_text(encoding="utf-8", errors="replace")
    if len(text) <= max_chars:
        return text, False
    return text[:max_chars], True


def build_safe_context(
    workspace: Path,
    *,
    source_status: str = "accepted",
    max_sources: int = 10,
    max_excerpt_chars: int = 1200,
) -> dict[str, Any]:
    if max_sources < 1:
        raise OpenAiError("max_sources must be at least 1")
    if max_excerpt_chars < 0:
        raise OpenAiError("max_excerpt_chars cannot be negative")

    register = read_yaml(workspace / "source-register.yaml")
    sources = [source for source in register.get("sources", []) if isinstance(source, dict)]
    selected = [source for source in sources if source.get("status") == source_status][:max_sources]

    entries = []
    for source in selected:
        entry: dict[str, Any] = {
            "metadata": _safe_source_metadata(source),
            "original_file_excluded": True,
            "full_document_excluded": True,
            "excerpt_source": None,
            "excerpt": None,
            "excerpt_truncated": False,
        }
        conversion = source.get("conversion") if isinstance(source.get("conversion"), dict) else {}
        output_path = conversion.get("output_path")
        if conversion.get("status") in {"converted", "skipped_unchanged"} and output_path and max_excerpt_chars > 0:
            converted_path = Path(str(output_path))
            if converted_path.is_file() and converted_path.resolve().is_relative_to(workspace.resolve()):
                excerpt, truncated = _read_excerpt(converted_path, max_excerpt_chars)
                entry["excerpt_source"] = str(converted_path.relative_to(workspace))
                entry["excerpt"] = excerpt
                entry["excerpt_truncated"] = truncated
        entries.append(entry)

    return {
        "version": 1,
        "purpose": "safe_ai_context_preview",
        "policy": {
            "requires_explicit_ai_flag": True,
            "original_files_excluded": True,
            "full_documents_excluded": True,
            "whole_csv_excluded": True,
            "whole_sqlite_excluded": True,
            "zotero_directory_no_write_boundary": True,
        },
        "limits": {
            "source_status": source_status,
            "max_sources": max_sources,
            "max_excerpt_chars": max_excerpt_chars,
        },
        "sources": entries,
    }


def _review_prompt(context: dict[str, Any]) -> str:
    return (
        "You are assisting with a local-first, evidence-first research workspace.\n"
        "Use only the provided safe context. Do not infer from unavailable full documents. "
        "Do not claim novelty or evidence strength certainty. Return concise markdown with sections: "
        "Scope, Useful Signals, Evidence Gaps, Source Follow-up, Human Review Required.\n\n"
        f"Safe context JSON:\n{json.dumps(context, ensure_ascii=False, indent=2)}"
    )


def ai_assisted_review(
    workspace: Path,
    credentials: OpenAiCredentials,
    *,
    max_sources: int = 10,
    max_excerpt_chars: int = 1200,
    opener: Callable[[Request], Any] | None = None,
) -> dict[str, Any]:
    context = build_safe_context(workspace, max_sources=max_sources, max_excerpt_chars=max_excerpt_chars)
    model = default_openai_model(workspace)
    response = openai_post(
        "responses",
        credentials,
        {
            "model": model,
            "input": _review_prompt(context),
        },
        opener=opener,
    )
    review_text = extract_response_text(response)
    return {
        "version": 1,
        "kind": "ai_assisted_review",
        "provider": "openai",
        "model": model,
        "ai_used": True,
        "requires_user_review": True,
        "safe_context_policy": context["policy"],
        "limits": context["limits"],
        "source_count": len(context["sources"]),
        "response_id": response.get("id") if isinstance(response, dict) else None,
        "review": review_text,
    }


def _novelty_prompt(context: dict[str, Any], research_questions: dict[str, Any]) -> str:
    return (
        "You are assisting with an AI-assisted novelty assessment for a local research workspace.\n"
        "Use only the safe context and research questions below. Do not claim that novelty is proven. "
        "Identify possible novelty signals, likely overlaps, missing evidence, and follow-up checks. "
        "Return concise markdown with sections: Assessment Boundary, Possible Novelty Signals, "
        "Likely Overlaps, Missing Evidence, Follow-up Checks, Human Review Required.\n\n"
        f"Research questions JSON:\n{json.dumps(research_questions, ensure_ascii=False, indent=2)}\n\n"
        f"Safe context JSON:\n{json.dumps(context, ensure_ascii=False, indent=2)}"
    )


def _append_novelty_assessment(workspace: Path, record: dict[str, Any]) -> None:
    ledger_path = workspace / "novelty-ledger.yaml"
    ledger = read_yaml(ledger_path)
    assessments = list(ledger.get("assessments", []))
    record = {"id": f"novelty-{len(assessments) + 1:03d}", **record}
    assessments.append(record)
    ledger["version"] = ledger.get("version", 1)
    ledger["assessments"] = assessments
    write_yaml(ledger_path, ledger)


def ai_novelty_assessment(
    workspace: Path,
    credentials: OpenAiCredentials,
    *,
    max_sources: int = 10,
    max_excerpt_chars: int = 1200,
    opener: Callable[[Request], Any] | None = None,
) -> dict[str, Any]:
    context = build_safe_context(workspace, max_sources=max_sources, max_excerpt_chars=max_excerpt_chars)
    research_questions = {
        "approved": read_yaml(workspace / "research-questions.yaml").get("research_questions", []),
        "candidates": read_yaml(workspace / "research-question-candidates.yaml").get("candidates", []),
    }
    model = default_openai_model(workspace)
    response = openai_post(
        "responses",
        credentials,
        {
            "model": model,
            "input": _novelty_prompt(context, research_questions),
        },
        opener=opener,
    )
    assessment_text = extract_response_text(response)
    report = {
        "version": 1,
        "kind": "ai_assisted_novelty_assessment",
        "provider": "openai",
        "model": model,
        "ai_used": True,
        "requires_user_review": True,
        "novelty_not_proven": True,
        "safe_context_policy": context["policy"],
        "limits": context["limits"],
        "source_count": len(context["sources"]),
        "research_question_count": len(research_questions["approved"]) + len(research_questions["candidates"]),
        "response_id": response.get("id") if isinstance(response, dict) else None,
        "assessment": assessment_text,
    }
    _append_novelty_assessment(
        workspace,
        {
            "kind": report["kind"],
            "provider": report["provider"],
            "model": report["model"],
            "response_id": report["response_id"],
            "requires_user_review": True,
            "novelty_not_proven": True,
            "source_count": report["source_count"],
            "research_question_count": report["research_question_count"],
            "assessment": assessment_text,
        },
    )
    return report


def _rq_assessment_prompt(context: dict[str, Any], research_questions: dict[str, Any], rq_id: str | None) -> str:
    return (
        "You are assisting with research-question assessment for a local-first research workspace.\n"
        "Use only the provided research questions and safe context. Do not claim that novelty, usefulness, "
        "or evidence quality are proven. Assess likely strengths, weaknesses, scope risks, evidence fit, "
        "field usefulness signals, and follow-up revisions. Return concise markdown with one section per "
        "research question and a final Human Review Required section.\n\n"
        f"Requested research question id: {rq_id or 'all'}\n\n"
        f"Research questions JSON:\n{json.dumps(research_questions, ensure_ascii=False, indent=2)}\n\n"
        f"Safe context JSON:\n{json.dumps(context, ensure_ascii=False, indent=2)}"
    )


def _filter_research_questions(research_questions: dict[str, Any], rq_id: str | None) -> dict[str, Any]:
    if rq_id is None:
        return research_questions
    filtered: dict[str, Any] = {}
    matched = False
    for group, items in research_questions.items():
        group_items = [item for item in items if isinstance(item, dict) and item.get("id") == rq_id]
        if group_items:
            matched = True
        filtered[group] = group_items
    if not matched:
        raise OpenAiError(f"Unknown research question: {rq_id}")
    return filtered


def ai_research_question_assessment(
    workspace: Path,
    credentials: OpenAiCredentials,
    *,
    rq_id: str | None = None,
    max_sources: int = 10,
    max_excerpt_chars: int = 1200,
    opener: Callable[[Request], Any] | None = None,
) -> dict[str, Any]:
    context = build_safe_context(workspace, max_sources=max_sources, max_excerpt_chars=max_excerpt_chars)
    research_questions = {
        "approved": read_yaml(workspace / "research-questions.yaml").get("research_questions", []),
        "candidates": read_yaml(workspace / "research-question-candidates.yaml").get("candidates", []),
    }
    selected_questions = _filter_research_questions(research_questions, rq_id)
    question_count = sum(len(items) for items in selected_questions.values())
    model = default_openai_model(workspace)
    response = openai_post(
        "responses",
        credentials,
        {
            "model": model,
            "input": _rq_assessment_prompt(context, selected_questions, rq_id),
        },
        opener=opener,
    )
    assessment_text = extract_response_text(response)
    return {
        "version": 1,
        "kind": "ai_research_question_assessment",
        "provider": "openai",
        "model": model,
        "ai_used": True,
        "requires_user_review": True,
        "novelty_not_proven": True,
        "safe_context_policy": context["policy"],
        "limits": context["limits"],
        "source_count": len(context["sources"]),
        "research_question_count": question_count,
        "rq_id": rq_id,
        "response_id": response.get("id") if isinstance(response, dict) else None,
        "assessment": assessment_text,
    }


AI_WORKSPACE_REPORTS = {
    "corpus_summary": {
        "title": "AI corpus summary",
        "sections": "Scope, Main Themes, Evidence Signals, Gaps, Human Review Required",
    },
    "claim_checking": {
        "title": "AI claim-checking assistance",
        "sections": "Claim Coverage, Supported Signals, Missing Evidence, Risky Claims, Human Review Required",
    },
    "citation_gaps": {
        "title": "AI citation gap recommendations",
        "sections": "Likely Citation Gaps, Candidate Source Links, Missing Source Types, Follow-up Checks, Human Review Required",
    },
    "artefact_cross_reference": {
        "title": "AI artefact cross-reference review",
        "sections": "Artefact Coverage, Source Links, Research Question Links, Evidence Gaps, Human Review Required",
    },
    "source_relevance": {
        "title": "AI source relevance recommendations",
        "sections": "Relevant Source Signals, Low-Relevance Risks, Suggested Review Tags, Follow-up Checks, Human Review Required",
    },
    "abstract_screening": {
        "title": "AI-assisted abstract screening",
        "sections": "Likely Relevant Abstracts, Low-Relevance Abstracts, Missing Metadata, Suggested Review Queue, Human Review Required",
    },
    "query_generation": {
        "title": "AI-assisted external search query generation and refinement",
        "sections": "Suggested Queries, Refinement Rationale, Excluded Unsafe Context, Search Budget Notes, Human Approval Required",
    },
}


def _workspace_ai_payload(workspace: Path, context: dict[str, Any]) -> dict[str, Any]:
    return {
        "safe_context": context,
        "research_questions": {
            "approved": read_yaml(workspace / "research-questions.yaml").get("research_questions", []),
            "candidates": read_yaml(workspace / "research-question-candidates.yaml").get("candidates", []),
        },
        "claims": read_yaml(workspace / "claims-ledger.yaml").get("claims", []),
        "artefacts": read_yaml(workspace / "artefact-registry.yaml").get("artefacts", []),
        "abstract_candidates": read_yaml(workspace / "outputs" / "recommendations" / "abstract-candidates.yaml")
        if (workspace / "outputs" / "recommendations" / "abstract-candidates.yaml").exists()
        else {"candidates": [], "filtered": [], "skipped": []},
    }


def _workspace_report_prompt(kind: str, payload: dict[str, Any]) -> str:
    spec = AI_WORKSPACE_REPORTS[kind]
    return (
        f"You are assisting with {spec['title']} for a local-first, evidence-first research workspace.\n"
        "Use only the supplied safe context and workspace state. Do not claim certainty, do not modify statuses, "
        "and cite source IDs when referring to sources. Return concise markdown with sections: "
        f"{spec['sections']}.\n\n"
        f"Workspace payload JSON:\n{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )


def ai_workspace_report(
    workspace: Path,
    credentials: OpenAiCredentials,
    *,
    kind: str,
    max_sources: int = 10,
    max_excerpt_chars: int = 1200,
    opener: Callable[[Request], Any] | None = None,
) -> dict[str, Any]:
    if kind not in AI_WORKSPACE_REPORTS:
        allowed = ", ".join(sorted(AI_WORKSPACE_REPORTS))
        raise OpenAiError(f"Invalid AI workspace report kind: {kind}. Expected one of: {allowed}")
    context = build_safe_context(workspace, max_sources=max_sources, max_excerpt_chars=max_excerpt_chars)
    payload = _workspace_ai_payload(workspace, context)
    model = default_openai_model(workspace)
    response = openai_post(
        "responses",
        credentials,
        {
            "model": model,
            "input": _workspace_report_prompt(kind, payload),
        },
        opener=opener,
    )
    text = extract_response_text(response)
    return {
        "version": 1,
        "kind": kind,
        "provider": "openai",
        "model": model,
        "ai_used": True,
        "requires_user_review": True,
        "status_changes_applied": False,
        "safe_context_policy": context["policy"],
        "limits": context["limits"],
        "source_count": len(context["sources"]),
        "claim_count": len(payload["claims"]),
        "artefact_count": len(payload["artefacts"]),
        "abstract_candidate_count": len(payload["abstract_candidates"].get("candidates", [])),
        "research_question_count": len(payload["research_questions"]["approved"])
        + len(payload["research_questions"]["candidates"]),
        "response_id": response.get("id") if isinstance(response, dict) else None,
        "report": text,
    }
