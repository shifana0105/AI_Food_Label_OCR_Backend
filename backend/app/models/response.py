"""Pydantic response models for the API layer.

Every successful endpoint returns the standard envelope:

    {
        "success": true,
        "message": "...",
        "data": { ... }
    }
"""

from typing import Generic, List, TypeVar

from pydantic import BaseModel, Field

DataT = TypeVar("DataT")


class APIResponse(BaseModel, Generic[DataT]):
    """Standard success envelope wrapping every endpoint payload."""

    success: bool = Field(default=True, description="Whether the request succeeded.")
    message: str = Field(..., description="Human-readable result summary.")
    data: DataT = Field(..., description="Endpoint-specific payload.")


class ErrorResponse(BaseModel):
    """Standard error payload produced by the exception handlers."""

    success: bool = Field(default=False, description="Always false for errors.")
    message: str = Field(..., description="Human-readable error summary.")
    error: str = Field(..., description="Detailed error description.")
    status_code: int = Field(..., description="HTTP status code of the error.")


class HealthData(BaseModel):
    """Payload for the health check endpoint."""

    status: str = Field(..., description="Health status of the service.")
    service: str = Field(..., description="Human-readable service name.")
    version: str = Field(..., description="Semantic version of the service.")


class OCRLine(BaseModel):
    """A single detected text line with confidence and bounding box."""

    text: str = Field(..., description="Recognized text content.")
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Recognition confidence."
    )
    bounding_box: List[List[float]] = Field(
        ...,
        description="Quadrilateral bounding box as four [x, y] points.",
    )


class OCRData(BaseModel):
    """OCR pipeline payload nested inside the upload response."""

    average_confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Mean confidence across all lines."
    )
    raw_text: str = Field(
        ..., description="Text as recognized, one entry per detected line."
    )
    clean_text: str = Field(
        ..., description="Normalized, merged, de-duplicated text."
    )
    lines: List[OCRLine] = Field(
        default_factory=list, description="Per-line OCR details."
    )


class UploadData(BaseModel):
    """Payload for the upload endpoint."""

    processing_time: str = Field(
        ..., description="Total processing time, e.g. '1.42s'."
    )
    ocr: OCRData = Field(..., description="Structured OCR results.")
