import asyncio
from copy import deepcopy

import pytest
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from test_integration import context as context
from test_integration import onboard, request

from app.core.database import SessionFactory
from app.core.security import decode_token
from app.models.master import MasterDefinition, MasterSourceBinding
from app.schemas.configuration import ETLConfiguration
from app.services.google_sheets_service import GoogleSheetsService
from app.workers.runner import run_pending

pytestmark = pytest.mark.integration


def definition(config_data):
    config = ETLConfiguration(**config_data)
    return {
        "code": "products",
        "definition": {
            "name": "Produk",
            "aliases": ["Barang"],
            "fields": [
                {
                    "name": c.target_column,
                    "type": c.target_type,
                    "nullable": c.nullable,
                    "pii_classification": c.pii_classification,
                }
                for c in config.columns
            ],
            "business_key": ["transaction_id"],
            "label_field": "branch_name",
            "policy": {"new_record_policy": "PROPOSE_INSERT", "source_conflict_policy": "REQUIRE_REVIEW"},
        },
    }


async def approved_master(ctx, config_data):
    master = (await request(ctx, "POST", "/master-definitions", expected=201, data=definition(config_data)))[
        "data"
    ]
    path = f"/master-definitions/{master['id']}"
    await request(ctx, "POST", path + "/submit-review", data={"revision_no": 1})
    return (await request(ctx, "POST", path + "/approve", who="approver", data={"revision_no": 2}))["data"]


async def master_sheet(ctx, config_data):
    source, sheet, config = await onboard(ctx, config_data, classify=False)
    await request(
        ctx,
        "PUT",
        f"/source-sheets/{sheet}/classification",
        data={"revision_no": 1, "dataset_kind": "MASTER"},
    )
    return source, sheet, config


def binding_body(master, config_data, revision=0):
    return {
        "revision_no": revision,
        "master_definition_id": master["id"],
        "master_version": master["approved_version"],
        "classification_revision": 2,
        "columns": ETLConfiguration(**config_data).model_dump(mode="json")["columns"],
    }


async def test_master_lifecycle_search_and_duplicate_review(context, config_data):
    ctx = context
    body = definition(config_data)
    await request(ctx, "POST", "/master-definitions", data=body, who="approver", expected=403)
    master = (await request(ctx, "POST", "/master-definitions", data=body, expected=201))["data"]
    path = f"/master-definitions/{master['id']}"
    await request(ctx, "GET", path, who="outsider", expected=404)
    await request(ctx, "GET", path, who="viewer", expected=403)
    assert (await request(ctx, "GET", "/master-definitions?search=Barang&limit=1"))["data"][0][
        "id"
    ] == master["id"]
    await request(ctx, "POST", path + "/approve", who="approver", data={"revision_no": 1}, expected=409)
    await request(ctx, "POST", path + "/submit-review", data={"revision_no": 1})
    await request(ctx, "POST", path + "/approve", data={"revision_no": 2}, expected=403)
    await request(
        ctx, "POST", path + "/reject", who="approver", data={"revision_no": 2, "comment": "Periksa definisi"}
    )
    await request(ctx, "POST", path + "/submit-review", data={"revision_no": 3})
    master = (await request(ctx, "POST", path + "/approve", who="approver", data={"revision_no": 4}))["data"]
    assert master["approved_version"] == 1 and master["approved_definition_json"]["name"] == "Produk"
    duplicate = {**body, "code": "other_products"}
    candidates = (await request(ctx, "POST", "/master-definitions/preview", data=duplicate))["data"][
        "candidates"
    ]
    assert candidates[0]["id"] == master["id"]
    error = await request(ctx, "POST", "/master-definitions", data=duplicate, expected=409)
    assert error["errors"][0]["code"] == "MASTER_DUPLICATE_REVIEW_REQUIRED"
    await request(
        ctx,
        "POST",
        "/master-definitions",
        data={
            **duplicate,
            "reviewed_candidate_ids": [master["id"]],
            "duplicate_review_reason": "Kategori barang berbeda; definisi sengaja terpisah.",
        },
        expected=201,
    )
    # Same business code is rejected even if the display name has no similarity.
    distinct = deepcopy(body)
    distinct["definition"]["name"] = "Kepegawaian"
    distinct["definition"]["aliases"] = []
    error = await request(ctx, "POST", "/master-definitions", data=distinct, expected=409)
    assert error["errors"][0]["code"] == "RESOURCE_CONFLICT"


