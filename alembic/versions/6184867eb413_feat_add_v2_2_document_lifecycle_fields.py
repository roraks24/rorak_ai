"""feat: add V2.2 document lifecycle fields

Revision ID: 6184867eb413
Revises: b56ab54c4f90
Create Date: 2026-09-29 20:37:47.800617

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "6184867eb413"
down_revision: Union[str, Sequence[str], None] = "b56ab54c4f90"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add V2.2 document lifecycle fields safely."""

    # ---------------------------------------------------------
    # 1. Add new columns as nullable first.
    #    Existing rows already exist in the database, so we
    #    cannot add NOT NULL columns without backfilling them.
    # ---------------------------------------------------------

    op.add_column(
        "documents",
        sa.Column(
            "display_name",
            sa.String(length=255),
            nullable=True,
        ),
    )

    op.add_column(
        "documents",
        sa.Column(
            "mime_type",
            sa.String(length=100),
            nullable=True,
        ),
    )

    op.add_column(
        "documents",
        sa.Column(
            "chunk_count",
            sa.Integer(),
            nullable=True,
        ),
    )

    op.add_column(
        "documents",
        sa.Column(
            "storage_key",
            sa.String(length=500),
            nullable=True,
        ),
    )

    op.add_column(
        "documents",
        sa.Column(
            "checksum_sha256",
            sa.String(length=64),
            nullable=True,
        ),
    )

    op.add_column(
        "documents",
        sa.Column(
            "failure_reason",
            sa.Text(),
            nullable=True,
        ),
    )

    # ---------------------------------------------------------
    # 2. Backfill display_name for existing documents.
    #
    # Prefer original_filename, then filename.
    # Both columns already exist in V2.1.
    # ---------------------------------------------------------

    op.execute(
        """
        UPDATE documents
        SET display_name =
            COALESCE(
                NULLIF(TRIM(original_filename), ''),
                filename
            )
        """
    )

    # ---------------------------------------------------------
    # 3. Backfill MIME type.
    #
    # Existing V2.1 documents are currently PDF-oriented.
    # Preserve a sensible MIME value for legacy rows.
    # ---------------------------------------------------------

    op.execute(
        """
        UPDATE documents
        SET mime_type =
            CASE
                WHEN LOWER(file_type) = 'pdf'
                    THEN 'application/pdf'
                ELSE 'application/octet-stream'
            END
        """
    )

    # ---------------------------------------------------------
    # 4. Backfill chunk_count from the authoritative
    #    document_chunks table.
    # ---------------------------------------------------------

    op.execute(
        """
        UPDATE documents AS d
        SET chunk_count = (
            SELECT COUNT(*)
            FROM document_chunks AS dc
            WHERE dc.document_id = d.id
        )
        """
    )

    # ---------------------------------------------------------
    # 5. Give legacy documents a stable storage key.
    #
    # These are legacy records created before durable artifact
    # storage existed. This creates a deterministic identity for
    # future V2.2 storage handling; it does NOT claim that a
    # legacy physical file currently exists.
    # ---------------------------------------------------------

    op.execute(
        """
        UPDATE documents
        SET storage_key =
            'legacy/' || id::text || '/' || filename
        """
    )

    # ---------------------------------------------------------
    # 6. Convert fields that must be present into NOT NULL.
    # ---------------------------------------------------------

    op.alter_column(
        "documents",
        "display_name",
        existing_type=sa.String(length=255),
        nullable=False,
    )

    op.alter_column(
        "documents",
        "mime_type",
        existing_type=sa.String(length=100),
        nullable=False,
    )

    op.alter_column(
        "documents",
        "chunk_count",
        existing_type=sa.Integer(),
        nullable=False,
    )

    op.alter_column(
        "documents",
        "storage_key",
        existing_type=sa.String(length=500),
        nullable=False,
    )

    # checksum_sha256 remains nullable.
    # failure_reason remains nullable.

    # IMPORTANT:
    # Do NOT alter documents.status.
    # V2.2 keeps the existing VARCHAR(50) type.


def downgrade() -> None:
    """Remove V2.2 document lifecycle fields."""

    op.drop_column("documents", "failure_reason")
    op.drop_column("documents", "checksum_sha256")
    op.drop_column("documents", "storage_key")
    op.drop_column("documents", "chunk_count")
    op.drop_column("documents", "mime_type")
    op.drop_column("documents", "display_name")