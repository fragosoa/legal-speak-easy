# Legal Speak Easy

> Your Daily Law Companion — AI-powered backend that translates legal contracts into plain language.

Legal Speak Easy helps non-lawyers understand what they sign. Upload a work or rent contract (PDF or DOCX) and get back a plain-language summary, a list of key facts, risk flags, and definitions of legal terminology — all powered by OpenAI GPT-4o.

**Target users:** Young professionals signing rent and work contracts who want to fully understand their documents without hiring a lawyer.

---

## Features

- **Plain-language summary** — 2-4 sentence overview of the entire contract
- **Key facts extraction** — specific numbers, dates, and amounts (rent price, duration, deposit, notice periods)
- **Risk flags** — clauses with unexpected obligations or restrictions, ranked by severity (high / medium / low)
- **Legal term definitions** — 5-15 terms identified in the document, each with a verbatim quote, plain definition, and explanation of practical impact
- **PDF and DOCX support** — file type detected by content (not filename extension)
- **Stateless design** — no database required; a signed context token is returned for future Q&A use

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Framework | FastAPI |
| AI | OpenAI GPT-4o (`gpt-4o`) |
| PDF parsing | pdfplumber |
| DOCX parsing | python-docx |
| Config | pydantic-settings |
| Runtime | Python 3.9+ |

---

## Project Structure

```
legal-speak-easy/
├── app/
│   ├── main.py                  # FastAPI app, CORS, exception handlers
│   ├── config.py                # Environment variable settings
│   ├── routers/
│   │   └── contracts.py         # API endpoints
│   ├── services/
│   │   ├── document_parser.py   # PDF and DOCX text extraction
│   │   └── ai_service.py        # OpenAI integration and prompt logic
│   ├── schemas/
│   │   └── contract.py          # Pydantic request/response models
│   └── core/
│       └── exceptions.py        # Custom exceptions and error handlers
├── tests/
│   ├── test_document_parser.py
│   └── test_contracts_router.py
├── Procfile                     # Railway deployment start command
├── runtime.txt                  # Python version for Railway
├── requirements.txt
└── .env.example
```

---

## Getting Started

### Prerequisites

- Python 3.9+
- An [OpenAI API key](https://platform.openai.com/api-keys)

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
    },
    {
      "term": "force majeure",
      "original_context": "Neither party shall be liable for delays caused by force majeure events beyond their reasonable control.",
      "plain_definition": "Neither side is responsible for failing to meet obligations if an extraordinary event outside their control occurs (e.g. natural disaster, pandemic).",
      "why_it_matters": "This could limit your ability to break the lease without penalty during unusual circumstances."
    }
  ],
  "context_token": "<signed token for future Q&A use>"
}
```

**Error responses**

| Status | Cause |
|--------|-------|
| `400` | Unsupported file type (not PDF or DOCX) |
| `413` | File exceeds the 10 MB size limit |
| `422` | Text could not be extracted (e.g. scanned image PDF) |
| `502` | OpenAI API is unavailable |

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
  "answer": "Based on the contract, you are required to give 60 days written notice before leaving. Leaving 30 days early means you did not meet this requirement, so the landlord may be entitled to keep part of your deposit and charge an early termination fee equivalent to 2 months rent (Section 9.2).",
  "source_excerpt": "Section 9.2: Tenant must provide 60 days written notice prior to vacating the premises..."
}
```

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENAI_API_KEY` | Yes | — | Your OpenAI API key |
| `SECRET_KEY` | Yes | — | Random secret for signing context tokens |
| `OPENAI_MODEL` | No | `gpt-4o` | OpenAI model to use |
| `OPENAI_MAX_TOKENS` | No | `4096` | Max tokens for AI response |
| `APP_ENV` | No | `development` | `development` or `production` |
| `MAX_FILE_SIZE_MB` | No | `10` | Maximum upload size in MB |
| `CONTRACT_TEXT_MAX_CHARS` | No | `80000` | Text truncation limit before sending to AI |
| `ALLOWED_ORIGINS` | No | `http://localhost:3000,...` | Comma-separated CORS origins |

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
