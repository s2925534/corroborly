from pathlib import Path
import sqlite3

from researchboss.engine.zotero import (
    attachment_health_report,
    attachment_metadata_by_storage_key,
    duplicate_metadata_candidates,
    export_bibtex_from_metadata,
    fulltext_availability_report,
    has_zotero_fulltext_cache,
    keyword_terms,
    list_zotero_collections,
    metadata_quality_report,
    score_zotero_relevance,
    search_zotero_storage,
    storage_keys_for_collections,
    zotero_metadata_snapshot,
    zotero_relative_path,
    zotero_root_from_storage,
    zotero_storage_key,
)


def make_storage(tmp_path: Path) -> tuple[Path, Path, Path]:
    storage = tmp_path / "Zotero" / "storage"
    first_dir = storage / "ABCD1234"
    second_dir = storage / "WXYZ9876"
    first_dir.mkdir(parents=True)
    second_dir.mkdir(parents=True)

    first = first_dir / "Evidence Synthesis.pdf"
    second = second_dir / "Unrelated Notes.pdf"
    first.write_text("pdf-ish", encoding="utf-8")
    second.write_text("pdf-ish", encoding="utf-8")
    (first_dir / ".zotero-ft-cache").write_text(
        "This paper discusses local first research workspaces and evidence review.",
        encoding="utf-8",
    )
    return storage, first, second


def test_zotero_storage_paths_and_cache_detection(tmp_path: Path) -> None:
    storage, first, _second = make_storage(tmp_path)

    assert zotero_root_from_storage(storage) == tmp_path / "Zotero"
    assert zotero_storage_key(first, storage) == "ABCD1234"
    assert zotero_relative_path(first, storage) == "ABCD1234/Evidence Synthesis.pdf"
    assert has_zotero_fulltext_cache(first, storage) is True
    assert zotero_storage_key(tmp_path / "outside.pdf", storage) is None


def test_keyword_terms_are_normalized_and_deduplicated() -> None:
    assert keyword_terms("Evidence, evidence local-first") == ["evidence", "local-first"]


def test_zotero_relevance_scores_filename_and_fulltext_cache(tmp_path: Path) -> None:
    storage, first, second = make_storage(tmp_path)

    first_hit = score_zotero_relevance(first, storage, ["evidence", "workspace"])
    second_hit = score_zotero_relevance(second, storage, ["evidence", "workspace"])

    assert first_hit.score > second_hit.score
    assert first_hit.matched_terms == ["evidence", "workspace"]
    assert first_hit.matched_in == ["filename", "fulltext_cache"]
    assert first_hit.snippet is not None


def test_search_zotero_storage_returns_ranked_hits(tmp_path: Path) -> None:
    storage, first, second = make_storage(tmp_path)

    hits = search_zotero_storage(storage, ["evidence"], [second, first], limit=5)

    assert [hit.file_path for hit in hits] == [first]


