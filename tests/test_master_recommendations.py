import pytest

from app.services.master_recommendation import (
    field_name_similarity,
    normalize_field_name,
    source_header_name,
)


@pytest.mark.parametrize(
    ("source", "master_field"),
    [
        ("Kode Produk", "product_code"),
        ("Nama Pelanggan", "customer_name"),
        ("TGL Transaksi", "transaction_date"),
        ("Jumlah Barang", "product_quantity"),
        ("Nama-Cabang", "branch_name"),
    ],
)
def test_name_recommendations_normalize_indonesian_and_english_terms(source, master_field):
    assert field_name_similarity(source, master_field) == 1.0


def test_name_recommendations_ignore_case_and_punctuation():
    assert normalize_field_name(" PRODUCT.Code ") == ("code", "product")
    assert field_name_similarity("PRODUCT.Code", "product_code") == 1.0


def test_source_header_extraction_supports_profile_column_payload():
    assert source_header_name({"source_column": "Kode Produk", "inferred_type": "text"}) == "Kode Produk"
    assert source_header_name({"name": "Kode Produk"}) == "Kode Produk"


def test_unrelated_names_do_not_receive_a_strong_match():
    assert field_name_similarity("Alamat Pelanggan", "product_price") < 0.55
