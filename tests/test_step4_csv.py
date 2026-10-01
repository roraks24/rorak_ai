"""
Unit and integration tests for Rorak AI V2.5 Step 4: CSV/Table-Aware Ingestion.

Tests cover:
- 18. Validate CSV input: encodings, delimiters, empty files, malformed/binary input.
- 19. Define deterministic header/column handling: trimming, empty names, duplicates, padding.
- 20. Represent rows with enough column context to remain meaningful after chunking.
- 21. Carry document, row-range, and column metadata where useful.
- 22. Bound memory use for very large tables.
- 23. Retrieval tests for exact identifiers, values, and multi-column questions via FAISS vector store.
"""
from pathlib import Path
import pytest
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document as LCDocument

from backend.parsers.base import ParsedDocument, StructuredBlock
from backend.parsers.registry import (
    ParserError,
    UnsupportedFormatError,
    default_parser_registry,
)
from backend.parsers.adapters.csv import CSVDocumentParser
from backend.rag.embeddings import embedding_model
from backend.services.ingestion import ingest_func, ingest_parsed_document


# ============================================================
# 18. VALIDATE CSV INPUT TESTS
# ============================================================

def test_csv_supports_extension_and_mime():
    """18: Verify CSV parser supports .csv extension and MIME types."""
    parser = CSVDocumentParser()
    assert parser.supports("csv") is True
    assert parser.supports(".csv") is True
    assert parser.supports("CSV") is True
    assert parser.supports("text/csv") is True
    assert parser.supports("application/csv") is True

    # Rejection of wrong extensions
    assert parser.supports("pdf") is False
    assert parser.supports("docx") is False
    assert parser.supports("txt") is False
    assert parser.supports("") is False


def test_csv_delimiter_sniffing(tmp_path):
    """18: Verify automatic sniffing of delimiters: comma, semicolon, tab, pipe."""
    parser = CSVDocumentParser()

    # Comma
    comma_file = tmp_path / "comma.csv"
    comma_file.write_text("id,name,role\n1,Alice,Engineer\n2,Bob,Designer\n", encoding="utf-8")
    parsed_comma = parser.parse(comma_file)
    assert parsed_comma.metadata["delimiter"] == ","
    assert len(parsed_comma.structured_blocks) == 2

    # Semicolon
    semi_file = tmp_path / "semi.csv"
    semi_file.write_text("id;name;role\n1;Alice;Engineer\n2;Bob;Designer\n", encoding="utf-8")
    parsed_semi = parser.parse(semi_file)
    assert parsed_semi.metadata["delimiter"] == ";"
    assert len(parsed_semi.structured_blocks) == 2

    # Tab (TSV)
    tab_file = tmp_path / "tab.csv"
    tab_file.write_text("id\tname\trole\n1\tAlice\tEngineer\n2\tBob\tDesigner\n", encoding="utf-8")
    parsed_tab = parser.parse(tab_file)
    assert parsed_tab.metadata["delimiter"] == "\t"
    assert len(parsed_tab.structured_blocks) == 2

    # Pipe
    pipe_file = tmp_path / "pipe.csv"
    pipe_file.write_text("id|name|role\n1|Alice|Engineer\n2|Bob|Designer\n", encoding="utf-8")
    parsed_pipe = parser.parse(pipe_file)
    assert parsed_pipe.metadata["delimiter"] == "|"
    assert len(parsed_pipe.structured_blocks) == 2


def test_csv_rejects_binary_null_bytes(tmp_path):
    """18: Verify binary data disguised as CSV is safely rejected with ParserError."""
    bad_csv = tmp_path / "malicious.csv"
    bad_csv.write_bytes(b"id,name\n1,Test\x00BinaryPayload")

    parser = CSVDocumentParser()
    with pytest.raises(ParserError, match="Binary content detected"):
        parser.parse(bad_csv)


def test_csv_empty_minimal_file(tmp_path):
    """18: Verify empty and header-only CSV files return empty ParsedDocument without error."""
    parser = CSVDocumentParser()

    # 0-byte file
    empty_csv = tmp_path / "empty.csv"
    empty_csv.write_bytes(b"")
    parsed_empty = parser.parse(empty_csv)
    assert parsed_empty.structured_blocks == []
    assert parsed_empty.metadata["total_rows"] == 0

    # Header-only file (0 data rows)
    header_only = tmp_path / "header_only.csv"
    header_only.write_text("col1,col2,col3\n", encoding="utf-8")
    parsed_header = parser.parse(header_only)
    assert parsed_header.structured_blocks == []
    assert parsed_header.metadata["total_rows"] == 0
    assert parsed_header.metadata["columns"] == ["col1", "col2", "col3"]


