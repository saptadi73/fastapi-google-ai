import asyncio
import base64
import io
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from openpyxl import load_workbook
from sqlalchemy import delete, func, select, text, update
from sqlalchemy.engine import make_url

from app.core.config import get_settings
from app.core.database import SessionFactory
from app.core.exceptions import AppError
from app.core.security import decode_token, password_hasher
from app.main import app
from app.models import Base
from app.models.access import AccessAttribute, UserAssignment
from app.models.audit import AuditEvent
from app.models.auth import Tenant, User
from app.models.configuration import Artifact, Configuration
from app.models.etl import Job, Snapshot
from app.models.import_review import ImportReview
from app.models.master import MasterDefinition
from app.models.semantic import DataProduct, JoinRelationship, SavedQuery
from app.models.source import DataSource, SourceSheet
from app.services.configuration_service import ConfigurationService
from app.services.google_sheets_service import GoogleSheetsService
from app.services.release_approval_service import require_release_ready
from app.workers.runner import run_pending, schedule_sources

pytestmark = pytest.mark.integration


async def test_connection_uses_dedicated_database():
    expected = make_url(get_settings().test_database_url.get_secret_value()).database
    async with SessionFactory() as session:
        actual = await session.scalar(text("SELECT current_database()"))
    assert actual == expected
    assert actual.endswith("_test")


@pytest.fixture
async def context(monkeypatch, tmp_path, sheet_values):
    tenant_ids = []
    settings = get_settings()
    monkeypatch.setattr(settings, "artifact_storage_path", tmp_path / "artifacts")
    monkeypatch.setattr(settings, "openai_api_key", type(settings.openai_api_key)(""))
    monkeypatch.setattr(settings, "require_separate_approver", True)
    current_values = [row[:] for row in sheet_values]

    async def metadata(self, spreadsheet_id):
        return {"sheets": [{"properties": {"sheetId": 1, "title": "Sales", "sheetType": "GRID"}}]}

    async def read(self, spreadsheet_id, sheets):
        return [[r[:] for r in current_values] for _ in sheets]

    monkeypatch.setattr(GoogleSheetsService, "metadata", metadata)
    monkeypatch.setattr(GoogleSheetsService, "read_sheets", read)
    async with SessionFactory() as session, session.begin():
        tenant = Tenant(code="integration_" + uuid4().hex)
        outsider = Tenant(code="integration_" + uuid4().hex)
        session.add_all([tenant, outsider])
        await session.flush()
        tenant_ids.extend([tenant.id, outsider.id])
        for target, name, role, scope in [
            (tenant, "admin", "PLATFORM_ADMIN", {}),
            (tenant, "approver", "TECHNICAL_APPROVER", {}),
            (tenant, "viewer", "VIEWER", {"SALES": {"branch_name": ["Jakarta"]}}),
            (outsider, "admin", "PLATFORM_ADMIN", {}),
        ]:
            session.add(
                User(
                    tenant_id=target.id,
                    username=name,
                    password_hash=password_hasher.hash("test-password-123"),
                    role=role,
                    row_scope=scope,
                )
            )
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:

        async def login(name, tenant_code=tenant.code):
            r = await client.post(
                "/api/v1/auth/login",
                json={"tenant_code": tenant_code, "username": name, "password": "test-password-123"},
            )
            assert r.status_code == 200, r.text
            return r.json()["data"]

        tokens = {name: await login(name) for name in ("admin", "approver", "viewer")}
        tokens["outsider"] = await login("admin", outsider.code)
        headers = {
            name: {"Authorization": "Bearer " + token["access_token"]} for name, token in tokens.items()
        }
        try:
            yield SimpleNamespace(
                client=client,
                headers=headers,
                tokens=tokens,
                values=current_values,
                tenant_id=tenant.id,
                tenant_code=tenant.code,
            )
        finally:
            # Cleanup is restricted to UUIDs created by this fixture. No existing tenant is touched.
            async with SessionFactory() as session, session.begin():
                sheets = list(
                    (
                        await session.scalars(
                            select(SourceSheet).where(SourceSheet.tenant_id.in_(tenant_ids))
                        )
                    ).all()
                )
                configs = list(
                    (
                        await session.scalars(
                            select(Configuration).where(Configuration.tenant_id.in_(tenant_ids))
                        )
                    ).all()
                )
                quote = session.bind.dialect.identifier_preparer.quote
                master_ids = (
                    await session.scalars(
                        select(MasterDefinition.id).where(MasterDefinition.tenant_id.in_(tenant_ids))
                    )
                ).all()
                for master_id in master_ids:
                    await session.execute(
                        text(f"DROP TABLE IF EXISTS trusted.{quote('master_' + master_id.replace('-', ''))}")
                    )
                for sheet in sheets:
                    await session.execute(
                        text(f"DROP VIEW IF EXISTS semantic.{quote('v_' + sheet.id.replace('-', ''))}")
                    )
                names = {
                    c.configuration_json["target_table"] + "_" + c.source_sheet_id.replace("-", "")
                    for c in configs
                }
                for name in names:
                    await session.execute(text(f"DROP TABLE IF EXISTS trusted.{quote(name)}"))
                await session.execute(
                    update(SourceSheet)
                    .where(SourceSheet.tenant_id.in_(tenant_ids))
                    .values(active_configuration_id=None)
                )
                for table in reversed(Base.metadata.sorted_tables):
                    if "tenant_id" in table.c:
                        await session.execute(delete(table).where(table.c.tenant_id.in_(tenant_ids)))
                await session.execute(
                    delete(Tenant).where(Tenant.id.in_(tenant_ids), Tenant.code.like("integration_%"))
                )


async def request(ctx, method, path, *, who="admin", expected=200, data=None):
    response = await ctx.client.request(method, "/api/v1" + path, headers=ctx.headers[who], json=data)
    assert response.status_code == expected, response.text
    return response.json()


async def test_release_needs_it_and_each_related_unit_on_same_revision(context):
    async with SessionFactory() as session, session.begin():
        users = {item.username: item for item in (await session.scalars(
            select(User).where(User.tenant_id == context.tenant_id)
        )).all()}
        units = [AccessAttribute(tenant_id=context.tenant_id, kind="DEPARTMENT",
                                 code="release_" + uuid4().hex, label=label)
                 for label in ("Penjualan Malang", "Keuangan Surabaya")]
        manager = User(tenant_id=context.tenant_id, username="manager", role="VIEWER",
                       password_hash=password_hasher.hash("test-password-123"))
        source = DataSource(tenant_id=context.tenant_id, source_code="release_" + uuid4().hex[:20],
                            name="Rilis lintas unit", spreadsheet_id="test-release-sheet",
                            owner_user_id=users["admin"].id)
        session.add_all([*units, manager, source])
        await session.flush()
        sheet = SourceSheet(tenant_id=context.tenant_id, source_id=source.id, sheet_id=1,
                            sheet_name="Penjualan")
        session.add(sheet)
        await session.flush()
        config = Configuration(tenant_id=context.tenant_id, source_id=source.id,
                               source_sheet_id=sheet.id, version_no=1, status="APPROVED",
                               based_on_fingerprint="a" * 64,
                               configuration_json={"target_table": "release_test"},
                               review_state={"snapshot_hash": "b" * 64},
                               created_by=users["admin"].id)
        session.add(config)
        await session.flush()
        source_id, config_id = source.id, config.id
        unit_id, second_unit_id = [unit.id for unit in units]
        technical_id, business_id = users["approver"].id, users["viewer"].id
        manager_id = manager.id

    login_response = await context.client.post("/api/v1/auth/login", json={
        "tenant_code": context.tenant_code, "username": "manager", "password": "test-password-123"
    })
    assert login_response.status_code == 200
    context.headers["manager"] = {"Authorization": "Bearer " + login_response.json()["data"]["access_token"]}

    await request(context, "POST", f"/access/users/{business_id}/unit-assignments", expected=201,
                  data={"unit_ids": [unit_id, second_unit_id], "note": "Approver rilis unit"})
    await request(context, "POST", f"/access/users/{manager_id}/unit-assignments", expected=201,
                  data={"unit_ids": [second_unit_id], "note": "Approver unit terkait"})
    groups = [{"unit_id": unit_id, "approver_ids": [business_id]},
              {"unit_id": second_unit_id, "approver_ids": [manager_id]}]
    await request(context, "PUT", f"/release-approvals/sources/{source_id}/policy", expected=422,
                  data={"revision": 1, "technical_approver_ids": [technical_id],
                        "unit_groups": [{"unit_id": unit_id, "approver_ids": [business_id]},
                                        {"unit_id": second_unit_id, "approver_ids": [business_id]}]})
    policy = await request(context, "PUT", f"/release-approvals/sources/{source_id}/policy",
                           data={"revision": 1, "technical_approver_ids": [technical_id],
                                 "unit_groups": groups})
    assert policy["data"]["revision"] == 2
    status = await request(context, "GET", f"/release-approvals/configurations/{config_id}", who="viewer")
    assert not status["data"]["ready"]
    assert [group["status"] for group in status["data"]["groups"]] == ["PENDING"] * 3
    inbox = await request(context, "GET", "/release-approvals/inbox", who="viewer")
    assert any(item["configuration_id"] == config_id for item in inbox["data"])
    await request(context, "POST", f"/configurations/{config_id}/deploy", who="approver", expected=409)
    async with SessionFactory() as session:
        actor = await session.scalar(select(User).where(
            User.tenant_id == context.tenant_id, User.username == "approver"
        ))
        with pytest.raises(AppError) as worker_error:
            await ConfigurationService(session, actor).deploy(config_id)
        assert worker_error.value.code == "RELEASE_APPROVAL_REQUIRED"
    await request(context, "POST", f"/release-approvals/configurations/{config_id}/decisions",
                  who="viewer", expected=403,
                  data={"revision_no": 1, "group_type": "TECHNICAL", "decision": "APPROVE",
                        "comment": "Tidak berwenang", "technical_checks": {
                            "schema_and_mapping": True, "data_quality": True, "security_and_access": True,
                        }})
    await request(context, "POST", f"/release-approvals/configurations/{config_id}/decisions",
                  who="approver", expected=422,
                  data={"revision_no": 1, "group_type": "TECHNICAL", "decision": "APPROVE",
                        "comment": "Checklist belum lengkap"})
    await request(context, "POST", f"/release-approvals/configurations/{config_id}/decisions",
                  who="approver", data={"revision_no": 1, "group_type": "TECHNICAL",
                                        "decision": "APPROVE", "comment": "Tes skema dan keamanan lulus",
                                        "technical_checks": {"schema_and_mapping": True,
                                                             "data_quality": True,
                                                             "security_and_access": True}})
    await request(context, "POST", f"/configurations/{config_id}/deploy", who="approver", expected=409)
    partial = await request(context, "POST", f"/release-approvals/configurations/{config_id}/decisions",
                              who="viewer", data={"revision_no": 1, "group_type": "UNIT",
                                                   "unit_id": unit_id, "decision": "APPROVE",
                                                   "comment": "Definisi bisnis sesuai"})
    assert not partial["data"]["ready"]
    await request(context, "POST", f"/release-approvals/configurations/{config_id}/decisions",
                  who="viewer", expected=403,
                  data={"revision_no": 1, "group_type": "UNIT", "unit_id": second_unit_id,
                        "decision": "APPROVE", "comment": "Tidak berwenang unit lain"})
    completed = await request(context, "POST", f"/release-approvals/configurations/{config_id}/decisions",
                              who="manager", data={"revision_no": 1, "group_type": "UNIT",
                                                   "unit_id": second_unit_id, "decision": "APPROVE",
                                                   "comment": "Data unit terkait sesuai"})
    assert completed["data"]["ready"]
    async with SessionFactory() as session:
        config = await session.get(Configuration, config_id)
        source = await session.get(DataSource, source_id)
        assert require_release_ready(config, source)["ready"]
    await request(context, "PUT", f"/release-approvals/sources/{source_id}/policy",
                  data={"revision": 2, "technical_approver_ids": [technical_id],
                        "unit_groups": groups})
    stale = await request(context, "GET", f"/release-approvals/configurations/{config_id}", who="viewer")
    assert not stale["data"]["ready"]
    async with SessionFactory() as session:
        config = await session.get(Configuration, config_id)
        source = await session.get(DataSource, source_id)
        with pytest.raises(AppError) as error:
            require_release_ready(config, source)
        assert error.value.code == "RELEASE_APPROVAL_REQUIRED"
    rejected = await request(context, "POST", f"/release-approvals/configurations/{config_id}/decisions",
                             who="approver", data={"revision_no": 1, "group_type": "TECHNICAL",
                                                   "decision": "REJECT", "comment": "Masalah keamanan belum selesai"})
    assert rejected["data"]["groups"][0]["status"] == "REJECTED"
    await request(context, "POST", f"/release-approvals/configurations/{config_id}/decisions",
                  who="approver", expected=409,
                  data={"revision_no": 1, "group_type": "TECHNICAL", "decision": "APPROVE",
                        "comment": "Coba menyetujui tanpa revisi baru", "technical_checks": {
                            "schema_and_mapping": True, "data_quality": True, "security_and_access": True,
                        }})


