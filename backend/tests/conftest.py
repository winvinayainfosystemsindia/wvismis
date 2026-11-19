import os
import sys
from pathlib import Path

# Ensure backend directory is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Set test environment variables before importing app modules
os.environ.setdefault("POSTGRES_SERVER", "localhost")
os.environ.setdefault("POSTGRES_USER", "postgres")
os.environ.setdefault("POSTGRES_PASSWORD", "postgres")
os.environ.setdefault("POSTGRES_DB", "wvismis")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-wvismis-suite-32chars")
os.environ.setdefault("ENVIRONMENT", "testing")

import pytest
from typing import AsyncGenerator
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from app.main import app
from app.core.database import get_db, Base


TEST_DATABASE_URL = "sqlite+aiosqlite:///./test_wvismis.db"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
)

TestSessionLocal = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestSessionLocal() as session:
        yield session

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(app=app, base_url="http://test") as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
def test_user_data():
    return {
        "email": "admin@winvinaya.com",
        "username": "wvadmin",
        "password": "TestPass123",
        "full_name": "WinVinaya Admin",
        "organization_name": "WinVinaya Infosystems",
        "organization_slug": "winvinaya",
    }
