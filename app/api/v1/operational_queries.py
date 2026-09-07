import csv
import io

from fastapi.responses import Response

from app.api.dependencies import CurrentUser, Session
from app.core.exceptions import success
from app.core.routing import APIRouter
from app.repositories.base import record
from app.schemas.semantic import QueryPlan
from app.services.query_execution_service import QueryExecutionService
from app.services.semantic_catalog_service import SemanticCatalogService

router = APIRouter(tags=["Operational queries"])


@router.get("/data-products")
async def products(session: Session, user: CurrentUser):
    return success(await SemanticCatalogService(session, user).products())


@router.get("/data-products/{code}")
async def product(code: str, session: Session, user: CurrentUser):
    return success(
        record(await SemanticCatalogService(session, user).repo.product(code, user), exclude=("view_name",))
    )


@router.get("/data-products/{code}/dimensions")
async def dimensions(code: str, session: Session, user: CurrentUser):
    return success((await SemanticCatalogService(session, user).repo.product(code, user)).dimensions)


@router.get("/data-products/{code}/metrics")
async def metrics(code: str, session: Session, user: CurrentUser):
    return success((await SemanticCatalogService(session, user).repo.product(code, user)).metrics)


@router.post("/data-products/{code}/query")
async def query(code: str, data: QueryPlan, session: Session, user: CurrentUser):
    result = await QueryExecutionService(session, user).execute(code, data)
    return success(result["rows"], **result["meta"])


@router.post("/data-products/{code}/export", response_class=Response)
async def export(code: str, data: QueryPlan, session: Session, user: CurrentUser):
    result = await QueryExecutionService(session, user).execute(code, data)
    stream = io.StringIO(newline="")
    if result["rows"]:
        writer = csv.DictWriter(stream, fieldnames=list(result["rows"][0]))
        writer.writeheader()
        for row in result["rows"]:
            # CSV injection protection applies only to string values, preserving numeric negatives.
            writer.writerow(
                {
                    k: "'" + v
                    if isinstance(v, str) and v.lstrip().startswith(("=", "+", "-", "@", "\t", "\r"))
                    else v
                    for k, v in row.items()
                }
            )
    return Response(
        stream.getvalue().encode("utf-8-sig"),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="data-export.csv"'},
    )


@router.post("/saved-queries/{code}/run")
async def run_saved(code: str, session: Session, user: CurrentUser):
    saved = await SemanticCatalogService(session, user).saved(code)
    result = await QueryExecutionService(session, user).execute(
        saved.data_product_code, QueryPlan.model_validate(saved.plan), query_source="SAVED_QUERY"
    )
    return success(result["rows"], **result["meta"])
