from app.api.v1 import (
    access,
    admin_ai_usage,
    ai_policies,
    auth,
    configurations,
    data_quality,
    etl_runs,
    help,
    import_reviews,
    masters,
    nl2sql,
    operational_queries,
    operations,
    profiling,
    release_approvals,
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
    access.router,
    sources.router,
    masters.router,
    taxonomies.router,
    import_reviews.router,
    profiling.router,
    configurations.router,
    release_approvals.router,
    etl_runs.router,
    help.router,
    data_quality.router,
    semantic_catalog.router,
    operational_queries.router,
    reports.router,
    nl2sql.router,
    admin_ai_usage.router,
    ai_policies.router,
    operations.router,
):
    router.include_router(child)
