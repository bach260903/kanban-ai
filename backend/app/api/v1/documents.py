"""Documents + generate-spec (US4 / T037)."""

from __future__ import annotations

import asyncio
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.exceptions import InvalidTransitionError, NotFoundError
from app.middleware.auth import require_jwt
from app.models.agent_run import AgentRun, AgentRunStatus, AgentType
from app.models.document import Document, DocumentStatus, DocumentType
from app.schemas.document import (
    DocumentContentUpdate,
    DocumentListItem,
    DocumentResponse,
    DocumentTypeFilter,
    GenerateSpecRequest,
    GenerateSpecResponse,
)
from app.services.document_service import DocumentService
from app.services.intent_service import IntentService
from app.services.project_service import ProjectService
from app.services.spec_generation_runner import run_generate_spec_task

router = APIRouter(prefix="/projects", tags=["documents"])


@router.get("/{project_id}/documents", response_model=list[DocumentListItem])
async def list_documents(
    project_id: UUID,
    _sub: Annotated[str, Depends(require_jwt)],
    session: Annotated[AsyncSession, Depends(get_db)],
    doc_type: Annotated[DocumentTypeFilter | None, Query(alias="type")] = None,
) -> list[DocumentListItem]:
    await ProjectService.get(session, project_id)
    stmt = select(Document).where(Document.project_id == project_id).order_by(Document.updated_at.desc())
    if doc_type is not None:
        stmt = stmt.where(Document.document_type == DocumentType(doc_type))
    result = await session.execute(stmt)
    rows = list(result.scalars().all())
    return [DocumentListItem.model_validate(r) for r in rows]


@router.get("/{project_id}/documents/{document_id}", response_model=DocumentResponse)
async def get_document(
    project_id: UUID,
    document_id: UUID,
    _sub: Annotated[str, Depends(require_jwt)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> DocumentResponse:
    await ProjectService.get(session, project_id)
    document = await session.get(Document, document_id)
    if document is None or document.project_id != project_id:
        raise NotFoundError("Document not found.")
    return DocumentResponse.model_validate(document)


@router.put("/{project_id}/documents/{document_id}", response_model=DocumentResponse)
async def update_document(
    project_id: UUID,
    document_id: UUID,
    body: DocumentContentUpdate,
    _sub: Annotated[str, Depends(require_jwt)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> DocumentResponse:
    document = await DocumentService.update_content(
        session, document_id, body.content, project_id=project_id
    )
    await session.commit()
    await session.refresh(document)
    return DocumentResponse.model_validate(document)


@router.post(
    "/{project_id}/generate-spec",
    response_model=GenerateSpecResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def generate_spec(
    project_id: UUID,
    body: GenerateSpecRequest,
    _sub: Annotated[str, Depends(require_jwt)],
    session: Annotated[AsyncSession, Depends(get_db)],
    force: bool = False,
) -> GenerateSpecResponse:
    await ProjectService.get(session, project_id)

    try:
        spec_doc = await DocumentService.get_by_type(session, project_id, DocumentType.SPEC)
    except NotFoundError:
        spec_doc = await DocumentService.create(session, project_id, DocumentType.SPEC, "")
    else:
        if spec_doc.status == DocumentStatus.APPROVED and not force:
            raise InvalidTransitionError(
                "An approved SPEC already exists. Generating a new SPEC will replace it. "
                "Confirm with ?force=true.",
            )
        if spec_doc.status == DocumentStatus.APPROVED and force:
            spec_doc.status = DocumentStatus.DRAFT
            spec_doc.content = ""
            await session.flush()

    intent_row = await IntentService.create(session, project_id, body.intent.strip())

    agent_run = AgentRun(
        project_id=project_id,
        task_id=None,
        agent_type=AgentType.ARCHITECT,
        status=AgentRunStatus.RUNNING,
    )
    session.add(agent_run)
    await session.flush()

    await session.commit()

    asyncio.create_task(
        run_generate_spec_task(
            project_id,
            agent_run.id,
            spec_doc.id,
            body.intent.strip(),
        )
    )

    return GenerateSpecResponse(
        agent_run_id=agent_run.id,
        intent_id=intent_row.id,
        document_id=spec_doc.id,
    )
