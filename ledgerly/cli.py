from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Optional

import click
import typer
from rich.console import Console
from rich.progress import BarColumn, Progress, TaskProgressColumn, TextColumn, TimeElapsedColumn
from rich.table import Table

from ledgerly.core.runlog import JsonlLogger, RunSummary, make_run_paths, write_run_summary
from ledgerly.core.yamlio import read_yaml, write_yaml
from ledgerly.engine.ai import (
    OpenAiError,
    ai_citation_plan_review,
    ai_assisted_review,
    ai_novelty_assessment,
    ai_research_question_assessment,
    ai_workspace_report,
    build_safe_context,
    openai_credentials,
    openai_readiness,
    require_ai_flag,
    require_directory_ai_opt_in,
    require_full_file_ai_opt_in,
    require_full_source_document_ai_opt_in,
    require_full_target_document_ai_opt_in,
)
from ledgerly.engine.abstracts import import_abstract_folder
from ledgerly.engine.artefact_creation import SUPPORTED_ARTEFACT_TYPES, create_deterministic_artefact
from ledgerly.engine.artefacts import artefact_dependency_report, list_artefacts, register_artefact, set_artefact_review_status
from ledgerly.engine.backup import create_workspace_backup, inspect_backup
from ledgerly.engine.claims import (
    add_claim,
    claim_source_validation_report,
    list_claims,
    set_claim_status,
    write_citation_gap_report,
    write_stale_claims_report,
)
from ledgerly.engine.conversion import convert_sources, extract_text, ocr_readiness_report, processing_issue_report
from ledgerly.engine.citations import apply_citation_plan, create_citation_plan, set_citation_plan_insertion_review_status
from ledgerly.engine.data import data_source_counts, list_data_sources, profile_data_sources
from ledgerly.engine.database import (
    activate_secondary_backend,
    apply_pending_changes,
    database_privacy_report,
    database_status,
    deactivate_secondary_backend,
    init_database,
    rebuild_database,
    repair_secondary_from_sqlite,
    repair_sqlite_from_secondary,
    search_corpus,
    secondary_backend_status,
    sync_database,
    pending_changes_report,
)
from ledgerly.engine.db_backends.base import SecondaryBackendError
from ledgerly.engine.cross_reference import (
    apply_cross_reference_links,
    cross_reference_candidates,
    set_cross_reference_candidate_review_status,
)
from ledgerly.engine.derived_text import build_derived_text_snapshot
from ledgerly.engine.doc_validation import validate_document
from ledgerly.engine.export import build_supervisor_bundle, export_accepted_source_corpus, export_evidence_bundle
from ledgerly.engine.external_search import (
    ExternalSearchError,
    SearchBudgets,
    SearchThresholds,
    auto_refine_plan_path,
    external_candidate_deduplication_report,
    external_candidate_duplicates_path,
    external_candidate_zotero_match_report,
    external_candidate_zotero_matches_path,
    external_evidence_validation_path,
    external_run_comparison_path,
    external_search_evidence_validation_report,
    external_search_run_comparison_report,
    filter_unused_queries,
    generate_auto_refine_plan,
    generate_search_query_plan,
    high_signal_candidate_report_path,
    import_external_candidates,
    require_external_search_flag,
    scopus_credentials,
    scopus_readiness,
    scopus_search,
    write_high_signal_candidate_report,
)
from ledgerly.engine.guidelines import (
    GUIDELINE_SCOPES,
    build_ai_guideline_context,
    guideline_conflict_report,
    list_guidelines,
    register_guideline,
    set_default_guidelines,
)
from ledgerly.engine.health import corpus_dashboard_summary, workspace_health_report
from ledgerly.engine.metadata import extract_citation_metadata
from ledgerly.engine.metadata_quality import (
    build_keyword_index,
    citation_consistency_report,
    duplicate_metadata_report,
    filename_suggestion_report,
)
from ledgerly.engine.migrations import migrate_workspace
from ledgerly.engine.pdf_merge import pdf_merge_report
from ledgerly.engine.notes import add_note, add_note_tag, import_transcript, list_notes, search_notes
from ledgerly.engine.transcription import (
    TranscriptionError,
    get_transcription_job,
    list_transcription_jobs,
    sourcescribe_readiness_report,
    start_transcription,
    upload_transcription_source,
)
from ledgerly.engine.project_log import (
    add_context_change,
    add_decision,
    add_feedback,
    add_terminology,
    list_context_changes,
    list_decisions,
    list_feedback,
    list_terminology,
    timeline_report,
)
from ledgerly.engine.research_questions import (
    QUESTION_TYPES,
    add_research_question_candidate,
    assess_research_question_readiness,
    check_research_question_readiness,
    approve_research_question,
    archive_research_question,
    compose_research_question,
    list_research_questions,
    reject_research_question,
    split_candidate_relations,
)
from ledgerly.engine.progress_log import research_progress_report
from ledgerly.engine.relationships import citation_relationship_map
from ledgerly.engine.report_schemas import export_report_schemas
from ledgerly.engine.reports import generate_workspace_report
from ledgerly.engine.sidecars import import_sidecar_metadata
from ledgerly.engine.vault import (
    compare_document_versions,
    create_document_version,
    diff_document_versions,
    intake_uploaded_artefact,
    list_document_versions,
    list_uploaded_artefacts,
    restore_document_version,
)
from ledgerly.engine.sources import (
    ScanResult,
    iter_source_files,
    list_sources,
    scan_sources,
    set_source_status,
    set_source_note,
    add_source_tag,
    source_review_report,
    source_counts,
    validate_source_provider,
)
from ledgerly.engine.watch import write_watch_report
from ledgerly.engine.zotero import (
    attachment_health_report,
    configured_source_root,
    configured_zotero,
    duplicate_metadata_candidates,
    export_bibtex_from_metadata,
    fulltext_availability_report,
    ensure_path_not_in_zotero,
    keyword_terms,
    list_zotero_collections,
    metadata_quality_report,
    resolve_zotero_paths,
    search_zotero_storage,
    storage_keys_for_collections,
    write_zotero_config,
    zotero_metadata_snapshot,
    zotero_readiness_report,
    zotero_root_from_storage,
)
from ledgerly.engine.zotero_api import (
    ZoteroApiError,
    clear_zotero_api_credentials,
    save_zotero_api_credentials,
    zotero_api_collections,
    zotero_api_credentials,
    zotero_api_readiness,
)
from ledgerly import __version__
from ledgerly.engine.workspace import (
    AI_PREFERENCES,
    DATA_FILE_EXPECTATIONS,
    PRIMARY_OUTPUT_TYPES,
    PROJECT_TYPES,
    SOURCE_REVIEW_DEFAULTS,
    DEFAULT_CITATION_STYLE,
    citation_style_choices,
    default_documents_dir,
    find_default_zotero_storage,
    infer_source_mode,
    init_workspace,
)

app = typer.Typer(add_completion=False, help="Ledgerly (Phase 1 foundation).")
sources_app = typer.Typer(help="Source inbox + register commands.")
config_app = typer.Typer(help="Config commands.")
zotero_app = typer.Typer(help="Read-only local Zotero storage commands.")
metadata_app = typer.Typer(help="Deterministic metadata commands.")
data_app = typer.Typer(help="Local data source commands.")
rqs_app = typer.Typer(help="Research question workflow commands.")
artefacts_app = typer.Typer(help="Artefact registry commands.")
claims_app = typer.Typer(help="Claim ledger commands.")
decisions_app = typer.Typer(help="Decision log commands.")
terminology_app = typer.Typer(help="Terminology glossary commands.")
feedback_app = typer.Typer(help="Supervisor/stakeholder feedback commands.")
context_app = typer.Typer(help="Context changelog commands.")
ai_app = typer.Typer(help="Optional OpenAI commands.")
search_app = typer.Typer(help="Explicit opt-in external search commands.")
guidelines_app = typer.Typer(help="Local guideline registration commands.")
cite_app = typer.Typer(help="Citation planning commands.")
abstracts_app = typer.Typer(help="Local abstract import and screening commands.")
db_app = typer.Typer(help="Workspace SQLite index and memory commands.")
doc_app = typer.Typer(help="Document vault version, diff, and restore commands.")
notes_app = typer.Typer(help="Personal notes, meeting notes, and transcript commands.")
paper_app = typer.Typer(help="Deterministic paper-draft skeleton commands.")
transcribe_app = typer.Typer(help="Audio/video transcription via SourceScribe (subprocess).")

app.add_typer(sources_app, name="sources")
app.add_typer(config_app, name="config")
app.add_typer(zotero_app, name="zotero")
app.add_typer(metadata_app, name="metadata")
app.add_typer(data_app, name="data")
app.add_typer(rqs_app, name="rqs")
app.add_typer(artefacts_app, name="artefacts")
app.add_typer(claims_app, name="claims")
app.add_typer(decisions_app, name="decisions")
app.add_typer(terminology_app, name="terminology")
app.add_typer(feedback_app, name="feedback")
app.add_typer(context_app, name="context")
app.add_typer(notes_app, name="notes")
app.add_typer(ai_app, name="ai")
app.add_typer(search_app, name="search")
app.add_typer(guidelines_app, name="guidelines")
app.add_typer(cite_app, name="cite")
app.add_typer(abstracts_app, name="abstracts")
app.add_typer(db_app, name="db")
app.add_typer(doc_app, name="doc")
app.add_typer(paper_app, name="paper")
app.add_typer(transcribe_app, name="transcribe")

console = Console()
DEFAULT_WORKSPACES_DIR = "workspaces"
CLI_DEFAULTS_FILE = ".ledgerly-cli.local.yaml"
MIN_PYTHON = (3, 11)
REQUIRED_RUNTIME_MODULES = ["click", "typer", "rich", "pydantic", "yaml", "fastapi", "uvicorn", "python_multipart", "jinja2"]


def _runtime_check_errors() -> list[str]:
    errors: list[str] = []
    if sys.version_info < MIN_PYTHON:
        errors.append(
            "Python 3.11 or newer is required "
            f"(running {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro})."
        )

    for module_name in REQUIRED_RUNTIME_MODULES:
        try:
            importlib.import_module(module_name)
        except ImportError:
            errors.append(f"Missing required Python package: {module_name}")

    return errors


def _ensure_runtime_ready() -> None:
    errors = _runtime_check_errors()
    if not errors:
        return

    console.print("[red]Ledgerly is not ready to run.[/red]")
    for error in errors:
        console.print(f"- {error}")
    console.print("\nInstall the project before running commands:")
    console.print('  [bold]python -m pip install -e ".[dev]"[/bold]')
    raise typer.Exit(code=2)


def _resolve_workspace(workspace: Optional[Path]) -> Path:
    if workspace is not None:
        return workspace

    candidates = _discover_workspaces(Path.cwd())
    if not candidates:
        console.print("[red]No Ledgerly workspaces found.[/red]")
        console.print("Pass --workspace, run from a workspace folder, or create one with `ledgerly init`.")
        raise typer.Exit(code=2)

    if len(candidates) == 1:
        return candidates[0]

    return _prompt_workspace_selection(candidates)


def _is_workspace(path: Path) -> bool:
    return (path / "research-context.yaml").is_file() and (path / "source-register.yaml").is_file()


def _workspace_search_root(cwd: Path) -> Path:
    if (cwd / DEFAULT_WORKSPACES_DIR).is_dir():
        return cwd
    if cwd.parent.name == DEFAULT_WORKSPACES_DIR:
        return cwd.parent.parent
    return cwd


def _cli_defaults_path(cwd: Path) -> Path:
    root = _workspace_search_root(cwd)
    workspaces_dir = root / DEFAULT_WORKSPACES_DIR
    if workspaces_dir.exists():
        return workspaces_dir / CLI_DEFAULTS_FILE
    return root / CLI_DEFAULTS_FILE


def _discover_workspaces(cwd: Path) -> list[Path]:
    candidates: list[Path] = []
    if _is_workspace(cwd):
        candidates.append(cwd)

    root = _workspace_search_root(cwd)
    workspaces_dir = root / DEFAULT_WORKSPACES_DIR
    if workspaces_dir.is_dir():
        for child in sorted(workspaces_dir.iterdir()):
            if child.is_dir() and _is_workspace(child):
                candidates.append(child)

    unique: list[Path] = []
    seen: set[Path] = set()
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved not in seen:
            unique.append(candidate)
            seen.add(resolved)
    return unique


def _read_default_workspace(cwd: Path, candidates: list[Path]) -> Optional[Path]:
    defaults_path = _cli_defaults_path(cwd)
    if not defaults_path.exists():
        return None

    data = read_yaml(defaults_path)
    configured = data.get("default_workspace")
    if not configured:
        return None

    configured_path = Path(configured).expanduser()
    for candidate in candidates:
        if candidate.resolve() == configured_path.resolve():
            return candidate
    return None


def _write_default_workspace(cwd: Path, workspace: Path) -> None:
    write_yaml(_cli_defaults_path(cwd), {"version": 1, "default_workspace": str(workspace)})


def _prompt_workspace_selection(candidates: list[Path]) -> Path:
    default_workspace = _read_default_workspace(Path.cwd(), candidates)
    default_index = candidates.index(default_workspace) + 1 if default_workspace in candidates else 1

    console.print("Select workspace")
    for index, candidate in enumerate(candidates, start=1):
        suffix = " (default)" if candidate == default_workspace else ""
        console.print(f"{index}. {candidate}{suffix}")

    valid_choices = {str(index) for index in range(1, len(candidates) + 1)}
    while True:
        selected = typer.prompt("Enter number", default=str(default_index)).strip()
        if selected in valid_choices:
            workspace = candidates[int(selected) - 1]
            break
        console.print(f"Please enter a number from 1 to {len(candidates)}.")

    if default_workspace is None and typer.confirm("Use this workspace as the default for future commands?", default=True):
        _write_default_workspace(Path.cwd(), workspace)

    return workspace


def _command_slug(parts: list[str]) -> str:
    return "__".join(parts).replace("-", "_")


def _workspace_slug(project_name: str) -> str:
    return "".join(ch if ch.isalnum() or ch in ("-", "_") else "-" for ch in project_name).strip("-") or "workspace"


def _default_workspace_path(project_name: str) -> Path:
    return Path.cwd() / DEFAULT_WORKSPACES_DIR / _workspace_slug(project_name)


def _prompt_numbered_choice(title: str, choices: list[str], *, default_index: int = 1) -> str:
    console.print(title)
    for index, label in enumerate(choices, start=1):
        console.print(f"{index}. {label}")
    valid_choices = {str(index) for index in range(1, len(choices) + 1)}
    while True:
        selected = typer.prompt("Enter number", default=str(default_index)).strip()
        if selected in valid_choices:
            return choices[int(selected) - 1]
        console.print(f"Please enter a number from 1 to {len(choices)}.")


def _prompt_research_questions() -> list[dict[str, object]]:
    console.print(
        "Research questions are optional, but adding them now helps Ledgerly keep useful context for later processing."
    )
    if not typer.confirm("Add research questions now?", default=False):
        return []

    questions: list[dict[str, object]] = []
    while True:
        question = typer.prompt("Research question", default="").strip()
        if not question:
            break

        status = _prompt_numbered_choice("Research question status", ["Draft", "Approved"], default_index=1)
        subquestions = []
        if typer.confirm("Add optional subquestions for this research question?", default=False):
            while True:
                subquestion = typer.prompt("Subquestion (leave blank to finish)", default="").strip()
                if not subquestion:
                    break
                subquestions.append(subquestion)

        questions.append(
            {
                "question": question,
                "status": "approved" if status == "Approved" else "draft",
                "subquestions": subquestions,
            }
        )

        if not typer.confirm("Add another research question?", default=False):
            break

    return questions


def _prompt_optional_list(intro: str, item_prompt: str) -> list[str]:
    if not typer.confirm(intro, default=False):
        return []

    items: list[str] = []
    while True:
        item = typer.prompt(item_prompt, default="").strip()
        if not item:
            break
        items.append(item)
        if not typer.confirm("Add another?", default=False):
            break
    return items


def _prompt_setup_preferences() -> dict[str, object]:
    supervisors = _prompt_optional_list(
        "Record supervisor or stakeholder names for local context?",
        "Supervisor or stakeholder name",
    )
    citation_styles = citation_style_choices()
    citation_style = _prompt_numbered_choice(
        "Preferred citation style",
        citation_styles,
        default_index=citation_styles.index(DEFAULT_CITATION_STYLE) + 1
        if DEFAULT_CITATION_STYLE in citation_styles
        else 1,
    )
    custom_citation_style = None
    if citation_style == "Custom Zotero/CSL style name":
        custom_citation_style = typer.prompt("Custom Zotero/CSL style name", default="").strip() or None

    primary_output_type = _prompt_numbered_choice("Primary output type", PRIMARY_OUTPUT_TYPES, default_index=1)
    custom_primary_output_type = None
    if primary_output_type == "custom":
        custom_primary_output_type = typer.prompt("Custom primary output type", default="").strip() or None

    expects_data_files = _prompt_numbered_choice(
        "Will this project include CSV or SQLite data files?",
        DATA_FILE_EXPECTATIONS,
        default_index=3,
    )
    source_review_default = _prompt_numbered_choice(
        "Default status for newly scanned sources",
        SOURCE_REVIEW_DEFAULTS,
        default_index=1,
    )
    ai_preference = _prompt_numbered_choice(
        "Optional AI features preference (AI remains disabled during init)",
        AI_PREFERENCES,
        default_index=1,
    )

    return {
        "supervisors": supervisors,
        "citation_style": citation_style,
        "custom_citation_style": custom_citation_style,
        "primary_output_type": primary_output_type,
        "custom_primary_output_type": custom_primary_output_type,
        "expects_data_files": expects_data_files,
        "source_review_default": source_review_default,
        "ai_preference": ai_preference,
    }


def _run_ctx(command_parts: list[str], workspace: Path, log_level: str):
    slug = _command_slug(command_parts)
    log_path, summary_path = make_run_paths(workspace, slug)
    logger = JsonlLogger(log_path, command=slug, workspace=workspace, level=log_level)
    summary = RunSummary(command=" ".join(command_parts), workspace=str(workspace))
    summary.start_clock()
    return slug, logger, summary, summary_path, log_path


def _finish(summary: RunSummary, summary_path: Path, *, next_action: Optional[str] = None) -> None:
    summary.complete(next_action=next_action)
    write_run_summary(summary_path, summary)


def _print_ai_review_footer(report: dict, review_required_message: str) -> None:
    """Print the right footer for an `engine.ai` report: "insufficient evidence"
    (Core Rule item 3: a required, valid, successful output, printed plainly,
    not as an error) is a materially different outcome from "AI generated
    something, go review it" and must never be described with the same
    "human review is required" phrasing — nothing was generated to review.
    """
    if report.get("insufficient_evidence"):
        console.print(f"[yellow]Insufficient evidence.[/yellow] {report['insufficient_evidence_reason']}")
    else:
        console.print(f"[yellow]{review_required_message}[/yellow]")



def _zotero_filtered_candidates(storage_root: Path, zotero_root: Optional[Path], zotero_config: dict) -> list[Path]:
    candidates = list(iter_source_files(storage_root))
    if not zotero_root:
        return candidates
    if zotero_config.get("mode") != "selected_collections":
        return candidates

    selected = zotero_config.get("selected_collections") or []
    keys = [item.get("key") for item in selected if isinstance(item, dict) and item.get("key")]
    if not keys:
        return candidates

    allowed_keys = storage_keys_for_collections(
        zotero_root,
        keys,
        include_subcollections=bool(zotero_config.get("include_subcollections", True)),
    )
    return [path for path in candidates if path.parent.name in allowed_keys]


def _print_init_next_steps(workspace: Path, source_root: Optional[str]) -> None:
    console.print(f"[green]Workspace created:[/green] {workspace}")
    console.print("\n[bold]Useful next commands[/bold]")
    console.print(f"Validate the workspace:\n  [bold]ledgerly config validate --workspace {workspace}[/bold]")

    if source_root:
        console.print(
            "Scan your configured sources:\n"
            f"  [bold]ledgerly scan --workspace {workspace} --source {source_root}[/bold]"
        )
    else:
        console.print(
            "Scan a source folder when you are ready:\n"
            f"  [bold]ledgerly scan --workspace {workspace} --source /path/to/your/sources[/bold]"
        )

    console.print(f"Review pending sources:\n  [bold]ledgerly sources review --workspace {workspace}[/bold]")
    console.print(f"Show source counts:\n  [bold]ledgerly sources status --workspace {workspace}[/bold]")
    console.print(
        f"List accepted sources:\n  [bold]ledgerly sources list --workspace {workspace} --status accepted[/bold]"
    )


@app.command()
def version():
    """Show the installed Ledgerly version."""
    console.print(f"Ledgerly {__version__}")


