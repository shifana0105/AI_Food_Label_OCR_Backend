"""OCR engine service.

Wraps PaddleOCR in a lazily-initialized, thread-safe singleton. The
model is NOT loaded at server startup; it loads on the first OCR
request (double-checked locking) and the same instance is reused for
every subsequent request. PaddleOCR is never recreated.
"""

import threading
from dataclasses import dataclass, field
from typing import Any, List, Optional

import numpy as np

from app.core.config import settings
from app.core.exceptions import OCRProcessingError
from app.core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class OCRLineResult:
    """A single recognized text line."""

    text: str
    confidence: float
    bounding_box: List[List[float]] = field(default_factory=list)


@dataclass
class OCRResult:
    """Aggregated OCR output for one image."""

    lines: List[OCRLineResult] = field(default_factory=list)

    @property
    def average_confidence(self) -> float:
        """Mean confidence across all detected lines (0.0 if empty)."""
        if not self.lines:
            return 0.0
        return sum(line.confidence for line in self.lines) / len(self.lines)


class OCREngine:
    """Thread-safe PaddleOCR wrapper loaded lazily, once per process."""

    _instance: Optional["OCREngine"] = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        """Prepare the engine without loading the model."""
        self._ocr: Optional[Any] = None
        self._model_lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> "OCREngine":
        """Return the process-wide singleton instance."""
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @property
    def is_loaded(self) -> bool:
        """Whether the PaddleOCR model has been loaded."""
        return self._ocr is not None

    def _load_model(self) -> Any:
        """Load PaddleOCR exactly once (double-checked locking)."""
        if self._ocr is None:
            with self._model_lock:
                if self._ocr is None:
                    logger.info("Loading PaddleOCR model (one-time initialization)...")
                    from paddleocr import PaddleOCR

                    self._ocr = PaddleOCR(
                        use_angle_cls=settings.OCR_USE_ANGLE_CLS,
                        lang=settings.OCR_LANGUAGE,
                        show_log=False,
                    )
                    logger.info("PaddleOCR model loaded.")
        return self._ocr

    def extract_text(self, image: np.ndarray) -> OCRResult:
        """Run OCR on a preprocessed image.

        Args:
            image: BGR image as a NumPy array.

        Returns:
            An :class:`OCRResult` with detected lines, confidences,
            and bounding boxes.

        Raises:
            OCRProcessingError: If the underlying engine fails.
        """
        ocr = self._load_model()
        logger.info("OCR started.")

        try:
            raw_output = ocr.ocr(image, cls=settings.OCR_USE_ANGLE_CLS)
        except Exception as exc:  # noqa: BLE001 - convert any engine failure
            logger.error("OCR engine failure: %s", exc)
            raise OCRProcessingError("The OCR engine failed to process the image.") from exc

        result = OCRResult()

        # PaddleOCR returns a list per image; each entry is
        # [bounding_box, (text, confidence)].
        if raw_output and raw_output[0]:
            for detection in raw_output[0]:
                try:
                    bounding_box = [[float(x), float(y)] for x, y in detection[0]]
                    text = str(detection[1][0])
                    confidence = float(detection[1][1])
                except (IndexError, TypeError, ValueError):
                    logger.warning("Skipping malformed OCR detection: %s", detection)
                    continue

                result.lines.append(
                    OCRLineResult(
                        text=text,
                        confidence=confidence,
                        bounding_box=bounding_box,
                    )
                )

        logger.info(
            "OCR completed: %d lines, avg confidence %.4f",
            len(result.lines),
            result.average_confidence,
        )
        return result
