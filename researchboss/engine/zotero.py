from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Optional


FULLTEXT_CACHE_NAME = ".zotero-ft-cache"
MAX_CACHE_CHARS = 200_000
SNIPPET_RADIUS = 80
ZOTERO_SQLITE_NAME = "zotero.sqlite"


@dataclass(frozen=True)
class ZoteroSearchHit:
    file_path: Path
    storage_key: Optional[str]
    score: int
    matched_terms: list[str]
    matched_in: list[str]
    has_fulltext_cache: bool
    snippet: Optional[str]


@dataclass(frozen=True)
class ZoteroCollection:
    key: str
    name: str
    parent_key: Optional[str]
    path: str
    item_count: int


@dataclass(frozen=True)
class ZoteroAttachmentMetadata:
    attachment_item_key: str
    parent_item_key: Optional[str]
    item_type: Optional[str]
    title: Optional[str]
    creators: list[str]
    year: Optional[str]
    doi: Optional[str]
    url: Optional[str]
    publication_title: Optional[str]
    abstract_note: Optional[str]
    collections: list[dict[str, str]]

    def as_source_fields(self) -> dict[str, Any]:
        return {
            "zotero_attachment_item_key": self.attachment_item_key,
            "zotero_parent_item_key": self.parent_item_key,
            "zotero_item_type": self.item_type,
            "zotero_title": self.title,
            "zotero_creators": self.creators,
            "zotero_year": self.year,
            "zotero_doi": self.doi,
            "zotero_url": self.url,
            "zotero_publication_title": self.publication_title,
            "zotero_abstract_note": self.abstract_note,
            "zotero_collections": self.collections,
        }


def zotero_storage_key(path: Path, storage_root: Path) -> Optional[str]:
    """Return the Zotero storage item folder name for a path under storage_root."""
    try:
        relative = path.resolve().relative_to(storage_root.resolve())
    except ValueError:
        return None

    if not relative.parts:
        return None
    return relative.parts[0]


def zotero_relative_path(path: Path, storage_root: Path) -> Optional[str]:
    try:
        return str(path.resolve().relative_to(storage_root.resolve()))
    except ValueError:
        return None


def zotero_root_from_storage(storage_root: Path) -> Optional[Path]:
    storage_root = storage_root.expanduser()
    if storage_root.name != "storage":
        return None
    return storage_root.parent


def zotero_sqlite_path(zotero_root: Path) -> Path:
    return zotero_root / ZOTERO_SQLITE_NAME


def zotero_sqlite_exists(zotero_root: Path) -> bool:
    return zotero_sqlite_path(zotero_root).is_file()


def zotero_fulltext_cache_path(path: Path, storage_root: Path) -> Optional[Path]:
    key = zotero_storage_key(path, storage_root)
    if not key:
        return None
    return storage_root / key / FULLTEXT_CACHE_NAME


def has_zotero_fulltext_cache(path: Path, storage_root: Path) -> bool:
    cache_path = zotero_fulltext_cache_path(path, storage_root)
    return bool(cache_path and cache_path.is_file())


def read_zotero_fulltext_cache(path: Path, storage_root: Path, *, limit: int = MAX_CACHE_CHARS) -> str:
    cache_path = zotero_fulltext_cache_path(path, storage_root)
    if not cache_path or not cache_path.is_file():
        return ""
    text = cache_path.read_text(encoding="utf-8", errors="replace")
    return text[:limit]


def keyword_terms(query: str | Iterable[str]) -> list[str]:
    if isinstance(query, str):
        raw = query
    else:
        raw = " ".join(query)

    terms = []
    seen = set()
    for term in re.findall(r"[A-Za-z0-9][A-Za-z0-9_-]*", raw.lower()):
        if term not in seen:
            seen.add(term)
            terms.append(term)
    return terms


def _connect_readonly(db_path: Path) -> sqlite3.Connection:
    uri = f"file:{db_path.resolve()}?mode=ro&immutable=1"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _row_value(row: sqlite3.Row | dict[str, Any], key: str) -> Any:
    try:
        return row[key]
    except (KeyError, IndexError):
        return None


def _item_fields(conn: sqlite3.Connection, item_id: int) -> dict[str, str]:
    rows = conn.execute(
        """
        SELECT fields.fieldName, itemDataValues.value
        FROM itemData
        JOIN fields ON fields.fieldID = itemData.fieldID
        JOIN itemDataValues ON itemDataValues.valueID = itemData.valueID
        WHERE itemData.itemID = ?
        """,
        (item_id,),
    ).fetchall()
    return {str(row["fieldName"]): str(row["value"]) for row in rows if row["value"] is not None}


