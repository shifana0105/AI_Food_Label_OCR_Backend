"""Text post-processing service.

Cleans and normalizes raw OCR output: whitespace normalization,
empty-line removal, duplicate removal, and merging of lines that were
split mid-sentence or mid-word by the OCR engine. Confidence values
are preserved on every retained line.
"""

from typing import List

from app.core.logger import get_logger
from app.services.ocr_engine import OCRLineResult
from app.utils.text_utils import (
    ends_with_continuation,
    is_meaningful,
    merge_hyphenated,
    normalize_whitespace,
)

logger = get_logger(__name__)


class TextProcessor:
    """Normalizes OCR line output into clean, human-readable text."""

    def clean_lines(self, lines: List[OCRLineResult]) -> List[OCRLineResult]:
        """Normalize whitespace and drop empty, meaningless, or duplicate lines.

        Args:
            lines: Raw OCR line results in reading order.

        Returns:
            Cleaned lines with normalized text, preserving confidence
            and bounding boxes. Exact duplicate lines are removed.
        """
        cleaned: List[OCRLineResult] = []
        seen: set[str] = set()

        for line in lines:
            text = normalize_whitespace(line.text)
            if not text or not is_meaningful(text):
                continue

            fingerprint = text.casefold()
            if fingerprint in seen:
                continue
            seen.add(fingerprint)

            cleaned.append(
                OCRLineResult(
                    text=text,
                    confidence=line.confidence,
                    bounding_box=line.bounding_box,
                )
            )
        return cleaned

    def merge_split_lines(self, texts: List[str]) -> List[str]:
        """Merge lines that clearly continue onto the next line.

        Lines ending with a hyphen, comma, or an unfinished lowercase
        word are joined with the following line so ingredient lists
        read as continuous sentences.

        Args:
            texts: Cleaned text lines in reading order.

        Returns:
            Merged text lines.
        """
        merged: List[str] = []
        for text in texts:
            if merged and ends_with_continuation(merged[-1]):
                merged[-1] = merge_hyphenated(merged[-1], text)
            else:
                merged.append(text)
        return merged

    def build_raw_text(self, lines: List[OCRLineResult]) -> str:
        """Produce the raw text block (one entry per detected line).

        Args:
            lines: Cleaned OCR lines.

        Returns:
            A newline-joined string of the cleaned lines, unmerged.
        """
        return "\n".join(line.text for line in lines)

    def build_clean_text(self, lines: List[OCRLineResult]) -> str:
        """Produce the final merged, normalized text block.

        Args:
            lines: Cleaned OCR lines.

        Returns:
            A newline-joined string of merged, normalized lines.
        """
        texts = [line.text for line in lines]
        merged = self.merge_split_lines(texts)
        logger.info("Text processing produced %d merged lines.", len(merged))
        return "\n".join(merged)
