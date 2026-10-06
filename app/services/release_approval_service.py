"""Independent IT and affected-unit signoffs before a configuration goes live."""

from sqlalchemy import or_, select

from app.core.exceptions import AppError
from app.models.access import AccessAttribute, UserAssignment
from app.models.auth import User
from app.models.base import now
from app.models.configuration import Configuration
from app.models.source import DataSource
from app.repositories.base import TenantRepository
from app.services.audit_service import audit

TECHNICAL_ROLES = {"PLATFORM_ADMIN", "TECHNICAL_APPROVER"}


def _group_key(group_type, unit_id=None):
    return "TECHNICAL" if group_type == "TECHNICAL" else f"UNIT:{unit_id}"


async def _active_unit_memberships(session, tenant_id, user_ids):
    if not user_ids:
        return set()
    instant = now()
    rows = (await session.execute(
        select(UserAssignment.user_id, UserAssignment.attribute_id).where(
            UserAssignment.tenant_id == tenant_id,
            UserAssignment.user_id.in_(user_ids),
            UserAssignment.status == "ACTIVE",
            UserAssignment.valid_from <= instant,
            (UserAssignment.valid_to.is_(None) | (UserAssignment.valid_to > instant)),
        )
    )).all()
    return {(user_id, unit_id) for user_id, unit_id in rows}


def release_status(config, source):
    policy = source.release_policy
    if policy is None:
        return {"configured": False, "ready": True, "policy_revision": source.release_policy_revision,
                "configuration_revision": config.revision_no, "groups": []}
    decisions = config.release_decisions or {}
    groups = [("TECHNICAL", "Pemeriksaan IT", policy["technical_approver_ids"], None)]
    groups.extend((
        _group_key("UNIT", group["unit_id"]), group.get("label", group["unit_id"]),
        group["approver_ids"], group["unit_id"]
    ) for group in policy["unit_groups"])
    result = []
    for key, label, approver_ids, unit_id in groups:
        item = decisions.get(key, {})
        current = (
            item.get("policy_revision") == source.release_policy_revision
            and item.get("configuration_revision") == config.revision_no
            and item.get("snapshot_hash") == (config.review_state or {}).get("snapshot_hash")
        )
        result.append({
            "key": key, "label": label, "unit_id": unit_id, "approver_ids": approver_ids,
            "status": item.get("decision", "PENDING") if current else "PENDING",
            "decided_by": item.get("actor_id") if current else None,
            "decided_at": item.get("decided_at") if current else None,
            "comment": item.get("comment") if current else None,
        })
    return {
        "configured": True,
        "ready": bool(result) and all(group["status"] == "APPROVED" for group in result),
        "policy_revision": source.release_policy_revision,
        "configuration_revision": config.revision_no,
        "groups": result,
    }


def require_release_ready(config, source):
    status = release_status(config, source)
    if not status["ready"]:
        raise AppError("RELEASE_APPROVAL_REQUIRED",
                       "Persetujuan IT dan seluruh unit terkait belum lengkap untuk revisi ini.", 409)
    return status


def _release_summary(config):
    definition = config.configuration_json or {}
    semantic = definition.get("semantic") or {}
    return {
        "name": definition.get("dataset_business_name") or semantic.get("name") or "Konfigurasi data",
        "description": definition.get("dataset_description") or "",
        "product_code": semantic.get("code") or "",
        "columns": [{"name": item.get("target_column"), "type": item.get("target_type")}
                    for item in definition.get("columns", []) if isinstance(item, dict)],
        "metrics": [item.get("name") or item.get("code") for item in semantic.get("metrics", [])
                    if isinstance(item, dict)],
    }


