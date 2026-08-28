from typing import Optional
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    question: str = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="The user's question"
    )


class ChatResponse(BaseModel):
    answer: str


class DocumentUploadResponse(BaseModel):
    message: str
    filename: str
    chunks_created: int


class ErrorDetail(BaseModel):
    code: str
    message: str


class APIErrorResponse(BaseModel):
    error: ErrorDetail


class HealthResponse(BaseModel):
    status: str


class ReadyResponse(BaseModel):
    status: str
    models_loaded: bool
    vector_store_initialized: bool
    documents_indexed: int
    details: Optional[dict] = None