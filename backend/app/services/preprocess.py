"""Image preprocessing service.

Prepares uploaded food label photos for OCR using OpenCV. The pipeline
is modular: resize -> denoise -> CLAHE contrast -> sharpen -> deskew.
Each step is an independent method so steps can be tuned or reordered.
"""

import cv2
import numpy as np

from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)


class ImagePreprocessor:
    """Deterministic OpenCV preprocessing pipeline for OCR input."""

    def __init__(
        self,
        max_dimension: int = settings.PREPROCESS_MAX_DIMENSION,
        min_dimension: int = settings.PREPROCESS_MIN_DIMENSION,
    ) -> None:
        """Initialize the preprocessor.

        Args:
            max_dimension: Longest side is downscaled to this size if larger.
            min_dimension: Longest side is upscaled to this size if smaller.
        """
        self._max_dimension = max_dimension
        self._min_dimension = min_dimension

    def resize(self, image: np.ndarray) -> np.ndarray:
        """Resize the image so its longest side is within a usable range.

        Very large images slow OCR down without accuracy gains, while very
        small images lack the resolution needed for text detection.
        """
        height, width = image.shape[:2]
        longest = max(height, width)

        if longest > self._max_dimension:
            scale = self._max_dimension / longest
            interpolation = cv2.INTER_AREA
        elif longest < self._min_dimension:
            scale = self._min_dimension / longest
            interpolation = cv2.INTER_CUBIC
        else:
            return image

        new_size = (int(width * scale), int(height * scale))
        return cv2.resize(image, new_size, interpolation=interpolation)

    def denoise(self, image: np.ndarray) -> np.ndarray:
        """Reduce sensor noise while preserving edges."""
        return cv2.fastNlMeansDenoisingColored(image, None, 5, 5, 7, 21)

    def enhance_contrast(self, image: np.ndarray) -> np.ndarray:
        """Boost local contrast with CLAHE applied on the L channel."""
        lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
        l_channel, a_channel, b_channel = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        l_channel = clahe.apply(l_channel)
        merged = cv2.merge((l_channel, a_channel, b_channel))
        return cv2.cvtColor(merged, cv2.COLOR_LAB2BGR)

    def sharpen(self, image: np.ndarray) -> np.ndarray:
        """Sharpen text edges using an unsharp-mask style kernel."""
        kernel = np.array(
            [
                [0, -1, 0],
                [-1, 5, -1],
                [0, -1, 0],
            ],
            dtype=np.float32,
        )
        return cv2.filter2D(image, -1, kernel)

    def deskew(self, image: np.ndarray) -> np.ndarray:
        """Correct small rotations so text lines are horizontal.

        Estimates the dominant text angle from thresholded foreground
        pixels and rotates the image to compensate. Angles below half a
        degree (or implausibly large ones) are ignored to avoid harming
        already-straight images.
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        binary = cv2.threshold(
            gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
        )[1]

        coords = np.column_stack(np.where(binary > 0))
        if coords.shape[0] < 100:
            return image

        angle = cv2.minAreaRect(coords)[-1]
        if angle > 45.0:
            angle -= 90.0

        if abs(angle) < 0.5 or abs(angle) > 15.0:
            return image

        height, width = image.shape[:2]
        center = (width / 2.0, height / 2.0)
        rotation = cv2.getRotationMatrix2D(center, angle, 1.0)
        logger.info("Deskewing image by %.2f degrees.", angle)
        return cv2.warpAffine(
            image,
            rotation,
            (width, height),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_REPLICATE,
        )

    def process(self, image: np.ndarray) -> np.ndarray:
        """Run the full preprocessing pipeline.

        Args:
            image: BGR image as loaded by OpenCV.

        Returns:
            The processed BGR image, ready for OCR.
        """
        logger.info("Preprocessing started: shape=%s", image.shape)
        result = self.resize(image)
        result = self.denoise(result)
        result = self.enhance_contrast(result)
        result = self.sharpen(result)
        result = self.deskew(result)
        logger.info("Preprocessing finished: shape=%s", result.shape)
        return result
