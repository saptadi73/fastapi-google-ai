from uuid import UUID

from fastapi import Depends

from app.api.dependencies import CurrentUser, Session, require_roles
from app.core.exceptions import success
from app.core.routing import APIRouter
from app.domain.enums import EDIT_ROLES, REVIEW_ROLES
from app.repositories.base import record
from app.schemas.analytics_rules import AnalyticsRuleDefinition, AnalyticsRulesDecision, AnalyticsRulesImport
from app.services.analytics_rules_service import AnalyticsRulesService
from app.services.workflow_policy_service import workflow_reviewer

router = APIRouter(prefix="/analytics-rules", tags=["Analytics rules"])


@router.post("", dependencies=[Depends(require_roles(*EDIT_ROLES))])
async def create(data: AnalyticsRuleDefinition, session: Session, user: CurrentUser):
    return success(await AnalyticsRulesService(session, user).create(data))


@router.post("/import-sheet", dependencies=[Depends(require_roles(*EDIT_ROLES))])
async def import_sheet(data: AnalyticsRulesImport, session: Session, user: CurrentUser):
    return success(await AnalyticsRulesService(session, user).import_sheet(data))


@router.get("/{bundle_id}")
async def get(bundle_id: UUID, session: Session, user: CurrentUser):
    bundle, _ = await AnalyticsRulesService(session, user).get(bundle_id)
    return success(record(bundle))


@router.post("/{bundle_id}/decision", dependencies=[Depends(workflow_reviewer)])
async def decide(bundle_id: UUID, data: AnalyticsRulesDecision, session: Session, user: CurrentUser):
    return success(await AnalyticsRulesService(session, user).decide(bundle_id, data))


@router.post("/{bundle_id}/preview", dependencies=[Depends(require_roles(*EDIT_ROLES, *REVIEW_ROLES))])
async def preview(bundle_id: UUID, session: Session, user: CurrentUser):
    return success(await AnalyticsRulesService(session, user).evaluate(bundle_id, preview=True))


@router.post("/{bundle_id}/evaluate")
async def evaluate(bundle_id: UUID, session: Session, user: CurrentUser):
    return success(await AnalyticsRulesService(session, user).evaluate(bundle_id))
