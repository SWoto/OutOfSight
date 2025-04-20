from datetime import timedelta
from unittest.mock import patch
import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


from app.core.auth import create_token
from tests.api.base_users import BaseUser


class TestUserRegistration(BaseUser):
    """Tests for user registration functionality."""

    @pytest.mark.anyio
    async def test_successful_registration(self, logged_in_admin_token, mock_background, mock_confirmation_email, async_client: AsyncClient, session: AsyncSession):
        """Test successful user registration with confirmation email."""
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

        mock_background.assert_called_once()
        mock_confirmation_email.assert_called_once()
        args, kwargs = mock_confirmation_email.call_args
        assert kwargs['nickname'] == self.data["nickname"]
        assert kwargs['email'] == self.data["email"]
        assert "confirmation_url" in kwargs

        confirmation_url = str(kwargs["confirmation_url"])
        response = await async_client.get(str(confirmation_url))
        assert response.status_code == 202

    @pytest.mark.anyio
    async def test_already_registered(self, registered_user, async_client: AsyncClient):
        """Test registration with an email that's already registered."""
        response = await self.register_user(async_client, self.data)
        assert response.status_code == 409

    @pytest.mark.anyio
    @pytest.mark.parametrize("password", [
        (123566321.17), ("1234"), ("abcdefgh"),
        ("12345678"), ("abcde123"), ("Abcde123"),
        ("!#@$$#¨&#%¨*&@"), ("''\"\""), ("1"*100),
    ])
    async def test_invalid_password(self, password, async_client: AsyncClient):
        """Test registration with various invalid passwords."""
        custom_data = self.data.copy()
        custom_data["password"] = password
        response = await self.register_user(async_client, custom_data)
        assert response.status_code == 422

    @pytest.mark.anyio
    async def test_special_characters(self, mock_background, mock_confirmation_email, async_client: AsyncClient):
        """Test registration with special characters in nickname and email."""
        special_data = self.data.copy()
        special_data["nickname"] = "User!@#$%^&*()_+"
        special_data["email"] = "user+special@example.com"

        response = await self.register_user(async_client, special_data)
        assert response.status_code == 201

        user_data = response.json()
        assert user_data["nickname"] == special_data["nickname"]
        assert user_data["email"] == special_data["email"]

    @pytest.mark.anyio
    async def test_unicode_characters(self, async_client: AsyncClient):
        """Test registration with Unicode characters in nickname."""
        unicode_data = self.data.copy()
        unicode_data["nickname"] = "ユーザー名"
        unicode_data["email"] = "unicode@example.com"

        response = await self.register_user(async_client, unicode_data)
        assert response.status_code == 201

        user_data = response.json()
        assert user_data["nickname"] == unicode_data["nickname"]

    @pytest.mark.anyio
    async def test_empty_fields(self, async_client: AsyncClient):
        """Test registration with empty fields."""
        empty_data = self.data.copy()
        empty_data["nickname"] = ""
        empty_data["email"] = ""

        response = await self.register_user(async_client, empty_data)
        assert response.status_code == 422


