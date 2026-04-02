import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional, Tuple

from app.core.exceptions import AIServiceError
from app.schemas.contract import ContractAnalysis, ModelPerspective, PipelineMetadata
from app.services.ai_service import AIService
from app.services.claude_service import ClaudeService
from app.services.document_parser import ParsedDocument
from app.services.gemini_service import GeminiService

logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=4)


class PipelineOrchestrator:
    def __init__(
        self,
        openai_service: AIService,
        claude_service: ClaudeService,
        gemini_service: GeminiService,
        include_perspectives: bool = False,
    ) -> None:
        self._openai_service = openai_service
        self._claude_service = claude_service
        self._gemini_service = gemini_service
        self._include_perspectives = include_perspectives

    async def run(
        self,
        parsed_doc: ParsedDocument,
        contract_type: Optional[str],
    ) -> Tuple[ContractAnalysis, Optional[List[ModelPerspective]], PipelineMetadata]:
        loop = asyncio.get_running_loop()

        # Run Model A and Model B in parallel on separate threads
        future_a = loop.run_in_executor(
            _executor, self._openai_service.analyze_contract, parsed_doc, contract_type
        )
        future_b = loop.run_in_executor(
            _executor, self._claude_service.analyze_contract, parsed_doc, contract_type
        )

        result_a: Optional[ContractAnalysis] = None
        result_b: Optional[ContractAnalysis] = None
        error_a: Optional[Exception] = None
        error_b: Optional[Exception] = None

        try:
            result_a = await future_a
        except Exception as exc:
            error_a = exc
            logger.error("Model A (OpenAI) failed: %s", exc)

        try:
            result_b = await future_b
        except Exception as exc:
            error_b = exc
            logger.error("Model B (Claude) failed: %s", exc)

        if result_a is None and result_b is None:
            raise AIServiceError(
                "All AI analysis services are currently unavailable. Please try again."
            )

        # Determine fallback mode
        fallback_used = error_a is not None or error_b is not None
        fallback_reason: Optional[str] = None
        single_model_label: Optional[str] = None

        if error_a is not None and result_b is not None:
            fallback_reason = "model_a_failed"
            single_model_label = "B (Anthropic Claude)"
            effective_a = result_b
            effective_b = result_b
        elif error_b is not None and result_a is not None:
            fallback_reason = "model_b_failed"
            single_model_label = "A (OpenAI GPT-4o)"
            effective_a = result_a
            effective_b = result_a
        else:
            effective_a = result_a  # type: ignore[assignment]
            effective_b = result_b  # type: ignore[assignment]

        # Run Model C (Gemini) on a thread as well
        final = await loop.run_in_executor(
            _executor,
            self._gemini_service.reconcile,
            effective_a,
            effective_b,
            contract_type,
            single_model_label,
        )

        perspectives: Optional[List[ModelPerspective]] = None
        if self._include_perspectives:
            perspectives = []
            if result_a is not None:
                perspectives.append(ModelPerspective(
                    model=self._openai_service._model,
                    provider="openai",
                    analysis=result_a,
                ))
            if result_b is not None:
                perspectives.append(ModelPerspective(
                    model=self._claude_service._model,
                    provider="anthropic",
                    analysis=result_b,
                ))

        metadata = PipelineMetadata(
            model_a_succeeded=error_a is None,
            model_b_succeeded=error_b is None,
            reconciliation_model=self._gemini_service._model,
            fallback_used=fallback_used,
            fallback_reason=fallback_reason,
        )

        return final, perspectives, metadata
