import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


from app.models import UsersModel
from app.core.configs import settings


class BaseUser():
    data = {
        "email": "test6@example.net",
        "nickname": "Banana De Pijamas",
        "password": "osdn-19VS#",
        "confirmed": False,
    }

    API_USER_ENDPOINT = f"{settings.API_V1_STR}/user/"

    @classmethod
    @pytest.fixture
    def mock_sqs(cls, mocker):
        return mocker.patch('app.core.aws_handler.SQSHandler.send_message_to_sqs')

    @classmethod
    @pytest.fixture
    def mock_confirmation_email(cls, mocker):
        """Mock the send_confirmation_email function"""
        return mocker.patch('app.api.v1.endpoints.users.send_confirmation_email')

    @classmethod
    @pytest.fixture
    def mock_background(cls, mocker):
        return mocker.patch('fastapi.BackgroundTasks.add_task',
                            side_effect=lambda f, *args, **kwargs: f(*args, **kwargs))

    @staticmethod
    async def register_user(async_client: AsyncClient, user_data: dict) -> dict:
        int_user_data = user_data.copy()
        int_user_data.pop("confirmed")
        return await async_client.post(
            f"{BaseUser.API_USER_ENDPOINT}signup", json={**user_data}
        )

    @staticmethod
    async def login_user(async_client: AsyncClient, email: str, password: str) -> dict:
        return await async_client.post(
            f"{BaseUser.API_USER_ENDPOINT}login", data={'username': email, 'password': password})

    @staticmethod
    async def confirm_user(email, session: AsyncSession) -> dict:
        user = await UsersModel.find_by_email(email, session)
        user.confirm_register()
        await session.commit()

        return user

    @classmethod
    @pytest.fixture
    async def registered_user(cls, async_client: AsyncClient, session: AsyncSession, mock_background, mock_confirmation_email) -> UsersModel:
        "Returns registered user with mocked background task to avoid sending SQS triggers"
        response = await cls.register_user(async_client, cls.data)

        return response.json()

    @classmethod
    @pytest.fixture
    async def confirmed_user(cls, registered_user, session: AsyncSession) -> UsersModel:
        _ = await cls.confirm_user(registered_user["email"], session)

        return registered_user

    @classmethod
    @pytest.fixture
    async def logged_in_token(cls, confirmed_user, async_client: AsyncClient) -> str:
        response = await cls.login_user(async_client, cls.data["email"], cls.data["password"])

        return response.json()["access_token"]

    @classmethod
    @pytest.fixture
    async def logged_in_admin_token(cls, async_client: AsyncClient) -> str:
        response = await cls.login_user(async_client, settings.ADMIN_DEFAULT_EMAIL, settings.ADMIN_DEFAULT_PASSWORD)

        return response.json()["access_token"]

    @pytest.fixture(autouse=True)
    def reset_state(self) -> None:
        self.data["confirmed"] = False
