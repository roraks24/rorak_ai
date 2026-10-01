"""
Unit and integration tests for document parsers, registry, and canonical ingestion.

Rorak AI V2.5 Step 1: Tests for parser selection, format detection, and unsupported formats.
"""
from pathlib import Path
from uuid import UUID, uuid4
import pytest
from langchain_core.documents import Document as LCDocument
import pypdf

from backend.parsers.base import DocumentParser, ParsedDocument, StructuredBlock
from backend.parsers.registry import (
    ParserError,
    ParserRegistry,
    UnsupportedFormatError,
    default_parser_registry,
    normalize_format,
)
from backend.parsers.adapters.pdf import PDFDocumentParser
from backend.services.ingestion import ingest_func, ingest_parsed_document


# ============================================================
# DUMMY PARSER FIXTURE
# ============================================================

class DummyTextParser(DocumentParser):
    """Test parser for plain text files."""

    def supports(self, file_type: str) -> bool:
        normalized = file_type.strip().lower().lstrip(".")
        return normalized in {"txt", "text"}

    def parse(self, file_path: Path | str, **kwargs) -> ParsedDocument:
        path = Path(file_path)
        content = path.read_text(encoding="utf-8")
        block = StructuredBlock(
            text=content,
            block_type="text",
            page_number=1,
            metadata={"source": path.name},
        )
        return ParsedDocument(
            source_filename=path.name,
            source_type="txt",
            structured_blocks=[block],
            metadata={"char_count": len(content)},
        )


def _create_minimal_pdf(dest_path: Path, text: str = "Hello Rorak V2.5 Ingestion Test") -> Path:
    """Helper to create a small valid PDF file on disk using pypdf."""
    writer = pypdf.PdfWriter()
    # Add a blank page with content stream
    writer.add_blank_page(width=72, height=72)
    # Write to file
    with open(dest_path, "wb") as f:
        writer.write(f)
    return dest_path


# ============================================================
# BASE MODELS TESTS
# ============================================================

def test_structured_block_creation_and_methods():
    """Verify StructuredBlock defaults, dictionary conversion, and LangChain conversion."""
    block = StructuredBlock(
        text="Section 1 heading",
        block_type="heading",
        page_number=3,
        metadata={"custom_key": "val1"},
    )
    assert block.text == "Section 1 heading"
    assert block.block_type == "heading"
    assert block.page_number == 3

    # to_dict
    data = block.to_dict()
    assert data["text"] == "Section 1 heading"
    assert data["block_type"] == "heading"
    assert data["page_number"] == 3
    assert data["metadata"] == {"custom_key": "val1"}

    # to_langchain_document
    doc_id = str(uuid4())
    lc_doc = block.to_langchain_document(
        source_filename="test_doc.pdf",
        source_type="pdf",
        document_id=doc_id,
    )
    assert isinstance(lc_doc, LCDocument)
    assert lc_doc.page_content == "Section 1 heading"
    assert lc_doc.metadata["source"] == "test_doc.pdf"
    assert lc_doc.metadata["source_type"] == "pdf"
    assert lc_doc.metadata["document_id"] == doc_id
    assert lc_doc.metadata["page"] == 3
    assert lc_doc.metadata["block_type"] == "heading"
    assert lc_doc.metadata["custom_key"] == "val1"


def test_parsed_document_structure_and_conversion():
    """Verify ParsedDocument field initialization, aliases, full text generation, and LC conversion."""
    b1 = StructuredBlock(text="Line 1 of content.", block_type="paragraph", page_number=1)
    b2 = StructuredBlock(text="Line 2 of content.", block_type="paragraph", page_number=2)
    b_empty = StructuredBlock(text="   ", block_type="paragraph", page_number=2)

    parsed = ParsedDocument(
        source_filename="manual.pdf",
        source_type="pdf",
        structured_blocks=[b1, b2, b_empty],
        metadata={"author": "Alice"},
    )

    # Document ID is automatically populated with a UUID if not provided
    assert parsed.document_id is not None
    assert isinstance(parsed.document_id, UUID)
    assert parsed.source_filename == "manual.pdf"
    assert parsed.source_type == "pdf"
    assert len(parsed.structured_blocks) == 3
    assert parsed.blocks == parsed.structured_blocks
    assert parsed.metadata["author"] == "Alice"

    # get_full_text ignores whitespace-only blocks
    full_text = parsed.get_full_text(separator="\n")
    assert full_text == "Line 1 of content.\nLine 2 of content."

    # to_langchain_documents filters out empty blocks
    lc_docs = parsed.to_langchain_documents()
    assert len(lc_docs) == 2
    assert lc_docs[0].page_content == "Line 1 of content."
    assert lc_docs[0].metadata["page"] == 1
    assert lc_docs[0].metadata["source"] == "manual.pdf"
    assert lc_docs[1].page_content == "Line 2 of content."
    assert lc_docs[1].metadata["page"] == 2

    # to_dict
    serialized = parsed.to_dict()
    assert serialized["source_filename"] == "manual.pdf"
    assert serialized["source_type"] == "pdf"
    assert len(serialized["structured_blocks"]) == 3
    assert serialized["metadata"]["author"] == "Alice"


