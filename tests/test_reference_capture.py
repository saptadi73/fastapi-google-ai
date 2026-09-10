"""Dependency capture uses real is_current, approved bindings and PostgreSQL."""
from copy import deepcopy
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from test_import_reviews import create, non_master
from test_integration import context as context
from test_master_storage import row, setup_storage

from app.core.database import SessionFactory
from app.models.auth import User
from app.models.import_review import ImportReview
from app.models.master import MasterColumnBinding
from app.schemas.master import MasterColumnBindingCreate
from app.services.import_review_service import ImportReviewService
from app.services.master_service import MasterService

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("change", ["alias", "record"])
async def test_real_capture_detects_reference_dependency_changes(context, config_data, change):
    master, _, table = await setup_storage(context, config_data)
    consumer = deepcopy(config_data)
    consumer["columns"][2]["target_type"] = "uuid"
    body = await non_master(context, consumer)
    record = row(context)
    async with SessionFactory() as session, session.begin():
        await session.execute(table.insert().values(**record))
        editor = await session.scalar(select(User).where(User.tenant_id == context.tenant_id, User.username == "admin"))
        approver = await session.scalar(select(User).where(User.tenant_id == context.tenant_id, User.username == "approver"))
        binding = await MasterService(session, editor).save_column_binding(body["source_sheet_id"],
            MasterColumnBindingCreate(revision_no=0, source_column="Cabang", master_definition_id=master["id"],
                                      master_field="transaction_id", master_version=1,
                                      aliases={"Jakarta": record["_record_id"]}))
        await MasterService(session, approver).column_binding_decision(binding["id"], SimpleNamespace(revision_no=1))
    batch = await create(context, body)
    async with SessionFactory() as session, session.begin():
        stored = await session.get(ImportReview, batch["id"])
        assert stored.dependencies["reference_hash"]
        assert await ImportReviewService(session, editor).is_current(stored)
    async with SessionFactory() as session, session.begin():
        if change == "record":
            await session.execute(table.update().values(branch_name="Updated label", _revision_no=2))
        else:
            stored = await session.get(MasterColumnBinding, binding["id"])
            stored.aliases_json = {"Bandung": record["_record_id"]}
            stored.revision_no += 1
    async with SessionFactory() as session:
        stored = await session.get(ImportReview, batch["id"])
        assert not await ImportReviewService(session, editor).is_current(stored)
