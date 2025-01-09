import pytest
from httpx import AsyncClient
from fastapi import BackgroundTasks

from tests.api.base_users import BaseUser


class TestUsers(BaseUser):

    @pytest.mark.anyio
    async def test_crud(self, async_client: AsyncClient):
        # Create
        response = await self.register_user(async_client, self.data)
        assert response.status_code == 201

        id = response.json()["id"]
        # Read
        response = await async_client.get(f"/api/v1/user/{id}")
        assert response.status_code == 200

        user_data = response.json()
        assert user_data["email"] == self.data["email"]
        assert user_data["nickname"] == self.data["nickname"]
        assert user_data["id"] == str(id)

        # Update (PUT)
        updated_data = {
            "email": "updated@laland.pl",
            "nickname": "Updated Nickname",
            "password": "N3wSup3rDup3rPassword#1"
        }

        response = await async_client.put(f"/api/v1/user/{id}", json=updated_data)
        assert response.status_code == 202

        user_data = response.json()
        assert user_data["email"] == updated_data["email"]
        assert user_data["nickname"] == updated_data["nickname"]

    @pytest.mark.anyio
    async def test_register_user_already_registered(self, registered_user, async_client: AsyncClient):
        response = await self.register_user(async_client, self.data)
        assert response.status_code == 409

    @pytest.mark.anyio
    async def test_register_user_invalid_password(self, async_client: AsyncClient):
        custom_data = self.data.copy()
        passwords = [123566321.17, "1234", "abcdefgh", "12345678",
                     "abcde123", "Abcde123", "!#@$$#¨&#%¨*&@", "''\"\"", "1"*100]

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

    @pytest.mark.anyio
    async def test_get_user_by_id_invalid_id(self, async_client: AsyncClient):
        fake_id = "0"
        response = await async_client.get(f"/api/v1/user/{fake_id}")
        assert response.status_code == 422

    @pytest.mark.anyio
    async def test_get_user_by_id_wrong_id(self, async_client: AsyncClient):
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = await async_client.get(f"/api/v1/user/{fake_id}")
        assert response.status_code == 404

    @pytest.mark.anyio
    async def test_get_user_by_token(self, logged_in_token, async_client: AsyncClient):
        headers = {"Authorization": f"Bearer {logged_in_token}"}
        response = await async_client.get("/api/v1/user/", headers=headers)
        assert response.status_code == 200

        user_data = response.json()
        assert user_data["email"] == self.data["email"]
        assert user_data["nickname"] == self.data["nickname"]

    @pytest.mark.anyio
    async def test_get_user_by_token_invalid_token(self, async_client: AsyncClient):
        headers = {"Authorization": "Some rubish"}
        response = await async_client.get("/api/v1/user/", headers=headers)
        assert response.status_code == 401

    @pytest.mark.anyio
    async def test_put_user_not_found(self, async_client: AsyncClient):
        fake_id = "00000000-0000-0000-0000-000000000000"
        updated_data = {
            "email": "updated@laland.pl",
            "nickname": "Updated Nickname",
            "password": "N3wSup3rDup3rPassword#1"
        }

        response = await async_client.put(f"/api/v1/user/{fake_id}", json=updated_data)
        assert response.status_code == 404

    @pytest.mark.anyio
    async def test_put_user_invalid_id(self, logged_in_token, async_client: AsyncClient):
        headers = {"Authorization": f"Bearer {logged_in_token}"}
        fake_id = "0"
        updated_data = {
            "email": "updated@laland.pl",
            "nickname": "Updated Nickname",
            "password": "N3wSup3rDup3rPassword#1"
        }

        response = await async_client.put(f"/api/v1/user/{fake_id}", json=updated_data, headers=headers)
        assert response.status_code == 422

    @pytest.mark.anyio
    async def test_put_user_invalid_email(self, registered_user, async_client: AsyncClient):
        updated_data = {
            "email": "updated",
            "nickname": "Updated Nickname",
            "password": "N3wSup3rDup3rPassword#1"
        }

        response = await async_client.put(f"/api/v1/user/{registered_user.id}", json=updated_data)
        assert response.status_code == 422

    @pytest.mark.anyio
    async def test_put_user_invalid_password(self, registered_user, async_client: AsyncClient):
        updated_data = {
            "email": "updated@laland.pl",
            "nickname": "Updated Nickname",
            "password": "1234"
        }

        response = await async_client.put(f"/api/v1/user/{registered_user.id}", json=updated_data)
        assert response.status_code == 422

    @pytest.mark.anyio
    async def test_put_user_missing_data(self, registered_user, async_client: AsyncClient):
        updated_data = {
            "email": "updated@laland.pl",
            "nickname": "Updated Nickname",
            "password": "N3wSup3rDup3rPassword#1"
        }

        for key in updated_data:
            new_data = updated_data.copy()
            new_data.pop(key)
            response = await async_client.put(f"/api/v1/user/{registered_user.id}", json=new_data)
            assert response.status_code == 422

    @pytest.mark.anyio
    async def test_patch_user_nickname(self, registered_user, async_client: AsyncClient):
        patch_data = {"nickname": "Patched Nickname"}

        response = await async_client.patch(f"/api/v1/user/{registered_user.id}", json=patch_data)
        assert response.status_code == 202

        user_data = response.json()
        assert user_data["nickname"] == patch_data["nickname"]

    @pytest.mark.anyio
    async def test_patch_user_invalid_nickname(self, registered_user, async_client: AsyncClient):
        patch_data = {"nickname": ""} 

        response = await async_client.patch(f"/api/v1/user/{registered_user.id}", json=patch_data)
        assert response.status_code == 422

    @pytest.mark.anyio
    async def test_patch_user_password(self, registered_user, async_client: AsyncClient):
        patch_data = {"password": "SecurePass#123"}

        response = await async_client.patch(f"/api/v1/user/{registered_user.id}", json=patch_data)
        assert response.status_code == 202

        user_data = response.json()
        # Verify other data remain unchanged
        assert user_data["email"] == self.data["email"]

    @pytest.mark.anyio
    async def test_patch_user_invalid_password(self, registered_user, async_client: AsyncClient):
        invalid_passwords = ["short", "12345678", "", None, "abcdefgh"]

        for pwd in invalid_passwords:
            patch_data = {"password": pwd}
            response = await async_client.patch(f"/api/v1/user/{registered_user.id}", json=patch_data)
            assert response.status_code == 422

    @pytest.mark.anyio
    async def test_patch_user_email(self, registered_user, async_client: AsyncClient):
        patch_data = {"email": "updated@laland.pl"}

        response = await async_client.patch(f"/api/v1/user/{registered_user.id}", json=patch_data)
        assert response.status_code == 202

        user_data = response.json()
        assert user_data["email"] == patch_data["email"]

    @pytest.mark.anyio
    async def test_patch_user_invalid_email(self, registered_user, async_client: AsyncClient):
        invalid_emails = ["plainaddress",
                          "missingatsign.com", "@missinguser.com", "", None]

        for email in invalid_emails:
            patch_data = {"email": email}
            response = await async_client.patch(f"/api/v1/user/{registered_user.id}", json=patch_data)
            assert response.status_code == 422


    @pytest.mark.anyio
    async def test_delete_user_by_id(self, registered_user, async_client: AsyncClient):
        response = await async_client.delete(f"/api/v1/user/{registered_user.id}")
        assert response.status_code == 204

        response = await async_client.get(f"/api/v1/user/{registered_user.id}")
        assert response.status_code == 404


    @pytest.mark.anyio
    async def test_delete_user_by_token(self, confirmed_user, logged_in_token, async_client: AsyncClient):
        headers = {"Authorization": f"Bearer {logged_in_token}"}
        response = await async_client.delete("/api/v1/user/", headers=headers)
        assert response.status_code == 204

        response = await async_client.get(f"/api/v1/user/{confirmed_user.id}")
        assert response.status_code == 404