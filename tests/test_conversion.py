from pathlib import Path
import sys
import types
import zipfile

from researchboss.core.yamlio import read_yaml
from researchboss.engine.conversion import convert_sources, extract_text
from researchboss.engine.sources import scan_sources, set_source_status
from researchboss.engine.workspace import init_workspace


def make_workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test Project", project_type="M.Phil", topic="")
    return workspace


def test_convert_sources_converts_txt_to_sources_text(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    source_root = tmp_path / "sources"
    source_root.mkdir()
    source_file = source_root / "notes.txt"
    source_file.write_text("line one\r\nline two\r", encoding="utf-8")
    scan_sources(workspace, source_root)
    source_id = read_yaml(workspace / "source-register.yaml")["sources"][0]["source_id"]
    set_source_status(workspace, source_id=source_id, new_status="accepted")

    result = convert_sources(workspace, status="accepted")

    assert result.processed == 1
    assert result.converted == 1
    output_path = workspace / "sources_text" / f"{source_id}.txt"
    assert output_path.read_text(encoding="utf-8") == "line one\nline two\n"
    source = read_yaml(workspace / "source-register.yaml")["sources"][0]
    assert source["conversion"]["status"] == "converted"
    assert source["conversion"]["output_path"] == str(output_path)


def test_convert_sources_converts_md_to_plain_text(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    source_root = tmp_path / "sources"
    source_root.mkdir()
    source_file = source_root / "notes.md"
    source_file.write_text(
        "# Heading\n\n- **Important** [source](https://example.test)\n\n`code term`\n",
        encoding="utf-8",
    )
    scan_sources(workspace, source_root)

    result = convert_sources(workspace)

    assert result.converted == 1
    source_id = read_yaml(workspace / "source-register.yaml")["sources"][0]["source_id"]
    output = (workspace / "sources_text" / f"{source_id}.txt").read_text(encoding="utf-8")
    assert "Heading" in output
    assert "Important source" in output
    assert "code term" in output
    assert "**" not in output
    assert "https://example.test" not in output


def test_convert_sources_converts_docx_to_plain_text(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    source_root = tmp_path / "sources"
    source_root.mkdir()
    source_file = source_root / "paper.docx"
    document_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
      <w:body>
        <w:p><w:r><w:t>First paragraph.</w:t></w:r></w:p>
        <w:p><w:r><w:t>Second </w:t></w:r><w:r><w:t>paragraph.</w:t></w:r></w:p>
      </w:body>
    </w:document>
    """
    with zipfile.ZipFile(source_file, "w") as docx:
        docx.writestr("word/document.xml", document_xml)
    scan_sources(workspace, source_root)

    result = convert_sources(workspace)

    assert result.converted == 1
    source_id = read_yaml(workspace / "source-register.yaml")["sources"][0]["source_id"]
    output = (workspace / "sources_text" / f"{source_id}.txt").read_text(encoding="utf-8")
    assert output == "First paragraph.\nSecond paragraph.\n"


def test_convert_sources_converts_pdf_with_page_markers(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    source_root = tmp_path / "sources"
    source_root.mkdir()
    source_file = source_root / "paper.pdf"
    source_file.write_bytes(
        b"""%PDF-1.4
1 0 obj << /Type /Page /Contents 2 0 R >> endobj
2 0 obj << /Length 44 >> stream
BT /F1 12 Tf (First page text.) Tj ET
endstream endobj
3 0 obj << /Type /Page /Contents 4 0 R >> endobj
4 0 obj << /Length 45 >> stream
BT /F1 12 Tf (Second page text.) Tj ET
endstream endobj
%%EOF
"""
    )
    scan_sources(workspace, source_root)

    result = convert_sources(workspace)

    assert result.converted == 1
    source_id = read_yaml(workspace / "source-register.yaml")["sources"][0]["source_id"]
    output = (workspace / "sources_text" / f"{source_id}.txt").read_text(encoding="utf-8")
    assert "--- Page 1 ---" in output
    assert "First page text." in output
    assert "--- Page 2 ---" in output
    assert "Second page text." in output


def test_extract_pdf_uses_optional_pymupdf_when_available(tmp_path: Path, monkeypatch) -> None:
    source_file = tmp_path / "paper.pdf"
    source_file.write_bytes(b"%PDF-1.4 conservative fallback")

    class FakePage:
        def get_text(self, _mode):
            return "PyMuPDF page text"

    class FakeDoc(list):
        def close(self):
            self.closed = True

    fake_fitz = types.SimpleNamespace(open=lambda _path: FakeDoc([FakePage()]))
    monkeypatch.setitem(sys.modules, "fitz", fake_fitz)

    output = extract_text(source_file)

    assert "PyMuPDF page text" in output


def test_extract_pdf_falls_back_to_pypdf_when_pymupdf_missing(tmp_path: Path, monkeypatch) -> None:
    source_file = tmp_path / "paper.pdf"
    source_file.write_bytes(b"%PDF-1.4 conservative fallback")

    class FakePage:
        def extract_text(self):
            return "PyPDF page text"

    class FakeReader:
        pages = [FakePage()]

        def __init__(self, _path):
            pass

    fake_pypdf = types.SimpleNamespace(PdfReader=FakeReader)
    monkeypatch.setitem(sys.modules, "pypdf", fake_pypdf)
    monkeypatch.setitem(sys.modules, "fitz", None)

    output = extract_text(source_file)

    assert "PyPDF page text" in output


def test_convert_sources_skips_unchanged_cached_output(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    source_root = tmp_path / "sources"
    source_root.mkdir()
    source_file = source_root / "notes.txt"
    source_file.write_text("original", encoding="utf-8")
    scan_sources(workspace, source_root)

    first = convert_sources(workspace)
    source = read_yaml(workspace / "source-register.yaml")["sources"][0]
    output_path = Path(source["conversion"]["output_path"])
    output_path.write_text("manual marker", encoding="utf-8")
    second = convert_sources(workspace)

    assert first.converted == 1
    assert second.converted == 0
    assert second.skipped == 1
    assert second.results[0].status == "skipped_unchanged"
    assert output_path.read_text(encoding="utf-8") == "manual marker"


def test_convert_sources_records_failed_conversion(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    source_root = tmp_path / "sources"
    source_root.mkdir()
    source_file = source_root / "broken.docx"
    source_file.write_text("not a zip file", encoding="utf-8")
    scan_sources(workspace, source_root)

    result = convert_sources(workspace)

    assert result.failed == 1
    source = read_yaml(workspace / "source-register.yaml")["sources"][0]
    assert source["conversion"]["status"] == "failed"
    failed_path = Path(source["conversion"]["failed_path"])
    assert failed_path.is_file()
    failure = read_yaml(failed_path)
    assert failure["source_id"] == source["source_id"]
    assert failure["error"]
