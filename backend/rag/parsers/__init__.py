"""
RAG parsers package alias pointing to backend.parsers.
"""
from backend.parsers import (
    DocumentParser,
    ParsedDocument,
    StructuredBlock,
    ParserRegistry,
    default_parser_registry,
    ParserError,
    UnsupportedFormatError,
    PDFDocumentParser,
    DocxDocumentParser,
    TextDocumentParser,
    MarkdownDocumentParser,
)

__all__ = [
    "DocumentParser",
    "ParsedDocument",
    "StructuredBlock",
    "ParserRegistry",
    "default_parser_registry",
    "ParserError",
    "UnsupportedFormatError",
    "PDFDocumentParser",
    "DocxDocumentParser",
    "TextDocumentParser",
    "MarkdownDocumentParser",
]
