from __future__ import annotations

import platform
from pathlib import Path
from typing import Any, Optional
from xml.etree import ElementTree

from researchboss.core.constants import WORKSPACE_FILES, ensure_workspace_dirs
from researchboss.core.yamlio import write_yaml
from researchboss.engine.zotero import ensure_path_not_in_zotero, zotero_root_from_storage, zotero_sqlite_path


PROJECT_TYPES = ["M.Phil", "PhD", "Other academic research", "Industry research", "Custom"]
SOURCE_MODES = {"local_folder", "zotero_storage", "configure_later"}
ZOTERO_COMMON_CITATION_STYLES = [
    "American Psychological Association 7th edition",
    "American Psychological Association 6th edition",
    "Chicago Manual of Style 17th edition (author-date)",
    "Chicago Manual of Style 17th edition (full note)",
    "Modern Language Association 9th edition",
    "Custom Zotero/CSL style name",
    "IEEE",
    "Vancouver",
    "American Medical Association 11th edition",
    "American Chemical Society",
    "Not sure",
]
DEFAULT_CITATION_STYLE = "American Psychological Association 7th edition"
CITATION_STYLES = ZOTERO_COMMON_CITATION_STYLES
PRIMARY_OUTPUT_TYPES = ["thesis", "paper", "report", "presentation", "notes", "custom"]
DATA_FILE_EXPECTATIONS = ["yes", "no", "not sure"]
AI_PREFERENCES = ["no", "ask me later", "yes but disabled for now"]
SOURCE_REVIEW_DEFAULTS = ["pending_review", "maybe"]
MPHIL_STAGES = [
    "proposal",
    "literature_review",
    "methodology",
    "data_or_sources",
    "analysis",
    "writing",
    "submission",
]
PHD_STAGES = [
    "proposal",
    "confirmation",
    "literature_review",
    "methodology",
    "data_or_sources",
    "analysis",
    "chapter_drafting",
    "review",
    "submission",
]
RQ_TEMPLATES = {
    "M.Phil": [
        "How does [phenomenon] operate within [bounded context]?",
        "What factors shape [outcome] among [population/source set]?",
        "To what extent does [factor] affect [outcome] in [context]?",
    ],
    "PhD": [
        "How does [phenomenon] contribute to [theory/method/problem] within [context]?",
        "What explains [under-researched outcome] across [bounded source set/context]?",
        "In what ways can [method/theory] extend understanding of [research problem]?",
    ],
    "Other academic research": [
        "What is the relationship between [factor] and [outcome] in [context]?",
        "How is [topic] represented or measured across [source set]?",
        "Which factors are associated with [outcome] in [context]?",
    ],
    "Industry research": [
        "What operational factors affect [outcome] for [stakeholder/team]?",
        "How does [process/tool] influence [business/research outcome] in [context]?",
        "Which evidence supports decisions about [problem/opportunity]?",
    ],
    "Custom": [
        "How does [topic] relate to [outcome] in [context]?",
        "What evidence is needed to evaluate [question/problem]?",
        "Which sources or data can answer [question/problem]?",
    ],
}


def default_documents_dir(home: Optional[Path] = None) -> Path:
    return (home or Path.home()) / "Documents"


def zotero_storage_candidates(home: Optional[Path] = None, system: Optional[str] = None) -> list[Path]:
    user_home = home or Path.home()
    os_name = system or platform.system()

    if os_name == "Darwin":
        return [
            user_home / "Zotero" / "storage",
            *sorted((user_home / "Library" / "Application Support" / "Zotero" / "Profiles").glob("*/storage")),
        ]

    if os_name == "Windows":
        app_data = user_home / "AppData" / "Roaming" / "Zotero" / "Profiles"
        return [
            user_home / "Zotero" / "storage",
            user_home / "Documents" / "Zotero" / "storage",
            *sorted(app_data.glob("*/storage")),
        ]

    return []


def find_default_zotero_storage(home: Optional[Path] = None, system: Optional[str] = None) -> Optional[Path]:
    for candidate in zotero_storage_candidates(home=home, system=system):
        if candidate.is_dir():
            return candidate
    return None


def read_csl_style_title(path: Path) -> Optional[str]:
    try:
        root = ElementTree.parse(path).getroot()
    except (ElementTree.ParseError, OSError):
        return None

    namespace = {"csl": "http://purl.org/net/xbiblio/csl"}
    title = root.find("./csl:info/csl:title", namespace)
    if title is None or not title.text:
        title = root.find("./info/title")
    return title.text.strip() if title is not None and title.text else None


