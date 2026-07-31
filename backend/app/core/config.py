"""Application configuration.

All configuration values are read from environment variables (optionally
via a ``.env`` file). See ``.env.example`` for the full list of supported
variables. No other module may hardcode configuration values.
"""

from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_BASE_DIR: Path = Path(__file__).resolve().parents[2]

CONFIG_FOLDER: Path = _BASE_DIR / "config"


class Settings(BaseSettings):
    """Global application settings, loaded from the environment.

    Attributes:
        PROJECT_NAME: Human-readable service name.
        VERSION: Semantic version of the service.
        DEBUG: Enables debug behavior (verbose errors in logs).
        UPLOAD_FOLDER: Folder where uploaded images are temporarily stored.
        OUTPUT_FOLDER: Folder where processing artifacts may be written.
        MAX_FILE_SIZE: Maximum allowed upload size in bytes.
        ALLOWED_EXTENSIONS: Comma-separated list of allowed image extensions.
        ALLOWED_MIME_TYPES: Comma-separated list of allowed MIME types.
        OCR_LANGUAGE: PaddleOCR language code.
        OCR_USE_ANGLE_CLS: Whether PaddleOCR uses angle classification.
        LOG_LEVEL: Python logging level name (e.g. INFO, DEBUG).
        PREPROCESS_MAX_DIMENSION: Longest image side is downscaled to this.
        PREPROCESS_MIN_DIMENSION: Longest image side is upscaled to this.
    """

    model_config = SettingsConfigDict(
        env_file=_BASE_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    PROJECT_NAME: str = "Food Label Reader Backend"
    VERSION: str = "2.0.0"
    DEBUG: bool = False

    CONFIG_FOLDER: Path = CONFIG_FOLDER

    UPLOAD_FOLDER: Path = _BASE_DIR / "temp"
    OUTPUT_FOLDER: Path = _BASE_DIR / "outputs"
    OUTPUT_IMAGES_FOLDER: Path = OUTPUT_FOLDER / "images"
    OUTPUT_JSON_FOLDER: Path = OUTPUT_FOLDER / "json"

    MAX_FILE_SIZE: int = 15 * 1024 * 1024
    ALLOWED_EXTENSIONS: str = "jpg,jpeg,png"
    ALLOWED_MIME_TYPES: str = "image/jpeg,image/png"

    OCR_LANGUAGE: str = "en"
    OCR_USE_ANGLE_CLS: bool = True

    LOG_LEVEL: str = "INFO"

    PREPROCESS_MAX_DIMENSION: int = 2000
    PREPROCESS_MIN_DIMENSION: int = 600

    @field_validator(
    "CONFIG_FOLDER",
    "UPLOAD_FOLDER",
    "OUTPUT_FOLDER",
    "OUTPUT_IMAGES_FOLDER",
    "OUTPUT_JSON_FOLDER",
    mode="after",
)
    @classmethod
    def _resolve_folder(cls, value: Path) -> Path:
        """Resolve relative folders against the backend base directory."""
        if not value.is_absolute():
            value = _BASE_DIR / value
        return value

    @property
    def allowed_extensions(self) -> frozenset[str]:
        """Allowed extensions as a normalized lowercase set (no dots)."""
        return frozenset(
            ext.strip().lower().lstrip(".")
            for ext in self.ALLOWED_EXTENSIONS.split(",")
            if ext.strip()
        )

    @property
    def allowed_mime_types(self) -> frozenset[str]:
        """Allowed MIME types as a normalized lowercase set."""
        return frozenset(
            mime.strip().lower()
            for mime in self.ALLOWED_MIME_TYPES.split(",")
            if mime.strip()
        )

    def ensure_directories(self) -> None:
     self.UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
     self.OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)
     self.OUTPUT_IMAGES_FOLDER.mkdir(parents=True, exist_ok=True)
     self.OUTPUT_JSON_FOLDER.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached process-wide settings instance."""
    return Settings()


settings = get_settings()
