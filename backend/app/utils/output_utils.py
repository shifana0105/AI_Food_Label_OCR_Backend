# """
# Utility helpers for persisting OCR output artifacts (images and JSON
# results) to disk using timestamped filenames.
# """

# import json
# from datetime import datetime
# from pathlib import Path

# from app.core.config import settings


# def generate_timestamp_filename(original_filename: str) -> str:
#     """
#     Build a timestamped filename that preserves the original extension.

#     Example:
#         "oreo.jpg" -> "oreo_20260714_143215.jpg"
#     """
#     original_path = Path(original_filename)
#     stem = original_path.stem
#     suffix = original_path.suffix

#     timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

#     return f"{stem}_{timestamp}{suffix}"


# def save_image_copy(content: bytes, original_filename: str) -> Path:
#     """
#     Save a copy of image bytes into the configured output images folder,
#     using a timestamped filename derived from the original filename.

#     Returns the Path where the image was saved.
#     """
#     output_dir = settings.OUTPUT_IMAGES_FOLDER
#     output_dir.mkdir(parents=True, exist_ok=True)

#     filename = generate_timestamp_filename(original_filename)
#     output_path = output_dir / filename

#     output_path.write_bytes(content)

#     return output_path


# def save_json(data: dict, original_filename: str) -> Path:
#     """
#     Save a dict as a JSON file into the configured output json folder,
#     using a timestamped filename derived from the original filename.

#     Returns the Path where the JSON file was saved.
#     """
#     output_dir = Path(settings.OUTPUT_JSON_FOLDER)
#     output_dir.mkdir(parents=True, exist_ok=True)

#     json_filename = Path(generate_timestamp_filename(original_filename)).with_suffix(".json").name
#     output_path = output_dir / json_filename

#     with output_path.open("w", encoding="utf-8") as f:
#         json.dump(data, f, indent=2, ensure_ascii=False)

#     return output_path















"""
Utility helpers for persisting OCR output artifacts (images and JSON
results) to disk using timestamped filenames.
"""

import json
from datetime import datetime
from pathlib import Path

from app.core.config import settings


def generate_timestamp_filename(original_filename: str) -> str:
    """
    Build a timestamped filename that preserves the original extension.

    Example:
        "oreo.jpg" -> "oreo_20260714_143215.jpg"
    """
    original_path = Path(original_filename)
    stem = original_path.stem
    suffix = original_path.suffix

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    return f"{stem}_{timestamp}{suffix}"


def save_image_copy(content: bytes, original_filename: str) -> Path:
    """
    Save a copy of image bytes into the configured output images folder.

    Returns:
        Path to the saved image.
    """
    output_dir = settings.OUTPUT_IMAGES_FOLDER
    output_dir.mkdir(parents=True, exist_ok=True)

    filename = generate_timestamp_filename(original_filename)
    output_path = output_dir / filename

    output_path.write_bytes(content)

    return output_path


def save_json(data: dict, original_filename: str) -> Path:
    """
    Save OCR output as a JSON file.

    Returns:
        Path to the saved JSON.
    """
    output_dir = settings.OUTPUT_JSON_FOLDER
    output_dir.mkdir(parents=True, exist_ok=True)

    json_filename = (
        Path(generate_timestamp_filename(original_filename))
        .with_suffix(".json")
        .name
    )

    output_path = output_dir / json_filename

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    return output_path