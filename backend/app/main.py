"""WVISMIS FastAPI Application — Main Entry Point"""

import time
import psutil
from contextlib import asynccontextmanager
from fastapi import FastAPI, status, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError, ResponseValidationError
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.openapi.utils import get_openapi
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from loguru import logger

from app.core.config import settings
from app.core.logging import setup_logging
from app.core.database import close_db, get_db
from app.core.rate_limiter import limiter
from app.core.websocket import ws_manager
from app.middleware.logging import LoggingMiddleware
from app.middleware.error_handler import ErrorHandlerMiddleware
from app.middleware.timezone import TimezoneMiddleware
from app.api.v1.router import router as v1_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle events"""
    setup_logging()
    logger.info(
        f"Starting {settings.APP_NAME} v{settings.APP_VERSION} - Environment: {settings.ENVIRONMENT}"
    )

    # Initialize Database Tables, Plans, Parent Org and Superuser on startup
    try:
        from app.core.database import engine, Base, AsyncSessionLocal
        from app.core.bootstrap import init_parent_org_and_superuser

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            await conn.execute(text("""
                DO $$
                BEGIN
                    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='timezone') THEN
                        ALTER TABLE users ADD COLUMN timezone VARCHAR(64);
                    END IF;
                    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='reporting_manager_id') THEN
                        ALTER TABLE users ADD COLUMN reporting_manager_id INTEGER REFERENCES users(id) ON DELETE SET NULL;
                    END IF;
                    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='timesheet_week_unlock_requests' AND column_name='request_type') THEN
                        ALTER TABLE timesheet_week_unlock_requests ADD COLUMN request_type VARCHAR(20) NOT NULL DEFAULT 'unlock';
                    END IF;
                    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='reminders' AND column_name='public_id') THEN
                        ALTER TABLE reminders ADD COLUMN public_id UUID DEFAULT gen_random_uuid();
                    END IF;
                END $$;
            """))

        async with AsyncSessionLocal() as session:
            await init_parent_org_and_superuser(session)
    except Exception as exc:
        err_msg = str(exc)
        if "UndefinedColumnError" in err_msg or "does not exist" in err_msg:
            logger.warning(
                "Database schema has pending migrations (missing columns). "
                "Please run: 'alembic upgrade head' in the backend directory."
            )
        else:
            logger.warning(f"Could not run bootstrap database initialization on startup: {exc}")

    yield
    logger.info("Shutting down application...")
    await close_db()
    logger.info("Application shutdown complete")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "Production-grade WVISMIS Backend with MVC Architecture, Multi-Tenancy (Organizations), "
        "JWT Authentication, PostgreSQL (`wvismis`) + Alembic Migrations, Real-Time WebSockets Data Streaming, "
        "and Harness Agentic AI."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# Rate Limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    logger.error(f"Validation Error for {request.url}: {exc.errors()}")
    return await request_validation_exception_handler(request, exc)


@app.exception_handler(ResponseValidationError)
async def response_validation_exception_handler(request, exc: ResponseValidationError):
    logger.error(f"Response Validation Error for {request.url}: {exc.errors()}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=jsonable_encoder({"error": "Response Validation Error", "detail": str(exc)}),
    )


# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS if settings.BACKEND_CORS_ORIGINS else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "X-Process-Time", "WWW-Authenticate"],
)

# Custom Logging & Error Handling Middleware
app.add_middleware(LoggingMiddleware)
app.add_middleware(ErrorHandlerMiddleware)
app.add_middleware(TimezoneMiddleware)

# API Version 1 Router (/api/v1)
app.include_router(
    v1_router,
    prefix=settings.API_V1_PREFIX,
)


@app.get("/health", tags=["Health"], summary="Comprehensive system and database health check")
async def health_check(db: AsyncSession = Depends(get_db)):
    """
    Production health check endpoint reporting:
    - PostgreSQL (`wvismis`) database connectivity and latency
    - Active WebSocket connections across organizations
    - Harness Agentic AI status
    - Memory utilization and API server response time
    """
    start_time = time.time()
    metrics = []
    overall_status = "healthy"

    try:
        db_start = time.time()
        await db.execute(text("SELECT 1"))
        db_time = (time.time() - db_start) * 1000
        metrics.append({
            "name": "Database (PostgreSQL - wvismis)",
            "status": "operational",
            "responseTimeMs": round(db_time, 2),
        })
    except Exception:
        overall_status = "degraded"
        metrics.append({
            "name": "Database (PostgreSQL - wvismis)",
            "status": "down",
            "responseTimeMs": 0,
        })

    ws_stats = ws_manager.get_stats()
    metrics.append({
        "name": "WebSocket Streaming Engine",
        "status": "operational",
        "activeConnections": ws_stats["total_connections"],
        "activeOrganizations": ws_stats["total_organizations_connected"],
    })

    metrics.append({
        "name": "Harness Agentic AI",
        "status": "operational" if settings.AI_ENABLED else "disabled",
        "provider": settings.AI_PROVIDER,
    })

    memory = psutil.virtual_memory()
    metrics.append({
        "name": "Memory Usage",
        "status": "operational" if memory.percent < 90 else "degraded",
        "percentUsed": round(memory.percent, 2),
    })

    api_time = (time.time() - start_time) * 1000
    metrics.append({
        "name": "API Server",
        "status": "operational",
        "responseTimeMs": round(api_time, 2),
    })

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "status": overall_status,
            "name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "environment": settings.ENVIRONMENT,
            "api_version": settings.API_V1_PREFIX,
            "timestamp": time.time(),
            "metrics": metrics,
        },
    )


@app.get("/", tags=["Root"], summary="API Root Metadata")
async def root():
    """Returns API metadata and links to Swagger UI, ReDoc, OpenAPI JSON, and Health endpoints."""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "api_v1": settings.API_V1_PREFIX,
        "docs": "/docs",
        "redoc": "/redoc",
        "openapi": "/openapi.json",
        "health": "/health",
        "websocket_stream": f"{settings.API_V1_PREFIX}/ws/stream",
    }


def custom_openapi():
    """Customize OpenAPI 3.1 schema with rich documentation, tags, and security schemes"""
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="""
## WVISMIS — WinVinaya Management Information System Backend

