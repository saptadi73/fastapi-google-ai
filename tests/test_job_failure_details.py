from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.orm.exc import DetachedInstanceError

from app.core.exceptions import AppError
from app.workers import runner
from app.workers.runner import _job_failure_details


class DatabaseFailure(Exception):
    def __init__(self, sqlstate):
        self.sqlstate = sqlstate


class WrappedDatabaseFailure(Exception):
    def __init__(self, sqlstate):
        self.orig = DatabaseFailure(sqlstate)


def test_job_failure_details_maps_postgres_permission_error_for_deploy():
    code, message = _job_failure_details(WrappedDatabaseFailure("42501"), "DEPLOY")

    assert code == "DATABASE_PERMISSION_DENIED"
    assert "DATABASE_DDL_URL" in message
    assert "trusted" in message and "semantic" in message


def test_job_failure_details_maps_database_connection_error():
    code, message = _job_failure_details(DatabaseFailure("08006"), "ETL")

    assert code == "DATABASE_CONNECTION_FAILED"
    assert "08006" in message


def test_job_failure_details_keeps_domain_errors_actionable():
    code, message = _job_failure_details(AppError("SOURCE_ACCESS_DENIED", "Akses ditolak."), "PROFILE")

    assert (code, message) == ("SOURCE_ACCESS_DENIED", "Akses ditolak.")


def test_unexpected_exception_does_not_expose_raw_details():
    code, message = _job_failure_details(RuntimeError("sensitive database internals"), "DEPLOY")

    assert code == "JOB_EXECUTION_FAILED"
    assert "RuntimeError" in message
    assert "sensitive database internals" not in message


@pytest.mark.asyncio
async def test_worker_records_original_failure_after_rollback_detaches_job(monkeypatch):
    class ExpiringJob:
        id = "job-id"
        status = "QUEUED"
        expired = False

        @property
        def kind(self):
            if self.expired:
                raise DetachedInstanceError("Job was expired by rollback")
            return "IMPORT_REVIEW"

    job = ExpiringJob()
    failed_job = SimpleNamespace(
        id=job.id, kind="IMPORT_REVIEW", source_id=None, tenant_id="tenant",
    )

    class SessionContext:
        def __init__(self, session, expire_on_error=False):
            self.session = session
            self.expire_on_error = expire_on_error

        async def __aenter__(self):
            return self.session

        async def __aexit__(self, exc_type, exc, traceback):
            if exc is not None and self.expire_on_error:
                job.expired = True
            return False

    sessions = []
    for index in range(3):
        session = SimpleNamespace(
            scalar=AsyncMock(return_value=job),
            get=AsyncMock(return_value=failed_job),
        )
        session.begin = lambda session=session, index=index: SessionContext(session, index == 1)
        sessions.append(SessionContext(session))
    monkeypatch.setattr(runner, "SessionFactory", Mock(side_effect=sessions))
    monkeypatch.setattr(runner, "_audit_stage", Mock())
    monkeypatch.setattr(runner, "add_notification", Mock())
    fail_import = AsyncMock()
    monkeypatch.setattr(runner, "fail_import_job", fail_import)
    monkeypatch.setattr(
        runner, "execute_job", AsyncMock(side_effect=WrappedDatabaseFailure("42501")),
    )
    log = Mock()
    monkeypatch.setattr(runner, "logger", log)

    assert await runner.run_pending() == {"processed": 1, "job_id": job.id}
    assert failed_job.status == "FAILED"
    assert failed_job.error_code == "DATABASE_PERMISSION_DENIED"
    fail_import.assert_awaited_once_with(sessions[2].session, failed_job, "DATABASE_PERMISSION_DENIED")
    assert log.exception.call_args.kwargs["extra"]["job_kind"] == "IMPORT_REVIEW"
