from app.api.v1 import (
    admin_ai_usage,
    auth,
    configurations,
    data_quality,
    etl_runs,
    import_reviews,
    masters,
    nl2sql,
    operational_queries,
    profiling,
    reports,
    semantic_catalog,
    sources,
    taxonomies,
)
from app.core.routing import APIRouter
from app.schemas.common import Envelope

router = APIRouter(
    responses={
        401: {"model": Envelope},
        403: {"model": Envelope},
        404: {"model": Envelope},
        409: {"model": Envelope},
        422: {"model": Envelope},
        503: {"model": Envelope},
    }
)
for child in (
    auth.router,
    auth.users_router,
    sources.router,
    masters.router,
    taxonomies.router,
    import_reviews.router,
    profiling.router,
    configurations.router,
    etl_runs.router,
    data_quality.router,
    semantic_catalog.router,
    operational_queries.router,
    reports.router,
    nl2sql.router,
    admin_ai_usage.router,
):
    router.include_router(child)
