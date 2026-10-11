from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.schemas.configuration import ETLConfiguration
from app.schemas.import_review import AIImportReviewResult
from app.services import openai_service


@pytest.mark.parametrize("json_fallback", [False, True])
async def test_import_review_output_is_not_coerced_to_etl_configuration(monkeypatch, json_fallback):
    settings = get_settings()
    monkeypatch.setattr(settings, "openai_api_key", type(settings.openai_api_key)("test-placeholder"))
    monkeypatch.setattr(settings, "openai_model_etl_config", "review-model")
    monkeypatch.setattr(settings, "openai_model_etl_fallback", "")
    monkeypatch.setattr(settings, "ai_daily_tenant_budget_usd", 0)
    result = AIImportReviewResult(
        issues=[{"source_row": 2, "target_column": "name", "message": "Verify spelling"}],
        reviewed_rows=[2], coverage="COMPLETE",
    )
    response = SimpleNamespace(
        output_parsed=result, output_text=result.model_dump_json(), id="review_response",
        usage=SimpleNamespace(input_tokens=10, output_tokens=10, input_tokens_details=None),
    )
    parse = AsyncMock(side_effect=RuntimeError("structured parse failed") if json_fallback else None,
                      return_value=response)
    create = AsyncMock(return_value=response)
    ledger = []

    class Client:
        def __init__(self, **_kwargs):
            self.responses = SimpleNamespace(parse=parse, create=create)

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

        def add(self, item):
            ledger.append(item)

    monkeypatch.setattr(openai_service, "AsyncOpenAI", Client)
    monkeypatch.setattr(openai_service, "SessionFactory", Ledger)
    monkeypatch.setattr(openai_service, "_coerce_etl_draft", Mock(side_effect=AssertionError("Not a config")))
    value, metadata = await openai_service.OpenAIService().generate(
        SimpleNamespace(id=str(uuid4()), tenant_id=str(uuid4())),
        "ETL_CONFIG", '{"task":"Review values","rows":[]}', AIImportReviewResult,
        data_source_id=str(uuid4()),
    )
    assert value == result
    assert value.issues[0].model_dump()["target_column"] == "name"
    assert "required output schema is AIImportReviewResult" in parse.call_args.kwargs["input"][0]["content"]
    assert metadata["prompt_version"] == "etl_configuration_v1.md"
    assert ledger[0].purpose == "ETL_CONFIG"
    assert ledger[0].status == "SUCCEEDED"
    assert create.await_count == int(json_fallback)


def test_import_review_issue_schema_has_no_unconstrained_objects():
    schema = AIImportReviewResult.model_json_schema()
    issue = schema["$defs"]["AIImportReviewIssue"]
    assert issue["additionalProperties"] is False
    assert set(issue["properties"]) == {"source_row", "target_column", "message"}
    assert schema["properties"]["issues"]["items"] == {"$ref": "#/$defs/AIImportReviewIssue"}


@pytest.mark.parametrize(
    "reviewed_rows,coverage,expected",
    [
        ([2, 3], "COMPLETE", True),
        ([3, 2], "COMPLETE", True),
        ([2, 2], "COMPLETE", False),
        ([2, 3, 4], "COMPLETE", False),
        ([2, 4], "COMPLETE", False),
        ([2], "COMPLETE", False),
        ([2, 3], "PARTIAL", False),
    ],
)
def test_import_review_requires_exact_unique_row_coverage(reviewed_rows, coverage, expected):
    result = AIImportReviewResult(issues=[], reviewed_rows=reviewed_rows, coverage=coverage)
    assert result.is_complete_for_rows([2, 3]) is expected
    assert AIImportReviewResult.model_validate(
        result.model_dump(mode="json")
    ).is_complete_for_rows([2, 3]) is expected


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
    assert "CASE ELSE" not in str(scalar_queries[0].compile(dialect=postgresql.dialect()))
    scoped_query_index = len(scalar_queries)
    scope_field = "data_source_id" if purpose == "ETL_CONFIG" else "taxonomy_id"
    await openai_service.OpenAIService().generate(
        user,
        purpose,
        "masked profile",
        ETLConfiguration,
        **{scope_field: str(uuid4())},
    )
    scoped_query = str(scalar_queries[scoped_query_index])
    assert f"platform.ai_task_policy.{scope_field} =" in scoped_query
    assert "platform.ai_task_policy.data_product_code IS NULL" in scoped_query
    assert "platform.ai_task_policy.data_source_id IS NULL" in scoped_query
    assert "platform.ai_task_policy.taxonomy_id IS NULL" in scoped_query
    priority_case = scoped_query.rsplit("CASE WHEN", 1)[1].split("END DESC", 1)[0]
    assert f"platform.ai_task_policy.{scope_field} =" in priority_case
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


async def test_policy_budget_reserves_registered_prompt_before_provider(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "openai_api_key", type(settings.openai_api_key)("test-placeholder"))
    monkeypatch.setattr(settings, "openai_model_etl_config", "primary-model")
    monkeypatch.setattr(settings, "openai_allowed_models", ["primary-model"])
    monkeypatch.setattr(settings, "ai_daily_tenant_budget_usd", 0)
    monkeypatch.setattr(settings, "openai_input_usd_per_million", 1)
    monkeypatch.setattr(settings, "openai_output_usd_per_million", 1)
    monkeypatch.setattr(settings, "openai_max_output_tokens", 1)
    policy = SimpleNamespace(
        id=str(uuid4()),
        model="primary-model",
        fallback_model=None,
        allowed_models=["primary-model"],
        prompt_version="etl_configuration_v1.md",
        max_context_chars=1_000,
        daily_budget_usd=0.00001,
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

        def add(self, _value):
            raise AssertionError("Budget rejection must not write usage")

    provider = Mock()
    monkeypatch.setattr(openai_service, "AsyncOpenAI", provider)
    monkeypatch.setattr(openai_service, "SessionFactory", Ledger)
    user = SimpleNamespace(id=str(uuid4()), tenant_id=str(uuid4()))

    with pytest.raises(AppError) as error:
        await openai_service.OpenAIService().generate(
            user, "ETL_CONFIG", "short", ETLConfiguration
        )

    assert error.value.code == "AI_TASK_BUDGET_EXCEEDED"
    provider.assert_not_called()


async def test_runtime_rejects_invalid_stored_model_allowlist(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "openai_api_key", type(settings.openai_api_key)("test-placeholder"))
    monkeypatch.setattr(settings, "openai_model_etl_config", "primary-model")
    monkeypatch.setattr(settings, "openai_allowed_models", ["primary-model"])
    policy = SimpleNamespace(
        id=str(uuid4()),
        model="primary-model",
        fallback_model=None,
        allowed_models=["primary-model", "untrusted-model"],
        prompt_version="etl_configuration_v1.md",
        max_context_chars=1_000,
        daily_budget_usd=None,
    )

    class Ledger:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        def begin(self):
            return self

        async def scalar(self, *_args, **_kwargs):
            return policy

    provider = Mock()
    monkeypatch.setattr(openai_service, "AsyncOpenAI", provider)
    monkeypatch.setattr(openai_service, "SessionFactory", Ledger)
    user = SimpleNamespace(id=str(uuid4()), tenant_id=str(uuid4()))

    with pytest.raises(AppError) as error:
        await openai_service.OpenAIService().generate(
            user, "ETL_CONFIG", "short", ETLConfiguration
        )

    assert error.value.code == "AI_TASK_POLICY_INVALID"
    provider.assert_not_called()
