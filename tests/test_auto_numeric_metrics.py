from app.schemas.configuration import ETLConfiguration, MetricDefinition
from app.services.numeric_metric_service import (
    add_default_numeric_metrics,
    backfill_data_product_numeric_metrics,
)


def make_configuration():
    return ETLConfiguration.model_validate(
        {
            "dataset_business_name": "Penjualan",
            "grain": "Satu baris per transaksi",
            "target_table": "sales",
            "load_strategy": "FULL_REFRESH",
            "columns": [
                {
                    "source_column": "Units",
                    "target_column": "units",
                    "target_type": "integer",
                    "business_name": "Jumlah unit",
                },
                {
                    "source_column": "Value",
                    "target_column": "value",
                    "target_type": "numeric",
                    "business_name": "Nilai",
                },
                {
                    "source_column": "Ratio",
                    "target_column": "percentage_ratio",
                    "target_type": "numeric",
                    "business_name": "Persentase",
                },
                {
                    "source_column": "Sequence",
                    "target_column": "sequence",
                    "target_type": "bigint",
                    "is_business_key": True,
                    "nullable": False,
                    "business_name": "Nomor",
                },
                {
                    "source_column": "Name",
                    "target_column": "name",
                    "target_type": "text",
                },
                {
                    "source_column": "Private Number",
                    "target_column": "private_number",
                    "target_type": "bigint",
                    "pii_classification": "HIGH",
                },
            ],
            "semantic": {
                "code": "SALES",
                "dimensions": ["name"],
                "metrics": [],
            },
        }
    )


def test_non_master_numeric_columns_are_added_as_metrics_with_safe_key_aggregation():
    config = make_configuration()

    added = add_default_numeric_metrics(config, "NON_MASTER")

    assert added == ["units", "value", "percentage_ratio", "sequence"]
    metrics = {metric.column: metric for metric in config.semantic.metrics}
    assert metrics["units"].aggregation == "sum"
    assert metrics["value"].aggregation == "sum"
    assert metrics["percentage_ratio"].aggregation == "avg"
    assert metrics["sequence"].aggregation == "count_distinct"
    assert "private_number" not in metrics
    assert all(metric.code.startswith("metric_") for metric in metrics.values())


def test_master_columns_are_not_automatically_added_as_metrics():
    config = make_configuration()

    assert add_default_numeric_metrics(config, "MASTER") == []
    assert config.semantic.metrics == []


def test_existing_metric_is_preserved_and_not_duplicated():
    config = make_configuration()
    config.semantic.metrics.append(
        MetricDefinition(
            code="unit_total",
            column="units",
            aggregation="avg",
            label="Rata-rata unit",
        )
    )

    added = add_default_numeric_metrics(config, "NON_MASTER")

    assert added == ["value", "percentage_ratio", "sequence"]
    assert len([metric for metric in config.semantic.metrics if metric.column == "units"]) == 1
    assert next(metric for metric in config.semantic.metrics if metric.column == "units").aggregation == "avg"


def test_generated_metric_labels_are_unique_when_business_names_repeat():
    config = make_configuration()
    config.columns[1].business_name = "Jumlah unit"

    add_default_numeric_metrics(config, "NON_MASTER")

    labels = [metric.label.casefold() for metric in config.semantic.metrics]
    assert len(labels) == len(set(labels))


def test_existing_non_master_product_backfill_is_idempotent_and_bumps_semantic_version_once():
    from types import SimpleNamespace

    config = make_configuration()
    product = SimpleNamespace(
        status="ACTIVE",
        columns=[column.model_dump(mode="json") for column in config.columns],
        metrics=[],
        version=4,
    )

    added = backfill_data_product_numeric_metrics(product, "NON_MASTER")
    assert added == ["units", "value", "percentage_ratio", "sequence"]
    assert product.version == 5

    assert backfill_data_product_numeric_metrics(product, "NON_MASTER") == []
    assert product.version == 5


def test_backfill_skips_master_and_inactive_products():
    from types import SimpleNamespace

    config = make_configuration()
    product = SimpleNamespace(
        status="ACTIVE",
        columns=[column.model_dump(mode="json") for column in config.columns],
        metrics=[],
        version=2,
    )

    assert backfill_data_product_numeric_metrics(product, "MASTER") == []
    assert product.version == 2
    product.status = "SUSPENDED"
    assert backfill_data_product_numeric_metrics(product, "NON_MASTER") == []
    assert product.version == 2
