"""Bounded, advisory recommendations restricted to the current approved term set."""
from pydantic import ValidationError

from app.core.exceptions import AppError
from app.models.taxonomy import Taxonomy, TaxonomyTerm
from app.repositories.base import TenantRepository
from app.schemas.taxonomy import TaxonomyAIResult
from app.services.audit_service import audit
from app.services.openai_service import OpenAIService
from app.services.profiling_service import canonical_json, digest


async def recommend_taxonomy(session, user, taxonomy_id, data):
    repo = TenantRepository(session, user.tenant_id)

    async def snapshot(lock=False):
        taxonomy = await repo.get(Taxonomy, taxonomy_id, lock=lock)
        await session.refresh(taxonomy)
        if not taxonomy.is_active or taxonomy.status != "APPROVED" or taxonomy.version != data.taxonomy_version:
            raise AppError("TAXONOMY_VERSION_STALE", "Pilih versi taxonomy approved terbaru.", 409)
        terms = (await session.scalars(repo.query(TaxonomyTerm).where(
            TaxonomyTerm.taxonomy_id == taxonomy.id, TaxonomyTerm.is_active.is_(True))
            .order_by(TaxonomyTerm.id).limit(501).execution_options(populate_existing=True))).all()
        if len(terms) > 500:
            raise AppError("TAXONOMY_AI_SCOPE_LIMIT", "Saran AI dibatasi sampai 500 term aktif.", 422)
        return {"taxonomy_id": taxonomy.id, "version": taxonomy.version, "name": taxonomy.name,
                "terms": [{"id": t.id, "code": t.code, "label": t.label, "aliases": t.aliases,
                           "parent_id": t.parent_id} for t in terms]}

    before = await snapshot()
    context = canonical_json({**before, "limit": data.limit,
                              "inputs": [{"input_index": i, "value": value} for i, value in enumerate(data.values)]})
    if len(context.encode("utf-8")) > 150_000:
        raise AppError("TAXONOMY_AI_SCOPE_LIMIT", "Konteks taxonomy terlalu besar untuk saran AI.", 422)
    parsed, metadata = await OpenAIService().generate(user, "TAXONOMY_RECOMMEND", context, TaxonomyAIResult)
    try:
        parsed = TaxonomyAIResult.model_validate(parsed)
    except ValidationError:
        raise AppError("TAXONOMY_AI_RESULT_INVALID", "Saran AI tidak memenuhi kontrak.", 422) from None
    current = await snapshot(lock=True)
    if digest(before) != digest(current):
        raise AppError("TAXONOMY_VERSION_STALE", "Taxonomy berubah selama pembuatan saran; muat ulang.", 409)
    terms = {t["id"]: t for t in current["terms"]}
    items = parsed.recommendations
    if sorted(item.input_index for item in items) != list(range(len(data.values))):
        raise AppError("TAXONOMY_AI_RESULT_INVALID", "Cakupan input saran AI tidak lengkap/duplikat.", 422)
    recommendations = []
    for item in sorted(items, key=lambda item: item.input_index):
        ids = [str(c.term_id) for c in item.candidates]
        if len(ids) > data.limit or len(ids) != len(set(ids)) or any(term_id not in terms for term_id in ids):
            raise AppError("TAXONOMY_AI_RESULT_INVALID", "Kandidat AI bukan term aktif yang diizinkan.", 422)
        recommendations.append({"input_index": item.input_index, "value": data.values[item.input_index],
                                "candidates": [{"term": terms[str(c.term_id)], "confidence": c.confidence}
                                               for c in sorted(item.candidates, key=lambda c: c.confidence, reverse=True)],
                                "requires_confirmation": True})
    audit(session, user, "taxonomy.ai_recommended", str(taxonomy_id), taxonomy_version=data.taxonomy_version,
          input_count=len(data.values), **metadata)
    return {"taxonomy_id": str(taxonomy_id), "taxonomy_version": data.taxonomy_version,
            "recommendation_kind": "GENERATIVE", "recommendations": recommendations, **metadata}
