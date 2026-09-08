from uuid import UUID

from fastapi import Depends, Query

from app.api.dependencies import CurrentUser, Session, require_roles
from app.core.exceptions import success
from app.core.routing import APIRouter
from app.domain.enums import EDIT_ROLES, REVIEW_ROLES
from app.domain.import_workflow import ImportAction, ImportStatus
from app.schemas.import_review import (
    ImportProposalResolution,
    ImportQuestionDecision,
    ImportReviewAction,
    ImportReviewCreate,
    ImportReviewPreviewRequest,
    ImportReviewApproveRequest,
    ImportReviewApplyRequest,
    ImportReferenceResolveRequest,
)
from app.services.import_review_service import ImportReviewService

router = APIRouter(tags=["Import reviews"], dependencies=[Depends(require_roles(*EDIT_ROLES, *REVIEW_ROLES))])
edit = [Depends(require_roles(*EDIT_ROLES))]


@router.post("/import-reviews", status_code=202, dependencies=edit)
async def create_import_review(data: ImportReviewCreate, session: Session, user: CurrentUser):
    return success(await ImportReviewService(session, user).create(data))


@router.get("/import-reviews")
async def list_import_reviews(
    session: Session,
    user: CurrentUser,
    status: ImportStatus | None = None,
    source_sheet_id: UUID | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
):
    return success(
        await ImportReviewService(session, user).list(status, source_sheet_id, offset, limit),
        offset=offset,
        limit=limit,
    )


@router.get("/import-reviews/{review_id}")
async def get_import_review(review_id: UUID, session: Session, user: CurrentUser):
    return success(await ImportReviewService(session, user).detail(review_id))


@router.get("/import-reviews/{review_id}/findings")
async def import_findings(
    review_id: UUID,
    session: Session,
    user: CurrentUser,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
):
    return success(
        await ImportReviewService(session, user).findings(review_id, offset, limit),
        offset=offset,
        limit=limit,
    )


@router.get("/import-reviews/{review_id}/questions")
async def import_questions(
    review_id: UUID,
    session: Session,
    user: CurrentUser,
    status: str | None = Query(None, pattern=r"^(OPEN|ANSWERED|PENDING_APPROVAL|CANCELLED)$"),
    category: str | None = Query(None, max_length=40),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
):
    return success(
        await ImportReviewService(session, user).questions(review_id, status, category, offset, limit),
        offset=offset,
        limit=limit,
    )


@router.post("/import-reviews/{review_id}/questions/{question_id}/answer", dependencies=edit)
async def answer_import_question(
    review_id: UUID,
    question_id: UUID,
    data: ImportQuestionDecision,
    session: Session,
    user: CurrentUser,
):
    return success(await ImportReviewService(session, user).answer_question(review_id, question_id, data))


@router.post(
    "/import-reviews/{review_id}/questions/{question_id}/resolve-master-proposal",
    dependencies=[Depends(require_roles(*REVIEW_ROLES))],
)
async def resolve_master_proposal(
    review_id: UUID,
    question_id: UUID,
    data: ImportProposalResolution,
    session: Session,
    user: CurrentUser,
):
    return success(
        await ImportReviewService(session, user).resolve_master_proposal(review_id, question_id, data)
    )


@router.post("/import-reviews/{review_id}/cancel", dependencies=edit)
async def cancel_import(review_id: UUID, data: ImportReviewAction, session: Session, user: CurrentUser):
    return success(await ImportReviewService(session, user).action(review_id, data, ImportAction.CANCEL))


@router.post("/import-reviews/{review_id}/revalidate", dependencies=edit)
async def revalidate_import(review_id: UUID, data: ImportReviewAction, session: Session, user: CurrentUser):
    return success(await ImportReviewService(session, user).action(review_id, data, ImportAction.REVALIDATE))


@router.post("/import-reviews/{review_id}/resume", dependencies=edit)
async def resume_import(review_id: UUID, data: ImportReviewAction, session: Session, user: CurrentUser):
    return success(await ImportReviewService(session, user).action(review_id, data, ImportAction.RESUME))


@router.post("/import-reviews/{review_id}/preview", dependencies=edit)
async def preview_import(review_id: UUID, data: ImportReviewPreviewRequest, session: Session, user: CurrentUser):
    return success(await ImportReviewService(session, user).preview(review_id, data))


@router.post("/import-reviews/{review_id}/approve", dependencies=[Depends(require_roles(*REVIEW_ROLES))])
async def approve_import(review_id: UUID, data: ImportReviewApproveRequest, session: Session, user: CurrentUser):
    return success(await ImportReviewService(session, user).approve(review_id, data))


@router.post("/import-reviews/{review_id}/apply", dependencies=edit)
async def apply_import(review_id: UUID, data: ImportReviewApplyRequest, session: Session, user: CurrentUser):
    return success(await ImportReviewService(session, user).apply(review_id, data))


@router.post("/import-reviews/{review_id}/resolve-reference")
async def resolve_import_reference(
    review_id: UUID, data: ImportReferenceResolveRequest, session: Session, user: CurrentUser
):
    return success(await ImportReviewService(session, user).resolve_reference(review_id, data))
