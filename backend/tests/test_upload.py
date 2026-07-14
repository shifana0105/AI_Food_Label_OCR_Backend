"""Tests for the upload endpoint validation logic.

These tests cover request validation and the error envelope; full OCR
integration tests require the PaddleOCR model to be downloaded and are
exercised manually.
"""

import io

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _assert_error_envelope(body: dict, status_code: int) -> None:
    """Assert the standard error JSON shape."""
    assert body["success"] is False
    assert body["message"]
    assert body["error"]
    assert body["status_code"] == status_code


def test_upload_rejects_missing_file() -> None:
    """POST /api/v1/upload without a file should return 422."""
    response = client.post("/api/v1/upload")
    assert response.status_code == 422
    _assert_error_envelope(response.json(), 422)


def test_upload_rejects_invalid_extension() -> None:
    """POST /api/v1/upload with a non-image extension should return 400."""
    response = client.post(
        "/api/v1/upload",
        files={"file": ("label.txt", io.BytesIO(b"not an image"), "text/plain")},
    )
    assert response.status_code == 400
    body = response.json()
    _assert_error_envelope(body, 400)
    assert "Invalid file type" in body["error"]


def test_upload_rejects_invalid_mime_type() -> None:
    """POST /api/v1/upload with a disallowed MIME type should return 400."""
    response = client.post(
        "/api/v1/upload",
        files={"file": ("label.jpg", io.BytesIO(b"data"), "application/octet-stream")},
    )
    assert response.status_code == 400
    body = response.json()
    _assert_error_envelope(body, 400)
    assert "Invalid MIME type" in body["error"]


def test_upload_rejects_empty_file() -> None:
    """POST /api/v1/upload with an empty file should return 400."""
    response = client.post(
        "/api/v1/upload",
        files={"file": ("label.jpg", io.BytesIO(b""), "image/jpeg")},
    )
    assert response.status_code == 400
    body = response.json()
    _assert_error_envelope(body, 400)
    assert "empty" in body["error"].lower()


def test_upload_rejects_undecodable_image() -> None:
    """POST /api/v1/upload with junk bytes named .jpg should return 400."""
    response = client.post(
        "/api/v1/upload",
        files={"file": ("label.jpg", io.BytesIO(b"junk bytes"), "image/jpeg")},
    )
    assert response.status_code == 400
    body = response.json()
    _assert_error_envelope(body, 400)
    assert "not a valid image" in body["error"]
