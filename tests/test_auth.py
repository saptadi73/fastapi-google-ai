from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.core.exceptions import AppError
from app.core.security import decode_token, issue_token, password_hasher


def test_jwt_types_and_tampering():
    user = SimpleNamespace(id=str(uuid4()), tenant_id=str(uuid4()), role="VIEWER", token_version=2)
    access, _ = issue_token(user, "access")
    assert decode_token(access)["tenant_id"] == user.tenant_id
    refresh, _ = issue_token(user, "refresh")
    with pytest.raises(AppError):
        decode_token(refresh)
    head, payload, signature = access.split(".")
    corrupted = head + "." + payload + "." + ("a" if signature[0] != "a" else "b") + signature[1:]
    with pytest.raises(AppError):
        decode_token(corrupted)


def test_password_hash():
    hashed = password_hasher.hash("test-password-123")
    assert password_hasher.verify("test-password-123", hashed)
    assert not password_hasher.verify("wrong", hashed)
