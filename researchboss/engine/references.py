from __future__ import annotations

from typing import Any


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
