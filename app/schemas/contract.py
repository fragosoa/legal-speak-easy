from typing import List, Literal, Optional
from pydantic import BaseModel


# --- Sub-models ---

class DocumentMetadata(BaseModel):
    filename: str
    file_type: Literal["pdf", "docx"]
    page_count: int
    word_count: int
    extraction_method: str
    truncated: bool = False


class RiskFlag(BaseModel):
    severity: Literal["high", "medium", "low"]
    description: str


class ContractSummary(BaseModel):
    plain_language: str
    key_facts: List[str]
    risk_flags: List[RiskFlag]


class LegalTerm(BaseModel):
    term: str
    original_context: str
    plain_definition: str
    why_it_matters: str


# --- AI service internal model (what Claude returns) ---

class ContractAnalysis(BaseModel):
    summary: ContractSummary
    legal_terms: List[LegalTerm]


# --- API request/response models ---

class AnalyzeContractResponse(BaseModel):
    contract_type: Optional[str]
    document_metadata: DocumentMetadata
    summary: ContractSummary
    legal_terms: List[LegalTerm]
    context_token: str


class AskQuestionRequest(BaseModel):
    context_token: str
    question: str


class AskQuestionResponse(BaseModel):
    answer: str
    source_excerpt: Optional[str] = None
