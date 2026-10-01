"""
Markdown document parser adapter.

Rorak AI V2.5 Step 3.3: Markdown (.md) document parser with heading hierarchy
and structure-aware code block preservation.
"""
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID

from backend.parsers.base import DocumentParser, ParsedDocument, StructuredBlock
from backend.parsers.registry import ParserError, UnsupportedFormatError


logger = logging.getLogger(__name__)


class MarkdownDocumentParser(DocumentParser):
    """
    Parser adapter for Markdown (.md) files.
    Preserves heading hierarchies, section context, and fenced code blocks,
    enabling structure-aware chunking and rich semantic indexing.
    """

    SUPPORTED_EXTENSIONS = {"md", "markdown"}
    SUPPORTED_MIMES = {"text/markdown", "text/x-markdown"}

    CANDIDATE_ENCODINGS = ("utf-8", "utf-8-sig", "cp1252", "latin-1")

    def supports(self, file_type: str) -> bool:
        """Return True if the file type matches Markdown extension or MIME type."""
        if not file_type:
            return False
        normalized = file_type.strip().lower().lstrip(".")
        return (
            normalized in self.SUPPORTED_EXTENSIONS
            or file_type.strip().lower() in self.SUPPORTED_MIMES
        )

    def _decode_bytes(self, raw_bytes: bytes, filename: str) -> str:
        """Controlled decoding with null-byte rejection."""
        if b"\x00" in raw_bytes:
            raise ParserError(
                f"Binary content detected in markdown file '{filename}' (found null bytes)."
            )

        for encoding in self.CANDIDATE_ENCODINGS:
            try:
                return raw_bytes.decode(encoding)
            except UnicodeDecodeError:
                continue

        raise ParserError(
            f"Unable to decode markdown file '{filename}' with supported encodings."
        )

    def parse(
        self,
        file_path: Path | str,
        document_id: Optional[UUID | str] = None,
        **kwargs: Any,
    ) -> ParsedDocument:
        """
        Parse a Markdown document into a canonical ParsedDocument.
        """
        path_obj = Path(file_path)

        if not path_obj.exists():
            raise FileNotFoundError(f"Markdown file not found: {path_obj}")

        if not path_obj.is_file():
            raise ValueError(f"Path is not a file: {path_obj}")

        # Extension check
        ext = path_obj.suffix.lower().lstrip(".")
        if ext not in self.SUPPORTED_EXTENSIONS and path_obj.suffix != "":
            raise UnsupportedFormatError(
                f"File '{path_obj.name}' is not a markdown file (extension is '{path_obj.suffix}')."
            )

        # Read and decode
        try:
            raw_bytes = path_obj.read_bytes()
        except Exception as e:
            raise ParserError(f"Failed to read markdown file '{path_obj.name}': {e}")

        decoded_text = self._decode_bytes(raw_bytes, path_obj.name)
        normalized_text = decoded_text.replace("\r\n", "\n").replace("\r", "\n")

        lines = normalized_text.splitlines()

        blocks: List[StructuredBlock] = []
        heading_stack: List[tuple[int, str]] = []  # (level, heading_text)
        current_section: Optional[str] = None

        # State tracking for code blocks and paragraphs
        in_code_block = False
        code_fence_char = ""
        code_fence_len = 0
        code_lang = ""
        code_lines: List[str] = []

        paragraph_lines: List[str] = []

        def flush_paragraph() -> None:
            nonlocal paragraph_lines
            if not paragraph_lines:
                return
            clean_text = "\n".join(paragraph_lines).strip()
            paragraph_lines = []
            if not clean_text:
                return

            heading_path = " > ".join(h[1] for h in heading_stack) if heading_stack else ""
            meta: Dict[str, Any] = {
                "source": path_obj.name,
            }
            if current_section:
                meta["section"] = current_section
            if heading_path:
                meta["heading_path"] = heading_path

            blocks.append(
                StructuredBlock(
                    text=clean_text,
                    block_type="paragraph",
                    metadata=meta,
                )
            )

        def flush_code_block() -> None:
            nonlocal in_code_block, code_lines, code_lang, code_fence_char, code_fence_len
            code_text = "\n".join(code_lines)
            heading_path = " > ".join(h[1] for h in heading_stack) if heading_stack else ""
            meta: Dict[str, Any] = {
                "source": path_obj.name,
                "language": code_lang or "text",
            }
            if current_section:
                meta["section"] = current_section
            if heading_path:
                meta["heading_path"] = heading_path

            blocks.append(
                StructuredBlock(
                    text=code_text,
                    block_type="code",
                    metadata=meta,
                )
            )
            in_code_block = False
            code_lines = []
            code_lang = ""
            code_fence_char = ""
            code_fence_len = 0

        # Regex patterns
        fence_start_pattern = re.compile(r"^(\`{3,}|~{3,})\s*([a-zA-Z0-9_\-\+]*)\s*$")
        heading_pattern = re.compile(r"^(#{1,6})\s+(.*?)(?:\s+#+)?$")

        for line in lines:
            # Check for code fence
            fence_match = fence_start_pattern.match(line)

            if in_code_block:
                # Check if this line closes the code block
                if fence_match and fence_match.group(1)[0] == code_fence_char and len(fence_match.group(1)) >= code_fence_len:
                    flush_code_block()
                else:
                    code_lines.append(line)
                continue

            if fence_match:
                flush_paragraph()
                in_code_block = True
                code_fence_char = fence_match.group(1)[0]
                code_fence_len = len(fence_match.group(1))
                code_lang = fence_match.group(2).strip().lower()
                continue

            # Check for ATX heading
            heading_match = heading_pattern.match(line)
            if heading_match:
                flush_paragraph()
                level = len(heading_match.group(1))
                heading_title = heading_match.group(2).strip()

                # Adjust heading stack for hierarchy
                while heading_stack and heading_stack[-1][0] >= level:
                    heading_stack.pop()
                heading_stack.append((level, heading_title))
                current_section = heading_title
                heading_path = " > ".join(h[1] for h in heading_stack)

                blocks.append(
                    StructuredBlock(
                        text=line.strip(),
                        block_type="heading",
                        metadata={
                            "source": path_obj.name,
                            "level": level,
                            "heading_text": heading_title,
                            "heading_path": heading_path,
                            "section": current_section,
                        },
                    )
                )
                continue

            # Check for blank line
            if not line.strip():
                flush_paragraph()
                continue

            # Regular content line
            paragraph_lines.append(line.rstrip())

        # Flush any remaining buffers
        if in_code_block:
            flush_code_block()
        flush_paragraph()

        metadata: Dict[str, Any] = {
            "source_type": "md",
            "file_size": len(raw_bytes),
            "heading_count": len([b for b in blocks if b.block_type == "heading"]),
            "code_block_count": len([b for b in blocks if b.block_type == "code"]),
            "paragraph_count": len([b for b in blocks if b.block_type == "paragraph"]),
            "block_count": len(blocks),
        }

        return ParsedDocument(
            document_id=document_id,
            source_filename=path_obj.name,
            source_type="md",
            structured_blocks=blocks,
            metadata=metadata,
        )
