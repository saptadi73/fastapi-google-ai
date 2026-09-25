import pytest
from pydantic import ValidationError

from app.schemas.configuration import ETLConfiguration


def test_metric_metadata_is_normalized_in_reviewed_configuration(config_data):
    config_data["semantic"]["metrics"][0].update(
        label=" Penjualan   Bersih ",
        description=" Total   setelah diskon ",
        synonyms=["Pendapatan   bersih", "Net revenue"],
        unit=" IDR ",
    )
    metric = ETLConfiguration.model_validate(config_data).semantic.metrics[0]
    assert metric.label == "Penjualan Bersih"
    assert metric.description == "Total setelah diskon"
    assert metric.synonyms == ["Pendapatan bersih", "Net revenue"]
    assert metric.unit == "IDR"


@pytest.mark.parametrize(
    "update",
    [
        {"synonyms": ["Revenue", " revenue "]},
        {"synonyms": ["x" * 101]},
        {"unit": "x" * 41},
        {"description": "x" * 1001},
    ],
)
def test_metric_metadata_rejects_invalid_values(config_data, update):
    config_data["semantic"]["metrics"][0].update(update)
    with pytest.raises(ValidationError):
        ETLConfiguration.model_validate(config_data)


def test_metric_terms_cannot_identify_another_metric(config_data):
    config_data["semantic"]["metrics"][0]["synonyms"] = ["Transaction count"]
    config_data["semantic"]["metrics"][1]["label"] = "transaction   COUNT"
    with pytest.raises(ValidationError, match="must not identify another metric"):
        ETLConfiguration.model_validate(config_data)