class ReleaseApprovalService:
    def __init__(self, session, actor):
        self.session, self.actor = session, actor
        self.repo = TenantRepository(session, actor.tenant_id)

    async def candidates(self):
        users = (await self.session.scalars(
            self.repo.query(User).where(User.is_active.is_(True)).order_by(User.username).limit(500)
        )).all()
        memberships = await _active_unit_memberships(self.session, self.actor.tenant_id,
                                                       [item.id for item in users])
        return [{"id": item.id, "username": item.username, "role": item.role,
                 "unit_ids": sorted(unit for user_id, unit in memberships if user_id == item.id)}
                for item in users]

    async def _actor_status(self, config, source):
        status = release_status(config, source)
        memberships = await _active_unit_memberships(self.session, self.actor.tenant_id, [self.actor.id])
        approved_elsewhere = {group["key"] for group in status["groups"]
                              if group["status"] == "APPROVED" and group["decided_by"] == self.actor.id}
        for group in status["groups"]:
            group["can_view"] = (
                self.actor.id in group["approver_ids"]
                and (group["key"] == "TECHNICAL" and self.actor.role in TECHNICAL_ROLES
                     or group["unit_id"] is not None
                     and (self.actor.id, group["unit_id"]) in memberships)
            )
            group["can_decide"] = (
                group["can_view"] and config.status in {"APPROVED", "SUPERSEDED"}
                and config.created_by != self.actor.id and group["status"] != "REJECTED"
                and not any(key != group["key"] for key in approved_elsewhere)
            )
        return status

    async def inbox(self, offset=0, limit=50):
        actor_id = self.actor.id
        memberships = await _active_unit_memberships(self.session, self.actor.tenant_id, [actor_id])
        eligible_sources = [DataSource.release_policy.contains(
            {"unit_groups": [{"unit_id": unit_id, "approver_ids": [actor_id]}]}
        ) for _, unit_id in memberships]
        if self.actor.role in TECHNICAL_ROLES:
            eligible_sources.append(DataSource.release_policy.contains(
                {"technical_approver_ids": [actor_id]}
            ))
        if not eligible_sources:
            return []
        rows = (await self.session.execute(
            select(Configuration, DataSource).join(
                DataSource, (Configuration.source_id == DataSource.id)
                & (Configuration.tenant_id == DataSource.tenant_id)
            ).where(
                Configuration.tenant_id == self.actor.tenant_id,
                Configuration.status.in_(["APPROVED", "SUPERSEDED"]),
                DataSource.release_policy.is_not(None),
                or_(*eligible_sources),
            ).order_by(Configuration.created_at.desc()).offset(offset).limit(limit)
        )).all()
        result = []
        for config, source in rows:
            status = await self._actor_status(config, source)
            result.append({"configuration_id": config.id, "source_id": source.id,
                           "source_name": source.name, "version_no": config.version_no,
                           "status": config.status, "summary": _release_summary(config), **status})
        return result

    async def policy(self, source_id):
        source = await self.repo.get(DataSource, source_id)
        return {"source_id": source.id, "revision": source.release_policy_revision,
                "configured": source.release_policy is not None,
                "policy": source.release_policy or {"technical_approver_ids": [], "unit_groups": []}}

    async def replace_policy(self, source_id, data):
        source = await self.repo.get(DataSource, source_id, lock=True)
        if data.revision != source.release_policy_revision:
            raise AppError("RELEASE_POLICY_STALE", "Aturan persetujuan berubah; muat ulang.", 409)
        technical_ids = {str(value) for value in data.technical_approver_ids}
        business_list = [str(value) for group in data.unit_groups for value in group.approver_ids]
        business_ids = set(business_list)
        if len(business_list) != len(business_ids):
            raise AppError("RELEASE_APPROVER_CONFLICT",
                           "Satu akun hanya boleh menjadi approver untuk satu unit pada rilis yang sama.", 422)
        if technical_ids & business_ids:
            raise AppError("RELEASE_APPROVER_CONFLICT", "Pemeriksa IT harus berbeda dari approver unit.", 422)
        users = (await self.session.scalars(
            self.repo.query(User).where(User.id.in_(technical_ids | business_ids))
        )).all()
        valid_users = {item.id: item for item in users if item.is_active}
        if set(valid_users) != technical_ids | business_ids or any(
            valid_users[user_id].role not in TECHNICAL_ROLES for user_id in technical_ids
        ):
            raise AppError("RELEASE_APPROVER_INVALID", "Pilih pengguna aktif dan reviewer IT yang sah.", 422)
        units = (await self.session.scalars(
            self.repo.query(AccessAttribute).where(AccessAttribute.id.in_(
                [str(group.unit_id) for group in data.unit_groups]
            ))
        )).all()
        unit_map = {unit.id: unit for unit in units if unit.kind == "DEPARTMENT" and unit.is_active}
        if len(unit_map) != len(data.unit_groups):
            raise AppError("RELEASE_UNIT_INVALID", "Pilih unit aktif dari tenant ini.", 422)
        memberships = await _active_unit_memberships(self.session, self.actor.tenant_id, business_ids)
        if any((str(user_id), str(group.unit_id)) not in memberships
               for group in data.unit_groups for user_id in group.approver_ids):
            raise AppError("RELEASE_UNIT_APPROVER_INVALID",
                           "Approver unit harus memiliki assignment aktif pada unit tersebut.", 422)
        source.release_policy = {
            "technical_approver_ids": [str(value) for value in data.technical_approver_ids],
            "unit_groups": [{"unit_id": str(group.unit_id), "label": unit_map[str(group.unit_id)].label,
                             "approver_ids": [str(value) for value in group.approver_ids]}
                            for group in data.unit_groups],
        }
        source.release_policy_revision += 1
        audit(self.session, self.actor, "source.release_policy_updated", source.id,
              revision=source.release_policy_revision, unit_count=len(data.unit_groups))
        return await self.policy(source.id)

    async def status(self, config_id):
        config = await self.repo.get(Configuration, config_id)
        source = await self.repo.get(DataSource, config.source_id)
        status = await self._actor_status(config, source)
        if (self.actor.role not in {"PLATFORM_ADMIN", "TECHNICAL_APPROVER", "SOURCE_OWNER", "DATA_STEWARD"}
                and not any(group["can_view"] for group in status["groups"])):
            raise AppError("RESOURCE_NOT_FOUND", "Konfigurasi tidak tersedia untuk akun ini.", 404)
        return {"configuration_id": config.id, "status": config.status,
                "summary": _release_summary(config), **status}

    async def decide(self, config_id, data):
        config = await self.repo.get(Configuration, config_id, lock=True)
        source = await self.repo.get(DataSource, config.source_id, lock=True)
        if source.release_policy is None:
            raise AppError("RELEASE_POLICY_REQUIRED", "Aturan persetujuan siap tayang belum diatur.", 409)
        if config.status not in {"APPROVED", "SUPERSEDED"} or config.revision_no != data.revision_no:
            raise AppError("RELEASE_CONFIGURATION_STALE", "Konfigurasi belum approved atau revisi berubah.", 409)
        if config.created_by == self.actor.id:
            raise AppError("SEPARATE_APPROVER_REQUIRED", "Pembuat konfigurasi tidak boleh menyetujui rilisnya.", 403)
        key = _group_key(data.group_type, str(data.unit_id) if data.unit_id else None)
        policy = source.release_policy
        if data.group_type == "TECHNICAL":
            eligible = policy["technical_approver_ids"]
            if self.actor.role not in TECHNICAL_ROLES:
                raise AppError("FORBIDDEN", "Role pemeriksa teknis diperlukan.", 403)
        else:
            group = next((item for item in policy["unit_groups"]
                          if item["unit_id"] == str(data.unit_id)), None)
            if group is None:
                raise AppError("RELEASE_GROUP_NOT_FOUND", "Unit ini tidak terkait persetujuan rilis.", 404)
            eligible = group["approver_ids"]
            memberships = await _active_unit_memberships(self.session, self.actor.tenant_id, [self.actor.id])
            if (self.actor.id, str(data.unit_id)) not in memberships:
                raise AppError("RELEASE_UNIT_MEMBERSHIP_REQUIRED", "Assignment unit aktif diperlukan.", 403)
        if self.actor.id not in eligible:
            raise AppError("RELEASE_APPROVER_NOT_ASSIGNED", "Anda tidak ditunjuk untuk kelompok ini.", 403)
        current = release_status(config, source)
        current_group = next(group for group in current["groups"] if group["key"] == key)
        if current_group["status"] == "REJECTED":
            raise AppError("RELEASE_REJECTED", "Rilis ditolak; buat revisi konfigurasi baru.", 409)
        if current_group["status"] == "APPROVED" and data.decision == "APPROVE":
            raise AppError("RELEASE_ALREADY_APPROVED", "Kelompok ini sudah menyetujui revisi ini.", 409)
        if any(group["decided_by"] == self.actor.id and group["key"] != key
               and group["status"] == "APPROVED" for group in current["groups"]):
            raise AppError("RELEASE_SEPARATION_REQUIRED", "Pemeriksa IT dan unit harus berbeda.", 403)
        config.release_decisions = {
            **(config.release_decisions or {}),
            key: {"decision": "APPROVED" if data.decision == "APPROVE" else "REJECTED",
                  "actor_id": self.actor.id, "decided_at": now().isoformat(),
                  "comment": data.comment, "policy_revision": source.release_policy_revision,
                  "configuration_revision": config.revision_no,
                  "snapshot_hash": (config.review_state or {}).get("snapshot_hash"),
                  "technical_checks": data.technical_checks.model_dump() if data.technical_checks else None},
        }
        audit(self.session, self.actor, "configuration.release_decision", config.id,
              group=key, decision=data.decision, revision=config.revision_no)
        return {"configuration_id": config.id, "status": config.status,
                "summary": _release_summary(config), **await self._actor_status(config, source)}
