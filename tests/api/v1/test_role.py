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
        response = await async_client.get(f"{self.API_ROLE_ENDPOINT}{id}")
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

        response = await async_client.put(f"{self.API_ROLE_ENDPOINT}{id}", json=updated_data)
        assert response.status_code == 202

        data = response.json()
        assert data["name"] == updated_data["name"]
        assert data["authority"] == updated_data["authority"]
        assert data["id"] == id

        # DELETE
        response = await async_client.delete(f"{self.API_ROLE_ENDPOINT}{id}")
        assert response.status_code == 204

        response = await async_client.get(f"{self.API_ROLE_ENDPOINT}{id}")
        assert response.status_code == 404

    @pytest.mark.anyio
    async def test_register_role_same_auth(self, registered_role, async_client: AsyncClient):
        response = await self.register_role(async_client, self.data)
        assert response.status_code == 409

    @pytest.mark.anyio
    async def test_get_role_wrong_id(self, async_client: AsyncClient):
        response = await async_client.get(f"{self.API_ROLE_ENDPOINT}01234")
        assert response.status_code == 422

        response = await async_client.get(f"{self.API_ROLE_ENDPOINT}00000000-0000-0000-0000-000000000000")
        assert response.status_code == 404

    @pytest.mark.anyio
    async def test_create_role_ivalid_authority(self, async_client: AsyncClient):
        rand_float = random.random()*10
        int_below_range = int(settings.MIN_ROLE-10)
        int_above_range = int(settings.MAX_ROLE+10)

        authorities = [rand_float, int_below_range, int_above_range]
        data = self.data.copy()
        for auth in authorities:
            data["authority"] = auth
            response = await self.register_role(async_client, data)
            assert response.status_code == 422

    @pytest.mark.anyio
    async def test_put_missing_info(self, registered_role, async_client: AsyncClient):
        response = await async_client.put(f"{self.API_ROLE_ENDPOINT}{registered_role['id']}", json={"name": "lalaland"})
        assert response.status_code == 422

        response = await async_client.put(f"{self.API_ROLE_ENDPOINT}{registered_role['id']}", json={"authority": 34})
        assert response.status_code == 422

    @pytest.mark.anyio
    async def test_delete_id_issues(self, async_client: AsyncClient):
        tests = {
            "wrong": {
                "id": "00000000-0000-0000-0000-000000000000",
                "status_code": 404
            },
            "invalid": {
                "id": "12345",
                "status_code": 422
            }
        }

        for key in tests:
            test = tests[key]
            response = await async_client.delete(f"{self.API_ROLE_ENDPOINT}{test['id']}")
            assert response.status_code == test["status_code"]
