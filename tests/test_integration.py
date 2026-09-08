import base64
import io
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from openpyxl import load_workbook
from sqlalchemy import delete, select, text, update
from sqlalchemy.engine import make_url

from app.core.config import get_settings
from app.core.database import SessionFactory
from app.core.security import password_hasher
from app.main import app
from app.models import Base
from app.models.auth import Tenant, User
from app.models.configuration import Artifact, Configuration
from app.models.source import SourceSheet
from app.services.google_sheets_service import GoogleSheetsService
from app.workers.runner import run_pending

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


async def onboard(ctx, config_data):
    data = await request(
        ctx,
        "POST",
        "/sources/google-sheets",
        expected=202,
        data={"source_code": "sales_test", "name": "Sales Test", "spreadsheet_url": "fake_sheet_12345"},
    )
    source_id = data["data"]["source"]["id"]
    await run_pending(ctx.tenant_id)
    job = await request(ctx, "GET", "/jobs/" + data["data"]["job_id"])
    assert job["data"]["status"] == "SUCCEEDED", job
    sheets = await request(ctx, "GET", f"/sources/{source_id}/sheets")
    sheet_id = sheets["data"][0]["id"]
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
    data = await request(
        context,
        "POST",
        "/sources/google-sheets",
        expected=202,
        data={"source_code": "unavailable", "name": "Missing access", "spreadsheet_url": "fake_sheet_12345"},
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
