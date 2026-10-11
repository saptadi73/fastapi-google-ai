import json
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


@pytest.mark.parametrize(
    "question,role,route",
    [
        ("menambah kolom date periode w1 january profiling ulang", "DATA_STEWARD", "/workspace"),
        ("ubah header sumber schema migrasi", "SOURCE_OWNER", "/sources"),
        ("query tanggal january w1 periode", "VIEWER", "/dashboard"),
        ("tambah field master nullable", "DATA_STEWARD", "/masters/master-id/storage"),
    ],
)
def test_source_evolution_guidance_is_retrieved_within_provider_budget(question, role, route):
    articles = KnowledgeBase().search(question, role, route)
    context = "\n".join(item.body[:6000] for item in articles)

    assert "profiling ulang" in context
    assert "migrasi" in context
    if "nullable" in question:
        assert "Field baru nullable" in context or "field nullable" in context
    else:
        assert "january" in context
        assert "tahun" in context


@pytest.mark.asyncio
async def test_help_passes_source_date_and_migration_guidance_to_provider():
    class AI:
        async def generate(self, user, purpose, context, schema):
            payload = json.loads(context)
            content = "\n".join(item["content"] for item in payload["knowledge_articles"])
            assert purpose == "USER_HELP"
            assert all(len(item["content"]) <= 6000 for item in payload["knowledge_articles"])
            assert "Workspace tidak menulis data ke Sheet" in content
            assert "migrasi manual yang direview" in content
            assert "jangan" in content.lower() and "menebak tanggal" in content
            assert "periode mulai dan selesai" in content
            article_id = payload["knowledge_articles"][0]["id"]
            return HelpAnswer(
                answer="Ubah sumber, profiling ulang, dan review draft; schema target perlu migrasi.",
                citations=[HelpCitation(article_id=article_id, title="Panduan")],
            ), {"ai_model": "test"}

    service = HelpService(SimpleNamespace(role="DATA_STEWARD"), ai=AI())
    answer, _ = await service.ask(
        HelpQuestion(question="menambah kolom date periode w1 january profiling ulang", route="/workspace")
    )
    assert answer.citations


def test_all_knowledge_articles_fit_provider_context():
    articles = KnowledgeBase().articles("PLATFORM_ADMIN")
    assert len({item.article_id for item in articles}) == len(articles)
    assert all(len(item.body) <= 6000 for item in articles)


def test_catalog_access_guidance_explains_separate_source_gate():
    articles = KnowledgeBase().search(
        "katalog kosong sumber ACTIVE policy assignment", "SOURCE_OWNER", "/workspace"
    )
    content = "\n".join(item.body[:6000] for item in articles)
    assert "POLICY_APPROVED" in content
    assert "DISCOVER/READ/QUERY" in content
    assert "admin berbeda" in content
    assert "AND" in content
    assert "Policy DATA_PRODUCT saja tidak menggantikan policy SOURCE" in content


@pytest.mark.parametrize(
    "route,expected",
    [
        ("/masters", "master-dan-taxonomy"),
        ("/taxonomies", "master-dan-taxonomy"),
        ("/admin", "pengguna-role-dan-akses"),
    ],
)
def test_help_topic_lists_include_registry_root_routes(route, expected):
    service = HelpService(SimpleNamespace(role="PLATFORM_ADMIN"), ai=object())
    assert expected in {item["id"] for item in service.list_articles(route=route)}


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
