from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.schemas.configuration import ETLConfiguration
from app.services import openai_service


@pytest.mark.parametrize("purpose", ["ETL_CONFIG", "TAXONOMY_RECOMMEND"])
async def test_responses_api_contract_and_usage(monkeypatch, config_data, purpose):
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
    calls, ledger, scalar_queries = [], [], []

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
            scalar_queries.append(args[0])
            return 0

        def add(self, value):
            ledger.append(value)

    monkeypatch.setattr(openai_service, "AsyncOpenAI", Client)
    monkeypatch.setattr(openai_service, "SessionFactory", Ledger)
    user = SimpleNamespace(id=str(uuid4()), tenant_id=str(uuid4()))
    value, metadata = await openai_service.OpenAIService().generate(
        user, purpose, "masked profile", ETLConfiguration
    )
    assert value == parsed and metadata["ai_model"] == "approved-model-test"
    arguments = parse.call_args.kwargs
    assert arguments["store"] is False
    assert arguments["text_format"] is ETLConfiguration
    assert arguments["input"][1]["content"] == "masked profile"
    assert calls[0]["max_retries"] == 0
    assert ledger[0].input_tokens == 100 and ledger[0].cached_tokens == 20
    assert ledger[0].purpose == purpose
    assert metadata["prompt_version"] == ("taxonomy_recommend_v1.md" if purpose == "TAXONOMY_RECOMMEND" else "etl_configuration_v1.md")
    assert "platform.ai_task_policy.approved_at DESC" in str(scalar_queries[0])
    assert "platform.ai_task_policy.data_product_code IS NULL" in str(scalar_queries[0])
    scoped_query_index = len(scalar_queries)
    await openai_service.OpenAIService().generate(
        user,
        purpose,
        "masked profile",
        ETLConfiguration,
        data_product_code="SALES",
    )
    scoped_query = str(scalar_queries[scoped_query_index])
    assert "platform.ai_task_policy.data_product_code =" in scoped_query
    assert "OR platform.ai_task_policy.data_product_code IS NULL" in scoped_query
    assert "CASE WHEN" in scoped_query
    parse.return_value = SimpleNamespace(output_parsed=None, id="refused", usage=None)
    with pytest.raises(AppError):
        await openai_service.OpenAIService().generate(user, purpose, "masked profile", ETLConfiguration)
    assert ledger[-1].status == "FAILED"


async def test_approved_policy_falls_back_and_records_policy_usage(monkeypatch, config_data):
    settings = get_settings()
    monkeypatch.setattr(settings, "openai_api_key", type(settings.openai_api_key)("test-placeholder"))
    monkeypatch.setattr(settings, "openai_model_etl_config", "primary-model")
    monkeypatch.setattr(settings, "openai_allowed_models", ["primary-model", "fallback-model"])
    monkeypatch.setattr(settings, "ai_daily_tenant_budget_usd", 0)
    parsed = ETLConfiguration.model_validate(config_data)
    policy = SimpleNamespace(
        id=str(uuid4()),
        model="primary-model",
        fallback_model="fallback-model",
        allowed_models=["primary-model", "fallback-model"],
        prompt_version="etl_configuration_v1.md",
        max_context_chars=10_000,
        daily_budget_usd=None,
    )
    success = SimpleNamespace(
        output_parsed=parsed,
        id="resp_fallback",
        usage=SimpleNamespace(input_tokens=80, output_tokens=20, input_tokens_details=None),
    )
    parse = AsyncMock(side_effect=[RuntimeError("primary failed"), success])
    ledger = []

    class Client:
        def __init__(self, **_kwargs):
            self.responses = SimpleNamespace(parse=parse)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

    class Ledger:
        def __init__(self):
            self.scalar_calls = 0

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        def begin(self):
            return self

        async def execute(self, *args, **kwargs):
            pass

        async def scalar(self, *_args, **_kwargs):
            self.scalar_calls += 1
            return policy if self.scalar_calls == 1 else 0

        def add(self, value):
            ledger.append(value)

    monkeypatch.setattr(openai_service, "AsyncOpenAI", Client)
    monkeypatch.setattr(openai_service, "SessionFactory", Ledger)
    user = SimpleNamespace(id=str(uuid4()), tenant_id=str(uuid4()))

    value, metadata = await openai_service.OpenAIService().generate(
        user, "ETL_CONFIG", "masked profile", ETLConfiguration
    )

    assert value == parsed
    assert [call.kwargs["model"] for call in parse.await_args_list] == [
        "primary-model",
        "fallback-model",
    ]
    assert metadata["ai_model"] == "fallback-model" and metadata["fallback_used"] is True
    assert ledger[0].policy_id == policy.id and ledger[0].model == "fallback-model"
    assert ledger[0].status == "SUCCEEDED"


@pytest.mark.parametrize(
    ("context", "budget", "expected_code"),
    [
        ("x" * 1_001, None, "AI_CONTEXT_LIMIT_EXCEEDED"),
        ("short", 0.001, "AI_TASK_BUDGET_EXCEEDED"),
    ],
)
async def test_policy_runtime_limits_stop_before_provider(
    monkeypatch, context, budget, expected_code
):
    settings = get_settings()
    monkeypatch.setattr(settings, "openai_api_key", type(settings.openai_api_key)("test-placeholder"))
    monkeypatch.setattr(settings, "openai_model_etl_config", "primary-model")
    monkeypatch.setattr(settings, "openai_allowed_models", ["primary-model"])
    monkeypatch.setattr(settings, "ai_daily_tenant_budget_usd", 0)
    monkeypatch.setattr(settings, "openai_input_usd_per_million", 1)
    monkeypatch.setattr(settings, "openai_output_usd_per_million", 1)
    policy = SimpleNamespace(
        id=str(uuid4()),
        model="primary-model",
        fallback_model=None,
        allowed_models=["primary-model"],
        prompt_version="etl_configuration_v1.md",
        max_context_chars=1_000,
        daily_budget_usd=budget,
    )

    class Ledger:
        def __init__(self):
            self.scalar_calls = 0

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        def begin(self):
            return self

        async def execute(self, *args, **kwargs):
            pass

        async def scalar(self, *_args, **_kwargs):
            self.scalar_calls += 1
            return policy if self.scalar_calls == 1 else 0

    provider = Mock()
    monkeypatch.setattr(openai_service, "AsyncOpenAI", provider)
    monkeypatch.setattr(openai_service, "SessionFactory", Ledger)
    user = SimpleNamespace(id=str(uuid4()), tenant_id=str(uuid4()))

    with pytest.raises(AppError) as error:
        await openai_service.OpenAIService().generate(
            user, "ETL_CONFIG", context, ETLConfiguration
        )

    assert error.value.code == expected_code
    provider.assert_not_called()
