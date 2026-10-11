from copy import deepcopy
from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.engine import make_url
from test_integration import activate, onboard, request
from test_integration import context as context

import app.services.configuration_service as configuration_service
import app.workers.runner as worker_runner
from app.core.config import get_settings
from app.core.database import SessionFactory
from app.core.exceptions import AppError
from app.models.audit import AuditEvent
from app.schemas.configuration import ETLConfiguration
from app.services.profiling_service import digest
from app.services.schema_compiler_service import compile_table
from app.workers.runner import run_pending

pytestmark = pytest.mark.integration


@pytest.fixture
async def separate_deployment_roles(context, monkeypatch):
    settings = get_settings()
    test_url = make_url(settings.test_database_url.get_secret_value())
    assert test_url.database.endswith("_test")
    suffix = uuid4().hex[:16]
    runtime, ddl = "codex_runtime_" + suffix, "codex_ddl_" + suffix
    password = uuid4().hex
    async with SessionFactory() as session, session.begin():
        await session.execute(text(f'CREATE ROLE "{runtime}" NOLOGIN'))
        await session.execute(text(f'CREATE ROLE "{ddl}" LOGIN NOINHERIT PASSWORD \'{password}\''))
        await session.execute(text(f'GRANT "{runtime}" TO "{ddl}" WITH INHERIT FALSE, SET TRUE'))
        await session.execute(text(f'GRANT USAGE ON SCHEMA platform,raw,staging,quarantine,audit,trusted,semantic TO "{runtime}"'))
        await session.execute(text(f'GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA platform,raw,staging,quarantine,audit TO "{runtime}"'))
        await session.execute(text(f'GRANT USAGE,CREATE ON SCHEMA trusted,semantic TO "{ddl}"'))
        await session.execute(text(f'GRANT USAGE ON SCHEMA audit TO "{ddl}"'))
        await session.execute(text(f'GRANT INSERT ON audit.event_log TO "{ddl}"'))
    secret = type(settings.database_url)
    monkeypatch.setattr(settings, "database_url", secret(test_url.set(username=runtime, password=None).render_as_string(hide_password=False)))
    monkeypatch.setattr(settings, "database_ddl_url", secret(test_url.set(username=ddl, password=password).render_as_string(hide_password=False)))
    try:
        yield context
    finally:
        async with SessionFactory() as session, session.begin():
            # Only these UUID-named test roles and their temporary objects are removed.
            await session.execute(text(f'DROP OWNED BY "{ddl}","{runtime}"'))
            await session.execute(text(f'DROP ROLE "{ddl}"'))
            await session.execute(text(f'DROP ROLE "{runtime}"'))


