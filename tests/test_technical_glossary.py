from pathlib import Path

import pytest

from app.services.help_service import KnowledgeBase


def test_glossary_documents_are_synchronized():
    from scripts.export_technical_glossary import documents

    for path, content in documents().items():
        assert Path(path).read_text(encoding="utf-8") == content


@pytest.mark.parametrize("question,group,phrase", [
    ("arti istilah grain business key primary key nullable", "dasar", "Satu baris mewakili apa?"),
    ("penjelasan istilah taxonomy master data alias cleansing", "rujukan", "Daftar kategori atau istilah yang disepakati"),
    ("arti istilah metrik dimensi denominator waktu pengambilan", "analitik", "berbeda dari periode yang dilaporkan"),
    ("istilah APPEND UPSERT FULL_REFRESH deploy sync", "operasi", "bisa terhitung ganda"),
])
def test_non_technical_reader_can_retrieve_glossary(question, group, phrase):
    articles = KnowledgeBase().search(question, "TECHNICAL_APPROVER", "/workspace")
    article = next(item for item in articles if item.article_id == f"istilah-teknis-{group}")
    assert phrase in article.body and len(article.body) <= 6000
