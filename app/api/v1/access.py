from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import Depends, Query

from app.api.dependencies import CurrentUser, Session, require_roles
from app.core.exceptions import AppError, success
from app.core.routing import APIRouter
from app.domain.enums import EDIT_ROLES
from app.schemas.access import (
    AccessAttributeCreate,
    AccessAttributeUpdate,
    AccessEvaluationRequest,
    AccessPolicyBindingCreate,
    AccessPolicyCreate,
    AccessPolicyTransition,
    AccessPolicyUpdate,
    AccessRequestCreate,
    AccessRequestDecision,
    AccessRequestReject,
    AssignmentRevoke,
    MultiUnitAssignmentCreate,
    PermissionBundleCreate,
    PermissionBundleUpdate,
    PermissionGrantCreate,
    UserAssignmentCreate,
)
from app.services.access_service import AccessService

router = APIRouter(prefix="/access", tags=["Access jurisdiction"])
admin = [Depends(require_roles("PLATFORM_ADMIN"))]


@router.get("/registration-options", dependencies=[Depends(require_roles(*EDIT_ROLES))])
async def registration_options(session: Session, user: CurrentUser):
    return success(await AccessService(session, user).registration_options())


@router.get("/resources", dependencies=admin)
async def list_policy_resources(
    session: Session,
    user: CurrentUser,
    resource_type: Literal["DATA_PRODUCT", "SOURCE", "MASTER", "TAXONOMY"],
    search: str = Query("", max_length=63),
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
):
    items, total = await AccessService(session, user).list_policy_resources(
        resource_type, search, offset, limit
    )
    return success(items, offset=offset, limit=limit, total=total)


@router.get("/attributes", dependencies=admin)
async def list_attributes(
    session: Session,
    user: CurrentUser,
    kind: Literal["DEPARTMENT", "BUSINESS_DOMAIN", "JURISDICTION", "CLEARANCE", "PURPOSE"] | None = None,
    include_inactive: bool = False,
):
    return success(await AccessService(session, user).list_attributes(kind, include_inactive))


@router.post("/attributes", status_code=201, dependencies=admin)
async def create_attribute(data: AccessAttributeCreate, session: Session, user: CurrentUser):
    return success(await AccessService(session, user).create_attribute(data))


@router.patch("/attributes/{attribute_id}", dependencies=admin)
async def update_attribute(attribute_id: UUID, data: AccessAttributeUpdate, session: Session, user: CurrentUser):
    return success(await AccessService(session, user).update_attribute(attribute_id, data))


@router.get("/permission-bundles", dependencies=admin)
async def list_permission_bundles(session: Session, user: CurrentUser, include_inactive: bool = Query(False)):
    return success(await AccessService(session, user).list_bundles(include_inactive))


@router.post("/permission-bundles", status_code=201, dependencies=admin)
async def create_permission_bundle(data: PermissionBundleCreate, session: Session, user: CurrentUser):
    return success(await AccessService(session, user).create_bundle(data))


@router.patch("/permission-bundles/{bundle_id}", dependencies=admin)
async def update_permission_bundle(
    bundle_id: UUID, data: PermissionBundleUpdate, session: Session, user: CurrentUser
):
    return success(await AccessService(session, user).update_bundle(bundle_id, data))


@router.get("/users/{user_id}/assignments", dependencies=admin)
async def list_assignments(
    user_id: UUID, session: Session, user: CurrentUser, include_inactive: bool = Query(False)
):
    return success(await AccessService(session, user).list_assignments(user_id, include_inactive))


@router.post("/users/{user_id}/assignments", status_code=201, dependencies=admin)
async def create_assignment(user_id: UUID, data: UserAssignmentCreate, session: Session, user: CurrentUser):
    return success(await AccessService(session, user).create_assignment(user_id, data))


@router.post("/users/{user_id}/unit-assignments", status_code=201, dependencies=admin)
async def create_unit_assignments(user_id: UUID, data: MultiUnitAssignmentCreate, session: Session, user: CurrentUser):
    return success(await AccessService(session, user).create_unit_assignments(user_id, data))


@router.post("/assignments/{assignment_id}/revoke", dependencies=admin)
async def revoke_assignment(assignment_id: UUID, data: AssignmentRevoke, session: Session, user: CurrentUser):
    return success(await AccessService(session, user).revoke_assignment(assignment_id, data))


@router.get("/users/{user_id}/permission-grants", dependencies=admin)
async def list_permission_grants(
    user_id: UUID, session: Session, user: CurrentUser, include_inactive: bool = Query(False)
):
    return success(await AccessService(session, user).list_permission_grants(user_id, include_inactive))


@router.post("/users/{user_id}/permission-grants", status_code=201, dependencies=admin)
async def create_permission_grant(
    user_id: UUID, data: PermissionGrantCreate, session: Session, user: CurrentUser
):
    return success(await AccessService(session, user).create_permission_grant(user_id, data))


@router.post("/permission-grants/{grant_id}/revoke", dependencies=admin)
async def revoke_permission_grant(grant_id: UUID, data: AssignmentRevoke, session: Session, user: CurrentUser):
    return success(await AccessService(session, user).revoke_permission_grant(grant_id, data))


