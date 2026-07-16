from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile

from ledgerly.core.yamlio import read_yaml, write_yaml


EVIDENCE_FILES = [
    "accepted-sources.yaml",
    "source-register.yaml",
    "claims-ledger.yaml",
    "research-questions.yaml",
    "research-question-candidates.yaml",
    "artefact-registry.yaml",
]


@dataclass(frozen=True)
class CorpusExport:
    corpus_path: Path
    manifest_path: Path
    included_count: int
    skipped_count: int


def export_evidence_bundle(workspace: Path) -> Path:
    output_dir = workspace / "outputs" / "reports"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "evidence-bundle.zip"
    accepted = set(read_yaml(workspace / "accepted-sources.yaml").get("source_ids", []))
    register = read_yaml(workspace / "source-register.yaml")
    accepted_sources = [
        source
        for source in register.get("sources", [])
        if isinstance(source, dict) and source.get("source_id") in accepted
    ]
    manifest = {
        "version": 1,
        "includes_original_files": False,
        "accepted_source_count": len(accepted_sources),
        "contents": EVIDENCE_FILES + ["outputs/data-profiles/*.yaml"],
    }
    manifest_path = workspace / "outputs" / "reports" / "evidence-bundle-manifest.yaml"
    write_yaml(manifest_path, manifest)

    with ZipFile(output_path, "w", compression=ZIP_DEFLATED) as zf:
        zf.write(manifest_path, "manifest.yaml")
        zf.writestr("accepted-source-records.yaml", _yaml_text({"version": 1, "sources": accepted_sources}))
        for relative in EVIDENCE_FILES:
            path = workspace / relative
            if path.is_file():
                zf.write(path, relative)
        profile_dir = workspace / "outputs" / "data-profiles"
        if profile_dir.is_dir():
            for path in sorted(profile_dir.glob("*.yaml")):
                zf.write(path, path.relative_to(workspace).as_posix())
    return output_path


def export_accepted_source_corpus(workspace: Path) -> CorpusExport:
    output_dir = workspace / "outputs" / "reports"
    output_dir.mkdir(parents=True, exist_ok=True)
    corpus_path = output_dir / "accepted-source-corpus.txt"
    manifest_path = output_dir / "accepted-source-corpus-manifest.yaml"

    accepted = set(read_yaml(workspace / "accepted-sources.yaml").get("source_ids", []))
    register = read_yaml(workspace / "source-register.yaml")
    included = []
    skipped = []
    sections = []
    for source in register.get("sources", []):
        if not isinstance(source, dict) or source.get("source_id") not in accepted:
            continue
        conversion = source.get("conversion") if isinstance(source.get("conversion"), dict) else {}
        text_path = Path(str(conversion.get("output_path") or ""))
        if not text_path.is_file():
            skipped.append(
                {
                    "source_id": source.get("source_id"),
                    "reason": "converted_text_missing",
                    "text_path": str(text_path) if str(text_path) != "." else None,
                }
            )
            continue
        text = text_path.read_text(encoding="utf-8", errors="replace").strip()
        if not text:
            skipped.append({"source_id": source.get("source_id"), "reason": "converted_text_empty", "text_path": str(text_path)})
            continue
        header = _corpus_header(source, text_path)
        sections.append(header + "\n\n" + text + "\n")
        included.append(_corpus_manifest_record(source, text_path, len(text)))

    corpus_path.write_text(("\n" + "=" * 80 + "\n\n").join(sections), encoding="utf-8")
    manifest = {
        "version": 1,
        "includes_original_files": False,
        "corpus_path": str(corpus_path),
        "included_count": len(included),
        "skipped_count": len(skipped),
        "included_sources": included,
        "skipped_sources": skipped,
        "notes": "The corpus is built from workspace converted text for accepted sources only.",
    }
    write_yaml(manifest_path, manifest)
    return CorpusExport(corpus_path=corpus_path, manifest_path=manifest_path, included_count=len(included), skipped_count=len(skipped))


