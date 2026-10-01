"""
Canonical interfaces and domain models for document ingestion and parsing.

Rorak AI V2.5 Step 1: Parser and Adaptor Boundary Architecture.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from langchain_core.documents import Document


@dataclass
class StructuredBlock:
    """
    A discrete structured element within a parsed document.
    Represents semantic units like pages, paragraphs, sections, tables, or code.
    """

    text: str
    block_type: str = "text"
    page_number: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize structured block to a dictionary."""
        return {
            "text": self.text,
            "block_type": self.block_type,
            "page_number": self.page_number,
            "metadata": dict(self.metadata),
        }

    def to_langchain_document(
        self,
        source_filename: str = "",
        source_type: str = "",
        document_id: Optional[str] = None,
    ) -> Document:
        """Convert structured block into a LangChain Document with rich metadata."""
        meta = dict(self.metadata)
        if source_filename:
            meta["source"] = source_filename
        if source_type:
            meta["source_type"] = source_type
        if document_id:
            meta["document_id"] = document_id
        if self.page_number is not None:
            meta["page"] = self.page_number
        meta["block_type"] = self.block_type

        return Document(
            page_content=self.text,
            metadata=meta,
        )


@dataclass
class ParsedDocument:
    """
    Canonical document representation returned by all document parsers.
    The rest of the ingestion pipeline operates solely on this canonical structure.
    """

    source_filename: str
    source_type: str
    structured_blocks: List[StructuredBlock] = field(default_factory=list)
    document_id: Optional[UUID | str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.document_id is None:
            self.document_id = uuid4()

    @property
    def blocks(self) -> List[StructuredBlock]:
        """Alias for structured_blocks."""
        return self.structured_blocks

    def get_full_text(self, separator: str = "\n\n") -> str:
        """Combine all structured blocks into full text representation."""
        texts = [b.text.strip() for b in self.structured_blocks if b.text and b.text.strip()]
        return separator.join(texts)

    def to_langchain_documents(self) -> List[Document]:
        """
        Convert structured blocks into LangChain Document objects suitable
        for text splitting and embedding generation.
        """
        doc_id_str = str(self.document_id) if self.document_id else None
        documents: List[Document] = []

        for block in self.structured_blocks:
            if not block.text or not block.text.strip():
                continue
            documents.append(
                block.to_langchain_document(
                    source_filename=self.source_filename,
                    source_type=self.source_type,
                    document_id=doc_id_str,
                )
            )

        return documents

    def to_dict(self) -> Dict[str, Any]:
        """Serialize parsed document to a dictionary."""
        return {
            "document_id": str(self.document_id) if self.document_id else None,
            "source_filename": self.source_filename,
            "source_type": self.source_type,
            "structured_blocks": [b.to_dict() for b in self.structured_blocks],
            "metadata": dict(self.metadata),
        }


class DocumentParser(ABC):
    """
    Abstract base interface for format-specific document parsers / adapters.
    Each adapter isolates the third-party libraries and parsing logic for a specific format.
    """

    @abstractmethod
    def supports(self, file_type: str) -> bool:
        """
        Determine if this parser supports the specified file format, extension, or MIME type.
        """
        raise NotImplementedError

    @abstractmethod
    def parse(self, file_path: Path | str, **kwargs: Any) -> ParsedDocument:
        """
        Parse the document at the given file path into a canonical ParsedDocument.
        """
        raise NotImplementedError
