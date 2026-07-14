"""JSON formatting service.

Converts internal OCR results into the public API response schema.
"""

from typing import List

from app.models.response import OCRData, OCRLine, UploadData
from app.services.ocr_engine import OCRLineResult


class JSONFormatter:
    """Builds the final API response payload from processed OCR data."""

    def format(
        self,
        processing_time_seconds: float,
        lines: List[OCRLineResult],
        raw_text: str,
        clean_text: str,
    ) -> UploadData:
        """Assemble the upload response payload.

        Args:
            processing_time_seconds: Total pipeline duration in seconds.
            lines: Cleaned OCR lines with confidences and boxes.
            raw_text: Cleaned per-line text, unmerged.
            clean_text: Final merged, normalized text block.

        Returns:
            A fully populated :class:`UploadData` payload.
        """
        average_confidence = (
            sum(line.confidence for line in lines) / len(lines) if lines else 0.0
        )

        return UploadData(
            processing_time=f"{processing_time_seconds:.2f}s",
            ocr=OCRData(
                average_confidence=round(average_confidence, 4),
                raw_text=raw_text,
                clean_text=clean_text,
                lines=[
                    OCRLine(
                        text=line.text,
                        confidence=round(line.confidence, 4),
                        bounding_box=line.bounding_box,
                    )
                    for line in lines
                ],
            ),
        )
