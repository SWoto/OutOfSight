from fastapi import APIRouter, status

import psutil
import os
from datetime import datetime, timezone

from app.schemas.status import PlainStatusSchema
from app.core.configs import settings

router = APIRouter()


@router.get('/', status_code=status.HTTP_200_OK, response_model=PlainStatusSchema)
async def get_status():
    """
    Endpoint to check the health of the API.
    """
    startup_time = datetime.fromisoformat(os.getenv('STARTUP_TIME'))
    current_date = datetime.now(timezone.utc)
    uptime_secs = int((current_date - startup_time).total_seconds())
    cpu_usage = psutil.cpu_percent()
    memory_usage = psutil.virtual_memory().percent
    if settings.ENV_STATE == "TEST":
        cpu_usage = 0.55 if cpu_usage < 0 else cpu_usage
        memory_usage = 0.55 if memory_usage < 0 else memory_usage
    return {
        "status": "ok",
        "timestamp": current_date.isoformat(),
        "uptime_secs": uptime_secs,
        "cpu_usage": cpu_usage,
        "memory_usage": memory_usage,
    }