async def test_multi_unit_assignment_and_explicit_source_approvers(context):
    async with SessionFactory() as session, session.begin():
        users = {item.username: item for item in (await session.scalars(
            select(User).where(User.tenant_id == context.tenant_id)
        )).all()}
        units = [AccessAttribute(tenant_id=context.tenant_id, kind="DEPARTMENT",
                                 code="unit_" + uuid4().hex, label=label)
                 for label in ("Penjualan Malang", "Penjualan Surabaya")]
        source = DataSource(tenant_id=context.tenant_id, source_code="approval_" + uuid4().hex[:20],
                            name="Sumber approval", spreadsheet_id="test-approver-sheet",
                            owner_user_id=users["admin"].id)
        session.add_all([*units, source])
        await session.flush()
        sheet = SourceSheet(tenant_id=context.tenant_id, source_id=source.id, sheet_id=1,
                            sheet_name="Penjualan")
        session.add(sheet)
        await session.flush()
        configuration = Configuration(
            tenant_id=context.tenant_id, source_id=source.id, source_sheet_id=sheet.id,
            version_no=1, status="NEEDS_REVIEW", based_on_fingerprint="a" * 64,
            configuration_json={"target_table": "approval_test"}, created_by=users["admin"].id,
        )
        snapshot = Snapshot(
            tenant_id=context.tenant_id, source_id=source.id, source_sheet_id=sheet.id,
            content_hash="b" * 64, row_count=0, values=[],
        )
        session.add_all([configuration, snapshot])
        await session.flush()
        review = ImportReview(
            tenant_id=context.tenant_id, source_id=source.id, source_sheet_id=sheet.id,
            snapshot_id=snapshot.id, created_by=users["admin"].id,
            idempotency_key=uuid4().hex, status="VALIDATING", dependencies={},
            configuration_json={}, checkpoint={},
        )
        session.add(review)
        await session.flush()
        unit_ids = [item.id for item in units]
        source_id = source.id
        configuration_id = configuration.id
        review_id = review.id
        reviewer_id = users["approver"].id
        viewer_id = users["viewer"].id

    created = await request(context, "POST", f"/access/users/{viewer_id}/unit-assignments",
                            expected=201, data={"unit_ids": unit_ids})
    assert {item["attribute_id"] for item in created["data"]} == set(unit_ids)
    effective = await request(context, "GET", f"/access/users/{viewer_id}/effective")
    assert set(effective["data"]["dimensions"]["DEPARTMENT"]) == {item.code for item in units}

    await request(context, "POST", f"/sources/{source_id}/access-review", who="approver", expected=403,
                  data={"revision_no": 1, "decision": "APPROVE", "reason": "METADATA_VERIFIED"})

    setup = await request(context, "PUT", f"/sources/{source_id}/approvers", data={
        "revision": 1, "metadata_review": [reviewer_id],
        "configuration": [reviewer_id], "import_review": [reviewer_id],
    })
    assert setup["data"]["configured"] is True
    await request(context, "PUT", f"/sources/{source_id}/approvers", expected=409, data={
        "revision": 1, "metadata_review": [], "configuration": [], "import_review": [],
    })
    await request(context, "POST", f"/sources/{source_id}/access-review", expected=403,
                  data={"revision_no": 1, "decision": "APPROVE", "reason": "METADATA_VERIFIED"})
    await request(context, "POST", f"/configurations/{configuration_id}/approve", expected=403,
                  data={"revision_no": 1, "comment": "Review"})
    await request(context, "POST", f"/import-reviews/{review_id}/approve", expected=403,
                  data={"revision_no": 1, "comment": "Review"})
    await request(context, "POST", f"/sources/{source_id}/access-review", who="approver", expected=409,
                  data={"revision_no": 1, "decision": "APPROVE", "reason": "METADATA_VERIFIED"})
    await request(context, "POST", f"/configurations/{configuration_id}/approve", who="approver", expected=409,
                  data={"revision_no": 2, "comment": "Review"})
    await request(context, "POST", f"/import-reviews/{review_id}/approve", who="approver", expected=409,
                  data={"revision_no": 1, "comment": "Review"})


async def source_access_metadata(ctx):
    async with SessionFactory() as session, session.begin():
        admin_id = await session.scalar(
            select(User.id).where(User.tenant_id == ctx.tenant_id, User.username == "admin")
        )
        metadata = {
            "data_owner_user_id": admin_id,
            "data_steward_user_id": admin_id,
            "sensitivity": "LOW",
        }
        for field, kind in (
            ("owner_unit_id", "DEPARTMENT"),
            ("business_domain_id", "BUSINESS_DOMAIN"),
            ("jurisdiction_id", "JURISDICTION"),
            ("purpose_id", "PURPOSE"),
        ):
            attribute = AccessAttribute(
                tenant_id=ctx.tenant_id,
                kind=kind,
                code="TEST_" + uuid4().hex,
                label=kind.title(),
            )
            session.add(attribute)
            await session.flush()
            metadata[field] = attribute.id
            if kind != "PURPOSE":
                session.add(
                    UserAssignment(
                        tenant_id=ctx.tenant_id,
                        user_id=admin_id,
                        attribute_id=attribute.id,
                        granted_by=admin_id,
                        valid_from=datetime.now(timezone.utc) - timedelta(days=1),
                    )
                )
    return metadata


async def test_new_unit_assignment_appears_for_source_registrant(context):
    """The registration dropdown must reflect a newly granted unit for that exact login."""
    async with SessionFactory() as session, session.begin():
        registrant = User(
            tenant_id=context.tenant_id,
            username="saptadi1",
            role="SOURCE_OWNER",
            password_hash=password_hasher.hash("test-password-123"),
        )
        unit = AccessAttribute(
            tenant_id=context.tenant_id,
            kind="DEPARTMENT",
            code="MARKETING",
            label="Marketing",
        )
        session.add_all([registrant, unit])
        await session.flush()
        registrant_id, unit_id = registrant.id, unit.id

    login_response = await context.client.post("/api/v1/auth/login", json={
        "tenant_code": context.tenant_code,
        "username": "saptadi1",
        "password": "test-password-123",
    })
    assert login_response.status_code == 200
    context.headers["saptadi1"] = {
        "Authorization": "Bearer " + login_response.json()["data"]["access_token"]
    }
    before = (await request(context, "GET", "/access/registration-options", who="saptadi1"))["data"]
    assert unit_id not in {scope["id"] for scope in before["scopes"]}

    created = await request(
        context,
        "POST",
        f"/access/users/{registrant_id}/unit-assignments",
        expected=201,
        data={"unit_ids": [unit_id]},
    )
    assert created["data"][0]["attribute_id"] == unit_id
    after = (await request(context, "GET", "/access/registration-options", who="saptadi1"))["data"]
    assert {scope["id"] for scope in after["scopes"]} == {unit_id}
    assert after["scopes"][0]["code"] == "MARKETING"



async def test_source_registration_checks_access_metadata(context):
    ctx = context
    base = {"name": "Scoped source", "spreadsheet_url": "fake_sheet_12345"}
    await request(ctx, "POST", "/sources/google-sheets", expected=422, data=base)
    metadata = await source_access_metadata(ctx)
    options = (await request(ctx, "GET", "/access/registration-options"))["data"]
    assert {item["id"] for item in options["scopes"]} == {
        metadata["owner_unit_id"],
        metadata["business_domain_id"],
        metadata["jurisdiction_id"],
    }
    assert [item["id"] for item in options["purposes"]] == [metadata["purpose_id"]]
    assert options["sensitivities"] == ["LOW", "MEDIUM", "HIGH"]
    assert (await request(ctx, "GET", "/access/registration-options", who="outsider"))["data"]["scopes"] == []
    await request(ctx, "GET", "/access/registration-options", who="viewer", expected=403)
    await request(
        ctx,
        "POST",
        "/sources/google-sheets",
        expected=422,
        data={**base, "access_metadata": {**metadata, "purpose_id": metadata["owner_unit_id"]}},
    )
    await request(
        ctx,
        "POST",
        "/sources/google-sheets",
        who="approver",
        expected=403,
        data={**base, "access_metadata": metadata},
    )
    outsider_id = decode_token(ctx.tokens["outsider"]["access_token"])["sub"]
    async with SessionFactory() as session, session.begin():
        outsider_tenant_id = await session.scalar(select(User.tenant_id).where(User.id == outsider_id))
        foreign_attribute = AccessAttribute(
            tenant_id=outsider_tenant_id, kind="DEPARTMENT", code="FOREIGN_SCOPE", label="Outside"
        )
        unassigned_attribute = AccessAttribute(
            tenant_id=ctx.tenant_id, kind="DEPARTMENT", code="UNASSIGNED_SCOPE", label="Unassigned"
        )
        session.add_all([foreign_attribute, unassigned_attribute])
        await session.flush()
        foreign_id, unassigned_id = foreign_attribute.id, unassigned_attribute.id
        viewer_id = await session.scalar(
            select(User.id).where(User.tenant_id == ctx.tenant_id, User.username == "viewer")
        )
    await request(
        ctx,
        "POST",
        "/sources/google-sheets",
        expected=404,
        data={**base, "access_metadata": {**metadata, "owner_unit_id": foreign_id}},
    )
    await request(
        ctx,
        "POST",
        "/sources/google-sheets",
        expected=404,
        data={**base, "access_metadata": {**metadata, "data_owner_user_id": outsider_id}},
    )
    await request(
        ctx,
        "POST",
        "/sources/google-sheets",
        expected=403,
        data={**base, "access_metadata": {**metadata, "owner_unit_id": unassigned_id}},
    )
    await request(ctx, "PATCH", f"/users/{viewer_id}", data={"is_active": False})
    await request(
        ctx,
        "POST",
        "/sources/google-sheets",
        expected=422,
        data={**base, "access_metadata": {**metadata, "data_steward_user_id": viewer_id}},
    )
    created = await request(
        ctx,
        "POST",
        "/sources/google-sheets",
        expected=202,
        data={**base, "access_metadata": metadata},
    )
    source = (await request(ctx, "GET", f"/sources/{created['data']['source']['id']}"))["data"]
    assert source["source_code"] == "scoped_source"
    assert source["access_status"] == "ACCESS_POLICY_REQUIRED"
    assert source["access_metadata"] == metadata
    repeated = await request(
        ctx,
        "POST",
        "/sources/google-sheets",
        expected=202,
        data={
            **base,
            "spreadsheet_url": "https://docs.google.com/spreadsheets/d/fake_sheet_12345/edit?gid=1",
            "access_metadata": metadata,
        },
    )
    assert repeated["data"]["already_registered"] is True
    assert repeated["data"]["source"]["id"] == source["id"]
    assert repeated["data"]["job_id"] == created["data"]["job_id"]
    assert repeated["data"]["duplicate_source_ids"] == []
    async with SessionFactory() as session:
        source_count = await session.scalar(
            select(func.count()).select_from(DataSource).where(
                DataSource.tenant_id == ctx.tenant_id,
                DataSource.spreadsheet_id == "fake_sheet_12345",
            )
        )
        job_count = await session.scalar(
            select(func.count()).select_from(Job).where(Job.source_id == source["id"])
        )
    assert source_count == 1
    assert job_count == 1
    duplicate_name = await request(
        ctx,
        "POST",
        "/sources/google-sheets",
        expected=202,
        data={**base, "spreadsheet_url": "fake_sheet_67890", "access_metadata": metadata},
    )
    assert duplicate_name["data"]["source"]["source_code"] == "scoped_source_2"
    concurrent = await asyncio.gather(*[
        request(
            ctx,
            "POST",
            "/sources/google-sheets",
            expected=202,
            data={**base, "spreadsheet_url": "fake_sheet_concurrent", "access_metadata": metadata},
        )
        for _ in range(2)
    ])
    assert len({item["data"]["source"]["id"] for item in concurrent}) == 1
    assert len({item["data"]["job_id"] for item in concurrent}) == 1
    assert sorted(item["data"]["already_registered"] for item in concurrent) == [False, True]
    admin_id = decode_token(ctx.tokens["admin"]["access_token"])["sub"]
    async with SessionFactory() as session, session.begin():
        legacy_duplicate = DataSource(
            tenant_id=ctx.tenant_id,
            source_code="legacy_duplicate",
            name="Legacy duplicate",
            spreadsheet_id="fake_sheet_12345",
            owner_user_id=admin_id,
            credential_ref="default",
            access_metadata=metadata,
        )
        session.add(legacy_duplicate)
        await session.flush()
        legacy_duplicate_id = legacy_duplicate.id
    groups = (await request(ctx, "GET", "/sources/duplicate-groups"))["data"]
    group = next(item for item in groups if item["spreadsheet_id"] == "fake_sheet_12345")
    assert group["same_owner"] is True
    assert group["suggested_source_id"] == source["id"]
    assert {item["id"] for item in group["sources"]} == {source["id"], legacy_duplicate_id}
    assert (await request(ctx, "GET", "/sources/duplicate-groups", who="outsider"))["data"] == []
    repeated_with_legacy = await request(
        ctx,
        "POST",
        "/sources/google-sheets",
        expected=202,
        data={**base, "access_metadata": metadata},
    )
    assert repeated_with_legacy["data"]["source"]["id"] == source["id"]
    assert repeated_with_legacy["data"]["duplicate_source_ids"] == [legacy_duplicate_id]
    async with SessionFactory() as session, session.begin():
        session.add(DataSource(
            tenant_id=ctx.tenant_id,
            source_code="other_owner_source",
            name="Other owner's source",
            spreadsheet_id="fake_sheet_other_owner",
            owner_user_id=viewer_id,
            credential_ref="default",
            access_metadata=metadata,
        ))
    blocked_other_owner = await request(
        ctx,
        "POST",
        "/sources/google-sheets",
        expected=409,
        data={**base, "spreadsheet_url": "fake_sheet_other_owner", "access_metadata": metadata},
    )
    assert blocked_other_owner["errors"][0]["code"] == "SOURCE_ALREADY_REGISTERED"
    async with SessionFactory() as session, session.begin():
        await session.execute(
            update(UserAssignment)
            .where(
                UserAssignment.tenant_id == ctx.tenant_id,
                UserAssignment.attribute_id == metadata["owner_unit_id"],
            )
            .values(status="REVOKED")
        )
    options_after_revoke = (await request(ctx, "GET", "/access/registration-options"))["data"]
    assert metadata["owner_unit_id"] not in {item["id"] for item in options_after_revoke["scopes"]}
    await request(
        ctx,
        "POST",
        "/sources/google-sheets",
        expected=403,
        data={**base, "source_code": "scope_after_revoke", "access_metadata": metadata},
    )


