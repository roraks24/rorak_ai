"""
Unit and integration tests for Rorak chat endpoint and RAG generation logic.
"""
from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.rag.prompts import prompt_func
from backend.services.generator import chat_func, NO_CONTEXT_FALLBACK_ANSWER
from langchain_core.documents import Document


client = TestClient(app)


def test_root_endpoint():
    """Verify GET / returns service metadata."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Rorak"
    assert data["status"] == "running"


def test_chat_validation_empty_string():
    """Verify empty query fails with 422 Unprocessable Entity."""
    response = client.post("/chat/", json={"question": ""})
    assert response.status_code == 422


def test_chat_validation_oversized_query():
    """Verify query exceeding 10,000 chars fails with 422."""
    huge_question = "A" * 10001
    response = client.post("/chat/", json={"question": huge_question})
    assert response.status_code == 422


def test_prompt_hardening_structure():
    """Verify prompt constructor separates context as UNTRUSTED DATA."""
    query = "What is the secret?"
    context = "Document context content"
    rendered_prompt = prompt_func(query, context)

    assert "UNTRUSTED DATA" in rendered_prompt
    assert "<context>\nDocument context content\n</context>" in rendered_prompt
    assert "<question>\nWhat is the secret?\n</question>" in rendered_prompt
    assert "Do not output raw HTML tags" in rendered_prompt


@patch("backend.services.generator.retriev_func", return_value=[])
@patch("backend.services.generator._call_groq_completion", return_value="Hello! I am **Rorak AI**, your AI assistant. How can I help you today?")
def test_chat_general_query_when_no_documents(mock_groq, mock_retriever):
    """Verify general conversation (e.g. 'hi') succeeds via general assistant mode when no documents are attached."""
    response = client.post("/chat/", json={"question": "hi"})
    assert response.status_code == 200
    assert "Rorak AI" in response.json()["answer"]


@patch("backend.services.generator.retriev_func")
@patch("backend.services.generator.rerank_func")
@patch("backend.services.generator._call_groq_completion")
def test_chat_grounded_successful_generation(mock_groq, mock_rerank, mock_retriever):
    """Verify standard grounded RAG flow with mock retrieval and LLM completion."""
    mock_doc = Document(page_content="The revenue was 5 million dollars.", metadata={"source": "report.pdf", "page": 1})
    mock_retriever.return_value = [mock_doc]
    mock_rerank.return_value = [{"document": mock_doc, "score": 0.95}]
    mock_groq.return_value = "The quarterly revenue was **$5 million**."

    response = client.post("/chat/", json={"question": "What is the quarterly revenue?"})
    assert response.status_code == 200
    data = response.json()
    assert "revenue was **$5 million**" in data["answer"]


@patch("backend.services.generator.retriev_func")
@patch("backend.services.generator.rerank_func")
@patch("backend.services.generator.client.chat.completions.create")
def test_empty_llm_response_retry_success(mock_create, mock_rerank, mock_retriever):
    """Verify single retry on empty LLM response before succeeding."""
    mock_doc = Document(page_content="Some doc text", metadata={"source": "test.pdf", "page": 1})
    mock_retriever.return_value = [mock_doc]
    mock_rerank.return_value = [{"document": mock_doc, "score": 0.9}]

    # First attempt: empty content, Second attempt: valid content
    mock_resp1 = MagicMock()
    mock_resp1.choices = [MagicMock(message=MagicMock(content=""))]

    mock_resp2 = MagicMock()
    mock_resp2.choices = [MagicMock(message=MagicMock(content="Grounded Answer After Retry"))]

    mock_create.side_effect = [mock_resp1, mock_resp2]

    response = client.post("/chat/", json={"question": "Explain the policy."})
    assert response.status_code == 200
    assert response.json()["answer"] == "Grounded Answer After Retry"
    assert mock_create.call_count == 2
