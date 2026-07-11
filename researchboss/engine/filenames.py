from __future__ import annotations

import re
from typing import Any


def safe_filename_token(value: str, *, fallback: str) -> str:
    text = re.sub(r"[^A-Za-z0-9]+", "-", value.lower()).strip("-")
    text = re.sub(r"-{2,}", "-", text)
    return (text or fallback)[:60]


def author_token(authors: list[Any]) -> str:
    if not authors:
        return "unknown-author"
    first = str(authors[0])
    if "," in first:
        return first.split(",", 1)[0].strip()
    parts = first.split()
    return parts[-1] if parts else "unknown-author"