async def test_legacy_source_access_metadata_update(context):
    ctx = context
    metadata = await source_access_metadata(ctx)
    async with SessionFactory() as session, session.begin():
        admin_id = await session.scalar(
            select(User.id).where(User.tenant_id == ctx.tenant_id, User.username == "admin")
        )
        legacy = DataSource(
            tenant_id=ctx.tenant_id,
            source_code="legacy_access",
            name="Legacy access",
            spreadsheet_id="legacy_sheet",
            owner_user_id=admin_id,
            status="ACTIVE",
        )
        session.add(legacy)
        await session.flush()
        source_id = legacy.id
    path = f"/sources/{source_id}/access-metadata"
    before = (await request(ctx, "GET", f"/sources/{source_id}"))["data"]
    assert before["access_metadata"] is None and before["access_revision"] == 1
    assert before["access_review_status"] == "PENDING"
    await request(
        ctx, "PATCH", path, who="viewer", expected=403, data={"revision_no": 1, "access_metadata": metadata}
    )
    await request(
        ctx, "PATCH", path, who="outsider", expected=404, data={"revision_no": 1, "access_metadata": metadata}
    )
    await request(
        ctx,
        "PATCH",
        path,
        expected=422,
        data={"revision_no": 1, "access_metadata": {**metadata, "purpose_id": metadata["owner_unit_id"]}},
    )
    result = (await request(ctx, "PATCH", path, data={"revision_no": 1, "access_metadata": metadata}))["data"]
    assert result["access_metadata"] == metadata
    assert result["access_revision"] == 2
    assert result["access_status"] == "ACCESS_POLICY_REQUIRED"
    assert result["access_metadata_editor_id"] == admin_id
    assert result["access_review_status"] == "PENDING"
    assert result["status"] == "ACTIVE"
    repeated = (await request(ctx, "PATCH", path, data={"revision_no": 2, "access_metadata": metadata}))[
        "data"
    ]
    assert repeated["access_revision"] == 2
    await request(ctx, "PATCH", path, expected=409, data={"revision_no": 1, "access_metadata": metadata})
    async with SessionFactory() as session, session.begin():
        await session.execute(
            update(DataSource).where(DataSource.id == source_id).values(access_status="POLICY_APPROVED")
        )
    corrected = (
        await request(
            ctx,
            "PATCH",
            path,
            data={"revision_no": 2, "access_metadata": {**metadata, "sensitivity": "HIGH"}},
        )
    )["data"]
    assert corrected["access_revision"] == 3
    assert corrected["access_status"] == "ACCESS_POLICY_REQUIRED"
    assert corrected["access_metadata"]["sensitivity"] == "HIGH"
    async with SessionFactory() as session:
        events = (
            await session.scalars(
                select(AuditEvent)
                .where(
                    AuditEvent.tenant_id == ctx.tenant_id,
                    AuditEvent.resource_id == source_id,
                    AuditEvent.event == "source.access_metadata_updated",
                )
                .order_by(AuditEvent.created_at)
            )
        ).all()
    assert len(events) == 2
    assert events[0].user_id == admin_id
    assert set(events[0].details["changed_fields"]) == set(metadata)
    assert events[1].details["changed_fields"] == ["sensitivity"]
    assert metadata["data_owner_user_id"] not in str(events[0].details)


async def test_source_metadata_review_separates_editor_and_reviewer(context):
    ctx = context
    metadata = await source_access_metadata(ctx)
    async with SessionFactory() as session, session.begin():
        admin_id = await session.scalar(
            select(User.id).where(User.tenant_id == ctx.tenant_id, User.username == "admin")
        )
        source = DataSource(
            tenant_id=ctx.tenant_id,
            source_code="review_metadata",
            name="Review metadata",
            spreadsheet_id="review_sheet",
            owner_user_id=admin_id,
        )
        session.add(source)
        await session.flush()
        source_id = source.id
    path = f"/sources/{source_id}/access-review"
    await request(
        ctx,
        "POST",
        path,
        expected=409,
        data={"revision_no": 1, "decision": "APPROVE", "reason": "METADATA_VERIFIED"},
    )
    await request(
        ctx,
        "POST",
        path,
        who="outsider",
        expected=404,
        data={"revision_no": 1, "decision": "APPROVE", "reason": "METADATA_VERIFIED"},
    )
    await request(
        ctx,
        "POST",
        path,
        who="viewer",
        expected=403,
        data={"revision_no": 1, "decision": "APPROVE", "reason": "METADATA_VERIFIED"},
    )
    edited = (
        await request(
            ctx,
            "PATCH",
            f"/sources/{source_id}/access-metadata",
            data={"revision_no": 1, "access_metadata": metadata},
        )
    )["data"]
    assert edited["access_revision"] == 2 and edited["access_metadata_editor_id"] == admin_id
    await request(
        ctx,
        "POST",
        path,
        expected=422,
        data={"revision_no": 2, "decision": "APPROVE", "reason": "SCOPE_MISMATCH"},
    )
    await request(
        ctx,
        "POST",
        path,
        expected=403,
        data={"revision_no": 2, "decision": "APPROVE", "reason": "METADATA_VERIFIED"},
    )
    reviewer = (
        await request(
            ctx,
            "POST",
            "/users",
            expected=201,
            data={"username": "metadata_reviewer", "password": "test-password-456", "role": "PLATFORM_ADMIN"},
        )
    )["data"]
    login_response = await ctx.client.post(
        "/api/v1/auth/login",
        json={
            "tenant_code": ctx.tenant_code,
            "username": "metadata_reviewer",
            "password": "test-password-456",
        },
    )
    assert login_response.status_code == 200, login_response.text
    ctx.headers["reviewer"] = {"Authorization": "Bearer " + login_response.json()["data"]["access_token"]}
    await request(ctx, "GET", f"/sources/{source_id}/access-review-context", who="outsider", expected=404)
    await request(ctx, "GET", f"/sources/{source_id}/access-review-context", who="viewer", expected=403)
    review_context = (
        await request(ctx, "GET", f"/sources/{source_id}/access-review-context", who="reviewer")
    )["data"]
    assert review_context["access_revision"] == 2
    assert review_context["attributes"]["owner_unit_id"]["is_active"] is True
    assert review_context["people"]["data_owner_user_id"]["username"] == "admin"
    assert review_context["sensitivity"] == "LOW"
    approved = (
        await request(
            ctx,
            "POST",
            path,
            who="reviewer",
            data={"revision_no": 2, "decision": "APPROVE", "reason": "METADATA_VERIFIED"},
        )
    )["data"]
    assert approved["access_review_status"] == "APPROVED"
    assert approved["access_reviewed_by"] == reviewer["id"]
    assert approved["access_review_reason"] == "METADATA_VERIFIED"
    assert approved["access_reviewed_at"] is not None
    assert approved["access_revision"] == 3
    assert approved["access_status"] == "ACCESS_POLICY_REQUIRED"
    await request(
        ctx,
        "POST",
        path,
        who="reviewer",
        expected=409,
        data={"revision_no": 3, "decision": "APPROVE", "reason": "METADATA_VERIFIED"},
    )
    updated = (
        await request(
            ctx,
            "PATCH",
            f"/sources/{source_id}/access-metadata",
            data={"revision_no": 3, "access_metadata": {**metadata, "sensitivity": "HIGH"}},
        )
    )["data"]
    assert updated["access_review_status"] == "PENDING"
    assert updated["access_reviewed_by"] is None and updated["access_reviewed_at"] is None
    assert updated["access_revision"] == 4
    await request(
        ctx,
        "POST",
        path,
        who="reviewer",
        expected=409,
        data={"revision_no": 3, "decision": "REJECT", "reason": "SCOPE_MISMATCH"},
    )
    async with SessionFactory() as session, session.begin():
        await session.execute(
            update(UserAssignment)
            .where(
                UserAssignment.tenant_id == ctx.tenant_id,
                UserAssignment.attribute_id == metadata["owner_unit_id"],
            )
            .values(status="REVOKED")
        )
    await request(
        ctx,
        "POST",
        path,
        who="reviewer",
        expected=403,
        data={"revision_no": 4, "decision": "APPROVE", "reason": "METADATA_VERIFIED"},
    )
    rejected = (
        await request(
            ctx,
            "POST",
            path,
            who="reviewer",
            data={"revision_no": 4, "decision": "REJECT", "reason": "SCOPE_MISMATCH"},
        )
    )["data"]
    assert rejected["access_review_status"] == "REJECTED"
    assert rejected["access_status"] == "ACCESS_POLICY_REQUIRED"
    async with SessionFactory() as session, session.begin():
        await session.execute(
            update(UserAssignment)
            .where(
                UserAssignment.tenant_id == ctx.tenant_id,
                UserAssignment.attribute_id == metadata["owner_unit_id"],
            )
            .values(status="ACTIVE")
        )
    reopened = (
        await request(
            ctx,
            "PATCH",
            f"/sources/{source_id}/access-metadata",
            data={"revision_no": 5, "access_metadata": {**metadata, "sensitivity": "HIGH"}},
        )
    )["data"]
    assert reopened["access_review_status"] == "PENDING" and reopened["access_revision"] == 6
    async with SessionFactory() as session:
        events = (
            await session.scalars(
                select(AuditEvent)
                .where(
                    AuditEvent.tenant_id == ctx.tenant_id,
                    AuditEvent.resource_id == source_id,
                    AuditEvent.event == "source.access_metadata_reviewed",
                )
                .order_by(AuditEvent.created_at)
            )
        ).all()
    assert len(events) == 2
    assert all(event.user_id == reviewer["id"] for event in events)
    assert [event.details["reason_code"] for event in events] == ["METADATA_VERIFIED", "SCOPE_MISMATCH"]
    assert metadata["data_owner_user_id"] not in str([event.details for event in events])


