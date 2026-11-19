"""AI Engine — Multi-turn Chat & SSE Streaming Endpoints"""

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.core.rate_limiter import limiter
from app.ai.services.chat_service import AIChatService
from app.models.user import User
from app.schemas.ai_chat import (
    AIChatSessionRead,
    AIChatSessionCreate,
    AIChatSessionDetail,
    AIChatMessageCreate,
)

router = APIRouter()


@router.post("/sessions", response_model=AIChatSessionDetail, summary="Create a new AI Harness chat session")
@limiter.limit("10/minute")
async def create_chat_session(
    request: Request,
    *,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
    session_in: AIChatSessionCreate,
) -> Any:
    """Start a new multi-turn conversation with the Harness Agentic AI."""
    service = AIChatService(db, current_user)
    return await service.create_session(session_in)


@router.get("/sessions", response_model=list[AIChatSessionRead], summary="List AI chat sessions")
async def list_chat_sessions(
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Retrieve history of AI conversations for the current user."""
    service = AIChatService(db, current_user)
    return await service.get_sessions()


@router.get("/sessions/{session_id}", response_model=AIChatSessionDetail, summary="Get chat session details")
async def get_chat_session(
    session_id: int,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Get full details and message history of a chat session."""
    service = AIChatService(db, current_user)
    session = await service.get_session_details(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.post("/sessions/{session_id}/messages", summary="Send message and stream SSE response")
@limiter.limit("15/minute")
async def send_chat_message(
    request: Request,
    session_id: int,
    *,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
    message_in: AIChatMessageCreate,
) -> Any:
    """Send a message to the AI Harness and receive a Server-Sent Events (SSE) streaming response."""
    service = AIChatService(db, current_user)
    return StreamingResponse(
        service.stream_message(session_id, message_in),
        media_type="text/event-stream",
    )


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete chat session")
async def delete_chat_session(
    session_id: int,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    """Permanently delete a chat session and its messages."""
    service = AIChatService(db, current_user)
    success = await service.delete_session(session_id)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