def test_document_parser_abc_cannot_be_instantiated():
    """Verify DocumentParser is an ABC and cannot be directly instantiated."""
    with pytest.raises(TypeError):
        DocumentParser()  # type: ignore


# ============================================================
# PARSER REGISTRY & FORMAT DETECTION TESTS
# ============================================================

def test_normalize_format():
    """Verify format normalization handles extensions, MIME types, and cases."""
    assert normalize_format("pdf") == "pdf"
    assert normalize_format(".PDF") == "pdf"
    assert normalize_format("  .docx  ") == "docx"
    assert normalize_format("application/pdf") == "pdf"
    assert normalize_format("text/plain") == "txt"
    assert normalize_format("text/markdown") == "md"


def test_registry_detect_format():
    """Verify format detection from filenames, paths, and MIME types."""
    reg = ParserRegistry()

    # From filename / suffix
    assert reg.detect_format(filename="sample.pdf") == "pdf"
    assert reg.detect_format(filename="document.DOCX") == "docx"
    assert reg.detect_format(filename="notes.txt") == "txt"
    assert reg.detect_format(filename="readme.md") == "md"
    assert reg.detect_format(file_path=Path("/tmp/data/report.pdf")) == "pdf"

    # From explicit MIME type
    assert reg.detect_format(mime_type="application/pdf") == "pdf"
    assert reg.detect_format(mime_type="text/plain") == "txt"
    assert reg.detect_format(mime_type="text/markdown") == "md"
    assert reg.detect_format(mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document") == "docx"

    # Priority: MIME type takes precedence if valid
    assert reg.detect_format(filename="ambiguous.dat", mime_type="application/pdf") == "pdf"

    # Unknown
    assert reg.detect_format(filename="unknown_file_with_no_ext") == ""
    assert reg.detect_format(filename="script.exe") == "exe"


def test_registry_parser_registration_and_selection():
    """Verify registering and retrieving parsers based on supported types."""
    reg = ParserRegistry()
    pdf_parser = PDFDocumentParser()
    txt_parser = DummyTextParser()

    reg.register(pdf_parser)
    reg.register(txt_parser)

    # Retrieval by format
    assert reg.get_parser("pdf") is pdf_parser
    assert reg.get_parser(".pdf") is pdf_parser
    assert reg.get_parser("PDF") is pdf_parser
    assert reg.get_parser("application/pdf") is pdf_parser

    assert reg.get_parser("txt") is txt_parser
    assert reg.get_parser(".TXT") is txt_parser
    assert reg.get_parser("text") is txt_parser

    # Retrieval by file path
    assert reg.get_parser_for_file(Path("/docs/spec.pdf")) is pdf_parser
    assert reg.get_parser_for_file("/tmp/notes.txt") is txt_parser

    # Query supported formats
    supported = reg.get_supported_formats()
    assert "pdf" in supported
    assert "txt" in supported


def test_registry_invalid_parser_registration():
    """Verify non-DocumentParser instances are rejected."""
    reg = ParserRegistry()
    with pytest.raises(TypeError, match="Parser must inherit from DocumentParser"):
        reg.register("NotAParser")  # type: ignore


def test_registry_unsupported_format_raises_exception():
    """Verify UnsupportedFormatError is raised for unsupported extensions or unknown formats."""
    reg = ParserRegistry()
    reg.register(PDFDocumentParser())

    # Unsupported file types
    with pytest.raises(UnsupportedFormatError, match="Unsupported document format: 'docx'"):
        reg.get_parser("docx")

    with pytest.raises(UnsupportedFormatError, match="Unsupported document format: 'exe'"):
        reg.get_parser_for_file("malicious.exe")

    with pytest.raises(UnsupportedFormatError, match="Unsupported document format: 'zip'"):
        reg.get_parser("zip")

    # Empty or undetectable format
    with pytest.raises(UnsupportedFormatError, match="Could not determine document format"):
        reg.get_parser_for_file("no_extension_file")


def test_default_parser_registry_contains_pdf_parser():
    """Verify the global default_parser_registry has PDFDocumentParser registered."""
    parser = default_parser_registry.get_parser("pdf")
    assert isinstance(parser, PDFDocumentParser)
    assert default_parser_registry.get_parser_for_file("test.pdf") is parser


# ============================================================
# PDF ADAPTER TESTS
# ============================================================

def test_pdf_adapter_supports():
    """Verify PDFDocumentParser.supports matches PDF variations."""
    parser = PDFDocumentParser()
    assert parser.supports("pdf") is True
    assert parser.supports(".pdf") is True
    assert parser.supports("PDF") is True
    assert parser.supports("application/pdf") is True
    assert parser.supports("docx") is False
    assert parser.supports("txt") is False
    assert parser.supports("exe") is False
    assert parser.supports("") is False


def test_pdf_adapter_parse_valid_pdf(tmp_path):
    """Verify PDFDocumentParser correctly parses a valid PDF file."""
    pdf_file = tmp_path / "sample.pdf"
    _create_minimal_pdf(pdf_file)

    parser = PDFDocumentParser()
    parsed_doc = parser.parse(pdf_file)

    assert isinstance(parsed_doc, ParsedDocument)
    assert parsed_doc.source_filename == "sample.pdf"
    assert parsed_doc.source_type == "pdf"
    assert parsed_doc.metadata["source_type"] == "pdf"
    assert "page_count" in parsed_doc.metadata


def test_pdf_adapter_file_validation_errors(tmp_path):
    """Verify PDFDocumentParser raises FileNotFoundError and ValueError appropriately."""
    parser = PDFDocumentParser()

    with pytest.raises(FileNotFoundError):
        parser.parse(tmp_path / "non_existent.pdf")

    # Directory instead of file
    with pytest.raises(ValueError, match="Path is not a file"):
        parser.parse(tmp_path)


# ============================================================
# INGESTION SERVICE CONSUMPTION TESTS (FORMAT-AGNOSTIC)
# ============================================================

def test_ingest_parsed_document_chunks_content():
    """Verify ingest_parsed_document operates purely on ParsedDocument without format knowledge."""
    # Construct a synthetic ParsedDocument representing arbitrary source (e.g. DOCX, Markdown, etc.)
    blocks = [
        StructuredBlock(
            text="Lorem ipsum dolor sit amet, consectetur adipiscing elit. " * 15,
            block_type="paragraph",
            page_number=1,
        ),
        StructuredBlock(
            text="Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. " * 15,
            block_type="paragraph",
            page_number=2,
        ),
    ]

    parsed_doc = ParsedDocument(
        source_filename="arbitrary_report.docx",
        source_type="docx",
        structured_blocks=blocks,
        metadata={"department": "Engineering"},
    )

    chunks = ingest_parsed_document(parsed_doc, chunk_size=200, chunk_overlap=20)
    assert len(chunks) > 2
    for chunk in chunks:
        assert isinstance(chunk, LCDocument)
        assert chunk.metadata["source"] == "arbitrary_report.docx"
        assert chunk.metadata["source_type"] == "docx"
        assert "page" in chunk.metadata


def test_ingest_parsed_document_empty_handling():
    """Verify ingest_parsed_document handles empty or whitespace-only documents safely."""
    empty_doc = ParsedDocument(
        source_filename="empty.txt",
        source_type="txt",
        structured_blocks=[],
    )
    assert ingest_parsed_document(empty_doc) == []

    whitespace_doc = ParsedDocument(
        source_filename="whitespace.txt",
        source_type="txt",
        structured_blocks=[StructuredBlock(text="   \n   ", page_number=1)],
    )
    assert ingest_parsed_document(whitespace_doc) == []


def test_ingest_func_end_to_end_with_custom_registry(tmp_path):
    """Verify ingest_func uses the registry, parses to ParsedDocument, and chunks output."""
    custom_reg = ParserRegistry()
    custom_reg.register(DummyTextParser())

    test_file = tmp_path / "notes.txt"
    test_file.write_text("Rorak V2.5 Ingestion Interface Step 1 Works Successfully!\n" * 10, encoding="utf-8")

    chunks = ingest_func(test_file, parser_registry=custom_reg)
    assert len(chunks) >= 1
    assert chunks[0].metadata["source"] == "notes.txt"
    assert chunks[0].metadata["source_type"] == "txt"


def test_ingest_func_unsupported_format_raises(tmp_path):
    """Verify ingest_func raises UnsupportedFormatError for unsupported files."""
    bad_file = tmp_path / "program.exe"
    bad_file.write_bytes(b"binary data")

    with pytest.raises(UnsupportedFormatError, match="Unsupported document format"):
        ingest_func(bad_file)