def citation_styles_from_zotero_styles_dir(styles_dir: Path) -> list[str]:
    if not styles_dir.is_dir():
        return []

    titles = []
    seen = set()
    for path in sorted(styles_dir.glob("*.csl")):
        title = read_csl_style_title(path)
        if title and title not in seen:
            seen.add(title)
            titles.append(title)
    return titles


def citation_style_choices(styles_dir: Optional[Path] = None) -> list[str]:
    local_styles = citation_styles_from_zotero_styles_dir(styles_dir) if styles_dir else []
    choices = local_styles or list(ZOTERO_COMMON_CITATION_STYLES)
    for required in ("Custom Zotero/CSL style name", "Not sure"):
        if required not in choices:
            choices.append(required)
    return choices


def infer_source_mode(source_answer: str, zotero_storage: Optional[Path] = None) -> str:
    if source_answer in SOURCE_MODES:
        return source_answer

    source_path = Path(source_answer).expanduser()
    if zotero_storage and source_path == zotero_storage.expanduser():
        return "zotero_storage"

    if source_path.name == "storage" and source_path.parent.name == "Zotero":
        return "zotero_storage"

    return "local_folder"


def zotero_config_for_source(source_root: Optional[str], source_mode: str) -> dict[str, Any]:
    if source_mode != "zotero_storage" or not source_root:
        return {
            "root": None,
            "storage": None,
            "database_path": None,
            "mode": "not_configured",
            "selected_collections": [],
            "include_subcollections": True,
            "metadata_source": "local_sqlite",
            "strict_one_way_from_zotero_to_researchboss": True,
            "block_writes_to_zotero_directory": True,
        }

    storage = Path(source_root).expanduser()
    root = zotero_root_from_storage(storage)
    return {
        "root": str(root) if root else None,
        "storage": str(storage),
        "database_path": str(zotero_sqlite_path(root)) if root else None,
        "mode": "entire_library",
        "selected_collections": [],
        "include_subcollections": True,
        "metadata_source": "local_sqlite",
        "strict_one_way_from_zotero_to_researchboss": True,
        "block_writes_to_zotero_directory": True,
    }


def _default_app_settings(ai_preference: str = "no") -> dict[str, Any]:
    return {
        "ai": {
            "enabled": False,
            "setup_preference": ai_preference,
            "default_provider": "openai",
            "providers": {
                "openai": {
                    "enabled": True,
                    "api_key_env": "OPENAI_API_KEY",
                    "default_model": "gpt-4o-mini",
                    "reasoning_model": "gpt-4o",
                    "novelty_model": "gpt-4o",
                },
                "anthropic": {"enabled": False, "api_key_env": "ANTHROPIC_API_KEY", "future_flag": True},
                "local": {"enabled": False, "future_flag": True},
            },
            "feature_flags": {
                "ai_assisted_review": True,
                "novelty_assessment": True,
                "anthropic_provider": False,
                "local_llm_provider": False,
                "external_search": False,
            },
        }
    }


def research_stage_template(project_type: str) -> list[dict[str, Any]]:
    if project_type == "M.Phil":
        names = MPHIL_STAGES
    elif project_type == "PhD":
        names = PHD_STAGES
    else:
        names = []
    return [{"id": f"stage-{index:02d}", "name": name, "status": "not_started"} for index, name in enumerate(names, 1)]


def research_question_templates(project_type: str) -> list[str]:
    return list(RQ_TEMPLATES.get(project_type, RQ_TEMPLATES["Custom"]))


