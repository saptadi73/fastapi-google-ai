"""Validation shared by test provisioning and pytest, without importing application settings."""

import re

from sqlalchemy.engine import make_url


def validate_test_database(application_url: str, test_url: str):
    application = make_url(application_url)
    target = make_url(test_url)
    if target.drivername != "postgresql+asyncpg":
        raise ValueError("TEST_DATABASE_URL must use postgresql+asyncpg")
    if not target.database or not re.fullmatch(r"[a-z][a-z0-9_]*_test", target.database):
        raise ValueError("TEST_DATABASE_URL must use a database name ending in _test")
    # Reject matching database names even if the same server is addressed with different aliases/users.
    if target.database == application.database:
        raise ValueError("Test database must be different from the application database")
    return target
