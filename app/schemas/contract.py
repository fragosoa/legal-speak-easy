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


# --- AI service internal model (what OpenAI returns) ---

class ContractAnalysis(BaseModel):
    summary: ContractSummary
    legal_terms: List[LegalTerm]


# --- Multi-model pipeline metadata ---

class ModelPerspective(BaseModel):
    model: str
    provider: str
    analysis: ContractAnalysis


class PipelineMetadata(BaseModel):
    model_a_succeeded: bool
    model_b_succeeded: bool
    reconciliation_model: str
    fallback_used: bool = False
    fallback_reason: Optional[str] = None


# --- API request/response models ---

class AnalyzeContractResponse(BaseModel):
    contract_type: Optional[str]
    document_metadata: DocumentMetadata
    summary: ContractSummary
    legal_terms: List[LegalTerm]
    context_token: str
    model_perspectives: Optional[List[ModelPerspective]] = None
    pipeline_metadata: Optional[PipelineMetadata] = None


class AskQuestionRequest(BaseModel):
    context_token: str
    question: str


class AskQuestionResponse(BaseModel):
    answer: str
    source_excerpt: Optional[str] = None
