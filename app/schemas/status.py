from pydantic import BaseModel, PositiveFloat
from typing import Any, Dict, Literal, Optional
from datetime import datetime


class PlainStatusSchema(BaseModel):
    status: Literal["ok", "not-ok"]
    timestamp: datetime
    uptime_secs: int
    cpu_usage: PositiveFloat
    memory_usage: PositiveFloat


class DatabaseStatusSchema(BaseModel):
    status: Literal["connected", "disconnected"]
    latency_ms: float
    error: Optional[str] = None


class VersionInfoSchema(BaseModel):
    python_version: str
    platform: str
    app_version: str


class DetailedStatusSchema(PlainStatusSchema):
    disk_usage: PositiveFloat
    network_io: Dict[str, Any]
    database: DatabaseStatusSchema
    version: VersionInfoSchema
