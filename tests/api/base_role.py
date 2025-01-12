import pytest
import random
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.configs import settings


class BaseRole():
    data = {
        "name": "Banana De Pijamas",
        "authority": 23,
    }

    API_ROLE_ENDPOINT = f"{settings.API_V1_STR}/role/"

    @staticmethod
    async def register_role(async_client: AsyncClient, role_data: dict) -> dict:
        return await async_client.post(BaseRole.API_ROLE_ENDPOINT, json={**role_data})

    @classmethod
    @pytest.fixture
    async def registed_role(cls, async_client: AsyncClient) -> dict:
        response = await cls.register_role(async_client, cls.data)
        return response.json()