def init_workspace(
    workspace: Path,
    *,
    project_name: str,
    project_type: str,
    topic: str,
    strict_evidence_mode: bool = True,
    source_root: Optional[str] = None,
    source_mode: str = "configure_later",  # local_folder | zotero_storage | configure_later
    artefact_root: Optional[str] = None,
    research_questions: Optional[list[dict[str, Any]]] = None,
    supervisors: Optional[list[str]] = None,
    citation_style: str = DEFAULT_CITATION_STYLE,
    custom_citation_style: Optional[str] = None,
    primary_output_type: str = "notes",
    custom_primary_output_type: Optional[str] = None,
    expects_data_files: str = "not sure",
    source_review_default: str = "pending_review",
    prevent_full_document_uploads: bool = True,
    ai_preference: str = "no",
) -> None:
    zotero_config = zotero_config_for_source(source_root, source_mode)
    if zotero_config.get("block_writes_to_zotero_directory") and zotero_config.get("root"):
        ensure_path_not_in_zotero(workspace, Path(str(zotero_config["root"])))

    workspace.mkdir(parents=True, exist_ok=True)
    ensure_workspace_dirs(workspace)

    # Required YAML/MD files
    write_yaml(
        workspace / WORKSPACE_FILES.research_context,
        {
            "version": 1,
            "project": {
                "name": project_name,
                "type": project_type,
                "topic": topic,
                "strict_evidence_mode": strict_evidence_mode,
                "supervisors_or_stakeholders": supervisors or [],
            },
            "sources": {
                "mode": source_mode,
                "root": source_root,
                "new_source_status": source_review_default,
                "requires_manual_review": source_review_default == "pending_review",
            },
            "zotero": zotero_config,
            "artefacts": {
                "root": artefact_root,
                "primary_output_type": primary_output_type,
                "custom_primary_output_type": custom_primary_output_type,
            },
            "citation": {"style": citation_style, "custom_style": custom_citation_style},
            "guidelines": {
                "default_guideline_ids": [],
                "priority": [],
            },
            "data": {"expects_csv_or_sqlite": expects_data_files},
            "warning_thresholds": {
                "draft_research_questions": 10,
                "maybe_sources": 25,
                "unsupported_claims": 5,
                "failed_conversions": 1,
            },
            "privacy": {
                "local_first": True,
                "do_not_upload_full_documents": prevent_full_document_uploads,
                "no_external_search_mvp": True,
            },
        },
    )

    write_yaml(workspace / WORKSPACE_FILES.research_state, {"version": 1, "current_stage": None, "last_scan_at": None})
    write_yaml(workspace / WORKSPACE_FILES.research_stages, {"version": 1, "stages": research_stage_template(project_type)})

    approved_questions = []
    draft_questions = []
    for index, question in enumerate(research_questions or [], start=1):
        record = {
            "id": f"rq-{index:03d}",
            "question": question["question"],
            "subquestions": question.get("subquestions", []),
        }
        if question.get("status") == "approved":
            approved_questions.append(record)
        else:
            record["status"] = "draft"
            draft_questions.append(record)

    write_yaml(
        workspace / WORKSPACE_FILES.research_questions,
        {"version": 1, "research_questions": approved_questions},
    )
    write_yaml(
        workspace / WORKSPACE_FILES.research_question_candidates,
        {
            "version": 1,
            "templates": {
                "project_type": project_type,
                "items": research_question_templates(project_type),
            },
            "candidates": draft_questions,
        },
    )
    write_yaml(workspace / WORKSPACE_FILES.rejected_research_questions, {"version": 1, "rejected": []})

    write_yaml(workspace / WORKSPACE_FILES.source_register, {"version": 1, "sources": []})
    write_yaml(workspace / WORKSPACE_FILES.accepted_sources, {"version": 1, "source_ids": []})
    write_yaml(workspace / WORKSPACE_FILES.ignored_sources, {"version": 1, "ignored": []})  # keep reason per id
    write_yaml(workspace / WORKSPACE_FILES.maybe_sources, {"version": 1, "source_ids": []})

    write_yaml(workspace / WORKSPACE_FILES.claims_ledger, {"version": 1, "claims": []})
    write_yaml(workspace / WORKSPACE_FILES.novelty_ledger, {"version": 1, "assessments": []})
    write_yaml(workspace / WORKSPACE_FILES.terminology, {"version": 1, "terms": []})
    write_yaml(workspace / WORKSPACE_FILES.supervisor_feedback, {"version": 1, "items": []})
    write_yaml(workspace / WORKSPACE_FILES.artefact_registry, {"version": 1, "artefacts": []})

    (workspace / WORKSPACE_FILES.decisions_md).write_text("# Decisions\n", encoding="utf-8")
    (workspace / WORKSPACE_FILES.memory_md).write_text("# Memory\n", encoding="utf-8")
    (workspace / WORKSPACE_FILES.context_changelog_md).write_text("# Context changelog\n", encoding="utf-8")

    write_yaml(workspace / WORKSPACE_FILES.app_settings_local, _default_app_settings(ai_preference))

    (workspace / WORKSPACE_FILES.gitignore).write_text(
        "\n".join(
            [
                ".env",
                "__pycache__/",
                "*.pyc",
                ".pytest_cache/",
                ".mypy_cache/",
                ".ruff_cache/",
                "dist/",
                "build/",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
