from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from backend.models.db.document import Document


class DocumentRepository:

    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, document_id: UUID) -> Document | None:
        stmt = select(Document).where(Document.id == document_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def get_by_workspace(
        self,
        workspace_id: UUID,
    ) -> list[Document]:
        stmt = select(Document).where(
            Document.workspace_id == workspace_id
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_by_workspace_paginated(
        self,
        workspace_id: UUID,
        skip: int = 0,
        limit: int = 20,
    ) -> list[Document]:
        stmt = (
            select(Document)
            .where(Document.workspace_id == workspace_id)
            .order_by(Document.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars().all())

    def count_by_workspace(self, workspace_id: UUID) -> int:
        stmt = select(func.count(Document.id)).where(
            Document.workspace_id == workspace_id
        )
        return self.db.execute(stmt).scalar() or 0

    def create(self, document: Document) -> Document:
        self.db.add(document)
        self.db.flush()
        return document

    def update_status(self, document_id: UUID, status: str) -> Document | None:
        doc = self.get_by_id(document_id)
        if doc:
            doc.status = status
            self.db.flush()
        return doc

    def delete(self, document: Document) -> None:
        self.db.delete(document)
        self.db.flush()