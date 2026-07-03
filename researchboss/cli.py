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

from researchboss.core.runlog import JsonlLogger, RunSummary, make_run_paths, write_run_summary
from researchboss.core.yamlio import read_yaml, write_yaml
from researchboss.engine.conversion import convert_sources
from researchboss.engine.data import data_source_counts, list_data_sources, profile_data_sources
from researchboss.engine.metadata import extract_citation_metadata
from researchboss.engine.sources import (
    ScanResult,
    iter_source_files,
    list_sources,
    scan_sources,
    set_source_status,
    source_counts,
)
from researchboss.engine.zotero import (
    attachment_health_report,
    duplicate_metadata_candidates,
    export_bibtex_from_metadata,
    fulltext_availability_report,
    keyword_terms,
    list_zotero_collections,
    metadata_quality_report,
    search_zotero_storage,
    storage_keys_for_collections,
    zotero_metadata_snapshot,
    zotero_readiness_report,
    zotero_root_from_storage,
)
from researchboss import __version__
from researchboss.engine.workspace import (
    AI_PREFERENCES,
    CITATION_STYLES,
    DATA_FILE_EXPECTATIONS,
    PRIMARY_OUTPUT_TYPES,
    PROJECT_TYPES,
    SOURCE_REVIEW_DEFAULTS,
    default_documents_dir,
    find_default_zotero_storage,
    infer_source_mode,
    init_workspace,
)

app = typer.Typer(add_completion=False, help="ResearchBoss (Phase 1 foundation).")
sources_app = typer.Typer(help="Source inbox + register commands.")
config_app = typer.Typer(help="Config commands.")
zotero_app = typer.Typer(help="Read-only local Zotero storage commands.")
metadata_app = typer.Typer(help="Deterministic metadata commands.")
data_app = typer.Typer(help="Local data source commands.")

app.add_typer(sources_app, name="sources")
app.add_typer(config_app, name="config")
app.add_typer(zotero_app, name="zotero")
app.add_typer(metadata_app, name="metadata")
app.add_typer(data_app, name="data")

console = Console()
DEFAULT_WORKSPACES_DIR = "workspaces"
CLI_DEFAULTS_FILE = ".researchboss-cli.local.yaml"
MIN_PYTHON = (3, 11)
REQUIRED_RUNTIME_MODULES = ["click", "typer", "rich", "pydantic", "yaml"]


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

    console.print("[red]ResearchBoss is not ready to run.[/red]")
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
        console.print("[red]No ResearchBoss workspaces found.[/red]")
        console.print("Pass --workspace, run from a workspace folder, or create one with `researchboss init`.")
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
        "Research questions are optional, but adding them now helps ResearchBoss keep useful context for later processing."
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
    citation_style = _prompt_numbered_choice("Preferred citation style", CITATION_STYLES, default_index=7)
    custom_citation_style = None
    if citation_style == "Custom":
        custom_citation_style = typer.prompt("Custom citation style", default="").strip() or None

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


def _configured_source_root(workspace: Path) -> tuple[Optional[Path], str, dict]:
    ctx = read_yaml(workspace / "research-context.yaml")
    source_config = ctx.get("sources") or {}
    cfg_root = source_config.get("root")
    source_mode = source_config.get("mode") or "local_folder"
    return (Path(cfg_root) if cfg_root else None), source_mode, source_config


def _configured_zotero(workspace: Path) -> dict:
    ctx = read_yaml(workspace / "research-context.yaml")
    return ctx.get("zotero") or {}


def _resolve_zotero_paths(workspace: Path, storage: Optional[Path] = None) -> tuple[Path, Optional[Path], dict]:
    cfg_root, _source_mode, _source_config = _configured_source_root(workspace)
    zotero_config = _configured_zotero(workspace)
    storage_root = storage or (Path(zotero_config["storage"]) if zotero_config.get("storage") else cfg_root)
    if not storage_root:
        raise ValueError("No Zotero storage root configured or provided")
    zotero_root = Path(zotero_config["root"]) if zotero_config.get("root") else zotero_root_from_storage(storage_root)
    return storage_root, zotero_root, zotero_config


def _write_zotero_config(workspace: Path, updates: dict) -> None:
    context_path = workspace / "research-context.yaml"
    ctx = read_yaml(context_path)
    zotero_config = ctx.get("zotero") or {}
    zotero_config.update(updates)
    ctx["zotero"] = zotero_config
    write_yaml(context_path, ctx)


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
    console.print(f"Validate the workspace:\n  [bold]researchboss config validate --workspace {workspace}[/bold]")

    if source_root:
        console.print(
            "Scan your configured sources:\n"
            f"  [bold]researchboss scan --workspace {workspace} --source {source_root}[/bold]"
        )
    else:
        console.print(
            "Scan a source folder when you are ready:\n"
            f"  [bold]researchboss scan --workspace {workspace} --source /path/to/your/sources[/bold]"
        )

    console.print(f"Review pending sources:\n  [bold]researchboss sources review --workspace {workspace}[/bold]")
    console.print(f"Show source counts:\n  [bold]researchboss sources status --workspace {workspace}[/bold]")
    console.print(
        f"List accepted sources:\n  [bold]researchboss sources list --workspace {workspace} --status accepted[/bold]"
    )


