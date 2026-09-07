from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from starlette.exceptions import HTTPException


class AppError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 422):
        self.code, self.message, self.status_code = code, message, status_code
        super().__init__(message)


def success(data: Any = None, **meta):
    return {"status": "success", "data": data, "meta": meta, "errors": []}


def error_response(request: Request, code: str, message: str, status: int, details=None):
    return JSONResponse(
        status_code=status,
        content={
            "status": "error",
            "data": None,
            "meta": {"request_id": getattr(request.state, "request_id", None)},
            "errors": [{"code": code, "message": message, "details": details}],
        },
        headers={"WWW-Authenticate": "Bearer"} if status == 401 else None,
    )


def install_handlers(app):
    @app.exception_handler(AppError)
    async def app_error(request, exc):
        return error_response(request, exc.code, exc.message, exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        details = [{"field": ".".join(map(str, e["loc"])), "message": e["msg"]} for e in exc.errors()]
        return error_response(request, "VALIDATION_ERROR", "Periksa parameter permintaan.", 422, details)

    @app.exception_handler(HTTPException)
    async def http_error(request, exc):
        return error_response(request, f"HTTP_{exc.status_code}", str(exc.detail), exc.status_code)

    @app.exception_handler(IntegrityError)
    async def conflict(request, exc):
        return error_response(request, "RESOURCE_CONFLICT", "Data duplikat atau relasi tidak valid.", 409)

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request, exc):
        return error_response(request, "DATABASE_UNAVAILABLE", "Operasi database gagal.", 503)

    @app.exception_handler(Exception)
    async def unexpected(request, exc):
        return error_response(request, "INTERNAL_ERROR", "Terjadi kesalahan internal.", 500)