@pytest.mark.parametrize("populated", [False, True])
@pytest.mark.parametrize("drift_stage", [None, "approval", "deploy", "activation", "activation_drift", "job_status"])
async def test_date_schema_preview_submission_approval_worker_and_audit(
    context, config_data, populated, drift_stage, monkeypatch
):
    ctx = context
    config_data["columns"][1]["date_input_format"] = "GOOGLE_SHEETS_SERIAL"
    for index, row in enumerate(ctx.values[1:]):
        row[1] = 46023 + index
    old = deepcopy(config_data)
    old["columns"][1]["target_type"] = "bigint"
    old["columns"][1]["transformation_codes"] = []
    old["columns"][1]["date_input_format"] = None
    _, sheet, initial = await onboard(ctx, old)
    await activate(ctx, initial)
    if populated:
        original = compile_table(ETLConfiguration.model_validate(old), sheet)
        business = {
            "transaction_id": "001",
            "transaction_date": 46023,
            "branch_name": "Jakarta",
            "net_amount": 100,
        }
        async with SessionFactory() as session, session.begin():
            await session.execute(
                original.insert().values(
                    **business,
                    _tenant_id=ctx.tenant_id,
                    _source_sheet_id=sheet,
                    _source_row=2,
                    _etl_run_id=str(uuid4()),
                    _row_hash=digest(business),
                )
            )
    cloned = (await request(ctx, "POST", f"/configurations/{initial['id']}/clone", expected=201))["data"]
    patched = (
        await request(
            ctx,
            "PATCH",
            f"/configurations/{cloned['id']}",
            data={
                "revision_no": cloned["revision_no"],
                "configuration": config_data,
            },
        )
    )["data"]
    path = f"/configurations/{cloned['id']}"
    validation = (await request(ctx, "POST", path + "/validate"))["data"]
    migration = validation["deployment_plan"]["migration"]
    assert migration["allowed"] and migration["requires_migration"]
    assert any(
        op["column"] == "transaction_date"
        and op["action"] == ("SERIAL_TO_DATE" if populated else "ALTER_TYPE")
        for op in migration["operations"]
    )
    body = {
        "revision_no": patched["revision_no"],
        "snapshot_hash": validation["snapshot_hash"],
        "reviewed_columns": [c["target_column"] for c in config_data["columns"]],
        "reviewed_sections": ["identity", "columns", "cleansing", "quality", "load", "semantic"],
    }
    error = await request(ctx, "POST", path + "/submit-review", data=body, expected=409)
    assert error["errors"][0]["code"] == "SCHEMA_REVIEW_REQUIRED"
    submitted = (
        await request(
            ctx,
            "POST",
            path + "/submit-review",
            data={
                **body,
                "reviewed_schema_fingerprint": migration["fingerprint"],
            },
        )
    )["data"]
    assert submitted["review_state"]["schema_migration"]["fingerprint"] == migration["fingerprint"]
    original = compile_table(ETLConfiguration.model_validate(old), sheet)
    async with SessionFactory() as session:
        assert (
            await session.scalar(
                text(
                    "SELECT data_type FROM information_schema.columns WHERE table_schema='trusted' "
                    "AND table_name=:table AND column_name='transaction_date'"
                ),
                {"table": original.name},
            )
            == "bigint"
        )
    if drift_stage == "approval":
        async with SessionFactory() as session, session.begin():
            await session.execute(
                text(f"ALTER TABLE trusted.{original.name} ALTER COLUMN branch_name SET NOT NULL")
            )
        response = await request(
            ctx,
            "POST",
            path + "/approve",
            data={"revision_no": submitted["revision_no"]},
            who="approver",
            expected=409,
        )
        assert response["errors"][0]["code"] == "SCHEMA_MIGRATION_STALE"
        return
    await request(
        ctx, "POST", path + "/approve", data={"revision_no": submitted["revision_no"]}, who="approver"
    )
    if drift_stage == "deploy":
        async with SessionFactory() as session, session.begin():
            await session.execute(
                text(f"ALTER TABLE trusted.{original.name} ALTER COLUMN branch_name SET NOT NULL")
            )
    original_audit = configuration_service.audit
    if drift_stage in ("activation", "activation_drift"):

        def fail_activation(session, user, event, resource_id=None, **details):
            if event == "configuration.activated":
                raise AppError("TEST_ACTIVATION_FAILED", "Intentional registry failure")
            original_audit(session, user, event, resource_id, **details)

        monkeypatch.setattr(configuration_service, "audit", fail_activation)
    if drift_stage == "job_status":
        original_stage = worker_runner._audit_stage

        def fail_success_stage(session, job, status, **details):
            if job.kind == "DEPLOY" and status == "SUCCEEDED":
                raise AppError("TEST_JOB_COMMIT_FAILED", "Intentional failure before job commit")
            original_stage(session, job, status, **details)

        monkeypatch.setattr(worker_runner, "_audit_stage", fail_success_stage)
    queued = (await request(ctx, "POST", path + "/deploy", who="approver", expected=202))["data"]
    await run_pending(ctx.tenant_id)
    job = (await request(ctx, "GET", "/jobs/" + queued["job_id"]))["data"]
    assert job["status"] == ("FAILED" if drift_stage else "SUCCEEDED"), job
    if drift_stage == "deploy":
        assert job["error_code"] == "SCHEMA_MIGRATION_STALE"
    async with SessionFactory() as session:
        events = (
            await session.scalars(
                select(AuditEvent).where(
                    AuditEvent.tenant_id == ctx.tenant_id,
                    AuditEvent.resource_id == cloned["id"],
                    AuditEvent.event == "configuration.schema.migrated",
                )
            )
        ).all()
        assert len(events) == (0 if drift_stage else 1)
        kind = await session.scalar(
            text(
                "SELECT data_type FROM information_schema.columns WHERE table_schema='semantic' "
                "AND table_name=:view AND column_name='transaction_date'"
            ),
            {"view": "v_" + sheet.replace("-", "")},
        )
        assert kind == ("bigint" if drift_stage else "date")
        if drift_stage:
            from app.models.configuration import Configuration
            from app.models.source import SourceSheet

            assert (await session.get(Configuration, cloned["id"])).status == "APPROVED"
            assert (await session.get(SourceSheet, sheet)).active_configuration_id == initial["id"]
            failed = await session.scalar(select(AuditEvent).where(
                AuditEvent.resource_id == cloned["id"], AuditEvent.event == "configuration.deploy.failed",
            ))
            assert failed and failed.details["transaction_rolled_back"]
            if populated:
                row = (await session.execute(original.select())).mappings().one()
                assert row["transaction_date"] == 46023 and row["_row_hash"] == digest(business)
    if drift_stage in ("activation", "activation_drift"):
        monkeypatch.setattr(configuration_service, "audit", original_audit)
        if drift_stage == "activation_drift":
            async with SessionFactory() as session, session.begin():
                if populated:
                    # Change values without changing row count or requiring new DDL.
                    await session.execute(text(f"UPDATE trusted.{original.name} SET net_amount=net_amount+1"))
                else:
                    await session.execute(text(f"ALTER TABLE trusted.{original.name} ALTER COLUMN branch_name SET NOT NULL"))
        retried = (await request(ctx, "POST", path + "/deploy", who="approver", expected=202))["data"]
        await run_pending(ctx.tenant_id)
        retry_job = (await request(ctx, "GET", "/jobs/" + retried["job_id"]))["data"]
        if drift_stage == "activation_drift":
            assert retry_job["status"] == "FAILED"
            assert retry_job["error_code"] == "SCHEMA_MIGRATION_STALE"
        else:
            assert retry_job["status"] == "SUCCEEDED"
        async with SessionFactory() as session:
            assert (
                len(
                    (
                        await session.scalars(
                            select(AuditEvent).where(
                                AuditEvent.resource_id == cloned["id"],
                                AuditEvent.event == "configuration.schema.migrated",
                            )
                        )
                    ).all()
                )
                == (0 if drift_stage == "activation_drift" else 1)
            )


