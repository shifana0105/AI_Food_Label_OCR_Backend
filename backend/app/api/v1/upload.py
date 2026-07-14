"""Image upload and OCR pipeline endpoint (v1)."""

import time

from fastapi import APIRouter, Depends, File, UploadFile

from app.api.deps import (
    get_json_formatter,
    get_ocr_engine,
    get_preprocessor,
    get_text_processor,
)
from app.core.config import settings
from app.core.exceptions import FileTooLargeError, OCRProcessingError, ValidationAppError
from app.core.logger import get_logger
from app.models.response import APIResponse, ErrorResponse, UploadData
from app.services.json_formatter import JSONFormatter
from app.services.ocr_engine import OCREngine
from app.services.preprocess import ImagePreprocessor
from app.services.text_processor import TextProcessor
from app.utils.image_utils import (
    delete_file,
    generate_unique_filename,
    is_allowed_extension,
    is_allowed_mime_type,
    is_allowed_size,
    is_decodable_image,
    load_image,
    save_bytes_to_temp,
)
from app.utils.output_utils import save_image_copy, save_json

logger = get_logger(__name__)

router = APIRouter(tags=["OCR"])


@router.post(
    "/upload",
    response_model=APIResponse[UploadData],
    responses={
        400: {"model": ErrorResponse, "description": "Invalid file"},
        413: {"model": ErrorResponse, "description": "File too large"},
        422: {"model": ErrorResponse, "description": "Missing image"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def upload_image(
    file: UploadFile = File(...),
    preprocessor: ImagePreprocessor = Depends(get_preprocessor),
    text_processor: TextProcessor = Depends(get_text_processor),
    formatter: JSONFormatter = Depends(get_json_formatter),
    ocr_engine: OCREngine = Depends(get_ocr_engine),
) -> APIResponse[UploadData]:
    """Accept a food label image, run the OCR pipeline, return results.

    Pipeline: validate -> save to temp -> preprocess -> OCR ->
    text cleanup -> JSON formatting -> delete temp image.

    Args:
        file: The uploaded image (allowed extensions and size come
            from configuration).
        preprocessor: Injected image preprocessing service.
        text_processor: Injected text cleanup service.
        formatter: Injected response formatting service.
        ocr_engine: Injected lazily-loaded OCR engine.

    Returns:
        The standard envelope containing the structured OCR result.

    Raises:
        ValidationAppError: On invalid extension, MIME type, empty or
            corrupted files.
        FileTooLargeError: When the upload exceeds the size limit.
        OCRProcessingError: When the OCR engine fails.
    """
    started = time.perf_counter()

    if not file.filename:
        raise ValidationAppError("No image file provided.")

    if not is_allowed_extension(file.filename):
        raise ValidationAppError(
            "Invalid file type. Allowed extensions: "
            f"{', '.join(sorted(settings.allowed_extensions))}."
        )

    if not is_allowed_mime_type(file.content_type):
        raise ValidationAppError(
            "Invalid MIME type. Allowed types: "
            f"{', '.join(sorted(settings.allowed_mime_types))}."
        )

    content = await file.read()

    if len(content) == 0:
        raise ValidationAppError("Uploaded file is empty.")

    if not is_allowed_size(len(content)):
        raise FileTooLargeError(
            "File too large. Maximum allowed size is "
            f"{settings.MAX_FILE_SIZE // (1024 * 1024)} MB."
        )

    if not is_decodable_image(content):
        raise ValidationAppError("Uploaded file is not a valid image.")
    # Save a permanent copy of the uploaded image
    save_image_copy(content, file.filename)
    saved_path = None

    unique_filename = generate_unique_filename(file.filename)
    saved_path = save_bytes_to_temp(
    content,
    unique_filename,
)
    logger.info("Image uploaded: %s -> %s", file.filename, unique_filename)

    try:
        image = load_image(saved_path)
        if image is None:
            raise OCRProcessingError("Failed to read the saved image from disk.")

        processed = preprocessor.process(image)
        ocr_result = ocr_engine.extract_text(processed)

        cleaned_lines = text_processor.clean_lines(ocr_result.lines)
        raw_text = text_processor.build_raw_text(cleaned_lines)
        clean_text = text_processor.build_clean_text(cleaned_lines)
    finally:
        if saved_path:
            delete_file(saved_path)

    elapsed = time.perf_counter() - started
    logger.info("Upload pipeline finished in %.2fs.", elapsed)
    
    response_data = formatter.format(
    processing_time_seconds=elapsed,
    lines=cleaned_lines,
    raw_text=raw_text,
    clean_text=clean_text,
)

    save_json(response_data.model_dump(), file.filename)

    return APIResponse(
    message="Image processed successfully.",
    data=response_data,
)
