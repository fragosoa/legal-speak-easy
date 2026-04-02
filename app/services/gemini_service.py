import json
import logging
from typing import Optional

import google.genai as genai
import google.genai.types as genai_types

from app.core.exceptions import AIServiceError
from app.schemas.contract import ContractAnalysis
from app.services.ai_service import _JSON_SCHEMA_BLOCK

logger = logging.getLogger(__name__)

_RECONCILE_SYSTEM_PROMPT = """\
You are a senior legal document review AI acting as an arbitrator.
You will receive two independent analyses of the same contract, produced by two separate AI systems.
Your task is to produce one single, authoritative, reconciled analysis.

Rules:
- Where both analyses agree, reflect that consensus.
- Where they disagree on facts (dates, amounts, names), prefer the version supported by the contract text.
- Where they disagree on risk assessment or interpretation, synthesize a balanced view that captures the most important concerns from both.
- Do not invent clauses or terms not present in either analysis.
- Do not include a legal term in the final output unless at least one of the two analyses identified it.
- Always respond with ONLY a raw JSON object. No markdown fences, no prose.
- Use plain, direct language at an 8th-grade reading level.\
"""

_RECONCILE_USER_TEMPLATE = """\
You are reconciling two independent AI analyses of the following {contract_type_hint}contract.

=== ANALYSIS FROM MODEL A (OpenAI GPT-4o) ===
{analysis_a_json}

=== ANALYSIS FROM MODEL B (Anthropic Claude) ===
{analysis_b_json}

Produce a single reconciled JSON object with exactly this structure:

{json_schema}

Guidelines for reconciliation:
- plain_language: Synthesize a summary that captures the most accurate and complete picture from both models.
- key_facts: Include all facts from both analyses, deduplicating where identical. Prefer the most specific version.
- risk_flags: Include all risk flags from either model. Consolidate duplicates. Escalate severity if both models flagged the same risk at different levels.
- legal_terms: Include terms identified by either model. For conflicts in definition, write the most accurate and clearest version.

Respond ONLY with the JSON object. No preamble, no explanation outside the JSON.\
"""

_SINGLE_MODEL_USER_TEMPLATE = """\
You are reviewing and finalizing an AI analysis of the following {contract_type_hint}contract.

=== ANALYSIS FROM MODEL {model_label} ===
{analysis_json}

Review the analysis and produce a final validated JSON object with exactly this structure:

{json_schema}

Respond ONLY with the JSON object. No preamble, no explanation outside the JSON.\
"""


class GeminiService:
    def __init__(self, client: genai.Client, model: str, max_tokens: int) -> None:
        self._client = client
        self._model = model
        self._max_tokens = max_tokens

    def reconcile(
        self,
        analysis_a: ContractAnalysis,
        analysis_b: ContractAnalysis,
        contract_type: Optional[str],
        single_model_label: Optional[str] = None,
    ) -> ContractAnalysis:
        contract_type_hint = f"{contract_type} " if contract_type else ""

        if single_model_label is not None:
            prompt = _SINGLE_MODEL_USER_TEMPLATE.format(
                contract_type_hint=contract_type_hint,
                model_label=single_model_label,
                analysis_json=analysis_a.model_dump_json(indent=2),
                json_schema=_JSON_SCHEMA_BLOCK,
            )
        else:
            prompt = _RECONCILE_USER_TEMPLATE.format(
                contract_type_hint=contract_type_hint,
                analysis_a_json=analysis_a.model_dump_json(indent=2),
                analysis_b_json=analysis_b.model_dump_json(indent=2),
                json_schema=_JSON_SCHEMA_BLOCK,
            )

        raw_json = self._call_gemini(prompt)
        return self._parse_response(raw_json, retry_prompt=prompt)

    def _call_gemini(self, prompt: str) -> str:
        try:
            response = self._client.models.generate_content(
                model=self._model,
                contents=prompt,
                config=genai_types.GenerateContentConfig(
                    system_instruction=_RECONCILE_SYSTEM_PROMPT,
                    max_output_tokens=self._max_tokens,
                    response_mime_type="application/json",
                ),
            )
        except Exception as exc:
            logger.error("Gemini API error [%s]: %s", type(exc).__name__, exc)
            raise AIServiceError(
                "Gemini reconciliation service is temporarily unavailable. Please try again."
            ) from exc
        return response.text

    def _parse_response(self, raw_json: str, retry_prompt: str) -> ContractAnalysis:
        try:
            data = json.loads(raw_json)
            return ContractAnalysis.model_validate(data)
        except (json.JSONDecodeError, ValueError):
            logger.warning("Gemini returned invalid JSON; retrying once.")

        retry = (
            retry_prompt
            + "\n\nIMPORTANT: Your previous response was not valid JSON. "
            "Return ONLY the raw JSON object, nothing else."
        )
        raw_json_retry = self._call_gemini(retry)

        try:
            data = json.loads(raw_json_retry)
            return ContractAnalysis.model_validate(data)
        except (json.JSONDecodeError, ValueError) as exc:
            raise AIServiceError(
                "Gemini reconciliation service returned an unexpected response. Please try again."
            ) from exc
