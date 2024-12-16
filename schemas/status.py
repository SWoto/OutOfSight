from pydantic import BaseModel
from typing import Literal
from decimal import Decimal
from datetime import datetime


class PlainStatusSchema(BaseModel):
    status: Literal["ok", "not-ok"]
    timestamp: datetime
    uptime: Decimal
    cpu_usage: Decimal
    memory_usage: Decimal
