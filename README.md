# Legal Speak Easy

> Your Daily Law Companion — AI-powered backend that translates legal contracts into plain language.

---

## Problem

Young professionals frequently sign legally binding contracts — leases, employment agreements, freelance contracts — without fully understanding what they are agreeing to. Legal language is intentionally precise, but that precision makes it inaccessible to anyone without a legal background. Hiring a lawyer to review a standard rent or work contract is expensive and often impractical.

The result: people sign documents they don't understand, sometimes with significant financial or legal consequences.

---

## Solution

Legal Speak Easy is an AI-powered backend API that accepts a contract file (PDF or DOCX) and returns a plain-language breakdown of what it says. The system is designed for young professionals who want confidence before they sign — not legal advice, but genuine comprehension.

A user uploads their contract and gets back:

- A **plain-language summary** of the entire document
- A list of **key facts** (rent amount, duration, deposit, deadlines)
- **Risk flags** ranked by severity — clauses that create unexpected obligations or restrict rights
- Definitions of **legal terms** found in the document, with the exact sentence where each appears and a plain explanation of why it matters

**Target users:** Young professionals signing rent and work contracts who want to fully understand their documents without hiring a lawyer.

---

## Multi-Model AI Pipeline

The system uses three AI calls per request to improve accuracy and reduce hallucinations.

A single LLM can misread, skip, or misinterpret clauses — especially in dense legal text. To address this, the system runs two models independently and then uses a reconciliation step:

```
Contract uploaded
      │
      ├──> Model A: GPT-4o        (independent analysis)
      └──> Model B: Claude         (independent analysis)
            [both run in parallel]
                    │
                    ▼
           Model A: GPT-4o         (reconciliation call)
           — compares both outputs
           — merges facts, deduplicates terms
           — escalates risk flags where both models agreed
                    │
                    ▼
             Final response
```

- Two models analyzing the same contract independently reduces the chance that a misread clause slips through
- The reconciliation step instructs GPT-4o to prefer facts grounded in the contract text when models disagree
- Risk flags are escalated when both models flagged the same clause at different severity levels
- If one model fails, the reconciliation call runs with the surviving model's output and `pipeline_metadata.fallback_used` is set to `true`

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Framework | FastAPI |
| Model A + Reconciliation | OpenAI GPT-4o (`gpt-4o`) |
| Model B | Anthropic Claude (`claude-sonnet-4-6`) |
| PDF parsing | pdfplumber |
| DOCX parsing | python-docx |
| Config | pydantic-settings |
| Runtime | Python 3.9+ |
| Deployment | Railway |

---

## Project Structure

```
legal-speak-easy/
├── app/
│   ├── main.py                       # FastAPI app, CORS, exception handlers
│   ├── config.py                     # Environment variable settings
│   ├── routers/
│   │   └── contracts.py              # API endpoints + pipeline wiring
│   ├── services/
│   │   ├── document_parser.py        # PDF and DOCX text extraction
│   │   ├── ai_service.py             # GPT-4o: analysis + reconciliation
│   │   ├── claude_service.py         # Claude: independent analysis
│   │   └── pipeline_orchestrator.py  # Parallel execution + fallback logic
│   ├── schemas/
│   │   └── contract.py               # Pydantic request/response models
│   └── core/
│       └── exceptions.py             # Custom exceptions and error handlers
├── tests/
│   ├── test_document_parser.py
│   └── test_contracts_router.py
├── Procfile                          # Railway deployment start command
├── runtime.txt                       # Python version for Railway
├── requirements.txt
└── .env.example
```

---

## Getting Started

### Prerequisites

