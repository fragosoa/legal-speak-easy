import base64
import gzip
import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone
from typing import Annotated, Optional

import anthropic
import openai
from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.config import Settings, get_settings
from app.core.exceptions import FileTooLargeError, UnsupportedFileTypeError
from app.schemas.contract import (
    AnalyzeContractResponse,
    AskQuestionRequest,
    AskQuestionResponse,
    DocumentMetadata,
)
from app.services import document_parser
from app.services.ai_service import AIService
from app.services.claude_service import ClaudeService
from app.services.pipeline_orchestrator import PipelineOrchestrator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/contracts", tags=["contracts"])

_SUPPORTED_CONTENT_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


def get_pipeline_orchestrator(
    settings: Annotated[Settings, Depends(get_settings)],
) -> PipelineOrchestrator:
    return PipelineOrchestrator(
        openai_service=AIService(
            client=openai.OpenAI(api_key=settings.openai_api_key),
            model=settings.openai_model,
            max_tokens=settings.openai_max_tokens,
        ),
        claude_service=ClaudeService(
            client=anthropic.Anthropic(api_key=settings.anthropic_api_key),
            model=settings.claude_model,
            max_tokens=settings.openai_max_tokens,
        ),
        include_perspectives=(settings.app_env != "production"),
    )


def _build_context_token(text: str, contract_type: Optional[str], secret_key: str) -> str:
    """Build a signed, gzip-compressed context token for future Q&A use."""
    compressed = gzip.compress(text.encode("utf-8"), compresslevel=6)
    text_b64 = base64.b64encode(compressed).decode("ascii")
    payload = {
        "v": 1,
        "contract_type": contract_type,
        "text_hash": hashlib.sha256(text.encode()).hexdigest(),
        "text_b64": text_b64,
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
    }
    payload_bytes = json.dumps(payload).encode("utf-8")
    signature = hmac.new(
        secret_key.encode("utf-8"), payload_bytes, hashlib.sha256
    ).hexdigest()
    envelope = {"payload": payload, "sig": signature}
    return base64.b64encode(json.dumps(envelope).encode("utf-8")).decode("ascii")


@router.post("/analyze", response_model=AnalyzeContractResponse)
async def analyze_contract(
    file: Annotated[UploadFile, File(description="PDF or DOCX contract, max 10 MB")],
    contract_type: Annotated[
        Optional[str],
        Form(description="Optional hint: 'rent' or 'work'"),
    ] = None,
    settings: Settings = Depends(get_settings),
    orchestrator: PipelineOrchestrator = Depends(get_pipeline_orchestrator),
) -> AnalyzeContractResponse:
    # Validate file size
    file_bytes = await file.read()
    max_bytes = settings.max_file_size_mb * 1024 * 1024
    if len(file_bytes) > max_bytes:
        raise FileTooLargeError(
            f"File exceeds maximum allowed size of {settings.max_file_size_mb} MB."
        )

    # Validate content type as a first pass (magic bytes checked inside parser)
    if file.content_type and file.content_type not in _SUPPORTED_CONTENT_TYPES:
        raise UnsupportedFileTypeError(
            "Unsupported file type. Only PDF and DOCX files are accepted."
        )

    # Parse document
    parsed = document_parser.parse(file_bytes, file.filename or "upload")

    # Truncate text if needed to control API cost
    truncated = len(parsed.text) > settings.contract_text_max_chars
    if truncated:
        logger.warning(
            "Contract text truncated from %d to %d chars for file '%s'",
            len(parsed.text),
            settings.contract_text_max_chars,
            file.filename,
        )
        parsed.text = parsed.text[: settings.contract_text_max_chars]

    # Run multi-model pipeline: A + B in parallel, then C reconciles
    final_analysis, perspectives, pipeline_meta = await orchestrator.run(
        parsed_doc=parsed,
        contract_type=contract_type,
    )

    # Build context token for future Q&A
    context_token = _build_context_token(parsed.text, contract_type, settings.secret_key)

    return AnalyzeContractResponse(
        contract_type=contract_type,
        document_metadata=DocumentMetadata(
            filename=file.filename or "upload",
            file_type=parsed.file_type,  # type: ignore[arg-type]
            page_count=parsed.page_count,
            word_count=parsed.word_count,
            extraction_method=parsed.extraction_method,
            truncated=truncated,
        ),
        summary=final_analysis.summary,
        legal_terms=final_analysis.legal_terms,
        context_token=context_token,
        model_perspectives=perspectives,
        pipeline_metadata=pipeline_meta,
    )


@router.post("/ask", response_model=AskQuestionResponse)
async def ask_question(body: AskQuestionRequest) -> AskQuestionResponse:
    """Q&A endpoint — scaffolded for future implementation."""
    from fastapi import HTTPException
    raise HTTPException(
        status_code=501,
        detail="Q&A feature is not yet available. Coming soon.",
    )
