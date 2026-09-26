from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from pydantic import ValidationError

from app.core.exceptions import AppError
from app.models.ai_policy import AITaskPolicy
from app.schemas.ai_policy import AITaskPolicyCreate
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