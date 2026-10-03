"""
Unit and integration tests for Rorak AI V2.5 Step 3: DOCX, TXT, and Markdown Adapters.

Tests cover:
- 8.1 DOCX: Validate extension/MIME, extract paragraphs/headings, normalize whitespace,
  preserve heading metadata, return ParsedDocument.
- 8.2 TXT: Normalize line endings, controlled decoding, preserve paragraph boundaries,
  safely reject malformed/binary input.
- 8.3 Markdown: Preserve heading hierarchy, preserve meaningful code blocks, represent
  sections for structure-aware chunking, carry filename/section metadata.
- 8.4 Tests: Valid fixture, empty/minimal file, malformed file, wrong extension/MIME,
  boundary-size file, metadata preservation.
"""
from pathlib import Path
import zipfile
import pytest
from langchain_core.documents import Document as LCDocument

import docx

from backend.parsers.base import ParsedDocument, StructuredBlock
from backend.parsers.registry import (
    ParserError,
    UnsupportedFormatError,
    default_parser_registry,
    normalize_format,
)
from backend.parsers.adapters.docx import DocxDocumentParser
from backend.parsers.adapters.txt import TextDocumentParser
from backend.parsers.adapters.markdown import MarkdownDocumentParser
from backend.services.ingestion import ingest_func, ingest_parsed_document


# ============================================================
# 8.1 DOCX ADAPTER TESTS
# ============================================================

def _create_sample_docx(
    file_path: Path,
    title: str = "Technical Specification",
    sections: list[tuple[str, str, list[str]]] = None,
    with_table: bool = True,
) -> Path:
    """Helper to generate a rich, valid .docx file using python-docx."""
    doc = docx.Document()
    doc.add_heading(title, level=0)

    if sections is None:
        sections = [
            ("Heading 1", "Architecture Overview", ["Rorak AI uses an agentic RAG architecture.", "It indexes multiple document formats."]),
            ("Heading 2", "Vector Indexing", ["FAISS CPU is utilized for dense vector search.", "Embeddings are generated via SentenceTransformers."]),
        ]

    for style, heading_text, paragraphs in sections:
        # Determine heading level from style
        lvl = 1 if "1" in style else 2
        doc.add_heading(heading_text, level=lvl)
        for p in paragraphs:
            doc.add_paragraph(f"  {p}  \t")  # deliberately add whitespace to test normalization

    if with_table:
        table = doc.add_table(rows=2, cols=2)
        table.cell(0, 0).text = " Component "
        table.cell(0, 1).text = " Technology "
        table.cell(1, 0).text = " Embedding "
        table.cell(1, 1).text = " MiniLM-L6-v2 "

    doc.save(str(file_path))
    return file_path


def test_docx_supports_extension_and_mime():
    """8.1 & 8.4: Verify DOCX parser supports valid extensions and MIME types, rejects others."""
    parser = DocxDocumentParser()
    assert parser.supports("docx") is True
    assert parser.supports(".docx") is True
    assert parser.supports("DOCX") is True
    assert parser.supports("application/vnd.openxmlformats-officedocument.wordprocessingml.document") is True
    assert parser.supports("application/docx") is True

    # Rejection of wrong extensions/MIMEs
    assert parser.supports("pdf") is False
    assert parser.supports("txt") is False
    assert parser.supports("md") is False
    assert parser.supports("application/pdf") is False
    assert parser.supports("") is False