async def test_pending_source_product_blocks_direct_reads(context):
    from app.core.exceptions import AppError
    from app.schemas.semantic import QueryPlan
    from app.services.query_execution_service import QueryExecutionService

    ctx = context
    metadata = await source_access_metadata(ctx)
    async with SessionFactory() as session, session.begin():
        admin_id = await session.scalar(
            select(User.id).where(User.tenant_id == ctx.tenant_id, User.username == "admin")
        )
        source = DataSource(
            tenant_id=ctx.tenant_id,
            source_code="be16_pending",
            name="Pending source",
            spreadsheet_id="pending_sheet",
            owner_user_id=admin_id,
            access_metadata=metadata,
            access_metadata_editor_id=admin_id,
        )
        session.add(source)
        await session.flush()
        sheet = SourceSheet(tenant_id=ctx.tenant_id, source_id=source.id, sheet_id=1, sheet_name="Pending")
        session.add(sheet)
        await session.flush()
        session.add(
            DataProduct(
                tenant_id=ctx.tenant_id,
                source_sheet_id=sheet.id,
                code="BE16_PENDING",
                name="Pending product",
                view_name="v_be16_pending",
                columns=[{"target_column": "region_code", "target_type": "text"}],
                dimensions=["region_code"],
                metrics=[],
                allowed_roles=["PLATFORM_ADMIN", "VIEWER"],
            )
        )
        legacy_source = DataSource(
            tenant_id=ctx.tenant_id,
            source_code="be16_legacy_join",
            name="Legacy join source",
            spreadsheet_id="legacy_join_sheet",
            owner_user_id=admin_id,
        )
        session.add(legacy_source)
        await session.flush()
        legacy_sheet = SourceSheet(
            tenant_id=ctx.tenant_id, source_id=legacy_source.id, sheet_id=2, sheet_name="Legacy join"
        )
        session.add(legacy_sheet)
        await session.flush()
        session.add(
            DataProduct(
                tenant_id=ctx.tenant_id,
                source_sheet_id=legacy_sheet.id,
                code="BE16_LEGACY",
                name="Legacy join product",
                view_name="v_be16_legacy",
                columns=[{"target_column": "region_code", "target_type": "text"}],
                dimensions=["region_code"],
                metrics=[],
                allowed_roles=["PLATFORM_ADMIN", "VIEWER"],
            )
        )
        session.add(
            JoinRelationship(
                tenant_id=ctx.tenant_id,
                code="legacy_to_pending",
                left_product_code="BE16_LEGACY",
                left_column="region_code",
                right_product_code="BE16_PENDING",
                right_column="region_code",
                cardinality="MANY_TO_ONE",
                join_type="LEFT",
                duplicate_policy="REJECT_AMBIGUOUS",
                status="APPROVED",
                created_by=admin_id,
            )
        )
        for suffix in ("A", "B"):
            session.add(
                SavedQuery(
                    tenant_id=ctx.tenant_id,
                    code=f"PENDING_{suffix}",
                    data_product_code="BE16_PENDING",
                    plan={"dimensions": ["region_code"]},
                    examples=["pending report"],
                    allowed_roles=["VIEWER"],
                    semantic_version=1,
                    status="ACTIVE",
                    created_by=admin_id,
                )
            )
    assert not any(
        item["code"] == "BE16_PENDING" for item in (await request(ctx, "GET", "/data-products"))["data"]
    )
    assert not any(
        item["code"] == "BE16_PENDING"
        for item in (await request(ctx, "GET", "/semantic/data-products"))["data"]
    )
    assert (await request(ctx, "GET", "/semantic/metrics"))["data"] == []
    assert (await request(ctx, "GET", "/semantic/join-relationships"))["data"] == []
    assert (await request(ctx, "GET", "/semantic/query-templates", who="viewer"))["data"] == []
    await request(ctx, "GET", "/data-products/BE16_PENDING", expected=404)
    await request(ctx, "GET", "/data-products/BE16_PENDING/dimensions", expected=404)
    await request(ctx, "GET", "/data-products/BE16_PENDING/metrics", expected=404)
    await request(
        ctx,
        "POST",
        "/data-products/BE16_PENDING/query",
        who="viewer",
        expected=404,
        data={"dimensions": ["region_code"]},
    )
    await request(
        ctx,
        "POST",
        "/data-products/BE16_PENDING/export",
        who="viewer",
        expected=404,
        data={"dimensions": ["region_code"]},
    )
    await request(ctx, "POST", "/saved-queries/PENDING_A/run", who="viewer", expected=404)
    await request(
        ctx,
        "POST",
        "/nl2sql/query",
        who="viewer",
        expected=404,
        data={"question": "Pending report?", "data_product_code": "BE16_PENDING"},
    )
    async with SessionFactory() as session:
        viewer = await session.scalar(
            select(User).where(User.tenant_id == ctx.tenant_id, User.username == "viewer")
        )
        with pytest.raises(AppError) as denied_join:
            await QueryExecutionService(session, viewer).compile(
                "BE16_LEGACY",
                QueryPlan(join_relationships=["legacy_to_pending"], dimensions=["BE16_PENDING.region_code"]),
            )
        assert denied_join.value.code == "DATA_PRODUCT_NOT_FOUND"


async def test_source_activation_requires_live_subject_policy(context):
    from app.core.exceptions import AppError
    from app.schemas.semantic import QueryPlan
    from app.services.query_execution_service import QueryExecutionService

    ctx = context
    metadata = await source_access_metadata(ctx)
    async with SessionFactory() as session, session.begin():
        admin_id = await session.scalar(
            select(User.id).where(User.tenant_id == ctx.tenant_id, User.username == "admin")
        )
        viewer_id = await session.scalar(
            select(User.id).where(User.tenant_id == ctx.tenant_id, User.username == "viewer")
        )
        source = DataSource(
            tenant_id=ctx.tenant_id,
            source_code="reviewed_source",
            name="Reviewed source",
            spreadsheet_id="reviewed_sheet",
            owner_user_id=admin_id,
            access_metadata=metadata,
            access_metadata_editor_id=admin_id,
        )
        session.add(source)
        await session.flush()
        source_id = source.id
        sheet = SourceSheet(tenant_id=ctx.tenant_id, source_id=source_id, sheet_id=1, sheet_name="Reviewed")
        session.add(sheet)
        await session.flush()
        session.add(
            DataProduct(
                tenant_id=ctx.tenant_id,
                source_sheet_id=sheet.id,
                code="BE16_REVIEWED",
                name="Reviewed product",
                view_name="v_be16_reviewed",
                columns=[{"target_column": "region_code", "target_type": "text"}],
                dimensions=["region_code"],
                metrics=[],
                allowed_roles=["PLATFORM_ADMIN", "VIEWER"],
            )
        )
    path = f"/sources/{source_id}/access-activate"
    await request(ctx, "POST", path, expected=409, data={"revision_no": 1, "policy_id": str(uuid4())})
    await request(ctx, "GET", "/data-products/BE16_REVIEWED", who="viewer", expected=404)
    reviewer = (
        await request(
            ctx,
            "POST",
            "/users",
            expected=201,
            data={
                "username": "source_policy_reviewer",
                "password": "test-password-456",
                "role": "PLATFORM_ADMIN",
            },
        )
    )["data"]
    login_response = await ctx.client.post(
        "/api/v1/auth/login",
        json={
            "tenant_code": ctx.tenant_code,
            "username": "source_policy_reviewer",
            "password": "test-password-456",
        },
    )
    assert login_response.status_code == 200, login_response.text
    ctx.headers["source_reviewer"] = {
        "Authorization": "Bearer " + login_response.json()["data"]["access_token"]
    }
    metadata_review = (
        await request(
            ctx,
            "POST",
            f"/sources/{source_id}/access-review",
            who="source_reviewer",
            data={"revision_no": 1, "decision": "APPROVE", "reason": "METADATA_VERIFIED"},
        )
    )["data"]
    assert metadata_review["access_status"] == "ACCESS_POLICY_REQUIRED"
    broad = (
        await request(
            ctx,
            "POST",
            "/access/policies",
            expected=201,
            data={
                "code": "reviewed_source_broad",
                "label": "Reviewed broad",
                "effect": "ALLOW",
                "actions": ["DISCOVER", "QUERY"],
                "required_attribute_ids": [],
            },
        )
    )["data"]
    await request(
        ctx,
        "POST",
        f"/access/policies/{broad['id']}/bindings",
        expected=201,
        data={"resource_type": "SOURCE", "resource_id": "reviewed_source"},
    )
    broad_submitted = (
        await request(
            ctx,
            "POST",
            f"/access/policies/{broad['id']}/submit",
            data={"revision": 2, "note": "Broad scope"},
        )
    )["data"]
    await request(
        ctx,
        "POST",
        f"/access/policies/{broad['id']}/approve",
        who="source_reviewer",
        data={"revision": broad_submitted["revision"], "note": "Broad approved"},
    )
    assert (await request(ctx, "GET", f"/sources/{source_id}/access-policy-options", who="source_reviewer"))[
        "data"
    ] == []
    await request(
        ctx,
        "POST",
        path,
        who="source_reviewer",
        expected=422,
        data={"revision_no": 2, "policy_id": broad["id"]},
    )
    policy = (
        await request(
            ctx,
            "POST",
            "/access/policies",
            expected=201,
            data={
                "code": "reviewed_source_allow",
                "label": "Reviewed source allow",
                "effect": "ALLOW",
                "actions": ["DISCOVER", "QUERY", "EXPORT"],
                "required_attribute_ids": [
                    metadata["owner_unit_id"],
                    metadata["business_domain_id"],
                    metadata["jurisdiction_id"],
                ],
            },
        )
    )["data"]
    await request(
        ctx,
        "POST",
        path,
        who="source_reviewer",
        expected=409,
        data={"revision_no": 2, "policy_id": policy["id"]},
    )
    await request(
        ctx,
        "POST",
        f"/access/policies/{policy['id']}/bindings",
        expected=201,
        data={"resource_type": "SOURCE", "resource_id": "reviewed_source"},
    )
    submitted = (
        await request(
            ctx,
            "POST",
            f"/access/policies/{policy['id']}/submit",
            data={"revision": 2, "note": "Review source"},
        )
    )["data"]
    approved_policy = (
        await request(
            ctx,
            "POST",
            f"/access/policies/{policy['id']}/approve",
            who="source_reviewer",
            data={"revision": submitted["revision"], "note": "Approved source"},
        )
    )["data"]
    await request(ctx, "GET", f"/sources/{source_id}/access-policy-options", who="viewer", expected=403)
    await request(ctx, "GET", f"/sources/{source_id}/access-policy-options", who="outsider", expected=404)
    options = (
        await request(ctx, "GET", f"/sources/{source_id}/access-policy-options", who="source_reviewer")
    )["data"]
    assert [item["id"] for item in options] == [policy["id"]]
    await request(ctx, "POST", path, expected=403, data={"revision_no": 2, "policy_id": policy["id"]})
    await request(
        ctx, "POST", path, who="viewer", expected=403, data={"revision_no": 2, "policy_id": policy["id"]}
    )
    activated = (
        await request(
            ctx,
            "POST",
            path,
            who="source_reviewer",
            data={"revision_no": 2, "policy_id": policy["id"]},
        )
    )["data"]
    assert activated["access_revision"] == 3
    assert activated["access_status"] == "POLICY_APPROVED"
    assert activated["access_review_status"] == "APPROVED"
    await request(ctx, "GET", "/data-products/BE16_REVIEWED", who="viewer", expected=404)
    async with SessionFactory() as session, session.begin():
        for field in ("owner_unit_id", "business_domain_id", "jurisdiction_id"):
            session.add(
                UserAssignment(
                    tenant_id=ctx.tenant_id,
                    user_id=viewer_id,
                    attribute_id=metadata[field],
                    granted_by=admin_id,
                    valid_from=datetime.now(timezone.utc) - timedelta(days=1),
                )
            )
    product = (await request(ctx, "GET", "/data-products/BE16_REVIEWED", who="viewer"))["data"]
    assert product["code"] == "BE16_REVIEWED"
    assert any(
        item["code"] == "BE16_REVIEWED"
        for item in (await request(ctx, "GET", "/data-products", who="viewer"))["data"]
    )
    async with SessionFactory() as session:
        viewer = await session.scalar(select(User).where(User.id == viewer_id))
        admin = await session.scalar(select(User).where(User.id == admin_id))
        plan = QueryPlan(dimensions=["region_code"])
        compiled = await QueryExecutionService(session, viewer).compile("BE16_REVIEWED", plan)
        assert compiled[0].code == "BE16_REVIEWED"
        with pytest.raises(AppError) as denied_export:
            await QueryExecutionService(session, viewer).compile("BE16_REVIEWED", plan, action="EXPORT")
        assert denied_export.value.code == "DATA_PRODUCT_NOT_FOUND"
        with pytest.raises(AppError) as admin_export:
            await QueryExecutionService(session, admin).compile("BE16_REVIEWED", plan, action="EXPORT")
        assert admin_export.value.code == "DATA_PRODUCT_NOT_FOUND"
    deny = (
        await request(
            ctx,
            "POST",
            "/access/policies",
            expected=201,
            data={
                "code": "reviewed_source_deny",
                "label": "Reviewed deny",
                "effect": "DENY",
                "actions": ["DISCOVER", "QUERY"],
                "required_attribute_ids": [metadata["owner_unit_id"]],
            },
        )
    )["data"]
    await request(
        ctx,
        "POST",
        f"/access/policies/{deny['id']}/bindings",
        expected=201,
        data={"resource_type": "SOURCE", "resource_id": "reviewed_source"},
    )
    deny_submitted = (
        await request(
            ctx,
            "POST",
            f"/access/policies/{deny['id']}/submit",
            data={"revision": 2, "note": "Deny source"},
        )
    )["data"]
    deny_approved = (
        await request(
            ctx,
            "POST",
            f"/access/policies/{deny['id']}/approve",
            who="source_reviewer",
            data={"revision": deny_submitted["revision"], "note": "Approved deny"},
        )
    )["data"]
    await request(ctx, "GET", "/data-products/BE16_REVIEWED", who="viewer", expected=404)
    await request(
        ctx,
        "POST",
        f"/access/policies/{deny['id']}/revoke",
        data={"revision": deny_approved["revision"], "note": "Deny ended"},
    )
    await request(ctx, "GET", "/data-products/BE16_REVIEWED", who="viewer")
    scoped = (
        await request(
            ctx,
            "POST",
            "/access/policies",
            expected=201,
            data={
                "code": "reviewed_source_scoped",
                "label": "Reviewed scoped",
                "effect": "ALLOW",
                "actions": ["DISCOVER", "QUERY"],
                "required_attribute_ids": [
                    metadata["owner_unit_id"],
                    metadata["business_domain_id"],
                    metadata["jurisdiction_id"],
                ],
                "row_scope": {"region_code": ["JATIM"]},
            },
        )
    )["data"]
    await request(
        ctx,
        "POST",
        f"/access/policies/{scoped['id']}/bindings",
        expected=201,
        data={"resource_type": "SOURCE", "resource_id": "reviewed_source"},
    )
    scoped_submitted = (
        await request(
            ctx,
            "POST",
            f"/access/policies/{scoped['id']}/submit",
            data={"revision": 2, "note": "Scoped source"},
        )
    )["data"]
    scoped_approved = (
        await request(
            ctx,
            "POST",
            f"/access/policies/{scoped['id']}/approve",
            who="source_reviewer",
            data={"revision": scoped_submitted["revision"], "note": "Approved scoped"},
        )
    )["data"]
    await request(ctx, "GET", "/data-products/BE16_REVIEWED", who="viewer", expected=404)
    await request(
        ctx,
        "POST",
        f"/access/policies/{scoped['id']}/revoke",
        data={"revision": scoped_approved["revision"], "note": "Scoped ended"},
    )
    await request(ctx, "GET", "/data-products/BE16_REVIEWED", who="viewer")
    await request(
        ctx,
        "POST",
        f"/access/policies/{policy['id']}/revoke",
        data={"revision": approved_policy["revision"], "note": "Revoke access"},
    )
    await request(ctx, "GET", "/data-products/BE16_REVIEWED", who="viewer", expected=404)
    await request(
        ctx,
        "POST",
        "/data-products/BE16_REVIEWED/export",
        who="viewer",
        expected=404,
        data={"dimensions": ["region_code"]},
    )
    assert reviewer["id"] == activated["access_reviewed_by"]


