import logging
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse

from backend.services.generator import chat_func
from backend.models.schemas import ChatRequest, ChatResponse, APIErrorResponse, ErrorDetail


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/chat",
    tags=["Chat"]
)


@router.post(
    "/",
    response_model=ChatResponse,
    responses={
        422: {"model": APIErrorResponse, "description": "Validation Error"},
        500: {"model": APIErrorResponse, "description": "Internal Server Error"},
        503: {"model": APIErrorResponse, "description": "Service Unavailable"},
    }
)
def chat(request: ChatRequest):
    """
    Document-grounded chat endpoint.
    Accepts user question, retrieves relevant context from documents, and generates answer.
    """
    try:
        answer = chat_func(request.question)
        return ChatResponse(answer=answer)

    except RuntimeError as e:
        error_msg = str(e)
        logger.error("Chat generation failed: %s", error_msg)
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "error": {
                    "code": "LLM_PROVIDER_ERROR",
                    "message": error_msg
                }
            }
        )

    except Exception:
        logger.exception("Unexpected error occurred in chat endpoint.")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "An unexpected error occurred. Please try again."
                }
            }
        )