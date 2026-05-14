"""Document ORM model (SPEC / PLAN)."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, func, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.project import Project


class DocumentType(StrEnum):
    SPEC = "SPEC"
    PLAN = "PLAN"


class DocumentStatus(StrEnum):
    DRAFT = "draft"
    APPROVED = "approved"
    REVISION_REQUESTED = "revision_requested"


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint("type IN ('SPEC','PLAN')", name="ck_documents_type"),
        CheckConstraint(
            "status IN ('draft','approved','revision_requested')",
            name="ck_documents_status",
        ),
        Index("idx_documents_project_type", "project_id", "type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    document_type: Mapped[DocumentType] = mapped_column(
        "type",
        String(10),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    status: Mapped[DocumentStatus] = mapped_column(
        String(30),
        nullable=False,
        server_default=text("'draft'"),
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    project: Mapped[Project] = relationship(back_populates="documents")
