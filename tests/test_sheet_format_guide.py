import json
from pathlib import Path

import pytest

from app.services.help_service import KnowledgeBase

ROOT = Path(__file__).resolve().parents[1]


def test_generated_sheet_guide_is_complete_and_bounded():
    from scripts.export_sheet_format_guide import documents

    for path, content in documents().items():
        assert path.read_text(encoding="utf-8") == content
    guide = json.loads((ROOT / "docs/google-sheet-format.json").read_text(encoding="utf-8"))
    assert all(section["blocks"] for section in guide["sections"])
    assert len({section["id"] for section in guide["sections"]}) == len(guide["sections"])


@pytest.mark.parametrize("question,expected,required", [
    ("format google sheet header kosong grain business key", "struktur", ["Header wajib terisi", "Business key tidak boleh NULL"]),
    ("data periodik waktu pengambilan measured_at collected_at period_start", "nilai-waktu", ["wajib", "collected_at", "period_start", "UTC"]),
    ("master istilah taxonomy metrik presisi denominator", "master-metrik", ["metrics=[]", "penyebut berbeda", "Expression rasio bebas belum didukung"]),
    ("action plan akurat bukti penyebab owner tenggat kualitas", "tindak-lanjut", ["cause_status", "due_date", "verifikasi hasil oleh manusia"]),
    ("asupan analitik strategi load UPSERT APPEND akses", "operasi", ["UPSERT", "hitungan ganda", "hak baca otomatis"]),
    ("contoh format KPI bulanan Action_Plan checklist", "contoh", ["KPI-202601-U01-RSP", "collected_at", "ACT-001", "Checklist"]),
])
def test_helper_finds_sheet_preparation_guidance_for_actual_reader(question, expected, required):
    articles = KnowledgeBase().search(question, "TECHNICAL_APPROVER", "/guide")
    article = next(a for a in articles if a.article_id == f"format-google-sheet-{expected}")
    assert len(article.body) <= 6000
    for phrase in required:
        assert phrase in article.body
