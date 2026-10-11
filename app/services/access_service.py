from datetime import datetime

from sqlalchemy import func, or_, select

from app.core.exceptions import AppError
from app.models.access import (
    AccessAttribute,
    AccessPolicy,
    AccessPolicyBinding,
    AccessRequest,
    PermissionBundle,
    UserAssignment,
    UserPermissionGrant,
)
from app.models.auth import User
from app.models.base import now
from app.models.master import MasterDefinition
from app.models.semantic import DataProduct
from app.models.source import DataSource, SourceSheet
from app.models.taxonomy import Taxonomy
from app.repositories.base import TenantRepository, record
from app.schemas.access import AccessRequestDecision
from app.services.audit_service import audit
from app.services.notification_service import add_notification, resolve_notifications

ROLE_ACTIONS = {
    "PLATFORM_ADMIN": ["DISCOVER", "READ", "QUERY", "EXPORT", "EDIT", "APPROVE", "OPERATE", "ADMIN"],
    "SOURCE_OWNER": ["DISCOVER", "READ", "QUERY", "EDIT", "OPERATE"],
    "DATA_STEWARD": ["DISCOVER", "READ", "QUERY", "EDIT"],
    "TECHNICAL_APPROVER": ["DISCOVER", "READ", "QUERY", "APPROVE"],
    "ANALYST": ["DISCOVER", "READ", "QUERY", "EXPORT"],
    "VIEWER": ["DISCOVER", "READ", "QUERY"],
}

POLICY_RESOURCES = {
    "DATA_PRODUCT": (DataProduct, DataProduct.code),
    "SOURCE": (DataSource, DataSource.source_code),
    "MASTER": (MasterDefinition, MasterDefinition.code),
    "TAXONOMY": (Taxonomy, Taxonomy.code),
}


def attribute_record(item):
    return record(item)


def assignment_record(item, attribute=None):
    result = record(item)
    if attribute is not None:
        result["attribute"] = attribute_record(attribute)
    return result


def bundle_record(item):
    return record(item)


def grant_record(item, bundle=None):
    result = record(item)
    if bundle is not None:
        result["bundle"] = bundle_record(bundle)
    return result


def policy_record(item):
    return record(item)


def access_request_record(item, requester, subject, attribute=None, bundle=None):
    result = record(item)
    result["requester"] = {
        "id": requester.id,
        "username": requester.username,
        "full_name": requester.full_name,
    }
    result["subject_user"] = {
        "id": subject.id,
        "username": subject.username,
        "full_name": subject.full_name,
        "role": subject.role,
    }
    result["attribute"] = attribute_record(attribute) if attribute else None
    result["bundle"] = bundle_record(bundle) if bundle else None
    return result


