from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.core.exceptions import (
    AIServiceError,
    ExtractionError,
    FileTooLargeError,
    UnsupportedFileTypeError,
    ai_service_error_handler,
    extraction_error_handler,
    file_too_large_handler,
    unsupported_file_type_handler,
)
from app.routers import contracts

app = FastAPI(
    title="Legal Speak Easy",
    description="AI-powered API that explains legal contracts in plain language.",
    version="0.1.0",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.allowed_origins.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Custom exception handlers
app.add_exception_handler(ExtractionError, extraction_error_handler)  # type: ignore[arg-type]
app.add_exception_handler(UnsupportedFileTypeError, unsupported_file_type_handler)  # type: ignore[arg-type]
app.add_exception_handler(FileTooLargeError, file_too_large_handler)  # type: ignore[arg-type]
app.add_exception_handler(AIServiceError, ai_service_error_handler)  # type: ignore[arg-type]

# Routers
app.include_router(contracts.router)


@app.get("/api/v1/health", tags=["health"])
def health() -> dict:
    return {"status": "ok", "model": settings.openai_model}
