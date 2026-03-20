from fastapi import Request
from fastapi.responses import JSONResponse


class ExtractionError(Exception):
    """Raised when text cannot be extracted from an uploaded document."""
    pass


class UnsupportedFileTypeError(Exception):
    """Raised when the uploaded file type is not PDF or DOCX."""
    pass


class FileTooLargeError(Exception):
    """Raised when the uploaded file exceeds the size limit."""
    pass


class AIServiceError(Exception):
    """Raised when the Claude API call fails or returns unparseable output."""
    pass


async def extraction_error_handler(request: Request, exc: ExtractionError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": str(exc)})


async def unsupported_file_type_handler(request: Request, exc: UnsupportedFileTypeError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(exc)})


async def file_too_large_handler(request: Request, exc: FileTooLargeError) -> JSONResponse:
    return JSONResponse(status_code=413, content={"detail": str(exc)})


async def ai_service_error_handler(request: Request, exc: AIServiceError) -> JSONResponse:
    return JSONResponse(status_code=502, content={"detail": str(exc)})
