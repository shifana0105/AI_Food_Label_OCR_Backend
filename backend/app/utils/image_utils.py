"""Image-related utility helpers.

Handles upload validation (extension, MIME type, size, decodability),
unique filename generation, temporary storage, image loading, and
temp-folder cleanup.
"""

import uuid
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)


def get_extension(filename: str) -> str:
    """Return the lowercase extension of a filename without the dot.

    Args:
        filename: Original filename provided by the client.

    Returns:
        The extension in lowercase, or an empty string if none exists.
    """
    return Path(filename).suffix.lower().lstrip(".")


def is_allowed_extension(filename: str) -> bool:
    """Check whether a filename has an allowed image extension."""
    return get_extension(filename) in settings.allowed_extensions


def is_allowed_mime_type(content_type: Optional[str]) -> bool:
    """Check whether a MIME type is in the configured allow-list.

    Args:
        content_type: The Content-Type header of the uploaded part.

    Returns:
        True if the MIME type is allowed.
    """
    if not content_type:
        return False
    return content_type.split(";")[0].strip().lower() in settings.allowed_mime_types


def is_allowed_size(size_in_bytes: int) -> bool:
    """Check whether a file size is within the configured limit."""
    return 0 < size_in_bytes <= settings.MAX_FILE_SIZE


def generate_unique_filename(original_filename: str) -> str:
    """Generate a collision-safe filename preserving the extension.

    Args:
        original_filename: The client-provided filename.

    Returns:
        A unique filename such as ``a1b2c3d4e5.png``.
    """
    extension = get_extension(original_filename)
    return f"{uuid.uuid4().hex}.{extension}"


def save_bytes_to_temp(content: bytes, unique_filename: str) -> Path:
    """Persist raw bytes to the upload (temp) folder.

    Args:
        content: Raw file bytes.
        unique_filename: Target filename (already validated and unique).

    Returns:
        Absolute path of the saved file.
    """
    settings.ensure_directories()
    destination = settings.UPLOAD_FOLDER / unique_filename
    destination.write_bytes(content)
    logger.info("Saved uploaded file to %s (%d bytes)", destination, len(content))
    return destination


def load_image(path: Path) -> Optional[np.ndarray]:
    """Load an image from disk as a BGR NumPy array.

    Args:
        path: Path of the image file.

    Returns:
        The decoded image, or ``None`` if decoding failed.
    """
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None:
        logger.error("Failed to decode image at %s", path)
    return image


def is_decodable_image(content: bytes) -> bool:
    """Verify that raw bytes decode into a valid image.

    Args:
        content: Raw file bytes.

    Returns:
        True if OpenCV can decode the bytes into an image.
    """
    buffer = np.frombuffer(content, dtype=np.uint8)
    image = cv2.imdecode(buffer, cv2.IMREAD_COLOR)
    return image is not None


def delete_file(path: Path) -> None:
    """Delete a file, ignoring the error if it is already gone."""
    try:
        path.unlink(missing_ok=True)
        logger.info("Deleted temporary file %s", path)
    except OSError as exc:  # pragma: no cover - defensive
        logger.warning("Could not delete file %s: %s", path, exc)


def cleanup_temp() -> int:
    """Remove every file from the upload (temp) folder.

    Returns:
        The number of files removed.
    """
    settings.ensure_directories()
    removed = 0
    for entry in settings.UPLOAD_FOLDER.iterdir():
        if entry.is_file() and entry.name != ".gitkeep":
            delete_file(entry)
            removed += 1
    if removed:
        logger.info("cleanup_temp removed %d stale file(s).", removed)
    return removed
