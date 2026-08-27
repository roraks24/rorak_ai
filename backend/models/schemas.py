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