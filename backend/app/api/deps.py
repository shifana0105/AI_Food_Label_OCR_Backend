"""Dependency providers for the API layer.

Services are created once per process and injected into routes via
FastAPI's ``Depends`` mechanism. Routes never instantiate services
directly, keeping construction centralized and easily overridable in
tests (``app.dependency_overrides``).
"""

from functools import lru_cache

from app.services.json_formatter import JSONFormatter
from app.services.nutrition_pipeline import NutritionPipeline
from app.services.ocr_engine import OCREngine
from app.services.preprocess import ImagePreprocessor
from app.services.text_processor import TextProcessor


@lru_cache(maxsize=1)
def get_preprocessor() -> ImagePreprocessor:
    """Provide the shared image preprocessor."""
    return ImagePreprocessor()


@lru_cache(maxsize=1)
def get_text_processor() -> TextProcessor:
    """Provide the shared text processor."""
    return TextProcessor()


@lru_cache(maxsize=1)
def get_json_formatter() -> JSONFormatter:
    """Provide the shared JSON formatter."""
    return JSONFormatter()


def get_ocr_engine() -> OCREngine:
    """Provide the lazily-loaded OCR engine singleton.

    The PaddleOCR model itself is not loaded here; it loads on the
    first call to :meth:`OCREngine.extract_text`.
    """
    return OCREngine.get_instance()


@lru_cache(maxsize=1)
def get_nutrition_pipeline() -> NutritionPipeline:
    """Provide the shared NutritionPipeline singleton.

    BUG-01 fix: NutritionPipeline was previously instantiated inside the
    upload route handler on every request, causing MLPredictor.__init__
    to call joblib.load() (loading a 422 MB Random Forest model) on every
    single request.  With lru_cache the pipeline — and therefore the ML
    model — is loaded exactly once per process, matching the pattern used
    by OCREngine, ImagePreprocessor, TextProcessor, and JSONFormatter.
    """
    return NutritionPipeline()