async def test_access_jurisdiction_lifecycle_and_tenant_scope(context):
    ctx = context
    users = (await request(ctx, "GET", "/users"))["data"]
    viewer_id = next(item["id"] for item in users if item["username"] == "viewer")
    admin_id = next(item["id"] for item in users if item["username"] == "admin")
    from app.core.security import decode_token

    outsider_id = decode_token(ctx.tokens["outsider"]["access_token"])["sub"]
    async with SessionFactory() as session, session.begin():
        outsider_tenant = await session.scalar(select(User.tenant_id).where(User.id == outsider_id))
        source = DataSource(
            tenant_id=ctx.tenant_id,
            source_code="finance_source",
            name="Finance source",
            spreadsheet_id="finance_sheet",
            owner_user_id=admin_id,
        )
        outside_source = DataSource(
            tenant_id=outsider_tenant,
            source_code="outside_source",
            name="Outside source",
            spreadsheet_id="outside_sheet",
            owner_user_id=outsider_id,
        )
        session.add_all([source, outside_source])
        await session.flush()
        for sheet_id, product_code in enumerate(("FINANCE_REPORT", "FINANCE_EXPORT"), start=1):
            sheet = SourceSheet(
                tenant_id=ctx.tenant_id,
                source_id=source.id,
                sheet_id=sheet_id,
                sheet_name=product_code,
            )
            session.add(sheet)
            await session.flush()
            session.add(
                DataProduct(
                    tenant_id=ctx.tenant_id,
                    source_sheet_id=sheet.id,
                    code=product_code,
                    name=product_code,
                    view_name=f"v_finance_{sheet_id}",
                    columns=[],
                    allowed_roles=["VIEWER"],
                )
            )
    products = (await request(ctx, "GET", "/access/resources?resource_type=DATA_PRODUCT&search=FINANCE"))[
        "data"
    ]
    assert {item["code"] for item in products} == {"FINANCE_REPORT", "FINANCE_EXPORT"}
    sources = (await request(ctx, "GET", "/access/resources?resource_type=SOURCE"))["data"]
    assert {item["code"] for item in sources} == {"finance_source"}
    await request(ctx, "GET", "/access/resources?resource_type=SOURCE", who="viewer", expected=403)
    department = (
        await request(
            ctx,
            "POST",
            "/access/attributes",
            expected=201,
            data={"kind": "DEPARTMENT", "code": "finance", "label": "Finance"},
        )
    )["data"]
    assert department["code"] == "FINANCE"
    child = (
        await request(
            ctx,
            "POST",
            "/access/attributes",
            expected=201,
            data={
                "kind": "DEPARTMENT",
                "code": "accounting",
                "label": "Accounting",
                "parent_id": department["id"],
            },
        )
    )["data"]
    await request(
        ctx,
        "PATCH",
        f"/access/attributes/{department['id']}",
        expected=422,
        data={"parent_id": child["id"], "revision": department["revision"]},
    )
    assert (await request(ctx, "GET", "/access/attributes", who="outsider"))["data"] == []
    await request(ctx, "GET", "/access/attributes", who="viewer", expected=403)

    assignment = (
        await request(
            ctx,
            "POST",
            f"/access/users/{viewer_id}/assignments",
            expected=201,
            data={
                "attribute_id": department["id"],
                "valid_from": "2026-01-01T00:00:00Z",
                "valid_to": "2027-01-01T00:00:00Z",
                "note": "Finance 2026",
            },
        )
    )["data"]
    await request(
        ctx,
        "POST",
        f"/access/users/{viewer_id}/assignments",
        expected=409,
        data={
            "attribute_id": department["id"],
            "valid_from": "2026-06-01T00:00:00Z",
            "valid_to": "2027-06-01T00:00:00Z",
        },
    )
    effective = (
        await request(
            ctx,
            "GET",
            f"/access/users/{viewer_id}/effective?at=2026-09-27T00:00:00Z",
        )
    )["data"]
    assert effective["dimensions"] == {"DEPARTMENT": ["FINANCE"]}
    assert effective["actions"] == ["DISCOVER", "QUERY", "READ"]
    own = (await request(ctx, "GET", "/access/me/effective", who="viewer"))["data"]
    assert own["user"]["username"] == "viewer"

    await request(
        ctx,
        "POST",
        f"/access/users/{admin_id}/assignments",
        expected=422,
        data={"attribute_id": department["id"]},
    )

    bundle = (
        await request(
            ctx,
            "POST",
            "/access/permission-bundles",
            expected=201,
            data={
                "code": "report_exporter",
                "label": "Report Exporter",
                "description": "Ekspor laporan terotorisasi",
                "actions": ["READ", "QUERY", "EXPORT"],
            },
        )
    )["data"]
    assert (await request(ctx, "GET", "/access/permission-bundles", who="outsider"))["data"] == []
    admin_id = next(item["id"] for item in users if item["username"] == "admin")
    await request(
        ctx,
        "POST",
        f"/access/users/{admin_id}/permission-grants",
        expected=422,
        data={"bundle_id": bundle["id"]},
    )
    grant = (
        await request(
            ctx,
            "POST",
            f"/access/users/{viewer_id}/permission-grants",
            expected=201,
            data={
                "bundle_id": bundle["id"],
                "valid_from": "2026-01-01T00:00:00Z",
                "valid_to": "2027-01-01T00:00:00Z",
            },
        )
    )["data"]
    effective = (
        await request(
            ctx,
            "GET",
            f"/access/users/{viewer_id}/effective?at=2026-09-27T00:00:00Z",
        )
    )["data"]
    assert effective["actions"] == ["DISCOVER", "EXPORT", "QUERY", "READ"]
    assert effective["permission_grants"][0]["bundle"]["code"] == "REPORT_EXPORTER"

    policy = (
        await request(
            ctx,
            "POST",
            "/access/policies",
            expected=201,
            data={
                "code": "finance_report_query",
                "label": "Finance report query",
                "effect": "ALLOW",
                "actions": ["QUERY", "EXPORT"],
                "required_attribute_ids": [department["id"]],
                "row_scope": {"region_code": ["JATIM"]},
                "column_rules": {"bank_account": "HIDDEN"},
                "export_allowed": False,
                "valid_from": "2026-01-01T00:00:00Z",
                "valid_to": "2027-01-01T00:00:00Z",
            },
        )
    )["data"]
    await request(
        ctx,
        "POST",
        f"/access/policies/{policy['id']}/bindings",
        expected=404,
        data={"resource_type": "DATA_PRODUCT", "resource_id": "MISSING_PRODUCT"},
    )
    await request(
        ctx,
        "POST",
        f"/access/policies/{policy['id']}/bindings",
        expected=404,
        data={"resource_type": "SOURCE", "resource_id": "outside_source"},
    )
    await request(
        ctx,
        "POST",
        f"/access/policies/{policy['id']}/bindings",
        expected=201,
        data={"resource_type": "DATA_PRODUCT", "resource_id": "FINANCE_REPORT"},
    )
    submitted = (
        await request(
            ctx,
            "POST",
            f"/access/policies/{policy['id']}/submit",
            data={"revision": 2, "note": "Ready for review"},
        )
    )["data"]
    await request(
        ctx,
        "POST",
        f"/access/policies/{policy['id']}/approve",
        expected=422,
        data={"revision": submitted["revision"], "note": "Self approval"},
    )
    await request(
        ctx,
        "POST",
        "/users",
        expected=201,
        data={
            "username": "policy_reviewer",
            "password": "test-password-456",
            "role": "PLATFORM_ADMIN",
        },
    )
    reviewer_login = await ctx.client.post(
        "/api/v1/auth/login",
        json={
            "tenant_code": ctx.tenant_code,
            "username": "policy_reviewer",
            "password": "test-password-456",
        },
    )
    assert reviewer_login.status_code == 200
    reviewer_headers = {"Authorization": "Bearer " + reviewer_login.json()["data"]["access_token"]}
    approved_response = await ctx.client.post(
        f"/api/v1/access/policies/{policy['id']}/approve",
        headers=reviewer_headers,
        json={"revision": submitted["revision"], "note": "Approved by separate admin"},
    )
    assert approved_response.status_code == 200, approved_response.text
    decision = (
        await request(
            ctx,
            "POST",
            "/access/evaluate",
            data={
                "user_id": viewer_id,
                "action": "QUERY",
                "resource_type": "DATA_PRODUCT",
                "resource_id": "FINANCE_REPORT",
                "at": "2026-09-27T00:00:00Z",
            },
        )
    )["data"]
    assert decision == {
        "allowed": True,
        "reason_code": "POLICY_MATCH",
        "policy_ids": [policy["id"]],
        "policy_revisions": [{"id": policy["id"], "revision": 4}],
        "row_scope": {"region_code": ["JATIM"]},
        "columns": {"bank_account": "HIDDEN"},
        "export_allowed": False,
    }
    export_decision = (
        await request(
            ctx,
            "POST",
            "/access/evaluate",
            data={
                "user_id": viewer_id,
                "action": "EXPORT",
                "resource_type": "DATA_PRODUCT",
                "resource_id": "FINANCE_REPORT",
                "at": "2026-09-27T00:00:00Z",
            },
        )
    )["data"]
    assert export_decision["allowed"] is False
    assert export_decision["reason_code"] == "EXPORT_NOT_ALLOWED"
    assert export_decision["export_allowed"] is False
    export_policy = (
        await request(
            ctx,
            "POST",
            "/access/policies",
            expected=201,
            data={
                "code": "finance_export",
                "label": "Finance export",
                "effect": "ALLOW",
                "actions": ["EXPORT"],
                "required_attribute_ids": [department["id"]],
                "export_allowed": True,
                "valid_from": "2026-01-01T00:00:00Z",
                "valid_to": "2027-01-01T00:00:00Z",
            },
        )
    )["data"]
    await request(
        ctx,
        "POST",
        f"/access/policies/{export_policy['id']}/bindings",
        expected=201,
        data={"resource_type": "DATA_PRODUCT", "resource_id": "FINANCE_EXPORT"},
    )
    export_submitted = (
        await request(
            ctx,
            "POST",
            f"/access/policies/{export_policy['id']}/submit",
            data={"revision": 2, "note": "Ready for review"},
        )
    )["data"]
    export_approval = await ctx.client.post(
        f"/api/v1/access/policies/{export_policy['id']}/approve",
        headers=reviewer_headers,
        json={"revision": export_submitted["revision"], "note": "Export reviewed"},
    )
    assert export_approval.status_code == 200, export_approval.text
    permitted_export = (
        await request(
            ctx,
            "POST",
            "/access/evaluate",
            data={
                "user_id": viewer_id,
                "action": "EXPORT",
                "resource_type": "DATA_PRODUCT",
                "resource_id": "FINANCE_EXPORT",
                "at": "2026-09-27T00:00:00Z",
            },
        )
    )["data"]
    assert permitted_export["allowed"] is True
    assert permitted_export["export_allowed"] is True
    default_denied = (
        await request(
            ctx,
            "POST",
            "/access/evaluate",
            data={
                "user_id": viewer_id,
                "action": "QUERY",
                "resource_type": "DATA_PRODUCT",
                "resource_id": "UNBOUND_REPORT",
            },
        )
    )["data"]
    assert default_denied["reason_code"] == "DEFAULT_DENY"

    deny_policy = (
        await request(
            ctx,
            "POST",
            "/access/policies",
            expected=201,
            data={
                "code": "finance_report_deny",
                "label": "Finance report explicit deny",
                "effect": "DENY",
                "actions": ["QUERY"],
                "required_attribute_ids": [department["id"]],
                "valid_from": "2026-01-01T00:00:00Z",
                "valid_to": "2027-01-01T00:00:00Z",
            },
        )
    )["data"]
    await request(
        ctx,
        "POST",
        f"/access/policies/{deny_policy['id']}/bindings",
        expected=201,
        data={"resource_type": "DATA_PRODUCT", "resource_id": "FINANCE_REPORT"},
    )
    deny_submitted = (
        await request(
            ctx,
            "POST",
            f"/access/policies/{deny_policy['id']}/submit",
            data={"revision": 2, "note": "Deny review"},
        )
    )["data"]
    deny_approved_response = await ctx.client.post(
        f"/api/v1/access/policies/{deny_policy['id']}/approve",
        headers=reviewer_headers,
        json={"revision": deny_submitted["revision"], "note": "Deny approved"},
    )
    assert deny_approved_response.status_code == 200, deny_approved_response.text
    denied = (
        await request(
            ctx,
            "POST",
            "/access/evaluate",
            data={
                "user_id": viewer_id,
                "action": "QUERY",
                "resource_type": "DATA_PRODUCT",
                "resource_id": "FINANCE_REPORT",
                "at": "2026-09-27T00:00:00Z",
            },
        )
    )["data"]
    assert denied["reason_code"] == "EXPLICIT_DENY"
    await request(
        ctx,
        "POST",
        f"/access/policies/{deny_policy['id']}/revoke",
        data={"revision": deny_approved_response.json()["data"]["revision"], "note": "Deny ended"},
    )

    permission_revoked = (
        await request(
            ctx,
            "POST",
            f"/access/permission-grants/{grant['id']}/revoke",
            data={"revision": grant["revision"], "note": "Periode tugas selesai"},
        )
    )["data"]
    assert permission_revoked["status"] == "REVOKED"

    revoked = (
        await request(
            ctx,
            "POST",
            f"/access/assignments/{assignment['id']}/revoke",
            data={"revision": assignment["revision"], "note": "Pindah unit"},
        )
    )["data"]
    assert revoked["status"] == "REVOKED"
    history = (await request(ctx, "GET", f"/access/users/{viewer_id}/assignments?include_inactive=true"))[
        "data"
    ]
    assert history[0]["revoked_by"] is not None
    await request(ctx, "PATCH", f"/users/{viewer_id}", data={"is_active": False})
    inactive = (await request(ctx, "GET", f"/access/users/{viewer_id}/effective"))["data"]
    assert inactive["actions"] == []
    assert inactive["assignments"] == []
    inactive_decision = (
        await request(
            ctx,
            "POST",
            "/access/evaluate",
            data={
                "user_id": viewer_id,
                "action": "QUERY",
                "resource_type": "DATA_PRODUCT",
                "resource_id": "FINANCE_REPORT",
            },
        )
    )["data"]
    assert inactive_decision["allowed"] is False
    assert inactive_decision["reason_code"] == "USER_INACTIVE"

    async with SessionFactory() as session, session.begin():
        self_assignment = UserAssignment(
            tenant_id=ctx.tenant_id,
            user_id=admin_id,
            attribute_id=department["id"],
            granted_by=admin_id,
            valid_from=datetime.now(timezone.utc) - timedelta(days=1),
        )
        session.add(self_assignment)
        await session.flush()
        self_assignment_id = self_assignment.id
        self_assignment_revision = self_assignment.revision
    await request(
        ctx,
        "POST",
        f"/access/assignments/{self_assignment_id}/revoke",
        expected=422,
        data={"revision": self_assignment_revision, "note": "Self revoke"},
    )


