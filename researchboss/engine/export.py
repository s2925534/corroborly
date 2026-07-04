from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile

from researchboss.core.yamlio import read_yaml, write_yaml


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
