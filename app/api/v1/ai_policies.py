from uuid import UUID

from fastapi import Depends

from app.api.dependencies import CurrentUser, Session, require_roles
from app.core.exceptions import success
from app.core.routing import APIRouter
from app.domain.enums import EDIT_ROLES, REVIEW_ROLES
from app.schemas.ai_policy import AITaskPolicyAction, AITaskPolicyCreate
from app.services.ai_policy_service import AITaskPolicyService

router = APIRouter(prefix="/ai-task-policies", tags=["AI task policies"])
edit = [Depends(require_roles(*EDIT_ROLES))]
review = [Depends(require_roles(*REVIEW_ROLES))]


@router.get("")
async def list_policies(session: Session, user: CurrentUser):
    return success(await AITaskPolicyService(session, user).list())


@router.post("", status_code=201, dependencies=edit)
async def create_policy(data: AITaskPolicyCreate, session: Session, user: CurrentUser):
    return success(await AITaskPolicyService(session, user).create(data))


@router.post("/{policy_id}/approve", dependencies=review)
async def approve_policy(policy_id: UUID, data: AITaskPolicyAction, session: Session, user: CurrentUser):
    return success(await AITaskPolicyService(session, user).approve(policy_id, data))


@router.post("/{policy_id}/reject", dependencies=review)
async def reject_policy(policy_id: UUID, data: AITaskPolicyAction, session: Session, user: CurrentUser):
    return success(await AITaskPolicyService(session, user).reject(policy_id, data))