def test_docx_valid_fixture_and_metadata_preservation(tmp_path):
    """8.1 & 8.4: Verify valid DOCX parsing, paragraph/heading extraction, whitespace normalization, and metadata."""
    docx_path = tmp_path / "valid_architecture.docx"
    _create_sample_docx(docx_path)

    parser = DocxDocumentParser()
    parsed = parser.parse(docx_path)

    assert isinstance(parsed, ParsedDocument)
    assert parsed.source_filename == "valid_architecture.docx"
    assert parsed.source_type == "docx"
    assert len(parsed.structured_blocks) > 0

    # Verify heading extraction & metadata
    headings = [b for b in parsed.structured_blocks if b.block_type == "heading"]
    assert len(headings) >= 3  # Title (lvl 1), Architecture Overview (lvl 1), Vector Indexing (lvl 2)

    h_arch = next(b for b in headings if b.metadata.get("heading_text") == "Architecture Overview")
    assert h_arch.metadata["heading_level"] == 1
    assert "Architecture Overview" in h_arch.metadata["heading_path"]

    h_vec = next(b for b in headings if b.metadata.get("heading_text") == "Vector Indexing")
    assert h_vec.metadata["heading_level"] == 2
    assert "Architecture Overview > Vector Indexing" in h_vec.metadata["heading_path"]

    # Verify paragraphs have normalized whitespace and inherited section metadata
    paras = [b for b in parsed.structured_blocks if b.block_type == "paragraph"]
    assert len(paras) >= 4
    for p in paras:
        assert not p.text.startswith(" ")
        assert not p.text.endswith(" ")
        assert "\t" not in p.text
        assert "section" in p.metadata
        assert "heading_path" in p.metadata

    # Verify table extraction
    tables = [b for b in parsed.structured_blocks if b.block_type == "table"]
    assert len(tables) == 1
    assert "Component" in tables[0].text
    assert "MiniLM-L6-v2" in tables[0].text
    assert tables[0].metadata["row_count"] == 2


def test_docx_empty_minimal_file(tmp_path):
    """8.1 & 8.4: Verify empty DOCX file produces an empty ParsedDocument safely without crashing."""
    docx_path = tmp_path / "empty.docx"
    doc = docx.Document()
    doc.save(str(docx_path))

    parser = DocxDocumentParser()
    parsed = parser.parse(docx_path)

    assert isinstance(parsed, ParsedDocument)
    assert parsed.structured_blocks == []
    assert parsed.metadata["paragraph_count"] == 0
    assert parsed.metadata["heading_count"] == 0


def test_docx_malformed_corrupt_zip(tmp_path):
    """8.1 & 8.4: Verify corrupted DOCX file (invalid zip bytes) is rejected with ParserError."""
    bad_docx = tmp_path / "corrupt.docx"
    bad_docx.write_bytes(b"This is not a zip file content at all")

    parser = DocxDocumentParser()
    with pytest.raises(ParserError, match="not a valid zip"):
        parser.parse(bad_docx)


def test_docx_malformed_missing_document_xml(tmp_path):
    """8.1 & 8.4: Verify zip file lacking word/document.xml is rejected with ParserError."""
    fake_docx = tmp_path / "fake.docx"
    with zipfile.ZipFile(fake_docx, "w") as zf:
        zf.writestr("some_other_file.txt", "Hello world")

    parser = DocxDocumentParser()
    with pytest.raises(ParserError, match="missing 'word/document.xml'"):
        parser.parse(fake_docx)


def test_docx_wrong_extension(tmp_path):
    """8.1 & 8.4: Verify wrong extension raises UnsupportedFormatError."""
    wrong_file = tmp_path / "document.pdf"
    wrong_file.write_bytes(b"%PDF-1.4")

    parser = DocxDocumentParser()
    with pytest.raises(UnsupportedFormatError, match="not a .docx file"):
        parser.parse(wrong_file)


def test_docx_boundary_size_file(tmp_path):
    """8.1 & 8.4: Boundary-size DOCX with 30 paragraphs and deep heading hierarchy."""
    large_docx = tmp_path / "large_spec.docx"
    doc = docx.Document()
    doc.add_heading("Large Document Test", level=0)

    for i in range(1, 6):
        doc.add_heading(f"Module {i}", level=1)
        for j in range(1, 4):
            doc.add_heading(f"Submodule {i}.{j}", level=2)
            doc.add_paragraph(f"Content for submodule {i}.{j}. " * 15)

    doc.save(str(large_docx))

    parser = DocxDocumentParser()
    parsed = parser.parse(large_docx)
    assert parsed.metadata["heading_count"] == 1 + 5 + 15
    assert parsed.metadata["paragraph_count"] == 15

    # Verify chunking through format-agnostic ingestion engine
    chunks = ingest_parsed_document(parsed, chunk_size=300, chunk_overlap=30)
    assert len(chunks) > 15
    for c in chunks:
        assert c.metadata["source"] == "large_spec.docx"
        assert c.metadata["source_type"] == "docx"
        assert "section" in c.metadata


# ============================================================
# 8.2 TXT ADAPTER TESTS
# ============================================================

