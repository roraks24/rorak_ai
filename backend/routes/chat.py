import logging

from fastapi import APIRouter, HTTPException

from backend.services.generator import chat_func
from backend.models.schemas import ChatRequest, ChatResponse


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/chat",
    tags=["chat"]
)


@router.post("/", response_model=ChatResponse)
def chat(request: ChatRequest):

    try:
        answer = chat_func(request.question)
        return ChatResponse(answer=answer)

    except RuntimeError as e:
        logger.error("Chat failed: %s", str(e))
        raise HTTPException(
            status_code=503,
            detail=str(e)
        )
    except Exception:
        logger.exception("Unexpected error in chat endpoint.")
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred. Please try again."
        )