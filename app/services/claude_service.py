import json
import logging
from typing import Optional

import anthropic

from app.core.exceptions import AIServiceError
from app.schemas.contract import ContractAnalysis
from app.services.ai_service import _JSON_SCHEMA_BLOCK, _USER_PROMPT_TEMPLATE
from app.services.document_parser import ParsedDocument

logger = logging.getLogger(__name__)

_CLAUDE_SYSTEM_PROMPT = """\
You are a legal document assistant that helps non-lawyers understand contracts.
Your audience is young professionals with no legal background.

Rules:
- Always respond with ONLY a raw JSON object. No markdown fences, no prose, no explanation.
- Use plain, direct language. Aim for an 8th-grade reading level.
- Never give legal advice. Explain what the contract says, not what the person should do.
- Do not invent clauses or terms that are not present in the document.
- If a section is ambiguous or unclear, say so plainly in your explanation.
- Flag anything that deviates significantly from standard contracts of the specified type.\
"""


class ClaudeService:
    def __init__(self, client: anthropic.Anthropic, model: str, max_tokens: int) -> None:
        self._client = client
        self._model = model
        self._max_tokens = max_tokens

    def analyze_contract(
        self, parsed_doc: ParsedDocument, contract_type: Optional[str]
    ) -> ContractAnalysis:
        contract_type_hint = f"{contract_type} " if contract_type else ""
        user_prompt = _USER_PROMPT_TEMPLATE.format(
            contract_type_hint=contract_type_hint,
            json_schema=_JSON_SCHEMA_BLOCK,
            contract_text=parsed_doc.text,
        )
        raw_json = self._call_claude(user_prompt)
        return self._parse_response(raw_json, retry_prompt=user_prompt)

    def _call_claude(self, user_prompt: str) -> str:
        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
                system=_CLAUDE_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}],
            )
        except anthropic.APIError as exc:
            logger.error(
                "Claude API error [%s]: %s", type(exc).__name__, exc
            )
            raise AIServiceError(
                "Claude analysis service is temporarily unavailable. Please try again."
            ) from exc
        return response.content[0].text

    def _parse_response(self, raw_json: str, retry_prompt: str) -> ContractAnalysis:
        try:
            data = json.loads(raw_json)
            return ContractAnalysis.model_validate(data)
        except (json.JSONDecodeError, ValueError):
            logger.warning("Claude returned invalid JSON; retrying once.")

        retry = (
            retry_prompt
            + "\n\nIMPORTANT: Your previous response was not valid JSON. "
            "Return ONLY the raw JSON object, nothing else. No markdown, no backticks."
        )
        raw_json_retry = self._call_claude(retry)

        try:
            data = json.loads(raw_json_retry)
            return ContractAnalysis.model_validate(data)
        except (json.JSONDecodeError, ValueError) as exc:
            raise AIServiceError(
                "Claude analysis service returned an unexpected response. Please try again."
            ) from exc
