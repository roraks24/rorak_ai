import logging
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.models.schemas import APIErrorResponse, ChatRequest, ChatResponse, ErrorDetail
from backend.services.conversation_service import ConversationService
from backend.services.exceptions import ConversationNotFound, ValidationError
from backend.services.generator import chat_func

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/chat",
    tags=["Chat"],
)


@router.post(
    "/",
    response_model=ChatResponse,
    responses={
        400: {"model": APIErrorResponse, "description": "Validation Error"},
        404: {"model": APIErrorResponse, "description": "Conversation Not Found"},
        422: {"model": APIErrorResponse, "description": "Validation Error"},
        500: {"model": APIErrorResponse, "description": "Internal Server Error"},
        503: {"model": APIErrorResponse, "description": "Service Unavailable"},
    },
)
def chat(
    request: ChatRequest,
    db: Session = Depends(get_db),
):
    """
    Document-grounded chat endpoint.
    Accepts user question, retrieves relevant context from documents, and generates answer.

    Step 9 Contract:
    Carries conversation_id when continuing an existing thread.
    Avoids accidentally creating a new conversation for every message.
    """
    try:
        if request.conversation_id:
            # Continuing an existing conversation thread without creating duplicate threads
            service = ConversationService(db)
            _, assistant_msg = service.send_user_message_and_reply(
                conversation_id=request.conversation_id,
                user_content=request.question,
                workspace_id=request.workspace_id,
                user_id=request.user_id,
            )
            return ChatResponse(
                answer=assistant_msg.content,
                conversation_id=request.conversation_id,
            )
        elif request.workspace_id and request.user_id:
            # Explicitly starting a new conversation thread in a workspace
            service = ConversationService(db)
            title = request.question.strip()[:50]
            conv = service.create_conversation(
                workspace_id=request.workspace_id,
                user_id=request.user_id,
                title=title,
            )
            _, assistant_msg = service.send_user_message_and_reply(
                conversation_id=conv.id,
                user_content=request.question,
                workspace_id=request.workspace_id,
                user_id=request.user_id,
            )
            return ChatResponse(
                answer=assistant_msg.content,
                conversation_id=conv.id,
            )
        else:
            # Standalone / stateless chat generation
            answer = chat_func(request.question)
            return ChatResponse(answer=answer, conversation_id=None)

    except ConversationNotFound as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": e.code, "message": str(e)}},
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": e.code, "message": str(e)}},
        )
    except RuntimeError as e:
        error_msg = str(e)
        logger.error("Chat generation failed: %s", error_msg)
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "error": {
                    "code": "LLM_PROVIDER_ERROR",
                    "message": error_msg,
                }
            },
        )
    except Exception:
        logger.exception("Unexpected error occurred in chat endpoint.")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "An unexpected error occurred. Please try again.",
                }
            },
        )