def _corpus_header(source: dict[str, Any], text_path: Path) -> str:
    metadata = source.get("citation_metadata") if isinstance(source.get("citation_metadata"), dict) else {}
    title = source.get("zotero_title") or metadata.get("title") or source.get("file_name") or "Unknown title"
    authors = source.get("zotero_creators") or metadata.get("authors") or "Unknown authors"
    if isinstance(authors, list):
        authors = "; ".join(str(author) for author in authors) or "Unknown authors"
    year = source.get("zotero_year") or metadata.get("year") or "Unknown year"
    lines = [
        f"Source ID: {source.get('source_id')}",
        f"Title: {title}",
        f"Authors: {authors}",
        f"Year: {year}",
        f"Converted text path: {text_path}",
    ]
    return "\n".join(lines)


def _corpus_manifest_record(source: dict[str, Any], text_path: Path, character_count: int) -> dict[str, Any]:
    metadata = source.get("citation_metadata") if isinstance(source.get("citation_metadata"), dict) else {}
    return {
        "source_id": source.get("source_id"),
        "title": source.get("zotero_title") or metadata.get("title") or source.get("file_name"),
        "authors": source.get("zotero_creators") or metadata.get("authors"),
        "year": source.get("zotero_year") or metadata.get("year"),
        "text_path": str(text_path),
        "character_count": character_count,
    }


def _yaml_text(data: object) -> str:
    import yaml

    return yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=120)


def _gather_supervisor_bundle_data(workspace: Path) -> dict[str, Any]:
    """The data both `build_supervisor_bundle` (Markdown) and
    `build_supervisor_bundle_html` (HTML) render -- gathered once so the two
    output formats can never silently drift out of sync with each other.
    """
    from ledgerly.engine.ai import list_ai_usage
    from ledgerly.engine.claims import citation_gap_claims, claim_source_validation_report, list_claims
    from ledgerly.engine.reports import generate_workspace_report

    workspace_report_path = generate_workspace_report(workspace)
    claims = list_claims(workspace)
    gap_ids = {claim.get("id") for claim in citation_gap_claims(workspace)}
    validation = claim_source_validation_report(workspace)
    issues_by_claim = {row.get("claim_id"): row.get("issues", []) for row in validation.get("claims", [])}

    plan_dir = workspace / "outputs" / "citation-plans"
    plan_paths = sorted(plan_dir.glob("citation-plan-*.md")) if plan_dir.is_dir() else []

    return {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "workspace_report_path": workspace_report_path,
        "claims": claims,
        "gap_ids": gap_ids,
        "issues_by_claim": issues_by_claim,
        "plan_paths": plan_paths,
        "ai_usage": list_ai_usage(workspace),
    }