def test_csv_wrong_extension(tmp_path):
    """18: Verify wrong extension raises UnsupportedFormatError."""
    wrong_file = tmp_path / "data.json"
    wrong_file.write_text('{"id": 1}', encoding="utf-8")

    parser = CSVDocumentParser()
    with pytest.raises(UnsupportedFormatError, match="not a CSV file"):
        parser.parse(wrong_file)


# ============================================================
# 19. DETERMINISTIC HEADER / COLUMN HANDLING TESTS
# ============================================================

def test_csv_deterministic_header_normalization(tmp_path):
    """19: Verify header whitespace trimming, empty column naming, and duplicate disambiguation."""
    csv_file = tmp_path / "dirty_headers.csv"
    # Headers with: extra spaces, empty column, duplicate column 'price'
    csv_file.write_text("  item_id  ,, price , price , description \n101,A,10.0,9.5,Sample\n", encoding="utf-8")

    parser = CSVDocumentParser()
    parsed = parser.parse(csv_file)

    expected_columns = ["item_id", "unnamed_2", "price", "price_2", "description"]
    assert parsed.metadata["columns"] == expected_columns
    assert parsed.metadata["column_count"] == 5

    # Check row block has disambiguated column labels
    block = parsed.structured_blocks[0]
    assert "item_id: 101" in block.text
    assert "unnamed_2: A" in block.text
    assert "price: 10.0" in block.text
    assert "price_2: 9.5" in block.text
    assert "description: Sample" in block.text


def test_csv_row_padding_for_missing_cells(tmp_path):
    """19: Verify rows shorter than headers are safely padded with empty strings."""
    csv_file = tmp_path / "short_rows.csv"
    csv_file.write_text("col_a,col_b,col_c\nval_a\nval_a2,val_b2\n", encoding="utf-8")

    parser = CSVDocumentParser()
    parsed = parser.parse(csv_file)

    assert len(parsed.structured_blocks) == 2
    row1 = parsed.structured_blocks[0]
    assert "col_a: val_a" in row1.text
    assert "col_b: " in row1.text
    assert "col_c: " in row1.text


# ============================================================
# 20 & 21. ROW CONTEXT & METADATA PRESERVATION TESTS
# ============================================================

def test_csv_row_representation_and_metadata(tmp_path):
    """20 & 21: Verify rows have column context, block_type='table_row', and rich row metadata."""
    csv_file = tmp_path / "inventory.csv"
    content = (
        "SKU,Product,Price,Quantity\n"
        "SKU-001,Wireless Keyboard,$45.00,120\n"
        "SKU-002,Ergonomic Mouse,$30.00,85\n"
    )
    csv_file.write_text(content, encoding="utf-8")

    parser = CSVDocumentParser()
    parsed = parser.parse(csv_file)

    assert parsed.source_filename == "inventory.csv"
    assert parsed.source_type == "csv"
    assert parsed.metadata["total_rows"] == 2
    assert len(parsed.structured_blocks) == 2

    block1 = parsed.structured_blocks[0]
    assert block1.block_type == "table_row"
    # Never simply a raw dump; column headers are explicitly coupled to values
    assert block1.text == "Row 1: | SKU: SKU-001 | Product: Wireless Keyboard | Price: $45.00 | Quantity: 120"
    assert block1.metadata["row_index"] == 1
    assert block1.metadata["row_start"] == 1
    assert block1.metadata["row_end"] == 1
    assert block1.metadata["columns"] == ["SKU", "Product", "Price", "Quantity"]
    assert block1.metadata["row_data"]["SKU"] == "SKU-001"
    assert block1.metadata["row_data"]["Price"] == "$45.00"

    block2 = parsed.structured_blocks[1]
    assert block2.metadata["row_index"] == 2
    assert "SKU: SKU-002" in block2.text


def test_csv_batched_rows_per_block(tmp_path):
    """20 & 21: Verify configurable rows_per_block groups rows while retaining row-range metadata."""
    csv_file = tmp_path / "batch.csv"
    rows = ["id,val"] + [f"{i},value_{i}" for i in range(1, 7)]
    csv_file.write_text("\n".join(rows), encoding="utf-8")

    parser = CSVDocumentParser()
    # Batch 2 rows per block
    parsed = parser.parse(csv_file, rows_per_block=2)

    assert len(parsed.structured_blocks) == 3
    b1 = parsed.structured_blocks[0]
    assert b1.metadata["row_start"] == 1
    assert b1.metadata["row_end"] == 2
    assert b1.metadata["row_count"] == 2
    assert "Row 1:" in b1.text
    assert "Row 2:" in b1.text


# ============================================================
# 22. BOUND MEMORY USE FOR LARGE TABLES TESTS
# ============================================================

