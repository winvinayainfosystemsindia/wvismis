# WVISMIS Backend — Production-Grade FastAPI MVC & Harness Agentic AI

Production-ready backend for **WVISMIS (WinVinaya Management Information System)** engineered with **FastAPI**, **PostgreSQL (`wvismis`)**, **Alembic**, **Multi-Tenancy (Organizations)**, **JWT Authentication**, **Real-Time WebSockets Data Streaming**, and the **Harness Agentic AI Engine**.

---

## 🏗️ Architecture Overview (MVC + Service-Repository + AI Harness)

```
backend/
├── app/
│   ├── api/                        # Controllers / View Endpoints (Versioned)
│   │   ├── deps.py                 # JWT auth, RBAC, Multi-Tenant resolution dependencies
│   │   └── v1/                     # API Version 1 (/api/v1)
│   │       ├── endpoints/
│   │       │   ├── auth.py         # Register, Login, Verify, Refresh, Logout, Password
│   │       │   ├── organizations.py# Multi-tenancy CRUD, quotas, stats
│   │       │   ├── users.py        # Tenant-scoped User CRUD, roles, search, stats
│   │       │   ├── activity_logs.py# Multi-tenant audit trail endpoints
│   │       │   ├── websockets.py   # Bidirectional WebSocket streaming & broadcast
│   │       │   ├── ai.py           # Harness Agentic AI task runner, tools, approval
│   │       │   ├── ai_settings.py  # Runtime LLM provider & API key management
│   │       │   └── ai_chat.py      # Multi-turn AI chat with SSE streaming
│   │       └── router.py           # Aggregated /api/v1 router
│   ├── ai/                         # Harness Agentic AI Engine
│   │   ├── brain/
│   │   │   ├── engine.py           # Harness orchestrator (Plan -> Guardrails -> Execute -> Journal)
│   │   │   ├── planner.py          # Jinja2 prompt builder + JSON plan parser
│   │   │   ├── synthesizer.py      # Human-readable response synthesizer
│   │   │   ├── journal.py          # Immutable DB execution journal (ai_task_logs)
│   │   │   ├── memory.py           # Few-shot experience retrieval
│   │   │   ├── schemas.py          # ToolDefinition, ToolCallPlan, ToolResult
│   │   │   └── exceptions.py       # Structured AI exception hierarchy
│   │   ├── mcp/
│   │   │   ├── base_tool.py        # BaseTool interface with schema validation
│   │   │   ├── registry.py         # Central MCP-compatible ToolRegistry
│   │   │   └── tools/              # Built-in Multi-Tenant & Streaming AI Tools
│   │   ├── prompts/                # Jinja2 system prompts (aria_planner.md)
│   │   ├── providers/              # Multi-LLM adapters (Gemini, OpenAI, Anthropic, Groq, Mistral)
│   │   ├── schemas/                # API request/response contracts
│   │   └── services/               # Multi-turn chat service
│   ├── core/                       # Core Infrastructure
│   │   ├── config.py               # Multi-env Pydantic Settings (.env, .env.dev, .env.prod)
│   │   ├── database.py             # Async SQLAlchemy 2.0 engine & session factory
│   │   ├── security.py             # Bcrypt hashing, JWT access/refresh tokens with JTI
│   │   ├── websocket.py            # Multi-tenant WebSocket Connection & Channel Manager
│   │   ├── rate_limiter.py         # SlowAPI rate limiting
│   │   └── logging.py              # Structured Loguru JSON/console logging
│   ├── models/                     # SQLAlchemy 2.0 ORM Models (PostgreSQL: wvismis)
│   │   ├── base.py                 # BaseModel, TimestampMixin, SoftDeleteMixin, TenantMixin
│   │   ├── organization.py         # Organization (Tenant) model
│   │   ├── user.py                 # User model with UserRole & organization_id
│   │   ├── token_blacklist.py      # Revoked JWT JTI store
│   │   ├── activity_log.py         # Multi-tenant audit trail
│   │   ├── system_setting.py       # Runtime settings store
│   │   ├── ai_task_log.py          # Harness AI task execution journal
│   │   └── ai_chat.py              # AI Chat sessions & messages
│   ├── repositories/               # Data Access Layer (Generic & Tenant-Scoped CRUD)
│   ├── schemas/                    # Pydantic v2 Validation Schemas
│   ├── services/                   # Business Logic Layer
│   ├── middleware/                 # Request ID Logging & Global Error Handling Middleware
│   ├── utils/                      # Audit Activity Tracker utilities
│   └── main.py                     # FastAPI Entrypoint & Custom OpenAPI 3.1 Schema
├── alembic/                        # Database Version Control & Migrations
│   ├── env.py                      # Async Alembic runner connected to app.models
│   └── versions/                   # Initial WVISMIS schema migration
├── tests/                          # Async Pytest Test Suite
├── .env.example                    # Base environment template
├── .env.dev.example                # Development environment template (.env.dev)
├── .env.prod.example               # Production environment template (.env.prod)
├── .gitignore
├── alembic.ini
└── requirements.txt
```

---

## 🌍 Multi-Environment Setup (`dev` & `prod`)

The backend supports environment-specific `.env` files via `ENV_FILE` or `APP_ENV`:

1. **Development (`dev`)**:
   ```bash
   cp .env.dev.example .env.dev
   # Or copy to .env for default local runs
   cp .env.dev.example .env
   ```
   Run with development config:
   ```bash
   ENV_FILE=.env.dev uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
   ```

