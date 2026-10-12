"""Validate AI evidence against private staging without sending private values to AI."""

from app.core.exceptions import AppError
from app.services.profiling_service import digest

AI_REVIEW_POLICY_VERSION = "BE10-v3-advisory-values"
TEXT_CLEANSING_POLICY_VERSION = "text-trim-v1"


def verified_ai_issues(issues, rows, columns, masked_fields):
    accepted, discarded = [], []
    for issue in issues:
        number, column = issue["source_row"], issue["target_column"]
        if number not in rows or column not in columns:
            raise AppError("AI_REVIEW_INVALID", "Temuan AI menunjuk baris atau kolom di luar batch.", 409)
        reason = None
        if issue.get("issue_kind") == "EXACT_DUPLICATE":
            peer = issue.get("related_source_row")
            # Compare complete original business rows, never redacted AI payloads.
            if peer == number or peer not in rows or digest(rows[number]) != digest(rows[peer]):
                reason = "DUPLICATE_NOT_PROVEN"
        elif column in masked_fields:
            reason = "MASKED_VALUE_NOT_REVIEWABLE"
        if reason:
            discarded.append({"source_row": number, "target_column": column, "reason": reason})
        else:
            accepted.append(issue)
    return accepted, discarded


def split_ai_issues(issues):
    """Keep verified duplicates and privacy risks actionable; other AI findings are advice."""
    blockers, warnings = [], []
    for issue in issues:
        if issue.get("issue_kind") in ("EXACT_DUPLICATE", "PRIVACY_RISK"):
            blockers.append(issue)
        else:
            warnings.append({**issue, "severity": "WARN"})
    return blockers, warnings
