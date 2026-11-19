"""API v1 main router — aggregates Authentication, Organizations, Users, Activity Logs, WebSockets, and AI Harness"""

from fastapi import APIRouter
from app.api.v1.endpoints import (
    auth,
    organizations,
    users,
    plans,
    activity_logs,
    websockets,
    ai,
    ai_settings,
    ai_chat,
    frontend_compat,
)

router = APIRouter()

# Core Authentication, Multi-Tenancy, Users & Plans
router.include_router(auth.router)
router.include_router(organizations.router)
router.include_router(users.router)
router.include_router(plans.router)
router.include_router(activity_logs.router)
router.include_router(frontend_compat.router)

# Real-Time WebSockets & Data Streaming
router.include_router(websockets.router)

# AI Credits, Usage & Agentic Harness
router.include_router(ai.router)
router.include_router(ai_settings.router, prefix="/ai/settings", tags=["Harness AI Settings"])
router.include_router(ai_chat.router, prefix="/ai/chat", tags=["Harness AI Chat"])
