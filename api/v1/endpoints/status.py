from fastapi import APIRouter, status

import psutil
import os
from datetime import datetime, timezone

from schemas.status import PlainStatusSchema


router = APIRouter()


# TODO: check what happens without the status code
@router.get('/', status_code=status.HTTP_200_OK, response_model=PlainStatusSchema)
async def get_status():
    """
    Endpoint to check the health of the API.
    """
    startup_time = datetime.fromisoformat(os.getenv('STARTUP_TIME'))
    current_date = datetime.now(timezone.utc)
    cpu_usage = psutil.cpu_percent()
    memory_usage = psutil.virtual_memory().percent
    uptime_secs = int((current_date - startup_time).total_seconds())
    return {
        "status": "ok",
        "timestamp": current_date.isoformat(),
        "uptime_secs": uptime_secs,
        "cpu_usage": cpu_usage,
        "memory_usage": memory_usage,
    }