class AccessService:
    def __init__(self, session, actor):
        self.session, self.actor = session, actor
        self.repo = TenantRepository(session, actor.tenant_id)

    async def _attribute(self, attribute_id, *, lock=False):
        return await self.repo.get(AccessAttribute, attribute_id, lock=lock)

    async def _user(self, user_id):
        return await self.repo.get(User, user_id)

    async def _bundle(self, bundle_id, *, lock=False):
        return await self.repo.get(PermissionBundle, bundle_id, lock=lock)

    async def _policy(self, policy_id, *, lock=False):
        return await self.repo.get(AccessPolicy, policy_id, lock=lock)

    async def _access_request(self, request_id, *, lock=False):
        return await self.repo.get(AccessRequest, request_id, lock=lock)

    async def _access_request_record(self, item):
        requester = await self._user(item.requester_id)
        subject = (
            requester if item.subject_user_id == requester.id else await self._user(item.subject_user_id)
        )
        attribute = await self._attribute(item.attribute_id) if item.attribute_id else None
        bundle = await self._bundle(item.bundle_id) if item.bundle_id else None
        return access_request_record(item, requester, subject, attribute, bundle)

    async def request_options(self):
        attributes = await self.repo.list(
            AccessAttribute,
            limit=500,
            conditions=[AccessAttribute.is_active.is_(True)],
        )
        bundles = await self.repo.list(
            PermissionBundle,
            limit=500,
            conditions=[PermissionBundle.is_active.is_(True)],
        )
        requestable_users = [self.actor]
        if self.actor.role == "PLATFORM_ADMIN":
            requestable_users = await self.repo.list(
                User,
                limit=500,
                conditions=[User.is_active.is_(True)],
            )
        return {
            "attributes": [attribute_record(item) for item in attributes],
            "permission_bundles": [bundle_record(item) for item in bundles],
            "requestable_users": [
                {
                    "id": item.id,
                    "username": item.username,
                    "full_name": item.full_name,
                    "role": item.role,
                }
                for item in requestable_users
            ],
            "max_duration_days": 366,
        }

    async def create_access_request(self, data):
        if not self.actor.is_active:
            raise AppError("USER_INACTIVE", "Pengguna nonaktif tidak dapat meminta akses.")
        subject_id = str(data.subject_user_id) if data.subject_user_id else self.actor.id
        if subject_id != self.actor.id and self.actor.role != "PLATFORM_ADMIN":
            raise AppError(
                "ACCESS_REQUEST_DELEGATION_FORBIDDEN", "Hanya admin yang dapat meminta untuk user lain.", 403
            )
        subject = await self._user(subject_id)
        if not subject.is_active:
            raise AppError("USER_INACTIVE", "Akses tidak dapat diminta untuk pengguna nonaktif.")
        attribute = None
        bundle = None
        target_condition = None
        if data.request_type == "ATTRIBUTE":
            attribute = await self._attribute(data.attribute_id)
            if not attribute.is_active:
                raise AppError("ACCESS_ATTRIBUTE_INACTIVE", "Atribut akses tidak aktif.")
            target_condition = AccessRequest.attribute_id == attribute.id
        else:
            bundle = await self._bundle(data.bundle_id)
            if not bundle.is_active:
                raise AppError("PERMISSION_BUNDLE_INACTIVE", "Permission bundle tidak aktif.")
            target_condition = AccessRequest.bundle_id == bundle.id
        duplicate = await self.session.scalar(
            self.repo.query(AccessRequest).where(
                AccessRequest.subject_user_id == subject.id,
                AccessRequest.status == "PENDING",
                target_condition,
            )
        )
        if duplicate:
            raise AppError("ACCESS_REQUEST_DUPLICATE", "Permintaan untuk akses tersebut masih menunggu.", 409)
        item = await self.repo.add(
            AccessRequest,
            requester_id=self.actor.id,
            subject_user_id=subject.id,
            request_type=data.request_type,
            attribute_id=attribute.id if attribute else None,
            bundle_id=bundle.id if bundle else None,
            valid_from=data.valid_from,
            valid_to=data.valid_to,
            business_reason=data.business_reason,
        )
        audit(
            self.session,
            self.actor,
            "access.request_created",
            item.id,
            request_type=item.request_type,
            subject_user_id=subject.id,
        )
        reviewers = await self.repo.list(
            User,
            limit=500,
            conditions=[
                User.role == "PLATFORM_ADMIN",
                User.is_active.is_(True),
                User.id != self.actor.id,
            ],
        )
        for reviewer in reviewers:
            add_notification(
                self.session,
                tenant_id=self.actor.tenant_id,
                event_key=f"access-request:{item.id}:pending:{reviewer.id}",
                kind="ACCESS_REQUEST_PENDING",
                severity="INFO",
                resource_type="ACCESS_REQUEST",
                resource_id=item.id,
                title="Permintaan akses menunggu keputusan",
                message="Tinjau permintaan akses sementara dan periode yang diajukan.",
                details={"request_type": item.request_type, "subject_user_id": subject.id},
                recipient_user_id=reviewer.id,
            )
        return access_request_record(item, self.actor, subject, attribute, bundle)

    async def list_access_requests(self, *, mine=False, status=None, offset=0, limit=100):
        conditions = []
        if mine:
            conditions.append(
                or_(
                    AccessRequest.requester_id == self.actor.id,
                    AccessRequest.subject_user_id == self.actor.id,
                )
            )
        if status:
            conditions.append(AccessRequest.status == status)
        items = await self.repo.list(AccessRequest, offset=offset, limit=limit, conditions=conditions)
        return [await self._access_request_record(item) for item in items]

    async def decide_access_request(self, request_id, data, decision):
        item = await self._access_request(request_id, lock=True)
        if item.revision != data.revision:
            raise AppError("STALE_REVISION", "Permintaan akses telah berubah; muat ulang.", 409)
        if item.status != "PENDING":
            raise AppError("ACCESS_REQUEST_NOT_PENDING", "Permintaan akses tidak lagi menunggu.", 409)
        if item.requester_id == self.actor.id:
            raise AppError("ACCESS_REQUEST_APPROVER_CONFLICT", "Permintaan harus diputuskan admin lain.")
        target = await self._user(item.subject_user_id)
        if not target.is_active:
            raise AppError("USER_INACTIVE", "Akses tidak dapat diberikan kepada pengguna nonaktif.")
        item.reviewed_by = self.actor.id
        item.reviewed_at = now()
        item.decision_note = data.note
        if decision == "reject":
            item.status = "REJECTED"
        else:
            if item.valid_to <= now():
                raise AppError("ACCESS_REQUEST_EXPIRED", "Periode permintaan akses telah berakhir.", 409)
            if item.request_type == "ATTRIBUTE":
                attribute = await self._attribute(item.attribute_id)
                if not attribute.is_active:
                    raise AppError("ACCESS_ATTRIBUTE_INACTIVE", "Atribut akses tidak aktif.")
                overlap = await self.session.scalar(
                    self.repo.query(UserAssignment).where(
                        UserAssignment.user_id == target.id,
                        UserAssignment.attribute_id == attribute.id,
                        UserAssignment.status == "ACTIVE",
                        or_(UserAssignment.valid_to.is_(None), UserAssignment.valid_to > item.valid_from),
                        UserAssignment.valid_from < item.valid_to,
                    )
                )
                if overlap:
                    raise AppError(
                        "ASSIGNMENT_PERIOD_OVERLAP", "Assignment pada periode tersebut sudah ada.", 409
                    )
                assignment = await self.repo.add(
                    UserAssignment,
                    user_id=target.id,
                    attribute_id=attribute.id,
                    valid_from=item.valid_from,
                    valid_to=item.valid_to,
                    granted_by=self.actor.id,
                    note=f"Access request {item.id}",
                )
                item.assignment_id = assignment.id
            else:
                bundle = await self._bundle(item.bundle_id)
                if not bundle.is_active:
                    raise AppError("PERMISSION_BUNDLE_INACTIVE", "Permission bundle tidak aktif.")
                overlap = await self.session.scalar(
                    self.repo.query(UserPermissionGrant).where(
                        UserPermissionGrant.user_id == target.id,
                        UserPermissionGrant.bundle_id == bundle.id,
                        UserPermissionGrant.status == "ACTIVE",
                        or_(
                            UserPermissionGrant.valid_to.is_(None),
                            UserPermissionGrant.valid_to > item.valid_from,
                        ),
                        UserPermissionGrant.valid_from < item.valid_to,
                    )
                )
                if overlap:
                    raise AppError(
                        "PERMISSION_GRANT_PERIOD_OVERLAP",
                        "Permission bundle pada periode tersebut sudah ada.",
                        409,
                    )
                grant = await self.repo.add(
                    UserPermissionGrant,
                    user_id=target.id,
                    bundle_id=bundle.id,
                    valid_from=item.valid_from,
                    valid_to=item.valid_to,
                    granted_by=self.actor.id,
                    note=f"Access request {item.id}",
                )
                item.permission_grant_id = grant.id
            item.status = "APPROVED"
        item.revision += 1
        audit(
            self.session,
            self.actor,
            f"access.request_{'approved' if decision == 'approve' else 'rejected'}",
            item.id,
            requester_id=item.requester_id,
            subject_user_id=item.subject_user_id,
        )
        await resolve_notifications(
            self.session,
            tenant_id=self.actor.tenant_id,
            resource_type="ACCESS_REQUEST",
            resource_id=item.id,
            actor_id=self.actor.id,
        )
        return await self._access_request_record(item)

    async def approve_access_requests(self, data):
        if self.actor.role != "PLATFORM_ADMIN":
            raise AppError("FORBIDDEN", "Persetujuan akses memerlukan admin.", 403)
        results = []
        for item in sorted(data.requests, key=lambda value: str(value.id)):
            results.append(await self.decide_access_request(
                item.id, AccessRequestDecision(revision=item.revision, note=data.note), "approve"
            ))
        return results

    async def cancel_access_request(self, request_id, data):
        item = await self._access_request(request_id, lock=True)
        if self.actor.id not in (item.requester_id, item.subject_user_id):
            raise AppError("FORBIDDEN", "Hanya pemohon atau user tujuan yang dapat membatalkan.", 403)
        if item.revision != data.revision:
            raise AppError("STALE_REVISION", "Permintaan akses telah berubah; muat ulang.", 409)
        if item.status != "PENDING":
            raise AppError(
                "ACCESS_REQUEST_NOT_PENDING", "Hanya permintaan menunggu yang dapat dibatalkan.", 409
            )
        item.status = "CANCELLED"
        item.revision += 1
        item.decision_note = data.note
        audit(self.session, self.actor, "access.request_cancelled", item.id)
        await resolve_notifications(
            self.session,
            tenant_id=self.actor.tenant_id,
            resource_type="ACCESS_REQUEST",
            resource_id=item.id,
            actor_id=self.actor.id,
        )
        return await self._access_request_record(item)

    async def revoke_access_request(self, request_id, data):
        item = await self._access_request(request_id, lock=True)
        if self.actor.role != "PLATFORM_ADMIN" and self.actor.id not in (
            item.requester_id,
            item.subject_user_id,
        ):
            raise AppError("FORBIDDEN", "Hanya pemohon, user tujuan, atau admin yang dapat mencabut.", 403)
        if item.revision != data.revision:
            raise AppError("STALE_REVISION", "Permintaan akses telah berubah; muat ulang.", 409)
        if item.status != "APPROVED":
            raise AppError("ACCESS_REQUEST_NOT_APPROVED", "Hanya akses approved yang dapat dicabut.", 409)
        target = await self._user(item.subject_user_id)
        if item.assignment_id:
            assignment = await self.repo.get(UserAssignment, item.assignment_id, lock=True)
            if assignment.status == "ACTIVE":
                assignment.status = "REVOKED"
                assignment.revision += 1
                assignment.revoked_by = self.actor.id
                assignment.revoked_at = now()
        if item.permission_grant_id:
            grant = await self.repo.get(UserPermissionGrant, item.permission_grant_id, lock=True)
            if grant.status == "ACTIVE":
                grant.status = "REVOKED"
                grant.revision += 1
                grant.revoked_by = self.actor.id
                grant.revoked_at = now()
        target.token_version += 1
        item.status = "REVOKED"
        item.revision += 1
        item.reviewed_by = self.actor.id
        item.reviewed_at = now()
        item.decision_note = data.note
        audit(self.session, self.actor, "access.request_revoked", item.id, requester_id=target.id)
        return await self._access_request_record(item)

    async def list_policy_resources(self, resource_type, search="", offset=0, limit=100):
        model, code = POLICY_RESOURCES[resource_type]
        conditions = [or_(code.ilike(f"%{search}%"), model.name.ilike(f"%{search}%"))] if search else []
        items = await self.repo.list(model, offset=offset, limit=limit, conditions=conditions)
        total = await self.session.scalar(
            select(func.count()).select_from(model).where(
                model.tenant_id == self.actor.tenant_id, *conditions
            )
        )
        return (
            [
                {"id": item.id, "code": getattr(item, code.key), "name": item.name, "status": item.status}
                for item in items
            ],
            total or 0,
        )

    async def _policy_values(self, data, current=None):
        values = data.model_dump(exclude_unset=True)
        attribute_ids = values.get(
            "required_attribute_ids", current.required_attribute_ids if current else []
        )
        normalized_ids = [str(value) for value in attribute_ids]
        if len(normalized_ids) != len(set(normalized_ids)):
            raise AppError("POLICY_ATTRIBUTE_DUPLICATE", "Atribut policy tidak boleh duplikat.")
        for attribute_id in normalized_ids:
            attribute = await self._attribute(attribute_id)
            if not attribute.is_active:
                raise AppError("ACCESS_ATTRIBUTE_INACTIVE", "Policy tidak boleh memakai atribut nonaktif.")
        values["required_attribute_ids"] = normalized_ids
        actions = values.get("actions", current.actions if current else [])
        values["actions"] = sorted(set(actions))
        effect = values.get("effect", current.effect if current else None)
        row_scope = values.get("row_scope", current.row_scope if current else {})
        column_rules = values.get("column_rules", current.column_rules if current else {})
        export_allowed = values.get("export_allowed", current.export_allowed if current else False)
        valid_from = values.get("valid_from", current.valid_from if current else now())
        valid_to = values.get("valid_to", current.valid_to if current else None)
        if valid_to is not None and valid_to <= valid_from:
            raise AppError("POLICY_PERIOD_INVALID", "valid_to harus setelah valid_from.")
        values["valid_from"] = valid_from
        if effect == "DENY" and (row_scope or column_rules or export_allowed):
            raise AppError("DENY_POLICY_CONTROL_INVALID", "DENY tidak menerima kontrol hasil ALLOW.")
        return values

    async def create_policy(self, data):
        values = await self._policy_values(data)
        values["code"] = data.code.upper()
        values["created_by"] = self.actor.id
        item = await self.repo.add(AccessPolicy, **values)
        audit(self.session, self.actor, "access.policy_created", item.id, code=item.code)
        return policy_record(item)

    async def list_policies(self, include_revoked=False):
        conditions = [] if include_revoked else [AccessPolicy.status != "REVOKED"]
        items = await self.repo.list(AccessPolicy, limit=500, conditions=conditions)
        return [policy_record(item) for item in items]

    async def update_policy(self, policy_id, data):
        item = await self._policy(policy_id, lock=True)
        if item.status != "DRAFT":
            raise AppError("POLICY_NOT_EDITABLE", "Hanya policy DRAFT yang dapat diubah.", 409)
        if item.revision != data.revision:
            raise AppError("STALE_REVISION", "Policy telah berubah; muat ulang sebelum menyimpan.", 409)
        values = await self._policy_values(data, item)
        values.pop("revision", None)
        for field, value in values.items():
            setattr(item, field, value)
        item.revision += 1
        audit(self.session, self.actor, "access.policy_updated", item.id, revision=item.revision)
        return policy_record(item)

    async def create_policy_binding(self, policy_id, data):
        policy = await self._policy(policy_id, lock=True)
        if policy.status != "DRAFT":
            raise AppError("POLICY_NOT_EDITABLE", "Binding hanya dapat ditambah pada policy DRAFT.", 409)
        model, code = POLICY_RESOURCES[data.resource_type]
        resource = await self.session.scalar(self.repo.query(model).where(code == data.resource_id))
        if resource is None:
            raise AppError("RESOURCE_NOT_FOUND", "Data tidak ditemukan.", 404)
        binding = await self.repo.add(
            AccessPolicyBinding,
            policy_id=policy.id,
            resource_type=data.resource_type,
            resource_id=data.resource_id,
        )
        policy.revision += 1
        audit(
            self.session,
            self.actor,
            "access.policy_binding_created",
            binding.id,
            policy_id=policy.id,
            resource_type=binding.resource_type,
            bound_resource_id=binding.resource_id,
        )
        return record(binding)

    async def list_policy_bindings(self, policy_id):
        await self._policy(policy_id)
        items = await self.repo.list(
            AccessPolicyBinding, limit=500, conditions=[AccessPolicyBinding.policy_id == str(policy_id)]
        )
        return [record(item) for item in items]

    async def transition_policy(self, policy_id, data, action):
        item = await self._policy(policy_id, lock=True)
        if item.revision != data.revision:
            raise AppError("STALE_REVISION", "Policy telah berubah; muat ulang sebelum melanjutkan.", 409)
        if action == "submit":
            if item.status != "DRAFT":
                raise AppError("POLICY_TRANSITION_INVALID", "Hanya policy DRAFT yang dapat diajukan.", 409)
            binding = await self.session.scalar(
                self.repo.query(AccessPolicyBinding).where(AccessPolicyBinding.policy_id == item.id)
            )
            if binding is None:
                raise AppError("POLICY_BINDING_REQUIRED", "Tambahkan minimal satu binding resource.")
            item.status = "IN_REVIEW"
            item.submitted_by = self.actor.id
            item.submitted_at = now()
        elif action == "approve":
            if item.status != "IN_REVIEW":
                raise AppError(
                    "POLICY_TRANSITION_INVALID", "Hanya policy IN_REVIEW yang dapat disetujui.", 409
                )
            if item.created_by == self.actor.id:
                raise AppError(
                    "POLICY_APPROVER_CONFLICT", "Pembuat policy tidak boleh menyetujui policy sendiri."
                )
            item.status = "APPROVED"
            item.approved_by = self.actor.id
            item.approved_at = now()
        elif action == "revoke":
            if item.status != "APPROVED":
                raise AppError("POLICY_TRANSITION_INVALID", "Hanya policy APPROVED yang dapat dicabut.", 409)
            item.status = "REVOKED"
            item.revoked_by = self.actor.id
            item.revoked_at = now()
        item.revision += 1
        item.decision_note = data.note
        audit(self.session, self.actor, f"access.policy_{action}", item.id, revision=item.revision)
        return policy_record(item)

    async def create_bundle(self, data):
        item = await self.repo.add(
            PermissionBundle,
            code=data.code.upper(),
            label=data.label,
            description=data.description,
            actions=sorted(set(data.actions)),
        )
        audit(self.session, self.actor, "access.permission_bundle_created", item.id, code=item.code)
        return bundle_record(item)

    async def list_bundles(self, include_inactive=False):
        conditions = [] if include_inactive else [PermissionBundle.is_active.is_(True)]
        items = await self.repo.list(PermissionBundle, limit=500, conditions=conditions)
        return [bundle_record(item) for item in items]

    async def update_bundle(self, bundle_id, data):
        item = await self._bundle(bundle_id, lock=True)
        if item.revision != data.revision:
            raise AppError(
                "STALE_REVISION", "Permission bundle telah berubah; muat ulang sebelum menyimpan.", 409
            )
        changes = data.model_dump(exclude={"revision"}, exclude_unset=True)
        if changes.get("actions") is not None:
            changes["actions"] = sorted(set(changes["actions"]))
        for field, value in changes.items():
            setattr(item, field, value)
        item.revision += 1
        audit(self.session, self.actor, "access.permission_bundle_updated", item.id, revision=item.revision)
        return bundle_record(item)

    async def create_permission_grant(self, user_id, data):
        target = await self._user(user_id)
        if target.id == self.actor.id:
            raise AppError("SELF_ACCESS_CHANGE", "Permission bundle harus diberikan oleh admin lain.")
        if not target.is_active:
            raise AppError("USER_INACTIVE", "Permission tidak dapat diberikan kepada pengguna nonaktif.")
        bundle = await self._bundle(data.bundle_id)
        if not bundle.is_active:
            raise AppError("PERMISSION_BUNDLE_INACTIVE", "Permission bundle tidak aktif.")
        overlap = await self.session.scalar(
            self.repo.query(UserPermissionGrant).where(
                UserPermissionGrant.user_id == target.id,
                UserPermissionGrant.bundle_id == bundle.id,
                UserPermissionGrant.status == "ACTIVE",
                or_(UserPermissionGrant.valid_to.is_(None), UserPermissionGrant.valid_to > data.valid_from),
                True if data.valid_to is None else UserPermissionGrant.valid_from < data.valid_to,
            )
        )
        if overlap:
            raise AppError(
                "PERMISSION_GRANT_PERIOD_OVERLAP", "Permission aktif pada periode tersebut sudah ada.", 409
            )
        item = await self.repo.add(
            UserPermissionGrant,
            user_id=target.id,
            bundle_id=bundle.id,
            valid_from=data.valid_from,
            valid_to=data.valid_to,
            granted_by=self.actor.id,
            note=data.note,
        )
        target.token_version += 1
        audit(
            self.session,
            self.actor,
            "access.permission_grant_created",
            item.id,
            assigned_user_id=target.id,
            bundle_id=bundle.id,
        )
        return grant_record(item, bundle)

    async def list_permission_grants(self, user_id, include_inactive=False):
        await self._user(user_id)
        query = (
            select(UserPermissionGrant, PermissionBundle)
            .join(PermissionBundle, PermissionBundle.id == UserPermissionGrant.bundle_id)
            .where(
                UserPermissionGrant.tenant_id == self.actor.tenant_id,
                PermissionBundle.tenant_id == self.actor.tenant_id,
                UserPermissionGrant.user_id == str(user_id),
            )
            .order_by(UserPermissionGrant.created_at.desc())
        )
        if not include_inactive:
            query = query.where(UserPermissionGrant.status == "ACTIVE")
        rows = (await self.session.execute(query)).all()
        return [grant_record(item, bundle) for item, bundle in rows]

    async def revoke_permission_grant(self, grant_id, data):
        item = await self.repo.get(UserPermissionGrant, grant_id, lock=True)
        if item.user_id == self.actor.id:
            raise AppError("SELF_ACCESS_CHANGE", "Permission bundle harus dicabut oleh admin lain.")
        if item.revision != data.revision:
            raise AppError(
                "STALE_REVISION", "Permission grant telah berubah; muat ulang sebelum mencabut.", 409
            )
        if item.status == "REVOKED":
            raise AppError("PERMISSION_GRANT_ALREADY_REVOKED", "Permission grant sudah dicabut.", 409)
        item.status = "REVOKED"
        item.revision += 1
        item.revoked_by = self.actor.id
        item.revoked_at = now()
        if data.note:
            item.note = data.note
        target = await self._user(item.user_id)
        target.token_version += 1
        bundle = await self._bundle(item.bundle_id)
        audit(
            self.session,
            self.actor,
            "access.permission_grant_revoked",
            item.id,
            assigned_user_id=item.user_id,
            bundle_id=item.bundle_id,
        )
        return grant_record(item, bundle)

    async def create_attribute(self, data):
        parent = None
        if data.parent_id:
            parent = await self._attribute(data.parent_id)
            if parent.kind != data.kind:
                raise AppError(
                    "ACCESS_HIERARCHY_KIND_MISMATCH", "Induk harus memiliki jenis atribut yang sama."
                )
        item = await self.repo.add(
            AccessAttribute,
            kind=data.kind,
            code=data.code.upper(),
            label=data.label,
            parent_id=parent.id if parent else None,
            attribute_data=data.attribute_data,
        )
        audit(self.session, self.actor, "access.attribute_created", item.id, kind=item.kind, code=item.code)
        return attribute_record(item)

    async def list_attributes(self, kind=None, include_inactive=False):
        conditions = []
        if kind:
            conditions.append(AccessAttribute.kind == kind)
        if not include_inactive:
            conditions.append(AccessAttribute.is_active.is_(True))
        items = await self.repo.list(AccessAttribute, limit=500, conditions=conditions)
        return [attribute_record(item) for item in items]

    async def registration_options(self):
        effective = await self.effective_access(self.actor.id)
        scopes = [
            item["attribute"]
            for item in effective["assignments"]
            if item["attribute"]["kind"] in ("DEPARTMENT", "BUSINESS_DOMAIN", "JURISDICTION")
        ]
        purposes = await self.repo.list(
            AccessAttribute,
            limit=500,
            conditions=[AccessAttribute.kind == "PURPOSE", AccessAttribute.is_active.is_(True)],
        )
        people = await self.repo.list(
            User,
            limit=500,
            conditions=[
                User.is_active.is_(True),
                or_(User.id == self.actor.id, User.role.in_(("SOURCE_OWNER", "DATA_STEWARD"))),
            ],
        )
        return {
            "scopes": scopes,
            "purposes": [attribute_record(item) for item in purposes],
            "people": [{"id": item.id, "username": item.username, "role": item.role} for item in people],
            "sensitivities": ["LOW", "MEDIUM", "HIGH"],
        }

    async def update_attribute(self, attribute_id, data):
        item = await self._attribute(attribute_id, lock=True)
        if item.revision != data.revision:
            raise AppError(
                "STALE_REVISION", "Atribut akses telah berubah; muat ulang sebelum menyimpan.", 409
            )
        changes = data.model_dump(exclude={"revision"}, exclude_unset=True)
        if "parent_id" in changes and changes["parent_id"] is not None:
            if str(changes["parent_id"]) == item.id:
                raise AppError("ACCESS_HIERARCHY_CYCLE", "Atribut tidak dapat menjadi induknya sendiri.")
            parent = await self._attribute(changes["parent_id"])
            if parent.kind != item.kind:
                raise AppError(
                    "ACCESS_HIERARCHY_KIND_MISMATCH", "Induk harus memiliki jenis atribut yang sama."
                )
            ancestor = parent
            visited = {item.id}
            while ancestor is not None:
                if ancestor.id in visited:
                    raise AppError(
                        "ACCESS_HIERARCHY_CYCLE", "Hierarchy atribut tidak boleh membentuk siklus."
                    )
                visited.add(ancestor.id)
                ancestor = await self._attribute(ancestor.parent_id) if ancestor.parent_id else None
            changes["parent_id"] = parent.id
        for field, value in changes.items():
            setattr(item, field, value)
        item.revision += 1
        audit(self.session, self.actor, "access.attribute_updated", item.id, revision=item.revision)
        return attribute_record(item)

    async def create_assignment(self, user_id, data):
        target = await self._user(user_id)
        if target.id == self.actor.id:
            raise AppError("SELF_ACCESS_CHANGE", "Assignment harus diberikan oleh admin lain.", 422)
        if not target.is_active:
            raise AppError("USER_INACTIVE", "Assignment tidak dapat diberikan kepada pengguna nonaktif.")
        attribute = await self._attribute(data.attribute_id)
        if not attribute.is_active:
            raise AppError("ACCESS_ATTRIBUTE_INACTIVE", "Atribut akses tidak aktif.")
        overlap = await self.session.scalar(
            self.repo.query(UserAssignment).where(
                UserAssignment.user_id == target.id,
                UserAssignment.attribute_id == attribute.id,
                UserAssignment.status == "ACTIVE",
                or_(UserAssignment.valid_to.is_(None), UserAssignment.valid_to > data.valid_from),
                True if data.valid_to is None else UserAssignment.valid_from < data.valid_to,
            )
        )
        if overlap:
            raise AppError(
                "ASSIGNMENT_PERIOD_OVERLAP",
                "Assignment aktif pada atribut dan periode tersebut sudah ada.",
                409,
            )
        item = await self.repo.add(
            UserAssignment,
            user_id=target.id,
            attribute_id=attribute.id,
            valid_from=data.valid_from,
            valid_to=data.valid_to,
            granted_by=self.actor.id,
            note=data.note,
        )
        audit(
            self.session,
            self.actor,
            "access.assignment_created",
            item.id,
            assigned_user_id=target.id,
            attribute_id=attribute.id,
        )
        return assignment_record(item, attribute)

    async def create_unit_assignments(self, user_id, data):
        # The API request is one transaction: a failure in any unit rolls back all assignments.
        from app.schemas.access import UserAssignmentCreate

        units = (await self.session.scalars(
            self.repo.query(AccessAttribute).where(AccessAttribute.id.in_([str(value) for value in data.unit_ids]))
        )).all()
        if len(units) != len(data.unit_ids) or any(item.kind != "DEPARTMENT" for item in units):
            raise AppError("UNIT_ASSIGNMENT_INVALID", "Pilih hanya unit tenant yang tersedia.", 422)
        result = []
        for unit_id in data.unit_ids:
            result.append(await self.create_assignment(user_id, UserAssignmentCreate(
                attribute_id=unit_id, valid_from=data.valid_from, valid_to=data.valid_to,
                note=data.note,
            )))
        return result

    async def list_assignments(self, user_id, include_inactive=False):
        await self._user(user_id)
        query = (
            select(UserAssignment, AccessAttribute)
            .join(AccessAttribute, AccessAttribute.id == UserAssignment.attribute_id)
            .where(
                UserAssignment.tenant_id == self.actor.tenant_id,
                AccessAttribute.tenant_id == self.actor.tenant_id,
                UserAssignment.user_id == str(user_id),
            )
            .order_by(UserAssignment.created_at.desc())
        )
        if not include_inactive:
            query = query.where(UserAssignment.status == "ACTIVE")
        rows = (await self.session.execute(query)).all()
        return [assignment_record(item, attribute) for item, attribute in rows]

    async def revoke_assignment(self, assignment_id, data):
        item = await self.repo.get(UserAssignment, assignment_id, lock=True)
        if item.user_id == self.actor.id:
            raise AppError("SELF_ACCESS_CHANGE", "Assignment harus dicabut oleh admin lain.", 422)
        if item.revision != data.revision:
            raise AppError("STALE_REVISION", "Assignment telah berubah; muat ulang sebelum mencabut.", 409)
        if item.status == "REVOKED":
            raise AppError("ASSIGNMENT_ALREADY_REVOKED", "Assignment sudah dicabut.", 409)
        item.status = "REVOKED"
        item.revision += 1
        item.revoked_by = self.actor.id
        item.revoked_at = now()
        if data.note:
            item.note = data.note
        target = await self._user(item.user_id)
        target.token_version += 1
        attribute = await self._attribute(item.attribute_id)
        audit(
            self.session,
            self.actor,
            "access.assignment_revoked",
            item.id,
            assigned_user_id=item.user_id,
            attribute_id=item.attribute_id,
        )
        return assignment_record(item, attribute)

    async def effective_access(self, user_id, at: datetime | None = None):
        target = await self._user(user_id)
        instant = at or now()
        if not target.is_active:
            return {
                "user": {
                    "id": target.id,
                    "username": target.username,
                    "role": target.role,
                    "is_active": False,
                },
                "as_of": instant,
                "actions": [],
                "dimensions": {},
                "assignments": [],
                "permission_grants": [],
            }
        query = (
            select(UserAssignment, AccessAttribute)
            .join(AccessAttribute, AccessAttribute.id == UserAssignment.attribute_id)
            .where(
                UserAssignment.tenant_id == self.actor.tenant_id,
                AccessAttribute.tenant_id == self.actor.tenant_id,
                UserAssignment.user_id == target.id,
                UserAssignment.status == "ACTIVE",
                UserAssignment.valid_from <= instant,
                or_(UserAssignment.valid_to.is_(None), UserAssignment.valid_to > instant),
                AccessAttribute.is_active.is_(True),
            )
            .order_by(AccessAttribute.kind, AccessAttribute.code)
        )
        rows = (await self.session.execute(query)).all()
        assignments = [assignment_record(item, attribute) for item, attribute in rows]
        dimensions = {}
        for _, attribute in rows:
            dimensions.setdefault(attribute.kind, []).append(attribute.code)
        grants_query = (
            select(UserPermissionGrant, PermissionBundle)
            .join(PermissionBundle, PermissionBundle.id == UserPermissionGrant.bundle_id)
            .where(
                UserPermissionGrant.tenant_id == self.actor.tenant_id,
                PermissionBundle.tenant_id == self.actor.tenant_id,
                UserPermissionGrant.user_id == target.id,
                UserPermissionGrant.status == "ACTIVE",
                UserPermissionGrant.valid_from <= instant,
                or_(UserPermissionGrant.valid_to.is_(None), UserPermissionGrant.valid_to > instant),
                PermissionBundle.is_active.is_(True),
            )
            .order_by(PermissionBundle.code)
        )
        grant_rows = (await self.session.execute(grants_query)).all()
        grants = [grant_record(item, bundle) for item, bundle in grant_rows]
        actions = set(ROLE_ACTIONS.get(target.role, []))
        for _, bundle in grant_rows:
            actions.update(bundle.actions)
        return {
            "user": {
                "id": target.id,
                "username": target.username,
                "role": target.role,
                "is_active": target.is_active,
            },
            "as_of": instant,
            "actions": sorted(actions),
            "dimensions": dimensions,
            "assignments": assignments,
            "permission_grants": grants,
        }

    async def evaluate(self, data):
        target_id = data.user_id or self.actor.id
        effective = await self.effective_access(target_id, data.at)

        def finish(decision):
            decision.setdefault("policy_revisions", [])
            audit(
                self.session,
                self.actor,
                "access.evaluated",
                data.resource_id,
                subject_user_id=str(target_id),
                action=data.action,
                resource_type=data.resource_type,
                allowed=decision["allowed"],
                reason_code=decision["reason_code"],
                policy_ids=decision["policy_ids"],
            )
            return decision

        if not effective["user"]["is_active"]:
            return finish(
                {
                    "allowed": False,
                    "reason_code": "USER_INACTIVE",
                    "policy_ids": [],
                    "row_scope": {},
                    "columns": {},
                    "export_allowed": False,
                }
            )

        resource_bindings = [
            (AccessPolicyBinding.resource_type == data.resource_type)
            & (AccessPolicyBinding.resource_id == data.resource_id)
        ]
        parent_source = None
        if data.resource_type == "DATA_PRODUCT":
            parent_source = await self.session.scalar(
                self.repo.query(DataSource)
                .join(
                    SourceSheet,
                    (SourceSheet.source_id == DataSource.id)
                    & (SourceSheet.tenant_id == self.actor.tenant_id),
                )
                .join(
                    DataProduct,
                    (DataProduct.source_sheet_id == SourceSheet.id)
                    & (DataProduct.tenant_id == self.actor.tenant_id),
                )
                .where(DataProduct.code == data.resource_id)
            )
            if parent_source is not None:
                resource_bindings.append(
                    (AccessPolicyBinding.resource_type == "SOURCE")
                    & (AccessPolicyBinding.resource_id == parent_source.source_code)
                )
        query = (
            select(AccessPolicy)
            .join(AccessPolicyBinding, AccessPolicyBinding.policy_id == AccessPolicy.id)
            .where(
                AccessPolicy.tenant_id == self.actor.tenant_id,
                AccessPolicyBinding.tenant_id == self.actor.tenant_id,
                or_(*resource_bindings),
                AccessPolicy.status == "APPROVED",
                AccessPolicy.valid_from <= data.at,
                or_(AccessPolicy.valid_to.is_(None), AccessPolicy.valid_to > data.at),
                AccessPolicy.actions.contains([data.action]),
            )
            .distinct()
        )
        policies = list((await self.session.scalars(query)).all())
        active_attributes = {item["attribute_id"] for item in effective["assignments"]}
        source_scope = set()
        if data.resource_type in ("SOURCE", "DATA_PRODUCT"):
            source = parent_source
            if source is None and data.resource_type == "SOURCE":
                source = await self.session.scalar(
                    self.repo.query(DataSource).where(DataSource.source_code == data.resource_id)
                )
            if source is not None and source.access_metadata:
                source_scope = {
                    source.access_metadata[field]
                    for field in ("owner_unit_id", "business_domain_id", "jurisdiction_id")
                }
        matched = [
            policy
            for policy in policies
            if set(policy.required_attribute_ids).issubset(active_attributes)
            and (policy.effect == "DENY" or source_scope.issubset(policy.required_attribute_ids))
        ]
        denied = [policy for policy in matched if policy.effect == "DENY"]
        if denied:
            return finish(
                {
                    "allowed": False,
                    "reason_code": "EXPLICIT_DENY",
                    "policy_ids": [policy.id for policy in denied],
                    "policy_revisions": [{"id": policy.id, "revision": policy.revision} for policy in denied],
                    "row_scope": {},
                    "columns": {},
                    "export_allowed": False,
                }
            )
        if data.action not in effective["actions"]:
            return finish(
                {
                    "allowed": False,
                    "reason_code": "ACTION_NOT_GRANTED",
                    "policy_ids": [],
                    "row_scope": {},
                    "columns": {},
                    "export_allowed": False,
                }
            )
        allowed = [policy for policy in matched if policy.effect == "ALLOW"]
        if not allowed:
            return finish(
                {
                    "allowed": False,
                    "reason_code": "DEFAULT_DENY",
                    "policy_ids": [],
                    "row_scope": {},
                    "columns": {},
                    "export_allowed": False,
                }
            )
        if data.action == "EXPORT" and not all(policy.export_allowed for policy in allowed):
            return finish(
                {
                    "allowed": False,
                    "reason_code": "EXPORT_NOT_ALLOWED",
                    "policy_ids": [policy.id for policy in allowed],
                    "policy_revisions": [
                        {"id": policy.id, "revision": policy.revision} for policy in allowed
                    ],
                    "row_scope": {},
                    "columns": {},
                    "export_allowed": False,
                }
            )
        row_scope = {}
        for policy in allowed:
            for field, values in policy.row_scope.items():
                permitted = set(values)
                row_scope[field] = sorted(
                    permitted if field not in row_scope else set(row_scope[field]) & permitted
                )
        rank = {"VISIBLE": 0, "MASKED": 1, "HIDDEN": 2}
        columns = {}
        for policy in allowed:
            for field, visibility in policy.column_rules.items():
                if field not in columns or rank[visibility] > rank[columns[field]]:
                    columns[field] = visibility
        return finish(
            {
                "allowed": True,
                "reason_code": "POLICY_MATCH",
                "policy_ids": [policy.id for policy in allowed],
                "policy_revisions": [{"id": policy.id, "revision": policy.revision} for policy in allowed],
                "row_scope": row_scope,
                "columns": columns,
                "export_allowed": data.action == "EXPORT"
                and all(policy.export_allowed for policy in allowed),
            }
        )
