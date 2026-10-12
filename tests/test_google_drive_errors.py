import json

import httplib2
from googleapiclient.errors import HttpError

from app.services.google_sheets_service import GoogleSheetsService


def test_drive_error_reason_reads_structured_google_reason_only():
    error = HttpError(
        httplib2.Response({"status": "403"}),
        json.dumps({"error": {"errors": [{"reason": "accessNotConfigured"}]}}).encode(),
    )

    assert GoogleSheetsService._google_error_reason(error) == "accessNotConfigured"


def test_drive_error_reason_handles_unstructured_response():
    error = HttpError(httplib2.Response({"status": "403"}), b"not-json")

    assert GoogleSheetsService._google_error_reason(error) is None
