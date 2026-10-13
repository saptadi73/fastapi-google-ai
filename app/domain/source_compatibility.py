SOURCE_ACCESS_METADATA_FIELDS = (
    "owner_unit_id",
    "business_domain_id",
    "jurisdiction_id",
    "purpose_id",
    "data_owner_user_id",
    "data_steward_user_id",
    "sensitivity",
)


def classify_source_compatibility(
    *, access_metadata, access_status, review_status, reviewed_by, reviewed_at
):
    """Describe the next safe step for an existing source without granting access."""
    metadata = access_metadata or {}
    missing_fields = [field for field in SOURCE_ACCESS_METADATA_FIELDS if not metadata.get(field)]
    if missing_fields:
        action = "OWNER_METADATA_REQUIRED"
    elif review_status == "REJECTED":
        action = "SOURCE_REVIEW_REJECTED"
    elif review_status != "APPROVED" or not reviewed_by or not reviewed_at:
        action = "SOURCE_REVIEW_REQUIRED"
    elif access_status != "POLICY_APPROVED":
        action = "OWNER_ACCESS_ACTIVATION_REQUIRED"
    else:
        action = "READY_NO_BACKFILL"
    return {"action": action, "missing_metadata_fields": missing_fields}
