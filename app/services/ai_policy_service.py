from datetime import datetime, timezone

from sqlalchemy import desc, select

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.models.ai_policy import AITaskPolicy, AITaskPolicyVersion
from app.models.source import DataSource
from app.models.taxonomy import Taxonomy
from app.repositories.base import TenantRepository, record
from app.repositories.semantic_repository import SemanticRepository
from app.schemas.ai_policy import PURPOSE_PROMPTS
from app.services.audit_service import audit


class AITaskPolicyService:
    def __init__(self, session, user):
        self.session, self.user = session, user
        self.repo = TenantRepository(session, user.tenant_id)
        self.semantic_repo = SemanticRepository(session, user.tenant_id)

    def allowed_models(self):
        settings = get_settings()
        return (set(settings.openai_allowed_models) | {
            settings.openai_model_etl_config,
            settings.openai_model_nl2sql,
            settings.openai_model_help,
        }) - {""}

    async def validate_model_assignment(self, data):
        server_models = self.allowed_models()
        if (
            data.model not in server_models
            or not set(data.allowed_models).issubset(server_models)
            or (data.fallback_model and data.fallback_model not in server_models)
        ):
            raise AppError(
                "AI_MODEL_NOT_ALLOWLISTED",
                "Model policy harus seluruhnya termasuk allowlist server.",
                422,
            )
        if data.data_product_code:
            await self.semantic_repo.product(data.data_product_code, self.user)
        if data.data_source_id:
            await self.repo.get(DataSource, data.data_source_id)
        if data.taxonomy_id:
            taxonomy = await self.repo.get(Taxonomy, data.taxonomy_id)
            if not taxonomy.is_active or taxonomy.status != "APPROVED":
                raise AppError("TAXONOMY_NOT_APPROVED", "Scope AI harus memakai taxonomy approved aktif.", 409)
        return data

    @staticmethod
    def snapshot(obj):
        return {
            "code": obj.code,
            "purpose": obj.purpose,
            "prompt_version": obj.prompt_version,
            "model": obj.model,
            "allowed_models": list(obj.allowed_models),
            "data_product_code": obj.data_product_code,
            "data_source_id": obj.data_source_id,
            "taxonomy_id": obj.taxonomy_id,
            "max_context_chars": obj.max_context_chars,
            "daily_budget_usd": obj.daily_budget_usd,
            "fallback_model": obj.fallback_model,
            "revision_no": obj.revision_no,
            "status": obj.status,
            "approved_by": obj.approved_by,
            "approved_at": obj.approved_at.isoformat() if obj.approved_at else None,
        }

    async def record_version(self, obj, action):
        await self.repo.add(
            AITaskPolicyVersion,
            policy_id=obj.id,
            revision_no=obj.revision_no,
            action=action,
            snapshot_json=self.snapshot(obj),
            actor_user_id=self.user.id,
        )

    async def create(self, data):
        await self.validate_model_assignment(data)
        obj = await self.repo.add(
            AITaskPolicy, **data.model_dump(mode="json"), created_by=self.user.id
        )
        await self.record_version(obj, "CREATED")
        audit(self.session, self.user, "ai_task_policy.created", obj.id, purpose=data.purpose)
        return record(obj)

    async def list(self):
        return [record(item) for item in await self.repo.list(AITaskPolicy, limit=1000)]

    async def versions(self, policy_id, offset=0, limit=50):
        await self.repo.get(AITaskPolicy, policy_id)
        rows = await self.session.scalars(
            select(AITaskPolicyVersion)
            .where(
                AITaskPolicyVersion.tenant_id == self.user.tenant_id,
                AITaskPolicyVersion.policy_id == str(policy_id),
            )
            .order_by(desc(AITaskPolicyVersion.revision_no))
            .offset(offset)
            .limit(limit)
        )
        return [record(item) for item in rows.all()]

    async def update(self, policy_id, data):
        obj = await self.repo.get(AITaskPolicy, policy_id, lock=True)
        if obj.revision_no != data.revision_no or obj.status != "DRAFT":
            raise AppError("AI_TASK_POLICY_REVISION_CONFLICT", "Policy berubah atau bukan draft.", 409)
        await self.validate_model_assignment(data)
        changes = data.model_dump(mode="json", exclude={"revision_no"})
        for field, value in changes.items():
            setattr(obj, field, value)
        obj.revision_no += 1
        obj.approved_by = None
        obj.approved_at = None
        await self.record_version(obj, "UPDATED")
        audit(
            self.session,
            self.user,
            "ai_task_policy.updated",
            obj.id,
            revision_no=obj.revision_no,
            changed_fields=sorted(changes),
        )
        return record(obj)

    async def approve(self, policy_id, data):
        obj = await self.repo.get(AITaskPolicy, policy_id, lock=True)
        if obj.revision_no != data.revision_no or obj.status != "DRAFT":
            raise AppError("AI_TASK_POLICY_REVISION_CONFLICT", "Policy berubah atau bukan draft.", 409)
        server_models = self.allowed_models()
        fallback_model = getattr(obj, "fallback_model", None)
        if (
            obj.model not in server_models
            or (fallback_model and fallback_model == obj.model)
            or (fallback_model and fallback_model not in server_models)
        ):
            raise AppError("AI_MODEL_NOT_ALLOWLISTED", "Model tidak lagi ada dalam allowlist server.", 422)
        allowed_models = getattr(obj, "allowed_models", [])
        if (
            obj.model not in allowed_models
            or not set(allowed_models).issubset(server_models)
            or (fallback_model and fallback_model not in allowed_models)
            or obj.prompt_version != PURPOSE_PROMPTS.get(obj.purpose)
        ):
            raise AppError("AI_TASK_POLICY_INVALID", "Assignment policy AI tersimpan tidak valid.", 422)
        obj.status, obj.approved_by, obj.approved_at = "APPROVED", self.user.id, datetime.now(timezone.utc)
        obj.revision_no += 1
        await self.record_version(obj, "APPROVED")
        audit(self.session, self.user, "ai_task_policy.approved", obj.id, revision_no=obj.revision_no)
        return record(obj)

    async def reject(self, policy_id, data):
        obj = await self.repo.get(AITaskPolicy, policy_id, lock=True)
        if obj.revision_no != data.revision_no or obj.status != "DRAFT":
            raise AppError("AI_TASK_POLICY_REVISION_CONFLICT", "Policy berubah atau bukan draft.", 409)
        obj.status, obj.revision_no = "REJECTED", obj.revision_no + 1
        await self.record_version(obj, "REJECTED")
        audit(self.session, self.user, "ai_task_policy.rejected", obj.id, revision_no=obj.revision_no)
        return record(obj)
