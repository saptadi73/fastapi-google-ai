from datetime import datetime, timezone

from sqlalchemy import func, or_, select

from app.core.exceptions import AppError
from app.models.semantic import QueryRequest, SavedNL2SQLQuery
from app.repositories.base import TenantRepository
from app.schemas.nl2sql import SavedNL2SQLQueryCreate, SavedNL2SQLQueryUpdate
from app.schemas.semantic import QueryPlan
from app.services.audit_service import audit
from app.services.profiling_service import digest
from app.services.query_execution_service import QueryExecutionService


class SavedNL2SQLService:
    def __init__(self, session, user):
        self.session, self.user = session, user
        self.repo = TenantRepository(session, user.tenant_id)
        self.executor = QueryExecutionService(session, user)

    def owner_query(self):
        return self.repo.query(SavedNL2SQLQuery).where(SavedNL2SQLQuery.user_id == self.user.id)

    @staticmethod
    def payload(item):
        return {
            "id": item.id,
            "created_at": item.created_at,
            "user_id": item.user_id,
            "source_request_id": item.source_request_id,
            "name": item.name,
            "description": item.description,
            "question": item.question,
            "data_product_code": item.data_product_code,
            "plan": item.plan,
            "sql_preview": item.sql_preview,
            "run_count": item.run_count,
            "last_run_at": item.last_run_at,
        }

    async def list(self, *, search="", offset=0, limit=20):
        query = self.owner_query()
        term = search.strip()
        if term:
            pattern = f"%{term}%"
            query = query.where(
                or_(
                    SavedNL2SQLQuery.name.ilike(pattern),
                    SavedNL2SQLQuery.description.ilike(pattern),
                    SavedNL2SQLQuery.question.ilike(pattern),
                    SavedNL2SQLQuery.data_product_code.ilike(pattern),
                )
            )
        total = await self.session.scalar(select(func.count()).select_from(query.subquery()))
        items = list(
            (
                await self.session.scalars(
                    query.order_by(SavedNL2SQLQuery.created_at.desc(), SavedNL2SQLQuery.id)
                    .offset(offset)
                    .limit(limit)
                )
            ).all()
        )
        return {
            "items": [self.payload(item) for item in items],
            "total": total or 0,
            "offset": offset,
            "limit": limit,
        }

    async def owned(self, query_id, *, lock=False):
        query = self.owner_query().where(SavedNL2SQLQuery.id == str(query_id))
        if lock:
            query = query.with_for_update()
        item = await self.session.scalar(query)
        if item is None:
            raise AppError("RESOURCE_NOT_FOUND", "Perintah tersimpan tidak ditemukan.", 404)
        return item

    async def create_from_request(self, request_id, data: SavedNL2SQLQueryCreate):
        if not data.name.strip():
            raise AppError("SAVED_COMMAND_NAME_REQUIRED", "Nama perintah wajib diisi.", 422)
        log = await self.repo.get(QueryRequest, request_id)
        if log.user_id != self.user.id:
            raise AppError("RESOURCE_NOT_FOUND", "Query request tidak ditemukan.", 404)
        if log.status != "SUCCEEDED":
            raise AppError("QUERY_NOT_SAVEABLE", "Hanya hasil NL2SQL yang berhasil dapat disimpan.", 409)
        if digest(data.question) != log.question_hash:
            raise AppError("QUERY_REQUEST_MISMATCH", "Pertanyaan tidak sesuai dengan request NL2SQL.", 409)
        existing = await self.session.scalar(
            self.owner_query().where(SavedNL2SQLQuery.source_request_id == log.id)
        )
        if existing:
            return self.payload(existing)

        code = log.plan.get("data_product_code") if isinstance(log.plan, dict) else None
        raw_plan = log.plan.get("plan") if isinstance(log.plan, dict) else None
        if not code or not isinstance(raw_plan, dict):
            raise AppError("QUERY_NOT_SAVEABLE", "Plan query berhasil tidak tersedia.", 409)
        plan = QueryPlan.model_validate(raw_plan)
        sql_preview = await self.executor.preview_sql(code, plan)
        item = await self.repo.add(
            SavedNL2SQLQuery,
            user_id=self.user.id,
            source_request_id=log.id,
            name=data.name.strip(),
            description=data.description.strip(),
            question=data.question.strip(),
            data_product_code=code,
            plan=plan.model_dump(mode="json"),
            sql_preview=sql_preview,
        )
        audit(
            self.session,
            self.user,
            "nl2sql.command.saved",
            item.id,
            data_product_code=code,
            source_request_id=log.id,
        )
        return self.payload(item)

    async def update(self, query_id, data: SavedNL2SQLQueryUpdate):
        item = await self.owned(query_id, lock=True)
        changes = data.model_dump(exclude_unset=True)
        if "name" in changes:
            changes["name"] = changes["name"].strip()
            if not changes["name"]:
                raise AppError("SAVED_COMMAND_NAME_REQUIRED", "Nama perintah wajib diisi.", 422)
        if "description" in changes:
            changes["description"] = changes["description"].strip()
        for key, value in changes.items():
            setattr(item, key, value)
        audit(self.session, self.user, "nl2sql.command.updated", item.id, changed_fields=sorted(changes))
        return self.payload(item)

    async def delete(self, query_id):
        item = await self.owned(query_id, lock=True)
        item_id = item.id
        await self.session.delete(item)
        audit(
            self.session,
            self.user,
            "nl2sql.command.deleted",
            item_id,
            data_product_code=item.data_product_code,
        )
        return {"deleted": True, "id": item_id}

    async def run(self, query_id):
        item = await self.owned(query_id, lock=True)
        result = await self.executor.execute(
            item.data_product_code,
            QueryPlan.model_validate(item.plan),
            ai=False,
            query_source="SAVED_COMMAND",
            use_nl2sql_reader=True,
        )
        item.run_count += 1
        item.last_run_at = datetime.now(timezone.utc)
        item.sql_preview = result["meta"].get("sql_preview", item.sql_preview)
        audit(
            self.session,
            self.user,
            "nl2sql.command.executed",
            item.id,
            data_product_code=item.data_product_code,
            run_count=item.run_count,
            row_count=result["meta"].get("row_count", 0),
            cached=result["meta"].get("cached", False),
        )
        result["meta"].update(
            saved_command_id=item.id,
            saved_command_name=item.name,
            openai_called=False,
        )
        return result
