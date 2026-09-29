from pathlib import Path
from uuid import uuid4

from backend.services.document_storage import (
    build_storage_key,
    calculate_sha256,
    delete_artifact,
    save_artifact,
)


def test_calculate_sha256(tmp_path: Path):
    file_path = tmp_path / "test.txt"
    file_path.write_bytes(b"hello rorak")

    checksum = calculate_sha256(file_path)

    assert len(checksum) == 64
    assert checksum == calculate_sha256(file_path)


def test_build_storage_key():
    document_id = uuid4()

    storage_key = build_storage_key(
        document_id,
        "research.pdf",
    )

    assert storage_key == (
        f"documents/{document_id}/original/research.pdf"
    )


def test_save_and_delete_artifact(tmp_path: Path):
    source = tmp_path / "research.pdf"
    source.write_bytes(b"PDF test content")

    document_id = uuid4()

    storage_key = save_artifact(
        source_path=source,
        document_id=document_id,
        filename="research.pdf",
    )

    assert storage_key.startswith(
        f"documents/{document_id}/original/"
    )

    delete_artifact(storage_key)