import pytest
from httpx import AsyncClient
from datetime import datetime

from app.core.configs import settings


class TestStatus():

    API_STATUS_ENDPOINT = f"{settings.API_V1_STR}/status/"

    @pytest.mark.anyio
    async def test_get_status(self, async_client: AsyncClient):
        response = await async_client.get(self.API_STATUS_ENDPOINT)
        assert response.status_code == 200

        data = response.json()
        assert data["status"] in ["ok", "not-ok"]
        assert isinstance(datetime.fromisoformat(data["timestamp"]), datetime)
        assert data["uptime_secs"] >= 0 and isinstance(
            data["uptime_secs"], int)
        assert 0 <= data["cpu_usage"] <= 100
        assert 0 <= data["memory_usage"] <= 100