@app.command()
def doctor():
    """Check that Ledgerly runtime requirements are available."""
    errors = _runtime_check_errors()
    if errors:
        console.print("[red]Ledgerly runtime check failed.[/red]")
        for error in errors:
            console.print(f"- {error}")
        console.print('\nRun [bold]python -m pip install -e ".[dev]"[/bold] and try again.')
        raise typer.Exit(code=2)

    console.print(f"[green]OK[/green] Ledgerly {__version__} is ready.")


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", "--host", help="Bind host. Use 0.0.0.0 only behind a reverse proxy/auth layer."),
    port: int = typer.Option(8000, "--port", help="Bind port."),
    reload: bool = typer.Option(False, "--reload", help="Auto-reload on source changes (development only)."),
):
    """Run the local Ledgerly FastAPI app with uvicorn."""
    import uvicorn

    uvicorn.run("ledgerly.api.app:app", host=host, port=port, reload=reload)


@app.command()
def init(
    path: Optional[Path] = typer.Argument(None, help="Workspace folder to create (default: ./<project-name>)"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Create a new Ledgerly workspace (bare minimum wizard)."""
    _ensure_runtime_ready()
    project_name = typer.prompt("Project name")
    project_type = _prompt_numbered_choice("Research level / project type", PROJECT_TYPES)
    topic = typer.prompt("Research topic / short description", default="")
    research_questions = _prompt_research_questions()
    setup_preferences = _prompt_setup_preferences()
    default_zotero_storage = find_default_zotero_storage()
    source_answer = typer.prompt(
        "Where are your source files?",
        default=str(default_zotero_storage) if default_zotero_storage else "configure_later",
    )
    source_mode = infer_source_mode(source_answer, default_zotero_storage)
    source_root = None
    if source_answer in ("local_folder", "zotero_storage"):
        source_root = typer.prompt("Source root folder path", default="")
    elif source_mode in ("local_folder", "zotero_storage"):
        source_root = source_answer

    artefact_root = typer.prompt("Destination / artefact root (optional)", default=str(default_documents_dir()))
    strict = typer.confirm("Enable strict evidence mode?", default=True)
    prevent_uploads = typer.confirm(
        "Prevent workflows that upload full documents or datasets?",
        default=True,
    )

    workspace = path or _default_workspace_path(project_name)
    if path is None:
        console.print(f"Workspace will be created at: {workspace}")
        if not typer.confirm("Continue with this workspace path?", default=True):
            raise typer.Abort()

    # init needs a workspace for logs; we log into the new workspace.
    workspace.mkdir(parents=True, exist_ok=True)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["init"], workspace, log_level)

    try:
        init_workspace(
            workspace,
            project_name=project_name,
            project_type=project_type,
            topic=topic,
            strict_evidence_mode=strict,
            source_root=source_root or None,
            source_mode=source_mode,
            artefact_root=artefact_root or None,
            research_questions=research_questions,
            prevent_full_document_uploads=prevent_uploads,
            **setup_preferences,
        )
        logger.info("Workspace created", operation="init", workspace=str(workspace))
        _finish(summary, summary_path, next_action=f"Run `ledgerly scan --workspace {workspace}`")
    except Exception as e:
        logger.error("Init failed", operation="init", error=str(e))
        summary.errors += 1
        _finish(summary, summary_path, next_action="Fix the error and rerun init")
        raise

    if not quiet:
        _print_init_next_steps(workspace, source_root)


@app.command()
def status(
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Workspace path (default: CWD)"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Show workspace status summary (Phase 1: source counts)."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["status"], ws, log_level)

    try:
        counts = source_counts(ws)
        logger.info("Computed status", operation="status", counts=counts)
        _finish(summary, summary_path, next_action="Use `ledgerly sources list` to inspect sources.")
    except Exception as e:
        logger.error("Status failed", operation="status", error=str(e))
        summary.errors += 1
        _finish(summary, summary_path)
        raise

    if quiet:
        return

    table = Table(title="Ledgerly Status (sources)")
    table.add_column("Status")
    table.add_column("Count", justify="right")
    for k in sorted(counts.keys()):
        table.add_row(k, str(counts[k]))
    console.print(table)


@app.command("compare-workspaces")
def compare_workspaces(
    workspaces: list[Path] = typer.Argument(..., help="Two or more workspace paths to compare side by side."),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Compare source/claim/artefact/RQ counts and last-activity across two or more workspaces."""
    if len(workspaces) < 2:
        console.print("[red]Provide at least two workspace paths to compare.[/red]")
        raise typer.Exit(code=2)
    resolved = [_resolve_workspace(ws) for ws in workspaces]
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["compare-workspaces"], resolved[0], log_level)

    rows = []
    for ws in resolved:
        context = read_yaml(ws / "research-context.yaml") if (ws / "research-context.yaml").exists() else {}
        summary_data = corpus_dashboard_summary(ws)
        rows.append({"workspace": ws, "project_name": context.get("project", {}).get("name"), **summary_data})
    logger.info("Compared workspaces", operation="compare_workspaces", count=len(rows))
    _finish(summary, summary_path)
    if quiet:
        return

    table = Table(title="Workspace Comparison")
    table.add_column("Workspace")
    table.add_column("Sources", justify="right")
    table.add_column("Claims", justify="right")
    table.add_column("Artefacts", justify="right")
    table.add_column("Open RQs", justify="right")
    table.add_column("Last activity", justify="right")
    for row in rows:
        label = row["project_name"] or str(row["workspace"])
        last_activity = (
            "no activity yet" if row["days_since_last_activity"] is None else f"{row['days_since_last_activity']}d ago"
        )
        table.add_row(
            label,
            str(row["source_counts"].get("total", 0)),
            str(row["claim_counts"].get("total", 0)),
            str(row["artefact_count"]),
            str(row["open_research_question_count"]),
            last_activity,
        )
    console.print(table)


@app.command()
def validate(
    target: str = typer.Argument(..., help="Document target: path, artefact ID/title, alias, or artefact type."),
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Workspace path."),
    source_path: list[Path] = typer.Option(
        [],
        "--source-path",
        help="Additional source document path to compare against. Can be repeated.",
    ),
    guideline_ids: list[str] = typer.Option(
        [],
        "--guidelines",
        help="Guideline ID to apply. Can be repeated. Explicit IDs override default guidelines.",
    ),
    no_default_guidelines: bool = typer.Option(
        False,
        "--no-default-guidelines",
        help="Do not apply workspace default guidelines.",
    ),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Validate a document deterministically against accepted and explicitly supplied sources."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["validate"], ws, log_level)

    try:
        result = validate_document(
            ws,
            target,
            source_paths=source_path,
            guideline_ids=guideline_ids,
            use_default_guidelines=not no_default_guidelines,
            cwd=Path.cwd(),
        )
        logger.info(
            "Document validation report written",
            operation="validate",
            target=target,
            yaml_path=str(result.yaml_path),
            markdown_path=str(result.markdown_path),
        )
        _finish(summary, summary_path, next_action=f"Review `{result.markdown_path}`")
    except Exception as e:
        logger.error("Document validation failed", operation="validate", target=target, error=str(e))
        summary.errors += 1
        _finish(summary, summary_path, next_action="Fix the target or source paths and rerun validation.")
        raise

    if quiet:
        return

    report_summary = result.report["summary"]
    console.print(f"[green]Validation report:[/green] {result.markdown_path}")
    console.print(f"YAML report: {result.yaml_path}")
    console.print(
        "Compared "
        f"{report_summary['source_count']} sources; "
        f"{report_summary['sources_with_overlap']} had deterministic term overlap."
    )


@cite_app.command("plan")
def cite_plan(
    target: str = typer.Argument(..., help="Document target: path, artefact ID/title, alias, or artefact type."),
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Workspace path."),
    source_path: list[Path] = typer.Option(
        [],
        "--source-path",
        help="Additional source document path to compare against. Can be repeated.",
    ),
    guideline_ids: list[str] = typer.Option(
        [],
        "--guidelines",
        help="Guideline ID to apply. Can be repeated. Explicit IDs override default guidelines.",
    ),
    no_default_guidelines: bool = typer.Option(
        False,
        "--no-default-guidelines",
        help="Do not apply workspace default guidelines.",
    ),
    allow_candidate_citations: bool = typer.Option(
        False,
        "--allow-candidate-citations",
        help="Allow citation suggestions from explicit or not-yet-accepted sources.",
    ),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Create a reviewable citation insertion plan without editing the target document."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["cite", "plan"], ws, log_level)

    try:
        result = create_citation_plan(
            ws,
            target,
            source_paths=source_path,
            guideline_ids=guideline_ids,
            use_default_guidelines=not no_default_guidelines,
            allow_candidate_citations=allow_candidate_citations,
            cwd=Path.cwd(),
        )
        logger.info(
            "Citation plan written",
            operation="cite_plan",
            target=target,
            yaml_path=str(result.yaml_path),
            markdown_path=str(result.markdown_path),
            insertion_count=len(result.plan.get("insertions", [])),
        )
        _finish(summary, summary_path, next_action=f"Review `{result.markdown_path}`")
    except Exception as e:
        logger.error("Citation plan failed", operation="cite_plan", target=target, error=str(e))
        summary.errors += 1
        _finish(summary, summary_path)
        raise

    if not quiet:
        console.print(f"[green]Citation plan:[/green] {result.markdown_path}")
        console.print(f"YAML plan: {result.yaml_path}")
        console.print(f"Proposed insertions: {len(result.plan.get('insertions', []))}")


@cite_app.command("ai-plan")
def cite_ai_plan(
    target: str = typer.Argument(..., help="Document target: path, artefact ID/title, alias, or artefact type."),
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Workspace path."),
    ai: bool = typer.Option(False, "--ai", help="Required explicit opt-in for OpenAI citation planning."),
    full_target_document_ai: bool = typer.Option(
        False,
        "--full-target-document-ai",
        help="Explicitly allow sending the whole target document text to the AI provider.",
    ),
    source_path: list[Path] = typer.Option(
        [],
        "--source-path",
        help="Additional source document path to compare against. Can be repeated.",
    ),
    allow_candidate_citations: bool = typer.Option(
        False,
        "--allow-candidate-citations",
        help="Allow citation suggestions from explicit or not-yet-accepted sources.",
    ),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Create an AI-assisted citation insertion plan for review without editing the target document."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["cite", "ai_plan"], ws, log_level)
    try:
        require_full_target_document_ai_opt_in(ai=ai, full_target_document=full_target_document_ai)
        deterministic = create_citation_plan(
            ws,
            target,
            source_paths=source_path,
            allow_candidate_citations=allow_candidate_citations,
            cwd=Path.cwd(),
        )
        target_path = Path(str(deterministic.plan["target"]["path"]))
        target_text = extract_text(target_path)
        ai_review = ai_citation_plan_review(
            ws,
            openai_credentials(ws),
            target_text=target_text,
            citation_plan=deterministic.plan,
        )
        plan = {
            **deterministic.plan,
            "ai_used": True,
            "ai_assistance": ai_review,
            "full_target_document_ai_opt_in": True,
            "original_document_modified": False,
            "plan_status": "ai_review_required",
        }
        write_yaml(deterministic.yaml_path, plan)
        deterministic.markdown_path.write_text(
            deterministic.markdown_path.read_text(encoding="utf-8")
            + "\n## AI Recommendations\n\n"
            + str(ai_review.get("recommendations") or "No recommendations returned.")
            + "\n",
            encoding="utf-8",
        )
    except (OpenAiError, Exception) as e:
        logger.error("AI citation plan failed", operation="cite_ai_plan", target=target, error=str(e))
        summary.errors += 1
        _finish(summary, summary_path)
        if not quiet:
            console.print(f"[red]{e}[/red]")
        raise typer.Exit(code=2)

    logger.info(
        "AI citation plan written",
        operation="cite_ai_plan",
        target=target,
        yaml_path=str(deterministic.yaml_path),
        markdown_path=str(deterministic.markdown_path),
    )
    _finish(summary, summary_path, next_action=f"Review `{deterministic.markdown_path}`")
    if not quiet:
        console.print(f"[green]AI citation plan:[/green] {deterministic.markdown_path}")
        console.print("[yellow]Original document was not modified. Human review is required.[/yellow]")


@cite_app.command("review")
def cite_review(
    target: str = typer.Argument(..., help="Same document target used for `cite plan`."),
    sentence_index: int = typer.Argument(...),
    source_id: str = typer.Argument(...),
    review_status: str = typer.Argument(..., help="needs_human_review|accepted|approved|rejected"),
    plan_path: Optional[Path] = typer.Option(None, "--plan", help="Optional citation plan YAML path."),
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Workspace path."),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Set one citation-plan insertion's review_status without hand-editing the plan file."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["cite", "review"], ws, log_level)

    try:
        insertion = set_citation_plan_insertion_review_status(
            ws, target, sentence_index, source_id, review_status, plan_path=plan_path, cwd=Path.cwd()
        )
        logger.info(
            "Citation plan insertion review status updated",
            operation="cite_review",
            target=target,
            sentence_index=sentence_index,
            source_id=source_id,
            review_status=review_status,
        )
        _finish(summary, summary_path)
    except Exception as e:
        logger.error(
            "Citation plan insertion review update failed",
            operation="cite_review",
            target=target,
            sentence_index=sentence_index,
            source_id=source_id,
            error=str(e),
        )
        summary.errors += 1
        _finish(summary, summary_path)
        raise

    if not quiet:
        console.print(f"[green]Updated:[/green] sentence {insertion['sentence_index']}/{insertion['source_id']} -> {insertion['review_status']}")


@cite_app.command("apply")
def cite_apply(
    target: str = typer.Argument(..., help="Document target whose reviewed citation plan should be applied."),
    plan_path: Optional[Path] = typer.Option(None, "--plan", help="Optional citation plan YAML path."),
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Workspace path."),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Apply accepted citation-plan insertions to a revised output copy."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["cite", "apply"], ws, log_level)

    try:
        result = apply_citation_plan(ws, target, plan_path=plan_path, cwd=Path.cwd())
        logger.info(
            "Citation plan applied",
            operation="cite_apply",
            target=target,
            output_path=str(result.output_path),
            report_path=str(result.report_path),
            applied=result.applied,
            skipped=result.skipped,
        )
        _finish(summary, summary_path, next_action=f"Review `{result.output_path}`")
    except Exception as e:
        logger.error("Citation apply failed", operation="cite_apply", target=target, error=str(e))
        summary.errors += 1
        _finish(summary, summary_path)
        raise

    if not quiet:
        console.print(f"[green]Revised citation copy:[/green] {result.output_path}")
        console.print(f"Applied insertions: {result.applied}")
        console.print(f"Skipped insertions: {result.skipped}")
        console.print(f"Document vault version: {result.version_id}")


@config_app.command("validate")
def config_validate(
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Workspace path (default: CWD)"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Validate basic workspace presence and YAML readability."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["config", "validate"], ws, log_level)

    required = ["research-context.yaml", "source-register.yaml", "outputs/logs"]
    missing = [p for p in required if not (ws / p).exists()]
    if missing:
        msg = f"Missing required workspace paths: {missing}"
        logger.error(msg, operation="config_validate")
        summary.errors += 1
        _finish(summary, summary_path, next_action="Run `ledgerly init` or fix the workspace path.")
        if not quiet:
            console.print(f"[red]{msg}[/red]")
        raise typer.Exit(code=2)

    # YAML parse checks
    try:
        _ = read_yaml(ws / "research-context.yaml")
        _ = read_yaml(ws / "source-register.yaml")
        logger.info("Workspace config validated", operation="config_validate")
        _finish(summary, summary_path)
    except Exception as e:
        logger.error("YAML validation failed", operation="config_validate", error=str(e))
        summary.errors += 1
        _finish(summary, summary_path)
        raise

    if not quiet:
        console.print(f"[green]OK[/green] Workspace looks valid: {ws}")


@config_app.command("migrate")
def config_migrate(
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Workspace path (default: CWD)"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Fill missing workspace config fields for the current schema."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["config", "migrate"], ws, log_level)
    changes = migrate_workspace(ws)
    logger.info("Migrated workspace config", operation="config_migrate", changes=changes)
    _finish(summary, summary_path)
    if not quiet:
        console.print(f"[green]Migration complete[/green] changes={len(changes)}")


@guidelines_app.command("add")
def guidelines_add(
    source: str = typer.Argument(..., help="Local guideline file path or http(s) URL."),
    title: Optional[str] = typer.Option(None, "--title", help="Optional guideline title."),
    scope: list[str] = typer.Option(
        ["all_purpose"],
        "--scope",
        help=f"Guideline scope. Can be repeated. Allowed: {', '.join(sorted(GUIDELINE_SCOPES))}.",
    ),
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Workspace path."),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Register a guideline source by snapshotting and extracting text inside the workspace."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["guidelines", "add"], ws, log_level)

    try:
        result = register_guideline(ws, source, title=title, scopes=scope)
        logger.info(
            "Registered guideline",
            operation="guidelines_add",
            guideline_id=result.record["id"],
            source=source,
            snapshot_path=str(result.snapshot_path),
            text_path=str(result.text_path),
        )
        _finish(summary, summary_path, next_action="Use `ledgerly guidelines list` to review registered guidelines.")
    except Exception as e:
        logger.error("Guideline registration failed", operation="guidelines_add", source=source, error=str(e))
        summary.errors += 1
        _finish(summary, summary_path)
        raise

    if not quiet:
        console.print(f"[green]Guideline registered:[/green] {result.record['id']}")
        console.print(f"Snapshot: {result.snapshot_path}")
        console.print(f"Text: {result.text_path}")


@guidelines_app.command("list")
def guidelines_list(
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Workspace path."),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """List registered guidelines."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["guidelines", "list"], ws, log_level)
    rows = list_guidelines(ws)
    logger.info("Listed guidelines", operation="guidelines_list", count=len(rows))
    _finish(summary, summary_path)

    if quiet:
        return

    table = Table(title="Guidelines")
    table.add_column("id")
    table.add_column("title")
    table.add_column("kind")
    table.add_column("scopes")
    table.add_column("text_path")
    for row in rows:
        table.add_row(
            str(row.get("id")),
            str(row.get("title")),
            str(row.get("source_kind")),
            ", ".join(row.get("scopes") or []),
            str(row.get("text_path")),
        )
    console.print(table)


@guidelines_app.command("defaults")
def guidelines_defaults(
    guideline_id: list[str] = typer.Argument(..., help="Guideline IDs in default priority order."),
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Workspace path."),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Set workspace default guidelines and precedence order."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["guidelines", "defaults"], ws, log_level)

    try:
        config = set_default_guidelines(ws, list(guideline_id))
        logger.info(
            "Set default guidelines",
            operation="guidelines_defaults",
            default_guideline_ids=config.get("default_guideline_ids") or [],
        )
        _finish(summary, summary_path, next_action="Run `ledgerly validate <target>` to apply default guidelines.")
    except Exception as e:
        logger.error("Default guideline update failed", operation="guidelines_defaults", error=str(e))
        summary.errors += 1
        _finish(summary, summary_path)
        raise

    if not quiet:
        console.print("[green]Default guidelines updated[/green]")
        console.print(", ".join(config.get("default_guideline_ids") or []) or "None")


@guidelines_app.command("conflicts")
def guidelines_conflicts(
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Workspace path."),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Write deterministic guideline conflict checks for human review."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["guidelines", "conflicts"], ws, log_level)
    report = guideline_conflict_report(ws)
    output_path = ws / "outputs" / "validation" / "guideline-conflicts.yaml"
    logger.info(
        "Wrote guideline conflict report",
        operation="guidelines_conflicts",
        conflict_count=report["conflict_count"],
        output_path=str(output_path),
    )
    _finish(summary, summary_path, next_action=f"Review `{output_path}`")

    if not quiet:
        console.print(f"[green]Guideline conflict report:[/green] {output_path}")
        console.print(f"Conflicts requiring review: {report['conflict_count']}")


@guidelines_app.command("ai-context")
def guidelines_ai_context(
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Workspace path."),
    ai: bool = typer.Option(False, "--ai", help="Required explicit opt-in for AI guideline context preparation."),
    full_guidelines_ai: bool = typer.Option(False, "--full-guidelines-ai", help="Explicitly include full converted guideline text."),
    max_excerpt_chars: int = typer.Option(1200, "--max-excerpt-chars", help="Maximum guideline excerpt length when full text is not opted in."),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Write safe AI guideline context using excerpts unless full guidelines are explicitly opted in."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["guidelines", "ai_context"], ws, log_level)
    try:
        require_ai_flag(ai)
        if full_guidelines_ai and not ai:
            raise OpenAiError("Pass --ai with --full-guidelines-ai.")
        context = build_ai_guideline_context(ws, full_guidelines=full_guidelines_ai, max_excerpt_chars=max_excerpt_chars)
    except OpenAiError as e:
        logger.error("AI guideline context failed", operation="guidelines_ai_context", error=str(e))
        summary.errors += 1
        _finish(summary, summary_path)
        if not quiet:
            console.print(f"[red]{e}[/red]")
        raise typer.Exit(code=2)
    output_path = ws / "outputs" / "validation" / "ai-guideline-context.yaml"
    logger.info(
        "Wrote AI guideline context",
        operation="guidelines_ai_context",
        guideline_count=context["guideline_count"],
        full_guidelines_included=context["full_guidelines_included"],
    )
    _finish(summary, summary_path)
    if not quiet:
        console.print(f"[green]Wrote[/green] {output_path}")


@ai_app.command("test")
def ai_test(
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Workspace path (default: CWD)"),
    ai: bool = typer.Option(False, "--ai", help="Allow a live OpenAI credential check for this command."),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Check OpenAI readiness without printing the API key."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["ai", "test"], ws, log_level)
    try:
        credentials = openai_credentials(ws)
        report = openai_readiness(ws, credentials, live=ai)
    except OpenAiError as e:
        logger.error("OpenAI readiness check failed", operation="ai_test", error=str(e))
        summary.errors += 1
        _finish(summary, summary_path)
        if not quiet:
            console.print(f"[red]{e}[/red]")
        raise typer.Exit(code=2)

    output_path = ws / "outputs" / "validation" / "openai-test.yaml"
    write_yaml(output_path, report)
    logger.info(
        "Checked OpenAI readiness",
        operation="ai_test",
        key_loaded=report["key_loaded"],
        live_request_performed=report["live_request_performed"],
        workspace_ai_enabled=report["workspace_ai_enabled"],
    )
    _finish(summary, summary_path)
    if not quiet:
        console.print(f"[green]Wrote[/green] {output_path}")
        if not ai:
            console.print("No live OpenAI request was made. Pass --ai to explicitly allow a live credential check.")


@ai_app.command("context-preview")
def ai_context_preview(
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Workspace path (default: CWD)"),
    ai: bool = typer.Option(False, "--ai", help="Required explicit opt-in for AI-context preparation."),
    full_file_ai: bool = typer.Option(False, "--full-file-ai", help="Explicitly allow whole-file AI context in future full-file commands."),
    directory_ai: bool = typer.Option(False, "--directory-ai", help="Explicitly allow folder-level AI context in future directory commands."),
    max_sources: int = typer.Option(10, "--max-sources", help="Maximum accepted sources to include."),
    max_excerpt_chars: int = typer.Option(1200, "--max-excerpt-chars", help="Maximum converted-text excerpt characters per source."),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Write a safe AI context preview without uploading anything."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["ai", "context_preview"], ws, log_level)
    try:
        if full_file_ai:
            require_full_file_ai_opt_in(ai=ai, full_file=full_file_ai)
        if directory_ai:
            require_directory_ai_opt_in(ai=ai, directory=directory_ai)
        if not full_file_ai and not directory_ai:
            require_ai_flag(ai)
        context = build_safe_context(ws, max_sources=max_sources, max_excerpt_chars=max_excerpt_chars)
        context["full_file_ai_opt_in"] = full_file_ai
        context["directory_ai_opt_in"] = directory_ai
        context["warnings"] = [
            "Safe context preview still excludes original full files and directories.",
            "Whole-file or directory AI use requires explicit per-run opt-in flags on commands that support it.",
        ]
    except OpenAiError as e:
        logger.error("AI context preview failed", operation="ai_context_preview", error=str(e))
        summary.errors += 1
        _finish(summary, summary_path)
        if not quiet:
            console.print(f"[red]{e}[/red]")
        raise typer.Exit(code=2)

    output_path = ws / "outputs" / "validation" / "openai-safe-context.yaml"
    write_yaml(output_path, context)
    logger.info(
        "Built safe AI context preview",
        operation="ai_context_preview",
        source_count=len(context["sources"]),
        max_excerpt_chars=max_excerpt_chars,
    )
    _finish(summary, summary_path)
    if not quiet:
        console.print(f"[green]Wrote[/green] {output_path}")
        console.print("No OpenAI request was made.")


@ai_app.command("review")
def ai_review(
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Workspace path (default: CWD)"),
    ai: bool = typer.Option(False, "--ai", help="Required explicit opt-in for OpenAI review."),
    max_sources: int = typer.Option(10, "--max-sources", help="Maximum accepted sources to include."),
    max_excerpt_chars: int = typer.Option(1200, "--max-excerpt-chars", help="Maximum converted-text excerpt characters per source."),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Run an AI-assisted source/corpus review from safe context only."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["ai", "review"], ws, log_level)
    try:
        require_ai_flag(ai)
        credentials = openai_credentials(ws)
        report = ai_assisted_review(
            ws,
            credentials,
            max_sources=max_sources,
            max_excerpt_chars=max_excerpt_chars,
        )
    except OpenAiError as e:
        logger.error("AI-assisted review failed", operation="ai_review", error=str(e))
        summary.errors += 1
        _finish(summary, summary_path)
        if not quiet:
            console.print(f"[red]{e}[/red]")
        raise typer.Exit(code=2)

    output_path = ws / "outputs" / "validation" / "openai-review.yaml"
    write_yaml(output_path, report)
    logger.info(
        "Wrote AI-assisted review",
        operation="ai_review",
        source_count=report["source_count"],
        model=report["model"],
    )
    _finish(summary, summary_path)
    if not quiet:
        console.print(f"[green]Wrote[/green] {output_path}")
        _print_ai_review_footer(report, "Human review is required before using this output.")


def _run_ai_workspace_report(
    *,
    workspace: Optional[Path],
    ai: bool,
    kind: str,
    output_name: str,
    max_sources: int,
    max_excerpt_chars: int,
    log_level: str,
    quiet: bool,
) -> None:
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["ai", kind], ws, log_level)
    try:
        require_ai_flag(ai)
        report = ai_workspace_report(
            ws,
            openai_credentials(ws),
            kind=kind,
            max_sources=max_sources,
            max_excerpt_chars=max_excerpt_chars,
        )
    except OpenAiError as e:
        logger.error("AI workspace report failed", operation=f"ai_{kind}", error=str(e))
        summary.errors += 1
        _finish(summary, summary_path)
        if not quiet:
            console.print(f"[red]{e}[/red]")
        raise typer.Exit(code=2)
    output_path = ws / "outputs" / "validation" / output_name
    write_yaml(output_path, report)
    logger.info("Wrote AI workspace report", operation=f"ai_{kind}", kind=kind, source_count=report["source_count"])
    _finish(summary, summary_path)
    if not quiet:
        console.print(f"[green]Wrote[/green] {output_path}")
        _print_ai_review_footer(report, "Human review is required before using this output.")


@ai_app.command("corpus-summary")
def ai_corpus_summary(
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Workspace path (default: CWD)"),
    ai: bool = typer.Option(False, "--ai", help="Required explicit opt-in for OpenAI corpus summary."),
    max_sources: int = typer.Option(10, "--max-sources", help="Maximum accepted sources to include."),
    max_excerpt_chars: int = typer.Option(1200, "--max-excerpt-chars", help="Maximum converted-text excerpt characters per source."),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Generate an AI corpus summary from safe context only."""
    _run_ai_workspace_report(
        workspace=workspace,
        ai=ai,
        kind="corpus_summary",
        output_name="openai-corpus-summary.yaml",
        max_sources=max_sources,
        max_excerpt_chars=max_excerpt_chars,
        log_level=log_level,
        quiet=quiet,
    )


@ai_app.command("claim-check")
def ai_claim_check(
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Workspace path (default: CWD)"),
    ai: bool = typer.Option(False, "--ai", help="Required explicit opt-in for OpenAI claim-check assistance."),
    max_sources: int = typer.Option(10, "--max-sources", help="Maximum accepted sources to include."),
    max_excerpt_chars: int = typer.Option(1200, "--max-excerpt-chars", help="Maximum converted-text excerpt characters per source."),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Generate AI claim-checking assistance without changing claim statuses."""
    _run_ai_workspace_report(
        workspace=workspace,
        ai=ai,
        kind="claim_checking",
        output_name="openai-claim-checking.yaml",
        max_sources=max_sources,
        max_excerpt_chars=max_excerpt_chars,
        log_level=log_level,
        quiet=quiet,
    )


@ai_app.command("citation-gaps")
def ai_citation_gaps(
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Workspace path (default: CWD)"),
    ai: bool = typer.Option(False, "--ai", help="Required explicit opt-in for OpenAI citation-gap recommendations."),
    max_sources: int = typer.Option(10, "--max-sources", help="Maximum accepted sources to include."),
    max_excerpt_chars: int = typer.Option(1200, "--max-excerpt-chars", help="Maximum converted-text excerpt characters per source."),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Generate AI citation-gap recommendations from safe context only."""
    _run_ai_workspace_report(
        workspace=workspace,
        ai=ai,
        kind="citation_gaps",
        output_name="openai-citation-gaps.yaml",
        max_sources=max_sources,
        max_excerpt_chars=max_excerpt_chars,
        log_level=log_level,
        quiet=quiet,
    )


@ai_app.command("artefact-cross-reference")
def ai_artefact_cross_reference(
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Workspace path (default: CWD)"),
    ai: bool = typer.Option(False, "--ai", help="Required explicit opt-in for OpenAI artefact cross-reference."),
    max_sources: int = typer.Option(10, "--max-sources", help="Maximum accepted sources to include."),
    max_excerpt_chars: int = typer.Option(1200, "--max-excerpt-chars", help="Maximum converted-text excerpt characters per source."),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Generate AI artefact cross-reference review from registry metadata and safe context."""
    _run_ai_workspace_report(
        workspace=workspace,
        ai=ai,
        kind="artefact_cross_reference",
        output_name="openai-artefact-cross-reference.yaml",
        max_sources=max_sources,
        max_excerpt_chars=max_excerpt_chars,
        log_level=log_level,
        quiet=quiet,
    )


@ai_app.command("source-relevance")
def ai_source_relevance(
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Workspace path (default: CWD)"),
    ai: bool = typer.Option(False, "--ai", help="Required explicit opt-in for OpenAI source relevance recommendations."),
    max_sources: int = typer.Option(10, "--max-sources", help="Maximum accepted sources to include."),
    max_excerpt_chars: int = typer.Option(1200, "--max-excerpt-chars", help="Maximum converted-text excerpt characters per source."),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Generate AI source relevance recommendations without changing source statuses."""
    _run_ai_workspace_report(
        workspace=workspace,
        ai=ai,
        kind="source_relevance",
        output_name="openai-source-relevance.yaml",
        max_sources=max_sources,
        max_excerpt_chars=max_excerpt_chars,
        log_level=log_level,
        quiet=quiet,
    )


@ai_app.command("abstract-screening")
def ai_abstract_screening(
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Workspace path (default: CWD)"),
    ai: bool = typer.Option(False, "--ai", help="Required explicit opt-in for OpenAI abstract screening."),
    max_sources: int = typer.Option(10, "--max-sources", help="Maximum accepted sources to include."),
    max_excerpt_chars: int = typer.Option(1200, "--max-excerpt-chars", help="Maximum converted-text excerpt characters per source."),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Generate AI abstract-screening recommendations without changing abstract statuses."""
    _run_ai_workspace_report(
        workspace=workspace,
        ai=ai,
        kind="abstract_screening",
        output_name="openai-abstract-screening.yaml",
        max_sources=max_sources,
        max_excerpt_chars=max_excerpt_chars,
        log_level=log_level,
        quiet=quiet,
    )


@search_app.command("plan")
def search_plan(
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Workspace path (default: CWD)"),
    max_queries: int = typer.Option(20, "--max-queries", help="Maximum query combinations to generate."),
    strategy: str = typer.Option("balanced", "--strategy", help="Query generation strategy: broad|balanced|strict."),
    params_file: Optional[Path] = typer.Option(None, "--params-file", help="Legacy params file to import into the query plan."),
    unused_only: bool = typer.Option(False, "--unused-only", help="Show only queries not present in query history."),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Generate deterministic external-search query plans without calling external APIs."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["search", "plan"], ws, log_level)
    try:
        plan = generate_search_query_plan(ws, max_queries=max_queries, strategy=strategy, params_file=params_file)
    except ExternalSearchError as e:
        logger.error("External search query planning failed", operation="search_plan", error=str(e))
        summary.errors += 1
        _finish(summary, summary_path)
        if not quiet:
            console.print(f"[red]{e}[/red]")
        raise typer.Exit(code=2)
    queries = filter_unused_queries(ws, plan["queries"]) if unused_only else plan["queries"]
    logger.info("Generated external search query plan", operation="search_plan", query_count=len(queries))
    _finish(summary, summary_path)
    if quiet:
        return
    table = Table(title="External search query plan")
    table.add_column("#", justify="right")
    table.add_column("query")
    table.add_column("group")
    table.add_column("source")
    records_by_query = {record["query"]: record for record in plan.get("query_records", []) if isinstance(record, dict)}
    for index, query in enumerate(queries, start=1):
        record = records_by_query.get(query, {})
        table.add_row(str(index), query, str(record.get("group_label") or ""), str(record.get("source") or ""))
    console.print(table)


@search_app.command("ai-query-plan")
def search_ai_query_plan(
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Workspace path (default: CWD)"),
    ai: bool = typer.Option(False, "--ai", help="Required explicit opt-in for OpenAI query assistance."),
    external_search: bool = typer.Option(False, "--external-search", help="Required explicit opt-in for external-search planning."),
    max_sources: int = typer.Option(10, "--max-sources", help="Maximum accepted sources to include in safe context."),
    max_excerpt_chars: int = typer.Option(1200, "--max-excerpt-chars", help="Maximum converted-text excerpt characters per source."),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Generate AI-assisted external-search query suggestions without executing them."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["search", "ai_query_plan"], ws, log_level)
    try:
        require_ai_flag(ai)
        require_external_search_flag(external_search)
        report = ai_workspace_report(
            ws,
            openai_credentials(ws),
            kind="query_generation",
            max_sources=max_sources,
            max_excerpt_chars=max_excerpt_chars,
        )
    except (OpenAiError, ExternalSearchError) as e:
        logger.error("AI query plan failed", operation="search_ai_query_plan", error=str(e))
        summary.errors += 1
        _finish(summary, summary_path)
        if not quiet:
            console.print(f"[red]{e}[/red]")
        raise typer.Exit(code=2)
    output_path = ws / "outputs" / "recommendations" / "openai-external-query-plan.yaml"
    write_yaml(output_path, report)
    logger.info("Wrote AI external query plan", operation="search_ai_query_plan", source_count=report["source_count"])
    _finish(summary, summary_path, next_action=f"Review `{output_path}` before running any external search.")
    if not quiet:
        console.print(f"[green]Wrote[/green] {output_path}")
        console.print("[yellow]No external search was executed. Human approval is required.[/yellow]")


@search_app.command("ai-candidate-review")
def search_ai_candidate_review(
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Workspace path (default: CWD)"),
    ai: bool = typer.Option(False, "--ai", help="Required explicit opt-in for OpenAI candidate review."),
    external_search: bool = typer.Option(False, "--external-search", help="Required explicit opt-in for external candidate review."),
    full_source_document_ai: bool = typer.Option(
        False,
        "--full-source-document-ai",
        help="Explicitly allow future full-source-document AI review. Default uses candidate metadata and abstracts only.",
    ),
    max_sources: int = typer.Option(10, "--max-sources", help="Maximum accepted sources to include in safe context."),
    max_excerpt_chars: int = typer.Option(1200, "--max-excerpt-chars", help="Maximum converted-text excerpt characters per source."),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Generate AI candidate relevance and novelty review from metadata and abstracts first."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["search", "ai_candidate_review"], ws, log_level)
    try:
        require_ai_flag(ai)
        require_external_search_flag(external_search)
        if full_source_document_ai:
            require_full_source_document_ai_opt_in(ai=ai, full_source_document=full_source_document_ai)
        report = ai_workspace_report(
            ws,
            openai_credentials(ws),
            kind="candidate_validation",
            max_sources=max_sources,
            max_excerpt_chars=max_excerpt_chars,
        )
        report["full_source_document_ai_opt_in"] = full_source_document_ai
        report["full_text_mode"] = "explicit_opt_in" if full_source_document_ai else "metadata_and_abstracts_only"
    except (OpenAiError, ExternalSearchError) as e:
        logger.error("AI candidate review failed", operation="search_ai_candidate_review", error=str(e))
        summary.errors += 1
        _finish(summary, summary_path)
        if not quiet:
            console.print(f"[red]{e}[/red]")
        raise typer.Exit(code=2)
    output_path = ws / "outputs" / "validation" / "openai-candidate-validation.yaml"
    write_yaml(output_path, report)
    logger.info("Wrote AI candidate validation", operation="search_ai_candidate_review", source_count=report["source_count"])
    _finish(summary, summary_path, next_action=f"Review `{output_path}` before accepting candidate papers.")
    if not quiet:
        console.print(f"[green]Wrote[/green] {output_path}")
        console.print("[yellow]Candidate status changes were not applied.[/yellow]")


@search_app.command("refine-plan")
def search_refine_plan(
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Workspace path (default: CWD)"),
    max_queries: int = typer.Option(20, "--max-queries", help="Maximum follow-up queries to save."),
    max_refinement_rounds: int = typer.Option(1, "--max-refinement-rounds", help="Maximum deterministic refinement rounds to plan."),
    max_results_per_query: int = typer.Option(25, "--max-results-per-query", help="Planned result budget per follow-up query."),
    max_result_pages: int = typer.Option(20, "--max-result-pages", help="Maximum result pages allowed in the saved plan."),
    max_results: int = typer.Option(500, "--max-results", help="Maximum total result records allowed in the saved plan."),
    max_elapsed_seconds: int = typer.Option(300, "--max-elapsed-seconds", help="Maximum planning runtime budget in seconds."),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Save deterministic broader follow-up queries for no-result or low-result searches."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["search", "refine_plan"], ws, log_level)
    budgets = SearchBudgets.from_options(
        max_api_calls=0,
        max_generated_queries=max_queries,
        max_refinement_rounds=max_refinement_rounds,
        max_result_pages=max_result_pages,
        max_result_count=max_results,
        max_elapsed_seconds=max_elapsed_seconds,
    )
    plan = generate_auto_refine_plan(
        ws,
        budgets=budgets,
        max_queries=max_queries,
        max_refinement_rounds=max_refinement_rounds,
        max_results_per_query=max_results_per_query,
    )
    logger.info("Generated external search refine plan", operation="search_refine_plan", query_count=plan["query_count"])
    _finish(summary, summary_path)
    if quiet:
        return
    console.print(f"[green]Wrote[/green] {auto_refine_plan_path(ws)}")
    table = Table(title="External search refine plan")
    table.add_column("#", justify="right")
    table.add_column("query")
    table.add_column("source issue")
    for index, record in enumerate(plan.get("query_records", []), start=1):
        table.add_row(str(index), str(record.get("query") or ""), str(record.get("source_issue") or ""))
    console.print(table)


@search_app.command("reports")
def search_reports(
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Workspace path (default: CWD)"),
    limit: int = typer.Option(50, "--limit", help="Maximum high-signal candidates to include."),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Regenerate deterministic external-search reports from local candidate registers."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["search", "reports"], ws, log_level)
    high_signal = write_high_signal_candidate_report(ws, limit=limit)
    duplicates = external_candidate_deduplication_report(ws)
    zotero_matches = external_candidate_zotero_match_report(ws)
    evidence = external_search_evidence_validation_report(ws)
    comparison = external_search_run_comparison_report(ws)
    logger.info(
        "Generated external search reports",
        operation="search_reports",
        high_signal_candidates=high_signal["reported_count"],
        duplicate_groups=duplicates["duplicate_group_count"],
        zotero_matched_candidates=zotero_matches["matched_candidate_count"],
        evidence_candidates=evidence["candidate_count"],
        run_count=len(comparison["runs"]),
    )
    _finish(summary, summary_path)
    if quiet:
        return
    console.print(f"[green]Wrote[/green] {high_signal_candidate_report_path(ws)}")
    console.print(f"[green]Wrote[/green] {external_candidate_duplicates_path(ws)}")
    console.print(f"[green]Wrote[/green] {external_candidate_zotero_matches_path(ws)}")
    console.print(f"[green]Wrote[/green] {external_evidence_validation_path(ws)}")
    console.print(f"[green]Wrote[/green] {external_run_comparison_path(ws)}")


@search_app.command("import-candidates")
def search_import_candidates(
    candidate_id: list[str] = typer.Option(
        [],
        "--candidate-id",
        help="External candidate ID to import as a metadata-only pending-review source. Can be repeated.",
    ),
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Workspace path (default: CWD)"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Import reviewed external candidates into the source register as pending-review metadata-only sources."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["search", "import_candidates"], ws, log_level)
    try:
        report = import_external_candidates(ws, candidate_id)
    except ExternalSearchError as e:
        logger.error("External candidate import failed", operation="search_import_candidates", error=str(e))
        summary.errors += 1
        _finish(summary, summary_path)
        if not quiet:
            console.print(f"[red]{e}[/red]")
        raise typer.Exit(code=2)

    logger.info(
        "Imported external candidates",
        operation="search_import_candidates",
        imported_count=report["imported_count"],
        skipped_count=report["skipped_count"],
        missing_count=report["missing_count"],
    )
    _finish(summary, summary_path, next_action="Run `ledgerly sources list` and review imported metadata-only sources.")
    if not quiet:
        console.print(f"[green]Imported[/green] {report['imported_count']} candidate source(s)")
        console.print(f"Skipped: {report['skipped_count']} Missing: {report['missing_count']}")


@abstracts_app.command("import")
def abstracts_import(
    folder: Path = typer.Argument(..., help="Local folder containing legacy abstract text files."),
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Workspace path (default: CWD)"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Import local abstract text files into a reviewable candidate register."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["abstracts", "import"], ws, log_level)
    result = import_abstract_folder(ws, folder)
    summary.files_processed = result.processed
    summary.files_succeeded = result.candidate
    summary.files_skipped = result.filtered + result.skipped
    logger.info(
        "Imported abstract folder",
        operation="abstracts_import",
        processed=result.processed,
        candidate=result.candidate,
        filtered=result.filtered,
        skipped=result.skipped,
    )
    _finish(summary, summary_path, next_action=f"Review `{result.register_path}`")
    if not quiet:
        console.print(
            f"[green]Abstract import complete[/green] processed={result.processed} "
            f"candidate={result.candidate} filtered={result.filtered} skipped={result.skipped}"
        )


@search_app.command("scopus-test")
def search_scopus_test(
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Workspace path (default: CWD)"),
    external_search: bool = typer.Option(False, "--external-search", help="Required explicit opt-in for live Scopus API access."),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Test Scopus credentials without printing keys."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["search", "scopus_test"], ws, log_level)
    try:
        require_external_search_flag(external_search)
        report = scopus_readiness(scopus_credentials(ws))
    except ExternalSearchError as e:
        logger.error("Scopus readiness failed", operation="search_scopus_test", error=str(e))
        summary.errors += 1
        _finish(summary, summary_path)
        if not quiet:
            console.print(f"[red]{e}[/red]")
        raise typer.Exit(code=2)
    output_path = ws / "outputs" / "validation" / "scopus-test.yaml"
    write_yaml(output_path, report)
    logger.info("Tested Scopus credentials", operation="search_scopus_test", key_loaded=report["key_loaded"])
    _finish(summary, summary_path)
    if not quiet:
        console.print(f"[green]Wrote[/green] {output_path}")


@search_app.command("scopus")
def search_scopus(
    query: str = typer.Argument(..., help="Scopus query to run."),
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Workspace path (default: CWD)"),
    external_search: bool = typer.Option(False, "--external-search", help="Required explicit opt-in for live Scopus API access."),
    count: int = typer.Option(25, "--count", help="Maximum Scopus results to request."),
    min_citations: int = typer.Option(0, "--min-citations", help="Minimum citation count for candidate-register inclusion."),
    year_from: Optional[int] = typer.Option(None, "--year-from", help="Earliest publication year for candidate-register inclusion."),
    year_to: Optional[int] = typer.Option(None, "--year-to", help="Latest publication year for candidate-register inclusion."),
    open_access_only: bool = typer.Option(False, "--open-access-only", help="Only include Scopus results marked open access in the candidate register."),
    low_result_threshold: int = typer.Option(3, "--low-result-threshold", help="Log query as low-result when processed results are at or below this count."),
    max_api_calls: int = typer.Option(1, "--max-api-calls", help="Maximum API calls allowed for this run."),
    max_generated_queries: int = typer.Option(0, "--max-generated-queries", help="Maximum generated queries allowed for this run."),
    max_refinement_rounds: int = typer.Option(0, "--max-refinement-rounds", help="Maximum refinement rounds allowed for this run."),
    max_result_pages: int = typer.Option(1, "--max-result-pages", help="Maximum result pages allowed for this run."),
    max_results: int = typer.Option(200, "--max-results", help="Maximum result records allowed for this run."),
    max_elapsed_seconds: int = typer.Option(300, "--max-elapsed-seconds", help="Maximum elapsed-time budget in seconds."),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Run an explicit Scopus search and save a local response snapshot."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["search", "scopus"], ws, log_level)
    try:
        require_external_search_flag(external_search)
        thresholds = SearchThresholds.from_options(
            min_citations=min_citations,
            year_from=year_from,
            year_to=year_to,
            open_access_only=open_access_only,
            max_results_per_query=count,
            low_result_threshold=low_result_threshold,
        )
        budgets = SearchBudgets.from_options(
            max_api_calls=max_api_calls,
            max_generated_queries=max_generated_queries,
            max_refinement_rounds=max_refinement_rounds,
            max_result_pages=max_result_pages,
            max_result_count=max_results,
            max_elapsed_seconds=max_elapsed_seconds,
        )
        report = scopus_search(ws, scopus_credentials(ws), query=query, count=count, thresholds=thresholds, budgets=budgets)
    except ExternalSearchError as e:
        logger.error("Scopus search failed", operation="search_scopus", error=str(e))
        summary.errors += 1
        _finish(summary, summary_path)
        if not quiet:
            console.print(f"[red]{e}[/red]")
        raise typer.Exit(code=2)
    logger.info(
        "Ran Scopus search",
        operation="search_scopus",
        processed=report["metrics"]["processed"],
        candidate_count=report["metrics"]["candidate_count"],
    )
    _finish(summary, summary_path)
    if not quiet:
        console.print(f"[green]Wrote[/green] {report['snapshot_path']}")
        console.print(f"[green]Wrote[/green] {report['metrics']['candidate_register_path']}")
        console.print(f"[green]Wrote[/green] {report['metrics']['query_validation_path']}")
        console.print(f"[green]Wrote[/green] {report['metrics']['batch_summary_path']}")
        console.print(f"[green]Wrote[/green] {report['metrics']['filtered_candidate_log_path']}")
        console.print(f"[green]Wrote[/green] {report['metrics']['high_signal_report_path']}")
        console.print(f"[green]Wrote[/green] {report['metrics']['candidate_duplicates_path']}")
        console.print(f"[green]Wrote[/green] {report['metrics']['evidence_validation_path']}")
        console.print(f"[green]Wrote[/green] {report['metrics']['run_comparison_path']}")


@app.command("assess-novelty")
def assess_novelty(
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Workspace path (default: CWD)"),
    ai: bool = typer.Option(False, "--ai", help="Required explicit opt-in for OpenAI novelty assessment."),
    max_sources: int = typer.Option(10, "--max-sources", help="Maximum accepted sources to include."),
    max_excerpt_chars: int = typer.Option(1200, "--max-excerpt-chars", help="Maximum converted-text excerpt characters per source."),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Run AI-assisted novelty assessment from safe context only."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["assess_novelty"], ws, log_level)
    try:
        require_ai_flag(ai)
        credentials = openai_credentials(ws)
        report = ai_novelty_assessment(
            ws,
            credentials,
            max_sources=max_sources,
            max_excerpt_chars=max_excerpt_chars,
        )
    except OpenAiError as e:
        logger.error("AI novelty assessment failed", operation="assess_novelty", error=str(e))
        summary.errors += 1
        _finish(summary, summary_path)
        if not quiet:
            console.print(f"[red]{e}[/red]")
        raise typer.Exit(code=2)

    output_path = ws / "outputs" / "novelty" / "openai-novelty-assessment.yaml"
    write_yaml(output_path, report)
    logger.info(
        "Wrote AI-assisted novelty assessment",
        operation="assess_novelty",
        source_count=report["source_count"],
        research_question_count=report["research_question_count"],
        model=report["model"],
    )
    _finish(summary, summary_path)
    if not quiet:
        console.print(f"[green]Wrote[/green] {output_path}")
        _print_ai_review_footer(report, "Novelty is not proven. Human review and field-specific checks are required.")


@app.command()
def scan(
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Workspace path (default: CWD)"),
    source: Optional[Path] = typer.Option(None, "--source", "-s", help="Source root to scan (overrides config)"),
    kind: Optional[str] = typer.Option(None, "--kind", help="local_folder | zotero_storage"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Scan local folder or Zotero storage folder and register new sources as pending_review."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["scan"], ws, log_level)

    cfg_root, source_mode, source_config = configured_source_root(ws)
    initial_status = source_config.get("new_source_status", "pending_review")
    provider = kind or (source_mode if source_mode in {"local_folder", "zotero_storage"} else "local_folder")
    validate_source_provider(provider)
    scan_root = source or cfg_root
    if not scan_root:
        logger.error("No source root configured or provided", operation="scan")
        summary.errors += 1
        _finish(summary, summary_path, next_action="Set sources.root in research-context.yaml or pass --source")
        raise typer.Exit(code=2)

    if not scan_root.exists():
        logger.error("Source root does not exist", source_root=str(scan_root))
        summary.errors += 1
        _finish(summary, summary_path, next_action="Fix the path and rerun scan")
        raise typer.Exit(code=2)

    zotero_config = configured_zotero(ws)
    zotero_root = Path(zotero_config["root"]) if provider == "zotero_storage" and zotero_config.get("root") else None
    if provider == "zotero_storage":
        candidates = _zotero_filtered_candidates(scan_root, zotero_root, zotero_config)
    else:
        candidates = list(iter_source_files(scan_root))
    total = max(1, len(candidates))  # safe zero handling

    if not quiet:
        console.print(f"Scanning: {scan_root}  (kind={provider})")
        console.print(f"Candidate files: {len(candidates)}")

    progress = Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        disable=quiet,
    )

    task_id = progress.add_task("Hashing + registering...", total=total)

    with progress:
        # We do the real scan via engine scan (which walks + hashes allowed files).
        # We still advance the bar for rough UX.
        # Phase 1: keep simple.
        for _ in candidates:
            progress.advance(task_id, 1)

        result: ScanResult = scan_sources(
            ws,
            scan_root,
            provider=provider,
            logger=logger,
            file_paths=candidates,
            initial_status=initial_status,
            zotero_root=zotero_root,
        )

    summary.files_processed = result.processed
    summary.files_succeeded = result.added
    summary.files_skipped = result.skipped
    summary.warnings += 0
    _finish(summary, summary_path, next_action="Run `ledgerly sources review` to accept/ignore/maybe.")

    if not quiet:
        console.print(
            f"[green]Scan complete[/green] processed={result.processed} added={result.added} "
            f"duplicates={result.duplicates} skipped={result.skipped}"
        )


@app.command()
def report(
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Workspace path (default: CWD)"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Generate a local Markdown workspace report."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["report"], ws, log_level)
    output_path = generate_workspace_report(ws)
    logger.info("Generated workspace report", operation="report", output_path=str(output_path))
    _finish(summary, summary_path)
    if not quiet:
        console.print(f"[green]Wrote[/green] {output_path}")


@app.command("report-schemas")
def report_schemas(
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Workspace path (default: CWD)"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Write report schema and human-review guideline documentation."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["report_schemas"], ws, log_level)
    result = export_report_schemas(ws)
    logger.info(
        "Generated report schemas",
        operation="report_schemas",
        yaml_path=str(result.yaml_path),
        markdown_path=str(result.markdown_path),
        schema_count=result.schema_count,
    )
    _finish(summary, summary_path, next_action=f"Review `{result.markdown_path}`")
    if not quiet:
        console.print(f"[green]Wrote[/green] {result.markdown_path}")
        console.print(f"YAML schemas: {result.yaml_path}")


@app.command()
def watch(
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Workspace path (default: CWD)"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Detect unregistered files in the configured source folder."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["watch"], ws, log_level)
    output_path = write_watch_report(ws)
    report_data = read_yaml(output_path)
    logger.info("Wrote watch candidate report", operation="watch", output_path=str(output_path))
    _finish(summary, summary_path, next_action="Run `ledgerly scan` to register new candidate files.")
    if not quiet:
        console.print(f"[green]Wrote[/green] {output_path}")
        console.print(f"candidate_count={report_data.get('candidate_count', 0)}")


@app.command()
def backup(
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Workspace path (default: CWD)"),
    include_originals: bool = typer.Option(False, "--include-originals", help="Include sources_original in the zip."),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Create a local zip backup of workspace state."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["backup"], ws, log_level)
    output_path = create_workspace_backup(ws, include_originals=include_originals)
    logger.info("Created workspace backup", operation="backup", output_path=str(output_path))
    _finish(summary, summary_path)
    if not quiet:
        console.print(f"[green]Wrote[/green] {output_path}")


@app.command("backup-inspect")
def backup_inspect(
    backup_path: Path = typer.Argument(..., help="Backup zip path to inspect without restoring."),
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Workspace path for run logs."),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Inspect a backup zip without restoring or writing its contents."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["backup", "inspect"], ws, log_level)
    report = inspect_backup(backup_path)
    output_path = ws / "outputs" / "validation" / "backup-inspect.yaml"
    write_yaml(output_path, report)
    logger.info("Inspected backup", operation="backup_inspect", output_path=str(output_path))
    _finish(summary, summary_path)
    if not quiet:
        console.print(f"[green]Wrote[/green] {output_path}")
        console.print(f"files={report['file_count']} dry_run={report['dry_run']}")


@app.command("health")
def health(
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Workspace path (default: CWD)"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Run deterministic local workspace health checks."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["health"], ws, log_level)
    report = workspace_health_report(ws)
    logger.info("Wrote workspace health report", operation="health", status=report["status"])
    _finish(summary, summary_path)
    if not quiet:
        console.print(f"[green]Health[/green] {report['status']}")
        console.print(f"Wrote {ws / 'outputs' / 'validation' / 'workspace-health.yaml'}")


@app.command("export-evidence")
def export_evidence(
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Workspace path (default: CWD)"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Export a local evidence bundle without original source files."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["export", "evidence"], ws, log_level)
    output_path = export_evidence_bundle(ws)
    logger.info("Exported evidence bundle", operation="export_evidence", output_path=str(output_path))
    _finish(summary, summary_path)
    if not quiet:
        console.print(f"[green]Wrote[/green] {output_path}")


@app.command("export-supervisor-bundle")
def export_supervisor_bundle_cmd(
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Workspace path (default: CWD)"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Export a single 'hand this to my supervisor' bundle: claim ledger, citation plans, and the workspace review report."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["export", "supervisor-bundle"], ws, log_level)
    output_path = build_supervisor_bundle(ws)
    logger.info("Exported supervisor bundle", operation="export_supervisor_bundle", output_path=str(output_path))
    _finish(summary, summary_path)
    if not quiet:
        console.print(f"[green]Wrote[/green] {output_path}")


@app.command("export-corpus")
def export_corpus(
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Workspace path (default: CWD)"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Export accepted converted source text as a combined local corpus with a manifest."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["export", "corpus"], ws, log_level)
    result = export_accepted_source_corpus(ws)
    logger.info(
        "Exported accepted source corpus",
        operation="export_corpus",
        corpus_path=str(result.corpus_path),
        manifest_path=str(result.manifest_path),
        included_count=result.included_count,
        skipped_count=result.skipped_count,
    )
    _finish(summary, summary_path, next_action=f"Review `{result.manifest_path}`")
    if not quiet:
        console.print(f"[green]Wrote[/green] {result.corpus_path}")
        console.print(f"Manifest: {result.manifest_path}")


@app.command("merge-pdfs")
def merge_pdfs(
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Workspace path (default: CWD)"),
    write: bool = typer.Option(False, "--write", help="Write the merged PDF artefact. Default writes manifest reports only."),
    output: Optional[Path] = typer.Option(None, "--output", help="Optional merged PDF output path."),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Create accepted-source PDF merge manifests and optionally a merged PDF artefact."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["merge", "pdfs"], ws, log_level)
    result = pdf_merge_report(ws, dry_run=not write, output=output)
    logger.info(
        "Wrote PDF merge report",
        operation="merge_pdfs",
        dry_run=result.dry_run,
        included=result.included,
        skipped=result.skipped,
        failed=result.failed,
        output_path=str(result.output_path) if result.output_path else None,
    )
    _finish(summary, summary_path, next_action=f"Review `{result.manifest_path}`")
    if not quiet:
        console.print(f"[green]Wrote[/green] {result.manifest_path}")
        console.print(f"CSV: {result.csv_path}")
        if result.output_path:
            console.print(f"Merged PDF: {result.output_path}")


@app.command("search-corpus")
def search_corpus_cmd(
    query: str = typer.Argument(..., help="Keyword search query (SQLite FTS5 syntax)."),
    limit: int = typer.Option(20, "--limit", help="Maximum number of results."),
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Workspace path (default: CWD)"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Full-text keyword search across sources, artefacts, guidelines, claims, and research questions."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["search-corpus"], ws, log_level)
    result = search_corpus(ws, query, limit=limit)
    logger.info("Searched corpus", operation="search_corpus", status=result.report["status"], query=query)
    _finish(summary, summary_path)
    if quiet:
        return
    if result.report["status"] == "not_indexed":
        console.print(f"[yellow]Not indexed.[/yellow] {result.report['hint']}")
        return
    if result.report["status"] == "invalid_query":
        console.print(f"[red]Invalid query.[/red] {result.report['error']}")
        raise typer.Exit(code=2)
    if not result.report["results"]:
        console.print("[dim]No matches.[/dim]")
        return
    table = Table(title=f"Search: {query}")
    table.add_column("Kind")
    table.add_column("Path")
    table.add_column("Snippet")
    for row in result.report["results"]:
        table.add_row(row["doc_kind"], row["path"], row["snippet"])
    console.print(table)


@app.command("citation-relationships")
def citation_relationships(
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Workspace path (default: CWD)"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Show which sources support which claims, and which sources/research questions each artefact draws on."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["citation-relationships"], ws, log_level)
    report = citation_relationship_map(ws)
    logger.info(
        "Computed citation relationship map",
        operation="citation_relationships",
        source_count=len(report["sources"]),
        claim_count=len(report["claims"]),
        artefact_count=len(report["artefacts"]),
    )
    _finish(summary, summary_path)
    if quiet:
        return

    table = Table(title="Sources -> Claims / Artefacts")
    table.add_column("Source")
    table.add_column("Claims", justify="right")
    table.add_column("Artefacts", justify="right")
    for row in report["sources"]:
        table.add_row(row.get("file_name") or row.get("source_id"), str(len(row["claims"])), str(len(row["artefacts"])))
    console.print(table)


@app.command("research-progress")
def research_progress(
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Workspace path (default: CWD)"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Show research question / artefact activity over time — an honest local progress record, not a streak feature."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["research-progress"], ws, log_level)
    report = research_progress_report(ws)
    logger.info("Computed research progress report", operation="research_progress", event_count=report["event_count"])
    _finish(summary, summary_path)
    if quiet:
        return
    if not report["events"]:
        console.print("[dim]No research question or artefact activity recorded yet.[/dim]")
        return
    table = Table(title="Research Progress")
    table.add_column("At")
    table.add_column("Kind")
    table.add_column("Entity")
    table.add_column("Detail")
    for event in report["events"]:
        table.add_row(event.get("at", ""), event.get("kind", ""), event.get("entity_id", ""), event.get("detail", ""))
    console.print(table)


@app.command("timeline")
def timeline(
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Workspace path (default: CWD)"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Write a deterministic local timeline report."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["timeline"], ws, log_level)
    report = timeline_report(ws)
    logger.info("Wrote timeline report", operation="timeline", event_count=report["event_count"])
    _finish(summary, summary_path)
    if not quiet:
        console.print(f"[green]Wrote[/green] {ws / 'outputs' / 'reports' / 'timeline.yaml'}")


@app.command()
def convert(
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Workspace path (default: CWD)"),
    status: Optional[str] = typer.Option(None, "--status", help="Only convert sources with this review status."),
    ocr: bool = typer.Option(False, "--ocr", help="Explicitly allow local OCR fallback for scanned PDFs."),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Convert registered sources into local text files."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["convert"], ws, log_level)

    result = convert_sources(ws, status=status, allow_ocr=ocr)
    summary.files_processed = result.processed
    summary.files_succeeded = result.converted
    summary.files_skipped = result.skipped
    summary.errors += result.failed
    logger.info(
        "Converted sources",
        operation="convert",
        status_filter=status,
        processed=result.processed,
        converted=result.converted,
        skipped=result.skipped,
        failed=result.failed,
    )
    _finish(summary, summary_path, next_action="Review converted text under sources_text/.")

    if quiet:
        return
    console.print(
        f"[green]Convert complete[/green] processed={result.processed} converted={result.converted} "
        f"skipped={result.skipped} failed={result.failed}"
    )


@app.command("ocr-readiness")
def ocr_readiness(
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Workspace path (default: CWD)"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Check local OCR tool availability without processing documents."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["ocr", "readiness"], ws, log_level)
    report = ocr_readiness_report(ws)
    logger.info("Wrote OCR readiness report", operation="ocr_readiness", ocr_supported=report["ocr_supported_locally"])
    _finish(summary, summary_path)
    if not quiet:
        console.print(f"[green]Wrote[/green] {ws / 'outputs' / 'validation' / 'ocr-readiness.yaml'}")
        console.print(f"OCR supported locally: {report['ocr_supported_locally']}")


@app.command("processing-issues")
def processing_issues(
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Workspace path (default: CWD)"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Report skipped and failed processing issues without modifying originals."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["processing", "issues"], ws, log_level)
    report = processing_issue_report(ws)
    logger.info("Wrote processing issue report", operation="processing_issues", issue_count=report["issue_count"])
    _finish(summary, summary_path)
    if not quiet:
        console.print(f"[green]Wrote[/green] {ws / 'outputs' / 'validation' / 'processing-issues.yaml'}")


@metadata_app.command("extract")
def metadata_extract(
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Workspace path (default: CWD)"),
    status: Optional[str] = typer.Option(None, "--status", help="Only extract metadata for sources with this status."),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Extract deterministic citation metadata without inventing missing fields."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["metadata", "extract"], ws, log_level)

    result = extract_citation_metadata(ws, status=status)
    summary.files_processed = result.processed
    summary.files_succeeded = result.updated
    logger.info(
        "Extracted citation metadata",
        operation="metadata_extract",
        status_filter=status,
        processed=result.processed,
        updated=result.updated,
    )
    _finish(summary, summary_path, next_action="Inspect sources_metadata/ for extracted citation metadata.")

    if not quiet:
        console.print(f"[green]Metadata extracted[/green] processed={result.processed} updated={result.updated}")


@metadata_app.command("sidecars")
def metadata_sidecars(
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Workspace path (default: CWD)"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Parse local CSL JSON, BibTeX, and RIS sidecars for registered source metadata."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["metadata", "sidecars"], ws, log_level)
    result = import_sidecar_metadata(ws)
    summary.files_processed = result.processed
    summary.files_succeeded = result.updated
    summary.files_skipped = result.skipped
    logger.info(
        "Imported sidecar metadata",
        operation="metadata_sidecars",
        processed=result.processed,
        updated=result.updated,
        skipped=result.skipped,
    )
    _finish(summary, summary_path, next_action=f"Review `{result.report_path}`")
    if not quiet:
        console.print(
            f"[green]Sidecar metadata complete[/green] processed={result.processed} "
            f"updated={result.updated} skipped={result.skipped}"
        )


@metadata_app.command("validate")
def metadata_validate(
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Workspace path (default: CWD)"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Validate deterministic citation metadata quality, including DOI consistency."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["metadata", "validate"], ws, log_level)
    report = citation_consistency_report(ws)
    logger.info("Wrote citation consistency report", operation="metadata_validate", source_count=report["source_count"])
    _finish(summary, summary_path)
    if not quiet:
        console.print(f"[green]Wrote[/green] {ws / 'outputs' / 'validation' / 'citation-consistency.yaml'}")


@metadata_app.command("duplicates")
def metadata_duplicates(
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Workspace path (default: CWD)"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Report possible duplicate metadata by filename, title, and DOI."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["metadata", "duplicates"], ws, log_level)
    report = duplicate_metadata_report(ws)
    logger.info("Wrote metadata duplicate report", operation="metadata_duplicates", groups=len(report["duplicate_groups"]))
    _finish(summary, summary_path)
    if not quiet:
        console.print(f"[green]Wrote[/green] {ws / 'outputs' / 'validation' / 'metadata-duplicates.yaml'}")


@metadata_app.command("filename-suggestions")
def metadata_filename_suggestions(
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Workspace path (default: CWD)"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Write deterministic filename suggestions without renaming original files."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["metadata", "filename_suggestions"], ws, log_level)
    report = filename_suggestion_report(ws)
    logger.info("Wrote filename suggestion report", operation="metadata_filename_suggestions", source_count=report["source_count"])
    _finish(summary, summary_path)
    if not quiet:
        console.print(f"[green]Wrote[/green] {ws / 'outputs' / 'recommendations' / 'filename-suggestions.yaml'}")


@metadata_app.command("index")
def metadata_index(
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Workspace path (default: CWD)"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Build a deterministic local keyword index over converted text."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["metadata", "index"], ws, log_level)
    index = build_keyword_index(ws)
    logger.info("Built keyword index", operation="metadata_index", entry_count=index["entry_count"])
    _finish(summary, summary_path)
    if not quiet:
        console.print(f"[green]Wrote[/green] {ws / 'sources_metadata' / 'keyword-index.yaml'}")


@data_app.command("profile")
def data_profile(
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Workspace path (default: CWD)"),
    status: Optional[str] = typer.Option(None, "--status", help="Only profile data sources with this review status."),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Profile local CSV, SQLite, and JSON data sources."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["data", "profile"], ws, log_level)
    result = profile_data_sources(ws, status=status)
    summary.files_processed = result.processed
    summary.files_succeeded = result.profiled
    summary.files_skipped = result.skipped
    logger.info("Profiled data sources", operation="data_profile", processed=result.processed, profiled=result.profiled)
    _finish(summary, summary_path, next_action="Inspect outputs/data-profiles/.")
    if not quiet:
        console.print(
            f"[green]Data profile complete[/green] processed={result.processed} "
            f"profiled={result.profiled} skipped={result.skipped}"
        )


@data_app.command("list")
def data_list(
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Workspace path (default: CWD)"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """List registered local data sources."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["data", "list"], ws, log_level)
    rows = list_data_sources(ws)
    logger.info("Listed data sources", operation="data_list", count=len(rows))
    _finish(summary, summary_path)
    if quiet:
        return
    table = Table(title="Data sources")
    table.add_column("source_id")
    table.add_column("type")
    table.add_column("profile")
    table.add_column("file_name")
    for source in rows:
        profile = source.get("data_profile") if isinstance(source.get("data_profile"), dict) else {}
        table.add_row(
            str(source.get("source_id")),
            str(source.get("file_ext")),
            str(profile.get("status", "unprofiled")),
            str(source.get("file_name")),
        )
    console.print(table)


@data_app.command("status")
def data_status(
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Workspace path (default: CWD)"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Show local data source profile counts."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["data", "status"], ws, log_level)
    counts = data_source_counts(ws)
    logger.info("Computed data source counts", operation="data_status", counts=counts)
    _finish(summary, summary_path)
    if quiet:
        return
    table = Table(title="Data source status")
    table.add_column("status")
    table.add_column("count", justify="right")
    for key, value in counts.items():
        table.add_row(key, str(value))
    console.print(table)


def _maybe_prompt_secondary_backend_activation(ws: Path, *, quiet: bool) -> None:
    """Prompt to opt in to a configured-but-not-yet-active secondary
    backend, on `db init`/`db sync`/`db status` per Phase 24's spec. Never
    activates silently — this is the one place that asks, and only asks,
    never assumes yes. A quiet run skips the prompt entirely rather than
    blocking on stdin (matches every other `--quiet` behavior in this CLI).
    """
    if quiet:
        return
    try:
        status = secondary_backend_status(ws).report
    except SecondaryBackendError:
        return
    if not status.get("needs_activation_prompt"):
        return
    backend = status["configured"]
    reachable = "reachable" if status.get("reachable") else "NOT currently reachable"
    console.print(f"\n[yellow]A {backend} secondary backend is configured but not active for this workspace ({reachable}).[/yellow]")
    if not typer.confirm(f"Activate it now and mirror the current SQLite cache into it?", default=False):
        return
    try:
        result = activate_secondary_backend(ws)
    except SecondaryBackendError as e:
        console.print(f"[red]Activation failed:[/red] {e}")
        return
    console.print(f"[green]Activated {result.report['backend']}.[/green] Mirrored: {result.report['mirrored_counts']}")


@db_app.command("init")
def db_init(
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Workspace path (default: CWD)"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Initialize the optional workspace SQLite index database."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["db", "init"], ws, log_level)
    result = init_database(ws)
    logger.info("Initialized workspace database", operation="db_init", database=str(result.path))
    _finish(summary, summary_path, next_action="Run `ledgerly db sync` to index workspace state.")
    if not quiet:
        console.print(f"[green]Database initialized:[/green] {result.path}")
    _maybe_prompt_secondary_backend_activation(ws, quiet=quiet)


@db_app.command("sync")
def db_sync(
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Workspace path (default: CWD)"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Sync workspace YAML/Markdown metadata into the local SQLite index."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["db", "sync"], ws, log_level)
    result = sync_database(ws)
    logger.info("Synced workspace database", operation="db_sync", report=result.report)
    _finish(summary, summary_path, next_action="Run `ledgerly db status` or `ledgerly db privacy`.")
    if not quiet:
        console.print(f"[green]Database synced:[/green] {result.path}")
        console.print(
            f"files={result.report['files_synced']} changed={result.report['files_changed']} "
            f"missing={result.report['files_missing']} conflicts={result.report['conflicts']}"
        )
        secondary = result.report.get("secondary_backend")
        if secondary:
            console.print(f"Secondary backend ({secondary['backend']}): {secondary['status']}")
    _maybe_prompt_secondary_backend_activation(ws, quiet=quiet)


@db_app.command("status")
def db_status(
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Workspace path (default: CWD)"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Show SQLite index health, sync counts, and repair guidance."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["db", "status"], ws, log_level)
    result = database_status(ws)
    logger.info("Checked workspace database", operation="db_status", report=result.report)
    _finish(summary, summary_path)
    if quiet:
        return
    table = Table(title="Workspace database")
    table.add_column("Field")
    table.add_column("Value")
    for key in ("status", "schema_version", "source_of_truth", "last_sync_at", "integrity_check"):
        table.add_row(key, str(result.report.get(key)))
    for key, value in (result.report.get("counts") or {}).items():
        table.add_row(f"count.{key}", str(value))
    console.print(table)
    _maybe_prompt_secondary_backend_activation(ws, quiet=quiet)


@db_app.command("rebuild")
def db_rebuild(
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Workspace path (default: CWD)"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Rebuild the SQLite index from workspace YAML/Markdown source-of-truth files."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["db", "rebuild"], ws, log_level)
    result = rebuild_database(ws)
    logger.info("Rebuilt workspace database", operation="db_rebuild", report=result.report)
    _finish(summary, summary_path, next_action="Run `ledgerly db privacy` to inspect database privacy boundaries.")
    if not quiet:
        console.print(f"[green]Database rebuilt:[/green] {result.path}")


@db_app.command("apply-pending")
def db_apply_pending(
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Workspace path (default: CWD)"),
    review: bool = typer.Option(False, "--review", help="Review pending SQLite-to-file changes without applying."),
    apply: bool = typer.Option(False, "--apply", help="Apply reviewed pending changes to YAML/Markdown files."),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Review or apply explicit pending SQLite-to-YAML/Markdown changes."""
    if apply and review:
        console.print("[red]Use either --review or --apply, not both.[/red]")
        raise typer.Exit(code=2)
    if not apply:
        review = True

    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["db", "apply-pending"], ws, log_level)
    result = apply_pending_changes(ws, apply=apply) if apply else pending_changes_report(ws)
    logger.info("Handled pending database changes", operation="db_apply_pending", report=result.report)
    _finish(summary, summary_path)
    if quiet:
        return
    if review:
        console.print(f"Pending changes: {result.report.get('pending_count', result.report.get('review_count', 0))}")
        for item in result.report.get("pending_changes", result.report.get("review", [])):
            console.print(f"- #{item['id']} {item['relative_path']}: {item['reason']}")
    else:
        console.print(f"[green]Applied pending changes:[/green] {result.report['applied_count']}")


@db_app.command("privacy")
def db_privacy(
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Workspace path (default: CWD)"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Check that the SQLite database does not intentionally store secrets or original documents."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["db", "privacy"], ws, log_level)
    result = database_privacy_report(ws)
    logger.info("Checked database privacy", operation="db_privacy", report=result.report)
    if result.report["status"] != "ok":
        summary.warnings += int(result.report.get("issue_count", 0))
    _finish(summary, summary_path)
    if quiet:
        return
    if result.report["status"] == "ok":
        console.print("[green]OK[/green] Database privacy checks passed.")
    else:
        console.print(f"[yellow]Needs review[/yellow] issues={result.report['issue_count']}")
        for issue in result.report["issues"]:
            console.print(f"- {issue['issue']} in {issue.get('table')}.{issue.get('column')}")


@db_app.command("backend-status")
def db_backend_status(
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Workspace path (default: CWD)"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Show whether a secondary MariaDB/PostgreSQL backend is configured, active, and reachable. Read-only."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["db", "backend-status"], ws, log_level)
    result = secondary_backend_status(ws)
    logger.info("Checked secondary backend status", operation="db_backend_status", report=result.report)
    _finish(summary, summary_path)
    if quiet:
        return
    table = Table(title="Secondary database backend")
    table.add_column("Field")
    table.add_column("Value")
    for key, value in result.report.items():
        table.add_row(key, str(value))
    console.print(table)


@db_app.command("activate-backend")
def db_activate_backend(
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Workspace path (default: CWD)"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Explicitly activate the configured (LEDGERLY_DB_BACKEND) secondary backend and mirror SQLite into it."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["db", "activate-backend"], ws, log_level)
    try:
        result = activate_secondary_backend(ws)
    except SecondaryBackendError as e:
        logger.error("Secondary backend activation failed", operation="db_activate_backend", error=str(e))
        summary.errors += 1
        _finish(summary, summary_path)
        if not quiet:
            console.print(f"[red]{e}[/red]")
        raise typer.Exit(code=2)
    logger.info("Activated secondary backend", operation="db_activate_backend", report=result.report)
    _finish(summary, summary_path)
    if not quiet:
        console.print(f"[green]Activated {result.report['backend']}.[/green] Mirrored: {result.report['mirrored_counts']}")


@db_app.command("deactivate-backend")
def db_deactivate_backend(
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Workspace path (default: CWD)"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Stop mirroring to the active secondary backend. Does not delete data already written there or in SQLite."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["db", "deactivate-backend"], ws, log_level)
    result = deactivate_secondary_backend(ws)
    logger.info("Deactivated secondary backend", operation="db_deactivate_backend", report=result.report)
    _finish(summary, summary_path)
    if not quiet:
        if result.report["status"] == "not_active":
            console.print("[dim]No secondary backend was active.[/dim]")
        else:
            console.print(f"[green]Deactivated {result.report['backend']}.[/green]")


@db_app.command("repair-sqlite")
def db_repair_sqlite(
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Workspace path (default: CWD)"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Repair direction 1: local SQLite file is missing. Recreate it and repopulate from the active secondary backend."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["db", "repair-sqlite"], ws, log_level)
    try:
        result = repair_sqlite_from_secondary(ws)
    except SecondaryBackendError as e:
        logger.error("SQLite repair failed", operation="db_repair_sqlite", error=str(e))
        summary.errors += 1
        _finish(summary, summary_path)
        if not quiet:
            console.print(f"[red]{e}[/red]")
        raise typer.Exit(code=2)
    logger.info("Repaired SQLite from secondary backend", operation="db_repair_sqlite", report=result.report)
    _finish(summary, summary_path)
    if not quiet:
        console.print(f"[green]Repaired[/green] SQLite from {result.report['backend']}. Counts: {result.report['counts']}")


@db_app.command("repair-backend")
def db_repair_backend(
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Workspace path (default: CWD)"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Repair direction 2: the active secondary backend was unreachable/lost data. Re-mirror it from SQLite."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["db", "repair-backend"], ws, log_level)
    try:
        result = repair_secondary_from_sqlite(ws)
    except SecondaryBackendError as e:
        logger.error("Secondary backend repair failed", operation="db_repair_backend", error=str(e))
        summary.errors += 1
        _finish(summary, summary_path)
        if not quiet:
            console.print(f"[red]{e}[/red]")
        raise typer.Exit(code=2)
    logger.info("Repaired secondary backend from SQLite", operation="db_repair_backend", report=result.report)
    _finish(summary, summary_path)
    if not quiet:
        console.print(f"[green]Repaired[/green] {result.report['backend']} from SQLite. Counts: {result.report['counts']}")


@doc_app.command("version")
def doc_version(
    target: str = typer.Argument(..., help="Document target: path, artefact ID/title, alias, or artefact type."),
    reason: str = typer.Option("manual_snapshot", "--reason", help="Creation reason recorded on the version."),
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Snapshot a target document into the local document vault."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["doc", "version"], ws, log_level)
    try:
        record = create_document_version(
            ws,
            target,
            creation_reason=reason,
            source_command="doc version",
            cwd=Path.cwd(),
        )
    except ValueError as e:
        logger.error("Document version snapshot failed", operation="doc_version", target=target, error=str(e))
        summary.errors += 1
        _finish(summary, summary_path)
        raise typer.Exit(code=2)

    logger.info(
        "Wrote document version",
        operation="doc_version",
        target=target,
        version_id=record["version_id"],
        parent_version_id=record.get("parent_version_id"),
    )
    _finish(summary, summary_path, next_action=f"Run `ledgerly doc versions {target}` to see version history.")
    if not quiet:
        console.print(f"[green]Version:[/green] {record['version_id']}")
        console.print(f"Stored copy: {record['stored_path']}")


@doc_app.command("versions")
def doc_versions(
    target: Optional[str] = typer.Argument(None, help="Optional document target to filter by."),
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """List document versions stored in the local document vault."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["doc", "versions"], ws, log_level)
    rows = list_document_versions(ws, target)
    logger.info("Listed document versions", operation="doc_versions", target=target, count=len(rows))
    _finish(summary, summary_path)
    if quiet:
        return
    table = Table(title="Document versions")
    table.add_column("version_id")
    table.add_column("parent")
    table.add_column("reason")
    table.add_column("target_path")
    table.add_column("created_at")
    for row in rows:
        table.add_row(
            str(row.get("version_id")),
            str(row.get("parent_version_id") or "-"),
            str(row.get("creation_reason")),
            str(row.get("target_path")),
            str(row.get("created_at")),
        )
    console.print(table)


@doc_app.command("diff")
def doc_diff(
    version_id_a: str = typer.Argument(...),
    version_id_b: str = typer.Argument(...),
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Compare two document vault versions."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["doc", "diff"], ws, log_level)
    try:
        report = diff_document_versions(ws, version_id_a, version_id_b)
    except ValueError as e:
        logger.error("Document diff failed", operation="doc_diff", error=str(e))
        summary.errors += 1
        _finish(summary, summary_path)
        raise typer.Exit(code=2)

    logger.info(
        "Wrote document diff",
        operation="doc_diff",
        version_id_a=version_id_a,
        version_id_b=version_id_b,
        diff_supported=report["diff_supported"],
    )
    _finish(summary, summary_path)
    if quiet:
        return
    if not report["diff_supported"]:
        console.print(f"[yellow]Diff not supported:[/yellow] {report['reason']}")
        return
    for line in report["lines"]:
        console.print(line)


@doc_app.command("restore")
def doc_restore(
    version_id: str = typer.Argument(...),
    output: Optional[Path] = typer.Option(None, "--output", help="Restored copy destination (default: alongside the original)."),
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Restore a document vault version as a new copy without overwriting the current document."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["doc", "restore"], ws, log_level)
    try:
        record = restore_document_version(ws, version_id, output_path=output)
    except ValueError as e:
        logger.error("Document restore failed", operation="doc_restore", version_id=version_id, error=str(e))
        summary.errors += 1
        _finish(summary, summary_path)
        raise typer.Exit(code=2)

    logger.info(
        "Restored document version",
        operation="doc_restore",
        version_id=version_id,
        restored_to_path=record["restored_to_path"],
        new_version_id=record["version_id"],
    )
    _finish(summary, summary_path, next_action="Review the restored copy before replacing the current document.")
    if not quiet:
        console.print(f"[green]Restored:[/green] {record['restored_to_path']}")
        console.print(f"New version: {record['version_id']}")


@doc_app.command("compare")
def doc_compare(
    version_id_a: str = typer.Argument(...),
    version_id_b: str = typer.Argument(...),
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Compare how document strengths, weaknesses, unsupported claims, and references changed between two versions."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["doc", "compare"], ws, log_level)
    try:
        report = compare_document_versions(ws, version_id_a, version_id_b)
    except ValueError as e:
        logger.error("Document version comparison failed", operation="doc_compare", error=str(e))
        summary.errors += 1
        _finish(summary, summary_path)
        raise typer.Exit(code=2)

    logger.info(
        "Wrote document version comparison",
        operation="doc_compare",
        version_id_a=version_id_a,
        version_id_b=version_id_b,
        comparable=report["comparable"],
    )
    _finish(summary, summary_path)
    if quiet:
        return
    if not report["comparable"]:
        console.print(f"[yellow]Not comparable:[/yellow] {report['reason']}")
        return
    for section in ("strengths", "weaknesses", "unsupported_claims", "weakly_supported_claims", "references"):
        change = report[section]
        console.print(f"[bold]{section}[/bold] added={len(change['added'])} removed={len(change['removed'])}")


@doc_app.command("upload")
def doc_upload(
    source_path: Path = typer.Argument(..., help="Path to an externally created artefact file to bring into the vault."),
    title: Optional[str] = typer.Option(None, "--title", help="Optional title used for the renamed vault copy."),
    author: Optional[str] = typer.Option(None, "--author", help="Optional author used for the renamed vault copy."),
    year: Optional[str] = typer.Option(None, "--year", help="Optional year used for the renamed vault copy."),
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Copy an externally created artefact into the document vault under a sanitized, renamed name."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["doc", "upload"], ws, log_level)
    try:
        record = intake_uploaded_artefact(ws, source_path, title=title, author=author, year=year)
    except ValueError as e:
        logger.error("Artefact upload failed", operation="doc_upload", source_path=str(source_path), error=str(e))
        summary.errors += 1
        _finish(summary, summary_path)
        raise typer.Exit(code=2)

    logger.info(
        "Uploaded artefact into document vault",
        operation="doc_upload",
        upload_id=record["upload_id"],
        renamed_path=record["vault_renamed_path"],
    )
    _finish(summary, summary_path, next_action="Review the renamed copy before registering it as an artefact.")
    if not quiet:
        console.print(f"[green]Uploaded:[/green] {record['upload_id']}")
        console.print(f"Renamed copy: {record['vault_renamed_path']}")
        console.print(f"Original copy: {record['vault_original_copy_path']}")


@doc_app.command("uploads")
def doc_uploads(
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """List artefacts uploaded into the document vault."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["doc", "uploads"], ws, log_level)
    rows = list_uploaded_artefacts(ws)
    logger.info("Listed uploaded artefacts", operation="doc_uploads", count=len(rows))
    _finish(summary, summary_path)
    if quiet:
        return
    table = Table(title="Uploaded artefacts")
    table.add_column("upload_id")
    table.add_column("title")
    table.add_column("original_file_name")
    table.add_column("renamed_file_name")
    for row in rows:
        table.add_row(
            str(row.get("upload_id")),
            str(row.get("title")),
            str(row.get("original_file_name")),
            str(row.get("renamed_file_name")),
        )
    console.print(table)


@doc_app.command("derive-text")
def doc_derive_text(
    version_id: str = typer.Argument(...),
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Build a derived text snapshot with paragraph/sentence anchors for a document version."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["doc", "derive-text"], ws, log_level)
    try:
        snapshot = build_derived_text_snapshot(ws, version_id)
    except ValueError as e:
        logger.error("Derived text extraction failed", operation="doc_derive_text", version_id=version_id, error=str(e))
        summary.errors += 1
        _finish(summary, summary_path)
        raise typer.Exit(code=2)

    logger.info(
        "Wrote derived text snapshot",
        operation="doc_derive_text",
        version_id=version_id,
        section_count=snapshot["section_count"],
        paragraph_count=snapshot["paragraph_count"],
    )
    _finish(summary, summary_path)
    if not quiet:
        console.print(f"[green]Derived text:[/green] {snapshot['derived_text_path']}")
        console.print(f"Sections: {snapshot['section_count']}  Paragraphs: {snapshot['paragraph_count']}")


@doc_app.command("cross-reference")
def doc_cross_reference(
    upload_id: str = typer.Argument(...),
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Propose deterministic cross-reference candidates for an uploaded artefact (read-only)."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["doc", "cross-reference"], ws, log_level)
    try:
        report = cross_reference_candidates(ws, upload_id)
    except ValueError as e:
        logger.error("Cross-reference candidate generation failed", operation="doc_cross_reference", upload_id=upload_id, error=str(e))
        summary.errors += 1
        _finish(summary, summary_path)
        raise typer.Exit(code=2)

    logger.info(
        "Wrote cross-reference candidates",
        operation="doc_cross_reference",
        upload_id=upload_id,
        candidate_count=len(report.get("candidates", [])),
    )
    _finish(
        summary,
        summary_path,
        next_action="Run `doc cross-reference-review` per candidate (or hand-edit review_status), then `doc cross-reference-apply`.",
    )
    if not quiet:
        report_path = ws / "outputs" / "recommendations" / f"cross-reference-{upload_id}.yaml"
        console.print(f"[green]Candidates report:[/green] {report_path}")
        console.print(f"Candidates: {len(report.get('candidates', []))}")


@doc_app.command("cross-reference-review")
def doc_cross_reference_review(
    upload_id: str = typer.Argument(...),
    target_kind: str = typer.Argument(..., help="artefact|source|claim"),
    target_id: str = typer.Argument(...),
    review_status: str = typer.Argument(..., help="needs_human_review|accepted|approved|rejected"),
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Set one cross-reference candidate's review_status without hand-editing the report file."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["doc", "cross-reference-review"], ws, log_level)
    try:
        candidate = set_cross_reference_candidate_review_status(ws, upload_id, target_kind, target_id, review_status)
    except ValueError as e:
        logger.error(
            "Cross-reference review update failed",
            operation="doc_cross_reference_review",
            upload_id=upload_id,
            target_kind=target_kind,
            target_id=target_id,
            error=str(e),
        )
        summary.errors += 1
        _finish(summary, summary_path)
        raise typer.Exit(code=2)

    logger.info(
        "Updated cross-reference candidate review status",
        operation="doc_cross_reference_review",
        upload_id=upload_id,
        target_kind=target_kind,
        target_id=target_id,
        review_status=review_status,
    )
    _finish(summary, summary_path)
    if not quiet:
        console.print(f"[green]Updated:[/green] {candidate['target_kind']}/{candidate['target_id']} -> {candidate['review_status']}")


@doc_app.command("cross-reference-apply")
def doc_cross_reference_apply(
    upload_id: str = typer.Argument(...),
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Write reviewed (accepted/approved) cross-reference candidates onto the upload record."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["doc", "cross-reference-apply"], ws, log_level)
    try:
        result = apply_cross_reference_links(ws, upload_id)
    except ValueError as e:
        logger.error("Cross-reference apply failed", operation="doc_cross_reference_apply", upload_id=upload_id, error=str(e))
        summary.errors += 1
        _finish(summary, summary_path)
        raise typer.Exit(code=2)

    logger.info(
        "Applied cross-reference links",
        operation="doc_cross_reference_apply",
        upload_id=upload_id,
        applied_count=len(result.get("cross_references", [])),
    )
    _finish(summary, summary_path)
    if not quiet:
        console.print(f"[green]Applied links to upload:[/green] {upload_id}")
        console.print(f"Links: {len(result.get('cross_references', []))}")


@rqs_app.command("list")
def rqs_list(
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Workspace path (default: CWD)"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """List approved, candidate, rejected, and archived research questions."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["rqs", "list"], ws, log_level)
    groups = list_research_questions(ws)
    logger.info("Listed research questions", operation="rqs_list", counts={key: len(value) for key, value in groups.items()})
    _finish(summary, summary_path)
    if quiet:
        return
    table = Table(title="Research questions")
    table.add_column("group")
    table.add_column("id")
    table.add_column("question")
    for group, rows in groups.items():
        for row in rows:
            table.add_row(group, str(row.get("id")), str(row.get("question")))
    console.print(table)


@rqs_app.command("wizard")
def rqs_wizard(
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Workspace path (default: CWD)"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
):
    """Guided topic -> refined, falsifiable research question wizard. Usable any time, not just during init."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["rqs", "wizard"], ws, log_level)

    console.print("[bold]Research question wizard[/bold]")
    console.print("This builds one or more draft research questions from a few guided questions, entirely deterministic — no AI involved.\n")

    topic = typer.prompt("What's the general topic you're researching?").strip()
    scope = typer.prompt(
        "Scope/context (population, setting, time period — leave blank if not applicable)", default=""
    ).strip()
    relation = typer.prompt(
        "The phenomenon or relationship you're interested in (e.g. 'X reduces Y', or list several separated by commas/and)"
    ).strip()
    question_type = _prompt_numbered_choice(
        "Question type",
        ["Descriptive (what is/are...)", "Comparative (how does X differ...)", "Causal (does X affect Y...)", "Evaluative (how effective is X...)"],
    )
    question_type_key = {
        "Descriptive (what is/are...)": "descriptive",
        "Comparative (how does X differ...)": "comparative",
        "Causal (does X affect Y...)": "causal",
        "Evaluative (how effective is X...)": "evaluative",
    }[question_type]
    hypothesis = typer.prompt(
        "What existing assumption or claim are you testing? (this becomes your hypothesis — leave blank to skip)",
        default="",
    ).strip()
    proof_criteria = typer.prompt("What evidence would count as SUPPORT for that assumption?", default="").strip()
    disproof_criteria = typer.prompt("What evidence would count as REFUTING that assumption?", default="").strip()

    relations = split_candidate_relations(relation)
    if len(relations) > 1:
        console.print(f"\nYour answer implies {len(relations)} distinct angles — reviewing each as its own candidate question.\n")

    created: list[str] = []
    for phrase in relations:
        question = compose_research_question(phrase, scope, question_type_key)
        readiness = assess_research_question_readiness(question, project_type=str(read_yaml(ws / "research-context.yaml").get("project", {}).get("type", "")))
        console.print(f"\n[bold]{question}[/bold]")
        console.print(f"Deterministic readiness: {readiness['status']} (score {readiness['score']})")
        for finding in readiness["findings"]:
            console.print(f"  - [{finding['severity']}] {finding['message']}")
        if not typer.confirm("Save this as a draft research question?", default=True):
            continue
        record = add_research_question_candidate(
            ws,
            question,
            hypothesis=hypothesis or None,
            question_type=question_type_key,
            proof_criteria=proof_criteria or None,
            disproof_criteria=disproof_criteria or None,
        )
        created.append(record["id"])

    logger.info("Ran research question wizard", operation="rqs_wizard", topic=topic, created_count=len(created))
    _finish(summary, summary_path, next_action="Run `ledgerly rqs check` then `ledgerly rqs approve <id>` for each you keep.")
    if created:
        console.print(f"\n[green]Saved {len(created)} draft research question(s):[/green] {', '.join(created)}")
    else:
        console.print("\n[dim]No draft research questions were saved.[/dim]")


@rqs_app.command("approve")
def rqs_approve(
    rq_id: str = typer.Argument(...),
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Approve a draft research question."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["rqs", "approve"], ws, log_level)
    approve_research_question(ws, rq_id)
    logger.info("Approved research question", operation="rqs_approve", rq_id=rq_id)
    _finish(summary, summary_path)
    if not quiet:
        console.print(f"[green]Approved[/green] {rq_id}")


@rqs_app.command("check")
def rqs_check(
    rq_id: Optional[str] = typer.Argument(None, help="Optional research question ID to check."),
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Run deterministic readiness checks for research questions."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["rqs", "check"], ws, log_level)
    report = check_research_question_readiness(ws, rq_id=rq_id)
    logger.info("Checked research question readiness", operation="rqs_check", checked_count=report["checked_count"])
    _finish(summary, summary_path, next_action="Review findings before approving or using research questions.")
    if quiet:
        return

    table = Table(title="Research question readiness")
    table.add_column("id")
    table.add_column("group")
    table.add_column("status")
    table.add_column("score", justify="right")
    for row in report["research_questions"]:
        readiness = row["readiness"]
        table.add_row(str(row.get("id")), str(row.get("group")), str(readiness["status"]), str(readiness["score"]))
    console.print(table)


@rqs_app.command("reject")
def rqs_reject(
    rq_id: str = typer.Argument(...),
    reason: str = typer.Option("", "--reason", help="Reason for rejection"),
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Reject a research question."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["rqs", "reject"], ws, log_level)
    reject_research_question(ws, rq_id, reason=reason)
    logger.info("Rejected research question", operation="rqs_reject", rq_id=rq_id, reason=reason)
    _finish(summary, summary_path)
    if not quiet:
        console.print(f"[red]Rejected[/red] {rq_id}")


@rqs_app.command("archive")
def rqs_archive(
    rq_id: str = typer.Argument(...),
    reason: str = typer.Option("", "--reason", help="Reason for archiving"),
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Archive a research question."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["rqs", "archive"], ws, log_level)
    archive_research_question(ws, rq_id, reason=reason)
    logger.info("Archived research question", operation="rqs_archive", rq_id=rq_id, reason=reason)
    _finish(summary, summary_path)
    if not quiet:
        console.print(f"[yellow]Archived[/yellow] {rq_id}")


@rqs_app.command("assess")
def rqs_assess(
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Workspace path (default: CWD)"),
    rq_id: Optional[str] = typer.Option(None, "--rq", help="Optional research question id to assess."),
    ai: bool = typer.Option(False, "--ai", help="Required explicit opt-in for OpenAI research-question assessment."),
    max_sources: int = typer.Option(10, "--max-sources", help="Maximum accepted sources to include."),
    max_excerpt_chars: int = typer.Option(1200, "--max-excerpt-chars", help="Maximum converted-text excerpt characters per source."),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Run AI-assisted research-question assessment from safe context only."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["rqs", "assess"], ws, log_level)
    try:
        require_ai_flag(ai)
        credentials = openai_credentials(ws)
        report = ai_research_question_assessment(
            ws,
            credentials,
            rq_id=rq_id,
            max_sources=max_sources,
            max_excerpt_chars=max_excerpt_chars,
        )
    except OpenAiError as e:
        logger.error("AI research-question assessment failed", operation="rqs_assess", error=str(e))
        summary.errors += 1
        _finish(summary, summary_path)
        if not quiet:
            console.print(f"[red]{e}[/red]")
        raise typer.Exit(code=2)

    output_path = ws / "outputs" / "validation" / "openai-rq-assessment.yaml"
    write_yaml(output_path, report)
    logger.info(
        "Wrote AI research-question assessment",
        operation="rqs_assess",
        research_question_count=report["research_question_count"],
        source_count=report["source_count"],
        model=report["model"],
    )
    _finish(summary, summary_path)
    if not quiet:
        console.print(f"[green]Wrote[/green] {output_path}")
        _print_ai_review_footer(report, "Human review is required before using this output.")


@artefacts_app.command("register")
def artefacts_register(
    title: str = typer.Argument(...),
    artefact_type: str = typer.Option("report", "--type", help="Artefact type, e.g. thesis, paper, diagram, table."),
    path: Path = typer.Option(..., "--path", help="Local artefact path."),
    linked_source: Optional[list[str]] = typer.Option(None, "--source", help="Linked source ID. Repeatable."),
    linked_rq: Optional[list[str]] = typer.Option(None, "--rq", help="Linked research question ID. Repeatable."),
    requires_review: bool = typer.Option(True, "--requires-review/--no-review"),
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Register a local artefact in the workspace registry."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["artefacts", "register"], ws, log_level)
    record = register_artefact(
        ws,
        title=title,
        artefact_type=artefact_type,
        path=path,
        linked_sources=linked_source or [],
        linked_research_questions=linked_rq or [],
        requires_user_review=requires_review,
    )
    logger.info("Registered artefact", operation="artefacts_register", artefact_id=record["id"])
    _finish(summary, summary_path)
    if not quiet:
        console.print(f"[green]Registered[/green] {record['id']}")


@artefacts_app.command("create")
def artefacts_create(
    artefact_type: str = typer.Argument(
        ...,
        help="Deterministic artefact type. Use one of: "
        + ", ".join(sorted(SUPPORTED_ARTEFACT_TYPES.keys())),
    ),
    title: Optional[str] = typer.Option(None, "--title", help="Optional artefact title."),
    include_maybe: bool = typer.Option(False, "--include-maybe", help="Include maybe sources as well as accepted sources."),
    rq_id: Optional[str] = typer.Option(None, "--rq", help="Optional research question ID to link/filter."),
    overwrite: bool = typer.Option(False, "--overwrite", help="Overwrite an existing generated artefact file."),
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Create a deterministic, non-AI artefact from existing workspace state."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["artefacts", "create"], ws, log_level)
    try:
        result = create_deterministic_artefact(
            ws,
            artefact_type,
            title=title,
            include_maybe=include_maybe,
            rq_id=rq_id,
            overwrite=overwrite,
        )
    except ValueError as e:
        logger.error("Artefact creation failed", operation="artefacts_create", error=str(e))
        summary.errors += 1
        _finish(summary, summary_path)
        raise

    logger.info(
        "Created deterministic artefact",
        operation="artefacts_create",
        artefact_id=result.record["id"],
        output_path=str(result.path),
    )
    _finish(summary, summary_path, next_action="Review the artefact before using it as evidence.")
    if not quiet:
        console.print(f"[green]Created[/green] {result.record['id']}")
        console.print(f"Wrote {result.path}")


@paper_app.command("draft")
def paper_draft(
    rq_id: str = typer.Argument(..., help="Research question ID (e.g. rq-001) this paper draft is scoped to."),
    title: Optional[str] = typer.Option(None, "--title", help="Optional paper title."),
    include_maybe: bool = typer.Option(False, "--include-maybe", help="Include maybe sources as well as accepted sources."),
    overwrite: bool = typer.Option(False, "--overwrite", help="Overwrite an existing draft for this research question."),
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Assemble a deterministic, AI-free paper skeleton for one research question from real workspace data.

    Hypothesis statement, background/literature review (accepted sources), evidence sections built from the
    real claim ledger, and an explicitly unfinished conclusion — a genuinely useful scaffold, not empty prose.
    Claims aren't auto-sorted into supporting/refuting the hypothesis; that stays a human judgment call (or a
    future AI-assisted pass, gated behind explicit review) rather than a guess presented as fact.
    """
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["paper", "draft"], ws, log_level)
    try:
        result = create_deterministic_artefact(
            ws,
            "paper-draft",
            title=title,
            include_maybe=include_maybe,
            rq_id=rq_id,
            overwrite=overwrite,
        )
    except ValueError as e:
        logger.error("Paper draft failed", operation="paper_draft", error=str(e))
        summary.errors += 1
        _finish(summary, summary_path)
        if not quiet:
            console.print(f"[red]{e}[/red]")
        raise typer.Exit(code=2)

    logger.info(
        "Created paper draft skeleton",
        operation="paper_draft",
        artefact_id=result.record["id"],
        rq_id=rq_id,
        output_path=str(result.path),
    )
    _finish(
        summary,
        summary_path,
        next_action=f"Fill in the Evidence and Conclusion sections, then run `ledgerly validate {result.path}`.",
    )
    if not quiet:
        console.print(f"[green]Created[/green] {result.record['id']}")
        console.print(f"Wrote {result.path}")
        console.print("[yellow]Draft — the Evidence and Conclusion sections require your own work before this is final.[/yellow]")


@artefacts_app.command("list")
def artefacts_list(
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """List registered artefacts."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["artefacts", "list"], ws, log_level)
    rows = list_artefacts(ws)
    logger.info("Listed artefacts", operation="artefacts_list", count=len(rows))
    _finish(summary, summary_path)
    if quiet:
        return
    table = Table(title="Artefacts")
    table.add_column("id")
    table.add_column("type")
    table.add_column("review")
    table.add_column("title")
    for row in rows:
        table.add_row(str(row.get("id")), str(row.get("type")), str(row.get("review_status")), str(row.get("title")))
    console.print(table)


@artefacts_app.command("review")
def artefacts_review(
    artefact_id: str = typer.Argument(...),
    status: str = typer.Argument(..., help="reviewed | needs_revision | accepted | pending_review"),
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Set an artefact review status."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["artefacts", "review"], ws, log_level)
    set_artefact_review_status(ws, artefact_id, status)
    logger.info("Updated artefact review status", operation="artefacts_review", artefact_id=artefact_id, status=status)
    _finish(summary, summary_path)
    if not quiet:
        console.print(f"[green]Updated[/green] {artefact_id} {status}")


@artefacts_app.command("dependencies")
def artefacts_dependencies(
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Check artefact links against accepted sources and approved RQs."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["artefacts", "dependencies"], ws, log_level)
    report = artefact_dependency_report(ws)
    logger.info("Wrote artefact dependency report", operation="artefacts_dependencies", count=len(report["artefacts"]))
    _finish(summary, summary_path)
    if not quiet:
        console.print(f"[green]Wrote[/green] {ws / 'outputs' / 'validation' / 'artefact-dependencies.yaml'}")


@claims_app.command("add")
def claims_add(
    text: str = typer.Argument(...),
    linked_source: Optional[list[str]] = typer.Option(None, "--source", help="Linked source ID. Repeatable."),
    linked_rq: Optional[list[str]] = typer.Option(None, "--rq", help="Linked research question ID. Repeatable."),
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Add a manual claim to the local claims ledger."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["claims", "add"], ws, log_level)
    claim = add_claim(ws, text=text, linked_sources=linked_source or [], linked_research_questions=linked_rq or [])
    logger.info("Added claim", operation="claims_add", claim_id=claim["id"])
    _finish(summary, summary_path)
    if not quiet:
        console.print(f"[green]Added[/green] {claim['id']}")


@claims_app.command("list")
def claims_list(
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """List local claims."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["claims", "list"], ws, log_level)
    rows = list_claims(ws)
    logger.info("Listed claims", operation="claims_list", count=len(rows))
    _finish(summary, summary_path)
    if quiet:
        return
    table = Table(title="Claims")
    table.add_column("id")
    table.add_column("sources")
    table.add_column("text")
    for row in rows:
        table.add_row(str(row.get("id")), str(len(row.get("linked_sources", []))), str(row.get("text")))
    console.print(table)


@claims_app.command("gaps")
def claims_gaps(
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Write a local citation gap report for claims without linked sources."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["claims", "gaps"], ws, log_level)
    output_path = write_citation_gap_report(ws)
    logger.info("Wrote citation gap report", operation="claims_gaps", output_path=str(output_path))
    _finish(summary, summary_path)
    if not quiet:
        console.print(f"[green]Wrote[/green] {output_path}")


@claims_app.command("stale")
def claims_stale(
    days: int = typer.Option(14, "--days", help="Flag open claims not touched in at least this many days."),
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Write a local report of open claims (and citation gaps among them) not touched recently."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["claims", "stale"], ws, log_level)
    output_path = write_stale_claims_report(ws, days=days)
    logger.info("Wrote stale claims report", operation="claims_stale", output_path=str(output_path), days=days)
    _finish(summary, summary_path)
    if not quiet:
        console.print(f"[green]Wrote[/green] {output_path}")


@claims_app.command("status")
def claims_status(
    claim_id: str = typer.Argument(...),
    status: str = typer.Argument(..., help="supported | needs_evidence | rejected | needs_review | active"),
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Set a deterministic claim review status."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["claims", "status"], ws, log_level)
    set_claim_status(ws, claim_id, status)
    logger.info("Set claim status", operation="claims_status", claim_id=claim_id, status=status)
    _finish(summary, summary_path)
    if not quiet:
        console.print(f"[green]Updated[/green] {claim_id}")


@claims_app.command("validate")
def claims_validate(
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Validate that claims link only to existing accepted sources."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["claims", "validate"], ws, log_level)
    report = claim_source_validation_report(ws)
    logger.info("Wrote claim source validation report", operation="claims_validate", count=len(report["claims"]))
    _finish(summary, summary_path)
    if not quiet:
        console.print(f"[green]Wrote[/green] {ws / 'outputs' / 'validation' / 'claim-source-validation.yaml'}")


@decisions_app.command("add")
def decisions_add(
    text: str = typer.Argument(...),
    reason: str = typer.Option("", "--reason"),
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Append a structured local decision."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["decisions", "add"], ws, log_level)
    record = add_decision(ws, text, reason=reason)
    logger.info("Added decision", operation="decisions_add", decision_id=record["id"])
    _finish(summary, summary_path)
    if not quiet:
        console.print(f"[green]Added[/green] {record['id']}")


@decisions_app.command("list")
def decisions_list(
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """List recorded decisions."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["decisions", "list"], ws, log_level)
    rows = list_decisions(ws)
    logger.info("Listed decisions", operation="decisions_list", count=len(rows))
    _finish(summary, summary_path)
    if quiet:
        return
    table = Table(title="Decisions")
    table.add_column("id")
    table.add_column("decision")
    table.add_column("reason")
    for row in rows:
        table.add_row(row.get("id", ""), row.get("decision", ""), row.get("reason", ""))
    console.print(table)


@terminology_app.command("add")
def terminology_add(
    term: str = typer.Argument(...),
    definition: str = typer.Argument(...),
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Add or update a glossary term."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["terminology", "add"], ws, log_level)
    add_terminology(ws, term, definition)
    logger.info("Added terminology", operation="terminology_add", term=term)
    _finish(summary, summary_path)
    if not quiet:
        console.print(f"[green]Updated[/green] {term}")


@terminology_app.command("list")
def terminology_list(
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """List glossary terms."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["terminology", "list"], ws, log_level)
    rows = list_terminology(ws)
    logger.info("Listed terminology", operation="terminology_list", count=len(rows))
    _finish(summary, summary_path)
    if quiet:
        return
    table = Table(title="Terminology")
    table.add_column("term")
    table.add_column("definition")
    for row in rows:
        table.add_row(row.get("term", ""), row.get("definition", ""))
    console.print(table)


@feedback_app.command("add")
def feedback_add(
    text: str = typer.Argument(...),
    source: str = typer.Option("", "--source"),
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Add supervisor or stakeholder feedback."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["feedback", "add"], ws, log_level)
    record = add_feedback(ws, text, source=source)
    logger.info("Added feedback", operation="feedback_add", feedback_id=record["id"])
    _finish(summary, summary_path)
    if not quiet:
        console.print(f"[green]Added[/green] {record['id']}")


@feedback_app.command("list")
def feedback_list(
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """List supervisor/stakeholder feedback."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["feedback", "list"], ws, log_level)
    rows = list_feedback(ws)
    logger.info("Listed feedback", operation="feedback_list", count=len(rows))
    _finish(summary, summary_path)
    if quiet:
        return
    table = Table(title="Feedback")
    table.add_column("id")
    table.add_column("source")
    table.add_column("text")
    table.add_column("status")
    for row in rows:
        table.add_row(row.get("id", ""), row.get("source", ""), row.get("text", ""), row.get("status", ""))
    console.print(table)


@context_app.command("add")
def context_add(
    text: str = typer.Argument(...),
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Append a structured context changelog item."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["context", "add"], ws, log_level)
    record = add_context_change(ws, text)
    logger.info("Added context change", operation="context_add", change_id=record["id"])
    _finish(summary, summary_path)
    if not quiet:
        console.print(f"[green]Added[/green] {record['id']}")


@context_app.command("list")
def context_list(
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """List context changelog items."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["context", "list"], ws, log_level)
    rows = list_context_changes(ws)
    logger.info("Listed context changes", operation="context_list", count=len(rows))
    _finish(summary, summary_path)
    if quiet:
        return
    table = Table(title="Context changelog")
    table.add_column("id")
    table.add_column("text")
    for row in rows:
        table.add_row(row.get("id", ""), row.get("text", ""))
    console.print(table)


@notes_app.command("add")
def notes_add(
    text: str = typer.Argument(..., help="Note text."),
    kind: str = typer.Option("note", "--kind", help="note|meeting|transcript"),
    tag: list[str] = typer.Option([], "--tag", help="Add one or more tags (repeatable)."),
    source_label: str = typer.Option("", "--source-label", help="Optional label, e.g. a meeting name or date."),
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Workspace path (default: CWD)"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Add a personal note, meeting note, or transcript to the workspace's own note store."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["notes", "add"], ws, log_level)
    try:
        note = add_note(ws, text, kind=kind, tags=list(tag), source_label=source_label)
    except ValueError as e:
        logger.error("Failed to add note", operation="notes_add", error=str(e))
        summary.errors += 1
        _finish(summary, summary_path)
        if not quiet:
            console.print(f"[red]{e}[/red]")
        raise typer.Exit(code=2)
    logger.info("Added note", operation="notes_add", note_id=note["id"], kind=note["kind"])
    _finish(summary, summary_path)
    if not quiet:
        console.print(f"[green]Added[/green] {note['id']}")


@notes_app.command("list")
def notes_list(
    kind: Optional[str] = typer.Option(None, "--kind", help="Filter by note|meeting|transcript."),
    tag: Optional[str] = typer.Option(None, "--tag", help="Filter by tag."),
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Workspace path (default: CWD)"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """List personal notes, meeting notes, and transcripts."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["notes", "list"], ws, log_level)
    rows = list_notes(ws, kind=kind, tag=tag)
    logger.info("Listed notes", operation="notes_list", count=len(rows))
    _finish(summary, summary_path)
    if quiet:
        return
    table = Table(title="Notes")
    table.add_column("id")
    table.add_column("kind")
    table.add_column("text")
    table.add_column("tags")
    table.add_column("source_label")
    for row in rows:
        table.add_row(
            row.get("id", ""),
            row.get("kind", ""),
            row.get("text", ""),
            ", ".join(row.get("tags") or []),
            row.get("source_label", ""),
        )
    console.print(table)


@notes_app.command("search")
def notes_search(
    query: str = typer.Argument(..., help="Keyword(s) to search for across note text, tags, and source label."),
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Workspace path (default: CWD)"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Search notes by keyword — deterministic substring matching, no AI."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["notes", "search"], ws, log_level)
    rows = search_notes(ws, query)
    logger.info("Searched notes", operation="notes_search", query=query, hits=len(rows))
    _finish(summary, summary_path)
    if quiet:
        return
    table = Table(title=f"Notes matching '{query}'")
    table.add_column("id")
    table.add_column("kind")
    table.add_column("text")
    for row in rows:
        table.add_row(row.get("id", ""), row.get("kind", ""), row.get("text", ""))
    console.print(table)
    if not rows:
        console.print("[yellow]No matches found.[/yellow]")


@notes_app.command("tag")
def notes_tag(
    note_id: str = typer.Argument(..., help="Note ID, e.g. note-001."),
    tag: str = typer.Argument(..., help="Tag to add."),
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Workspace path (default: CWD)"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Add a tag to an existing note."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["notes", "tag"], ws, log_level)
    try:
        note = add_note_tag(ws, note_id, tag)
    except ValueError as e:
        logger.error("Failed to tag note", operation="notes_tag", error=str(e))
        summary.errors += 1
        _finish(summary, summary_path)
        if not quiet:
            console.print(f"[red]{e}[/red]")
        raise typer.Exit(code=2)
    logger.info("Tagged note", operation="notes_tag", note_id=note_id, tag=tag)
    _finish(summary, summary_path)
    if not quiet:
        console.print(f"[green]Tagged[/green] {note_id} with '{tag}' (tags now: {', '.join(note['tags'])})")


@notes_app.command("import-transcript")
def notes_import_transcript(
    path: Path = typer.Argument(..., help="Transcript file to import (plain text, .vtt, or .srt)."),
    kind: str = typer.Option("transcript", "--kind", help="note|meeting|transcript"),
    source_label: str = typer.Option("", "--source-label", help="Optional label; defaults to the file name."),
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Workspace path (default: CWD)"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Deterministically import a transcript export (plain text, VTT, or SRT) into the note store, no AI processing."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["notes", "import_transcript"], ws, log_level)
    try:
        note = import_transcript(ws, path, kind=kind, source_label=source_label)
    except ValueError as e:
        logger.error("Failed to import transcript", operation="notes_import_transcript", error=str(e))
        summary.errors += 1
        _finish(summary, summary_path)
        if not quiet:
            console.print(f"[red]{e}[/red]")
        raise typer.Exit(code=2)
    logger.info("Imported transcript", operation="notes_import_transcript", note_id=note["id"], path=str(path))
    _finish(summary, summary_path)
    if not quiet:
        console.print(f"[green]Imported[/green] {note['id']} from {path}")


@transcribe_app.command("readiness")
def transcribe_readiness(
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Workspace path (default: CWD)"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Check whether SourceScribe (LEDGERLY_SOURCESCRIBE_PATH) is reachable for transcription."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["transcribe", "readiness"], ws, log_level)
    report = sourcescribe_readiness_report(ws)
    logger.info("Checked SourceScribe readiness", operation="transcribe_readiness", available=report["available"])
    _finish(summary, summary_path)
    if quiet:
        return
    if report["available"]:
        console.print(f"[green]Available[/green] at {report['sourcescribe_path']}")
        console.print(f"  Python: {report['python_executable']}")
        console.print(f"  Supported extensions: {', '.join(report['supported_extensions'])}")
    else:
        console.print(f"[yellow]Not available[/yellow]: {report['reason']}")


@transcribe_app.command("upload")
def transcribe_upload(
    path: Path = typer.Argument(..., help="Audio/video file to upload for transcription."),
    max_size_mb: float = typer.Option(500.0, "--max-size-mb", help="Reject uploads larger than this."),
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Workspace path (default: CWD)"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Upload an audio/video file, registering a new pending transcription job (no transcription yet)."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["transcribe", "upload"], ws, log_level)
    try:
        job = upload_transcription_source(ws, path, max_file_size_bytes=int(max_size_mb * 1024 * 1024))
    except ValueError as e:
        logger.error("Failed to upload transcription source", operation="transcribe_upload", error=str(e))
        summary.errors += 1
        _finish(summary, summary_path)
        if not quiet:
            console.print(f"[red]{e}[/red]")
        raise typer.Exit(code=2)
    logger.info("Uploaded transcription source", operation="transcribe_upload", job_id=job["job_id"])
    _finish(summary, summary_path)
    if not quiet:
        console.print(f"[green]Uploaded[/green] {job['job_id']} ({job['original_file_name']}, status={job['status']})")


@transcribe_app.command("start")
def transcribe_start(
    job_id: str = typer.Argument(..., help="Job ID, e.g. transcribe-001."),
    language: Optional[str] = typer.Option(None, "--language", help="Optional language hint, e.g. en."),
    ai: bool = typer.Option(False, "--ai/--no-ai", help="Use the OpenAI API backend instead of local Whisper."),
    prompt: Optional[str] = typer.Option(None, "--prompt", help="Optional transcription prompt/context."),
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Workspace path (default: CWD)"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Synchronously run SourceScribe on an uploaded job, importing the transcript into the note store on success."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["transcribe", "start"], ws, log_level)
    try:
        job = start_transcription(ws, job_id, language=language, use_ai=ai, prompt=prompt)
    except (ValueError, TranscriptionError) as e:
        logger.error("Failed to start transcription", operation="transcribe_start", error=str(e))
        summary.errors += 1
        _finish(summary, summary_path)
        if not quiet:
            console.print(f"[red]{e}[/red]")
        raise typer.Exit(code=2)
    logger.info("Ran transcription job", operation="transcribe_start", job_id=job_id, status=job["status"])
    _finish(summary, summary_path)
    if quiet:
        return
    if job["status"] == "completed":
        console.print(f"[green]Completed[/green] {job_id} -> note {job.get('note_id')}")
    else:
        console.print(f"[yellow]Failed[/yellow] {job_id}: {job.get('error')}")


@transcribe_app.command("status")
def transcribe_status(
    job_id: str = typer.Argument(..., help="Job ID, e.g. transcribe-001."),
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Workspace path (default: CWD)"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Show a single transcription job's current status and details."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["transcribe", "status"], ws, log_level)
    try:
        job = get_transcription_job(ws, job_id)
    except ValueError as e:
        logger.error("Unknown transcription job", operation="transcribe_status", error=str(e))
        summary.errors += 1
        _finish(summary, summary_path)
        if not quiet:
            console.print(f"[red]{e}[/red]")
        raise typer.Exit(code=2)
    logger.info("Read transcription job status", operation="transcribe_status", job_id=job_id, status=job["status"])
    _finish(summary, summary_path)
    if not quiet:
        for key, value in job.items():
            console.print(f"  {key}: {value}")


@transcribe_app.command("list")
def transcribe_list(
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Workspace path (default: CWD)"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """List all transcription jobs."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["transcribe", "list"], ws, log_level)
    rows = list_transcription_jobs(ws)
    logger.info("Listed transcription jobs", operation="transcribe_list", count=len(rows))
    _finish(summary, summary_path)
    if quiet:
        return
    table = Table(title="Transcription jobs")
    table.add_column("job_id")
    table.add_column("status")
    table.add_column("original_file_name")
    table.add_column("note_id")
    for row in rows:
        table.add_row(row.get("job_id", ""), row.get("status", ""), row.get("original_file_name", ""), row.get("note_id", ""))
    console.print(table)


@zotero_app.command("collections")
def zotero_collections(
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Workspace path (default: CWD)"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """List collections from local zotero.sqlite without using the Zotero API."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["zotero", "collections"], ws, log_level)
    _storage_root, zotero_root, _zotero_config = resolve_zotero_paths(ws)
    if not zotero_root:
        logger.error("Could not derive Zotero root", operation="zotero_collections")
        summary.errors += 1
        _finish(summary, summary_path)
        raise typer.Exit(code=2)

    collections = list_zotero_collections(zotero_root)
    logger.info("Listed Zotero collections", operation="zotero_collections", count=len(collections))
    _finish(summary, summary_path)

    if quiet:
        return
    table = Table(title="Zotero collections")
    table.add_column("key")
    table.add_column("path")
    table.add_column("items", justify="right")
    for collection in collections:
        table.add_row(collection.key, collection.path, str(collection.item_count))
    console.print(table)


@zotero_app.command("test")
def zotero_test(
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Workspace path (default: CWD)"),
    storage: Optional[Path] = typer.Option(None, "--storage", help="Zotero storage folder override."),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Validate local Zotero storage and SQLite readability without using the Zotero API."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["zotero", "test"], ws, log_level)
    storage_root, zotero_root, _zotero_config = resolve_zotero_paths(ws, storage=storage)
    if not storage_root.exists():
        logger.error("Zotero storage root does not exist", operation="zotero_test", storage_root=str(storage_root))
        summary.errors += 1
        _finish(summary, summary_path)
        raise typer.Exit(code=2)

    paths = list(iter_source_files(storage_root))
    report = zotero_readiness_report(zotero_root, storage_root, paths)
    logger.info("Tested local Zotero configuration", operation="zotero_test", report=report)
    _finish(summary, summary_path)

    if quiet:
        return
    table = Table(title="Zotero local test")
    table.add_column("Check")
    table.add_column("Value")
    for key, value in report.items():
        table.add_row(key, str(value))
    console.print(table)


@zotero_app.command("select-collections")
def zotero_select_collections(
    collection_keys: list[str] = typer.Argument(..., help="Collection keys to use for Zotero scans."),
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Workspace path (default: CWD)"),
    include_subcollections: bool = typer.Option(True, "--include-subcollections/--no-subcollections"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Configure selected local Zotero collections for future scans."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["zotero", "select_collections"], ws, log_level)
    _storage_root, zotero_root, _zotero_config = resolve_zotero_paths(ws)
    if not zotero_root:
        logger.error("Could not derive Zotero root", operation="zotero_select_collections")
        summary.errors += 1
        _finish(summary, summary_path)
        raise typer.Exit(code=2)

    known = {collection.key: collection for collection in list_zotero_collections(zotero_root)}
    missing = [key for key in collection_keys if key not in known]
    if missing:
        logger.error("Unknown Zotero collection keys", operation="zotero_select_collections", missing=missing)
        summary.errors += 1
        _finish(summary, summary_path, next_action="Run `ledgerly zotero collections` to list valid keys.")
        if not quiet:
            console.print(f"[red]Unknown collection keys:[/red] {', '.join(missing)}")
        raise typer.Exit(code=2)

    selected = [{"key": key, "name": known[key].name, "path": known[key].path} for key in collection_keys]
    write_zotero_config(
        ws,
        {
            "mode": "selected_collections",
            "selected_collections": selected,
            "include_subcollections": include_subcollections,
        },
    )
    logger.info(
        "Configured selected Zotero collections",
        operation="zotero_select_collections",
        collection_keys=collection_keys,
        include_subcollections=include_subcollections,
    )
    _finish(summary, summary_path, next_action="Run `ledgerly scan` to scan selected collections.")
    if not quiet:
        console.print(f"[green]Configured[/green] {len(selected)} selected Zotero collection(s).")


@zotero_app.command("use-entire-library")
def zotero_use_entire_library(
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Workspace path (default: CWD)"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Configure Zotero scans to use the entire local storage library."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["zotero", "use_entire_library"], ws, log_level)
    write_zotero_config(ws, {"mode": "entire_library", "selected_collections": []})
    logger.info("Configured entire Zotero library mode", operation="zotero_use_entire_library")
    _finish(summary, summary_path)
    if not quiet:
        console.print("[green]Configured[/green] Zotero entire-library mode.")


@zotero_app.command("api-link")
def zotero_api_link(
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Workspace path (default: CWD)"),
    api_key: Optional[str] = typer.Option(None, "--api-key", help="Zotero Web API key (omit to be prompted, hidden)."),
    user_id: Optional[str] = typer.Option(None, "--user-id", help="Zotero user ID (omit to be prompted)."),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Link a Zotero Web API account by saving credentials into the workspace's .env.

    Replaces hand-editing .env; never prints the key back once saved. Run
    `ledgerly zotero api-test` afterwards to verify the link works.
    """
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["zotero", "api_link"], ws, log_level)
    resolved_key = api_key if api_key is not None else typer.prompt("Zotero Web API key", hide_input=True)
    resolved_user_id = user_id if user_id is not None else typer.prompt("Zotero user ID")
    try:
        save_zotero_api_credentials(ws, resolved_key, resolved_user_id)
    except ZoteroApiError as e:
        logger.error("Zotero API link failed", operation="zotero_api_link", error=str(e))
        summary.errors += 1
        _finish(summary, summary_path)
        if not quiet:
            console.print(f"[red]{e}[/red]")
        raise typer.Exit(code=2)
    logger.info("Linked Zotero Web API account", operation="zotero_api_link")
    _finish(summary, summary_path, next_action="Run `ledgerly zotero api-test` to verify the link.")
    if not quiet:
        console.print("[green]Linked[/green] Zotero Web API account (credentials saved, not shown).")


@zotero_app.command("api-unlink")
def zotero_api_unlink(
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Workspace path (default: CWD)"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Unlink a Zotero Web API account by removing saved credentials from the workspace's .env."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["zotero", "api_unlink"], ws, log_level)
    clear_zotero_api_credentials(ws)
    logger.info("Unlinked Zotero Web API account", operation="zotero_api_unlink")
    _finish(summary, summary_path)
    if not quiet:
        console.print("[green]Unlinked[/green] Zotero Web API account.")


@zotero_app.command("api-test")
def zotero_api_test(
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Workspace path (default: CWD)"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Test read-only Zotero Web API credentials without printing the key."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["zotero", "api_test"], ws, log_level)
    try:
        credentials = zotero_api_credentials(ws)
        report = zotero_api_readiness(credentials)
    except ZoteroApiError as e:
        logger.error("Zotero API test failed", operation="zotero_api_test", error=str(e))
        summary.errors += 1
        _finish(summary, summary_path)
        if not quiet:
            console.print(f"[red]{e}[/red]")
        raise typer.Exit(code=2)
    output_path = ws / "outputs" / "validation" / "zotero-api-test.yaml"
    write_yaml(output_path, report)
    logger.info(
        "Tested Zotero Web API credentials",
        operation="zotero_api_test",
        user_id=report["user_id"],
        key_has_write_access=report["key_has_write_access"],
    )
    _finish(summary, summary_path)
    if not quiet:
        console.print(f"[green]Wrote[/green] {output_path}")
        if report["key_has_write_access"]:
            console.print("[yellow]Warning: Zotero API key has write access. Use a read-only key for Ledgerly.[/yellow]")


@zotero_app.command("api-collections")
def zotero_api_collections_cmd(
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Workspace path (default: CWD)"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """List Zotero Web API collections using read-only credentials."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["zotero", "api_collections"], ws, log_level)
    try:
        credentials = zotero_api_credentials(ws)
        collections = zotero_api_collections(credentials)
    except ZoteroApiError as e:
        logger.error("Zotero API collection listing failed", operation="zotero_api_collections", error=str(e))
        summary.errors += 1
        _finish(summary, summary_path)
        if not quiet:
            console.print(f"[red]{e}[/red]")
        raise typer.Exit(code=2)
    output_path = ws / "outputs" / "validation" / "zotero-api-collections.yaml"
    write_yaml(output_path, {"version": 1, "collections": collections})
    logger.info("Listed Zotero Web API collections", operation="zotero_api_collections", count=len(collections))
    _finish(summary, summary_path)
    if quiet:
        return
    table = Table(title="Zotero Web API collections")
    table.add_column("key")
    table.add_column("name")
    table.add_column("parent")
    for collection in collections:
        table.add_row(str(collection.get("key")), str(collection.get("name")), str(collection.get("parent_key") or ""))
    console.print(table)


@zotero_app.command("api-select-collections")
def zotero_api_select_collections(
    collection_keys: list[str] = typer.Argument(..., help="Collection keys to select for future Zotero API workflows."),
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Workspace path (default: CWD)"),
    include_subcollections: bool = typer.Option(True, "--include-subcollections/--no-subcollections"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Save read-only Zotero Web API collection selection in workspace config."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["zotero", "api_select_collections"], ws, log_level)
    write_zotero_config(
        ws,
        {
            "api_mode": "selected_collections",
            "api_selected_collections": [{"key": key} for key in collection_keys],
            "api_include_subcollections": include_subcollections,
            "api_access": "read_only",
        },
    )
    logger.info(
        "Configured Zotero Web API selected collections",
        operation="zotero_api_select_collections",
        collection_keys=collection_keys,
        include_subcollections=include_subcollections,
    )
    _finish(summary, summary_path)
    if not quiet:
        console.print(f"[green]Configured[/green] {len(collection_keys)} Zotero API collection(s).")


@zotero_app.command("scan-collection")
def zotero_scan_collection(
    collection_key: str = typer.Argument(..., help="Collection key to scan once."),
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Workspace path (default: CWD)"),
    include_subcollections: bool = typer.Option(True, "--include-subcollections/--no-subcollections"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Scan one local Zotero collection without changing saved collection mode."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["zotero", "scan_collection"], ws, log_level)
    storage_root, zotero_root, _zotero_config = resolve_zotero_paths(ws)
    if not zotero_root:
        logger.error("Could not derive Zotero root", operation="zotero_scan_collection")
        summary.errors += 1
        _finish(summary, summary_path)
        raise typer.Exit(code=2)

    allowed_keys = storage_keys_for_collections(zotero_root, [collection_key], include_subcollections=include_subcollections)
    candidates = [path for path in iter_source_files(storage_root) if path.parent.name in allowed_keys]
    result = scan_sources(
        ws,
        storage_root,
        provider="zotero_storage",
        logger=logger,
        file_paths=candidates,
        zotero_root=zotero_root,
    )
    summary.files_processed = result.processed
    summary.files_succeeded = result.added
    summary.files_skipped = result.skipped
    logger.info(
        "Scanned Zotero collection",
        operation="zotero_scan_collection",
        collection_key=collection_key,
        candidates=len(candidates),
        added=result.added,
    )
    _finish(summary, summary_path, next_action="Run `ledgerly sources review` to review discovered sources.")
    if not quiet:
        console.print(
            f"[green]Collection scan complete[/green] processed={result.processed} added={result.added} "
            f"duplicates={result.duplicates} skipped={result.skipped}"
        )


@zotero_app.command("search")
def zotero_search(
    query: str = typer.Argument(..., help="Keyword query to match against filenames and Zotero full-text cache."),
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Workspace path (default: CWD)"),
    storage: Optional[Path] = typer.Option(None, "--storage", help="Zotero storage folder override."),
    limit: int = typer.Option(10, "--limit", min=1, help="Maximum matches to show."),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Search local Zotero storage filenames and .zotero-ft-cache text without using AI or the Zotero API."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["zotero", "search"], ws, log_level)

    cfg_root, source_mode, _source_config = configured_source_root(ws)
    zotero_config = configured_zotero(ws)
    storage_root = storage or (Path(zotero_config["storage"]) if zotero_config.get("storage") else cfg_root)
    if not storage_root:
        logger.error("No Zotero storage root configured or provided", operation="zotero_search")
        summary.errors += 1
        _finish(summary, summary_path, next_action="Pass --storage or configure sources.root during init.")
        raise typer.Exit(code=2)

    if not storage_root.exists():
        logger.error("Zotero storage root does not exist", storage_root=str(storage_root))
        summary.errors += 1
        _finish(summary, summary_path, next_action="Fix the Zotero storage path and rerun search.")
        raise typer.Exit(code=2)

    terms = keyword_terms(query)
    if not terms:
        logger.error("Empty Zotero search query", operation="zotero_search")
        summary.errors += 1
        _finish(summary, summary_path, next_action="Rerun search with at least one keyword.")
        raise typer.Exit(code=2)

    zotero_root = Path(zotero_config["root"]) if zotero_config.get("root") else zotero_root_from_storage(storage_root)
    candidates = list(iter_source_files(storage_root))
    hits = search_zotero_storage(storage_root, terms, candidates, limit=limit, zotero_root=zotero_root)

    summary.files_processed = len(candidates)
    summary.files_succeeded = len(hits)
    logger.info(
        "Searched Zotero storage",
        operation="zotero_search",
        source_mode=source_mode,
        storage_root=str(storage_root),
        terms=terms,
        candidates=len(candidates),
        hits=len(hits),
    )
    _finish(summary, summary_path, next_action="Run `ledgerly scan --kind zotero_storage` to register useful files.")

    if quiet:
        return

    table = Table(title="Zotero storage search")
    table.add_column("score", justify="right")
    table.add_column("key")
    table.add_column("cache")
    table.add_column("matched")
    table.add_column("file_name")
    for hit in hits:
        table.add_row(
            str(hit.score),
            str(hit.storage_key or ""),
            "yes" if hit.has_fulltext_cache else "no",
            ", ".join(hit.matched_terms),
            hit.file_path.name,
        )
    console.print(table)
    if not hits:
        console.print("[yellow]No matches found.[/yellow]")


@zotero_app.command("metadata-report")
def zotero_metadata_report(
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Workspace path (default: CWD)"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Report missing local Zotero metadata fields from read-only zotero.sqlite."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["zotero", "metadata_report"], ws, log_level)
    _storage_root, zotero_root, _zotero_config = resolve_zotero_paths(ws)
    if not zotero_root:
        logger.error("Could not derive Zotero root", operation="zotero_metadata_report")
        summary.errors += 1
        _finish(summary, summary_path)
        raise typer.Exit(code=2)

    report = metadata_quality_report(zotero_root)
    output_path = ws / "outputs" / "validation" / "zotero-metadata-report.yaml"
    write_yaml(output_path, report)
    logger.info("Wrote Zotero metadata report", operation="zotero_metadata_report", output_path=str(output_path))
    _finish(summary, summary_path)
    if not quiet:
        console.print(f"[green]Wrote[/green] {output_path}")
        console.print(
            f"attachments={report['total_attachments']} missing_title={len(report['missing_title'])} "
            f"missing_year={len(report['missing_year'])} missing_doi={len(report['missing_doi'])} "
            f"missing_creators={len(report['missing_creators'])}"
        )


@zotero_app.command("attachment-health")
def zotero_attachment_health(
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Workspace path (default: CWD)"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Compare local Zotero storage files with attachment records in zotero.sqlite."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["zotero", "attachment_health"], ws, log_level)
    storage_root, zotero_root, _zotero_config = resolve_zotero_paths(ws)
    if not zotero_root:
        logger.error("Could not derive Zotero root", operation="zotero_attachment_health")
        summary.errors += 1
        _finish(summary, summary_path)
        raise typer.Exit(code=2)

    paths = list(iter_source_files(storage_root))
    report = attachment_health_report(zotero_root, storage_root, paths)
    output_path = ws / "outputs" / "validation" / "zotero-attachment-health.yaml"
    write_yaml(output_path, report)
    logger.info("Wrote Zotero attachment health report", operation="zotero_attachment_health", output_path=str(output_path))
    _finish(summary, summary_path)
    if not quiet:
        console.print(f"[green]Wrote[/green] {output_path}")
        console.print(
            f"storage_files={report['storage_files']} sqlite_attachments={report['sqlite_attachments']} "
            f"missing_files={len(report['missing_attachment_files'])} unlinked_files={len(report['unlinked_storage_files'])}"
        )


@zotero_app.command("fulltext-report")
def zotero_fulltext_report(
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Workspace path (default: CWD)"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Report which local Zotero storage files have `.zotero-ft-cache` available."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["zotero", "fulltext_report"], ws, log_level)
    storage_root, _zotero_root, _zotero_config = resolve_zotero_paths(ws)
    paths = list(iter_source_files(storage_root))
    report = fulltext_availability_report(storage_root, paths)
    output_path = ws / "outputs" / "validation" / "zotero-fulltext-report.yaml"
    write_yaml(output_path, report)
    logger.info("Wrote Zotero fulltext report", operation="zotero_fulltext_report", output_path=str(output_path))
    _finish(summary, summary_path)
    if not quiet:
        console.print(f"[green]Wrote[/green] {output_path}")
        console.print(
            f"total={report['total_sources']} with_cache={report['with_fulltext_cache']} "
            f"without_cache={report['without_fulltext_cache']}"
        )


@zotero_app.command("duplicates")
def zotero_duplicates(
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Workspace path (default: CWD)"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Find possible local Zotero metadata duplicates by DOI or title/year."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["zotero", "duplicates"], ws, log_level)
    _storage_root, zotero_root, _zotero_config = resolve_zotero_paths(ws)
    if not zotero_root:
        logger.error("Could not derive Zotero root", operation="zotero_duplicates")
        summary.errors += 1
        _finish(summary, summary_path)
        raise typer.Exit(code=2)

    duplicates = {"version": 1, "duplicates": duplicate_metadata_candidates(zotero_root)}
    output_path = ws / "outputs" / "validation" / "zotero-duplicates.yaml"
    write_yaml(output_path, duplicates)
    logger.info("Wrote Zotero duplicate report", operation="zotero_duplicates", output_path=str(output_path))
    _finish(summary, summary_path)
    if not quiet:
        console.print(f"[green]Wrote[/green] {output_path}")
        console.print(f"duplicate_groups={len(duplicates['duplicates'])}")


@zotero_app.command("snapshot")
def zotero_snapshot(
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Workspace path (default: CWD)"),
    output: Optional[Path] = typer.Option(None, "--output", help="Snapshot output path."),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Write a reproducible local Zotero metadata snapshot into the workspace."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["zotero", "snapshot"], ws, log_level)
    _storage_root, zotero_root, _zotero_config = resolve_zotero_paths(ws)
    if not zotero_root:
        logger.error("Could not derive Zotero root", operation="zotero_snapshot")
        summary.errors += 1
        _finish(summary, summary_path)
        raise typer.Exit(code=2)

    output_path = output or (ws / "sources_metadata" / "zotero-snapshot.yaml")
    ensure_path_not_in_zotero(output_path, zotero_root)
    write_yaml(output_path, zotero_metadata_snapshot(zotero_root))
    logger.info("Wrote Zotero metadata snapshot", operation="zotero_snapshot", output_path=str(output_path))
    _finish(summary, summary_path)
    if not quiet:
        console.print(f"[green]Wrote[/green] {output_path}")


@zotero_app.command("export-bibtex")
def zotero_export_bibtex(
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Workspace path (default: CWD)"),
    output: Optional[Path] = typer.Option(None, "--output", help="BibTeX output path."),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Export conservative BibTeX from local Zotero SQLite metadata."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["zotero", "export_bibtex"], ws, log_level)
    _storage_root, zotero_root, _zotero_config = resolve_zotero_paths(ws)
    if not zotero_root:
        logger.error("Could not derive Zotero root", operation="zotero_export_bibtex")
        summary.errors += 1
        _finish(summary, summary_path)
        raise typer.Exit(code=2)

    output_path = output or (ws / "outputs" / "reports" / "zotero-references.bib")
    ensure_path_not_in_zotero(output_path, zotero_root)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    content = export_bibtex_from_metadata(zotero_root)
    output_path.write_text(content, encoding="utf-8")
    entries = content.count("\n@") + (1 if content.startswith("@") else 0)
    logger.info("Exported Zotero BibTeX", operation="zotero_export_bibtex", output_path=str(output_path), entries=entries)
    _finish(summary, summary_path)
    if not quiet:
        console.print(f"[green]Wrote[/green] {output_path}")
        console.print(f"entries={entries}")


@sources_app.command("list")
def sources_list(
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Workspace path (default: CWD)"),
    status: Optional[str] = typer.Option(None, "--status", help="Filter by status, e.g. pending_review"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """List sources from source-register.yaml."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["sources", "list"], ws, log_level)

    rows = list_sources(ws, status=status)
    logger.info("Listed sources", operation="sources_list", status=status, count=len(rows))
    _finish(summary, summary_path)

    if quiet:
        return

    table = Table(title="Sources")
    table.add_column("source_id")
    table.add_column("status")
    table.add_column("provider")
    table.add_column("file_name")
    table.add_column("file_path")
    for s in rows:
        table.add_row(
            str(s.get("source_id")),
            str(s.get("status")),
            str(s.get("provider")),
            str(s.get("file_name")),
            str(s.get("file_path")),
        )
    console.print(table)


@sources_app.command("status")
def sources_status(
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Workspace path (default: CWD)"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Show counts of sources by status."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["sources", "status"], ws, log_level)

    counts = source_counts(ws)
    logger.info("Computed source status counts", operation="sources_status", counts=counts)
    _finish(summary, summary_path)

    if quiet:
        return

    table = Table(title="Source status counts")
    table.add_column("status")
    table.add_column("count", justify="right")
    for k in sorted(counts.keys()):
        table.add_row(k, str(counts[k]))
    console.print(table)


@sources_app.command("accept")
def sources_accept(
    source_id: str = typer.Argument(...),
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Accept a source for this project."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["sources", "accept"], ws, log_level)

    set_source_status(ws, source_id=source_id, new_status="accepted")
    logger.info("Accepted source", operation="sources_accept", source_id=source_id)
    _finish(summary, summary_path)

    if not quiet:
        console.print(f"[green]Accepted[/green] {source_id}")


@sources_app.command("maybe")
def sources_maybe(
    source_id: str = typer.Argument(...),
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Mark a source as maybe for this project."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["sources", "maybe"], ws, log_level)

    set_source_status(ws, source_id=source_id, new_status="maybe")
    logger.info("Set source maybe", operation="sources_maybe", source_id=source_id)
    _finish(summary, summary_path)

    if not quiet:
        console.print(f"[yellow]Maybe[/yellow] {source_id}")


@sources_app.command("ignore")
def sources_ignore(
    source_id: str = typer.Argument(...),
    reason: str = typer.Option("", "--reason", help="Reason to ignore"),
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Ignore a source for this project (project-specific)."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["sources", "ignore"], ws, log_level)

    set_source_status(ws, source_id=source_id, new_status="ignored", ignore_reason=reason)
    logger.info("Ignored source", operation="sources_ignore", source_id=source_id, reason=reason)
    _finish(summary, summary_path)

    if not quiet:
        console.print(f"[red]Ignored[/red] {source_id}")


@sources_app.command("note")
def sources_note(
    source_id: str = typer.Argument(...),
    note: str = typer.Argument(...),
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Set a local note for a source."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["sources", "note"], ws, log_level)
    set_source_note(ws, source_id=source_id, note=note)
    logger.info("Set source note", operation="sources_note", source_id=source_id)
    _finish(summary, summary_path)
    if not quiet:
        console.print(f"[green]Updated[/green] {source_id}")


@sources_app.command("tag")
def sources_tag(
    source_id: str = typer.Argument(...),
    tag: str = typer.Argument(...),
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Add a deterministic manual tag to a source."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["sources", "tag"], ws, log_level)
    add_source_tag(ws, source_id=source_id, tag=tag)
    logger.info("Added source tag", operation="sources_tag", source_id=source_id, tag=tag)
    _finish(summary, summary_path)
    if not quiet:
        console.print(f"[green]Tagged[/green] {source_id}")


@sources_app.command("report")
def sources_report(
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Workspace path (default: CWD)"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Write a deterministic source review report."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["sources", "report"], ws, log_level)
    report = source_review_report(ws)
    logger.info("Wrote source review report", operation="sources_report", count=len(report["sources"]))
    _finish(summary, summary_path)
    if not quiet:
        console.print(f"[green]Wrote[/green] {ws / 'outputs' / 'validation' / 'source-review-report.yaml'}")


@sources_app.command("review")
def sources_review(
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Workspace path (default: CWD)"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
):
    """Interactive review of pending_review sources."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["sources", "review"], ws, log_level)

    pending = list_sources(ws, status="pending_review")
    if not pending:
        logger.info("No pending sources", operation="sources_review")
        _finish(summary, summary_path)
        console.print("[green]No pending sources.[/green]")
        return

    accepted_n = ignored_n = maybe_n = skipped_n = 0

    console.print(f"Pending sources: {len(pending)}")
    for s in pending:
        sid = s["source_id"]
        console.print(f"\n[bold]{sid}[/bold]  {s.get('file_name')}  ({s.get('file_path')})")
        action = typer.prompt("Action", type=click.Choice(["accept", "ignore", "maybe", "skip"]), default="skip")
        if action == "skip":
            skipped_n += 1
            continue
        if action == "ignore":
            reason = typer.prompt("Ignore reason", default="")
            set_source_status(ws, source_id=sid, new_status="ignored", ignore_reason=reason)
            ignored_n += 1
        elif action == "accept":
            set_source_status(ws, source_id=sid, new_status="accepted")
            accepted_n += 1
        elif action == "maybe":
            set_source_status(ws, source_id=sid, new_status="maybe")
            maybe_n += 1

    logger.info(
        "Completed interactive review",
        operation="sources_review",
        accepted=accepted_n,
        ignored=ignored_n,
        maybe=maybe_n,
        skipped=skipped_n,
    )
    _finish(summary, summary_path, next_action="Run `ledgerly sources list --status accepted` to confirm.")
    console.print("[green]Review complete.[/green]")
