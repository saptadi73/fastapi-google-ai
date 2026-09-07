import pytest

from app.core.exceptions import AppError
from app.services.profiling_service import infer_type, normalize_identifier, profile_values


@pytest.mark.parametrize(
    "raw,expected",
    [("Total Harga (Rp)", "total_harga_rp"), ("2026", "col_2026"), ("", "col_"), ("Café", "cafe")],
)
def test_normalize(raw, expected):
    assert normalize_identifier(raw) == expected


@pytest.mark.parametrize(
    "values,expected",
    [
        (["001", "002"], "text"),
        ([1, 2], "bigint"),
        ([1.2, 2], "numeric"),
        ([True, False], "boolean"),
        (["2026-09-01"], "date"),
        (["NaN"], "text"),
        ([], "text"),
    ],
)
def test_infer(values, expected):
    assert infer_type(values) == expected


def test_fingerprint_and_masking(sheet_values):
    first = profile_values(sheet_values, "Sales")
    sheet_values[1][3] = 777
    assert profile_values(sheet_values, "Sales")["fingerprint"] == first["fingerprint"]
    sheet_values[0][3] = "New Total"
    assert profile_values(sheet_values, "Sales")["fingerprint"] != first["fingerprint"]
    assert first["columns"][0]["sample_masked"] == ["[REDACTED]"] * 3


@pytest.mark.parametrize("values", [[], [["A", "A"]], [["A", ""]], [["A"], [1, 2]], [["A!", "A?"]]])
def test_bad_headers(values):
    with pytest.raises(AppError):
        profile_values(values, "test")
