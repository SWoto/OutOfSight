import pytest
from httpx import AsyncClient
from fastapi import BackgroundTasks

from tests.api.base_users import BaseUser


class TestUsers(BaseUser):

    @pytest.mark.anyio
    async def test_register_user(self, async_client: AsyncClient):
        response = await self.register_user(async_client, self.data)
        assert response.status_code == 201

        base_data = self.data.copy()

        base_data["id"] = response.json()["id"]
        base_data.pop("password")

        assert response.json().items() == base_data.items()

    
    @pytest.mark.anyio
    async def test_register_user_already_registered(self, registered_user, async_client: AsyncClient):
        response = await self.register_user(async_client, self.data)
        assert response.status_code == 409


    @pytest.mark.anyio
    async def test_register_user_invalid_password(self, async_client: AsyncClient):
        custom_data = self.data.copy()
        passwords = [123566321.17, "1234", "abcdefgh", "12345678", "abcde123", "Abcde123", "!#@$$#¨&#%¨*&@", "''\"\"", "1"*100]
        
        for pwd in passwords:
            custom_data["password"] = pwd
            response = await self.register_user(async_client, custom_data)
            assert response.status_code == 422


    @pytest.mark.anyio
    async def test_confirm_registered_user(self, async_client: AsyncClient, mocker):
        spy = mocker.spy(BackgroundTasks, "add_task")
        _ = await self.register_user(async_client, self.data)

        confirmation_url = str(spy.call_args[1]["confirmation_url"])
        response = await async_client.get(confirmation_url)
        
        assert response.status_code == 202

    
    @pytest.mark.anyio
    async def test_login_user(self, confirmed_user, async_client: AsyncClient):
        response = await self.login_user(async_client, self.data["email"], self.data["password"])
        
        assert response.status_code == 200


    @pytest.mark.anyio
    async def test_login_user_unregistered_email(self, confirmed_user, async_client: AsyncClient):
        response = await self.login_user(async_client, "bananade@pijamas.com", self.data["password"])
        
        assert response.status_code == 401


    @pytest.mark.anyio
    async def test_login_user_ivalid_email(self, confirmed_user, async_client: AsyncClient):
        response = await self.login_user(async_client, "bananadepijamas", self.data["password"])
        
        assert response.status_code == 401

    @pytest.mark.anyio
    async def test_login_wrong_password(self, confirmed_user, async_client: AsyncClient):
        response = await self.login_user(async_client, self.data["email"], "password")
        
        assert response.status_code == 401

    @pytest.mark.anyio
    async def test_login_user_not_confirmed(self, registered_user, async_client: AsyncClient):
        response = await self.login_user(async_client, self.data["email"], "password")
        
        assert response.status_code == 401