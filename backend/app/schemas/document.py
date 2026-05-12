"""Pydantic schemas for documents (SPEC / PLAN)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.document import DocumentStatus, DocumentType


class DocumentResponse(BaseModel):
    """Wire JSON uses ``type`` (see contracts/rest-api.md); ORM attribute is ``document_type``."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    project_id: UUID
    document_type: DocumentType = Field(serialization_alias="type")
    content: str
    status: DocumentStatus
    version: int
    created_at: datetime
    updated_at: datetime


class DocumentUpdate(BaseModel):
    content: str


class RevisionRequest(BaseModel):
    feedback: str = Field(..., min_length=1)
