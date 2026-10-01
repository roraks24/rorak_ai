"""
Document parsing and ingestion package.

Rorak AI V2.5 Step 1: Canonical DocumentParser interfaces, registry, and adapters.
"""
from backend.parsers.base import DocumentParser, ParsedDocument, StructuredBlock
from backend.parsers.registry import (
    ParserError,
    ParserRegistry,
    UnsupportedFormatError,
    default_parser_registry,
)
from backend.parsers.adapters.pdf import PDFDocumentParser

# Automatically register built-in adapters with the default registry
default_parser_registry.register(PDFDocumentParser())

__all__ = [
    "DocumentParser",
    "ParsedDocument",
    "StructuredBlock",
    "ParserRegistry",
    "default_parser_registry",
    "ParserError",
    "UnsupportedFormatError",
    "PDFDocumentParser",
]
