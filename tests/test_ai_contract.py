from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.schemas.configuration import ETLConfiguration
from app.services import openai_service


async def test_responses_api_contract_and_usage(monkeypatch, config_data):
    settings = get_settings()
    monkeypatch.setattr(settings, "openai_api_key", type(settings.openai_api_key)("test-placeholder"))
    monkeypatch.setattr(settings, "openai_model_etl_config", "approved-model-test")
    monkeypatch.setattr(settings, "ai_daily_tenant_budget_usd", 0)
    parsed = ETLConfiguration.model_validate(config_data)
    response = SimpleNamespace(
        output_parsed=parsed,
        id="resp_mock",
        usage=SimpleNamespace(
            input_tokens=100, output_tokens=50, input_tokens_details=SimpleNamespace(cached_tokens=20)
        ),
    )
    parse = AsyncMock(return_value=response)
    calls, ledger = [], []

    class Client:
        def __init__(self, **kwargs):
            calls.append(kwargs)
            self.responses = SimpleNamespace(parse=parse)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

    class Ledger:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        def begin(self):
            return self

        async def execute(self, *args, **kwargs):
            pass

        async def scalar(self, *args, **kwargs):
            return 0

        def add(self, value):
            ledger.append(value)

    monkeypatch.setattr(openai_service, "AsyncOpenAI", Client)
    monkeypatch.setattr(openai_service, "SessionFactory", Ledger)
    user = SimpleNamespace(id=str(uuid4()), tenant_id=str(uuid4()))
    value, metadata = await openai_service.OpenAIService().generate(
        user, "ETL_CONFIG", "masked profile", ETLConfiguration
    )
    assert value == parsed and metadata["ai_model"] == "approved-model-test"
    arguments = parse.call_args.kwargs
    assert arguments["store"] is False
    assert arguments["text_format"] is ETLConfiguration
    assert arguments["input"][1]["content"] == "masked profile"
    assert calls[0]["max_retries"] == 0
    assert ledger[0].input_tokens == 100 and ledger[0].cached_tokens == 20
    parse.return_value = SimpleNamespace(output_parsed=None, id="refused", usage=None)
    with pytest.raises(AppError):
        await openai_service.OpenAIService().generate(user, "ETL_CONFIG", "masked profile", ETLConfiguration)
    assert ledger[-1].status == "FAILED"
