import json
import logging
from typing import Optional

import openai

from app.core.exceptions import AIServiceError
from app.schemas.contract import ContractAnalysis
from app.services.document_parser import ParsedDocument

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are a legal document assistant that helps non-lawyers understand contracts.
Your audience is young professionals with no legal background.

Rules:
- Always respond in valid JSON matching the schema provided in each request.
- Use plain, direct language. Aim for an 8th-grade reading level.
- Never give legal advice. Explain what the contract says, not what the person should do.
- Do not invent clauses or terms that are not present in the document.
- If a section is ambiguous or unclear, say so plainly in your explanation.
- Flag anything that deviates significantly from standard contracts of the specified type.\
"""

_USER_PROMPT_TEMPLATE = """\
Analyze the following {contract_type_hint}contract and return a JSON object with exactly this structure:

{{
  "summary": {{
    "plain_language": "<2-4 sentence plain English summary of the whole contract>",
    "key_facts": ["<fact 1>", "<fact 2>"],
    "risk_flags": [
      {{
        "severity": "high|medium|low",
        "description": "<plain language description of the risk>"
      }}
    ]
  }},
  "legal_terms": [
    {{
      "term": "<the legal term as it appears in the contract>",
      "original_context": "<verbatim sentence from the contract where this term appears>",
      "plain_definition": "<1-2 sentence plain definition>",
      "why_it_matters": "<1 sentence explaining the practical impact on the signer>"
    }}
  ]
}}

Guidelines:
- key_facts: 4-8 bullet points with specific numbers, dates, and amounts (e.g. "Monthly rent: $1,800").
- risk_flags: Include 1-5 flags. Prioritize clauses that create unexpected obligations or restrict the signer's rights.
- legal_terms: Identify between 5 and 15 terms. Prioritize:
  1. Terms that are unusual or above standard complexity for this contract type
  2. Terms that create financial obligations or restrictions on the signer
  3. Terms that limit the signer's rights in ways they might not expect
  Do NOT include obvious common words like "agreement", "party", or "clause".

CONTRACT TEXT:
---
{contract_text}
---

Respond ONLY with the JSON object. No preamble, no explanation outside the JSON.\
"""


class AIService:
    def __init__(self, client: openai.OpenAI, model: str, max_tokens: int) -> None:
        self._client = client
        self._model = model
        self._max_tokens = max_tokens

    def analyze_contract(
        self, parsed_doc: ParsedDocument, contract_type: Optional[str]
    ) -> ContractAnalysis:
        contract_type_hint = f"{contract_type} " if contract_type else ""
        user_prompt = _USER_PROMPT_TEMPLATE.format(
            contract_type_hint=contract_type_hint,
            contract_text=parsed_doc.text,
        )

        raw_json = self._call_openai(user_prompt)
        return self._parse_response(raw_json, retry_prompt=user_prompt)

    def _call_openai(self, user_prompt: str) -> str:
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                max_tokens=self._max_tokens,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
            )
        except openai.APIError as exc:
            raise AIServiceError(
                "AI analysis service is temporarily unavailable. Please try again."
            ) from exc

        return response.choices[0].message.content or ""

    def _parse_response(self, raw_json: str, retry_prompt: str) -> ContractAnalysis:
        try:
            data = json.loads(raw_json)
            return ContractAnalysis.model_validate(data)
        except (json.JSONDecodeError, ValueError):
            logger.warning("OpenAI returned invalid JSON; retrying once.")

        # Retry with explicit reminder
        retry_prompt_with_reminder = (
            retry_prompt
            + "\n\nIMPORTANT: Your previous response was not valid JSON. "
            "Return ONLY the JSON object, nothing else."
        )
        raw_json_retry = self._call_openai(retry_prompt_with_reminder)

        try:
            data = json.loads(raw_json_retry)
            return ContractAnalysis.model_validate(data)
        except (json.JSONDecodeError, ValueError) as exc:
            raise AIServiceError(
                "AI analysis service returned an unexpected response. Please try again."
            ) from exc
