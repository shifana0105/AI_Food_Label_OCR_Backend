"""Tests for the OCR engine wrapper and text processing services.

These tests validate service behavior that does not require the
PaddleOCR model to be downloaded.
"""

from app.services.ocr_engine import OCREngine, OCRLineResult, OCRResult
from app.services.text_processor import TextProcessor


def test_ocr_engine_is_singleton() -> None:
    """get_instance must always return the same engine object."""
    first = OCREngine.get_instance()
    second = OCREngine.get_instance()
    assert first is second


def test_ocr_engine_is_lazy() -> None:
    """Creating the singleton must NOT load the PaddleOCR model."""
    engine = OCREngine.get_instance()
    assert engine.is_loaded is False


def test_ocr_result_average_confidence() -> None:
    """average_confidence must be the mean of line confidences."""
    result = OCRResult(
        lines=[
            OCRLineResult(text="a", confidence=0.8),
            OCRLineResult(text="b", confidence=1.0),
        ]
    )
    assert result.average_confidence == 0.9


def test_ocr_result_average_confidence_empty() -> None:
    """average_confidence must be 0.0 when no lines were detected."""
    assert OCRResult().average_confidence == 0.0


def test_text_processor_removes_duplicates_and_noise() -> None:
    """clean_lines drops empty, meaningless, and duplicate lines."""
    processor = TextProcessor()
    lines = [
        OCRLineResult(text="  SUGAR,   SALT ", confidence=0.95),
        OCRLineResult(text="sugar, salt", confidence=0.90),
        OCRLineResult(text="***", confidence=0.50),
        OCRLineResult(text="", confidence=0.10),
    ]

    cleaned = processor.clean_lines(lines)

    assert len(cleaned) == 1
    assert cleaned[0].text == "SUGAR, SALT"
    assert cleaned[0].confidence == 0.95


def test_text_processor_merges_split_lines() -> None:
    """Hyphen- and comma-split lines are merged into continuous text."""
    processor = TextProcessor()
    lines = [
        OCRLineResult(text="INGREDIENTS: WHEAT FLOUR,", confidence=0.97),
        OCRLineResult(text="COCOA POW-", confidence=0.96),
        OCRLineResult(text="DER, SALT.", confidence=0.95),
    ]

    clean_text = processor.build_clean_text(lines)

    assert clean_text == "INGREDIENTS: WHEAT FLOUR, COCOA POWDER, SALT."
