"""
CSV / Tabular document parser adapter.

Rorak AI V2.5 Step 4: Table-aware CSV parser with column context preservation,
deterministic header handling, memory-bounded streaming, and rich row metadata.
"""
import csv
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from backend.parsers.base import DocumentParser, ParsedDocument, StructuredBlock
from backend.parsers.registry import ParserError, UnsupportedFormatError


logger = logging.getLogger(__name__)


class CSVDocumentParser(DocumentParser):
    """
    Parser adapter for Comma-Separated Values (.csv) and tabular text files.
    Enforces deterministic column header handling, injects explicit column context
    into every row representation, bounds memory usage for large tables,
    and attaches row-range and column metadata to prevent context loss after chunking.
    """

    SUPPORTED_EXTENSIONS = {"csv"}
    SUPPORTED_MIMES = {"text/csv", "application/csv"}

    CANDIDATE_ENCODINGS = ("utf-8", "utf-8-sig", "cp1252", "latin-1")
    COMMON_DELIMITERS = [",", ";", "\t", "|"]

    DEFAULT_MAX_ROWS = 10000
    DEFAULT_ROWS_PER_BLOCK = 1

    def supports(self, file_type: str) -> bool:
        """Return True if the file type matches CSV extension or MIME type."""
        if not file_type:
            return False
        normalized = file_type.strip().lower().lstrip(".")
        return (
            normalized in self.SUPPORTED_EXTENSIONS
            or file_type.strip().lower() in self.SUPPORTED_MIMES
        )

    def _detect_encoding_and_check_binary(self, path: Path) -> Tuple[str, bytes]:
        """
        Scan initial byte sample to reject binary files and determine safe text encoding.
        """
        with open(path, "rb") as f:
            sample = f.read(8192)

        if b"\x00" in sample:
            raise ParserError(
                f"Binary content detected in CSV file '{path.name}' (null bytes present)."
            )

        if not sample:
            return "utf-8", b""

        for encoding in self.CANDIDATE_ENCODINGS:
            try:
                sample.decode(encoding)
                return encoding, sample
            except UnicodeDecodeError:
                continue

        raise ParserError(
            f"Unable to decode CSV file '{path.name}' with supported encodings {self.CANDIDATE_ENCODINGS}."
        )

    def _sniff_delimiter(self, sample_bytes: bytes, encoding: str) -> str:
        """
        Attempt to detect CSV delimiter from sample text, falling back to standard comma.
        """
        if not sample_bytes:
            return ","

        try:
            sample_text = sample_bytes.decode(encoding, errors="ignore")
            # Take first few non-empty lines for sniffing
            lines = [l for l in sample_text.splitlines() if l.strip()][:5]
            sniff_sample = "\n".join(lines)
            if sniff_sample:
                dialect = csv.Sniffer().sniff(sniff_sample, delimiters=",\t;|")
                if dialect.delimiter in self.COMMON_DELIMITERS:
                    return dialect.delimiter
        except Exception:
            pass

        # Fallback heuristic: count common delimiters in the first line
        try:
            first_line = sample_bytes.decode(encoding, errors="ignore").splitlines()[0]
            counts = {d: first_line.count(d) for d in self.COMMON_DELIMITERS}
            best_delimiter = max(counts, key=counts.get)  # type: ignore
            if counts[best_delimiter] > 0:
                return best_delimiter
        except Exception:
            pass

        return ","

    def _clean_and_disambiguate_headers(self, raw_headers: List[str]) -> List[str]:
        """
        Normalize column headers: strip whitespace, populate empty names,
        and disambiguate duplicate column names deterministically.
        """
        cleaned_headers: List[str] = []
        counts: Dict[str, int] = {}

        for idx, h in enumerate(raw_headers):
            name = h.strip() if h else ""
            if not name:
                name = f"unnamed_{idx + 1}"

            if name in counts:
                counts[name] += 1
                final_name = f"{name}_{counts[name]}"
            else:
                counts[name] = 1
                final_name = name

            cleaned_headers.append(final_name)

        return cleaned_headers

    def _format_row_with_context(
        self,
        headers: List[str],
        row_values: List[str],
        row_num: int,
    ) -> str:
        """
        Render a row with explicit column context so it remains semantically
        complete and self-contained after chunking.
        """
        parts: List[str] = [f"Row {row_num}:"]
        for idx, col in enumerate(headers):
            val = row_values[idx].strip() if idx < len(row_values) else ""
            parts.append(f"{col}: {val}")

        return " | ".join(parts)

    def parse(
        self,
        file_path: Path | str,
        document_id: Optional[UUID | str] = None,
        rows_per_block: Optional[int] = None,
        max_rows: Optional[int] = None,
        **kwargs: Any,
    ) -> ParsedDocument:
        """
        Parse a CSV document into a canonical ParsedDocument with table-aware row blocks.
        """
        path_obj = Path(file_path)

        if not path_obj.exists():
            raise FileNotFoundError(f"CSV file not found: {path_obj}")

        if not path_obj.is_file():
            raise ValueError(f"Path is not a file: {path_obj}")

        # Extension check
        ext = path_obj.suffix.lower().lstrip(".")
        if ext not in self.SUPPORTED_EXTENSIONS and path_obj.suffix != "":
            raise UnsupportedFormatError(
                f"File '{path_obj.name}' is not a CSV file (extension is '{path_obj.suffix}')."
            )

        # Decode & inspect binary
        encoding, sample_bytes = self._detect_encoding_and_check_binary(path_obj)
        file_size = path_obj.stat().st_size

        if file_size == 0 or not sample_bytes.strip():
            return ParsedDocument(
                document_id=document_id,
                source_filename=path_obj.name,
                source_type="csv",
                structured_blocks=[],
                metadata={
                    "source_type": "csv",
                    "file_size": 0,
                    "total_rows": 0,
                    "column_count": 0,
                    "columns": [],
                },
            )

        delimiter = self._sniff_delimiter(sample_bytes, encoding)
        logger.debug("Parsing CSV %s with delimiter '%s' and encoding %s", path_obj.name, delimiter, encoding)

        row_limit = max_rows if max_rows is not None else self.DEFAULT_MAX_ROWS
        batch_size = rows_per_block if rows_per_block is not None else self.DEFAULT_ROWS_PER_BLOCK
        if batch_size < 1:
            batch_size = 1

        blocks: List[StructuredBlock] = []
        headers: List[str] = []
        data_row_count = 0
        is_truncated = False

        # Memory-bounded streaming line-by-line using csv.reader
        try:
            with open(path_obj, mode="r", encoding=encoding, newline="", errors="replace") as csv_file:
                reader = csv.reader(csv_file, delimiter=delimiter)

                # 1. Deterministic header extraction
                for raw_row in reader:
                    if any(c.strip() for c in raw_row):
                        headers = self._clean_and_disambiguate_headers(raw_row)
                        break

                if not headers:
                    # Empty or blank file
                    return ParsedDocument(
                        document_id=document_id,
                        source_filename=path_obj.name,
                        source_type="csv",
                        structured_blocks=[],
                        metadata={
                            "source_type": "csv",
                            "file_size": file_size,
                            "total_rows": 0,
                            "column_count": 0,
                            "columns": [],
                        },
                    )

                # 2. Iterate data rows and construct column-context blocks
                current_batch_texts: List[str] = []
                current_batch_data: List[Dict[str, str]] = []
                batch_start_row = 1

                for raw_row in reader:
                    # Skip empty rows
                    if not any(c.strip() for c in raw_row):
                        continue

                    data_row_count += 1

                    # Pad row if shorter than headers
                    padded_row = list(raw_row)
                    if len(padded_row) < len(headers):
                        padded_row.extend([""] * (len(headers) - len(padded_row)))

                    # Extract row dictionary mapping
                    row_dict = {
                        headers[i]: padded_row[i].strip() if i < len(padded_row) else ""
                        for i in range(len(headers))
                    }
                    current_batch_data.append(row_dict)

                    # Build row text with explicit column context
                    formatted_row = self._format_row_with_context(
                        headers=headers,
                        row_values=padded_row,
                        row_num=data_row_count,
                    )
                    current_batch_texts.append(formatted_row)

                    # If batch is full, emit a StructuredBlock
                    if len(current_batch_texts) >= batch_size:
                        block_text = "\n".join(current_batch_texts)
                        blocks.append(
                            StructuredBlock(
                                text=block_text,
                                block_type="table_row",
                                metadata={
                                    "source": path_obj.name,
                                    "row_start": batch_start_row,
                                    "row_end": data_row_count,
                                    "row_index": batch_start_row if batch_size == 1 else None,
                                    "row_count": len(current_batch_texts),
                                    "columns": list(headers),
                                    "row_data": current_batch_data[0] if batch_size == 1 else current_batch_data,
                                },
                            )
                        )
                        current_batch_texts = []
                        current_batch_data = []
                        batch_start_row = data_row_count + 1

                    # Memory bounding guard
                    if data_row_count >= row_limit:
                        is_truncated = True
                        logger.warning(
                            "CSV %s reached max_rows limit (%d). Bounding table memory.",
                            path_obj.name,
                            row_limit,
                        )
                        break

                # Flush any remaining rows in the last batch
                if current_batch_texts:
                    block_text = "\n".join(current_batch_texts)
                    blocks.append(
                        StructuredBlock(
                            text=block_text,
                            block_type="table_row",
                            metadata={
                                "source": path_obj.name,
                                "row_start": batch_start_row,
                                "row_end": data_row_count,
                                "row_index": batch_start_row if len(current_batch_texts) == 1 else None,
                                "row_count": len(current_batch_texts),
                                "columns": list(headers),
                                "row_data": current_batch_data[0] if len(current_batch_data) == 1 else current_batch_data,
                            },
                        )
                    )

        except Exception as e:
            if isinstance(e, ParserError):
                raise
            raise ParserError(f"Failed to parse CSV file '{path_obj.name}': {e}")

        metadata: Dict[str, Any] = {
            "source_type": "csv",
            "file_size": file_size,
            "delimiter": delimiter,
            "columns": headers,
            "column_count": len(headers),
            "total_rows": data_row_count,
            "block_count": len(blocks),
            "truncated": is_truncated,
        }

        return ParsedDocument(
            document_id=document_id,
            source_filename=path_obj.name,
            source_type="csv",
            structured_blocks=blocks,
            metadata=metadata,
        )