async def test_temporary_access_request_approval_and_revoke(context):
    ctx = context
    users = (await request(ctx, "GET", "/users"))["data"]
    viewer_id = next(item["id"] for item in users if item["username"] == "viewer")
    second_admin = (
        await request(
            ctx,
            "POST",
            "/users",
            expected=201,
            data={
                "username": "access_admin_2",
                "password": "test-password-456",
                "full_name": "Second Access Admin",
                "role": "PLATFORM_ADMIN",
            },
        )
    )["data"]
    login = await ctx.client.post(
        "/api/v1/auth/login",
        json={
            "tenant_code": ctx.tenant_code,
            "username": "access_admin_2",
            "password": "test-password-456",
        },
    )
    assert login.status_code == 200, login.text
    ctx.headers["admin2"] = {"Authorization": "Bearer " + login.json()["data"]["access_token"]}
    department = (
        await request(
            ctx,
            "POST",
            "/access/attributes",
            expected=201,
            data={"kind": "DEPARTMENT", "code": "temporary_finance", "label": "Temporary Finance"},
        )
    )["data"]
    bundle = (
        await request(
            ctx,
            "POST",
            "/access/permission-bundles",
            expected=201,
            data={
                "code": "temporary_export",
                "label": "Temporary Export",
                "actions": ["READ", "QUERY", "EXPORT"],
            },
        )
    )["data"]
    options = (await request(ctx, "GET", "/access/request-options", who="viewer"))["data"]
    assert department["id"] in {item["id"] for item in options["attributes"]}
    assert bundle["id"] in {item["id"] for item in options["permission_bundles"]}

    payload = {
        "request_type": "ATTRIBUTE",
        "attribute_id": department["id"],
        "valid_from": "2026-10-01T00:00:00Z",
        "valid_to": "2027-01-01T00:00:00Z",
        "business_reason": "Membutuhkan laporan finance untuk penutupan triwulan.",
    }
    access_request = (
        await request(ctx, "POST", "/access/requests", who="viewer", expected=201, data=payload)
    )["data"]
    assert access_request["status"] == "PENDING"
    await request(ctx, "POST", "/access/requests", who="viewer", expected=409, data=payload)
    mine = (await request(ctx, "GET", "/access/requests/mine", who="viewer"))["data"]
    assert [item["id"] for item in mine] == [access_request["id"]]
    pending = (await request(ctx, "GET", "/access/requests?status=PENDING"))["data"]
    assert access_request["id"] in {item["id"] for item in pending}
    assert (await request(ctx, "GET", "/access/requests", who="outsider"))["data"] == []
    await request(
        ctx,
        "POST",
        f"/access/requests/{access_request['id']}/approve",
        who="viewer",
        expected=403,
        data={"revision": 1},
    )
    approved = (
        await request(
            ctx,
            "POST",
            f"/access/requests/{access_request['id']}/approve",
            data={"revision": 1, "note": "Kebutuhan bisnis terverifikasi"},
        )
    )["data"]
    assert approved["status"] == "APPROVED"
    assert approved["assignment_id"]
    await request(
        ctx,
        "POST",
        f"/access/requests/{access_request['id']}/reject",
        expected=409,
        data={"revision": 1, "note": "stale"},
    )
    effective = (
        await request(
            ctx,
            "GET",
            f"/access/users/{viewer_id}/effective?at=2026-11-01T00:00:00Z",
        )
    )["data"]
    assert effective["dimensions"] == {"DEPARTMENT": ["TEMPORARY_FINANCE"]}

    bundle_request = (
        await request(
            ctx,
            "POST",
            "/access/requests",
            who="viewer",
            expected=201,
            data={
                "request_type": "PERMISSION_BUNDLE",
                "bundle_id": bundle["id"],
                "valid_from": "2026-10-01T00:00:00Z",
                "valid_to": "2027-01-01T00:00:00Z",
                "business_reason": "Membutuhkan ekspor sementara untuk audit triwulan.",
            },
        )
    )["data"]
    bundle_request = (
        await request(
            ctx,
            "POST",
            f"/access/requests/{bundle_request['id']}/approve",
            data={"revision": bundle_request["revision"], "note": "Disetujui untuk audit"},
        )
    )["data"]
    assert bundle_request["permission_grant_id"]
    revoked = (
        await request(
            ctx,
            "POST",
            f"/access/requests/{bundle_request['id']}/revoke",
            who="viewer",
            data={"revision": bundle_request["revision"], "note": "Audit telah selesai"},
        )
    )["data"]
    assert revoked["status"] == "REVOKED"

    delegated_attribute = (
        await request(
            ctx,
            "POST",
            "/access/attributes",
            expected=201,
            data={"kind": "JURISDICTION", "code": "delegated_jatim", "label": "Delegated Jatim"},
        )
    )["data"]
    delegated_payload = {
        "request_type": "ATTRIBUTE",
        "subject_user_id": viewer_id,
        "attribute_id": delegated_attribute["id"],
        "valid_from": "2026-10-01T00:00:00Z",
        "valid_to": "2027-01-01T00:00:00Z",
        "business_reason": "Delegasi akses wilayah untuk penugasan audit sementara.",
    }
    delegated = (await request(ctx, "POST", "/access/requests", expected=201, data=delegated_payload))["data"]
    assert delegated["requester"]["username"] == "admin"
    assert delegated["subject_user"]["username"] == "viewer"
    reviewer_notifications = (await request(ctx, "GET", "/notifications?limit=10", who="admin2"))["data"]
    delegated_notification = next(
        item for item in reviewer_notifications if item["resource_id"] == delegated["id"]
    )
    assert delegated_notification["kind"] == "ACCESS_REQUEST_PENDING"
    assert delegated_notification["recipient_user_id"] == second_admin["id"]
    requester_notifications = (await request(ctx, "GET", "/notifications?limit=10"))["data"]
    assert delegated["id"] not in {item["resource_id"] for item in requester_notifications}
    await request(
        ctx,
        "POST",
        f"/notifications/{delegated_notification['id']}/acknowledge",
        expected=404,
    )
    await request(
        ctx,
        "POST",
        f"/access/requests/{delegated['id']}/approve",
        expected=422,
        data={"revision": delegated["revision"]},
    )
    delegated = (
        await request(
            ctx,
            "POST",
            f"/access/requests/{delegated['id']}/approve",
            who="admin2",
            data={"revision": delegated["revision"], "note": "Delegasi diperiksa admin kedua"},
        )
    )["data"]
    assert delegated["status"] == "APPROVED"
    assert delegated["assignment_id"]
    assert delegated["id"] not in {
        item["resource_id"]
        for item in (await request(ctx, "GET", "/notifications?limit=10", who="admin2"))["data"]
    }

    await request(
        ctx,
        "POST",
        "/access/requests",
        who="approver",
        expected=403,
        data={**delegated_payload, "subject_user_id": second_admin["id"]},
    )


async def onboard(ctx, config_data, *, classify=True, legacy_source=True):
    metadata = await source_access_metadata(ctx)
    data = await request(
        ctx,
        "POST",
        "/sources/google-sheets",
        expected=202,
        data={
            "source_code": "sales_test",
            "name": "Sales Test",
            "spreadsheet_url": "fake_sheet_12345",
            "access_metadata": metadata,
        },
    )
    source_id = data["data"]["source"]["id"]
    if legacy_source:
        async with SessionFactory() as session, session.begin():
            await session.execute(
                update(DataSource)
                .where(DataSource.tenant_id == ctx.tenant_id, DataSource.id == source_id)
                .values(access_metadata=text("NULL"), access_metadata_editor_id=None)
            )
    await run_pending(ctx.tenant_id)
    job = await request(ctx, "GET", "/jobs/" + data["data"]["job_id"])
    assert job["data"]["status"] == "SUCCEEDED", job
    sheets = await request(ctx, "GET", f"/sources/{source_id}/sheets")
    sheet_id = sheets["data"][0]["id"]
    if classify:
        await request(
            ctx,
            "PUT",
            f"/source-sheets/{sheet_id}/classification",
            data={"revision_no": 1, "dataset_kind": "NON_MASTER"},
        )
    config = await request(
        ctx,
        "POST",
        "/configurations",
        expected=201,
        data={"source_sheet_id": sheet_id, "configuration": config_data},
    )
    return source_id, sheet_id, config["data"]


async def activate(ctx, config):
    validation = (await request(ctx, "POST", f"/configurations/{config['id']}/validate"))["data"]
    config = (
        await request(
            ctx,
            "POST",
            f"/configurations/{config['id']}/submit-review",
            data={
                "revision_no": config["revision_no"],
                "snapshot_hash": validation["snapshot_hash"],
                "reviewed_columns": [c["target_column"] for c in config["configuration_json"]["columns"]],
                "reviewed_sections": ["identity", "columns", "cleansing", "quality", "load", "semantic"],
            },
        )
    )["data"]
    await request(
        ctx,
        "POST",
        f"/configurations/{config['id']}/approve",
        who="approver",
        data={"revision_no": config["revision_no"]},
    )
    data = await request(ctx, "POST", f"/configurations/{config['id']}/deploy", who="approver", expected=202)
    await run_pending(ctx.tenant_id)
    job = await request(ctx, "GET", "/jobs/" + data["data"]["job_id"])
    assert job["data"]["status"] == "SUCCEEDED", job


async def sync(ctx, source_id):
    data = await request(ctx, "POST", f"/sources/{source_id}/sync", expected=202)
    await run_pending(ctx.tenant_id)
    return (await request(ctx, "GET", "/jobs/" + data["data"]["job_id"]))["data"]


