"""FastAPI application entry point for the Food Label Reader backend."""

from contextlib import asynccontextmanager
from typing import AsyncIterator, Dict

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import v1
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.logger import get_logger
from app.utils.image_utils import cleanup_temp

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    """Application lifespan: prepare directories and clean stale files.

    The OCR model is intentionally NOT loaded here; it loads lazily on
    the first OCR request.
    """
    settings.ensure_directories()
    cleanup_temp()
    logger.info("Server started: %s v%s", settings.PROJECT_NAME, settings.VERSION)
    yield
    logger.info("%s shutting down.", settings.PROJECT_NAME)


def create_app() -> FastAPI:
    """Application factory.

    Returns:
        A fully configured FastAPI application with CORS, versioned
        routers, and centralized error handling.
    """
    application = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        description="OCR backend for reading food label images.",
        debug=settings.DEBUG,
        lifespan=lifespan,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(v1.router)
    register_exception_handlers(application)

    @application.get("/", include_in_schema=False)
    async def root() -> Dict[str, object]:
        """Service metadata for anyone hitting the API root."""
        return {
            "success": True,
            "message": f"{settings.PROJECT_NAME} v{settings.VERSION}",
            "data": {
                "docs": "/docs",
                "health": "/api/v1/health",
                "upload": "/api/v1/upload",
            },
        }

    return application


app = create_app()
