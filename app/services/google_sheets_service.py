import asyncio
import re
from pathlib import Path

import google_auth_httplib2
import httplib2
from google.auth.exceptions import GoogleAuthError
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import ROOT, get_settings
from app.core.exceptions import AppError


class TemporaryGoogleError(Exception):
    pass


class GoogleSheetsService:
    def _client(self):
        s = get_settings()
        path = Path(s.google_service_account_file)
        path = path if path.is_absolute() else ROOT / path
        if not path.is_file():
            raise AppError("GOOGLE_NOT_CONFIGURED", "Isi GOOGLE_SERVICE_ACCOUNT_FILE pada .env.", 503)
        try:
            credentials = Credentials.from_service_account_file(
                str(path), scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
            )
            http = google_auth_httplib2.AuthorizedHttp(
                credentials, http=httplib2.Http(timeout=s.google_api_timeout_seconds)
            )
            return build("sheets", "v4", http=http, cache_discovery=False)
        except (ValueError, GoogleAuthError):
            raise AppError("GOOGLE_NOT_CONFIGURED", "Konfigurasi Service Account tidak valid.", 503) from None

    @retry(
        retry=retry_if_exception_type(TemporaryGoogleError),
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=1, max=8),
        reraise=True,
    )
    def _execute(self, spreadsheet_id, ranges=None):
        try:
            # One client per call: httplib2 transports are not thread-safe.
            with self._client() as client:
                if ranges is None:
                    return (
                        client.spreadsheets()
                        .get(
                            spreadsheetId=spreadsheet_id,
                            fields="spreadsheetId,properties.title,sheets.properties",
                        )
                        .execute()
                    )
                return (
                    client.spreadsheets()
                    .values()
                    .batchGet(
                        spreadsheetId=spreadsheet_id,
                        ranges=ranges,
                        valueRenderOption="UNFORMATTED_VALUE",
                        dateTimeRenderOption="SERIAL_NUMBER",
                    )
                    .execute()
                )
        except HttpError as exc:
            status = exc.resp.status
            if status == 403:
                raise AppError(
                    "SOURCE_ACCESS_DENIED", "Bagikan Sheet kepada email Service Account sebagai Viewer.", 403
                ) from None
            if status == 404:
                raise AppError("SOURCE_NOT_FOUND", "Spreadsheet atau tab tidak ditemukan.", 404) from None
            if status == 429 or status >= 500:
                raise TemporaryGoogleError() from None
            raise AppError("SOURCE_READ_FAILED", "Google Sheets menolak permintaan.", 422) from None

    async def metadata(self, spreadsheet_id):
        try:
            return await asyncio.to_thread(self._execute, spreadsheet_id)
        except TemporaryGoogleError:
            raise AppError("UPSTREAM_RATE_LIMITED", "Google Sheets sementara tidak tersedia.", 503) from None

    async def read_sheets(self, spreadsheet_id, sheets):
        s = get_settings()
        ranges = []
        for sheet in sheets:
            # Reads are bounded; never silently truncate an unbounded source.
            match = re.fullmatch(r"([A-Z]+)(\d*):([A-Z]+)(\d*)", sheet.range_a1)
            if not match:
                raise AppError("INVALID_RANGE", "Range A1 tidak valid.")
            left, start, right, end = match.groups()
            if start and int(start) != 1:
                raise AppError(
                    "INVALID_RANGE", "Range harus mulai dari baris 1; gunakan header_row/data_start_row."
                )
            end = min(int(end) if end else s.google_max_rows + 1, s.google_max_rows + 1)
            escaped_name = sheet.sheet_name.replace("'", "''")
            ranges.append(f"'{escaped_name}'!{left}1:{right}{end}")
        try:
            result = await asyncio.to_thread(self._execute, spreadsheet_id, ranges)
        except TemporaryGoogleError:
            raise AppError("UPSTREAM_RATE_LIMITED", "Google Sheets sementara tidak tersedia.", 503) from None
        values = [r.get("values", []) for r in result.get("valueRanges", [])]
        if len(values) != len(sheets):
            raise AppError("SOURCE_READ_FAILED", "Jumlah range respons Google tidak cocok.")
        if any(len(v) > s.google_max_rows or any(len(r) > s.google_max_columns for r in v) for v in values):
            raise AppError("SOURCE_TOO_LARGE", "Sheet melebihi batas baris/kolom pada konfigurasi server.")
        return values
