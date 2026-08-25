from pydantic import BaseModel, Field, ConfigDict


class ChatRequest(BaseModel):
    question: str


class ChatResponse(BaseModel):
    answer: str


class DocumentUploadResponse(BaseModel):
    message: str
    filename: str
    chunks_created: int = Field(
        validation_alias="Chunks Created",
        serialization_alias="Chunks Created"
    )

    model_config = ConfigDict(
        populate_by_name=True
    )