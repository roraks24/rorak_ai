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
        "/documents/clear",
        "/documents/db-test",
        "/documents/",
        "/documents/{document_id}",
        "/workspaces/",
        "/workspaces/{workspace_id}",
        "/workspaces/{workspace_id}/members",
        "/workspaces/{workspace_id}/members/{user_id}",
        "/conversations/",
        "/conversations/{conversation_id}",
        "/conversations/{conversation_id}/messages",
    }

    missing_endpoints = expected_endpoints - set(paths.keys())
    assert not missing_endpoints, f"Missing OpenAPI endpoints: {missing_endpoints}"


def test_openapi_component_schemas_contract():
    """Verify all core V2.1 domain schemas are registered in OpenAPI components."""
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
        "CreateWorkspaceRequest",
        "WorkspaceResponse",
        "WorkspaceListResponse",
        "AddMemberRequest",
        "WorkspaceMemberResponse",
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
    workspace_get = schema["paths"]["/workspaces/{workspace_id}"]["get"]
    responses = workspace_get.get("responses", {})
    assert "404" in responses
    ref = responses["404"]["content"]["application/json"]["schema"]["$ref"]
    assert "APIErrorResponse" in ref
