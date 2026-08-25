from fastapi import APIRouter
from backend.services.generator import chat_func
from backend.models.schemas import ChatRequest, ChatResponse

router = APIRouter(
    prefix="/chat",
    tags=["chat"]

)

@router.post("/", response_model= ChatResponse)
def chat(request: ChatRequest):

    answer = chat_func(request.question)

    return ChatResponse(answer=answer)