def test_txt_supports_extension_and_mime():
    """8.2 & 8.4: Verify TXT parser supports valid extensions and MIME types."""
    parser = TextDocumentParser()
    assert parser.supports("txt") is True
    assert parser.supports(".txt") is True
    assert parser.supports("text") is True
    assert parser.supports("text/plain") is True

    # Rejection of wrong extensions
    assert parser.supports("pdf") is False
    assert parser.supports("docx") is False
    assert parser.supports("md") is False


def test_txt_valid_fixture_and_normalization(tmp_path):
    """8.2 & 8.4: Verify line ending normalization (CRLF/CR -> LF) and paragraph boundary preservation."""
    txt_path = tmp_path / "sample.txt"
    # Content with mixed CRLF and CR
    content = "First paragraph line 1.\r\nFirst paragraph line 2.\r\n\r\nSecond paragraph.\r\rThird paragraph line 1.\nThird paragraph line 2."
    txt_path.write_bytes(content.encode("utf-8"))

    parser = TextDocumentParser()
    parsed = parser.parse(txt_path)

    assert isinstance(parsed, ParsedDocument)
    assert parsed.source_filename == "sample.txt"
    assert parsed.source_type == "txt"
    assert len(parsed.structured_blocks) == 3

    # Ensure no carriage returns exist
    for b in parsed.structured_blocks:
        assert "\r" not in b.text
        assert b.block_type == "paragraph"
        assert "paragraph_index" in b.metadata
        assert "line_count" in b.metadata

    assert "First paragraph line 1.\nFirst paragraph line 2." in parsed.structured_blocks[0].text
    assert parsed.structured_blocks[1].text == "Second paragraph."


def test_txt_controlled_decoding(tmp_path):
    """8.2 & 8.4: Verify controlled decoding handles UTF-8 with BOM and Latin-1."""
    # 1. UTF-8 with BOM
    bom_file = tmp_path / "bom.txt"
    bom_file.write_bytes(b"\xef\xbb\xbfBOM Header Text Paragraph")
    parser = TextDocumentParser()
    parsed_bom = parser.parse(bom_file)
    assert "BOM Header Text Paragraph" in parsed_bom.structured_blocks[0].text

    # 2. Latin-1 / CP1252 encoded characters
    latin1_file = tmp_path / "latin1.txt"
    latin1_file.write_bytes("Café Münsterstraße".encode("latin-1"))
    parsed_latin1 = parser.parse(latin1_file)
    assert "Café Münsterstraße" in parsed_latin1.structured_blocks[0].text

    # 3. CP1252 with Euro symbol
    cp1252_file = tmp_path / "cp1252.txt"
    cp1252_file.write_bytes("Price: 100 €".encode("cp1252"))
    parsed_cp = parser.parse(cp1252_file)
    assert "Price: 100 €" in parsed_cp.structured_blocks[0].text


def test_txt_rejects_binary_null_bytes(tmp_path):
    """8.2 & 8.4: Verify binary content containing null bytes is safely rejected."""
    bad_txt = tmp_path / "binary_disguised.txt"
    bad_txt.write_bytes(b"Plain looking text\x00BinaryPayload")

    parser = TextDocumentParser()
    with pytest.raises(ParserError, match="Binary content detected"):
        parser.parse(bad_txt)


def test_txt_empty_minimal_file(tmp_path):
    """8.2 & 8.4: Verify 0-byte or whitespace-only text file yields empty ParsedDocument."""
    empty_txt = tmp_path / "empty.txt"
    empty_txt.write_bytes(b"")

    parser = TextDocumentParser()
    parsed = parser.parse(empty_txt)
    assert parsed.structured_blocks == []
    assert parsed.metadata["char_count"] == 0

    ws_txt = tmp_path / "whitespace.txt"
    ws_txt.write_text("   \n\n   \t  \n  ", encoding="utf-8")
    parsed_ws = parser.parse(ws_txt)
    assert parsed_ws.structured_blocks == []


def test_txt_wrong_extension(tmp_path):
    """8.2 & 8.4: Verify wrong extension raises UnsupportedFormatError."""
    wrong_file = tmp_path / "file.bin"
    wrong_file.write_text("Text", encoding="utf-8")

    parser = TextDocumentParser()
    with pytest.raises(UnsupportedFormatError, match="not a text file"):
        parser.parse(wrong_file)