async def test_two_tabs_bind_one_approved_master_without_loading(context, config_data, monkeypatch):
    ctx = context
    source, sheet, config = await master_sheet(ctx, config_data)
    master = await approved_master(ctx, config_data)

    async def metadata(self, spreadsheet_id):
        return {
            "sheets": [
                {"properties": {"sheetId": 1, "title": "Sales"}},
                {"properties": {"sheetId": 2, "title": "Other products"}},
            ]
        }

    monkeypatch.setattr(GoogleSheetsService, "metadata", metadata)
    await request(ctx, "POST", f"/sources/{source}/discover", expected=202)
    await run_pending(ctx.tenant_id)
    sheets = (await request(ctx, "GET", f"/sources/{source}/sheets"))["data"]
    second = next(s for s in sheets if s["id"] != sheet)
    await request(
        ctx,
        "PUT",
        f"/source-sheets/{second['id']}/classification",
        data={"revision_no": 1, "dataset_kind": "MASTER"},
    )
    for tab in (sheet, second["id"]):
        path = f"/source-sheets/{tab}/master-binding"
        saved = (await request(ctx, "PUT", path, data=binding_body(master, config_data)))["data"]
        assert saved["validation"]["valid"] and not saved["execution_ready"]
        await request(ctx, "POST", path + "/approve", data={"revision_no": 1}, expected=403)
        await request(ctx, "POST", path + "/approve", who="approver", data={"revision_no": 1})
        detail = (await request(ctx, "GET", path))["data"]
        assert detail["metadata_ready"] and not detail["execution_ready"]
        assert detail["binding"]["master_definition_id"] == master["id"]
    error = await request(ctx, "POST", f"/sources/{source}/sync", expected=409)
    assert error["errors"][0]["code"] == "MASTER_RUNTIME_PENDING"
    classification = (await request(ctx, "GET", f"/source-sheets/{sheet}/classification"))["data"]
    assert classification["master_binding"]["metadata_ready"] and not classification["execution_ready"]


async def test_binding_version_classification_snapshot_and_inactive_master(context, config_data):
    ctx = context
    source, sheet, _ = await master_sheet(ctx, config_data)
    master = await approved_master(ctx, config_data)
    path = f"/source-sheets/{sheet}/master-binding"
    body = binding_body(master, config_data)
    await request(ctx, "PUT", path, data=body)
    ctx.values[1][3] = 321
    await request(ctx, "POST", f"/sources/{source}/profile", expected=202)
    await run_pending(ctx.tenant_id)
    error = await request(
        ctx, "POST", path + "/approve", who="approver", data={"revision_no": 1}, expected=409
    )
    assert error["errors"][0]["code"] == "MASTER_BINDING_STALE"
    await request(ctx, "PUT", path, data={**body, "revision_no": 1})
    await request(ctx, "POST", path + "/approve", who="approver", data={"revision_no": 2})
    mpath = f"/master-definitions/{master['id']}"
    changed = definition(config_data)["definition"]
    changed["description"] = "Versi berikutnya"
    draft = (await request(ctx, "PATCH", mpath, data={"revision_no": 3, "definition": changed}))["data"]
    assert draft["approved_definition_json"]["description"] == ""
    assert (await request(ctx, "GET", path))["data"]["metadata_ready"]
    await request(ctx, "POST", mpath + "/submit-review", data={"revision_no": 4})
    await request(ctx, "POST", mpath + "/approve", who="approver", data={"revision_no": 5})
    detail = (await request(ctx, "GET", path))["data"]
    assert not detail["metadata_ready"] and detail["blocking_reason"] == "MASTER_VERSION_UNAVAILABLE"
    await request(ctx, "POST", mpath + "/deactivate", who="approver", data={"revision_no": 6})
    await request(ctx, "PUT", path, data={**body, "revision_no": 3, "master_version": 2}, expected=409)


async def test_binding_schema_errors_and_tenant_constraints(context, config_data):
    ctx = context
    _, sheet, _ = await master_sheet(ctx, config_data)
    master = await approved_master(ctx, config_data)
    body = binding_body(master, config_data)
    path = f"/source-sheets/{sheet}/master-binding"
    for change in (
        {"target_type": "numeric"},
        {"nullable": True},
        {"is_business_key": False},
        {"source_column": "Missing header"},
    ):
        invalid = deepcopy(body)
        invalid["columns"][0].update(change)
        await request(ctx, "PUT", path, data=invalid, expected=422)
    await request(ctx, "PUT", path, who="outsider", data=body, expected=404)
    await request(ctx, "PUT", path, who="approver", data=body, expected=403)
    saved = (await request(ctx, "PUT", path, data=body))["data"]["binding"]
    outsider = decode_token(ctx.tokens["outsider"]["access_token"])["sub"]
    async with SessionFactory() as session:
        with pytest.raises(IntegrityError):
            await session.execute(
                update(MasterSourceBinding)
                .where(MasterSourceBinding.id == saved["id"])
                .values(created_by=outsider)
            )
        await session.rollback()
    async with SessionFactory() as session:
        with pytest.raises(IntegrityError):
            await session.execute(
                update(MasterDefinition)
                .where(MasterDefinition.id == master["id"])
                .values(approved_by=outsider)
            )
        await session.rollback()


async def test_registry_concurrent_duplicate_creation(context, config_data):
    body = definition(config_data)
    responses = await asyncio.gather(
        *[
            context.client.post(
                "/api/v1/master-definitions", headers=context.headers["admin"], json={**body, "code": code}
            )
            for code in ("product_a", "product_b")
        ]
    )
    assert sorted(r.status_code for r in responses) == [201, 409]
    assert len((await request(context, "GET", "/master-definitions"))["data"]) == 1
