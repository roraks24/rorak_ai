"""
Parser registry and format detection factory for document ingestion.

Rorak AI V2.5 Step 1: Centralized parser registry and format detection.
"""
import logging
import mimetypes
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from backend.parsers.base import DocumentParser, ParsedDocument


logger = logging.getLogger(__name__)


class ParserError(Exception):
    """Base exception for parsing errors."""
    pass


class UnsupportedFormatError(ParserError):
    """Raised when an unsupported file type or document format is encountered."""
    pass


# Canonical MIME-type to format extension mapping
MIME_TO_FORMAT: Dict[str, str] = {
    "application/pdf": "pdf",
    "text/plain": "txt",
    "text/markdown": "md",
    "text/x-markdown": "md",
    "text/html": "html",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/msword": "doc",
    "application/json": "json",
    "text/csv": "csv",
}


def normalize_format(file_type: str) -> str:
    """
    Normalize format string by stripping whitespace, leading dots, and lowercasing.
    Handles MIME types if passed directly.
    """
    cleaned = file_type.strip().lower()
    if cleaned in MIME_TO_FORMAT:
        return MIME_TO_FORMAT[cleaned]
    return cleaned.lstrip(".")


class ParserRegistry:
    """
    Registry and factory for DocumentParser adapters.
    Maintains registered parsers and encapsulates document format detection.
    """

    def __init__(self) -> None:
        self._parsers: List[DocumentParser] = []

    def register(self, parser: DocumentParser) -> None:
        """Register a document parser instance."""
        if not isinstance(parser, DocumentParser):
            raise TypeError(f"Parser must inherit from DocumentParser, got {type(parser)}")
        # Avoid duplicate registration
        if parser not in self._parsers:
            self._parsers.append(parser)
            logger.debug("Registered document parser: %s", parser.__class__.__name__)

    def detect_format(
        self,
        file_path: Optional[Path | str] = None,
        filename: Optional[str] = None,
        mime_type: Optional[str] = None,
    ) -> str:
        """
        Detect canonical format identifier (e.g. 'pdf', 'docx', 'txt', 'md').
        Uses MIME type, file suffix, or system mimetypes detection.
        """
        # 1. Direct MIME-type lookup
        if mime_type and mime_type.strip():
            normalized_mime = mime_type.strip().lower()
            if normalized_mime in MIME_TO_FORMAT:
                return MIME_TO_FORMAT[normalized_mime]

        # 2. File path or filename extension
        target_name = None
        if filename and filename.strip():
            target_name = filename.strip()
        elif file_path:
            target_name = Path(file_path).name

        if target_name:
            suffix = Path(target_name).suffix
            if suffix:
                clean_ext = normalize_format(suffix)
                if clean_ext:
                    return clean_ext

            # 3. Fallback to mimetypes guessing from filename
            guessed_mime, _ = mimetypes.guess_type(target_name)
            if guessed_mime and guessed_mime.lower() in MIME_TO_FORMAT:
                return MIME_TO_FORMAT[guessed_mime.lower()]

        return ""

    def get_parser(self, file_type: str) -> DocumentParser:
        """
        Retrieve a registered parser that supports the given file format.
        Raises UnsupportedFormatError if no registered parser supports it.
        """
        if not file_type or not file_type.strip():
            raise UnsupportedFormatError("File format could not be determined or is empty.")

        normalized_type = normalize_format(file_type)

        for parser in self._parsers:
            if parser.supports(normalized_type) or parser.supports(file_type):
                return parser

        supported = sorted(self.get_supported_formats())
        raise UnsupportedFormatError(
            f"Unsupported document format: '{file_type}'. Supported formats: {supported}"
        )

    def get_parser_for_file(
        self,
        file_path: Path | str,
        mime_type: Optional[str] = None,
    ) -> DocumentParser:
        """
        Detect file format and retrieve the matching parser.
        """
        path_obj = Path(file_path)
        detected_format = self.detect_format(
            file_path=path_obj,
            mime_type=mime_type,
        )

        if not detected_format:
            raise UnsupportedFormatError(
                f"Could not determine document format for '{path_obj.name}'."
            )

        return self.get_parser(detected_format)

    def parse(
        self,
        file_path: Path | str,
        mime_type: Optional[str] = None,
        **kwargs: Any,
    ) -> ParsedDocument:
        """
        Convenience method to detect format, locate parser, and parse file into ParsedDocument.
        """
        parser = self.get_parser_for_file(file_path=file_path, mime_type=mime_type)
        return parser.parse(file_path=file_path, **kwargs)

    def get_supported_formats(self) -> Set[str]:
        """
        Query all registered parsers for their supported formats.
        """
        formats: Set[str] = set()
        # Probe common formats
        common_formats = ["pdf", "txt", "md", "docx", "csv", "json", "html"]
        for fmt in common_formats:
            for parser in self._parsers:
                if parser.supports(fmt):
                    formats.add(fmt)
        return formats


# Global default parser registry
default_parser_registry = ParserRegistry()
