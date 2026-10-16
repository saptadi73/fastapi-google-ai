"""Production owner mode: shared unit operations without legacy human approvals."""
from datetime import timedelta

import pytest
from sqlalchemy import select
from test_integration import context as context
from test_integration import onboard, request, source_access_metadata

from app.core.config import get_settings
from app.core.database import SessionFactory
from app.core.security import issue_token
from app.models.access import AccessPolicy, AccessPolicyBinding, UserAssignment
from app.models.auth import User
from app.models.base import now
from app.models.etl import Job
from app.models.semantic import DataProduct
from app.models.source import DataSource
from app.schemas.access import AccessEvaluationRequest
from app.services.access_service import AccessService
from app.workers.runner import run_pending, schedule_sources

pytestmark = pytest.mark.integration


@pytest.fixture
def owner_mode(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "etl_owner_workflow_enabled", True)
    monkeypatch.setattr(settings, "unit_domain_default_access_enabled", True)
    # A leftover legacy setting must not reinstate a second approver.
    monkeypatch.setattr(settings, "require_separate_approver", True)


async def peer(ctx, unit_id, *, role="SOURCE_OWNER", username="peer", assigned=True):
    async with SessionFactory() as session, session.begin():
        admin = await session.scalar(select(User).where(User.tenant_id == ctx.tenant_id, User.username == "admin"))
        user = User(tenant_id=ctx.tenant_id, username=username, role=role, password_hash=admin.password_hash)
        session.add(user)
        await session.flush()
        if assigned:
            session.add(UserAssignment(tenant_id=ctx.tenant_id, user_id=user.id, attribute_id=unit_id,
                                       valid_from=now()-timedelta(days=1), granted_by=admin.id))
        token, _ = issue_token(user, "access")
        ctx.headers[username] = {"Authorization": "Bearer " + token}
        return user.id


async def shared_source(ctx, data):
    source, sheet, config = await onboard(ctx, data, legacy_source=False)
    async with SessionFactory() as session:
        obj = await session.get(DataSource, source)
        unit = obj.access_metadata["owner_unit_id"]
    return source, sheet, config, unit


async def publish_and_deploy(ctx, config, who):
    path = "/configurations/"+config["id"]
    validation = (await request(ctx, "POST", path+"/validate", who=who))["data"]
    submitted = (await request(ctx, "POST", path+"/submit-review", who=who, data={
        "revision_no": config["revision_no"], "snapshot_hash": validation["snapshot_hash"],
        "reviewed_schema_fingerprint": validation["deployment_plan"]["migration"]["fingerprint"],
    }))["data"]
    assert submitted["status"] == "APPROVED"
    job = (await request(ctx, "POST", path+"/deploy", who=who, expected=202))["data"]
    await run_pending(ctx.tenant_id)
    finished = (await request(ctx, "GET", "/jobs/"+job["job_id"]))["data"]
    assert finished["status"] == "SUCCEEDED", finished


@pytest.mark.parametrize("role", ["SOURCE_OWNER", "DATA_STEWARD"])
async def test_shared_unit_editor_deploys_and_syncs_without_legacy_approvals(context, config_data, owner_mode, role):
    source, _, config, unit = await shared_source(context, config_data)
    await peer(context, unit, role=role)
    async with SessionFactory() as session, session.begin():
        obj = await session.get(DataSource, source)
        obj.access_status, obj.access_review_status = "ACCESS_POLICY_REQUIRED", "PENDING"
        obj.approval_assignees = {"configuration": [], "metadata_review": [], "import_review": []}
        obj.release_policy = {"technical_approver_ids": [], "unit_groups": []}
    activated = (await request(context, "POST", f"/sources/{source}/validate-access", who="peer"))["data"]
    assert activated["access_status"] == "POLICY_APPROVED" and activated["access_review_status"] == "APPROVED"
    tracking = (await request(context, "GET", "/sources/tracking", who="peer"))["data"]
    assert next(item for item in tracking if item["id"] == source)["it_approval_status"] == "VALIDATION_REQUIRED"
    async with SessionFactory() as session:
        original = await session.get(DataSource, source)
        spreadsheet = original.spreadsheet_id
        original_owner = original.owner_user_id
    duplicate = (await request(context, "GET", f"/sources/registration-check?spreadsheet_url={spreadsheet}", who="peer"))["data"]
    assert duplicate["can_manage"] and not duplicate["owned_by_me"] and duplicate["source_id"] == source
    async with SessionFactory() as session:
        assert (await session.get(DataSource, source)).owner_user_id == original_owner
    await publish_and_deploy(context, config, "peer")
    tracking = (await request(context, "GET", "/sources/tracking", who="peer"))["data"]
    assert next(item for item in tracking if item["id"] == source)["it_approval_status"] == "VALIDATED"
    products = (await request(context, "GET", "/semantic/data-products", who="peer"))["data"]
    product = next(item for item in products if item["code"] == config_data["semantic"]["code"])
    changed = (await request(context, "PATCH", f"/semantic/data-products/{product['id']}", who="peer", data={
        "expected_version": product["version"], "description": "Dikelola bersama dalam unit yang sama",
    }))["data"]
    assert changed["description"] == "Dikelola bersama dalam unit yang sama"
    await request(context, "POST", f"/sources/{source}/sync", who="peer", expected=202)
    for _ in range(4):
        await run_pending(context.tenant_id)
    batches = (await request(context, "GET", "/import-reviews", who="peer"))["data"]["items"]
    assert any(r["status"] == "SUCCEEDED" and r["checkpoint"]["approval_mode"] == "ACTIVE_CONFIGURATION" for r in batches), batches


