"""
API Contract and OpenAPI schema inspection tests for Rorak AI V2.1.
Verifies route presence, component schemas, and contract compliance.
"""
from fastapi.testclient import TestClient

from backend.main import app


client = TestClient(app)


def test_openapi_generation():
    """Verify OpenAPI document is cleanly generated with expected metadata."""
    schema = app.openapi()
    assert schema is not None
    assert schema["info"]["title"] == "Rorak"
    assert schema["info"]["version"] == app.version



def test_openapi_routes_contract():
    """Verify all required V1 and V2.1 endpoints are present in OpenAPI paths."""
    schema = app.openapi()
    paths = schema["paths"]

    expected_endpoints = {
        "/",
        "/health/",
        "/ready/",
        "/chat/",
        "/documents/upload",
        "/documents/",
        "/documents/{document_id}",
        "/conversations/",
        "/conversations/{conversation_id}",
        "/conversations/{conversation_id}/messages",
    }

    missing_endpoints = expected_endpoints - set(paths.keys())
    assert not missing_endpoints, f"Missing OpenAPI endpoints: {missing_endpoints}"


def test_openapi_component_schemas_contract():
    """Verify all core domain schemas are registered in OpenAPI components."""
    schema = app.openapi()
    components = schema.get("components", {}).get("schemas", {})

    expected_schemas = {
        "APIErrorResponse",
        "ErrorDetail",
        "ChatRequest",
        "ChatResponse",
        "DocumentUploadResponse",
        "HealthResponse",
        "ReadyResponse",
        "DocumentResponse",
        "DocumentListResponse",
        "CreateConversationRequest",
        "ConversationResponse",
        "ConversationListResponse",
        "CreateMessageRequest",
        "MessageResponse",
        "MessageListResponse",
        "Pagination",
        "DocumentStatus",
        "MessageRole",
    }

    missing_schemas = expected_schemas - set(components.keys())
    assert not missing_schemas, f"Missing OpenAPI component schemas: {missing_schemas}"


def test_openapi_ready_response_schema_properties():
    """Verify ReadyResponse contract separates documents_indexed, chunks_indexed, and database_connected."""
    schema = app.openapi()
    ready_schema = schema["components"]["schemas"]["ReadyResponse"]
    properties = ready_schema.get("properties", {})

    assert "database_connected" in properties
    assert "documents_indexed" in properties
    assert "chunks_indexed" in properties
    assert "models_loaded" in properties
    assert "vector_store_initialized" in properties


def test_openapi_error_response_contract_referenced():
    """Verify standard routes register APIErrorResponse in OpenAPI error responses."""
    schema = app.openapi()
    doc_get = schema["paths"]["/documents/{document_id}"]["get"]
    responses = doc_get.get("responses", {})
    assert "404" in responses
    ref = responses["404"]["content"]["application/json"]["schema"]["$ref"]
    assert "APIErrorResponse" in ref


def test_step_9_api_contracts():
    """
    Step 9 — API Contracts:
    Verify presence and contract of all 7 operations:
    1. Create: POST /conversations/
    2. List: GET /conversations/
    3. Get: GET /conversations/{conversation_id}
    4. Rename: PATCH /conversations/{conversation_id}
    5. Delete: DELETE /conversations/{conversation_id}
    6. Messages: GET /conversations/{conversation_id}/messages
    7. Memory: /memories/ (POST, GET) & /memories/{memory_id} (GET, PATCH, DELETE)
    And ChatRequest carrying conversation_id.
    """
    schema = app.openapi()
    paths = schema["paths"]
    components = schema.get("components", {}).get("schemas", {})

    # 1. Create thread: POST /conversations/
    assert "post" in paths["/conversations/"]

    # 2. List threads: GET /conversations/
    assert "get" in paths["/conversations/"]

    # 3. Get thread (reopen): GET /conversations/{conversation_id}
    assert "get" in paths["/conversations/{conversation_id}"]

    # 4. Rename thread (change title, no message mutation): PATCH /conversations/{conversation_id}
    assert "patch" in paths["/conversations/{conversation_id}"]

    # 5. Delete thread (safe message cleanup): DELETE /conversations/{conversation_id}
    assert "delete" in paths["/conversations/{conversation_id}"]

    # 6. Messages (load history in deterministic order): GET /conversations/{conversation_id}/messages
    assert "get" in paths["/conversations/{conversation_id}/messages"]

    # 7. Memory CRUD endpoints: manage durable memory with strict scope isolation
    assert "post" in paths["/memories/"]
    assert "get" in paths["/memories/"]
    assert "get" in paths["/memories/{memory_id}"]
    assert "patch" in paths["/memories/{memory_id}"]
    assert "delete" in paths["/memories/{memory_id}"]

    # 8. Chat contract: carry conversation_id when continuing an existing thread
    chat_request_props = components["ChatRequest"]["properties"]
    assert "conversation_id" in chat_request_props
    assert "workspace_id" in chat_request_props
    assert "user_id" in chat_request_props

    chat_response_props = components["ChatResponse"]["properties"]
    assert "conversation_id" in chat_response_props