def _item_creators(conn: sqlite3.Connection, item_id: int) -> list[str]:
    rows = conn.execute(
        """
        SELECT creators.firstName, creators.lastName, creators.fieldMode
        FROM itemCreators
        JOIN creators ON creators.creatorID = itemCreators.creatorID
        WHERE itemCreators.itemID = ?
        ORDER BY itemCreators.orderIndex
        """,
        (item_id,),
    ).fetchall()
    creators = []
    for row in rows:
        first = str(row["firstName"] or "").strip()
        last = str(row["lastName"] or "").strip()
        if row["fieldMode"] == 1:
            name = last or first
        else:
            name = " ".join(part for part in [first, last] if part)
        if name:
            creators.append(name)
    return creators


def _year_from_date(date_value: Optional[str]) -> Optional[str]:
    if not date_value:
        return None
    match = re.search(r"\b(1[5-9]\d{2}|20\d{2}|21\d{2})\b", date_value)
    return match.group(1) if match else None


def _collections_by_id(conn: sqlite3.Connection) -> dict[int, dict[str, Any]]:
    rows = conn.execute(
        "SELECT collectionID, collectionName, key, parentCollectionID FROM collections ORDER BY collectionName"
    ).fetchall()
    return {
        int(row["collectionID"]): {
            "id": int(row["collectionID"]),
            "name": str(row["collectionName"] or ""),
            "key": str(row["key"] or ""),
            "parent_id": row["parentCollectionID"],
        }
        for row in rows
    }


def _collection_path(collection_id: int, collections: dict[int, dict[str, Any]]) -> str:
    parts = []
    current: Optional[int] = collection_id
    seen = set()
    while current and current in collections and current not in seen:
        seen.add(current)
        collection = collections[current]
        parts.append(collection["name"])
        current = collection.get("parent_id")
    return " / ".join(reversed([part for part in parts if part]))


def list_zotero_collections(zotero_root: Path) -> list[ZoteroCollection]:
    db_path = zotero_sqlite_path(zotero_root)
    if not db_path.is_file():
        return []

    with _connect_readonly(db_path) as conn:
        collections = _collections_by_id(conn)
        counts = {
            int(row["collectionID"]): int(row["count"])
            for row in conn.execute(
                "SELECT collectionID, COUNT(*) AS count FROM collectionItems GROUP BY collectionID"
            ).fetchall()
        }
        by_id = collections
        result = []
        for collection_id, collection in sorted(by_id.items(), key=lambda item: _collection_path(item[0], by_id).lower()):
            parent_id = collection.get("parent_id")
            parent_key = by_id[int(parent_id)]["key"] if parent_id in by_id else None
            result.append(
                ZoteroCollection(
                    key=collection["key"],
                    name=collection["name"],
                    parent_key=parent_key,
                    path=_collection_path(collection_id, by_id),
                    item_count=counts.get(collection_id, 0),
                )
            )
        return result


def _descendant_collection_ids(
    collections: dict[int, dict[str, Any]],
    selected_ids: set[int],
) -> set[int]:
    descendants = set(selected_ids)
    changed = True
    while changed:
        changed = False
        for collection_id, collection in collections.items():
            parent_id = collection.get("parent_id")
            if parent_id in descendants and collection_id not in descendants:
                descendants.add(collection_id)
                changed = True
    return descendants


def storage_keys_for_collections(
    zotero_root: Path,
    collection_keys: Iterable[str],
    *,
    include_subcollections: bool = True,
) -> set[str]:
    keys = {key for key in collection_keys if key}
    if not keys:
        return set()

    db_path = zotero_sqlite_path(zotero_root)
    if not db_path.is_file():
        return set()

    with _connect_readonly(db_path) as conn:
        collections = _collections_by_id(conn)
        selected_ids = {cid for cid, collection in collections.items() if collection["key"] in keys}
        if include_subcollections:
            selected_ids = _descendant_collection_ids(collections, selected_ids)
        if not selected_ids:
            return set()

        placeholders = ",".join("?" for _ in selected_ids)
        parent_rows = conn.execute(
            f"SELECT DISTINCT itemID FROM collectionItems WHERE collectionID IN ({placeholders})",
            tuple(selected_ids),
        ).fetchall()
        parent_ids = {int(row["itemID"]) for row in parent_rows}
        if not parent_ids:
            return set()

        item_placeholders = ",".join("?" for _ in parent_ids)
        rows = conn.execute(
            f"""
            SELECT items.key
            FROM itemAttachments
            JOIN items ON items.itemID = itemAttachments.itemID
            WHERE itemAttachments.parentItemID IN ({item_placeholders})
            """,
            tuple(parent_ids),
        ).fetchall()
        return {str(row["key"]) for row in rows if row["key"]}