- Python 3.9+
- An [OpenAI API key](https://platform.openai.com/api-keys)
- An [Anthropic API key](https://console.anthropic.com/)

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/fragosoa/legal-speak-easy.git
cd legal-speak-easy

# 2. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up environment variables
cp .env.example .env
```

Edit `.env` and fill in the required values:

```bash
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
SECRET_KEY=<run: python -c "import secrets; print(secrets.token_hex(32))">
```

### Run the development server

```bash
uvicorn app.main:app --reload --port 8000
```

The API is now available at `http://localhost:8000`.

Interactive documentation (Swagger UI): `http://localhost:8000/docs`

---

## API Reference

### `GET /api/v1/health`

Liveness check. Returns the current status and model in use.

**Response**
```json
{
  "status": "ok",
  "model": "gpt-4o"
}
```

---

### `POST /api/v1/contracts/analyze`

Uploads a contract file and returns a full AI-powered analysis in plain language.

**Request** — `multipart/form-data`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file` | File | Yes | PDF or DOCX contract, max 10 MB |
| `contract_type` | Text | No | Hint for better analysis: `rent` or `work` |

**Response** — `200 OK`

```json
{
  "contract_type": "rent",
  "document_metadata": {
    "filename": "lease_agreement.pdf",
    "file_type": "pdf",
    "page_count": 8,
    "word_count": 3241,
    "extraction_method": "pdfplumber",
    "truncated": false
  },
  "summary": {
    "plain_language": "This is a 12-month lease for an apartment at 123 Main St. Your monthly rent is $1,800 due on the 1st of each month. You must give 60 days written notice before moving out. Breaking the lease early requires paying 2 months rent as a penalty.",
    "key_facts": [
      "Monthly rent: $1,800",
      "Lease duration: 12 months (Jan 1 2026 – Dec 31 2026)",
      "Security deposit: $3,600 (2 months rent)",
      "Notice to vacate: 60 days written notice",
      "Early termination penalty: 2 months rent"
    ],
    "risk_flags": [
      {
        "severity": "high",
        "description": "Automatic renewal clause: the lease renews for another 12 months unless you give 60 days written notice before the expiry date."
      },
      {
        "severity": "medium",
        "description": "The landlord can charge for any 'damage beyond normal wear and tear' — this term is vague and deposit disputes are common."
      }
    ]
  },
  "legal_terms": [
    {
      "term": "indemnification",
      "original_context": "Tenant agrees to indemnify and hold harmless the Landlord from any claims arising from Tenant's use of the premises.",
      "plain_definition": "You agree to cover the landlord's legal costs and damages if someone sues them because of something you did.",
      "why_it_matters": "You could be financially responsible for accidents or incidents in your unit even if the landlord is partly at fault."
    }
  ],
  "pipeline_metadata": {
    "model_a_succeeded": true,
    "model_b_succeeded": true,
    "reconciliation_model": "gpt-4o",
    "fallback_used": false,
    "fallback_reason": null
  },
  "model_perspectives": "<individual model outputs, included in development mode only>",
  "context_token": "<signed token for future Q&A use>"
}
```

**Error responses**

| Status | Cause |
|--------|-------|
| `400` | Unsupported file type (not PDF or DOCX) |
| `413` | File exceeds the 10 MB size limit |
| `422` | Text could not be extracted (e.g. scanned image PDF) |
| `502` | AI service unavailable |

---

### `POST /api/v1/contracts/ask` *(coming soon)*

> **Note:** This endpoint is scaffolded but not yet implemented — it currently returns `501 Not Implemented`.
>
> The planned feature allows users to ask follow-up questions about a contract they already analyzed. The `context_token` returned by `/analyze` will be passed back alongside the question — no re-upload needed. The server decodes the token to recover the contract text and answers the question in context.

**Planned request body**

```json
{
  "context_token": "<token from /analyze response>",
  "question": "Can my landlord keep my deposit if I leave 30 days early?"
}
```

**Planned response**

```json
{
  "answer": "Based on the contract, you are required to give 60 days written notice before leaving...",
  "source_excerpt": "Section 9.2: Tenant must provide 60 days written notice prior to vacating the premises..."
}
```

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENAI_API_KEY` | Yes | — | OpenAI API key (GPT-4o) |
| `ANTHROPIC_API_KEY` | Yes | — | Anthropic API key (Claude) |
| `SECRET_KEY` | Yes | — | Random secret for signing context tokens |
| `OPENAI_MODEL` | No | `gpt-4o` | OpenAI model for analysis and reconciliation |
| `OPENAI_MAX_TOKENS` | No | `4096` | Max tokens per AI response |
| `CLAUDE_MODEL` | No | `claude-sonnet-4-6` | Anthropic model for independent analysis |
| `APP_ENV` | No | `development` | `development` or `production` |
| `MAX_FILE_SIZE_MB` | No | `10` | Maximum upload size in MB |
| `CONTRACT_TEXT_MAX_CHARS` | No | `80000` | Text truncation limit before sending to AI |
| `ALLOWED_ORIGINS` | No | `http://localhost:3000,...` | Comma-separated CORS origins |

> In `development` mode, the response includes `model_perspectives` showing the raw outputs from GPT-4o and Claude before reconciliation. This field is omitted in `production`.

---

## Running Tests

```bash
pytest tests/ -v
```

---

## Deployment

This project is configured for one-click deployment on [Railway](https://railway.app). The `Procfile` and `runtime.txt` are already included.

```bash
# Production start command (used by Railway automatically)
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Key points:
- Set all environment variables in the Railway dashboard — never commit `.env`
- Railway injects the `PORT` variable automatically
- Push to `main` triggers automatic redeploys

---

## Disclaimer

Legal Speak Easy is an educational tool. It explains what contracts say in plain language — it does not provide legal advice. Always consult a qualified lawyer before signing any legal document.
