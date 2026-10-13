from app.services.access_service import _policy_scope_matches


def test_allow_policy_defaults_to_unit_and_domain_without_jurisdiction_or_department():
    unit, domain, jurisdiction, department = "unit", "domain", "jurisdiction", "department"
    assert _policy_scope_matches(
        "ALLOW",
        {unit, domain},
        [unit, domain],
        {unit, domain},
    )
    assert not _policy_scope_matches(
        "ALLOW",
        {unit, domain},
        [unit],
        {unit, domain},
    )
    assert not _policy_scope_matches(
        "ALLOW",
        {unit, domain},
        [unit, domain, jurisdiction, department],
        {unit, domain},
    )
    assert _policy_scope_matches(
        "ALLOW",
        {unit, domain},
        [unit, domain, jurisdiction, department],
        {unit, domain, jurisdiction, department},
    )


def test_deny_policy_remains_effective_without_baseline_scope_requirement():
    assert _policy_scope_matches("DENY", {"unit", "domain"}, [], set())
