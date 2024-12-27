import logging
from datetime import datetime, timezone
from fastapi import FastAPI
import os

from app.api.v1.api import api_router
from app.core.logging import configure_logging

logger = logging.getLogger(__name__)

app = FastAPI(debug=True, title="OutOfSight")
app.include_router(router=api_router)

os.environ['STARTUP_TIME'] = datetime.now(timezone.utc).isoformat()

if __name__ == '__main__':
    import unicorn

    unicorn.run('main.app', reload=True, log_level="debug")
