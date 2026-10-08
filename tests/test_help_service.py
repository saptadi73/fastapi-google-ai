from pathlib import Path
from types import SimpleNamespace

import pytest

from app.schemas.help import HelpAnswer, HelpCitation, HelpQuestion
from app.services.help_service import HelpService, KnowledgeBase


def article(path: Path, article_id: str, title: str, audiences: str, routes: str, body: str):
    path.write_text(
        f"---\nid: {article_id}\ntitle: {title}\nsummary: Ringkasan {title}\n"
        f"routes: [{routes}]\naudiences: [{audiences}]\nsource: docs/source.md\n---\n{body}\n",
        encoding="utf-8",
    )


def test_knowledge_search_respects_role_and_route(tmp_path):
    article(tmp_path / "public.md", "dashboard", "Dashboard", '"*"', '"/dashboard"', "chart penjualan")
    article(tmp_path / "admin.md", "admin", "Administrasi", '"PLATFORM_ADMIN"', '"/admin/*"', "kelola pengguna")
    knowledge = KnowledgeBase(tmp_path)

    assert [item.article_id for item in knowledge.search("chart", "VIEWER", "/dashboard")] == ["dashboard"]
    assert not knowledge.search("kelola pengguna", "VIEWER", "/admin/users")
    assert knowledge.search("kelola pengguna", "PLATFORM_ADMIN", "/admin/users")[0].article_id == "admin"


@pytest.mark.parametrize(
    "question,role,route,expected",
    [
        ("contoh isi taxonomy dan term", "DATA_STEWARD", "/taxonomies", "contoh-isian-taxonomy"),
        ("contoh pengisian yurisdiksi", "PLATFORM_ADMIN", "/admin", "contoh-isian-atribut-akses"),
        ("apa isi unit pemilik sumber", "SOURCE_OWNER", "/workspace", "contoh-isian-sumber-google-sheet"),
        ("contoh master cabang", "VIEWER", "/dashboard", "contoh-isian-master-dan-analitik"),
    ],
)
def test_example_questions_find_relevant_knowledge(question, role, route, expected):
    assert KnowledgeBase().search(question, role, route)[0].article_id == expected


def test_master_relation_question_retrieves_binding_guidance():
    articles = KnowledgeBase().search(
        "bagaimana menentukan field sumber berelasi dengan master",
        "SOURCE_OWNER",
        "/sources/source-id/sheets/sheet-id/column-bindings",
    )
    article_ids = {item.article_id for item in articles}
    assert "master-dan-taxonomy" in article_ids
    assert "contoh-isian-master-dan-analitik" in article_ids


@pytest.mark.asyncio
async def test_help_answer_only_keeps_retrieved_citations(tmp_path):
    article(tmp_path / "guide.md", "guide", "Panduan", '"*"', '"/guide"', "daftarkan sumber lalu profiling")

    class AI:
        async def generate(self, user, purpose, context, schema):
            assert purpose == "USER_HELP"
            return HelpAnswer(
                answer="Daftarkan sumber lalu jalankan profiling.",
                citations=[
                    HelpCitation(article_id="guide", title="judul dari model diabaikan"),
                    HelpCitation(article_id="invented", title="tidak tersedia"),
                ],
            ), {"ai_model": "test"}

    service = HelpService(
        SimpleNamespace(role="VIEWER", id="user", tenant_id="tenant"), KnowledgeBase(tmp_path), AI()
    )
    answer, meta = await service.ask(HelpQuestion(question="bagaimana daftar sumber", route="/guide"))

    assert answer.citations == [HelpCitation(article_id="guide", title="Panduan")]
    assert meta == {"ai_model": "test"}


@pytest.mark.asyncio
async def test_help_does_not_call_ai_without_context(tmp_path):
    class AI:
        async def generate(self, *_args):
            raise AssertionError("AI must not be called")

    service = HelpService(SimpleNamespace(role="VIEWER"), KnowledgeBase(tmp_path), AI())
    answer = await service.ask(HelpQuestion(question="pertanyaan tidak dikenal"))
    assert answer.insufficient_context is True

