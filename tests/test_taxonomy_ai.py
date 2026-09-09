"""HTTP/tenant/registry guards use PostgreSQL; provider results are controlled fixtures."""
import json
from uuid import uuid4

import pytest
from sqlalchemy import select, update
from test_integration import context as context
from test_integration import request
from test_taxonomy_workflow import taxonomy

from app.core.database import SessionFactory
from app.models.taxonomy import Taxonomy, TaxonomyTerm
from app.services.openai_service import OpenAIService

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("result_kind", ["valid", "empty", "unknown", "duplicate", "missing", "bad_score", "stale", "inactive"])
async def test_ai_recommendations_validate_scope_coverage_and_freshness(context, monkeypatch, result_kind):
    definition, terms = await taxonomy(context)
    async def generate(self, user, purpose, raw, schema):
        payload = json.loads(raw)
        assert purpose == "TAXONOMY_RECOMMEND" and payload["version"] == definition["version"]
        assert {t["id"] for t in payload["terms"]} == {t["id"] for t in terms}
        assert payload["inputs"] == [{"input_index": 0, "value": "first branch"}]
        candidates = [{"term_id": terms[0]["id"], "confidence": 0.8}]
        if result_kind == "unknown":
            candidates[0]["term_id"] = str(uuid4())
        if result_kind == "duplicate":
            candidates *= 2
        if result_kind == "empty":
            candidates = []
        if result_kind == "bad_score":
            candidates[0]["confidence"] = 2
        if result_kind in ("stale", "inactive"):
            async with SessionFactory() as session, session.begin():
                if result_kind == "stale":
                    await session.execute(update(Taxonomy).where(Taxonomy.id == definition["id"]).values(version=99))
                else:
                    await session.execute(update(TaxonomyTerm).where(TaxonomyTerm.id == terms[0]["id"]).values(is_active=False))
        return {"recommendations": [] if result_kind == "missing" else [{"input_index": 0, "candidates": candidates}]}, {
            "ai_model": "mock-model", "ai_response_id": "mock-response", "prompt_version": "taxonomy_recommend_v1.md"}
    monkeypatch.setattr(OpenAIService, "generate", generate)
    path = f"/taxonomies/{definition['id']}/recommend-terms-ai"
    body = {"taxonomy_version": definition["version"], "values": ["first branch"], "limit": 3}
    for who, expected in [("outsider", 404), ("viewer", 403), ("approver", 403)]:
        await request(context, "POST", path, who=who, data=body, expected=expected)
    expected = 200 if result_kind in ("valid", "empty") else 409 if result_kind in ("stale", "inactive") else 422
    response = await request(context, "POST", path, data=body, expected=expected)
    if result_kind in ("valid", "empty"):
        result = response["data"]
        assert result["recommendation_kind"] == "GENERATIVE"
        item = result["recommendations"][0]
        assert item["requires_confirmation"]
        if result_kind == "valid":
            assert item["candidates"][0]["term"]["id"] == terms[0]["id"]
        else:
            assert item["candidates"] == []
        async with SessionFactory() as session:
            stored = (await session.scalars(select(TaxonomyTerm).where(TaxonomyTerm.taxonomy_id == definition["id"]))).all()
            assert len(stored) == 2 and all(t.aliases == [" SHARED "] for t in stored)
    else:
        assert response["errors"][0]["code"] == ("TAXONOMY_VERSION_STALE" if expected == 409 else "TAXONOMY_AI_RESULT_INVALID")


async def test_ai_endpoint_reports_unconfigured_provider_without_fallback(context):
    definition, _ = await taxonomy(context)
    response = await request(context, "POST", f"/taxonomies/{definition['id']}/recommend-terms-ai", expected=503,
                             data={"taxonomy_version": definition["version"], "values": ["unknown"]})
    assert response["errors"][0]["code"] == "OPENAI_NOT_CONFIGURED"
