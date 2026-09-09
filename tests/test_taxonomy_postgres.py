import pytest
from test_integration import context as context
from test_integration import onboard, request

pytestmark = pytest.mark.integration


async def test_taxonomy_metadata_and_binding_approval_survive_http_roundtrip(context, config_data):
    _, sheet, _ = await onboard(context, config_data)
    taxonomy = (await request(context, "POST", "/taxonomies", expected=201,
                              data={"code": "category", "name": "Category"}))["data"]
    assert len(taxonomy["fingerprint"]) == len(taxonomy["snapshot_hash"]) == 64
    assert taxonomy["created_by"] and taxonomy["approved_by"] is None
    parent = (await request(context, "POST", f"/taxonomies/{taxonomy['id']}/terms", expected=201,
                            data={"code": "beverage", "label": "Beverage"}))["data"]
    child = (await request(context, "POST", f"/taxonomies/{taxonomy['id']}/terms", expected=201,
                           data={"code": "tea", "label": "Tea", "parent_id": parent["id"]}))["data"]
    assert child["created_by"] == taxonomy["created_by"] and len(child["snapshot_hash"]) == 64
    approved = (await request(context, "POST", f"/taxonomies/{taxonomy['id']}/approve",
                              who="approver"))["data"]
    assert approved["approved_by"] != taxonomy["created_by"] and approved["approved_at"]
    persisted = (await request(context, "GET", "/taxonomies"))["data"][0]
    assert persisted["approved_by"] == approved["approved_by"]
    path = f"/taxonomies/source-sheets/{sheet}/column-bindings"
    binding = (await request(context, "PUT", path, data={
        "source_column": "Cabang", "taxonomy_id": taxonomy["id"], "taxonomy_version": approved["version"],
    }))["data"]
    await request(context, "POST", f"/taxonomies/column-bindings/{binding['id']}/approve", who="approver",
                  data={"revision_no": binding["revision_no"]})
    persisted = (await request(context, "GET", path))["data"][0]
    assert persisted["status"] == "APPROVED" and persisted["approved_by"] == approved["approved_by"]
    assert persisted["approved_at"] and persisted["created_by"] == taxonomy["created_by"]
    for url in (path, f"/taxonomies/{taxonomy['id']}/terms"):
        await request(context, "GET", url, who="outsider", expected=404)
    await request(context, "POST", f"/taxonomies/{taxonomy['id']}/terms", who="outsider", expected=404,
                  data={"code": "intruder", "label": "Intruder"})