@pytest.mark.parametrize("drift_stage", ["approval", "deploy"])
async def test_target_data_drift_without_schema_operations(context, config_data, drift_stage):
    ctx = context
    _, sheet, initial = await onboard(ctx, config_data)
    await activate(ctx, initial)
    target = compile_table(ETLConfiguration.model_validate(config_data), sheet)
    async with SessionFactory() as session, session.begin():
        business = {
            "transaction_id": "001", "transaction_date": date(2026, 9, 1),
            "branch_name": "Jakarta", "net_amount": 100,
        }
        await session.execute(target.insert().values(
            **business, _tenant_id=ctx.tenant_id, _source_sheet_id=sheet,
            _source_row=2, _etl_run_id=str(uuid4()), _row_hash=digest(business),
        ))
    cloned = (await request(ctx, "POST", f"/configurations/{initial['id']}/clone", expected=201))["data"]
    path = f"/configurations/{cloned['id']}"
    validation = (await request(ctx, "POST", path + "/validate"))["data"]
    assert not validation["deployment_plan"]["migration"]["requires_migration"]
    submitted = (await request(ctx, "POST", path + "/submit-review", data={
        "revision_no": cloned["revision_no"], "snapshot_hash": validation["snapshot_hash"],
        "reviewed_columns": [c["target_column"] for c in config_data["columns"]],
        "reviewed_sections": ["identity", "columns", "cleansing", "quality", "load", "semantic"],
    }))["data"]
    if drift_stage == "deploy":
        await request(ctx, "POST", path + "/approve", who="approver",
                      data={"revision_no": submitted["revision_no"]})
    async with SessionFactory() as session, session.begin():
        await session.execute(target.update().values(net_amount=200))
    if drift_stage == "approval":
        result = await request(ctx, "POST", path + "/approve", who="approver", expected=409,
                               data={"revision_no": submitted["revision_no"]})
        assert result["errors"][0]["code"] == "SCHEMA_MIGRATION_STALE"
    else:
        queued = (await request(ctx, "POST", path + "/deploy", who="approver", expected=202))["data"]
        await run_pending(ctx.tenant_id)
        job = (await request(ctx, "GET", "/jobs/" + queued["job_id"]))["data"]
        assert job["status"] == "FAILED" and job["error_code"] == "SCHEMA_MIGRATION_STALE"


@pytest.mark.parametrize("populated", [False, True])
@pytest.mark.parametrize("failure", [None, "activation", "job_status"])
async def test_atomic_worker_with_separate_nonprivileged_roles(
    separate_deployment_roles, config_data, populated, failure, monkeypatch
):
    await test_date_schema_preview_submission_approval_worker_and_audit(
        separate_deployment_roles, config_data, populated, failure, monkeypatch
    )
