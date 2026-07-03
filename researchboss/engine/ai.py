from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from researchboss.core.yamlio import read_yaml


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
