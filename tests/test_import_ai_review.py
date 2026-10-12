import pytest

from app.core.exceptions import AppError
from app.services.import_ai_review_service import split_ai_issues, verified_ai_issues


def finding(column="name", **kwargs):
    return {"source_row": 2, "target_column": column, "message": "Verify value", **kwargs}


def test_masked_values_cannot_create_false_blockers_but_unmasked_pii_is_retained():
    rows = {2: {"name": "Unit A", "month": "Jan"}, 3: {"name": "Unit B", "month": "Jan"}}
    genuine = finding("month")
    issues = [finding(), finding("month", issue_kind="EXACT_DUPLICATE", related_source_row=3), genuine]
    accepted, discarded = verified_ai_issues(issues, rows, {"name", "month"}, {"name"})
    assert accepted == [genuine]
    assert [item["reason"] for item in discarded] == ["MASKED_VALUE_NOT_REVIEWABLE", "DUPLICATE_NOT_PROVEN"]


@pytest.mark.parametrize("peer", [None, 2, 99])
def test_duplicate_requires_distinct_existing_peer(peer):
    accepted, discarded = verified_ai_issues([finding(issue_kind="EXACT_DUPLICATE", related_source_row=peer)], {2: {"name": "Unit A"}}, {"name"}, set())
    assert not accepted and discarded[0]["reason"] == "DUPLICATE_NOT_PROVEN"


def test_true_duplicate_retained_even_when_sensitive_field_is_masked():
    issue = finding(issue_kind="EXACT_DUPLICATE", related_source_row=102)
    accepted, discarded = verified_ai_issues([issue], {2: {"name": "Unit A"}, 102: {"name": "Unit A"}}, {"name"}, {"name"})
    assert accepted == [issue] and not discarded


@pytest.mark.parametrize("issue", [finding("unknown"), {**finding(), "source_row": 99}])
def test_out_of_batch_evidence_still_rejected(issue):
    with pytest.raises(AppError, match="Temuan AI"):
        verified_ai_issues([issue], {2: {"name": "Unit A"}}, {"name"}, {"name"})


def test_literal_redacted_in_public_column_is_not_filtered():
    issue = finding()
    accepted, discarded = verified_ai_issues([issue], {2: {"name": "[REDACTED]"}}, {"name"}, set())
    assert accepted == [issue] and not discarded


def test_only_verified_duplicate_and_privacy_risk_remain_blockers():
    duplicate = finding(issue_kind="EXACT_DUPLICATE", related_source_row=3)
    privacy = finding("contact", issue_kind="PRIVACY_RISK")
    advisory = finding("month")

    blockers, warnings = split_ai_issues([duplicate, privacy, advisory])

    assert blockers == [duplicate, privacy]
    assert warnings == [{**advisory, "severity": "WARN"}]
