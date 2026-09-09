from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.core.exceptions import AppError
from app.schemas.configuration import ColumnMapping
from app.schemas.taxonomy import TaxonomyColumnBindingCreate, TaxonomyRecommendRequest
from app.services.taxonomy_validation_service import canonicalize_rows, validate_rows


def test_taxonomy_column_requires_id_for_version_or_required():
    with pytest.raises(ValidationError):
        ColumnMapping(source_column="category", target_column="category", target_type="text", taxonomy_version=2)
    with pytest.raises(ValidationError):
        ColumnMapping(source_column="category", target_column="category", target_type="text", taxonomy_required=True)


def test_taxonomy_column_accepts_versioned_binding():
    item = ColumnMapping(
        source_column="category", target_column="category", target_type="text",
        taxonomy_id="00000000-0000-0000-0000-000000000001", taxonomy_version=1, taxonomy_required=True,
    )
    assert item.taxonomy_version == 1 and item.taxonomy_required is True


def test_recommendation_limit_is_bounded():
    assert TaxonomyRecommendRequest(values=["Minuman"], limit=3).limit == 3
    with pytest.raises(ValidationError):
        TaxonomyRecommendRequest(values=["Minuman"], limit=11)


@pytest.mark.parametrize("values", [[" "], ["x" * 501], ["x"] * 51])
def test_ai_recommendation_input_limits(values):
    from app.schemas.taxonomy import TaxonomyAIRecommendRequest

    with pytest.raises(ValidationError):
        TaxonomyAIRecommendRequest(taxonomy_version=1, values=values)


def test_binding_revision_defaults_to_zero_for_create():
    item = TaxonomyColumnBindingCreate(
        source_column="category", taxonomy_id="00000000-0000-0000-0000-000000000001", taxonomy_version=1
    )
    assert item.revision_no == 0


@pytest.mark.parametrize("patch", [{}, {"taxonomy_version": 1, "target_type": "integer"}])
def test_taxonomy_mapping_requires_version_and_text(patch):
    with pytest.raises(ValidationError):
        ColumnMapping.model_validate({"source_column": "category", "target_column": "category", "target_type": "text",
                                      "taxonomy_id": "00000000-0000-0000-0000-000000000001", **patch})


def test_blank_alias_cannot_satisfy_required_taxonomy():
    column = SimpleNamespace(taxonomy_required=True, source_column="Category")
    term = SimpleNamespace(code="tea", label=" ", aliases=[""], is_active=True)
    context = {"category": (column, None, None, [term])}
    row = SimpleNamespace(source_row=2, transformed_data={"category": " "}, corrected_data={})
    with pytest.raises(AppError) as exc:
        validate_rows(context, [row])
    assert exc.value.code == "TAXONOMY_VALUE_INVALID"


def test_unsupported_taxonomy_normalization_rejected():
    with pytest.raises(ValidationError):
        TaxonomyColumnBindingCreate(source_column="category", taxonomy_id="00000000-0000-0000-0000-000000000001",
                                    taxonomy_version=1, normalization="FUZZY_AUTO")


def test_canonical_normalization_preserves_raw_and_blocks_new_key_collisions():
    column = SimpleNamespace(taxonomy_required=True, source_column="Category", target_column="category",
                             is_business_key=True, is_primary_key=False)
    term = SimpleNamespace(code="tea", label="Tea", aliases=["Teh"], is_active=True)
    context = {"category": (column, None, None, [term])}
    config = SimpleNamespace(columns=[column])
    rows = [SimpleNamespace(source_row=n, raw_data={"Category": v}, transformed_data={"category": v},
                            corrected_data={}) for n, v in [(2, " TEH "), (3, "Tea")]]
    with pytest.raises(AppError) as exc:
        canonicalize_rows(context, rows, config)
    assert exc.value.code == "TAXONOMY_KEY_COLLISION"
    assert all(not row.corrected_data for row in rows)
    canonicalize_rows(context, rows[:1], config)
    assert rows[0].corrected_data == {"category": "tea"}
    assert rows[0].raw_data == {"Category": " TEH "} and rows[0].transformed_data == {"category": " TEH "}
