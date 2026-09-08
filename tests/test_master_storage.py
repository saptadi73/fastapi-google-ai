import asyncio
from copy import deepcopy
from uuid import uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from test_integration import context as context
from test_integration import request
from test_masters import approved_master

from app.core.database import SessionFactory
from app.core.exceptions import AppError
from app.models.auth import User
from app.schemas.master import MasterSchema
from app.services.master_storage_service import MasterStorageService
from app.services.schema_compiler_service import compile_master_table

pytestmark = pytest.mark.integration


async def setup_storage(ctx, config_data):
    master = await approved_master(ctx, config_data)
    path = f"/master-definitions/{master['id']}"
    await request(
        ctx, "POST", path + "/deploy-storage", who="approver", data={"revision_no": master["revision_no"]}
    )
    table = compile_master_table(
        MasterSchema.model_validate(master["approved_definition_json"]), master["id"], ctx.tenant_id
    )
    return master, path, table


def row(ctx, code="001", **values):
    return {
        "_tenant_id": ctx.tenant_id,
        "_record_id": str(uuid4()),
        "_source_sheet_id": str(uuid4()),
        "_source_row": 2,
        "_source_snapshot_hash": "a" * 64,
        "_is_active": True,
        "transaction_id": code,
        "branch_name": "Nama awal",
        **values,
    }


async def test_storage_uuid_leading_zero_revision_and_permissions(context, config_data):
    ctx = context
    master = await approved_master(ctx, config_data)
    path = f"/master-definitions/{master['id']}"
    missing = await request(ctx, "GET", path + "/records", expected=409)
    assert missing["errors"][0]["code"] == "MASTER_STORAGE_REQUIRED"
    await request(ctx, "POST", path + "/deploy-storage", data={"revision_no": 1}, expected=409)
    await request(ctx, "GET", path + "/storage-plan", who="outsider", expected=404)
    for _ in range(2):
        result = await request(
            ctx, "POST", path + "/deploy-storage", who="approver", data={"revision_no": master["revision_no"]}
        )
        assert result["data"]["storage_ready"] and not result["data"]["execution_ready"]
    table = compile_master_table(
        MasterSchema.model_validate(master["approved_definition_json"]), master["id"], ctx.tenant_id
    )
    data = row(ctx)
    async with SessionFactory() as session, session.begin():
        await session.execute(table.insert().values(**data))
    async with SessionFactory() as session, session.begin():
        user = await session.scalar(
            select(User).where(User.tenant_id == ctx.tenant_id, User.username == "admin")
        )
        service = MasterStorageService(session, user)
        await service.update_attributes(master["id"], data["_record_id"], 1, {"branch_name": "Nama baru"})
        with pytest.raises(AppError, match="Record"):
            await service.update_attributes(master["id"], data["_record_id"], 1, {"branch_name": "Stale"})
        for forbidden in ("transaction_id", "_record_id", "_is_active"):
            with pytest.raises(AppError):
                await service.update_attributes(master["id"], data["_record_id"], 2, {forbidden: "changed"})
    items = (await request(ctx, "GET", path + "/records?search=001"))["data"]["items"]
    assert len(items) == 1 and items[0]["_record_id"] == data["_record_id"]
    assert items[0]["transaction_id"] == "001" and items[0]["branch_name"] == "Nama baru"
    assert items[0]["_revision_no"] == 2
    await request(ctx, "GET", path + "/records", who="viewer", expected=403)
    await request(ctx, "GET", path + "/records", who="outsider", expected=404)


