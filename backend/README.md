# Food Label Reader Backend

A production-grade FastAPI OCR backend that extracts text from food label
images using PaddleOCR. This service is the foundation of an AI Food Label
Reader: upload a label photo and receive cleaned, structured text with
per-line confidence scores.

## Architecture

The codebase follows a strict layered architecture:

```
HTTP request
    v
API layer (app/api/v1)          - routing, request validation, DI wiring
    v
Service layer (app/services)    - preprocessing, OCR, text cleanup, formatting
    v
Utility layer (app/utils)       - stateless helpers (files, text)
    v
Core layer (app/core)           - configuration, logging, exceptions
```

Key design decisions:

- **API versioning** - all routes live under `/api/v1`. New versions get
  their own router package without touching v1.
- **Lazy OCR loading** - PaddleOCR does NOT load at startup. It loads on
  the first OCR request via a thread-safe (double-checked locking)
  singleton, and the same instance serves every subsequent request.
- **Dependency injection** - routes never instantiate services. Providers
  in `app/api/deps.py` build each service once per process and inject
  them with FastAPI `Depends`, making tests trivially overridable.
- **Centralized error handling** - `app/core/exceptions.py` defines typed
  application errors and registers handlers so every error returns the
  same JSON shape.
- **Environment-driven configuration** - all settings come from
  environment variables (see `.env.example`) via `pydantic-settings`.
- **Temporary uploads** - uploaded images are deleted immediately after
  processing (success or failure), and stale files are purged at startup
  via `cleanup_temp()`.

## Folder Structure

```
backend/
    app/
        api/
            deps.py             # Dependency-injection providers
            v1/
                __init__.py     # /api/v1 aggregate router
                health.py       # GET /api/v1/health
                upload.py       # POST /api/v1/upload (OCR pipeline)
        core/
            config.py           # Env-driven settings (pydantic-settings)
            exceptions.py       # Typed errors + FastAPI exception handlers
            logger.py           # Timestamped console logging
        services/
            preprocess.py       # Resize, denoise, CLAHE, sharpen, deskew
            ocr_engine.py       # Lazy thread-safe PaddleOCR singleton
            text_processor.py   # Clean, dedupe, merge split lines
            json_formatter.py   # Internal results -> response schema
            interfaces.py       # Protocols for future pipeline modules
        models/
            response.py         # Envelope + payload Pydantic models
        utils/
            image_utils.py      # Validation, storage, cleanup_temp()
            text_utils.py       # Whitespace / merge helpers
        main.py                 # App factory, CORS, routers, lifespan
    outputs/                    # Processing artifacts (gitkept)
    temp/                       # Transient uploads (auto-cleaned)
    tests/
        test_health.py
        test_upload.py
        test_ocr_service.py
    .env.example
    .gitignore
    requirements.txt
    README.md
```

## Installation

Requires Python 3.11.

```bash
cd backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
```

## Running

```bash
cd backend
uvicorn app.main:app --reload
```

The server starts on `http://127.0.0.1:8000`. Interactive docs are at
`http://127.0.0.1:8000/docs`. The PaddleOCR model (~20 MB) downloads on
the first upload request, so the first call is slower than the rest.

## Endpoints

### GET /api/v1/health

```json
{
    "success": true,
    "message": "Service is healthy.",
    "data": {
        "status": "healthy",
        "service": "Food Label Reader Backend",
        "version": "2.0.0"
    }
}
```

### POST /api/v1/upload

Multipart form upload with a `file` field (jpg, jpeg, or png; max 15 MB).

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/upload" \
     -F "file=@/path/to/food-label.jpg"
```

Success response:

```json
{
    "success": true,
    "message": "Image processed successfully.",
    "data": {
        "processing_time": "1.42s",
        "ocr": {
            "average_confidence": 0.9631,
            "raw_text": "INGREDIENTS: WHEAT FLOUR,\nSUGAR, PALM OIL.",
            "clean_text": "INGREDIENTS: WHEAT FLOUR, SUGAR, PALM OIL.",
            "lines": [
                {
                    "text": "INGREDIENTS: WHEAT FLOUR,",
                    "confidence": 0.9712,
                    "bounding_box": [[12.0, 34.0], [410.0, 34.0], [410.0, 62.0], [12.0, 62.0]]
                }
            ]
        }
    }
}
```

Error response (consistent for every failure):

```json
{
    "success": false,
    "message": "Invalid upload.",
    "error": "Uploaded file is not a valid image.",
    "status_code": 400
}
```

Status codes: `400` invalid file, `413` too large, `422` missing file,
`500` OCR failure.

## Testing

```bash
cd backend
pytest tests/ -v
```

## Configuration

All settings are environment variables; see `.env.example` for the full
list and defaults (`PROJECT_NAME`, `VERSION`, `DEBUG`, `UPLOAD_FOLDER`,
`OUTPUT_FOLDER`, `MAX_FILE_SIZE`, `ALLOWED_EXTENSIONS`,
`ALLOWED_MIME_TYPES`, `OCR_LANGUAGE`, `LOG_LEVEL`, and preprocessing
bounds).

## Future Roadmap

The target pipeline, with clean interfaces already defined in
`app/services/interfaces.py`:

```
Image Upload
    -> Preprocessing
    -> PaddleOCR
    -> Text Processing
    -> Structured Extraction   (StructuredExtractor)
    -> Ingredient Parser       (IngredientParser)
    -> Nutrition Parser        (NutritionParser)
    -> Allergen Detector       (AllergenDetector)
    -> AI Recommendation Engine (RecommendationEngine)
    -> Frontend
```

Each future module implements its Protocol and gets wired into
`app/api/deps.py` — no changes to the existing pipeline are required.