def build_supervisor_bundle(workspace: Path) -> Path:
    """A single self-contained "hand this to my supervisor" bundle: the claim
    ledger, every citation plan created so far, and the workspace review
    report, as one readable Markdown digest plus a zip. Deliberately Markdown
    + zip rather than PDF — no PDF-generation dependency exists anywhere in
    this project today, and a Markdown digest is trivially convertible to
    PDF by the supervisor (or the user) with whatever tool they already have.
    """
    output_dir = workspace / "outputs" / "reports"
    output_dir.mkdir(parents=True, exist_ok=True)

    data = _gather_supervisor_bundle_data(workspace)
    workspace_report_path = data["workspace_report_path"]
    claims = data["claims"]
    gap_ids = data["gap_ids"]
    issues_by_claim = data["issues_by_claim"]
    plan_paths = data["plan_paths"]
    ai_usage = data["ai_usage"]

    lines = [
        "# Supervisor Review Bundle",
        "",
        f"Generated: {data['generated_at']}",
        "",
        "## Claim Ledger",
        "",
        "| ID | Status | Citation gap | Sources | Issues | Text |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for claim in claims:
        claim_id = claim.get("id", "")
        issue_count = len(issues_by_claim.get(claim_id, []))
        text = (claim.get("text") or "").replace("|", "\\|")
        lines.append(
            f"| {claim_id} | {claim.get('status', '')} | {'yes' if claim_id in gap_ids else 'no'} | "
            f"{len(claim.get('linked_sources', []))} | {issue_count} | {text} |"
        )
    if not claims:
        lines.append("| _none recorded yet_ | | | | | |")

    lines.extend(["", "## Citation Plans", ""])
    if plan_paths:
        for plan_path in plan_paths:
            lines.extend([f"### {plan_path.stem}", "", plan_path.read_text(encoding="utf-8").strip(), ""])
    else:
        lines.append("No citation plans created yet.")

    lines.extend(["", "## Workspace Review Report", "", workspace_report_path.read_text(encoding="utf-8").strip(), ""])

    lines.extend(["", "## AI Usage Disclosure", ""])
    if ai_usage:
        used_count = sum(1 for entry in ai_usage if entry.get("ai_used"))
        refused_count = sum(1 for entry in ai_usage if entry.get("insufficient_evidence"))
        grounded_count = sum(1 for entry in ai_usage if entry.get("grounding_fully_grounded") is True)
        ungrounded_count = sum(1 for entry in ai_usage if entry.get("grounding_fully_grounded") is False)
        lines.append(
            f"{len(ai_usage)} AI call(s) recorded against this workspace: {used_count} actually used an AI "
            f"provider, {refused_count} correctly refused with insufficient evidence (no call made). Of the "
            f"calls that used AI, {grounded_count} passed the deterministic grounding check fully and "
            f"{ungrounded_count} had at least one citation flagged as not traceable to the supplied context "
            "and require extra scrutiny before trusting. Every call required explicit per-request opt-in — "
            "AI is never invoked automatically or in the background."
        )
        lines.extend(["", "| Timestamp | Kind | AI used | Grounded | Model |", "| --- | --- | --- | --- | --- |"])
        for entry in ai_usage:
            grounded = entry.get("grounding_fully_grounded")
            grounded_label = "n/a" if grounded is None else ("yes" if grounded else "no")
            lines.append(
                f"| {entry.get('timestamp', '')} | {entry.get('kind', '')} | "
                f"{'yes' if entry.get('ai_used') else 'no'} | {grounded_label} | {entry.get('model') or ''} |"
            )
    else:
        lines.append("No AI features have been used in this workspace.")

    digest_path = output_dir / "supervisor-bundle.md"
    digest_path.write_text("\n".join(lines), encoding="utf-8")

    bundle_path = output_dir / "supervisor-bundle.zip"
    with ZipFile(bundle_path, "w", compression=ZIP_DEFLATED) as zf:
        zf.write(digest_path, digest_path.name)
        zf.write(workspace_report_path, workspace_report_path.name)
        zf.writestr("claims-ledger.yaml", _yaml_text({"version": 1, "claims": claims}))
        zf.writestr("ai-usage-ledger.yaml", _yaml_text({"version": 1, "entries": ai_usage}))
        for plan_path in plan_paths:
            zf.write(plan_path, plan_path.relative_to(workspace).as_posix())
        html_path = build_supervisor_bundle_html(workspace)
        zf.write(html_path, html_path.name)
    return bundle_path


_SUPERVISOR_BUNDLE_HTML_STYLE = """
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; max-width: 960px; margin: 2rem auto; padding: 0 1.5rem; line-height: 1.5; color: #1a1a1a; }
h1, h2, h3 { color: #111; }
table { border-collapse: collapse; width: 100%; margin: 1rem 0; }
th, td { border: 1px solid #ccc; padding: 0.4rem 0.6rem; text-align: left; vertical-align: top; font-size: 0.9rem; }
th { background: #f2f2f2; }
pre { background: #f7f7f7; border: 1px solid #ddd; padding: 1rem; overflow-x: auto; white-space: pre-wrap; }
.muted { color: #666; font-size: 0.9rem; }
@media (prefers-color-scheme: dark) {
  body { background: #12141a; color: #e4e6eb; }
  h1, h2, h3 { color: #f2f2f2; }
  th { background: #1e2028; }
  th, td { border-color: #333; }
  pre { background: #1a1c22; border-color: #333; }
  .muted { color: #9aa0a6; }
}
"""


def build_supervisor_bundle_html(workspace: Path) -> Path:
    """A fully self-contained, no-install HTML viewer for the same content
    `build_supervisor_bundle` writes as Markdown -- a supervisor or co-author
    without Ledgerly installed can open this by double-clicking rather than
    needing a Markdown renderer. Inline CSS only, no external assets, no JS.
    Long-form blocks (citation plans, the workspace review report) are
    already-formatted Markdown text -- shown verbatim in `<pre>` blocks
    rather than re-parsed, an honest simplification rather than a from-
    scratch Markdown-to-HTML renderer.
    """
    import html as html_module

    output_dir = workspace / "outputs" / "reports"
    output_dir.mkdir(parents=True, exist_ok=True)
    data = _gather_supervisor_bundle_data(workspace)
    esc = html_module.escape

    claim_rows = "".join(
        f"<tr><td>{esc(claim.get('id', ''))}</td><td>{esc(claim.get('status', ''))}</td>"
        f"<td>{'yes' if claim.get('id') in data['gap_ids'] else 'no'}</td>"
        f"<td>{len(claim.get('linked_sources', []))}</td>"
        f"<td>{len(data['issues_by_claim'].get(claim.get('id'), []))}</td>"
        f"<td>{esc(claim.get('text') or '')}</td></tr>"
        for claim in data["claims"]
    ) or "<tr><td colspan='6'><em>None recorded yet.</em></td></tr>"

    if data["plan_paths"]:
        plan_sections = "".join(
            f"<h3>{esc(plan_path.stem)}</h3><pre>{esc(plan_path.read_text(encoding='utf-8').strip())}</pre>"
            for plan_path in data["plan_paths"]
        )
    else:
        plan_sections = "<p class='muted'>No citation plans created yet.</p>"

    ai_usage = data["ai_usage"]
    if ai_usage:
        used_count = sum(1 for entry in ai_usage if entry.get("ai_used"))
        refused_count = sum(1 for entry in ai_usage if entry.get("insufficient_evidence"))
        grounded_count = sum(1 for entry in ai_usage if entry.get("grounding_fully_grounded") is True)
        ungrounded_count = sum(1 for entry in ai_usage if entry.get("grounding_fully_grounded") is False)
        ai_summary = (
            f"<p>{len(ai_usage)} AI call(s) recorded against this workspace: {used_count} actually used an AI "
            f"provider, {refused_count} correctly refused with insufficient evidence (no call made). Of the "
            f"calls that used AI, {grounded_count} passed the deterministic grounding check fully and "
            f"{ungrounded_count} had at least one citation flagged as not traceable to the supplied context "
            "and require extra scrutiny before trusting. Every call required explicit per-request opt-in — "
            "AI is never invoked automatically or in the background.</p>"
        )
        ai_rows = "".join(
            f"<tr><td>{esc(entry.get('timestamp', ''))}</td><td>{esc(entry.get('kind', ''))}</td>"
            f"<td>{'yes' if entry.get('ai_used') else 'no'}</td>"
            f"<td>{'n/a' if entry.get('grounding_fully_grounded') is None else ('yes' if entry.get('grounding_fully_grounded') else 'no')}</td>"
            f"<td>{esc(entry.get('model') or '')}</td></tr>"
            for entry in ai_usage
        )
        ai_section = (
            f"{ai_summary}<table><thead><tr><th>Timestamp</th><th>Kind</th><th>AI used</th>"
            f"<th>Grounded</th><th>Model</th></tr></thead><tbody>{ai_rows}</tbody></table>"
        )
    else:
        ai_section = "<p class='muted'>No AI features have been used in this workspace.</p>"

    html_doc = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Supervisor Review Bundle</title>
<style>{_SUPERVISOR_BUNDLE_HTML_STYLE}</style></head>
<body>
<h1>Supervisor Review Bundle</h1>
<p class="muted">Generated: {esc(data['generated_at'])}</p>

<h2>Claim Ledger</h2>
<table><thead><tr><th>ID</th><th>Status</th><th>Citation gap</th><th>Sources</th><th>Issues</th><th>Text</th></tr></thead>
<tbody>{claim_rows}</tbody></table>

<h2>Citation Plans</h2>
{plan_sections}

<h2>Workspace Review Report</h2>
<pre>{esc(data['workspace_report_path'].read_text(encoding='utf-8').strip())}</pre>

<h2>AI Usage Disclosure</h2>
{ai_section}
</body></html>
"""
    html_path = output_dir / "supervisor-bundle.html"
    html_path.write_text(html_doc, encoding="utf-8")
    return html_path