async def test_workbook_preview_apply_review_evidence_and_tenant_isolation(context, config_data):
    ctx = context
    config_data["unresolved_questions"] = ["Apakah ID unik?"]
    _, _, config = await onboard(ctx, config_data)
    path = f"/configurations/{config['id']}"
    await request(ctx, "GET", path + "/review", who="outsider", expected=404)
    view = (await request(ctx, "GET", path + "/review"))["data"]
    assert view["validation"]["valid"] is False
    assert len(view["validation"]["row_previews"]) == 3
    config_data["unresolved_questions"] = []
    await request(ctx, "PATCH", path, expected=422, data={"revision_no": 1, "configuration": config_data})
    await request(ctx, "POST", path + "/approve", who="approver", expected=409, data={"revision_no": 1})
    artifact = (await request(ctx, "POST", path + "/export", expected=201, data={"format": "XLSX"}))["data"]
    response = await ctx.client.get(
        "/api/v1" + path + f"/artifacts/{artifact['id']}/download", headers=ctx.headers["admin"]
    )
    assert response.status_code == 200
    book = load_workbook(io.BytesIO(response.content))
    book["14 Review"]["B2"] = "Sales reviewed"
    book["14 Review"]["B10"] = "Ya, ID transaksi unik."
    book["14 Review"]["C10"] = "Selesai"
    stream = io.BytesIO()
    book.save(stream)
    upload = {"content_base64": base64.b64encode(stream.getvalue()).decode()}
    await request(ctx, "POST", path + "/workbook-preview", who="viewer", expected=403, data=upload)
    p = (await request(ctx, "POST", path + "/workbook-preview", data=upload))["data"]
    assert p["can_apply"] is True, p
    assert p["validation"]["valid"] is True
    unchanged = (await request(ctx, "GET", path))["data"]
    assert unchanged["revision_no"] == 1
    assert unchanged["configuration_json"]["dataset_business_name"] != "Sales reviewed"
    body = {key: p[key] for key in ("revision_no", "configuration", "question_answers", "preview_token")}
    tampered = {**body, "configuration": {**body["configuration"], "dataset_business_name": "Tampered"}}
    await request(ctx, "POST", path + "/workbook-apply", data=tampered, expected=409)
    updated = (await request(ctx, "POST", path + "/workbook-apply", data=body))["data"]
    assert updated["revision_no"] == 2
    assert updated["review_state"]["answers"]["Apakah ID unik?"]["answer"] == "Ya, ID transaksi unik."
    await request(ctx, "POST", path + "/workbook-apply", data=body, expected=409)
    await request(ctx, "POST", path + "/approve", who="approver", expected=409, data={"revision_no": 2})
    review = {
        "revision_no": 2,
        "snapshot_hash": p["validation"]["snapshot_hash"],
        "reviewed_columns": [c["target_column"] for c in updated["configuration_json"]["columns"]],
        "reviewed_sections": ["identity", "columns", "cleansing", "quality", "load", "semantic"],
    }
    await request(
        ctx, "POST", path + "/submit-review", data={**review, "reviewed_sections": []}, expected=422
    )
    await request(
        ctx, "POST", path + "/submit-review", data={**review, "snapshot_hash": "0" * 64}, expected=409
    )
    await request(ctx, "POST", path + "/submit-review", data=review)
    await request(ctx, "POST", path + "/approve", who="approver", data={"revision_no": 3})
    ctx.values[1][3] = 999
    queued = (await request(ctx, "POST", path + "/deploy", who="approver", expected=202))["data"]
    await run_pending(ctx.tenant_id)
    job = (await request(ctx, "GET", "/jobs/" + queued["job_id"]))["data"]
    assert job["status"] == "FAILED"
    assert job["error_code"] == "REVIEW_STALE"


async def test_end_to_end_etl_permissions_and_saved_query(context, config_data):
    ctx = context
    source_id, sheet_id, config = await onboard(ctx, config_data)
    await request(ctx, "GET", f"/sources/{source_id}", who="outsider", expected=404)
    await request(ctx, "GET", "/sources", who="viewer", expected=403)
    await request(
        ctx, "POST", f"/configurations/{config['id']}/approve", expected=403, data={"revision_no": 1}
    )
    await request(
        ctx,
        "PATCH",
        f"/configurations/{config['id']}",
        expected=409,
        data={"revision_no": 999, "configuration": config_data},
    )
    await activate(ctx, config)
    job = await sync(ctx, source_id)
    assert job["status"] == "SUCCEEDED", job
    assert job["result"]["runs"][0]["rows_loaded"] == 3
    job = await sync(ctx, source_id)
    assert job["result"]["runs"][0]["status"] == "SKIPPED_DUPLICATE"
    plan = {"metrics": ["net_sales"], "dimensions": ["branch_name"]}
    dashboard = await request(ctx, "POST", "/data-products/SALES/query", who="viewer", data=plan)
    assert dashboard["data"] == [{"branch_name": "Jakarta", "net_sales": 150}], dashboard
    all_data = await request(ctx, "POST", "/data-products/SALES/query", data=plan)
    assert len(all_data["data"]) == 2
    await request(ctx, "POST", "/data-products/SALES/query", who="outsider", data=plan, expected=404)
    report = await request(
        ctx, "GET", "/reports/sales/trend?start_date=2026-09-01&end_date=2026-09-30", who="viewer"
    )
    assert report["data"][0]["net_sales"] == 150
    await request(
        ctx,
        "PATCH",
        f"/configurations/{config['id']}",
        expected=409,
        data={"revision_no": 2, "configuration": config_data},
    )
    saved = await request(
        ctx,
        "POST",
        "/semantic/query-templates",
        expected=201,
        data={
            "code": "SALES_BRANCH",
            "data_product_code": "SALES",
            "plan": plan,
            "examples": ["penjualan per cabang"],
        },
    )
    tid = saved["data"]["id"]
    await request(ctx, "POST", f"/semantic/query-templates/{tid}/validate")
    await request(ctx, "POST", f"/semantic/query-templates/{tid}/activate")
    answer = await request(
        ctx, "POST", "/nl2sql/query", who="viewer", data={"question": "Penjualan per cabang?"}
    )
    assert answer["meta"]["route"] == "INTENT_TEMPLATE"
    assert answer["meta"]["openai_called"] is False
    assert answer["data"][0]["net_sales"] == 150
    await request(
        ctx,
        "POST",
        "/nl2sql/query",
        who="viewer",
        expected=503,
        data={"question": "Buat analisis penjualan baru"},
    )


async def test_refresh_rotation_logout_and_credentials(context):
    ctx = context
    refresh = ctx.tokens["viewer"]["refresh_token"]
    response = await ctx.client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert response.status_code == 200
    response = await ctx.client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert response.status_code == 401
    await request(ctx, "POST", "/auth/logout", who="viewer")
    await request(ctx, "GET", "/auth/me", who="viewer", expected=401)


async def test_drift_stops_trusted_updates(context, config_data):
    source_id, _, config = await onboard(context, config_data)
    await activate(context, config)
    assert (await sync(context, source_id))["status"] == "SUCCEEDED"
    context.values[0].append("Unknown Column")
    job = await sync(context, source_id)
    assert job["result"]["runs"][0]["status"] == "CHANGE_DETECTED"
    result = await request(context, "POST", "/data-products/SALES/query", data={"metrics": ["net_sales"]})
    assert result["data"][0]["net_sales"] == 350


async def test_full_refresh_rollback_and_artifact_tampering(context, config_data):
    config_data["load_strategy"] = "FULL_REFRESH"
    config_data["data_quality_rules"] = [{"column": "net_amount", "rule": "min", "value": 0}]
    source_id, _, config = await onboard(context, config_data)
    await activate(context, config)
    assert (await sync(context, source_id))["status"] == "SUCCEEDED"
    context.values[1][3] = -999
    job = await sync(context, source_id)
    assert job["status"] == "FAILED" and job["error_code"] == "DQ_STOP_BATCH", job
    result = await request(context, "POST", "/data-products/SALES/query", data={"metrics": ["net_sales"]})
    assert result["data"][0]["net_sales"] == 350
    from pathlib import Path

    async with SessionFactory() as session:
        artifact = await session.scalar(
            select(Artifact).where(
                Artifact.configuration_version_id == config["id"], Artifact.artifact_type == "RUNTIME_CONFIG"
            )
        )
        Path(artifact.storage_uri).write_text("tampered", encoding="utf-8")
    job = await sync(context, source_id)
    assert job["error_code"] == "ARTIFACT_HASH_MISMATCH"


async def test_configuration_clone_rollback_and_exports(context, config_data):
    ctx = context
    source_id, sheet_id, config = await onboard(ctx, config_data)
    await activate(ctx, config)
    assert (await sync(ctx, source_id))["status"] == "SUCCEEDED"
    clone = (await request(ctx, "POST", f"/configurations/{config['id']}/clone", expected=201))["data"]
    assert clone["version_no"] == 2 and clone["status"] == "NEEDS_REVIEW"
    await activate(ctx, clone)
    old = (await request(ctx, "GET", f"/configurations/{config['id']}"))["data"]
    assert old["status"] == "SUPERSEDED"
    rollback = await request(
        ctx, "POST", f"/configurations/{config['id']}/rollback", who="approver", expected=202
    )
    await run_pending(ctx.tenant_id)
    job = (await request(ctx, "GET", "/jobs/" + rollback["data"]["job_id"]))["data"]
    assert job["status"] == "SUCCEEDED", job
    active = await request(ctx, "GET", f"/source-sheets/{sheet_id}/configurations/active")
    assert active["data"]["id"] == config["id"]
    for fmt in ("JSON", "YAML", "XLSX"):
        artifact = (
            await request(
                ctx, "POST", f"/configurations/{config['id']}/export", expected=201, data={"format": fmt}
            )
        )["data"]
        response = await ctx.client.get(
            f"/api/v1/configurations/{config['id']}/artifacts/{artifact['id']}/download",
            headers=ctx.headers["admin"],
        )
        assert response.status_code == 200 and len(response.content) == artifact["file_size_bytes"]


async def test_failed_google_job_is_observable(context, monkeypatch):
    ctx = context
    from app.core.exceptions import AppError

    async def denied(self, spreadsheet_id):
        raise AppError("SOURCE_ACCESS_DENIED", "Service account cannot read this sheet.", 403)

    monkeypatch.setattr(GoogleSheetsService, "metadata", denied)
    metadata = await source_access_metadata(ctx)
    data = await request(
        context,
        "POST",
        "/sources/google-sheets",
        expected=202,
        data={
            "source_code": "unavailable",
            "name": "Missing access",
            "spreadsheet_url": "fake_sheet_12345",
            "access_metadata": metadata,
        },
    )
    await run_pending(ctx.tenant_id)
    job = (await request(context, "GET", "/jobs/" + data["data"]["job_id"]))["data"]
    assert job["status"] == "FAILED" and job["error_code"] == "SOURCE_ACCESS_DENIED"


async def test_database_rejects_cross_tenant_foreign_key(context):
    from sqlalchemy.exc import IntegrityError

    from app.core.security import decode_token
    from app.models.source import DataSource

    outsider_id = decode_token(context.tokens["outsider"]["access_token"])["sub"]
    async with SessionFactory() as session:
        source = DataSource(
            tenant_id=context.tenant_id,
            source_code="invalid_owner",
            name="Invalid",
            spreadsheet_id="fake_sheet_123",
            owner_user_id=outsider_id,
        )
        session.add(source)
        with pytest.raises(IntegrityError):
            await session.flush()
        await session.rollback()


async def test_classification_required_and_master_gate(context, config_data):
    ctx = context
    source_id, sheet_id, config = await onboard(ctx, config_data, classify=False)
    source = (await request(ctx, "GET", f"/sources/{source_id}"))["data"]
    assert source["status"] == "NEEDS_REVIEW"
    assert source["access_status"] == "ACCESS_POLICY_REQUIRED"
    assert source["access_revision"] == 1
    path = f"/source-sheets/{sheet_id}/classification"
    current = (await request(ctx, "GET", path))["data"]
    assert current["status"] == "CLASSIFICATION_REQUIRED"
    assert current["dataset_kind"] is None and current["confirmed_by"] is None
    assert current["revision_no"] == 1 and current["execution_ready"] is False
    await request(ctx, "GET", path, who="outsider", expected=404)
    await request(ctx, "GET", path, who="viewer", expected=403)
    body = {"revision_no": 1, "dataset_kind": "MASTER"}
    await request(ctx, "PUT", path, who="approver", expected=403, data=body)
    await request(ctx, "PUT", path, who="outsider", expected=404, data=body)
    await request(ctx, "PUT", path, expected=422, data={**body, "master_definition_id": str(uuid4())})
    # Profiling and draft dry-run remain available before classification.
    validation = (await request(ctx, "POST", f"/configurations/{config['id']}/validate"))["data"]
    assert validation["valid"] and not validation["ready_for_review"]
    submission = {
        "revision_no": 1,
        "snapshot_hash": validation["snapshot_hash"],
        "reviewed_columns": [c["target_column"] for c in config["configuration_json"]["columns"]],
        "reviewed_sections": ["identity", "columns", "cleansing", "quality", "load", "semantic"],
    }
    for suffix, data, who in [
        ("submit-review", submission, "admin"),
        ("approve", {"revision_no": 1}, "approver"),
    ]:
        error = await request(
            ctx, "POST", f"/configurations/{config['id']}/{suffix}", data=data, who=who, expected=409
        )
        assert error["errors"][0]["code"] == "CLASSIFICATION_REQUIRED"
    error = await request(ctx, "POST", f"/sources/{source_id}/sync", expected=409)
    assert error["errors"][0]["code"] == "CLASSIFICATION_REQUIRED"
    current = (await request(ctx, "PUT", path, data=body))["data"]
    assert current["status"] == "CONFIRMED" and current["revision_no"] == 2
    assert current["confirmed_by"] and current["confirmed_at"]
    assert current["blocking_reason"]["code"] == "MASTER_RUNTIME_PENDING"
    error = await request(
        ctx, "POST", f"/configurations/{config['id']}/submit-review", data=submission, expected=409
    )
    assert error["errors"][0]["code"] == "MASTER_RUNTIME_PENDING"
    await request(ctx, "PUT", path, expected=409, data={"revision_no": 1, "dataset_kind": "NON_MASTER"})
    same = (await request(ctx, "PUT", path, data={"revision_no": 2, "dataset_kind": "MASTER"}))["data"]
    assert same == current  # No duplicate revision/audit when there is no change.
    current = (await request(ctx, "PUT", path, data={"revision_no": 2, "dataset_kind": "NON_MASTER"}))["data"]
    assert current["execution_ready"] and current["revision_no"] == 3
    await activate(ctx, config)
    await request(ctx, "PUT", path, data={"revision_no": 3, "dataset_kind": "MASTER"}, expected=409)
    assert (await sync(ctx, source_id))["status"] == "SUCCEEDED"