@app.command()
def version():
    """Show the installed ResearchBoss version."""
    console.print(f"ResearchBoss {__version__}")


@app.command()
def doctor():
    """Check that ResearchBoss runtime requirements are available."""
    errors = _runtime_check_errors()
    if errors:
        console.print("[red]ResearchBoss runtime check failed.[/red]")
        for error in errors:
            console.print(f"- {error}")
        console.print('\nRun [bold]python -m pip install -e ".[dev]"[/bold] and try again.')
        raise typer.Exit(code=2)

    console.print(f"[green]OK[/green] ResearchBoss {__version__} is ready.")


@app.command()
def init(
    path: Optional[Path] = typer.Argument(None, help="Workspace folder to create (default: ./<project-name>)"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Create a new ResearchBoss workspace (bare minimum wizard)."""
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
        _finish(summary, summary_path, next_action=f"Run `researchboss scan --workspace {workspace}`")
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
        _finish(summary, summary_path, next_action="Use `researchboss sources list` to inspect sources.")
    except Exception as e:
        logger.error("Status failed", operation="status", error=str(e))
        summary.errors += 1
        _finish(summary, summary_path)
        raise

    if quiet:
        return

    table = Table(title="ResearchBoss Status (sources)")
    table.add_column("Status")
    table.add_column("Count", justify="right")
    for k in sorted(counts.keys()):
        table.add_row(k, str(counts[k]))
    console.print(table)


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
        _finish(summary, summary_path, next_action="Run `researchboss init` or fix the workspace path.")
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

    cfg_root, source_mode, source_config = _configured_source_root(ws)
    initial_status = source_config.get("new_source_status", "pending_review")
    provider = kind or source_mode
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

    zotero_config = _configured_zotero(ws)
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
    _finish(summary, summary_path, next_action="Run `researchboss sources review` to accept/ignore/maybe.")

    if not quiet:
        console.print(
            f"[green]Scan complete[/green] processed={result.processed} added={result.added} "
            f"duplicates={result.duplicates} skipped={result.skipped}"
        )


@app.command()
def convert(
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Workspace path (default: CWD)"),
    status: Optional[str] = typer.Option(None, "--status", help="Only convert sources with this review status."),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Convert registered sources into local text files."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["convert"], ws, log_level)

    result = convert_sources(ws, status=status)
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


@zotero_app.command("collections")
def zotero_collections(
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w", help="Workspace path (default: CWD)"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """List collections from local zotero.sqlite without using the Zotero API."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["zotero", "collections"], ws, log_level)
    _storage_root, zotero_root, _zotero_config = _resolve_zotero_paths(ws)
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
    storage_root, zotero_root, _zotero_config = _resolve_zotero_paths(ws, storage=storage)
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
    _storage_root, zotero_root, _zotero_config = _resolve_zotero_paths(ws)
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
        _finish(summary, summary_path, next_action="Run `researchboss zotero collections` to list valid keys.")
        if not quiet:
            console.print(f"[red]Unknown collection keys:[/red] {', '.join(missing)}")
        raise typer.Exit(code=2)

    selected = [{"key": key, "name": known[key].name, "path": known[key].path} for key in collection_keys]
    _write_zotero_config(
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
    _finish(summary, summary_path, next_action="Run `researchboss scan` to scan selected collections.")
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
    _write_zotero_config(ws, {"mode": "entire_library", "selected_collections": []})
    logger.info("Configured entire Zotero library mode", operation="zotero_use_entire_library")
    _finish(summary, summary_path)
    if not quiet:
        console.print("[green]Configured[/green] Zotero entire-library mode.")


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
    storage_root, zotero_root, _zotero_config = _resolve_zotero_paths(ws)
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
    _finish(summary, summary_path, next_action="Run `researchboss sources review` to review discovered sources.")
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

    cfg_root, source_mode, _source_config = _configured_source_root(ws)
    zotero_config = _configured_zotero(ws)
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
    _finish(summary, summary_path, next_action="Run `researchboss scan --kind zotero_storage` to register useful files.")

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
    _storage_root, zotero_root, _zotero_config = _resolve_zotero_paths(ws)
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
    storage_root, zotero_root, _zotero_config = _resolve_zotero_paths(ws)
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
    storage_root, _zotero_root, _zotero_config = _resolve_zotero_paths(ws)
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
    _storage_root, zotero_root, _zotero_config = _resolve_zotero_paths(ws)
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
    _storage_root, zotero_root, _zotero_config = _resolve_zotero_paths(ws)
    if not zotero_root:
        logger.error("Could not derive Zotero root", operation="zotero_snapshot")
        summary.errors += 1
        _finish(summary, summary_path)
        raise typer.Exit(code=2)

    output_path = output or (ws / "sources_metadata" / "zotero-snapshot.yaml")
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
    _storage_root, zotero_root, _zotero_config = _resolve_zotero_paths(ws)
    if not zotero_root:
        logger.error("Could not derive Zotero root", operation="zotero_export_bibtex")
        summary.errors += 1
        _finish(summary, summary_path)
        raise typer.Exit(code=2)

    output_path = output or (ws / "outputs" / "reports" / "zotero-references.bib")
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
    _finish(summary, summary_path, next_action="Run `researchboss sources list --status accepted` to confirm.")
    console.print("[green]Review complete.[/green]")
