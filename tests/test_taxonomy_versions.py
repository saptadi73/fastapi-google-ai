"""Published taxonomy history and revision races against PostgreSQL."""
import asyncio
from uuid import uuid4

import pytest
from test_integration import context as context
from test_integration import request
from test_taxonomy_workflow import batch, taxonomy

pytestmark = pytest.mark.integration


async def draft(ctx, definition):
    return (await request(ctx, "POST", f"/taxonomies/{definition['id']}/versions", expected=201,
                          data={"base_version": definition["version"]}))["data"]


async def test_publish_preserves_history_identity_and_invalidates_old_binding(context, config_data):
    definition, terms, review, _, _ = await batch(context, config_data)
    version = await draft(context, definition)
    assert (await draft(context, definition))["id"] == version["id"]
    root = next(t for t in version["definition_json"]["terms"] if t["code"] == "alpha")
    root["label"] = "New alpha"
    child = {"id": str(uuid4()), "code": "child", "label": "Child", "parent_id": root["id"],
             "aliases": ["New child"], "is_active": True}
    path = f"/taxonomies/versions/{version['id']}"
    edited = (await request(context, "PUT", path, data={"revision_no": 1, "terms": [child, root]}))["data"]
    live = (await request(context, "GET", f"/taxonomies/{definition['id']}/terms"))["data"]
    assert next(t for t in live if t["code"] == "alpha")["label"] == "Alpha"
    await request(context, "POST", path + "/approve", data={"revision_no": 2}, expected=403)
    published = (await request(context, "POST", path + "/approve", who="approver",
                               data={"revision_no": edited["revision_no"]}))["data"]
    assert published["status"] == "APPROVED" and published["version"] == definition["version"] + 1
    live = (await request(context, "GET", f"/taxonomies/{definition['id']}/terms"))["data"]
    assert next(t for t in live if t["code"] == "alpha")["id"] == terms[0]["id"]
    assert next(t for t in live if t["code"] == "alpha")["label"] == "New alpha"
    assert next(t for t in live if t["code"] == "child")["parent_id"] == terms[0]["id"]
    assert not next(t for t in live if t["code"] == "beta")["is_active"]
    history = (await request(context, "GET", f"/taxonomies/{definition['id']}/versions"))["data"]
    assert len(history["items"]) == 2 and not history["has_more"]
    old = history["items"][1]
    assert next(t for t in old["definition_json"]["terms"] if t["code"] == "alpha")["label"] == "Alpha"
    await request(context, "PUT", path, expected=409, data={"revision_no": 3, "terms": [root]})
    await request(context, "POST", path + "/approve", who="approver", expected=409, data={"revision_no": 3})
    await request(context, "GET", path, who="outsider", expected=404)
    error = await request(context, "POST", f"/import-reviews/{review['id']}/preview", expected=409,
                          data={"revision_no": 1})
    assert error["errors"][0]["code"] == "IMPORT_STALE_REVIEW"


async def test_draft_validation_and_concurrent_revision(context):
    definition, _ = await taxonomy(context)
    version = await draft(context, definition)
    terms = version["definition_json"]["terms"]
    path = f"/taxonomies/versions/{version['id']}"
    await request(context, "PUT", path, expected=422,
                  data={"revision_no": 1, "terms": [{**terms[0], "parent_id": terms[0]["id"]}]})
    await request(context, "PUT", path, expected=409,
                  data={"revision_no": 1, "terms": [{**terms[0], "code": "replacement"}]})
    await request(context, "PUT", path, expected=409,
                  data={"revision_no": 1, "terms": [{**terms[0], "id": str(uuid4())}]})
    responses = await asyncio.gather(*(context.client.put("/api/v1" + path, headers=context.headers["admin"],
                                                         json={"revision_no": 1, "terms": terms}) for _ in range(2)))
    assert sorted(r.status_code for r in responses) == [200, 409]
    stored = (await request(context, "GET", path))["data"]
    assert stored["revision_no"] == 2 and stored["status"] == "DRAFT"
