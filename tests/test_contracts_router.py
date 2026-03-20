import io
import json
from unittest.mock import MagicMock, patch

import pytest
from docx import Document
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.contract import ContractAnalysis, ContractSummary, LegalTerm, RiskFlag


def _make_docx_bytes(paragraphs: list[str]) -> bytes:
    doc = Document()
    for text in paragraphs:
        doc.add_paragraph(text)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


_MOCK_ANALYSIS = ContractAnalysis(
    summary=ContractSummary(
        plain_language="This is a 12-month lease for an apartment.",
        key_facts=["Monthly rent: $1,800", "Duration: 12 months"],
        risk_flags=[
            RiskFlag(severity="high", description="Auto-renewal clause requires 60 days notice.")
        ],
    ),
    legal_terms=[
        LegalTerm(
            term="indemnification",
            original_context="Tenant agrees to indemnify and hold harmless the Landlord.",
            plain_definition="You cover the landlord's legal costs if they're sued because of you.",
            why_it_matters="You may be financially liable for incidents in your unit.",
        )
    ],
)


@pytest.fixture
def client():
    return TestClient(app)


class TestHealthEndpoint:
    def test_health_returns_ok(self, client):
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "model" in data


class TestAnalyzeEndpoint:
    def test_unsupported_file_type_returns_400(self, client):
        fake_file = io.BytesIO(b"NOTAFILE" * 100)
        response = client.post(
            "/api/v1/contracts/analyze",
            files={"file": ("contract.xyz", fake_file, "application/octet-stream")},
        )
        assert response.status_code == 400

    def test_analyze_docx_returns_200(self, client):
        long_text = "The tenant agrees to pay monthly rent. " * 50
        docx_bytes = _make_docx_bytes([long_text])

        with patch("app.routers.contracts.ai_service.analyze_contract", return_value=_MOCK_ANALYSIS):
            with patch("app.routers.contracts.get_ai_service") as mock_dep:
                mock_service = MagicMock()
                mock_service.analyze_contract.return_value = _MOCK_ANALYSIS
                mock_dep.return_value = mock_service

                response = client.post(
                    "/api/v1/contracts/analyze",
                    files={"file": ("lease.docx", io.BytesIO(docx_bytes), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
                    data={"contract_type": "rent"},
                )

        assert response.status_code == 200
        data = response.json()
        assert "summary" in data
        assert "legal_terms" in data
        assert "context_token" in data
        assert data["contract_type"] == "rent"

    def test_analyze_response_has_document_metadata(self, client):
        long_text = "The tenant agrees to pay monthly rent. " * 50
        docx_bytes = _make_docx_bytes([long_text])

        with patch("app.routers.contracts.get_ai_service") as mock_dep:
            mock_service = MagicMock()
            mock_service.analyze_contract.return_value = _MOCK_ANALYSIS
            mock_dep.return_value = mock_service

            response = client.post(
                "/api/v1/contracts/analyze",
                files={"file": ("lease.docx", io.BytesIO(docx_bytes), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
            )

        assert response.status_code == 200
        meta = response.json()["document_metadata"]
        assert meta["filename"] == "lease.docx"
        assert meta["file_type"] == "docx"
        assert meta["word_count"] > 0


class TestAskEndpoint:
    def test_ask_returns_501(self, client):
        response = client.post(
            "/api/v1/contracts/ask",
            json={"context_token": "sometoken", "question": "What is the deposit?"},
        )
        assert response.status_code == 501