def make_zotero_sqlite(zotero_root: Path) -> Path:
    db_path = zotero_root / "zotero.sqlite"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE itemTypes (itemTypeID INTEGER PRIMARY KEY, typeName TEXT);
        CREATE TABLE items (itemID INTEGER PRIMARY KEY, itemTypeID INTEGER, key TEXT);
        CREATE TABLE itemAttachments (itemID INTEGER PRIMARY KEY, parentItemID INTEGER, path TEXT, contentType TEXT);
        CREATE TABLE fields (fieldID INTEGER PRIMARY KEY, fieldName TEXT);
        CREATE TABLE itemData (itemID INTEGER, fieldID INTEGER, valueID INTEGER);
        CREATE TABLE itemDataValues (valueID INTEGER PRIMARY KEY, value TEXT);
        CREATE TABLE creators (creatorID INTEGER PRIMARY KEY, firstName TEXT, lastName TEXT, fieldMode INTEGER);
        CREATE TABLE itemCreators (itemID INTEGER, creatorID INTEGER, creatorTypeID INTEGER, orderIndex INTEGER);
        CREATE TABLE collections (
            collectionID INTEGER PRIMARY KEY,
            collectionName TEXT,
            key TEXT,
            parentCollectionID INTEGER,
            libraryID INTEGER
        );
        CREATE TABLE collectionItems (collectionID INTEGER, itemID INTEGER);
        """
    )
    conn.executemany("INSERT INTO itemTypes VALUES (?, ?)", [(1, "journalArticle"), (2, "attachment")])
    conn.executemany("INSERT INTO items VALUES (?, ?, ?)", [(10, 1, "PARENT01"), (20, 2, "ABCD1234"), (30, 2, "WXYZ9876")])
    conn.executemany(
        "INSERT INTO itemAttachments VALUES (?, ?, ?, ?)",
        [(20, 10, "storage:Evidence Synthesis.pdf", "application/pdf"), (30, 10, "storage:Copy.pdf", "application/pdf")],
    )
    fields = [(1, "title"), (2, "date"), (3, "DOI"), (4, "url"), (5, "publicationTitle"), (6, "abstractNote")]
    conn.executemany("INSERT INTO fields VALUES (?, ?)", fields)
    values = [
        (1, "Evidence Synthesis for Local Research"),
        (2, "2024"),
        (3, "10.1234/example"),
        (4, "https://example.test/paper"),
        (5, "Journal of Local Tools"),
        (6, "An abstract about local evidence review."),
    ]
    conn.executemany("INSERT INTO itemDataValues VALUES (?, ?)", values)
    conn.executemany("INSERT INTO itemData VALUES (?, ?, ?)", [(10, value_id, value_id) for value_id, _value in values])
    conn.execute("INSERT INTO creators VALUES (?, ?, ?, ?)", (1, "Pedro", "Veloso", 0))
    conn.execute("INSERT INTO itemCreators VALUES (?, ?, ?, ?)", (10, 1, 1, 0))
    conn.executemany(
        "INSERT INTO collections VALUES (?, ?, ?, ?, ?)",
        [(100, "Thesis", "COLLROOT", None, 1), (101, "Chapter One", "COLLCH1", 100, 1)],
    )
    conn.executemany("INSERT INTO collectionItems VALUES (?, ?)", [(100, 10), (101, 10)])
    conn.commit()
    conn.close()
    return db_path


def test_readonly_sqlite_metadata_and_collections(tmp_path: Path) -> None:
    storage, first, _second = make_storage(tmp_path)
    zotero_root = storage.parent
    make_zotero_sqlite(zotero_root)

    metadata = attachment_metadata_by_storage_key(zotero_root, "ABCD1234")
    assert metadata is not None
    assert metadata.parent_item_key == "PARENT01"
    assert metadata.title == "Evidence Synthesis for Local Research"
    assert metadata.creators == ["Pedro Veloso"]
    assert metadata.year == "2024"
    assert metadata.doi == "10.1234/example"
    assert metadata.collections[0]["key"] == "COLLROOT"

    collections = list_zotero_collections(zotero_root)
    assert [collection.key for collection in collections] == ["COLLROOT", "COLLCH1"]
    assert collections[1].path == "Thesis / Chapter One"

    keys = storage_keys_for_collections(zotero_root, ["COLLROOT"], include_subcollections=True)
    assert keys == {"ABCD1234", "WXYZ9876"}


def test_zotero_reports_snapshot_duplicates_and_bibtex(tmp_path: Path) -> None:
    storage, first, second = make_storage(tmp_path)
    zotero_root = storage.parent
    make_zotero_sqlite(zotero_root)

    quality = metadata_quality_report(zotero_root)
    assert quality["total_attachments"] == 2
    assert quality["missing_title"] == []

    health = attachment_health_report(zotero_root, storage, [first])
    assert health["sqlite_attachments"] == 2
    assert health["missing_attachment_files"] == ["WXYZ9876"]

    fulltext = fulltext_availability_report(storage, [first, second])
    assert fulltext["with_fulltext_cache"] == 1
    assert fulltext["without_fulltext_cache"] == 1

    duplicates = duplicate_metadata_candidates(zotero_root)
    assert len(duplicates) == 1
    assert duplicates[0]["match_type"] == "doi"

    snapshot = zotero_metadata_snapshot(zotero_root)
    assert len(snapshot["attachments"]) == 2
    assert len(snapshot["collections"]) == 2

    bibtex = export_bibtex_from_metadata(zotero_root)
    assert "@article{veloso_evidence_2024," in bibtex
    assert "doi = {10.1234/example}" in bibtex
