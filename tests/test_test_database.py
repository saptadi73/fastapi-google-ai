import pytest

from app.core.test_database import validate_test_database


def test_accepts_separate_database():
    result = validate_test_database(
        "postgresql+asyncpg://user@localhost/googleai", "postgresql+asyncpg://user@localhost/googleai_test"
    )
    assert result.database == "googleai_test"


@pytest.mark.parametrize(
    "application,target",
    [
        ("postgresql+asyncpg://user@localhost/googleai", "postgresql+asyncpg://user@localhost/googleai"),
        (
            "postgresql+asyncpg://user@localhost/googleai_test",
            "postgresql+asyncpg://other@127.0.0.1/googleai_test",
        ),
        ("postgresql+asyncpg://user@localhost/googleai", "sqlite:///googleai_test"),
    ],
)
def test_refuses_unsafe_test_database(application, target):
    with pytest.raises(ValueError):
        validate_test_database(application, target)