async def test_classification_changes_invalidate_submission_and_deployment(context, config_data):
    ctx = context
    source_id, sheet_id, config = await onboard(ctx, config_data)
    path = f"/configurations/{config['id']}"
    validation = (await request(ctx, "POST", path + "/validate"))["data"]
    body = {
        "revision_no": 1,
        "snapshot_hash": validation["snapshot_hash"],
        "reviewed_columns": [c["target_column"] for c in config["configuration_json"]["columns"]],
        "reviewed_sections": ["identity", "columns", "cleansing", "quality", "load", "semantic"],
    }
    submitted = (await request(ctx, "POST", path + "/submit-review", data=body))["data"]
    assert submitted["review_state"]["classification_revision"] == 2
    classification_path = f"/source-sheets/{sheet_id}/classification"
    for rev, kind in [(2, "MASTER"), (3, "NON_MASTER")]:
        await request(ctx, "PUT", classification_path, data={"revision_no": rev, "dataset_kind": kind})
    error = await request(
        ctx, "POST", path + "/approve", who="approver", expected=409, data={"revision_no": 2}
    )
    assert error["errors"][0]["code"] == "CLASSIFICATION_REVIEW_STALE"
    await request(ctx, "POST", path + "/submit-review", data={**body, "revision_no": 2})
    await request(ctx, "POST", path + "/approve", who="approver", data={"revision_no": 3})
    queued = (await request(ctx, "POST", path + "/deploy", who="approver", expected=202))["data"]
    await request(ctx, "PUT", classification_path, data={"revision_no": 4, "dataset_kind": "MASTER"})
    await run_pending(ctx.tenant_id)
    failed = (await request(ctx, "GET", "/jobs/" + queued["job_id"]))["data"]
    assert failed["status"] == "FAILED" and failed["error_code"] == "MASTER_RUNTIME_PENDING"
    await request(ctx, "PUT", classification_path, data={"revision_no": 5, "dataset_kind": "NON_MASTER"})
    error = await request(ctx, "POST", path + "/deploy", who="approver", expected=409)
    assert error["errors"][0]["code"] == "CLASSIFICATION_REVIEW_STALE"


async def test_mixed_tabs_and_worker_gate(context, config_data, monkeypatch):
    ctx = context
    source_id, first_id, config = await onboard(ctx, config_data)

    async def metadata(self, spreadsheet_id):
        return {
            "sheets": [
                {"properties": {"sheetId": 1, "title": "Sales"}},
                {"properties": {"sheetId": 2, "title": "Products"}},
            ]
        }

    monkeypatch.setattr(GoogleSheetsService, "metadata", metadata)
    await request(ctx, "POST", f"/sources/{source_id}/discover", expected=202)
    await run_pending(ctx.tenant_id)
    sheets = (await request(ctx, "GET", f"/sources/{source_id}/sheets"))["data"]
    first = next(s for s in sheets if s["id"] == first_id)
    second = next(s for s in sheets if s["id"] != first_id)
    assert first["dataset_kind"] == "NON_MASTER" and first["classification_revision"] == 2
    assert second["dataset_kind"] is None
    await request(
        ctx,
        "PUT",
        f"/source-sheets/{second['id']}/classification",
        data={"revision_no": 1, "dataset_kind": "MASTER"},
    )
    # Simulate a scheduler/job retry which does not enter through POST /sync.
    from app.core.security import decode_token
    from app.services.job_service import enqueue

    async with SessionFactory() as session, session.begin():
        user = await session.get(User, decode_token(ctx.tokens["admin"]["access_token"])["sub"])
        queued = await enqueue(session, user, "ETL", source_id)
    await run_pending(ctx.tenant_id)
    failed = (await request(ctx, "GET", "/jobs/" + queued["job_id"]))["data"]
    assert failed["status"] == "FAILED" and failed["error_code"] == "MASTER_RUNTIME_PENDING"
    await request(ctx, "PATCH", f"/source-sheets/{second['id']}", data={"enabled": False})
    await activate(ctx, config)
    assert (await sync(ctx, source_id))["status"] == "SUCCEEDED"


async def test_classification_optimistic_concurrency_and_database_constraints(context, config_data):
    ctx = context
    _, sheet_id, _ = await onboard(ctx, config_data, classify=False)
    path = f"/api/v1/source-sheets/{sheet_id}/classification"
    responses = await asyncio.gather(
        *[
            ctx.client.put(path, headers=ctx.headers["admin"], json={"revision_no": 1, "dataset_kind": kind})
            for kind in ("MASTER", "NON_MASTER")
        ]
    )
    assert sorted(r.status_code for r in responses) == [200, 409]
    from sqlalchemy.exc import IntegrityError

    from app.core.security import decode_token

    outsider = decode_token(ctx.tokens["outsider"]["access_token"])["sub"]
    for values in (
        {"classification_confirmed_by": outsider},
        {"dataset_kind": None},
        {"classification_revision": 0},
    ):
        async with SessionFactory() as session:
            with pytest.raises(IntegrityError):
                await session.execute(update(SourceSheet).where(SourceSheet.id == sheet_id).values(**values))
            await session.rollback()


async def test_scheduled_sync_review_refreshes_and_reuses_batch(context, config_data):
    ctx = context
    source_id, _, config = await onboard(ctx, config_data)
    await activate(ctx, config)
    async with SessionFactory() as session, session.begin():
        await session.execute(
            update(DataSource)
            .where(DataSource.id == source_id)
            .values(
                status="ACTIVE",
                sync_schedule="* * * * *",
                last_scheduled_at=datetime.now(timezone.utc) - timedelta(days=1),
            )
        )

    await schedule_sources()
    async with SessionFactory() as session:
        scheduled = await session.scalar(
            select(Job)
            .where(Job.source_id == source_id, Job.kind == "SYNC_REVIEW")
            .order_by(Job.created_at.desc())
        )
        assert scheduled is not None and scheduled.status == "QUEUED"
    await run_pending(ctx.tenant_id)
    async with SessionFactory() as session:
        completed = await session.get(Job, scheduled.id)
        reviews = (
            await session.scalars(select(ImportReview).where(ImportReview.source_id == source_id))
        ).all()
        assert completed.status == "SUCCEEDED", (completed.error_code, completed.error_message)
        assert completed.result["reviews"][0]["reused"] is False
        assert len(reviews) == 1

    async with SessionFactory() as session, session.begin():
        await session.execute(
            update(DataSource)
            .where(DataSource.id == source_id)
            .values(last_scheduled_at=datetime.now(timezone.utc) - timedelta(days=1))
        )
    await schedule_sources()
    await run_pending(ctx.tenant_id)
    await run_pending(ctx.tenant_id)
    async with SessionFactory() as session:
        reviews = (
            await session.scalars(select(ImportReview).where(ImportReview.source_id == source_id))
        ).all()
        assert len(reviews) == 1
        scheduled_jobs = (
            await session.scalars(select(Job).where(Job.source_id == source_id, Job.kind == "SYNC_REVIEW"))
        ).all()
        assert len(scheduled_jobs) == 2
        assert scheduled_jobs[-1].result["reviews"][0]["reused"] is True


async def test_ai_task_policy_version_history_is_tenant_scoped(context, monkeypatch):
    ctx = context
    settings = get_settings()
    monkeypatch.setattr(settings, "openai_allowed_models", ["history-model"])
    body = {
        "code": "history_policy",
        "purpose": "ETL_CONFIG",
        "prompt_version": "etl_configuration_v1.md",
        "model": "history-model",
        "allowed_models": ["history-model"],
        "data_product_code": None,
        "max_context_chars": 10000,
        "daily_budget_usd": None,
        "fallback_model": None,
    }

    created = await request(ctx, "POST", "/ai-task-policies", expected=201, data=body)
    policy_id = created["data"]["id"]
    initial = await request(ctx, "GET", f"/ai-task-policies/{policy_id}/versions")
    assert [(item["revision_no"], item["action"]) for item in initial["data"]] == [(1, "CREATED")]

    updated = await request(
        ctx,
        "PATCH",
        f"/ai-task-policies/{policy_id}",
        data={**body, "model": "history-model", "revision_no": 1},
    )
    assert updated["data"]["revision_no"] == 2
    await request(
        ctx,
        "POST",
        f"/ai-task-policies/{policy_id}/approve",
        who="approver",
        data={"revision_no": 2, "comment": "reviewed"},
    )

    latest = await request(
        ctx, "GET", f"/ai-task-policies/{policy_id}/versions?offset=0&limit=2"
    )
    assert [(item["revision_no"], item["action"]) for item in latest["data"]] == [
        (3, "APPROVED"),
        (2, "UPDATED"),
    ]
    assert latest["meta"] == {"offset": 0, "limit": 2}
    assert "api_key" not in latest["data"][0]["snapshot_json"]
    await request(ctx, "GET", f"/ai-task-policies/{policy_id}/versions", who="outsider", expected=404)


async def test_ai_task_policy_etl_and_taxonomy_scopes(context, config_data, monkeypatch):
    ctx = context
    settings = get_settings()
    monkeypatch.setattr(settings, "openai_allowed_models", ["scoped-policy-model"])
    source_id, _, _ = await onboard(ctx, config_data, legacy_source=False)
    taxonomy = await request(
        ctx,
        "POST",
        "/taxonomies",
        expected=201,
        data={"code": "scoped_regions", "name": "Scoped regions"},
    )
    taxonomy_id = taxonomy["data"]["id"]
    await request(ctx, "POST", f"/taxonomies/{taxonomy_id}/approve", who="approver")

    source_policy = await request(
        ctx,
        "POST",
        "/ai-task-policies",
        expected=201,
        data={
            "code": "source_scoped_etl",
            "purpose": "ETL_CONFIG",
            "prompt_version": "etl_configuration_v1.md",
            "model": "scoped-policy-model",
            "allowed_models": ["scoped-policy-model"],
            "data_source_id": source_id,
            "max_context_chars": 10000,
        },
    )
    await request(
        ctx,
        "POST",
        "/ai-task-policies",
        who="outsider",
        expected=404,
        data={
            "code": "foreign_taxonomy_scope",
            "purpose": "TAXONOMY_RECOMMEND",
            "prompt_version": "taxonomy_recommend_v1.md",
            "model": "scoped-policy-model",
            "allowed_models": ["scoped-policy-model"],
            "taxonomy_id": taxonomy_id,
            "max_context_chars": 10000,
        },
    )
    taxonomy_policy = await request(
        ctx,
        "POST",
        "/ai-task-policies",
        expected=201,
        data={
            "code": "taxonomy_scoped_recommend",
            "purpose": "TAXONOMY_RECOMMEND",
            "prompt_version": "taxonomy_recommend_v1.md",
            "model": "scoped-policy-model",
            "allowed_models": ["scoped-policy-model"],
            "taxonomy_id": taxonomy_id,
            "max_context_chars": 10000,
        },
    )

    assert source_policy["data"]["data_source_id"] == source_id
    assert source_policy["data"]["taxonomy_id"] is None
    assert taxonomy_policy["data"]["taxonomy_id"] == taxonomy_id
    assert taxonomy_policy["data"]["data_source_id"] is None
    await request(
        ctx,
        "POST",
        "/ai-task-policies",
        who="outsider",
        expected=404,
        data={
            "code": "foreign_source_scope",
            "purpose": "ETL_CONFIG",
            "prompt_version": "etl_configuration_v1.md",
            "model": "scoped-policy-model",
            "allowed_models": ["scoped-policy-model"],
            "data_source_id": source_id,
            "max_context_chars": 10000,
        },
    )
