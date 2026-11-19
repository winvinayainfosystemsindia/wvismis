"""Real-time WebSocket Connection & Streaming Manager with Multi-Tenancy Isolation"""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set
from fastapi import WebSocket
from loguru import logger


@dataclass
class WSClientConnection:
    """Represents an active authenticated WebSocket connection"""
    connection_id: str
    websocket: WebSocket
    user_id: int
    organization_id: int
    role: str
    channels: Set[str] = field(default_factory=lambda: {"general"})
    connected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class WebSocketConnectionManager:
    """
    Production-grade WebSocket manager supporting:
    - Multi-tenant isolation (broadcasting scoped to organization_id)
    - User-specific real-time event streaming (e.g., AI Harness step-by-step progress)
    - Channel/topic subscriptions within an organization
    - Heartbeat ping/pong and dead-connection cleanup
    """

    def __init__(self) -> None:
        # connection_id -> WSClientConnection
        self._connections: Dict[str, WSClientConnection] = {}
        # organization_id -> set of connection_ids
        self._org_connections: Dict[int, Set[str]] = {}
        # user_id -> set of connection_ids
        self._user_connections: Dict[int, Set[str]] = {}
        self._lock = asyncio.Lock()

    async def connect(
        self,
        websocket: WebSocket,
        user_id: int,
        organization_id: int,
        role: str,
        channels: Optional[List[str]] = None,
    ) -> WSClientConnection:
        """Accept and register a new authenticated WebSocket connection."""
        await websocket.accept()
        connection_id = str(uuid.uuid4())
        initial_channels = set(channels) if channels else {"general", "notifications", "ai_agent"}

        client = WSClientConnection(
            connection_id=connection_id,
            websocket=websocket,
            user_id=user_id,
            organization_id=organization_id,
            role=role,
            channels=initial_channels,
        )

        async with self._lock:
            self._connections[connection_id] = client
            self._org_connections.setdefault(organization_id, set()).add(connection_id)
            self._user_connections.setdefault(user_id, set()).add(connection_id)

        logger.info(
            f"WebSocket connected: conn_id={connection_id}, user_id={user_id}, org_id={organization_id}, channels={list(initial_channels)}"
        )

        # Send welcome handshake event
        await self.send_to_connection(
            connection_id,
            event_type="system.connected",
            data={
                "connection_id": connection_id,
                "user_id": user_id,
                "organization_id": organization_id,
                "subscribed_channels": sorted(initial_channels),
                "message": "Connected to WVISMIS real-time data stream",
            },
        )
        return client

    async def disconnect(self, connection_id: str) -> None:
        """Remove a WebSocket connection from all registries."""
        async with self._lock:
            client = self._connections.pop(connection_id, None)
            if not client:
                return

            org_set = self._org_connections.get(client.organization_id)
            if org_set:
                org_set.discard(connection_id)
                if not org_set:
                    self._org_connections.pop(client.organization_id, None)

            user_set = self._user_connections.get(client.user_id)
            if user_set:
                user_set.discard(connection_id)
                if not user_set:
                    self._user_connections.pop(client.user_id, None)

        logger.info(
            f"WebSocket disconnected: conn_id={connection_id}, user_id={client.user_id}, org_id={client.organization_id}"
        )

    async def subscribe(self, connection_id: str, channel: str) -> bool:
        """Subscribe an active connection to a topic channel."""
        client = self._connections.get(connection_id)
        if not client:
            return False
        client.channels.add(channel)
        await self.send_to_connection(
            connection_id,
            event_type="system.subscribed",
            data={"channel": channel, "subscribed_channels": sorted(client.channels)},
        )
        return True

    async def unsubscribe(self, connection_id: str, channel: str) -> bool:
        """Unsubscribe an active connection from a topic channel."""
        client = self._connections.get(connection_id)
        if not client:
            return False
        client.channels.discard(channel)
        await self.send_to_connection(
            connection_id,
            event_type="system.unsubscribed",
            data={"channel": channel, "subscribed_channels": sorted(client.channels)},
        )
        return True

    async def send_to_connection(
        self,
        connection_id: str,
        event_type: str,
        data: Any,
        channel: str = "general",
    ) -> bool:
        """Send a structured JSON event to a single WebSocket connection."""
        client = self._connections.get(connection_id)
        if not client:
            return False

        payload = {
            "event": event_type,
            "channel": channel,
            "organization_id": client.organization_id,
            "timestamp": time.time(),
            "data": data,
        }
        try:
            await client.websocket.send_json(payload)
            return True
        except Exception as e:
            logger.warning(f"Failed sending to WebSocket {connection_id}: {e}")
            await self.disconnect(connection_id)
            return False

    async def send_to_user(
        self,
        user_id: int,
        event_type: str,
        data: Any,
        channel: str = "general",
        organization_id: Optional[int] = None,
    ) -> int:
        """Send a real-time event to all active connections for a specific user."""
        conn_ids = list(self._user_connections.get(user_id, set()))
        sent_count = 0
        for cid in conn_ids:
            client = self._connections.get(cid)
            if not client:
                continue
            if organization_id is not None and client.organization_id != organization_id:
                continue
            if await self.send_to_connection(cid, event_type=event_type, data=data, channel=channel):
                sent_count += 1
        return sent_count

    async def broadcast_to_organization(
        self,
        organization_id: int,
        event_type: str,
        data: Any,
        channel: str = "general",
        exclude_user_id: Optional[int] = None,
    ) -> int:
        """Broadcast a real-time event to all active connections in a tenant organization subscribed to channel."""
        conn_ids = list(self._org_connections.get(organization_id, set()))
        sent_count = 0
        for cid in conn_ids:
            client = self._connections.get(cid)
            if not client:
                continue
            if exclude_user_id is not None and client.user_id == exclude_user_id:
                continue
            if channel != "system" and channel not in client.channels and "all" not in client.channels:
                continue
            if await self.send_to_connection(cid, event_type=event_type, data=data, channel=channel):
                sent_count += 1
        return sent_count

    async def broadcast_system(self, event_type: str, data: Any) -> int:
        """Broadcast a system-wide event across all tenants (Superuser/System alerts)."""
        conn_ids = list(self._connections.keys())
        sent_count = 0
        for cid in conn_ids:
            if await self.send_to_connection(cid, event_type=event_type, data=data, channel="system"):
                sent_count += 1
        return sent_count

    def get_stats(self, organization_id: Optional[int] = None) -> Dict[str, Any]:
        """Get real-time connection metrics, optionally filtered by organization_id."""
        if organization_id is not None:
            org_cids = self._org_connections.get(organization_id, set())
            org_clients = [self._connections[cid] for cid in org_cids if cid in self._connections]
            active_users = sorted({c.user_id for c in org_clients})
            channels: Dict[str, int] = {}
            for c in org_clients:
                for ch in c.channels:
                    channels[ch] = channels.get(ch, 0) + 1
            return {
                "organization_id": organization_id,
                "active_connections": len(org_clients),
                "active_unique_users": len(active_users),
                "active_user_ids": active_users,
                "channels": channels,
            }

        return {
            "total_connections": len(self._connections),
            "total_organizations_connected": len(self._org_connections),
            "total_unique_users_connected": len(self._user_connections),
            "connections_by_org": {
                str(org_id): len(cids) for org_id, cids in self._org_connections.items()
            },
        }


# Singleton WebSocket Connection Manager
ws_manager = WebSocketConnectionManager()
