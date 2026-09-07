from datetime import date

from fastapi import Depends

from app.api.dependencies import CurrentUser, Session, require_roles
from app.core.exceptions import success
from app.core.routing import APIRouter
from app.domain.enums import DATA_ROLES
from app.services.monitoring_service import MonitoringService
from app.services.report_service import ReportService

router = APIRouter(prefix="/reports", tags=["Dashboard reports"])


@router.get("/sales/summary")
async def sales_summary(start_date: date, end_date: date, session: Session, user: CurrentUser):
    result = await ReportService(session, user).sales(start_date, end_date)
    return success(result["rows"], **result["meta"])


@router.get("/sales/by-branch")
async def by_branch(start_date: date, end_date: date, session: Session, user: CurrentUser):
    result = await ReportService(session, user).sales(start_date, end_date, ["branch_name"])
    return success(result["rows"], **result["meta"])


@router.get("/sales/trend")
async def sales_trend(start_date: date, end_date: date, session: Session, user: CurrentUser):
    result = await ReportService(session, user).sales(start_date, end_date, ["transaction_date"], "month")
    return success(result["rows"], **result["meta"])


@router.get("/inventory/stock-position")
async def stock(session: Session, user: CurrentUser):
    result = await ReportService(session, user).stock()
    return success(result["rows"], **result["meta"])


@router.get("/data-quality/summary", dependencies=[Depends(require_roles(*DATA_ROLES))])
async def quality_summary(session: Session, user: CurrentUser):
    return success(await MonitoringService(session, user).quality_summary())
