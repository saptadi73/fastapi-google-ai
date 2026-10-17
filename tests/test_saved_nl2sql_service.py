from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.services.saved_nl2sql_service import SavedNL2SQLService


@pytest.mark.asyncio
async def test_saved_command_replays_compiled_plan_without_ai_using_reader_role():
    command = SimpleNamespace(
        id="saved-command-id",
        data_product_code="SALES",
        plan={"metrics": ["net_sales"]},
        name="Penjualan",
        run_count=0,
        last_run_at=None,
        sql_preview="SELECT ...",
    )
    service = SavedNL2SQLService.__new__(SavedNL2SQLService)
    service.owned = AsyncMock(return_value=command)
    service.executor = Mock(
        execute=AsyncMock(return_value={"rows": [], "meta": {"row_count": 0, "cached": False}})
    )
    service.session = Mock(add=Mock())
    service.user = SimpleNamespace(id="owner-id", tenant_id="tenant-id")

    await service.run(command.id)

    kwargs = service.executor.execute.await_args.kwargs
    assert kwargs["ai"] is False
    assert kwargs["query_source"] == "SAVED_COMMAND"
    assert kwargs["use_nl2sql_reader"] is True
    assert command.run_count == 1
