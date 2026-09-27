from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from pydantic import ValidationError

from app.core.exceptions import AppError
from app.models.ai_policy import AITaskPolicy
from app.schemas.ai_policy import AITaskPolicyCreate, AITaskPolicyUpdate
from app.services.ai_policy_service import AITaskPolicyService


def policy_payload():
    return AITaskPolicyCreate(
        code="taxonomy_review",
        purpose="TAXONOMY_RECOMMEND",
        prompt_version="taxonomy_recommend_v1.md",
        model="gpt-test",
        allowed_models=["gpt-test"],
    )


def test_ai_policy_requires_registered_prompt_and_model_membership():
    assert policy_payload().model == "gpt-test"
    with pytest.raises(ValidationError):
        AITaskPolicyCreate(
            code="bad", purpose="TAXONOMY_RECOMMEND", prompt_version="unknown.md",
            model="gpt-test", allowed_models=["gpt-test"],
        )
    with pytest.raises(ValidationError):
        AITaskPolicyCreate(
            code="bad_scope",
            purpose="ETL_CONFIG",
            prompt_version="etl_configuration_v1.md",
            model="gpt-test",
            allowed_models=["gpt-test"],
            data_product_code="SALES",
        )
    with pytest.raises(ValidationError):
        AITaskPolicyCreate(
            code="same_fallback",
            purpose="NL2SQL",
            prompt_version="nl2sql_v1.md",
            model="gpt-test",
            allowed_models=["gpt-test"],
            fallback_model="gpt-test",
        )
    with pytest.raises(ValidationError):
        AITaskPolicyCreate(
            code="small_context",
            purpose="NL2SQL",
            prompt_version="nl2sql_v1.md",
            model="gpt-test",
            allowed_models=["gpt-test"],
            max_context_chars=999,
        )


@pytest.mark.asyncio
async def test_nl2sql_policy_scope_rechecks_product_access(monkeypatch):
    service = AITaskPolicyService(
        Mock(), SimpleNamespace(tenant_id="tenant", id="editor", role="DATA_STEWARD")
    )
    service.semantic_repo.product = AsyncMock(return_value=SimpleNamespace(code="SALES"))
    monkeypatch.setattr(service, "allowed_models", lambda: {"gpt-test"})
    payload = AITaskPolicyCreate(
        code="sales_nl2sql",
        purpose="NL2SQL",
        prompt_version="nl2sql_v1.md",
        model="gpt-test",
        allowed_models=["gpt-test"],
        data_product_code="SALES",
    )

    await service.validate_model_assignment(payload)

    service.semantic_repo.product.assert_awaited_once_with("SALES", service.user)


@pytest.mark.asyncio
async def test_ai_policy_approval_requires_server_allowlist(monkeypatch):
    session = Mock()
    user = SimpleNamespace(tenant_id="tenant", id="reviewer")
    service = AITaskPolicyService(session, user)
    service.repo.get = AsyncMock(return_value=SimpleNamespace(
        id="policy", revision_no=1, status="DRAFT", model="gpt-test", allowed_models=["gpt-test"]
    ))
    monkeypatch.setattr(service, "allowed_models", lambda: {"gpt-approved"})
    with pytest.raises(AppError) as error:
        await service.approve("policy", SimpleNamespace(revision_no=1))
    assert error.value.code == "AI_MODEL_NOT_ALLOWLISTED"
    service.repo.get.assert_awaited_once_with(AITaskPolicy, "policy", lock=True)


@pytest.mark.asyncio
async def test_ai_policy_draft_update_uses_revision_and_invalidates_approval(monkeypatch):
    session = Mock()
    user = SimpleNamespace(tenant_id="tenant", id="editor")
    policy = SimpleNamespace(
        id="policy",
        code="old",
        purpose="NL2SQL",
        prompt_version="nl2sql_v1.md",
        model="gpt-test",
        allowed_models=["gpt-test"],
        revision_no=3,
        status="DRAFT",
        approved_by="reviewer",
        approved_at="yesterday",
    )
    service = AITaskPolicyService(session, user)
    service.repo.get = AsyncMock(return_value=policy)
    monkeypatch.setattr(service, "allowed_models", lambda: {"gpt-test", "gpt-next"})
    monkeypatch.setattr("app.services.ai_policy_service.record", lambda value: vars(value).copy())
    payload = AITaskPolicyUpdate(
        code="next",
        purpose="NL2SQL",
        prompt_version="nl2sql_v1.md",
        model="gpt-next",
        allowed_models=["gpt-test", "gpt-next"],
        revision_no=3,
    )

    result = await service.update("policy", payload)

    assert result["revision_no"] == 4 and result["model"] == "gpt-next"
    assert result["approved_by"] is None and result["approved_at"] is None
    audit = session.add.call_args.args[0]
    assert audit.event == "ai_task_policy.updated"
    with pytest.raises(AppError) as failure:
        await service.update("policy", payload)
    assert failure.value.code == "AI_TASK_POLICY_REVISION_CONFLICT"
