import pytest
from typing import Generator, AsyncGenerator
from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport

import os
os.environ["ENV_STATE"] = "test"

from app.main import app


@pytest.fixture(scope="session")
def ayio_backend():
    return "asyncio"


@pytest.fixture
def client() -> Generator:
    yield TestClient(app)


@pytest.fixture
async def async_client(client) -> AsyncGenerator:
    async with AsyncClient(transport=ASGITransport(app=app), base_url=client.base_url) as ac:
        yield ac