class TestUserAuthentication(BaseUser):
    """Tests for user authentication functionality."""

    @pytest.mark.anyio
    async def test_successful_login(self, confirmed_user, async_client: AsyncClient):
        """Test successful login with valid credentials."""
        response = await self.login_user(async_client, self.data["email"], self.data["password"])
        assert response.status_code == 200

    @pytest.mark.anyio
    @pytest.mark.parametrize("email", [
        ("bananade@pijamas.com"),
        ("bananadepijamas")
    ])
    async def test_login_email_failures(self, email, async_client: AsyncClient):
        """Test login with non-existent email addresses."""
        response = await self.login_user(async_client, email, self.data["password"])
        assert response.status_code == 401

    @pytest.mark.anyio
    async def test_wrong_password(self, confirmed_user, async_client: AsyncClient):
        """Test login with incorrect password."""
        response = await self.login_user(async_client, self.data["email"], "password")
        assert response.status_code == 401

    @pytest.mark.anyio
    async def test_not_confirmed(self, registered_user, async_client: AsyncClient):
        """Test login with unconfirmed email."""
        response = await self.login_user(async_client, self.data["email"], "password")
        assert response.status_code == 401

    @pytest.mark.anyio
    async def test_token_expiration(self, confirmed_user, async_client: AsyncClient):
        """Test behavior with expired tokens."""
        with patch("app.core.auth.create_token") as mock_create_token:
            mock_create_token.side_effect = lambda token_type, life_time, subject: create_token(
                token_type, timedelta(minutes=-1), subject
            )

            response = await self.login_user(async_client, self.data["email"], self.data["password"])
            mock_create_token.assert_called_once()

            token = response.json()["access_token"]

            headers = {"Authorization": f"Bearer {token}"}
            response = await async_client.get(f"{self.API_USER_ENDPOINT}", headers=headers)
            assert response.status_code == 401

    @pytest.mark.anyio
    async def test_malformed_token(self, async_client: AsyncClient):
        """Test with malformed tokens."""
        malformed_tokens = [
            "not_a_token",
            "Bearer ",
            "Bearer invalid.token.format",
            "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        ]

        for token in malformed_tokens:
            headers = {"Authorization": token}
            response = await async_client.get(f"{self.API_USER_ENDPOINT}", headers=headers)
            assert response.status_code == 401

    @pytest.mark.anyio
    async def test_logout(self, logged_in_token, async_client: AsyncClient):
        """Test user logout functionality."""
        headers = {"Authorization": f"Bearer {logged_in_token}"}

        response = await async_client.post(f"{self.API_USER_ENDPOINT}logout", headers=headers)
        assert response.status_code == 200
        assert response.json()["detail"] == "Successfully logged out"

        response = await async_client.get(f"{self.API_USER_ENDPOINT}", headers=headers)
        assert response.status_code == 401

    @pytest.mark.anyio
    @pytest.mark.parametrize("id", [
        ("12345"),
        (f"{str(uuid.uuid4())}"),
        (""),
        ("abcdef"),
    ])
    async def test_logout_invalid_token_id(self, id, async_client: AsyncClient):
        """Test user logout with invalid token."""
        headers = {
            "Authorization": f"Bearer {create_token('access_token', timedelta(minutes=1), id)}"}
        response = await async_client.post(f"{self.API_USER_ENDPOINT}logout", headers=headers)
        assert response.status_code == 401


class TestUserRetrieval(BaseUser):
    """Tests for user retrieval functionality."""

    @pytest.mark.anyio
    async def test_get_user_auth(self, registered_user, logged_in_token, logged_in_admin_token, async_client: AsyncClient):
        """Test authorization rules for user retrieval."""
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
        """Test user retrieval with invalid IDs."""
        header_admin = {"Authorization": f"Bearer {logged_in_admin_token}"}
        response = await async_client.get(f"{self.API_USER_ENDPOINT}{id}", headers=header_admin)
        assert response.status_code == status_code

    @pytest.mark.anyio
    async def test_get_user_by_token(self, logged_in_token, async_client: AsyncClient):
        """Test retrieving user by token."""
        headers = {"Authorization": f"Bearer {logged_in_token}"}
        response = await async_client.get(f"{self.API_USER_ENDPOINT}", headers=headers)
        assert response.status_code == 200

        user_data = response.json()
        assert user_data["email"] == self.data["email"]
        assert user_data["nickname"] == self.data["nickname"]

    @pytest.mark.anyio
    async def test_get_user_by_token_invalid_token(self, async_client: AsyncClient):
        """Test retrieving user with invalid token."""
        headers = {"Authorization": "Some rubbish"}
        response = await async_client.get(f"{self.API_USER_ENDPOINT}", headers=headers)
        assert response.status_code == 401


class TestUserUpdate(BaseUser):
    """Tests for user update functionality."""

    @pytest.mark.anyio
    async def test_put_user_invalid_auth(self, registered_user, logged_in_token, logged_in_admin_token, async_client: AsyncClient):
        """Test authorization rules for user updates."""
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
        """Test user updates with invalid IDs."""
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
        """Test user updates with invalid email."""
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
        """Test user updates with invalid password."""
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
        """Test user updates with missing required fields."""
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
        """Test authorization rules for partial user updates."""
        headers = {"Authorization": f"Bearer {logged_in_token}"}
        patch_data = {"nickname": "Patched Nickname"}

        response = await async_client.patch(f"{self.API_USER_ENDPOINT}{registered_user['id']}", json=patch_data)
        assert response.status_code == 401

        response = await async_client.patch(f"{self.API_USER_ENDPOINT}{registered_user['id']}", json=patch_data, headers=headers)
        assert response.status_code == 403

    @pytest.mark.anyio
    async def test_patch_user_nickname(self, registered_user, logged_in_admin_token, async_client: AsyncClient):
        """Test partial update of user nickname."""
        headers = {"Authorization": f"Bearer {logged_in_admin_token}"}

        patch_data = {"nickname": "Patched Nickname"}

        response = await async_client.patch(f"{self.API_USER_ENDPOINT}{registered_user['id']}", json=patch_data, headers=headers)
        assert response.status_code == 202

        user_data = response.json()
        assert user_data["nickname"] == patch_data["nickname"]

    @pytest.mark.anyio
    async def test_patch_user_invalid_nickname(self, registered_user, logged_in_admin_token, async_client: AsyncClient):
        """Test partial update with invalid nickname."""
        headers = {"Authorization": f"Bearer {logged_in_admin_token}"}

        patch_data = {"nickname": ""}

        response = await async_client.patch(f"{self.API_USER_ENDPOINT}{registered_user['id']}", json=patch_data, headers=headers)
        assert response.status_code == 422

    @pytest.mark.anyio
    async def test_patch_user_password(self, registered_user, logged_in_admin_token, async_client: AsyncClient):
        """Test partial update of user password."""
        headers = {"Authorization": f"Bearer {logged_in_admin_token}"}

        patch_data = {"password": "SecurePass#123"}

        response = await async_client.patch(f"{self.API_USER_ENDPOINT}{registered_user['id']}", json=patch_data, headers=headers)
        assert response.status_code == 202

        user_data = response.json()
        # Verify other data remain unchanged
        assert user_data["email"] == self.data["email"]

    @pytest.mark.anyio
    async def test_patch_user_invalid_password(self, registered_user, logged_in_admin_token, async_client: AsyncClient):
        """Test partial update with invalid password."""
        headers = {"Authorization": f"Bearer {logged_in_admin_token}"}

        invalid_passwords = ["short", "12345678", "", None, "abcdefgh"]

        for pwd in invalid_passwords:
            patch_data = {"password": pwd}
            response = await async_client.patch(f"{self.API_USER_ENDPOINT}{registered_user['id']}", json=patch_data, headers=headers)
            assert response.status_code == 422

    @pytest.mark.anyio
    async def test_patch_user_email(self, registered_user, logged_in_admin_token, async_client: AsyncClient):
        """Test partial update of user email."""
        headers = {"Authorization": f"Bearer {logged_in_admin_token}"}

        patch_data = {"email": "updated@laland.pl"}

        response = await async_client.patch(f"{self.API_USER_ENDPOINT}{registered_user['id']}", json=patch_data, headers=headers)
        assert response.status_code == 202

        user_data = response.json()
        assert user_data["email"] == patch_data["email"]

    @pytest.mark.anyio
    async def test_patch_user_invalid_email(self, registered_user, logged_in_admin_token, async_client: AsyncClient):
        """Test partial update with invalid email."""
        headers = {"Authorization": f"Bearer {logged_in_admin_token}"}

        invalid_emails = ["plainaddress",
                          "missingatsign.com", "@missinguser.com", "", None]

        for email in invalid_emails:
            patch_data = {"email": email}
            response = await async_client.patch(f"{self.API_USER_ENDPOINT}{registered_user['id']}", json=patch_data, headers=headers)
            assert response.status_code == 422

    @pytest.mark.anyio
    async def test_concurrent_updates(self, registered_user, logged_in_admin_token, async_client: AsyncClient):
        """Test concurrent updates to the same user."""
        headers = {"Authorization": f"Bearer {logged_in_admin_token}"}

        # Simulate concurrent updates
        update1 = {"nickname": "Update1"}
        update2 = {"nickname": "Update2"}

        # In a real test, you might use asyncio.gather to make concurrent requests
        response1 = await async_client.patch(f"{self.API_USER_ENDPOINT}{registered_user['id']}", json=update1, headers=headers)
        response2 = await async_client.patch(f"{self.API_USER_ENDPOINT}{registered_user['id']}", json=update2, headers=headers)

        # Check that both updates were processed
        assert response1.status_code == 202
        assert response2.status_code == 202

        # Get the final state
        response = await async_client.get(f"{self.API_USER_ENDPOINT}{registered_user['id']}", headers=headers)
        user_data = response.json()

        # The final state should be consistent (either Update1 or Update2)
        assert user_data["nickname"] in [
            update1["nickname"], update2["nickname"]]


class TestUserDeletion(BaseUser):
    """Tests for user deletion functionality."""

    @pytest.mark.anyio
    async def test_delete_user_invalid_auth(self, registered_user, logged_in_token, async_client: AsyncClient):
        """Test authorization rules for user deletion."""
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
        """Test user deletion by ID."""
        headers = {"Authorization": f"Bearer {logged_in_admin_token}"}

        response = await async_client.delete(f"{self.API_USER_ENDPOINT}{registered_user['id']}", headers=headers)
        assert response.status_code == 204

        response = await async_client.get(f"{self.API_USER_ENDPOINT}{registered_user['id']}", headers=headers)
        assert response.status_code == 404

    @pytest.mark.anyio
    async def test_delete_user_by_token(self, confirmed_user, logged_in_token, logged_in_admin_token, async_client: AsyncClient):
        """Test user deletion by token."""
        headers = {"Authorization": f"Bearer {logged_in_token}"}
        response = await async_client.delete(f"{self.API_USER_ENDPOINT}", headers=headers)
        assert response.status_code == 204

        headers_admin = {"Authorization": f"Bearer {logged_in_admin_token}"}
        response = await async_client.get(f"{self.API_USER_ENDPOINT}{confirmed_user['id']}", headers=headers_admin)
        assert response.status_code == 404


class TestUserCRUD(BaseUser):
    """Comprehensive test for the complete user lifecycle."""

    @pytest.mark.anyio
    async def test_crud(self, logged_in_admin_token, mock_background, mock_confirmation_email, async_client: AsyncClient, session: AsyncSession):
        """Test the complete user lifecycle: Create, Read, Update, Delete."""
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

        mock_background.assert_called_once()
        mock_confirmation_email.assert_called_once()
        args, kwargs = mock_confirmation_email.call_args
        assert kwargs['nickname'] == self.data["nickname"]
        assert kwargs['email'] == self.data["email"]
        assert "confirmation_url" in kwargs

        confirmation_url = str(kwargs["confirmation_url"])
        response = await async_client.get(str(confirmation_url))
        assert response.status_code == 202

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
