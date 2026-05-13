"""Document persistence and approval lifecycle (US4 / T036)."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import InvalidTransitionError, NotFoundError
from app.models.document import Document, DocumentStatus, DocumentType
from app.models.feedback import Feedback, FeedbackReferenceType
from app.models.project import Project


class DocumentService:
    """CRUD and HIL-related transitions for SPEC / PLAN documents."""

    @staticmethod
    async def _get_document(session: AsyncSession, document_id: UUID) -> Document:
        document = await session.get(Document, document_id)
        if document is None:
            raise NotFoundError("Document not found.")
        return document

    @staticmethod
    async def create(
        session: AsyncSession,
        project_id: UUID,
        document_type: DocumentType,
        content: str = "",
    ) -> Document:
        """Insert a new document row for ``project_id`` and ``document_type`` (status ``draft``)."""
        project = await session.get(Project, project_id)
        if project is None:
            raise NotFoundError("Project not found.")

        existing = await session.scalar(
            select(Document.id).where(
                Document.project_id == project_id,
                Document.document_type == document_type,
            )
        )
        if existing is not None:
            raise InvalidTransitionError(
                "A document of this type already exists for this project."
            )

        document = Document(
            project_id=project_id,
            document_type=document_type,
            content=content,
            status=DocumentStatus.DRAFT,
        )
        session.add(document)
        await session.flush()
        return document

    @staticmethod
    async def get_by_type(
        session: AsyncSession,
        project_id: UUID,
        document_type: DocumentType,
    ) -> Document:
        """Return the document for ``project_id`` + ``document_type`` (latest row if duplicates exist)."""
        result = await session.execute(
            select(Document)
            .where(
                Document.project_id == project_id,
                Document.document_type == document_type,
            )
            .order_by(Document.updated_at.desc())
        )
        document = result.scalars().first()
        if document is None:
            raise NotFoundError("Document not found.")
        return document

    @staticmethod
    async def update_content(
        session: AsyncSession,
        document_id: UUID,
        content: str,
        *,
        project_id: UUID | None = None,
    ) -> Document:
        """Manual PO edit: updates ``content`` only (no ``status`` / ``version`` change)."""
        document = await DocumentService._get_document(session, document_id)
        if project_id is not None and document.project_id != project_id:
            raise NotFoundError("Document not found.")

        if document.status not in (DocumentStatus.DRAFT, DocumentStatus.REVISION_REQUESTED):
            raise InvalidTransitionError(
                "Document content can only be edited while in draft or revision_requested state."
            )

        document.content = content
        document.updated_at = datetime.now(timezone.utc)
        await session.flush()
        return document

    @staticmethod
    async def approve(session: AsyncSession, document_id: UUID) -> Document:
        """Set status to ``approved`` when current state allows HIL approval."""
        document = await DocumentService._get_document(session, document_id)
        if document.status not in (
            DocumentStatus.DRAFT,
            DocumentStatus.REVISION_REQUESTED,
        ):
            raise InvalidTransitionError(
                "Document must be in draft or revision_requested state to approve."
            )
        document.status = DocumentStatus.APPROVED
        document.updated_at = datetime.now(timezone.utc)
        await session.flush()
        return document

    @staticmethod
    async def request_revision(
        session: AsyncSession,
        document_id: UUID,
        feedback: str,
    ) -> tuple[Document, Feedback]:
        """Append revision ``feedback`` and set status to ``revision_requested``."""
        document = await DocumentService._get_document(session, document_id)
        text = feedback.strip()
        if not text:
            raise InvalidTransitionError("Feedback must not be empty.")

        if document.status not in (
            DocumentStatus.DRAFT,
            DocumentStatus.APPROVED,
            DocumentStatus.REVISION_REQUESTED,
        ):
            raise InvalidTransitionError(
                "Document must be in draft, approved, or revision_requested state to request revision."
            )

        fb = Feedback(
            project_id=document.project_id,
            reference_type=FeedbackReferenceType.DOCUMENT,
            reference_id=document.id,
            content=text,
        )
        session.add(fb)
        document.status = DocumentStatus.REVISION_REQUESTED
        document.updated_at = datetime.now(timezone.utc)
        await session.flush()
        return document, fb
