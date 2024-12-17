from pydantic import BaseModel, PositiveFloat
from typing import Literal
from datetime import datetime


class PlainStatusSchema(BaseModel):
    status: Literal["ok", "not-ok"]
    timestamp: datetime
    uptime_secs: int
    cpu_usage: PositiveFloat
    memory_usage: PositiveFloat
