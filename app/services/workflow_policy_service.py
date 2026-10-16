"""One tenant/unit boundary for the owner-managed operational workflow."""
from sqlalchemy import String, and_, cast, or_, select, true

from app.api.dependencies import CurrentUser
from app.core.config import get_settings
from app.core.exceptions import AppError
from app.domain.enums import EDIT_ROLES, REVIEW_ROLES
from app.models.access import AccessAttribute, AccessPolicy, AccessPolicyBinding, UserAssignment
from app.models.base import now
from app.models.source import DataSource
from app.repositories.base import TenantRepository


def workflow_policy():
    settings = get_settings()
    return {"owner_managed": settings.etl_owner_workflow_enabled,
            "unit_default_access": settings.unit_domain_default_access_enabled,
            "shared_unit_management": settings.etl_owner_workflow_enabled and settings.unit_domain_default_access_enabled,
            "separate_approver_required": not settings.etl_owner_workflow_enabled and settings.require_separate_approver}


async def workflow_reviewer(user: CurrentUser):
    roles = EDIT_ROLES if get_settings().etl_owner_workflow_enabled else REVIEW_ROLES
    if user.role not in roles:
        raise AppError("FORBIDDEN", "Peran tidak diizinkan memvalidasi perubahan ini.", 403)
    return user


async def workflow_catalog_editor(user: CurrentUser):
    roles = EDIT_ROLES if get_settings().etl_owner_workflow_enabled else ("PLATFORM_ADMIN", "DATA_STEWARD")
    if user.role not in roles:
        raise AppError("FORBIDDEN", "Peran tidak diizinkan mengelola katalog.", 403)
    return user


async def active_attributes(session, tenant_id, user_id):
    instant = now()
    return set((await session.scalars(select(UserAssignment.attribute_id).join(
        AccessAttribute, (AccessAttribute.id == UserAssignment.attribute_id)
        & (AccessAttribute.tenant_id == UserAssignment.tenant_id)
    ).where(UserAssignment.tenant_id == tenant_id, UserAssignment.user_id == user_id,
            UserAssignment.status == "ACTIVE", UserAssignment.valid_from <= instant,
            or_(UserAssignment.valid_to.is_(None), UserAssignment.valid_to > instant), AccessAttribute.is_active.is_(True)))).all())


def source_visibility_condition(actor):
    if not (get_settings().etl_owner_workflow_enabled and get_settings().unit_domain_default_access_enabled) or actor.role == "PLATFORM_ADMIN":
        return true()
    instant = now()
    units = select(cast(AccessAttribute.id, String)).join(UserAssignment,
        (UserAssignment.attribute_id == AccessAttribute.id) & (UserAssignment.tenant_id == AccessAttribute.tenant_id)
    ).where(AccessAttribute.tenant_id == actor.tenant_id, AccessAttribute.kind == "DEPARTMENT",
            AccessAttribute.is_active.is_(True), UserAssignment.user_id == actor.id,
            UserAssignment.status == "ACTIVE", UserAssignment.valid_from <= instant,
            or_(UserAssignment.valid_to.is_(None), UserAssignment.valid_to > instant))
    return or_(DataSource.access_metadata["owner_unit_id"].astext.in_(units),
               and_(DataSource.access_metadata.is_(None), DataSource.owner_user_id == actor.id))


async def require_source_reader(session, actor, source_id):
    source = await session.scalar(select(DataSource).where(DataSource.tenant_id == actor.tenant_id,
        DataSource.id == str(source_id), source_visibility_condition(actor)))
    if source is None:
        raise AppError("RESOURCE_NOT_FOUND", "Sumber tidak tersedia dalam unit Anda.", 404)
    if get_settings().etl_owner_workflow_enabled and actor.role != "PLATFORM_ADMIN":
        from app.schemas.access import AccessEvaluationRequest
        from app.services.access_service import AccessService

        decision = await AccessService(session, actor).evaluate(AccessEvaluationRequest(
            resource_type="SOURCE", resource_id=source.source_code, action="READ"))
        if decision["reason_code"] == "EXPLICIT_DENY":
            raise AppError("RESOURCE_NOT_FOUND", "Sumber tidak tersedia untuk akses Anda.", 404)
    return source


async def may_manage_source(session, actor, source):
    if str(actor.tenant_id) != str(source.tenant_id) or actor.role not in EDIT_ROLES or not actor.is_active:
        return False
    if actor.role == "PLATFORM_ADMIN":
        return True
    metadata = source.access_metadata or {}
    if not (get_settings().etl_owner_workflow_enabled and get_settings().unit_domain_default_access_enabled):
        return str(actor.id) in {str(source.owner_user_id), str(metadata.get("data_owner_user_id")),
                                 str(metadata.get("data_steward_user_id"))}
    unit = metadata.get("owner_unit_id")
    unit_attribute = await session.scalar(select(AccessAttribute).where(
        AccessAttribute.tenant_id == actor.tenant_id, AccessAttribute.id == str(unit),
        AccessAttribute.kind == "DEPARTMENT", AccessAttribute.is_active.is_(True)
    )) if unit else None
    if unit_attribute is None:
        return False
    attributes = await active_attributes(session, actor.tenant_id, actor.id)
    if not unit or str(unit) not in {str(v) for v in attributes}:
        return False
    instant = now()
    denies = (await session.scalars(select(AccessPolicy).join(
        AccessPolicyBinding, (AccessPolicyBinding.policy_id == AccessPolicy.id)
        & (AccessPolicyBinding.tenant_id == AccessPolicy.tenant_id)
    ).where(AccessPolicy.tenant_id == actor.tenant_id, AccessPolicy.status == "APPROVED",
            AccessPolicy.effect == "DENY", AccessPolicy.valid_from <= instant,
            or_(AccessPolicy.valid_to.is_(None), AccessPolicy.valid_to > instant),
            AccessPolicyBinding.resource_type == "SOURCE", AccessPolicyBinding.resource_id == source.source_code))).all()
    return not any(set(policy.actions) & {"EDIT", "OPERATE"}
                   and set(policy.required_attribute_ids).issubset(attributes) for policy in denies)


async def require_source_manager(session, actor, source_id):
    source = await TenantRepository(session, actor.tenant_id).get(DataSource, source_id)
    if not await may_manage_source(session, actor, source):
        raise AppError("SOURCE_UNIT_FORBIDDEN", "Pengelolaan sumber memerlukan role pengelola dan keanggotaan unit sumber yang aktif.", 403)
    return source


async def require_registry_manager(session, actor, created_by):
    if actor.role == "PLATFORM_ADMIN":
        return
    if actor.role not in EDIT_ROLES:
        raise AppError("FORBIDDEN", "Peran pengelola diperlukan.", 403)
    if str(actor.id) == str(created_by):
        return
    units = set((await session.scalars(select(AccessAttribute.id).where(
        AccessAttribute.tenant_id == actor.tenant_id, AccessAttribute.kind == "DEPARTMENT", AccessAttribute.is_active.is_(True)
    ))).all())
    own = await active_attributes(session, actor.tenant_id, actor.id)
    creator = await active_attributes(session, actor.tenant_id, created_by)
    if not units.intersection(own, creator):
        raise AppError("SOURCE_UNIT_FORBIDDEN", "Referensi bersama hanya dapat diubah pembuat, rekan satu unit, atau admin.", 403)
