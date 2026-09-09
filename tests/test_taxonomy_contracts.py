import pytest
from pydantic import ValidationError

from app.schemas.configuration import ColumnMapping
from app.schemas.taxonomy import TaxonomyColumnBindingCreate, TaxonomyRecommendRequest


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


def test_binding_revision_defaults_to_zero_for_create():
    item = TaxonomyColumnBindingCreate(
        source_column="category", taxonomy_id="00000000-0000-0000-0000-000000000001", taxonomy_version=1
    )
    assert item.revision_no == 0