def test_txt_boundary_size_file(tmp_path):
    """8.2 & 8.4: Large text file with 100 paragraphs split into chunks."""
    large_txt = tmp_path / "large_novel.txt"
    paras = [f"Paragraph {i}: " + ("The quick brown fox jumps over the lazy dog. " * 10) for i in range(1, 51)]
    large_txt.write_text("\n\n".join(paras), encoding="utf-8")

    parser = TextDocumentParser()
    parsed = parser.parse(large_txt)
    assert parsed.metadata["paragraph_count"] == 50

    chunks = ingest_parsed_document(parsed, chunk_size=400, chunk_overlap=40)
    assert len(chunks) > 50
    for chunk in chunks:
        assert chunk.metadata["source"] == "large_novel.txt"
        assert chunk.metadata["source_type"] == "txt"


# ============================================================
# 8.3 MARKDOWN ADAPTER TESTS
# ============================================================

def test_markdown_supports_extension_and_mime():
    """8.3 & 8.4: Verify Markdown parser supports valid extensions and MIME types."""
    parser = MarkdownDocumentParser()
    assert parser.supports("md") is True
    assert parser.supports(".md") is True
    assert parser.supports("markdown") is True
    assert parser.supports(".markdown") is True
    assert parser.supports("text/markdown") is True
    assert parser.supports("text/x-markdown") is True

    # Rejection of wrong extensions
    assert parser.supports("pdf") is False
    assert parser.supports("docx") is False
    assert parser.supports("txt") is False


def test_markdown_valid_fixture_and_hierarchy_preservation(tmp_path):
    """8.3 & 8.4: Verify Markdown ATX heading hierarchy, section context, and code block preservation."""
    md_content = """# System Guide

This is the introductory section of Rorak.

## Getting Started

Prepare your environment before running tests.

### Prerequisites

Ensure Python 3.12+ and Docker are running.

```bash
docker ps
pytest -q
```

### Installation

Run the installation script:

```python
import os

def check_env():
    return os.getenv("GROQ_API_KEY") is not None
```

Final closing thoughts and remarks.
"""
    md_file = tmp_path / "guide.md"
    md_file.write_text(md_content, encoding="utf-8")

    parser = MarkdownDocumentParser()
    parsed = parser.parse(md_file)

    assert isinstance(parsed, ParsedDocument)
    assert parsed.source_filename == "guide.md"
    assert parsed.source_type == "md"

    # Check headings
    headings = [b for b in parsed.structured_blocks if b.block_type == "heading"]
    assert len(headings) == 4  # System Guide, Getting Started, Prerequisites, Installation

    h_prereq = next(b for b in headings if b.metadata.get("heading_text") == "Prerequisites")
    assert h_prereq.metadata["level"] == 3
    assert h_prereq.metadata["heading_path"] == "System Guide > Getting Started > Prerequisites"

    h_install = next(b for b in headings if b.metadata.get("heading_text") == "Installation")
    assert h_install.metadata["level"] == 3
    assert h_install.metadata["heading_path"] == "System Guide > Getting Started > Installation"

    # Check code blocks
    code_blocks = [b for b in parsed.structured_blocks if b.block_type == "code"]
    assert len(code_blocks) == 2

    # Bash code block
    cb_bash = code_blocks[0]
    assert cb_bash.metadata["language"] == "bash"
    assert cb_bash.metadata["section"] == "Prerequisites"
    assert "docker ps" in cb_bash.text
    assert "pytest -q" in cb_bash.text

    # Python code block with indentation preservation
    cb_py = code_blocks[1]
    assert cb_py.metadata["language"] == "python"
    assert cb_py.metadata["section"] == "Installation"
    assert "def check_env():\n    return os.getenv" in cb_py.text

    # Check paragraphs carrying section context
    paras = [b for b in parsed.structured_blocks if b.block_type == "paragraph"]
    assert len(paras) >= 4
    p_prereq = next(b for b in paras if "Ensure Python" in b.text)
    assert p_prereq.metadata["section"] == "Prerequisites"
    assert p_prereq.metadata["heading_path"] == "System Guide > Getting Started > Prerequisites"


def test_markdown_empty_minimal_file(tmp_path):
    """8.3 & 8.4: Verify empty Markdown file returns empty ParsedDocument."""
    empty_md = tmp_path / "empty.md"
    empty_md.write_text("   \n\n   \n", encoding="utf-8")

    parser = MarkdownDocumentParser()
    parsed = parser.parse(empty_md)
    assert parsed.structured_blocks == []
    assert parsed.metadata["heading_count"] == 0
    assert parsed.metadata["code_block_count"] == 0


