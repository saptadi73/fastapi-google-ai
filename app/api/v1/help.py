from fastapi import Query

from app.api.dependencies import CurrentUser
from app.core.exceptions import success
from app.core.routing import APIRouter
from app.schemas.help import HelpQuestion
from app.services.help_service import HelpService

router = APIRouter(prefix="/help", tags=["AI Help"])


@router.get("/articles")
async def articles(
    user: CurrentUser,
    route: str | None = Query(default=None, max_length=300, pattern=r"^/[^\s]*$"),
    query: str | None = Query(default=None, min_length=2, max_length=200),
):
    return success(HelpService(user).list_articles(route, query))


@router.post("/ask")
async def ask(data: HelpQuestion, user: CurrentUser):
    result = await HelpService(user).ask(data)
    if isinstance(result, tuple):
        answer, meta = result
        return success(answer.model_dump(mode="json"), **meta)
    return success(result.model_dump(mode="json"), retrieval_only=True)