def _item_collections(conn: sqlite3.Connection, item_id: int) -> list[dict[str, str]]:
    collections = _collections_by_id(conn)
    rows = conn.execute("SELECT collectionID FROM collectionItems WHERE itemID = ?", (item_id,)).fetchall()
    result = []
    for row in rows:
        collection_id = int(row["collectionID"])
        collection = collections.get(collection_id)
        if collection:
            result.append(
                {
                    "key": collection["key"],
                    "name": collection["name"],
                    "path": _collection_path(collection_id, collections),
                }
            )
    return result


def attachment_metadata_by_storage_key(
    zotero_root: Path,
    storage_key: str,
) -> Optional[ZoteroAttachmentMetadata]:
    db_path = zotero_sqlite_path(zotero_root)
    if not storage_key or not db_path.is_file():
        return None

    with _connect_readonly(db_path) as conn:
        attachment = conn.execute(
            """
            SELECT attachments.itemID AS attachmentItemID,
                   attachmentItems.key AS attachmentKey,
                   attachments.parentItemID AS parentItemID,
                   parentItems.key AS parentKey
            FROM itemAttachments AS attachments
            JOIN items AS attachmentItems ON attachmentItems.itemID = attachments.itemID
            LEFT JOIN items AS parentItems ON parentItems.itemID = attachments.parentItemID
            WHERE attachmentItems.key = ?
            """,
            (storage_key,),
        ).fetchone()
        if not attachment:
            return None

        item_id = attachment["parentItemID"] or attachment["attachmentItemID"]
        item = conn.execute(
            """
            SELECT items.itemID, items.key, itemTypes.typeName
            FROM items
            LEFT JOIN itemTypes ON itemTypes.itemTypeID = items.itemTypeID
            WHERE items.itemID = ?
            """,
            (item_id,),
        ).fetchone()
        if not item:
            return None

        fields = _item_fields(conn, int(item["itemID"]))
        title = fields.get("title")
        date_value = fields.get("date")
        return ZoteroAttachmentMetadata(
            attachment_item_key=str(attachment["attachmentKey"]),
            parent_item_key=str(attachment["parentKey"]) if attachment["parentKey"] else None,
            item_type=str(item["typeName"]) if item["typeName"] else None,
            title=title,
            creators=_item_creators(conn, int(item["itemID"])),
            year=_year_from_date(date_value),
            doi=fields.get("DOI"),
            url=fields.get("url"),
            publication_title=fields.get("publicationTitle"),
            abstract_note=fields.get("abstractNote"),
            collections=_item_collections(conn, int(item["itemID"])),
        )


def all_attachment_metadata(zotero_root: Path) -> list[ZoteroAttachmentMetadata]:
    db_path = zotero_sqlite_path(zotero_root)
    if not db_path.is_file():
        return []

    with _connect_readonly(db_path) as conn:
        rows = conn.execute(
            """
            SELECT items.key
            FROM itemAttachments
            JOIN items ON items.itemID = itemAttachments.itemID
            ORDER BY items.key
            """
        ).fetchall()
    metadata = []
    for row in rows:
        item = attachment_metadata_by_storage_key(zotero_root, str(row["key"]))
        if item:
            metadata.append(item)
    return metadata


def metadata_quality_report(zotero_root: Path) -> dict[str, Any]:
    items = all_attachment_metadata(zotero_root)
    missing_title = [item.attachment_item_key for item in items if not item.title]
    missing_year = [item.attachment_item_key for item in items if not item.year]
    missing_doi = [item.attachment_item_key for item in items if not item.doi]
    missing_creators = [item.attachment_item_key for item in items if not item.creators]
    return {
        "total_attachments": len(items),
        "missing_title": missing_title,
        "missing_year": missing_year,
        "missing_doi": missing_doi,
        "missing_creators": missing_creators,
    }


def attachment_health_report(zotero_root: Path, storage_root: Path, source_paths: Iterable[Path]) -> dict[str, Any]:
    source_keys = {key for path in source_paths if (key := zotero_storage_key(path, storage_root))}
    metadata_keys = {item.attachment_item_key for item in all_attachment_metadata(zotero_root)}
    missing_files = sorted(metadata_keys - source_keys)
    unlinked_files = sorted(source_keys - metadata_keys)
    return {
        "storage_files": len(source_keys),
        "sqlite_attachments": len(metadata_keys),
        "missing_attachment_files": missing_files,
        "unlinked_storage_files": unlinked_files,
    }


def fulltext_availability_report(storage_root: Path, source_paths: Iterable[Path]) -> dict[str, Any]:
    paths = list(source_paths)
    with_cache = [path for path in paths if has_zotero_fulltext_cache(path, storage_root)]
    without_cache = [path for path in paths if not has_zotero_fulltext_cache(path, storage_root)]
    return {
        "total_sources": len(paths),
        "with_fulltext_cache": len(with_cache),
        "without_fulltext_cache": len(without_cache),
        "without_fulltext_cache_files": [str(path) for path in without_cache],
    }


