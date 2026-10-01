"""
Document parser adapters package.

Exports format-specific adapters for PDF, DOCX, TXT, and Markdown.
"""
from backend.parsers.adapters.pdf import PDFDocumentParser
from backend.parsers.adapters.docx import DocxDocumentParser
from backend.parsers.adapters.txt import TextDocumentParser
from backend.parsers.adapters.markdown import MarkdownDocumentParser

__all__ = [
    "PDFDocumentParser",
    "DocxDocumentParser",
    "TextDocumentParser",
    "MarkdownDocumentParser",
]
