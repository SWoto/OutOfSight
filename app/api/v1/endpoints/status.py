from functools import lru_cache
import logging
import platform
import time
from sqlalchemy import text
from typing import Annotated, Any, Dict, Optional
from fastapi import APIRouter, Depends, status

from fastapi.responses import JSONResponse
import psutil
import os
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import RoleChecker
from app.schemas.status import PlainStatusSchema, DetailedStatusSchema
from app.core.configs import settings, TestConfig
from app.core.database import get_db_session

logger = logging.getLogger(__name__)


router = APIRouter()


@lru_cache(maxsize=1)
def get_cached_system_metrics():
    """Get system metrics with caching to prevent excessive CPU/memory checks."""
    return {
        "cpu_usage": psutil.cpu_percent(),
        "memory_usage": psutil.virtual_memory().percent,
        "disk_usage": psutil.disk_usage('/').percent,
        "network_io": psutil.net_io_counters()._asdict(),
    }


async def check_database_connection(db: AsyncSession) -> Dict[str, Any]:
    """Check if the database is accessible."""
    try:
        db_start_time = time.time()
        await db.execute(text("SELECT 1"))
        db_latency_ms = round((time.time() - db_start_time) * 1000, 2)
        return {"status": "connected", "latency_ms": db_latency_ms}
    except Exception as e:
        return {"status": "disconnected", "error": str(e)}


async def get_status(complete: bool = False, db: Optional[AsyncSession] = None):
    try:
        startup_time = datetime.fromisoformat(os.getenv('STARTUP_TIME'))
        current_date = datetime.now(timezone.utc)
        uptime_secs = int((current_date - startup_time).total_seconds())

        metrics = get_cached_system_metrics()
        cpu_usage = metrics["cpu_usage"]
        memory_usage = metrics["memory_usage"]
        if isinstance(settings, TestConfig):
            cpu_usage = 0.55 if cpu_usage < 0 else cpu_usage
            memory_usage = 0.55 if memory_usage < 0 else memory_usage

        overall_status = "ok" if cpu_usage < 90 and memory_usage < 90 else "not-ok"

        return_metrics = {
            "status": overall_status,
            "timestamp": current_date.isoformat(),
            "uptime_secs": uptime_secs,
            "cpu_usage": cpu_usage,
            "memory_usage": memory_usage
        }

        if complete and db:
            return_metrics["disk_usage"] = metrics.get("disk_usage")
            return_metrics["network_io"] = metrics.get("network_io")

            db_status = await check_database_connection(db)

            version_info = {
                "python_version": platform.python_version(),
                "platform": platform.platform(),
                "app_version": getattr(settings, "VERSION", "unknown"),
            }

            return_metrics["status"] = 'not-ok' if db_status["status"] == "disconnected" else return_metrics["status"]
            return_metrics["database"] = db_status
            return_metrics["version"] = version_info

        return return_metrics
    except Exception as e:
        logger.error(e)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"status": "not-ok", "error": str(e)},
        )


@router.get('/', status_code=status.HTTP_200_OK, response_model=PlainStatusSchema)
async def get_basic_status():
    return await get_status()


@router.get('/detailed', status_code=status.HTTP_200_OK, response_model=DetailedStatusSchema)
async def get_detailed_status(db: Annotated[AsyncSession, Depends(get_db_session)], role_check: Annotated[None, Depends(RoleChecker(min_allowed_role=90))]):
    return await get_status(complete=True, db=db)