async def test_storage_composite_key_concurrent_constraints(context, config_data):
    # The composite business key remains typed in PostgreSQL, not concatenated text.
    from test_masters import definition

    body = definition(config_data)
    body["definition"]["fields"][2]["nullable"] = False
    body["definition"]["business_key"].append("branch_name")
    ctx = context
    master = (await request(ctx, "POST", "/master-definitions", data=body, expected=201))["data"]
    path = f"/master-definitions/{master['id']}"
    await request(ctx, "POST", path + "/submit-review", data={"revision_no": 1})
    master = (await request(ctx, "POST", path + "/approve", who="approver", data={"revision_no": 2}))["data"]
    await request(ctx, "POST", path + "/deploy-storage", data={"revision_no": 3})
    table = compile_master_table(
        MasterSchema.model_validate(master["approved_definition_json"]), master["id"], ctx.tenant_id
    )

    async def insert(values):
        try:
            async with SessionFactory() as session, session.begin():
                await session.execute(table.insert().values(**values))
            return "ok"
        except IntegrityError:
            return "conflict"

    assert sorted(await asyncio.gather(insert(row(ctx)), insert(row(ctx)))) == ["conflict", "ok"]
    assert await insert(row(ctx, branch_name="Other source")) == "ok"
    assert await insert(row(ctx, _tenant_id=str(uuid4()))) == "conflict"
    assert await insert(row(ctx, transaction_id=None)) == "conflict"
    first = row(ctx, code="002")
    assert await insert(first) == "ok"
    assert await insert({**first, "transaction_id": "003"}) == "conflict"
    for strategy in ("FULL_REFRESH", "APPEND"):
        with pytest.raises(AppError):
            compile_master_table(
                MasterSchema.model_validate(master["approved_definition_json"]),
                master["id"],
                ctx.tenant_id,
                strategy,
            )


async def test_storage_masking_pagination_and_no_search_leak(context, config_data):
    config_data["columns"][2]["pii_classification"] = "HIGH"
    config_data["semantic"]["dimensions"].remove("branch_name")
    ctx = context
    _, path, table = await setup_storage(ctx, config_data)
    async with SessionFactory() as session, session.begin():
        await session.execute(
            table.insert(),
            [row(ctx, code="001", branch_name="SecretLabel"), row(ctx, code="002", _is_active=False)],
        )
    assert not (await request(ctx, "GET", path + "/records?search=SecretLabel", who="approver"))["data"][
        "items"
    ]
    masked = (await request(ctx, "GET", path + "/records?search=001", who="approver"))["data"]
    assert masked["items"][0]["branch_name"] == "***" and masked["masked_fields"] == ["branch_name"]
    assert (await request(ctx, "GET", path + "/records?search=SecretLabel"))["data"]["items"][0][
        "branch_name"
    ] == "SecretLabel"
    paged = (await request(ctx, "GET", path + "/records?active_only=false&limit=1"))["data"]
    assert paged["has_more"] and len(paged["items"]) == 1
    next_page = (await request(ctx, "GET", path + "/records?active_only=false&limit=1&offset=1"))["data"]
    assert (
        not next_page["has_more"] and next_page["items"][0]["_record_id"] != paged["items"][0]["_record_id"]
    )


async def test_storage_schema_evolution_and_tamper_detection(context, config_data):
    ctx = context
    master, path, table = await setup_storage(ctx, config_data)
    definition = deepcopy(master["approved_definition_json"])
    definition["fields"].append({"name": "notes", "type": "text", "nullable": True})
    await request(ctx, "PATCH", path, data={"revision_no": 3, "definition": definition})
    await request(ctx, "POST", path + "/submit-review", data={"revision_no": 4})
    await request(ctx, "POST", path + "/approve", who="approver", data={"revision_no": 5})
    assert (await request(ctx, "GET", path + "/records", expected=409))["errors"][0][
        "code"
    ] == "MASTER_STORAGE_STALE"
    await request(ctx, "POST", path + "/deploy-storage", data={"revision_no": 6})
    assert (await request(ctx, "GET", path + "/records"))["data"]["items"] == []
    definition["fields"][0]["type"] = "integer"
    await request(ctx, "PATCH", path, data={"revision_no": 6, "definition": definition})
    await request(ctx, "POST", path + "/submit-review", data={"revision_no": 7})
    assert (
        await request(ctx, "POST", path + "/approve", who="approver", data={"revision_no": 8}, expected=409)
    )["errors"][0]["code"] == "MASTER_SCHEMA_MIGRATION_REQUIRED"
    async with SessionFactory() as session, session.begin():
        # Target is generated from the test-owned UUID; no user-supplied SQL identifiers.
        await session.execute(text(f'ALTER TABLE trusted."{table.name}" DROP CONSTRAINT master_tenant_scope'))
    assert (await request(ctx, "POST", path + "/deploy-storage", data={"revision_no": 8}, expected=409))[
        "errors"
    ][0]["code"] == "MASTER_SCHEMA_MIGRATION_REQUIRED"