def test_csv_memory_bounding_limit(tmp_path):
    """22: Verify max_rows safely bounds memory by stopping stream and flagging truncated."""
    large_csv = tmp_path / "large_stream.csv"
    rows = ["id,code,status"] + [f"{i},CODE-{i:05d},ACTIVE" for i in range(1, 301)]
    large_csv.write_text("\n".join(rows), encoding="utf-8")

    parser = CSVDocumentParser()
    # Enforce limit of 50 rows
    parsed = parser.parse(large_csv, max_rows=50)

    assert parsed.metadata["total_rows"] == 50
    assert len(parsed.structured_blocks) == 50
    assert parsed.metadata["truncated"] is True
    # The 51st row was not read into memory
    assert "CODE-00050" in parsed.structured_blocks[-1].text
    assert not any("CODE-00051" in b.text for b in parsed.structured_blocks)


# ============================================================
# 23. RETRIEVAL TESTS FOR EXACT IDENTIFIERS, VALUES & MULTI-COLUMN QUESTIONS
# ============================================================

CATALOG_CSV_CONTENT = """Product_ID,Product_Name,Category,Price,Stock_Level,Warehouse_Location,Supplier
SKU-AUDIO-8921,Quantum Noise-Cancelling Headphones,Audio,$349.99,15,Warehouse-B,SonicTech
SKU-DESK-4412,Ergonomic Standing Desk,Furniture,$599.00,8,Warehouse-A,FlexiWork
SKU-MOUSE-1092,High-Precision Gaming Mouse,Electronics,$89.99,45,Warehouse-C,HyperGamer
SKU-MONITOR-7734,Ultra-Wide 4K Curved Monitor,Displays,$799.99,12,Warehouse-A,VisionCraft
SKU-KEYBOARD-3321,Mechanical Keyboard Brown Switches,Peripherals,$129.50,30,Warehouse-B,KeyCraft
"""


@pytest.fixture
def catalog_vector_store(tmp_path):
    """Fixture that parses CATALOG_CSV_CONTENT and indexes chunks into FAISS."""
    csv_file = tmp_path / "product_catalog.csv"
    csv_file.write_text(CATALOG_CSV_CONTENT, encoding="utf-8")

    # Ingest through common ingestion pipeline
    chunks = ingest_func(csv_file)
    assert len(chunks) == 5

    # Index into in-memory FAISS store
    vs = FAISS.from_documents(chunks, embedding_model)
    return vs


def test_retrieval_exact_identifier(catalog_vector_store):
    """23: Verify exact identifier query (e.g. SKU-DESK-4412) retrieves matching row with column context."""
    query = "What is the price and stock for SKU-DESK-4412?"
    results = catalog_vector_store.similarity_search(query, k=1)

    assert len(results) == 1
    top_doc = results[0]
    assert "SKU-DESK-4412" in top_doc.page_content
    assert "Ergonomic Standing Desk" in top_doc.page_content
    assert "Price: $599.00" in top_doc.page_content
    assert "Stock_Level: 8" in top_doc.page_content
    assert top_doc.metadata["source"] == "product_catalog.csv"
    assert top_doc.metadata["source_type"] == "csv"


def test_retrieval_exact_value(catalog_vector_store):
    """23: Verify exact value query (e.g. Quantum Noise-Cancelling Headphones) retrieves row."""
    query = "Where is the Quantum Noise-Cancelling Headphones stored and who is the supplier?"
    results = catalog_vector_store.similarity_search(query, k=1)

    assert len(results) == 1
    top_doc = results[0]
    assert "Quantum Noise-Cancelling Headphones" in top_doc.page_content
    assert "SonicTech" in top_doc.page_content
    assert "Warehouse-B" in top_doc.page_content
    assert "SKU-AUDIO-8921" in top_doc.page_content


def test_retrieval_multi_column_question(catalog_vector_store):
    """23: Verify multi-column query combining category, warehouse, and price attributes."""
    query = "Which item in the Displays category is located in Warehouse-A and costs $799.99?"
    results = catalog_vector_store.similarity_search(query, k=1)

    assert len(results) == 1
    top_doc = results[0]
    assert "Ultra-Wide 4K Curved Monitor" in top_doc.page_content
    assert "Displays" in top_doc.page_content
    assert "Warehouse-A" in top_doc.page_content
    assert "$799.99" in top_doc.page_content
    assert "SKU-MONITOR-7734" in top_doc.page_content


def test_end_to_end_csv_ingest_func(tmp_path):
    """20 & 21: Verify end-to-end ingest_func with CSV parses and splits into Document chunks."""
    csv_file = tmp_path / "simple.csv"
    csv_file.write_text("code,name\nC1,Alpha\nC2,Beta\n", encoding="utf-8")

    chunks = ingest_func(csv_file)
    assert len(chunks) == 2
    assert all(isinstance(c, LCDocument) for c in chunks)
    assert chunks[0].metadata["source"] == "simple.csv"
    assert chunks[0].metadata["source_type"] == "csv"
    assert "code: C1" in chunks[0].page_content