async def test_unit_only_registration_defaults_managers_and_needs_no_registration_review(context, owner_mode):
    metadata = await source_access_metadata(context)
    uid = await peer(context, metadata["owner_unit_id"])
    result = (await request(context, "POST", "/sources/google-sheets", who="peer", expected=202, data={
        "name": "Simple source", "spreadsheet_url": "simple_unit_source_123",
        "access_metadata": {"owner_unit_id": metadata["owner_unit_id"]},
    }))["data"]["source"]
    assert result["access_status"] == "POLICY_APPROVED"
    assert result["access_metadata"]["data_owner_user_id"] == uid
    assert result["access_metadata"]["data_steward_user_id"] == uid
    assert result["access_metadata"]["business_domain_id"] is None
    await run_pending(context.tenant_id)
    refreshed = (await request(context, "GET", "/sources/"+result["id"], who="peer"))["data"]
    assert refreshed["access_review_status"] == "APPROVED"


async def test_other_unit_and_revoked_membership_cannot_manage_or_read_source(context, config_data, owner_mode):
    source, _, config, unit = await shared_source(context, config_data)
    uid = await peer(context, unit)
    await peer(context, unit, username="other", assigned=False)
    await request(context, "POST", f"/sources/{source}/sync", who="other", expected=403)
    await request(context, "GET", f"/sources/{source}", who="other", expected=404)
    await request(context, "POST", f"/configurations/{config['id']}/validate", who="other", expected=404)
    assert not (await request(context, "GET", "/sources", who="other"))["data"]
    async with SessionFactory() as session, session.begin():
        assignment = await session.scalar(select(UserAssignment).where(UserAssignment.user_id == uid))
        assignment.status = "REVOKED"
    await request(context, "POST", f"/sources/{source}/validate-access", who="peer", expected=403)
    await request(context, "GET", f"/sources/{source}", who="peer", expected=404)
    await request(context, "GET", f"/sources/{source}", who="outsider", expected=404)


async def test_unit_default_read_ignores_draft_policy_but_preserves_explicit_deny(context, config_data, owner_mode):
    source, _, _, unit = await shared_source(context, config_data)
    uid = await peer(context, unit, role="VIEWER")
    async with SessionFactory() as session, session.begin():
        obj = await session.get(DataSource, source)
        policy = AccessPolicy(tenant_id=context.tenant_id, code="draft_block", label="Draft", effect="DENY",
            actions=["READ", "EDIT"], required_attribute_ids=[unit], status="DRAFT", valid_from=now()-timedelta(days=1), created_by=obj.owner_user_id)
        session.add(policy)
        await session.flush()
        session.add(AccessPolicyBinding(tenant_id=context.tenant_id, policy_id=policy.id, resource_type="SOURCE", resource_id=obj.source_code))
        pid, code = policy.id, obj.source_code
    async with SessionFactory() as session, session.begin():
        user = await session.get(User, uid)
        allowed = await AccessService(session, user).evaluate(AccessEvaluationRequest(resource_type="SOURCE", resource_id=code, action="READ"))
        assert allowed["allowed"] and not allowed["export_allowed"]
        exported = await AccessService(session, user).evaluate(AccessEvaluationRequest(resource_type="SOURCE", resource_id=code, action="EXPORT"))
        assert not exported["allowed"]
        policy = await session.get(AccessPolicy, pid)
        policy.status = "APPROVED"
        policy.required_attribute_ids = [obj.access_metadata["business_domain_id"]]
    async with SessionFactory() as session, session.begin():
        user = await session.get(User, uid)
        unmatched = await AccessService(session, user).evaluate(AccessEvaluationRequest(resource_type="SOURCE", resource_id=code, action="READ"))
        assert unmatched["allowed"], unmatched
        policy = await session.get(AccessPolicy, pid)
        policy.required_attribute_ids = [unit]
    async with SessionFactory() as session, session.begin():
        user = await session.get(User, uid)
        denied = await AccessService(session, user).evaluate(AccessEvaluationRequest(resource_type="SOURCE", resource_id=code, action="READ"))
        assert not denied["allowed"] and denied["reason_code"] == "EXPLICIT_DENY"