@router.get("/request-options")
async def access_request_options(session: Session, user: CurrentUser):
    return success(await AccessService(session, user).request_options())


@router.post("/requests", status_code=201)
async def create_access_request(data: AccessRequestCreate, session: Session, user: CurrentUser):
    return success(await AccessService(session, user).create_access_request(data))


@router.get("/requests/mine")
async def list_my_access_requests(
    session: Session,
    user: CurrentUser,
    status: Literal["PENDING", "APPROVED", "REJECTED", "CANCELLED", "REVOKED"] | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
):
    return success(
        await AccessService(session, user).list_access_requests(
            mine=True, status=status, offset=offset, limit=limit
        ),
        offset=offset,
        limit=limit,
    )


@router.get("/requests", dependencies=admin)
async def list_access_requests(
    session: Session,
    user: CurrentUser,
    status: Literal["PENDING", "APPROVED", "REJECTED", "CANCELLED", "REVOKED"] | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
):
    return success(
        await AccessService(session, user).list_access_requests(
            status=status, offset=offset, limit=limit
        ),
        offset=offset,
        limit=limit,
    )


@router.post("/requests/{request_id}/approve", dependencies=admin)
async def approve_access_request(
    request_id: UUID, data: AccessRequestDecision, session: Session, user: CurrentUser
):
    return success(await AccessService(session, user).decide_access_request(request_id, data, "approve"))


@router.post("/requests/{request_id}/reject", dependencies=admin)
async def reject_access_request(
    request_id: UUID, data: AccessRequestReject, session: Session, user: CurrentUser
):
    return success(await AccessService(session, user).decide_access_request(request_id, data, "reject"))


@router.post("/requests/{request_id}/cancel")
async def cancel_access_request(
    request_id: UUID, data: AccessRequestDecision, session: Session, user: CurrentUser
):
    return success(await AccessService(session, user).cancel_access_request(request_id, data))


@router.post("/requests/{request_id}/revoke")
async def revoke_access_request(
    request_id: UUID, data: AccessRequestReject, session: Session, user: CurrentUser
):
    return success(await AccessService(session, user).revoke_access_request(request_id, data))


@router.get("/policies", dependencies=admin)
async def list_access_policies(session: Session, user: CurrentUser, include_revoked: bool = Query(False)):
    return success(await AccessService(session, user).list_policies(include_revoked))


@router.post("/policies", status_code=201, dependencies=admin)
async def create_access_policy(data: AccessPolicyCreate, session: Session, user: CurrentUser):
    return success(await AccessService(session, user).create_policy(data))


@router.patch("/policies/{policy_id}", dependencies=admin)
async def update_access_policy(policy_id: UUID, data: AccessPolicyUpdate, session: Session, user: CurrentUser):
    return success(await AccessService(session, user).update_policy(policy_id, data))


@router.get("/policies/{policy_id}/bindings", dependencies=admin)
async def list_access_policy_bindings(policy_id: UUID, session: Session, user: CurrentUser):
    return success(await AccessService(session, user).list_policy_bindings(policy_id))


@router.post("/policies/{policy_id}/bindings", status_code=201, dependencies=admin)
async def create_access_policy_binding(
    policy_id: UUID, data: AccessPolicyBindingCreate, session: Session, user: CurrentUser
):
    return success(await AccessService(session, user).create_policy_binding(policy_id, data))


@router.post("/policies/{policy_id}/submit", dependencies=admin)
async def submit_access_policy(
    policy_id: UUID, data: AccessPolicyTransition, session: Session, user: CurrentUser
):
    return success(await AccessService(session, user).transition_policy(policy_id, data, "submit"))


@router.post("/policies/{policy_id}/approve", dependencies=admin)
async def approve_access_policy(
    policy_id: UUID, data: AccessPolicyTransition, session: Session, user: CurrentUser
):
    return success(await AccessService(session, user).transition_policy(policy_id, data, "approve"))


@router.post("/policies/{policy_id}/revoke", dependencies=admin)
async def revoke_access_policy(
    policy_id: UUID, data: AccessPolicyTransition, session: Session, user: CurrentUser
):
    return success(await AccessService(session, user).transition_policy(policy_id, data, "revoke"))


@router.post("/evaluate")
async def evaluate_access(data: AccessEvaluationRequest, session: Session, user: CurrentUser):
    if data.user_id and user.role != "PLATFORM_ADMIN" and str(data.user_id) != user.id:
        raise AppError("FORBIDDEN", "User hanya dapat mengevaluasi akses miliknya sendiri.", 403)
    return success(await AccessService(session, user).evaluate(data))


@router.get("/users/{user_id}/effective", dependencies=admin)
async def user_effective_access(
    user_id: UUID, session: Session, user: CurrentUser, at: datetime | None = Query(None)
):
    return success(await AccessService(session, user).effective_access(user_id, at))


@router.get("/me/effective")
async def my_effective_access(session: Session, user: CurrentUser, at: datetime | None = Query(None)):
    return success(await AccessService(session, user).effective_access(user.id, at))
