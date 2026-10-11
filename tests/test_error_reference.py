import ast
import json
from pathlib import Path

import pytest

from app.services.help_service import KnowledgeBase

ROOT = Path(__file__).resolve().parents[1]
ROWS = json.loads((ROOT / "docs/error-responses.json").read_text(encoding="utf-8"))


def test_error_reference_matches_registered_codes_and_generated_documents():
    from scripts.export_error_reference import documents

    known = set()
    for path in (ROOT / "app").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        known.update(node.value for node in ast.walk(tree) if isinstance(node, ast.Constant) and isinstance(node.value, str))
    assert len({row["code"] for row in ROWS}) == len(ROWS)
    assert all(row["code"] in known for row in ROWS if row["kind"] != "legacy")
    for path, expected in documents().items():
        assert path.read_text(encoding="utf-8") == expected


@pytest.mark.parametrize("row", ROWS, ids=lambda row: row["code"])
def test_helper_retrieves_complete_error_table_for_reader_role(row):
    articles = KnowledgeBase().search(f"{row['code']} penyebab tindakan", "TECHNICAL_APPROVER", "/jobs")
    article = next(item for item in articles if item.article_id == f"error-response-{row['group']}")
    assert len(article.body) <= 6000
    assert f"| `{row['code']}` | {row['cause']} | {row['action']} |" in article.body
