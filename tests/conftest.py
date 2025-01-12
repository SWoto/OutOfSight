import pytest
from typing import Generator, AsyncGenerator
from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text

import os
os.environ["ENV_STATE"] = "test"

from app.models.users import UsersModel
from app.core.database import engine, create_database, create_tables, drop_tables, Session, initialize_default_values
from app.main import app
from app.core.configs import settings


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture
def client() -> Generator:
    yield TestClient(app)


@pytest.fixture
async def async_client(client) -> AsyncGenerator:
    async with AsyncClient(transport=ASGITransport(app=app), base_url=client.base_url) as ac:
        yield ac

@pytest.fixture
async def session() -> AsyncGenerator:
    async with Session() as session:
        yield session

@pytest.fixture(scope="session", autouse=True)
async def initiate_db() -> AsyncGenerator:
    await create_database(settings.DATABASE_URL, settings.POSTGRES_DB)
    await create_tables()
    await initialize_default_values()
    yield 
    await drop_tables()


@pytest.fixture(autouse=True)
async def clear_db() -> AsyncGenerator:
    yield 
    async with Session() as session:
        await session.execute(text("DELETE FROM users"))  # Replace with UsersModel if ORM is preferred
        await session.commit()