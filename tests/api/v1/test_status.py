import pytest
from httpx import AsyncClient
from datetime import datetime

from app.core.configs import settings
from tests.api.base_users import BaseUser


class TestStatus(BaseUser):

    API_STATUS_ENDPOINT = f"{settings.API_V1_STR}/status/"

    @pytest.mark.anyio
    async def test_get_basic_status(self, async_client: AsyncClient):
        response = await async_client.get(self.API_STATUS_ENDPOINT)
        assert response.status_code == 200

        data = response.json()
        assert data["status"] in ["ok", "not-ok"]
        assert isinstance(datetime.fromisoformat(data["timestamp"]), datetime)
        assert data["uptime_secs"] >= 0 and isinstance(
            data["uptime_secs"], int)
        assert 0 <= data["cpu_usage"] <= 100
        assert 0 <= data["memory_usage"] <= 100

    @pytest.mark.anyio
    async def test_get_detailed_status(self, async_client: AsyncClient, logged_in_admin_token):
        headers = {"Authorization": f"Bearer {logged_in_admin_token}"}
        response = await async_client.get(f"{self.API_STATUS_ENDPOINT}detailed", headers=headers)
        assert response.status_code == 200

        data = response.json()
        # Basic status fields
        assert data["status"] in ["ok", "not-ok"]
        assert isinstance(datetime.fromisoformat(data["timestamp"]), datetime)
        assert data["uptime_secs"] >= 0 and isinstance(
            data["uptime_secs"], int)
        assert 0 <= data["cpu_usage"] <= 100
        assert 0 <= data["memory_usage"] <= 100

        # Additional detailed fields
        assert "disk_usage" in data
        assert 0 <= data["disk_usage"] <= 100
        assert "network_io" in data
        assert isinstance(data["network_io"], dict)
        assert "database" in data
        assert data["database"]["status"] in ["connected", "disconnected"]
        if data["database"]["status"] == "connected":
            assert "latency_ms" in data["database"]
            assert isinstance(data["database"]["latency_ms"], (int, float))
        assert "version" in data
        assert "python_version" in data["version"]
        assert "platform" in data["version"]
        assert "app_version" in data["version"]

    @pytest.mark.anyio
    async def test_get_detailed_status_unauthorized(self, async_client: AsyncClient):
        response = await async_client.get(f"{self.API_STATUS_ENDPOINT}detailed")
        assert response.status_code == 401