def test_markdown_rejects_binary_null_bytes(tmp_path):
    """8.3 & 8.4: Verify binary content in markdown file is rejected."""
    bad_md = tmp_path / "binary.md"
    bad_md.write_bytes(b"# Heading\n\x00BinaryContent")

    parser = MarkdownDocumentParser()
    with pytest.raises(ParserError, match="Binary content detected"):
        parser.parse(bad_md)


def test_markdown_wrong_extension(tmp_path):
    """8.3 & 8.4: Verify wrong extension raises UnsupportedFormatError."""
    wrong_file = tmp_path / "document.html"
    wrong_file.write_text("<h1>HTML</h1>", encoding="utf-8")

    parser = MarkdownDocumentParser()
    with pytest.raises(UnsupportedFormatError, match="not a markdown file"):
        parser.parse(wrong_file)


def test_markdown_boundary_size_file(tmp_path):
    """8.3 & 8.4: Large markdown file with nested structure and multiple code blocks."""
    large_md = tmp_path / "large_manual.md"
    lines = ["# Complete Reference Manual\n"]
    for i in range(1, 11):
        lines.append(f"## Chapter {i}: Concept Analysis\n")
        lines.append(f"Paragraph detailing the theoretical foundations of chapter {i}.\n" * 5)
        lines.append(f"```python\n# Code snippet {i}\ndef process_{i}():\n    return {i} * 42\n```\n")
        lines.append(f"### Chapter {i}.1: Practical Implementation\n")
        lines.append(f"Further discussion on practical steps for chapter {i}.\n" * 4)

    large_md.write_text("\n".join(lines), encoding="utf-8")

    parser = MarkdownDocumentParser()
    parsed = parser.parse(large_md)
    assert parsed.metadata["heading_count"] == 1 + 10 + 10
    assert parsed.metadata["code_block_count"] == 10

    chunks = ingest_parsed_document(parsed, chunk_size=350, chunk_overlap=35)
    assert len(chunks) > 20
    for chunk in chunks:
        assert chunk.metadata["source"] == "large_manual.md"
        assert chunk.metadata["source_type"] == "md"


# ============================================================
# END-TO-END INGEST_FUNC INTEGRATION FOR ALL FORMATS
# ============================================================

def test_ingest_func_end_to_end_docx(tmp_path):
    """8.4: Test full ingest_func pipeline with .docx file."""
    docx_file = tmp_path / "pipeline_test.docx"
    _create_sample_docx(docx_file, title="Ingestion Pipeline Test")

    chunks = ingest_func(docx_file)
    assert len(chunks) >= 2
    assert all(isinstance(c, LCDocument) for c in chunks)
    assert chunks[0].metadata["source"] == "pipeline_test.docx"
    assert chunks[0].metadata["source_type"] == "docx"


def test_ingest_func_end_to_end_txt(tmp_path):
    """8.4: Test full ingest_func pipeline with .txt file."""
    txt_file = tmp_path / "pipeline_test.txt"
    txt_file.write_text(
        "Rorak AI V2.5 Common Ingestion Pipeline.\n\n"
        "Testing full end-to-end plain text ingestion with multiple paragraphs.\n\n"
        "All formats produce canonical ParsedDocument instances before chunking.",
        encoding="utf-8",
    )

    chunks = ingest_func(txt_file)
    assert len(chunks) >= 1
    assert chunks[0].metadata["source"] == "pipeline_test.txt"
    assert chunks[0].metadata["source_type"] == "txt"


def test_ingest_func_end_to_end_markdown(tmp_path):
    """8.4: Test full ingest_func pipeline with .md file."""
    md_file = tmp_path / "pipeline_test.md"
    md_file.write_text(
        "# Pipeline Markdown Test\n\n"
        "This markdown document is being tested through the global ingest_func.\n\n"
        "## Sub-heading\n\n"
        "```python\nprint('Ingestion works')\n```\n",
        encoding="utf-8",
    )

    chunks = ingest_func(md_file)
    assert len(chunks) >= 1
    assert chunks[0].metadata["source"] == "pipeline_test.md"
    assert chunks[0].metadata["source_type"] == "md"
