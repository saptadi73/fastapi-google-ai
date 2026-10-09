from app.core.exceptions import AppError
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
