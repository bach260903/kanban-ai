"""Pydantic schemas for documents (US4)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.document import DocumentStatus, DocumentType

DocumentTypeFilter = Literal["SPEC", "PLAN"]


class DocumentListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    document_type: DocumentType = Field(serialization_alias="type")
    status: DocumentStatus
    version: int
    created_at: datetime
    updated_at: datetime


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    document_type: DocumentType = Field(serialization_alias="type")
    content: str
    status: DocumentStatus
    version: int
    created_at: datetime
    updated_at: datetime


class DocumentContentUpdate(BaseModel):
    content: str = Field(..., min_length=1)


# Backward-compatible name for ``app.schemas`` package exports.
DocumentUpdate = DocumentContentUpdate


class RevisionRequest(BaseModel):
    """PO feedback for document revision (used by T041)."""

    feedback: str = Field(..., min_length=1)


class GenerateSpecRequest(BaseModel):
    intent: str = Field(..., min_length=10, max_length=5000)


class GenerateSpecResponse(BaseModel):
    agent_run_id: UUID
    intent_id: UUID
    document_id: UUID
    status: str = "running"
    message: str = "SPEC generation started."
