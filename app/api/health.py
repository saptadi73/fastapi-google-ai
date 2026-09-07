from fastapi import Depends

from app.core.exceptions import success
from app.core.routing import APIRouter
from app.schemas.common import Envelope
from app.schemas.health import DatabaseHealthResponse, LivenessResponse, ReadinessResponse
from app.services.health_service import HealthService

router = APIRouter(prefix="/health", tags=["Health"], responses={503: {"model": Envelope}})


def get_health_service():
    return HealthService()


@router.get("", response_model=LivenessResponse, summary="Cek aplikasi aktif")
@router.get("/live", response_model=LivenessResponse, summary="Cek liveness aplikasi")
async def live(service: HealthService = Depends(get_health_service)):
    return success(service.live())


@router.get("/database", response_model=DatabaseHealthResponse, summary="Cek koneksi PostgreSQL")
async def database(service: HealthService = Depends(get_health_service)):
    return success(await service.database())


@router.get("/ready", response_model=ReadinessResponse, summary="Cek database, migrasi, dan Redis")
async def ready(service: HealthService = Depends(get_health_service)):
    return success(await service.ready())
