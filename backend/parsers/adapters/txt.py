"""
TXT document parser adapter.

Rorak AI V2.5 Step 3.2: Plain text (.txt) document parser with controlled decoding.
"""
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID

from backend.parsers.base import DocumentParser, ParsedDocument, StructuredBlock
from backend.parsers.registry import ParserError, UnsupportedFormatError


logger = logging.getLogger(__name__)


class TextDocumentParser(DocumentParser):
    """
    Parser adapter for plain text (.txt) files.
    Enforces controlled decoding, normalizes line endings, preserves paragraph boundaries,
    and safely rejects malformed or binary input.
    """

    SUPPORTED_EXTENSIONS = {"txt", "text"}
    SUPPORTED_MIMES = {"text/plain"}

    # Supported candidate encodings in priority order
    CANDIDATE_ENCODINGS = ("utf-8", "utf-8-sig", "cp1252", "latin-1")

    def supports(self, file_type: str) -> bool:
        """Return True if the file type matches plain text extension or MIME type."""
        if not file_type:
            return False
        normalized = file_type.strip().lower().lstrip(".")
        return (
            normalized in self.SUPPORTED_EXTENSIONS
            or file_type.strip().lower() in self.SUPPORTED_MIMES
        )

    def _decode_bytes(self, raw_bytes: bytes, filename: str) -> str:
        """
        Safely decode bytes using controlled encoding ladder.
        Rejects binary content containing null bytes.
        """
        if b"\x00" in raw_bytes:
            raise ParserError(
                f"Binary content detected in text file '{filename}' (found null bytes)."
            )

        for encoding in self.CANDIDATE_ENCODINGS:
            try:
                decoded = raw_bytes.decode(encoding)
                return decoded
            except UnicodeDecodeError:
                continue

        raise ParserError(
            f"Unable to decode text file '{filename}' with supported encodings {self.CANDIDATE_ENCODINGS}."
        )

    def parse(
        self,
        file_path: Path | str,
        document_id: Optional[UUID | str] = None,
        **kwargs: Any,
    ) -> ParsedDocument:
        """
        Parse a .txt document into a canonical ParsedDocument.
        """
        path_obj = Path(file_path)

        if not path_obj.exists():
            raise FileNotFoundError(f"Text file not found: {path_obj}")

        if not path_obj.is_file():
            raise ValueError(f"Path is not a file: {path_obj}")

        # Extension check
        ext = path_obj.suffix.lower().lstrip(".")
        if ext not in self.SUPPORTED_EXTENSIONS and path_obj.suffix != "":
            raise UnsupportedFormatError(
                f"File '{path_obj.name}' is not a text file (extension is '{path_obj.suffix}')."
            )

        # Read raw bytes
        try:
            raw_bytes = path_obj.read_bytes()
        except Exception as e:
            raise ParserError(f"Failed to read text file '{path_obj.name}': {e}")

        # Controlled decoding
        decoded_text = self._decode_bytes(raw_bytes, path_obj.name)

        # Normalize line endings: convert CRLF and CR to LF
        normalized_text = decoded_text.replace("\r\n", "\n").replace("\r", "\n")

        # Split on paragraph boundaries (two or more consecutive newlines, allowing optional spaces)
        raw_paragraphs = re.split(r"\n\s*\n+", normalized_text)

        blocks: List[StructuredBlock] = []
        char_count = 0

        for idx, para in enumerate(raw_paragraphs):
            clean_para = para.strip()
            if not clean_para:
                continue

            lines = [line.strip() for line in clean_para.splitlines() if line.strip()]
            rejoined_para = "\n".join(lines)
            char_count += len(rejoined_para)

            blocks.append(
                StructuredBlock(
                    text=rejoined_para,
                    block_type="paragraph",
                    metadata={
                        "paragraph_index": idx + 1,
                        "line_count": len(lines),
                    },
                )
            )

        metadata: Dict[str, Any] = {
            "source_type": "txt",
            "file_size": len(raw_bytes),
            "char_count": char_count,
            "paragraph_count": len(blocks),
            "block_count": len(blocks),
        }

        return ParsedDocument(
            document_id=document_id,
            source_filename=path_obj.name,
            source_type="txt",
            structured_blocks=blocks,
            metadata=metadata,
        )
