"""Explicit, tenant-scoped reviewers for decisions belonging to a source."""

from sqlalchemy import select

from app.core.exceptions import AppError
from app.domain.enums import REVIEW_ROLES
from app.models.auth import User
from app.models.source import DataSource
from app.repositories.base import TenantRepository
from app.services.audit_service import audit

WORKFLOWS = ("metadata_review", "configuration", "import_review")


async def require_source_approver(session, actor, source_id, workflow):
    if actor.role not in REVIEW_ROLES:
        raise AppError("FORBIDDEN", "Peran reviewer diperlukan untuk keputusan ini.", 403)
    repo = TenantRepository(session, actor.tenant_id)
    source = await repo.get(DataSource, source_id)
    if source.approval_assignees is None and workflow == "metadata_review" and actor.role != "PLATFORM_ADMIN":
        raise AppError("FORBIDDEN", "Review metadata sumber lama memerlukan admin hingga approver ditunjuk.", 403)
    if source.approval_assignees is not None and actor.id not in source.approval_assignees.get(workflow, []):
        raise AppError("SOURCE_APPROVER_NOT_ASSIGNED", "Anda tidak ditunjuk sebagai approver sumber untuk keputusan ini.", 403)
    return source


class SourceApproverService:
    def __init__(self, session, actor):
        self.session, self.actor = session, actor
        self.repo = TenantRepository(session, actor.tenant_id)

    async def options(self):
        users = (await self.session.scalars(
            select(User).where(
                User.tenant_id == self.actor.tenant_id,
                User.is_active.is_(True),
                User.role.in_(list(REVIEW_ROLES)),
            ).order_by(User.username).limit(500)
        )).all()
        return [{"id": item.id, "username": item.username, "role": item.role} for item in users]

    async def get(self, source_id):
        source = await self.repo.get(DataSource, source_id)
        return {
            "source_id": source.id,
            "revision": source.approval_revision,
            "configured": source.approval_assignees is not None,
            "approvers": source.approval_assignees or {key: [] for key in WORKFLOWS},
        }

    async def replace(self, source_id, data):
        source = await self.repo.get(DataSource, source_id, lock=True)
        if source.approval_revision != data.revision:
            raise AppError("SOURCE_APPROVERS_STALE", "Daftar approver berubah; muat ulang.", 409)
        ids = {str(item) for key in WORKFLOWS for item in getattr(data, key)}
        if ids:
            users = (await self.session.scalars(
                select(User).where(User.tenant_id == self.actor.tenant_id, User.id.in_(ids))
            )).all()
            valid = {item.id for item in users if item.is_active and item.role in REVIEW_ROLES}
            if valid != ids:
                raise AppError("SOURCE_APPROVER_INVALID", "Pilih hanya reviewer aktif dari tenant ini.", 422)
        source.approval_assignees = {
            key: [str(item) for item in getattr(data, key)] for key in WORKFLOWS
        }
        source.approval_revision += 1
        audit(self.session, self.actor, "source.approvers_replaced", source.id,
              revision=source.approval_revision, approver_counts={
                  key: len(source.approval_assignees[key]) for key in WORKFLOWS
              })
        return await self.get(source.id)
