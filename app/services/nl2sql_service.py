from datetime import datetime, timezone

from app.core.exceptions import AppError
from app.models.semantic import QueryRequest, SavedQuery
from app.repositories.semantic_repository import SemanticRepository
from app.schemas.nl2sql import AIQueryPlan
from app.schemas.semantic import QueryPlan
from app.services.openai_service import OpenAIService
from app.services.profiling_service import canonical_json, digest
from app.services.query_execution_service import QueryExecutionService
from app.services.semantic_catalog_service import SemanticCatalogService, normalize_intent


class NL2SQLService:
    def __init__(self, session, user):
        self.session, self.user = session, user
        self.repo = SemanticRepository(session, user.tenant_id)
        self.executor = QueryExecutionService(session, user)

    async def query(self, request):
        catalog = SemanticCatalogService(self.session, self.user)
        selected = None
        if request.saved_query_code:
            selected = await catalog.saved(request.saved_query_code)
            route = "SAVED_QUERY"
        else:
            templates = await self.repo.list(
                SavedQuery, limit=1000, conditions=(SavedQuery.status == "ACTIVE",)
            )
            matched = [
                t
                for t in templates
                if self.user.role in t.allowed_roles
                and normalize_intent(request.question) in t.examples
                and (not request.data_product_code or t.data_product_code == request.data_product_code)
            ]
            if len(matched) == 1:
                selected = await catalog.saved(matched[0].code)
                route = "INTENT_TEMPLATE"
        if selected:
            plan, code = QueryPlan.model_validate(selected.plan), selected.data_product_code
        else:
            products = await catalog.products()
            if request.data_product_code:
                products = [p for p in products if p["code"] == request.data_product_code]
            if not products:
                raise AppError("DATA_PRODUCT_NOT_FOUND", "Belum ada data product yang dapat Anda akses.", 404)
            if len(products) > 10:
                return await self.clarification(
                    request, "Sebutkan data_product_code agar pertanyaan lebih spesifik."
                )
            context = canonical_json(
                {
                    "today": datetime.now(timezone.utc).date().isoformat(),
                    "question": request.question,
                    "catalog": [
                        {
                            "code": p["code"],
                            "name": p["name"],
                            "metrics": p["metrics"],
                            "dimensions": p["dimensions"],
                            "columns": p["columns"],
                        }
                        for p in products
                    ],
                }
            )
            candidate, _ = await OpenAIService().generate(self.user, "NL2SQL", context, AIQueryPlan)
            if candidate.clarification_required:
                return await self.clarification(
                    request, candidate.clarification_question or "Mohon perjelas pertanyaan."
                )
            if candidate.plan is None or candidate.data_product_code not in {p["code"] for p in products}:
                raise AppError("NL2SQL_UNSAFE_QUERY", "Rencana AI merujuk data product di luar konteks.")
            plan, code, route = candidate.plan, candidate.data_product_code, "OPENAI"
        result = await self.executor.execute(code, plan, ai=route == "OPENAI", query_source=route)
        log = await self.repo.add(
            QueryRequest,
            user_id=self.user.id,
            question_hash=digest(request.question),
            route=route,
            plan={"data_product_code": code, "plan": plan.model_dump(mode="json")},
        )
        result["meta"].update(query_id=log.id, route=route, openai_called=route == "OPENAI")
        return result

    async def clarification(self, request, question):
        log = await self.repo.add(
            QueryRequest,
            user_id=self.user.id,
            question_hash=digest(request.question),
            route="CLARIFICATION",
            status="CLARIFICATION_REQUIRED",
            clarification_question=question,
        )
        return {
            "rows": [],
            "meta": {"query_id": log.id, "clarification_required": True, "question": question},
        }
