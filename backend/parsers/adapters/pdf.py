"""
PDF document parser adapter using PyPDFLoader and pypdf fallback extraction.

Rorak AI V2.5 Step 1: Format-specific PDF adapter.
"""
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID

import pypdf
from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document

from backend.parsers.base import DocumentParser, ParsedDocument, StructuredBlock
from backend.parsers.registry import ParserError


logger = logging.getLogger(__name__)


class PDFDocumentParser(DocumentParser):
    """
    Parser adapter for Adobe PDF (.pdf) documents.
    Encapsulates PyPDFLoader and layout-aware multi-strategy fallback extraction.
    """

    SUPPORTED_TYPES = {"pdf", "application/pdf"}

    def supports(self, file_type: str) -> bool:
        """Return True if the file type matches PDF format or MIME type."""
        if not file_type:
            return False
        normalized = file_type.strip().lower().lstrip(".")
        return (
            normalized in self.SUPPORTED_TYPES
            or file_type.strip().lower() in self.SUPPORTED_TYPES
        )

    def _extract_with_pypdf_reader(self, file_path: Path) -> List[StructuredBlock]:
        """
        Fallback reader using pypdf.PdfReader with plain and layout extraction modes.
        Extracts text, annotations, and form field streams into StructuredBlocks.
        """
        blocks: List[StructuredBlock] = []
        source_name = file_path.name

        try:
            reader = pypdf.PdfReader(str(file_path))
            for page_idx, page in enumerate(reader.pages):
                page_num = page_idx + 1
                text = ""

                # Strategy A: Standard extraction
                try:
                    text = page.extract_text() or ""
                except Exception:
                    text = ""

                # Strategy B: Layout mode extraction
                if not text.strip():
                    try:
                        text = page.extract_text(extraction_mode="layout") or ""
                    except Exception:
                        pass

                # Strategy C: Check annotations / form contents
                if not text.strip():
                    try:
                        if "/Annots" in page:
                            annot_texts = []
                            for annot in page["/Annots"]:
                                obj = annot.get_object() if hasattr(annot, "get_object") else annot
                                if isinstance(obj, dict) and "/Contents" in obj:
                                    annot_texts.append(str(obj["/Contents"]))
                            if annot_texts:
                                text = " ".join(annot_texts)
                    except Exception:
                        pass

                if text and text.strip():
                    blocks.append(
                        StructuredBlock(
                            text=text.strip(),
                            block_type="page",
                            page_number=page_num,
                            metadata={"source": source_name, "page": page_num},
                        )
                    )
        except Exception as e:
            logger.warning(
                "pypdf direct fallback reader encountered an issue for %s: %s",
                source_name,
                e,
            )

        return blocks

    def parse(
        self,
        file_path: Path | str,
        document_id: Optional[UUID | str] = None,
        **kwargs: Any,
    ) -> ParsedDocument:
        """
        Parse a PDF file into a canonical ParsedDocument.
        """
        path_obj = Path(file_path)

        if not path_obj.exists():
            raise FileNotFoundError(f"PDF file not found: {path_obj}")

        if not path_obj.is_file():
            raise ValueError(f"Path is not a file: {path_obj}")

        blocks: List[StructuredBlock] = []
        page_count = 0

        # Strategy 1: Primary extraction via PyPDFLoader
        try:
            loader = PyPDFLoader(str(path_obj))
            loaded_docs: List[Document] = loader.load()
            page_count = len(loaded_docs)

            for idx, doc in enumerate(loaded_docs):
                content = doc.page_content.strip() if doc.page_content else ""
                page_num = doc.metadata.get("page", idx + 1)
                # Ensure page number is 1-indexed
                if isinstance(page_num, int) and page_num == 0:
                    page_num = 1
                if content:
                    blocks.append(
                        StructuredBlock(
                            text=content,
                            block_type="page",
                            page_number=page_num,
                            metadata={
                                **doc.metadata,
                                "source": path_obj.name,
                                "page": page_num,
                            },
                        )
                    )
        except Exception as e:
            logger.warning(
                "PyPDFLoader failed for %s: %s. Trying fallback extraction.",
                path_obj.name,
                e,
            )
            blocks = []

        # Strategy 2: Multi-strategy pypdf fallback extraction
        if not blocks:
            logger.info("Using multi-strategy pypdf fallback extraction for %s.", path_obj.name)
            blocks = self._extract_with_pypdf_reader(path_obj)
            if not page_count and blocks:
                page_count = max((b.page_number or 1) for b in blocks)

        if not blocks:
            logger.warning(
                "No readable text content found in %s across all extraction strategies.",
                path_obj.name,
            )

        metadata: Dict[str, Any] = {
            "page_count": page_count or len(blocks),
            "source_type": "pdf",
            "file_size": path_obj.stat().st_size if path_obj.exists() else 0,
        }

        return ParsedDocument(
            document_id=document_id,
            source_filename=path_obj.name,
            source_type="pdf",
            structured_blocks=blocks,
            metadata=metadata,
        )
