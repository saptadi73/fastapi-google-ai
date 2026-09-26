from datetime import datetime, timezone

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.models.ai_policy import AITaskPolicy
from app.repositories.base import TenantRepository, record
from app.services.audit_service import audit


class AITaskPolicyService:
    def __init__(self, session, user):
        self.session, self.user = session, user
        self.repo = TenantRepository(session, user.tenant_id)

    def allowed_models(self):
        settings = get_settings()
        return (set(settings.openai_allowed_models) | {
            settings.openai_model_etl_config,
            settings.openai_model_nl2sql,
        }) - {""}

    async def validate_model_assignment(self, data):
        if data.model not in self.allowed_models():
            raise AppError("AI_MODEL_NOT_ALLOWLISTED", "Model tidak ada dalam allowlist server.", 422)
        return data

    async def create(self, data):
        await self.validate_model_assignment(data)
        obj = await self.repo.add(AITaskPolicy, **data.model_dump(), created_by=self.user.id)
        audit(self.session, self.user, "ai_task_policy.created", obj.id, purpose=data.purpose)
        return record(obj)

    async def list(self):
        return [record(item) for item in await self.repo.list(AITaskPolicy, limit=1000)]

    async def approve(self, policy_id, data):
        obj = await self.repo.get(AITaskPolicy, policy_id, lock=True)
        if obj.revision_no != data.revision_no or obj.status != "DRAFT":
            raise AppError("AI_TASK_POLICY_REVISION_CONFLICT", "Policy berubah atau bukan draft.", 409)
        if obj.model not in self.allowed_models():
            raise AppError("AI_MODEL_NOT_ALLOWLISTED", "Model tidak lagi ada dalam allowlist server.", 422)
        obj.status, obj.approved_by, obj.approved_at = "APPROVED", self.user.id, datetime.now(timezone.utc)
        obj.revision_no += 1
        audit(self.session, self.user, "ai_task_policy.approved", obj.id, revision_no=obj.revision_no)
        return record(obj)

    async def reject(self, policy_id, data):
        obj = await self.repo.get(AITaskPolicy, policy_id, lock=True)
        if obj.revision_no != data.revision_no or obj.status != "DRAFT":
            raise AppError("AI_TASK_POLICY_REVISION_CONFLICT", "Policy berubah atau bukan draft.", 409)
        obj.status, obj.revision_no = "REJECTED", obj.revision_no + 1
        audit(self.session, self.user, "ai_task_policy.rejected", obj.id, revision_no=obj.revision_no)
        return record(obj)
