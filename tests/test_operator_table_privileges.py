from app.services.schema_compiler_service import operator_table_privileges


def test_append_grants_only_insert():
    assert operator_table_privileges("APPEND") == ("INSERT",)


def test_upsert_grants_only_required_non_destructive_privileges():
    assert set(operator_table_privileges("UPSERT")) == {"SELECT", "INSERT", "UPDATE"}


def test_full_refresh_does_not_auto_grant_delete():
    assert operator_table_privileges("FULL_REFRESH") == ("INSERT",)
