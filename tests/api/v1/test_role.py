import pytest
from httpx import AsyncClient
import random

from tests.api.base_role import BaseRole
from app.core.configs import settings


class TestRoles(BaseRole):

    @pytest.mark.anyio
    async def test_crud(self, async_client: AsyncClient):
        # CREATE
        response = await self.register_role(async_client, self.data)
        assert response.status_code == 201

        data = response.json()
        id = data["id"]
        assert data["name"] == self.data["name"]
        assert data["authority"] == self.data["authority"]

        # READ
        response = await async_client.get(f"/api/v1/role/{id}")
        assert response.status_code == 200

        data = response.json()
        assert data["name"] == self.data["name"]
        assert data["authority"] == self.data["authority"]
        assert data["id"] == id

        # PUT
        updated_data = {
            "name": "Lolinha",
            "authority": 13,
        }

        response = await async_client.put(f"/api/v1/role/{id}", json=updated_data)
        assert response.status_code == 202

        data = response.json()
        assert data["name"] == updated_data["name"]
        assert data["authority"] == updated_data["authority"]
        assert data["id"] == id

        # DELETE
        response = await async_client.delete(f"/api/v1/role/{id}")
        assert response.status_code == 204

        response = await async_client.get(f"/api/v1/role/{id}")
        assert response.status_code == 404

    @pytest.mark.anyio
    async def test_register_role_same_auth(self, registed_role, async_client: AsyncClient):
        response = await self.register_role(async_client, self.data)
        assert response.status_code == 409

    @pytest.mark.anyio
    async def test_get_role_wrong_id(self, async_client: AsyncClient):
        response = await async_client.get("/api/v1/role/01234")
        assert response.status_code == 422

        response = await async_client.get("/api/v1/role/00000000-0000-0000-0000-000000000000")
        assert response.status_code == 404

    @pytest.mark.anyio
    async def test_create_role_wrong_authority(self, async_client: AsyncClient):
        rand_float = random.random()*10
        int_below_range = int(settings.MIN_ROLE-10)
        int_above_range = int(settings.MAX_ROLE+10)

        authorities = [rand_float, int_below_range, int_above_range]
        data = self.data.copy()
        for auth in authorities:
            data["authority"] = auth
            response = await self.register_role(async_client, data)
            assert response.status_code == 422
