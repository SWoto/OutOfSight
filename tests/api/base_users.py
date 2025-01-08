import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


from app.models import UsersModel


class BaseUser():
    data = {
        "email": "test6@example.net",
        "nickname": "Banana De Pijamas",
        "password": "osdn-19VS#",
        "confirmed": False,
    }

    @staticmethod
    async def register_user(async_client: AsyncClient, user_data: dict) -> dict:
        int_user_data = user_data.copy()
        int_user_data.pop("confirmed")
        return await async_client.post(
            "/api/v1/user/signup", json={**user_data}
        )

    @staticmethod
    async def login_user(async_client: AsyncClient, email: str, password: str) -> dict:
        return await async_client.post(
            "/api/v1/user/login", data={'username': email, 'password': password})


    @staticmethod
    async def confirm_user(email, session: AsyncSession) -> dict:
        user = await UsersModel.find_by_email(email, session)
        user.confirm_register()
        await session.commit()
        
        return user    

    @classmethod
    @pytest.fixture
    async def registered_user(cls, async_client: AsyncClient, session: AsyncSession) -> UsersModel:
        _ = await cls.register_user(async_client, cls.data)
        user = await UsersModel.find_by_email(cls.data["email"], session)
        
        return user
    

    @classmethod
    @pytest.fixture
    async def confirmed_user(cls, registered_user, session: AsyncSession) -> UsersModel:
        _ = await cls.confirm_user(registered_user.email, session)

        return registered_user
    

    @classmethod
    @pytest.fixture
    async def logged_in_token(cls, confirmed_user, async_client: AsyncClient) -> str:
        response = await cls.login_user(async_client, cls.data["email"], cls.data["password"])

        return response.json()["access_token"]
    

    @pytest.fixture(autouse=True)
    def reset_state(self) -> None:
        self.data["confirmed"] = False