Production-grade FastAPI backend engineered with **MVC + Service-Repository Architecture**:

- **Authentication & Security**: JWT Access & Refresh tokens with rotation, `/api/v1/auth/verify`, token revocation blacklist, and RBAC (`super_admin`, `org_admin`, `admin`, `manager`, `user`, etc.).
- **Multi-Tenancy (Organizations)**: Organization-scoped isolation (`organization_id`), tenant slug/domain matching, seat quotas (`max_users`), and tenant switching via `X-Organization-ID` or `X-Organization-Slug` headers.
- **Users Management**: Full multi-tenant user lifecycle, self-service profile updates, role breakdowns, and search.
- **Database & Versioning**: Async PostgreSQL (`wvismis`) with SQLAlchemy 2.0 and **Alembic** migrations.
- **Real-Time WebSockets Streaming**: Bidirectional event streaming at `/api/v1/ws/stream` with tenant-isolated channels and REST broadcast triggers.
- **Harness Agentic AI Engine**: Structured Planner -> ToolRegistry -> Guardrails & Approval Gates -> Synthesizer -> TaskJournal (`ai_task_logs`) with live WebSocket & SSE progress streaming.
        """,
        routes=app.routes,
    )

    openapi_schema.setdefault("components", {})["securitySchemes"] = {
        "HTTPBearer": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "Enter JWT Access Token obtained from `/api/v1/auth/login`",
        }
    }

    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        workers=1 if settings.DEBUG else settings.WORKERS,
        log_level=settings.LOG_LEVEL.lower(),
    )