2. **Production (`prod`)**:
   ```bash
   cp .env.prod.example .env.prod
   ```
   Run with production config:
   ```bash
   ENV_FILE=.env.prod uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
   ```

---

## 🗄️ PostgreSQL Database (`wvismis`) & Alembic Migrations

1. **Create the PostgreSQL database**:
   ```sql
   CREATE DATABASE wvismis;
   ```

2. **Run Alembic Migrations**:
   ```bash
   # Upgrade to latest schema version
   alembic upgrade head

   # Generate a new migration after modifying models
   alembic revision --autogenerate -m "description_of_changes"

   # Rollback one revision
   alembic downgrade -1
   ```

---

## 🔐 Key Functional Modules

### 1. JWT Authentication (`/api/v1/auth`)
- `POST /api/v1/auth/register` — Register a user (join existing organization by `organization_id`/`organization_slug`, or create a new tenant organization via `organization_name`).
- `POST /api/v1/auth/login` — Authenticate and receive JWT `access_token` + `refresh_token`.
- `POST /api/v1/auth/verify` — Verify any `access` or `refresh` token's validity, claims, and blacklist status.
- `POST /api/v1/auth/refresh` — Rotate refresh token (blacklists used refresh token JTI) and issue new token pair.
- `POST /api/v1/auth/logout` — Revoke current access and refresh tokens via `token_blacklist`.
- `POST /api/v1/auth/change-password` — Change authenticated user's password.
- `GET /api/v1/auth/me` — Retrieve authenticated user profile and active Organization summary.

### 2. Multi-Tenancy / Organizations (`/api/v1/organizations`)
- **Strict Association**: Every user in WVISMIS **must be associated with an organization** (`organization_id` is non-nullable). Self-registered users or new accounts without an explicitly specified organization automatically default to the root parent organization.
- **Root Parent Organization**: **WinVinaya Infosystems** (`slug: winvinaya`, `is_parent=True`) serves as the default parent organization across all environments.
- **Root Super Administrator**:
  - **Email**: `dharanidaran.a@winvinaya.com`
  - **Password**: `Testpass@123`
  - Automatically bootstrapped on startup under WinVinaya Infosystems.
- Every tenant-scoped model inherits `TenantMixin` (`organization_id`).
- `GET /api/v1/organizations/parent` — Retrieve the root parent organization (WinVinaya Infosystems).
- `GET /api/v1/organizations/current` — Inspect active tenant profile, hierarchy (`parent_id`, `is_parent`), and settings.
- `PUT /api/v1/organizations/current` — Update tenant branding, contact info, and settings.
- `GET /api/v1/organizations/current/stats` — View seat quota (`max_users`), active users, and role distribution.
- `POST /api/v1/organizations/` & `GET /api/v1/organizations/` — Superuser tenant provisioning and hierarchical sub-organization creation (`parent_id`).
- Superusers can switch tenant context on any endpoint using `X-Organization-ID` or `X-Organization-Slug` headers.

### 3. Users Management (`/api/v1/users`)
- Strict multi-tenant isolation: users and admins only see/manage users within their own organization.
- `GET /api/v1/users/me` & `PUT /api/v1/users/me` — Self-service profile inspection and updates.
- `GET /api/v1/users/roles` & `GET /api/v1/users/stats` — Available RBAC roles and tenant user statistics.
- `GET /api/v1/users/`, `POST /api/v1/users/`, `GET /api/v1/users/search`, `GET /api/v1/users/{id}`, `PUT /api/v1/users/{id}`, `DELETE /api/v1/users/{id}`.

### 4. Real-Time WebSockets Data Streaming (`/api/v1/ws`)
- **WebSocket Endpoint**: `ws://localhost:8000/api/v1/ws/stream?token=<JWT_ACCESS_TOKEN>&channels=general,notifications,ai_agent`
- Supports JSON actions: `ping`, `subscribe`, `unsubscribe`, `broadcast`, and `ai_run`.
- **REST Broadcast Trigger**: `POST /api/v1/ws/broadcast` — Push live JSON events to an organization channel or specific user.
- **Connection Metrics**: `GET /api/v1/ws/stats` — Inspect active WebSocket connections and channels for the organization.

### 5. Harness Agentic AI Engine (`/api/v1/ai`)
- **Task Orchestrator**: `POST /api/v1/ai/run` — Plans tool calls, enforces safety guardrails (`AI_MAX_TOOL_CALLS_PER_RUN`, `AI_TASK_TIMEOUT_SECONDS`, `AI_APPROVAL_RECORD_THRESHOLD`), streams live step events over WebSockets (`ai.task.started`, `ai.task.planning`, `ai.task.step_started`, `ai.task.step_completed`, `ai.task.completed`), and writes an immutable `AITaskLog`.
- **Human-in-the-Loop Approval Gate**: Tools marked `requires_approval=True` (such as `deactivate_organization_user`) pause the Harness in `awaiting_approval` state until approved via `POST /api/v1/ai/tasks/{task_id}/approve`.
- **Direct Tool Execution**: `POST /api/v1/ai/tools/{tool_name}/execute` & `GET /api/v1/ai/tools`.
- **Multi-Turn SSE Chat**: `/api/v1/ai/chat/sessions` & `/api/v1/ai/chat/sessions/{id}/messages`.
- **Runtime Provider Configuration**: `/api/v1/ai/settings` & `/api/v1/ai/settings/test-connection`.

---

## 📚 OpenAPI Documentation

When the server is running, interactive API documentation is available at:
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`
- **OpenAPI 3.1 JSON Spec**: `http://localhost:8000/openapi.json`
- **System Health Check**: `http://localhost:8000/health`
