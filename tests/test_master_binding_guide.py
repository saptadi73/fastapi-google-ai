from pathlib import Path

import pytest

from app.services.help_service import KnowledgeBase
from scripts.export_master_binding_guide import documents


def test_master_guide_generated_documents_are_current_and_not_truncated():
    for path, expected in documents().items():
        assert path.read_text(encoding="utf-8") == expected
    articles = [
        a for a in KnowledgeBase().articles("SOURCE_OWNER") if a.article_id.startswith("binding-master-")
    ]
    assert len(articles) == 3 and all(len(a.body) <= 6000 for a in articles)


@pytest.mark.parametrize(
    "question,route,expected,phrase",
    [
        (
            "binding master Registry storage Simpan binding dry-run Setujui binding",
            "/masters",
            "binding-master-langkah",
            "tidak ada langkah submit terpisah",
        ),
        (
            "MASTER_BINDING_REQUIRED binding APPROVED record kosong Apply",
            "/sources/source/sheets/sheet/master-binding",
            "binding-master-pemuatan",
            "Buat batch review/import",
        ),
        (
            "binding kolom referensi BISNIS is_active boolean business key",
            "/sources/source/sheets/sheet/column-bindings",
            "binding-master-referensi",
            "UUID internal tidak perlu disalin",
        ),
    ],
)
def test_helper_retrieves_the_right_binding_workflow(question, route, expected, phrase):
    articles = KnowledgeBase().search(question, "TECHNICAL_APPROVER", route)
    article = next(a for a in articles if a.article_id == expected)
    assert phrase in article.body


def test_binding_tutorial_uses_available_screen_actions():
    # Avoid sending users to the nonexistent submit button on tab bindings.
    body = (Path(__file__).resolve().parents[1] / "docs/PANDUAN_BINDING_MASTER.md").read_text(
        encoding="utf-8"
    )
    assert "Simpan binding & dry-run" in body and "Setujui binding" in body
    assert "Record kanonis" in body and "binding APPROVED belum berarti record sudah dimuat" in body