async def test_product_policy_cannot_be_widened_by_parent_source_allow(context, config_data, owner_mode):
    source, sheet, _, unit = await shared_source(context, config_data)
    uid = await peer(context, unit, role="VIEWER")
    async with SessionFactory() as session, session.begin():
        obj = await session.get(DataSource, source)
        session.add(DataProduct(tenant_id=context.tenant_id, source_sheet_id=sheet, code="UNIT_PRODUCT",
            name="Unit product", view_name="v_unit_product", columns=[], metrics=[], dimensions=[], allowed_roles=["VIEWER"]))
        for code, resource_type, resource_id, attributes in (
            ("source_allow", "SOURCE", obj.source_code, [unit]),
            ("product_scope", "DATA_PRODUCT", "UNIT_PRODUCT", [unit, obj.access_metadata["business_domain_id"]]),
        ):
            policy = AccessPolicy(tenant_id=context.tenant_id, code=code, label=code, effect="ALLOW",
                actions=["READ", "QUERY", "DISCOVER"], required_attribute_ids=attributes, status="APPROVED",
                valid_from=now()-timedelta(days=1), created_by=obj.owner_user_id)
            session.add(policy)
            await session.flush()
            session.add(AccessPolicyBinding(tenant_id=context.tenant_id, policy_id=policy.id,
                resource_type=resource_type, resource_id=resource_id))
    async with SessionFactory() as session, session.begin():
        user = await session.get(User, uid)
        denied = await AccessService(session, user).evaluate(AccessEvaluationRequest(
            resource_type="DATA_PRODUCT", resource_id="UNIT_PRODUCT", action="READ"))
        assert not denied["allowed"], denied


async def test_owner_publishes_taxonomy_and_activates_binding_without_another_reviewer(context, config_data, owner_mode):
    _, sheet, _, unit = await shared_source(context, config_data)
    await peer(context, unit)
    taxonomy = (await request(context, "POST", "/taxonomies", who="peer", expected=201,
                              data={"code": "branch", "name": "Branch"}))["data"]
    await request(context, "POST", f"/taxonomies/{taxonomy['id']}/terms", who="peer", expected=201,
                  data={"code": "jakarta", "label": "Jakarta"})
    approved = (await request(context, "POST", f"/taxonomies/{taxonomy['id']}/approve", who="peer"))["data"]
    assert approved["status"] == "APPROVED"
    bound = (await request(context, "PUT", f"/taxonomies/source-sheets/{sheet}/column-bindings", who="peer", data={
        "source_column": "Cabang", "taxonomy_id": taxonomy["id"], "taxonomy_version": approved["version"], "revision_no": 0,
    }))["data"]
    assert bound["status"] == "APPROVED" and bound["approved_by"] == taxonomy["created_by"]


async def test_scheduled_sync_uses_owner_auto_load_even_with_legacy_source_status(context, config_data, owner_mode):
    source, _, config, _ = await shared_source(context, config_data)
    await publish_and_deploy(context, config, "admin")
    async with SessionFactory() as session, session.begin():
        obj = await session.get(DataSource, source)
        obj.status, obj.sync_schedule = "NEEDS_REVIEW", "0 * * * *"
        obj.last_scheduled_at = now()-timedelta(days=2)
    await schedule_sources()
    async with SessionFactory() as session:
        jobs = (await session.scalars(select(Job).where(Job.source_id == source, Job.kind == "SYNC_REVIEW"))).all()
        assert len(jobs) == 1 and jobs[0].payload["auto_load"] is True
