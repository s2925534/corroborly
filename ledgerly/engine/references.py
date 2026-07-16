from __future__ import annotations

import re
from typing import Any


CITATION_STYLES = {"apa7", "mla", "chicago", "ieee"}


def apa7_reference(metadata: dict[str, Any]) -> str:
    authors = _authors(metadata.get("authors"))
    year = _year(metadata.get("year"))
    title = _field(metadata.get("title"), "Unknown title")
    venue = _field(metadata.get("publication_venue") or metadata.get("source_title"), "")
    doi = _doi(metadata.get("doi"))

    reference = f"{authors} ({year}). {title}."
    if venue:
        reference += f" {venue}."
    if doi:
        reference += f" {doi}"
    return reference


def mla_reference(metadata: dict[str, Any]) -> str:
    """A simplified, common approximation of MLA 9th-edition works-cited
    formatting -- not a full style-guide-compliant implementation (no
    container/publisher/access-date handling). Flag for the researcher to
    verify against their institution's exact style guide before submission,
    the same way this project never presents any AI output as final.
    """
    authors = _authors(metadata.get("authors"))
    title = _field(metadata.get("title"), "Unknown title")
    venue = _field(metadata.get("publication_venue") or metadata.get("source_title"), "")
    year = _year(metadata.get("year"))
    doi = _doi(metadata.get("doi"))

    reference = f'{authors}. "{title}."'
    if venue:
        reference += f" {venue},"
    reference += f" {year}."
    if doi:
        reference += f" {doi}"
    return reference


def chicago_reference(metadata: dict[str, Any]) -> str:
    """Chicago author-date reference-list format (the variant compatible
    with this project's author-date inline citations) -- simplified, same
    caveat as `mla_reference`.
    """
    authors = _authors(metadata.get("authors"))
    year = _year(metadata.get("year"))
    title = _field(metadata.get("title"), "Unknown title")
    venue = _field(metadata.get("publication_venue") or metadata.get("source_title"), "")
    doi = _doi(metadata.get("doi"))

    reference = f'{authors}. {year}. "{title}."'
    if venue:
        reference += f" {venue}."
    if doi:
        reference += f" {doi}"
    return reference


def ieee_reference(metadata: dict[str, Any], *, number: int | None = None) -> str:
    """IEEE numbered reference-list format -- simplified, same caveat as
    `mla_reference`. `number` is the reference's position in the citing
    document's own numbering sequence (assigned by the caller, e.g.
    `engine.citations.create_citation_plan`), not a global ID.
    """
    authors = _authors(metadata.get("authors"))
    title = _field(metadata.get("title"), "Unknown title")
    venue = _field(metadata.get("publication_venue") or metadata.get("source_title"), "")
    year = _year(metadata.get("year"))
    doi = _doi(metadata.get("doi"))

    prefix = f"[{number}] " if number is not None else ""
    reference = f'{prefix}{authors}, "{title},"'
    if venue:
        reference += f" {venue},"
    reference += f" {year}."
    if doi:
        reference += f" {doi}"
    return reference


def format_reference(metadata: dict[str, Any], style: str = "apa7", *, number: int | None = None) -> str:
    if style not in CITATION_STYLES:
        raise ValueError(f"Unknown citation style: {style}. Expected one of: {', '.join(sorted(CITATION_STYLES))}")
    if style == "apa7":
        return apa7_reference(metadata)
    if style == "mla":
        return mla_reference(metadata)
    if style == "chicago":
        return chicago_reference(metadata)
    return ieee_reference(metadata, number=number)


def format_inline_citation(metadata: dict[str, Any], style: str = "apa7", *, number: int | None = None) -> str:
    """The short in-text marker for a source, per style. IEEE's numbered
    bracket form requires a `number` (the reference's position in this
    document's own numbering sequence) -- callers that don't have one yet
    get a `[?]` placeholder rather than a silently wrong number.
    """
    if style not in CITATION_STYLES:
        raise ValueError(f"Unknown citation style: {style}. Expected one of: {', '.join(sorted(CITATION_STYLES))}")
    if style == "ieee":
        return f"[{number}]" if number is not None else "[?]"
    author = _first_author(metadata.get("authors"))
    year = _year(metadata.get("year"))
    if style == "apa7":
        return f"({author}, {year})"
    if style == "mla":
        # True MLA in-text citation uses author + page number, not year; this
        # project doesn't track page numbers, so the year is omitted rather
        # than fabricated.
        return f"({author})"
    return f"({author} {year})"


def _first_author(value: Any) -> str:
    if value in (None, "", [], "Unknown"):
        return "Unknown author"
    if isinstance(value, list):
        value = value[0] if value else "Unknown author"
    text = str(value)
    if "," in text:
        return text.split(",", 1)[0].strip() or "Unknown author"
    parts = re.split(r"\s+", text.strip())
    return parts[-1] if parts else "Unknown author"


def _authors(value: Any) -> str:
    if value in (None, "", [], "Unknown"):
        return "Unknown author"
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        names = []
        for item in value:
            if isinstance(item, dict):
                name = item.get("authname") or item.get("name") or item.get("creator") or item.get("last_name")
            else:
                name = str(item)
            if name:
                names.append(str(name))
        if names:
            return ", ".join(names)
    return "Unknown author"


def _year(value: Any) -> str:
    if value in (None, "", "Unknown"):
        return "n.d."
    return str(value)


def _field(value: Any, fallback: str) -> str:
    if value in (None, "", [], "Unknown"):
        return fallback
    return str(value)


def _doi(value: Any) -> str:
    if value in (None, "", "Unknown"):
        return ""
    doi = str(value).strip()
    if doi.startswith("http://") or doi.startswith("https://"):
        return doi
    return f"https://doi.org/{doi}"
