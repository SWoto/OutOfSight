import pytest
from httpx import AsyncClient
from fastapi import BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession


from tests.api.base_users import BaseUser


class TestUsers(BaseUser):

    @pytest.mark.anyio
    async def test_crud(self, logged_in_admin_token, async_client: AsyncClient, session: AsyncSession):
        header_admin = {"Authorization": f"Bearer {logged_in_admin_token}"}

        # Create
        response = await self.register_user(async_client, self.data)
        assert response.status_code == 201

        user_data = response.json()
        id = user_data["id"]
        assert user_data["email"] == self.data["email"]
        assert user_data["nickname"] == self.data["nickname"]
        assert user_data["confirmed"] == self.data["confirmed"]
        assert user_data["role"]["name"] == "Default"

        # Force Confirmation (confirmation method is tested in test_confirm_registered_user)
        await self.confirm_user(self.data["email"], session)

        # Get user token to proceed with the other methods
        response = await self.login_user(async_client, self.data["email"], self.data["password"])
        token = response.json()["access_token"]
        header = {"Authorization": f"Bearer {token}"}

        # Read
        response = await async_client.get(f"{self.API_USER_ENDPOINT}{id}", headers=header)
        assert response.status_code == 200

        user_data = response.json()
        assert user_data["email"] == self.data["email"]
        assert user_data["nickname"] == self.data["nickname"]
        assert user_data["id"] == id

        # Update (PUT)
        updated_data = {
            "email": "updated@laland.pl",
            "nickname": "Updated Nickname",
            "password": "N3wSup3rDup3rPassword#1"
        }

        response = await async_client.put(f"{self.API_USER_ENDPOINT}{id}", json=updated_data, headers=header_admin)
        assert response.status_code == 202

        user_data = response.json()
        assert user_data["email"] == updated_data["email"]
        assert user_data["nickname"] == updated_data["nickname"]
        assert user_data["id"] == id

        # Delete (can delete own, so no need for admin)
        response = await async_client.delete(f"{self.API_USER_ENDPOINT}{id}", headers=header)
        assert response.status_code == 204

        # Admin header to avoid unauthorized method
        response = await async_client.get(f"{self.API_USER_ENDPOINT}{id}", headers=header_admin)
        assert response.status_code == 404

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
    @pytest.mark.parametrize("email", [
        ("bananade@pijamas.com"),
        ("bananadepijamas")
    ])
    async def test_login_user_email_failures(self, email, async_client: AsyncClient):
        response = await self.login_user(async_client, email, self.data["password"])

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
    async def test_get_user_auth(self, registered_user, logged_in_token, logged_in_admin_token, async_client: AsyncClient):
        data = self.data.copy()
        data["email"] = "random@something.com"
        new_user = (await self.register_user(async_client, data)).json()

        header = {"Authorization": f"Bearer {logged_in_token}"}
        header_admin = {"Authorization": f"Bearer {logged_in_admin_token}"}

        # Request for own id
        response = await async_client.get(f"{self.API_USER_ENDPOINT}{registered_user['id']}", headers=header)
        assert response.status_code == 200

        # Request for different id
        response = await async_client.get(f"{self.API_USER_ENDPOINT}{new_user['id']}", headers=header)
        assert response.status_code == 403

        # Request with admin token
        response = await async_client.get(f"{self.API_USER_ENDPOINT}{new_user['id']}", headers=header_admin)
        assert response.status_code == 200
    
    @pytest.mark.anyio
    @pytest.mark.parametrize("id, status_code", [
        ("0", 422),
        ("00000000-0000-0000-0000-000000000000", 404)
    ])
    async def test_get_user_by_id_with_id_issues(self, id, status_code, logged_in_admin_token, async_client: AsyncClient):
        header_admin = {"Authorization": f"Bearer {logged_in_admin_token}"}
        response = await async_client.get(f"{self.API_USER_ENDPOINT}{id}", headers=header_admin)
        assert response.status_code == status_code

    @pytest.mark.anyio
    async def test_get_user_by_token(self, logged_in_token, async_client: AsyncClient):
        headers = {"Authorization": f"Bearer {logged_in_token}"}
        response = await async_client.get(f"{self.API_USER_ENDPOINT}", headers=headers)
        assert response.status_code == 200

        user_data = response.json()
        assert user_data["email"] == self.data["email"]
        assert user_data["nickname"] == self.data["nickname"]

    @pytest.mark.anyio
    async def test_get_user_by_token_invalid_token(self, async_client: AsyncClient):
        headers = {"Authorization": "Some rubbish"}
        response = await async_client.get(f"{self.API_USER_ENDPOINT}", headers=headers)
        assert response.status_code == 401

    @pytest.mark.anyio
    async def test_put_user_invalid_auth(self, registered_user, logged_in_token, logged_in_admin_token, async_client: AsyncClient):
        header = {"Authorization": f"Bearer {logged_in_token}"}
        header_admin = {"Authorization": f"Bearer {logged_in_admin_token}"}

        updated_data = {
            "email": "updated@gmail.com",
            "nickname": "Updated Nickname",
            "password": "N3wSup3rPassword#1"
        }

        response = await async_client.put(f"{self.API_USER_ENDPOINT}{registered_user['id']}", json=updated_data, headers=header)
        assert response.status_code == 403

        response = await async_client.put(f"{self.API_USER_ENDPOINT}{registered_user['id']}", json=updated_data, headers=header_admin)
        assert response.status_code == 202

    @pytest.mark.anyio
    @pytest.mark.parametrize("id, status_code", [
        ("0", 422),
        ("00000000-0000-0000-0000-000000000000", 404)
    ])
    async def test_put_user_id_issues(self, id, status_code, logged_in_admin_token, async_client: AsyncClient):
        headers = {"Authorization": f"Bearer {logged_in_admin_token}"}
        updated_data = {
            "email": "updated@laland.pl",
            "nickname": "Updated Nickname",
            "password": "N3wSup3rDup3rPassword#1"
        }

        response = await async_client.put(f"{self.API_USER_ENDPOINT}{id}", json=updated_data, headers=headers)
        assert response.status_code == status_code

    @pytest.mark.anyio
    async def test_put_user_invalid_email(self, registered_user, logged_in_admin_token, async_client: AsyncClient):
        headers = {"Authorization": f"Bearer {logged_in_admin_token}"}

        updated_data = {
            "email": "updated",
            "nickname": "Updated Nickname",
            "password": "N3wSup3rDup3rPassword#1"
        }

        response = await async_client.put(f"{self.API_USER_ENDPOINT}{registered_user['id']}", json=updated_data, headers=headers)
        assert response.status_code == 422

    @pytest.mark.anyio
    async def test_put_user_invalid_password(self, registered_user, logged_in_admin_token, async_client: AsyncClient):
        headers = {"Authorization": f"Bearer {logged_in_admin_token}"}

        updated_data = {
            "email": "updated@laland.pl",
            "nickname": "Updated Nickname",
            "password": "1234"
        }

        response = await async_client.put(f"{self.API_USER_ENDPOINT}{registered_user['id']}", json=updated_data, headers=headers)
        assert response.status_code == 422

    @pytest.mark.anyio
    async def test_put_user_missing_data(self, registered_user, logged_in_admin_token, async_client: AsyncClient):
        headers = {"Authorization": f"Bearer {logged_in_admin_token}"}

        updated_data = {
            "email": "updated@laland.pl",
            "nickname": "Updated Nickname",
            "password": "N3wSup3rDup3rPassword#1"
        }

        for key in updated_data:
            new_data = updated_data.copy()
            new_data.pop(key)
            response = await async_client.put(f"{self.API_USER_ENDPOINT}{registered_user['id']}", json=new_data, headers=headers)
            assert response.status_code == 422

    @pytest.mark.anyio
    async def test_patch_user_invalid_auth(self, registered_user, logged_in_token, async_client: AsyncClient):
        headers = {"Authorization": f"Bearer {logged_in_token}"}
        patch_data = {"nickname": "Patched Nickname"}

        response = await async_client.patch(f"{self.API_USER_ENDPOINT}{registered_user['id']}", json=patch_data)
        assert response.status_code == 401

        response = await async_client.patch(f"{self.API_USER_ENDPOINT}{registered_user['id']}", json=patch_data, headers=headers)
        assert response.status_code == 403
    
    @pytest.mark.anyio
    async def test_patch_user_nickname(self, registered_user, logged_in_admin_token, async_client: AsyncClient):
        headers = {"Authorization": f"Bearer {logged_in_admin_token}"}

        patch_data = {"nickname": "Patched Nickname"}

        response = await async_client.patch(f"{self.API_USER_ENDPOINT}{registered_user['id']}", json=patch_data, headers=headers)
        assert response.status_code == 202

        user_data = response.json()
        assert user_data["nickname"] == patch_data["nickname"]

    @pytest.mark.anyio
    async def test_patch_user_invalid_nickname(self, registered_user, logged_in_admin_token, async_client: AsyncClient):
        headers = {"Authorization": f"Bearer {logged_in_admin_token}"}
        
        patch_data = {"nickname": ""}

        response = await async_client.patch(f"{self.API_USER_ENDPOINT}{registered_user['id']}", json=patch_data, headers=headers)
        assert response.status_code == 422

    @pytest.mark.anyio
    async def test_patch_user_password(self, registered_user, logged_in_admin_token, async_client: AsyncClient):
        headers = {"Authorization": f"Bearer {logged_in_admin_token}"}
       
        patch_data = {"password": "SecurePass#123"}

        response = await async_client.patch(f"{self.API_USER_ENDPOINT}{registered_user['id']}", json=patch_data, headers=headers)
        assert response.status_code == 202

        user_data = response.json()
        # Verify other data remain unchanged
        assert user_data["email"] == self.data["email"]

    @pytest.mark.anyio
    async def test_patch_user_invalid_password(self, registered_user, logged_in_admin_token, async_client: AsyncClient):
        headers = {"Authorization": f"Bearer {logged_in_admin_token}"}
        
        invalid_passwords = ["short", "12345678", "", None, "abcdefgh"]

        for pwd in invalid_passwords:
            patch_data = {"password": pwd}
            response = await async_client.patch(f"{self.API_USER_ENDPOINT}{registered_user['id']}", json=patch_data, headers=headers)
            assert response.status_code == 422

    @pytest.mark.anyio
    async def test_patch_user_email(self, registered_user, logged_in_admin_token, async_client: AsyncClient):
        headers = {"Authorization": f"Bearer {logged_in_admin_token}"}
        
        patch_data = {"email": "updated@laland.pl"}

        response = await async_client.patch(f"{self.API_USER_ENDPOINT}{registered_user['id']}", json=patch_data, headers=headers)
        assert response.status_code == 202

        user_data = response.json()
        assert user_data["email"] == patch_data["email"]

    @pytest.mark.anyio
    async def test_patch_user_invalid_email(self, registered_user, logged_in_admin_token, async_client: AsyncClient):
        headers = {"Authorization": f"Bearer {logged_in_admin_token}"}
        
        invalid_emails = ["plainaddress",
                          "missingatsign.com", "@missinguser.com", "", None]

        for email in invalid_emails:
            patch_data = {"email": email}
            response = await async_client.patch(f"{self.API_USER_ENDPOINT}{registered_user['id']}", json=patch_data, headers=headers)
            assert response.status_code == 422

    @pytest.mark.anyio
    async def test_delete_user_invalid_auth(self, registered_user, logged_in_token, async_client: AsyncClient):
        # No Auth
        response = await async_client.delete(f"{self.API_USER_ENDPOINT}{registered_user['id']}")
        assert response.status_code == 401

        # Auth not permitted
        data = self.data.copy()
        data["email"] = "random@something.com"
        new_user = (await self.register_user(async_client, data)).json()

        headers = {"Authorization": f"Bearer {logged_in_token}"}
        response = await async_client.delete(f"{self.API_USER_ENDPOINT}{new_user['id']}", headers=headers)
        assert response.status_code == 403

    
    @pytest.mark.anyio
    async def test_delete_user_by_id(self, registered_user, logged_in_admin_token, async_client: AsyncClient):
        headers = {"Authorization": f"Bearer {logged_in_admin_token}"}
        
        response = await async_client.delete(f"{self.API_USER_ENDPOINT}{registered_user['id']}", headers=headers)
        assert response.status_code == 204

        response = await async_client.get(f"{self.API_USER_ENDPOINT}{registered_user['id']}", headers=headers)
        assert response.status_code == 404

    @pytest.mark.anyio
    async def test_delete_user_by_token(self, confirmed_user, logged_in_token, logged_in_admin_token, async_client: AsyncClient):
        headers = {"Authorization": f"Bearer {logged_in_token}"}
        response = await async_client.delete(f"{self.API_USER_ENDPOINT}", headers=headers)
        assert response.status_code == 204

        headers_admin = {"Authorization": f"Bearer {logged_in_admin_token}"}
        response = await async_client.get(f"{self.API_USER_ENDPOINT}{confirmed_user['id']}", headers=headers_admin)
        assert response.status_code == 404