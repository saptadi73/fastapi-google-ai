import os
from pathlib import Path

import pytest
from dotenv import dotenv_values

env = dotenv_values(Path(__file__).resolve().parents[1] / ".env")
test_url = os.getenv("TEST_DATABASE_URL") or env.get("TEST_DATABASE_URL")
if test_url:
    from app.core.test_database import validate_test_database

    validate_test_database(os.getenv("DATABASE_URL") or env["DATABASE_URL"], test_url)
    os.environ["DATABASE_URL"] = test_url
    os.environ["DATABASE_DDL_URL"] = ""
    os.environ["DATABASE_NL2SQL_URL"] = ""
    os.environ["OPENAI_API_KEY"] = ""
    os.environ["OPENAI_MODEL_ETL_CONFIG"] = ""
    os.environ["OPENAI_MODEL_NL2SQL"] = ""


def pytest_collection_modifyitems(items):
    if not test_url:
        for item in items:
            if "integration" in item.keywords:
                item.add_marker(
                    pytest.mark.skip(
                        reason="Run scripts/prepare_test_db.py to configure a separate TEST_DATABASE_URL"
                    )
                )


@pytest.fixture
def config_data():
    return {
        "dataset_business_name": "Penjualan",
        "grain": "Satu baris per transaksi",
        "target_table": "sales",
        "load_strategy": "UPSERT",
        "columns": [
            {
                "source_column": "ID",
                "target_column": "transaction_id",
                "target_type": "text",
                "nullable": False,
                "is_business_key": True,
            },
            {
                "source_column": "Tanggal",
                "target_column": "transaction_date",
                "target_type": "date",
                "transformation_codes": ["parse_date_id"],
            },
            {"source_column": "Cabang", "target_column": "branch_name", "target_type": "text"},
            {"source_column": "Total", "target_column": "net_amount", "target_type": "numeric"},
        ],
        "semantic": {
            "code": "SALES",
            "dimensions": ["transaction_date", "branch_name", "transaction_id"],
            "metrics": [
                {"code": "net_sales", "column": "net_amount", "aggregation": "sum"},
                {"code": "transaction_count", "column": "transaction_id", "aggregation": "count"},
            ],
        },
    }


@pytest.fixture
def sheet_values():
    return [
        ["ID", "Tanggal", "Cabang", "Total"],
        ["001", "2026-09-01", "Jakarta", 100],
        ["002", "2026-09-02", "Bandung", 200],
        ["003", "2026-09-03", "Jakarta", 50],
    ]
