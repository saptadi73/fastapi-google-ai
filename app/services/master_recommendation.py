import re
import unicodedata
from difflib import SequenceMatcher

_TOKEN_ALIASES = {
    "kode": "code",
    "kod": "code",
    "produk": "product",
    "barang": "product",
    "item": "product",
    "pelanggan": "customer",
    "klien": "customer",
    "cabang": "branch",
    "outlet": "branch",
    "departemen": "department",
    "divisi": "department",
    "karyawan": "employee",
    "pegawai": "employee",
    "transaksi": "transaction",
    "penjualan": "sales",
    "nama": "name",
    "tanggal": "date",
    "tgl": "date",
    "wilayah": "region",
    "area": "region",
    "kategori": "category",
    "jenis": "category",
    "jumlah": "quantity",
    "kuantitas": "quantity",
    "qty": "quantity",
    "nilai": "amount",
    "harga": "price",
    "alamat": "address",
    "telepon": "phone",
    "telp": "phone",
    "pemasok": "supplier",
    "vendor": "supplier",
}
_IGNORED_TOKENS = {"data", "field", "master", "source", "ref", "reference"}


def normalize_field_name(value: str) -> tuple[str, ...]:
    """Normalize source/master names across casing, punctuation, and common ID/EN terms."""
    folded = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().casefold()
    tokens = re.findall(r"[a-z0-9]+", folded)
    return tuple(sorted({_TOKEN_ALIASES.get(token, token) for token in tokens if token not in _IGNORED_TOKENS}))


def field_name_similarity(source_name: str, master_field: str) -> float:
    source_tokens = normalize_field_name(source_name)
    target_tokens = normalize_field_name(master_field)
    if not source_tokens or not target_tokens:
        return 0.0
    if source_tokens == target_tokens:
        return 1.0

    source = " ".join(source_tokens)
    target = " ".join(target_tokens)
    left, right = set(source_tokens), set(target_tokens)
    jaccard = len(left & right) / len(left | right)
    sequence = SequenceMatcher(None, source, target).ratio()
    return round(0.65 * jaccard + 0.35 * sequence, 3)


def source_header_name(header) -> str:
    if isinstance(header, dict):
        value = header.get("source_column", header.get("name", header.get("header", "")))
    else:
        value = header
    return str(value or "").strip()


def field_match_reason(score: float, source_name: str, master_field: str) -> str:
    if normalize_field_name(source_name) == normalize_field_name(master_field):
        return "Nama cocok setelah normalisasi atau padanan istilah."
    if score < 0.68:
        return "Kemiripan nama rendah; periksa arti dan nilai kolom dengan teliti."
    return "Ada kemiripan sebagian pada nama; periksa arti dan nilai kolom."

