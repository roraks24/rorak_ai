"""
Document parsing and ingestion package.

Rorak AI V2.5: Canonical DocumentParser interfaces, registry, and format adapters.
"""
from backend.parsers.base import DocumentParser, ParsedDocument, StructuredBlock
from backend.parsers.registry import (
    ParserError,
    ParserRegistry,
    UnsupportedFormatError,
    default_parser_registry,
)
from backend.parsers.adapters.pdf import PDFDocumentParser
from backend.parsers.adapters.docx import DocxDocumentParser
from backend.parsers.adapters.txt import TextDocumentParser
from backend.parsers.adapters.markdown import MarkdownDocumentParser

# Automatically register built-in adapters with the default registry
default_parser_registry.register(PDFDocumentParser())
default_parser_registry.register(DocxDocumentParser())
default_parser_registry.register(TextDocumentParser())
default_parser_registry.register(MarkdownDocumentParser())

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