def duplicate_metadata_candidates(zotero_root: Path) -> list[dict[str, Any]]:
    items = all_attachment_metadata(zotero_root)
    buckets: dict[tuple[str, str], list[ZoteroAttachmentMetadata]] = {}
    for item in items:
        if item.doi:
            key = ("doi", item.doi.lower())
        elif item.title and item.year:
            key = ("title_year", f"{item.title.lower()}::{item.year}")
        else:
            continue
        buckets.setdefault(key, []).append(item)

    duplicates = []
    for (kind, value), bucket in buckets.items():
        if len(bucket) < 2:
            continue
        duplicates.append(
            {
                "match_type": kind,
                "match_value": value,
                "items": [item.as_source_fields() for item in bucket],
            }
        )
    return duplicates


def zotero_metadata_snapshot(zotero_root: Path) -> dict[str, Any]:
    return {
        "version": 1,
        "zotero_root": str(zotero_root),
        "collections": [collection.__dict__ for collection in list_zotero_collections(zotero_root)],
        "attachments": [item.as_source_fields() for item in all_attachment_metadata(zotero_root)],
    }


def _bibtex_key(item: ZoteroAttachmentMetadata) -> str:
    author = "source"
    if item.creators:
        author = re.sub(r"[^A-Za-z0-9]+", "", item.creators[0].split()[-1].lower()) or "source"
    title = "untitled"
    if item.title:
        title_terms = keyword_terms(item.title)
        title = title_terms[0] if title_terms else "untitled"
    year = item.year or "nd"
    return f"{author}_{title}_{year}"


def _bibtex_entry_type(item_type: Optional[str]) -> str:
    if item_type in {"journalArticle", "conferencePaper"}:
        return "article"
    if item_type == "book":
        return "book"
    if item_type == "thesis":
        return "phdthesis"
    return "misc"


def _escape_bibtex(value: str) -> str:
    return value.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")


def export_bibtex_from_metadata(zotero_root: Path) -> str:
    entries = []
    used_keys: dict[str, int] = {}
    for item in all_attachment_metadata(zotero_root):
        if not item.title:
            continue
        base_key = _bibtex_key(item)
        used_keys[base_key] = used_keys.get(base_key, 0) + 1
        key = base_key if used_keys[base_key] == 1 else f"{base_key}_{used_keys[base_key]}"
        fields = {
            "title": item.title,
            "author": " and ".join(item.creators) if item.creators else None,
            "year": item.year,
            "doi": item.doi,
            "url": item.url,
            "journal": item.publication_title,
        }
        lines = [f"@{_bibtex_entry_type(item.item_type)}{{{key},"]
        for field, value in fields.items():
            if value:
                lines.append(f"  {field} = {{{_escape_bibtex(value)}}},")
        lines.append("}")
        entries.append("\n".join(lines))
    return "\n\n".join(entries) + ("\n" if entries else "")


def _snippet(text: str, term: str) -> Optional[str]:
    lower = text.lower()
    index = lower.find(term.lower())
    if index < 0:
        return None
    start = max(0, index - SNIPPET_RADIUS)
    end = min(len(text), index + len(term) + SNIPPET_RADIUS)
    snippet = " ".join(text[start:end].split())
    return snippet or None


def score_zotero_relevance(file_path: Path, storage_root: Path, terms: list[str]) -> ZoteroSearchHit:
    name_text = file_path.name.lower()
    cache_text = read_zotero_fulltext_cache(file_path, storage_root)
    cache_lower = cache_text.lower()

    score = 0
    matched_terms: list[str] = []
    matched_in: list[str] = []
    first_snippet: Optional[str] = None

    for term in terms:
        term_score = 0
        locations = []
        if term in name_text:
            term_score += 10
            locations.append("filename")
        if term in cache_lower:
            term_score += 3
            locations.append("fulltext_cache")
            if first_snippet is None:
                first_snippet = _snippet(cache_text, term)

        if term_score:
            score += term_score
            matched_terms.append(term)
            for location in locations:
                if location not in matched_in:
                    matched_in.append(location)

    return ZoteroSearchHit(
        file_path=file_path,
        storage_key=zotero_storage_key(file_path, storage_root),
        score=score,
        matched_terms=matched_terms,
        matched_in=matched_in,
        has_fulltext_cache=has_zotero_fulltext_cache(file_path, storage_root),
        snippet=first_snippet,
    )


def search_zotero_storage(
    storage_root: Path,
    terms: list[str],
    file_paths: Iterable[Path],
    *,
    limit: int = 10,
) -> list[ZoteroSearchHit]:
    hits = [score_zotero_relevance(path, storage_root, terms) for path in file_paths]
    hits = [hit for hit in hits if hit.score > 0]
    hits.sort(key=lambda hit: (-hit.score, str(hit.file_path).lower()))
    return hits[:limit]
