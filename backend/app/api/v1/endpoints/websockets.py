"""
WebSockets & Real-Time Data Streaming Endpoints
===============================================

Endpoints:
  WS   /api/v1/ws/stream       -> Real-time bidirectional data & AI Harness streaming
  POST /api/v1/ws/broadcast    -> Broadcast a real-time event to the active Organization
  GET  /api/v1/ws/stats        -> Active WebSocket connection & channel metrics for the Organization
"""

from __future__ import annotations

import time
from typing import Optional
from fastapi import (
    APIRouter,
    Depends,
    Query,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from loguru import logger

from app.core.database import AsyncSessionLocal
from app.core.security import decode_token, verify_token_type
from app.core.websocket import ws_manager
from app.api.deps import get_current_user, get_current_organization, require_roles
from app.models.user import User, UserRole
from app.models.organization import Organization
from app.repositories.user_repository import UserRepository
from app.repositories.token_blacklist_repository import TokenBlacklistRepository
from app.schemas.websocket import WSBroadcastRequest, WSBroadcastResponse, WSStatsResponse
from app.ai.brain.engine import AIEngine
from app.ai.schemas import AITaskRunRequest


router = APIRouter(prefix="/ws", tags=["WebSockets & Data Streaming"])


async def _authenticate_ws_token(token: Optional[str]) -> Optional[User]:
    """Validate JWT access token for a WebSocket handshake."""
    if not token:
        return None
    if token.lower().startswith("bearer "):
        token = token[7:].strip()

    payload = decode_token(token)
    if not payload or not verify_token_type(payload, "access"):
        return None

    user_id = payload.get("sub")
    if not user_id:
        return None

    async with AsyncSessionLocal() as db:
        jti = payload.get("jti")
        if jti:
            blacklist_repo = TokenBlacklistRepository(db)
            if await blacklist_repo.is_blacklisted(jti):
                return None

        user_repo = UserRepository(db)
        user = await user_repo.get(int(user_id))
        if not user or not user.is_active:
            return None
        return user


@router.websocket("/stream")
async def websocket_data_stream(
    websocket: WebSocket,
    token: Optional[str] = Query(None, description="JWT Access Token"),
    channels: Optional[str] = Query(
        "general,notifications,ai_agent",
        description="Comma-separated channels to subscribe to",
    ),
):
    """
    Real-time bidirectional WebSocket streaming endpoint.

    Authentication:
    - Pass `?token=<JWT_ACCESS_TOKEN>` in the query string or `Authorization: Bearer <token>` header.

    Supported Client Commands (JSON):
    - `{"action": "ping"}` -> Responds with `{"event": "system.pong", ...}`
    - `{"action": "subscribe", "channel": "analytics"}` -> Subscribe to a topic channel
    - `{"action": "unsubscribe", "channel": "analytics"}` -> Unsubscribe from a topic channel
    - `{"action": "broadcast", "channel": "general", "data": {...}}` -> Broadcast data to organization peers
    - `{"action": "ai_run", "task_hint": "...", "input_data": {...}, "dry_run": false}` -> Run Harness Agentic AI task with live step streaming
    """
    auth_token = token or websocket.headers.get("Authorization")
    user = await _authenticate_ws_token(auth_token)

    if not user or not user.organization_id:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Unauthorized")
        return

    channel_list = [ch.strip() for ch in (channels or "").split(",") if ch.strip()]
    client = await ws_manager.connect(
        websocket=websocket,
        user_id=user.id,
        organization_id=user.organization_id,
        role=user.role.value,
        channels=channel_list,
    )

    try:
        while True:
            message = await websocket.receive_json()
            action = str(message.get("action") or "").lower().strip()

            if action == "ping":
                await ws_manager.send_to_connection(
                    client.connection_id,
                    event_type="system.pong",
                    data={"server_time": time.time()},
                    channel="system",
                )

            elif action == "subscribe":
                ch = str(message.get("channel") or "").strip()
                if ch:
                    await ws_manager.subscribe(client.connection_id, ch)

            elif action == "unsubscribe":
                ch = str(message.get("channel") or "").strip()
                if ch:
                    await ws_manager.unsubscribe(client.connection_id, ch)

            elif action == "broadcast":
                ch = str(message.get("channel") or "general").strip()
                payload_data = message.get("data") or {}
                delivered = await ws_manager.broadcast_to_organization(
                    organization_id=client.organization_id,
                    event_type="client.stream.message",
                    channel=ch,
                    data={
                        "sender_user_id": client.user_id,
                        "payload": payload_data,
                    },
                )
                await ws_manager.send_to_connection(
                    client.connection_id,
                    event_type="system.broadcast_ack",
                    data={"delivered_connections": delivered, "channel": ch},
                    channel="system",
                )

            elif action == "ai_run":
                task_hint = str(message.get("task_hint") or "").strip()
                if not task_hint:
                    await ws_manager.send_to_connection(
                        client.connection_id,
                        event_type="ai.task.error",
                        data={"error": "Missing 'task_hint' for ai_run action"},
                        channel="ai_agent",
                    )
                    continue

                async with AsyncSessionLocal() as db:
                    engine = AIEngine(db=db, user=user)
                    run_req = AITaskRunRequest(
                        trigger_type="websocket",
                        task_hint=task_hint,
                        input_data=message.get("input_data") or {},
                        dry_run=bool(message.get("dry_run", False)),
                    )
                    await engine.run(run_req)

            else:
                await ws_manager.send_to_connection(
                    client.connection_id,
                    event_type="system.echo",
                    data={"received": message},
                    channel="general",
                )

    except WebSocketDisconnect:
        await ws_manager.disconnect(client.connection_id)
    except Exception as e:
        logger.warning(f"WebSocket error for conn {client.connection_id}: {e}")
        await ws_manager.disconnect(client.connection_id)


@router.post(
    "/broadcast",
    response_model=WSBroadcastResponse,
    summary="Broadcast a real-time event to connected WebSocket clients in the Organization",
)
async def broadcast_event(
    body: WSBroadcastRequest,
    current_user: User = Depends(
        require_roles([UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN, UserRole.ADMIN, UserRole.MANAGER])
    ),
    current_org: Organization = Depends(get_current_organization),
):
    """Push a real-time JSON event over WebSockets to the active Organization (or a specific user)."""
    if body.target_user_id is not None:
        delivered = await ws_manager.send_to_user(
            user_id=body.target_user_id,
            organization_id=current_org.id,
            event_type=body.event_type,
            channel=body.channel,
            data=body.data,
        )
    else:
        delivered = await ws_manager.broadcast_to_organization(
            organization_id=current_org.id,
            event_type=body.event_type,
            channel=body.channel,
            data=body.data,
        )

    return WSBroadcastResponse(
        delivered_connections=delivered,
        organization_id=current_org.id,
        channel=body.channel,
        event_type=body.event_type,
    )


@router.get(
    "/stats",
    response_model=WSStatsResponse,
    summary="Get active WebSocket streaming statistics for the Organization",
)
async def get_websocket_stats(
    current_user: User = Depends(get_current_user),
    current_org: Organization = Depends(get_current_organization),
):
    """Returns active connection count, connected users, and subscribed topic channels for the Organization."""
    stats = ws_manager.get_stats(organization_id=current_org.id)
    return WSStatsResponse(**stats)
