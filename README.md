# WVISMIS — WinVinaya Management Information System

Enterprise multi-tenant Management Information System built with a production-grade **FastAPI MVC Backend**, **PostgreSQL (`wvismis`)**, **Alembic Migrations**, **Real-Time WebSockets Streaming**, and **Harness Agentic AI**.

## 📂 Repository Structure

- **[backend/](backend/README.md)**: FastAPI MVC application, PostgreSQL + Alembic migrations, Multi-Tenancy (Organizations), JWT Authentication, WebSockets data streaming, and Harness Agentic AI Engine.

## 🚀 Quick Start (Backend)

```bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

# Copy environment configuration (dev or prod)
copy .env.dev.example .env

# Run database migrations against PostgreSQL (db: wvismis)
alembic upgrade head

# Start development server
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

See **[backend/README.md](backend/README.md)** for full architecture details, environment configuration (`.env.dev` / `.env.prod`), WebSocket streaming protocol, and OpenAPI documentation links.
