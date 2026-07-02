from __future__ import annotations

from pathlib import Path
from typing import Optional

import click
import typer
from rich.console import Console
from rich.progress import BarColumn, Progress, TaskProgressColumn, TextColumn, TimeElapsedColumn
from rich.table import Table

from researchboss.core.runlog import JsonlLogger, RunSummary, make_run_paths, write_run_summary
from researchboss.core.yamlio import read_yaml
from researchboss.engine.sources import (
    ScanResult,
    iter_source_files,
    list_sources,
    scan_sources,
    set_source_status,
    source_counts,
)
from researchboss.engine.workspace import (
    PROJECT_TYPES,
    default_documents_dir,
    find_default_zotero_storage,
    infer_source_mode,
    init_workspace,
)

app = typer.Typer(add_completion=False, help="ResearchBoss (Phase 1 foundation).")
sources_app = typer.Typer(help="Source inbox + register commands.")
config_app = typer.Typer(help="Config commands.")

app.add_typer(sources_app, name="sources")
app.add_typer(config_app, name="config")

console = Console()
DEFAULT_WORKSPACES_DIR = "workspaces"


def _resolve_workspace(workspace: Optional[Path]) -> Path:
    return workspace or Path.cwd()


def _command_slug(parts: list[str]) -> str:
    return "__".join(parts).replace("-", "_")


def _workspace_slug(project_name: str) -> str:
    return "".join(ch if ch.isalnum() or ch in ("-", "_") else "-" for ch in project_name).strip("-") or "workspace"


def _default_workspace_path(project_name: str) -> Path:
    return Path.cwd() / DEFAULT_WORKSPACES_DIR / _workspace_slug(project_name)


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


@app.command()
def init(
    path: Optional[Path] = typer.Argument(None, help="Workspace folder to create (default: ./<project-name>)"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Create a new ResearchBoss workspace (bare minimum wizard)."""
    project_name = typer.prompt("Project name")
    project_type = typer.prompt("Project type", type=click.Choice(PROJECT_TYPES), default=PROJECT_TYPES[0])
    topic = typer.prompt("Research topic / short description", default="")
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

    workspace = path or _default_workspace_path(project_name)

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
        )
        logger.info("Workspace created", operation="init", workspace=str(workspace))
        _finish(summary, summary_path, next_action=f"Run `researchboss scan --workspace {workspace}`")
    except Exception as e:
        logger.error("Init failed", operation="init", error=str(e))
        summary.errors += 1
        _finish(summary, summary_path, next_action="Fix the error and rerun init")
        raise

    if not quiet:
        console.print(f"[green]Workspace created:[/green] {workspace}")
        console.print(f"Next: run [bold]researchboss scan --workspace {workspace}[/bold]")


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
    kind: str = typer.Option("local_folder", "--kind", help="local_folder | zotero_storage"),
    log_level: str = typer.Option("info", "--log-level", help="debug|info|warning|error"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce console output (still logs/run summary)."),
):
    """Scan local folder or Zotero storage folder and register new sources as pending_review."""
    ws = _resolve_workspace(workspace)
    _slug, logger, summary, summary_path, _log_path = _run_ctx(["scan"], ws, log_level)

    ctx = read_yaml(ws / "research-context.yaml")
    cfg_root = (ctx.get("sources") or {}).get("root")
    scan_root = source or (Path(cfg_root) if cfg_root else None)
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

    candidates = list(iter_source_files(scan_root))
    total = max(1, len(candidates))  # safe zero handling

    if not quiet:
        console.print(f"Scanning: {scan_root}  (kind={kind})")
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

        result: ScanResult = scan_sources(ws, scan_root, provider=kind, logger=logger, file_paths=candidates)

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
