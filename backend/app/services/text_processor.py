# """Text post-processing service.

# Cleans and normalizes raw OCR output: whitespace normalization,
# empty-line removal, duplicate removal, and merging of lines that were
# split mid-sentence or mid-word by the OCR engine. Confidence values
# are preserved on every retained line.
# """

# from typing import List

# from app.core.logger import get_logger
# from app.services.ocr_engine import OCRLineResult
# from app.utils.text_utils import (
#     ends_with_continuation,
#     is_meaningful,
#     merge_hyphenated,
#     normalize_whitespace,
# )

# logger = get_logger(__name__)


# class TextProcessor:
#     """Normalizes OCR line output into clean, human-readable text."""

#     def clean_lines(self, lines: List[OCRLineResult]) -> List[OCRLineResult]:
#         """Normalize whitespace and drop empty, meaningless, or duplicate lines.

#         Args:
#             lines: Raw OCR line results in reading order.

#         Returns:
#             Cleaned lines with normalized text, preserving confidence
#             and bounding boxes. Exact duplicate lines are removed.
#         """
#         cleaned: List[OCRLineResult] = []
#         seen: set[str] = set()

#         for line in lines:
#             text = normalize_whitespace(line.text)
#             if not text or not is_meaningful(text):
#                 continue

#             fingerprint = text.casefold()
#             if fingerprint in seen:
#                 continue
#             seen.add(fingerprint)

#             cleaned.append(
#                 OCRLineResult(
#                     text=text,
#                     confidence=line.confidence,
#                     bounding_box=line.bounding_box,
#                 )
#             )
#         return cleaned

#     def merge_split_lines(self, texts: List[str]) -> List[str]:
#         """Merge lines that clearly continue onto the next line.

#         Lines ending with a hyphen, comma, or an unfinished lowercase
#         word are joined with the following line so ingredient lists
#         read as continuous sentences.

#         Args:
#             texts: Cleaned text lines in reading order.

#         Returns:
#             Merged text lines.
#         """
#         merged: List[str] = []
#         for text in texts:
#             if merged and ends_with_continuation(merged[-1]):
#                 merged[-1] = merge_hyphenated(merged[-1], text)
#             else:
#                 merged.append(text)
#         return merged

#     def build_raw_text(self, lines: List[OCRLineResult]) -> str:
#         """Produce the raw text block (one entry per detected line).

#         Args:
#             lines: Cleaned OCR lines.

#         Returns:
#             A newline-joined string of the cleaned lines, unmerged.
#         """
#         return "\n".join(line.text for line in lines)

#     def build_clean_text(self, lines: List[OCRLineResult]) -> str:
#         """Produce the final merged, normalized text block.

#         Args:
#             lines: Cleaned OCR lines.

#         Returns:
#             A newline-joined string of merged, normalized lines.
#         """
#         texts = [line.text for line in lines]
#         merged = self.merge_split_lines(texts)
#         logger.info("Text processing produced %d merged lines.", len(merged))
#         return "\n".join(merged)



"""Text post-processing service.

Cleans and normalizes raw OCR output: whitespace normalization,
empty-line removal, duplicate removal, and merging of lines that were
split mid-sentence or mid-word by the OCR engine. Confidence values
are preserved on every retained line.
"""

import re

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


# A "value-only" line contains nothing but a number (optionally preceded
# by a comparison symbol like '<' or '~') and an optional unit — e.g.
# "0.1g", "0.4 mg", "1.5g", "0mg", "9%". These are NOT unique identifiers:
# nutrition labels routinely repeat the same bare value across unrelated
# rows (e.g. two different nutrients both showing "0.1g"). Deduplicating
# on these by text alone silently deletes real, unrelated data.
#
# BUG FIX (Root Cause 5): TextProcessor.clean_lines() previously
# deduplicated on a global text fingerprint with no distinction between
# meaningful label lines and bare numeric value lines. On real nutrition
# panels, unrelated rows frequently share the exact same value string
# (e.g. Polyunsaturated Fat "0.1g" and Vitamin B12 "0.1g" on different
# rows). The old fingerprint-based dedup silently deleted the second
# occurrence as if it were a repeated OCR detection of the same line,
# corrupting downstream parsing (a later nutrient would end up reading
# the wrong / missing value). Value-only lines are now exempt from
# dedup entirely; only label-bearing lines (which legitimately can be
# re-detected duplicates of the same physical text) are deduplicated.
_VALUE_ONLY_RE = re.compile(
    r"^\s*[<>≤≥~±]?\s*"
    r"\d+(?:[.,]\d+)?\s*"
    r"(?:mcg|mg|g|kcal|kj|iu|ml|%)?\s*$",
    re.I,
)


class TextProcessor:
    """Normalizes OCR line output into clean, human-readable text."""

    @staticmethod
    def _is_value_only(text: str) -> bool:
        """Return True if a line is a bare number/unit with no label text.

        Such lines must never be discarded as "duplicates" of another
        row's value, since numeric coincidence across unrelated
        nutrients is common and does not indicate a repeated line.

        Args:
            text: Already whitespace-normalized line text.

        Returns:
            True if the line contains only a number and optional unit.
        """
        return bool(_VALUE_ONLY_RE.match(text))

    def clean_lines(self, lines: List[OCRLineResult]) -> List[OCRLineResult]:
        """Normalize whitespace and drop empty, meaningless, or duplicate lines.

        Args:
            lines: Raw OCR line results in reading order.

        Returns:
            Cleaned lines with normalized text, preserving confidence
            and bounding boxes. Exact duplicate LABEL lines are removed;
            bare value-only lines (e.g. "0.1g") are never deduplicated,
            since identical values commonly and legitimately recur
            across unrelated nutrient rows.
        """
        cleaned: List[OCRLineResult] = []
        seen: set[str] = set()

        for line in lines:
            text = normalize_whitespace(line.text)
            if not text or not is_meaningful(text):
                continue

            # Value-only lines (bare numbers/units) are never deduplicated:
            # numeric repetition across unrelated rows is expected and
            # each occurrence carries distinct, position-relevant meaning.
            if not self._is_value_only(text):
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