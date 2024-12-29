import logging
from datetime import datetime, timezone
from fastapi import FastAPI
import os
from contextlib import asynccontextmanager
from asgi_correlation_id import CorrelationIdMiddleware


from app.core.configs import settings, DevConfig, TestConfig
from app.core.logging import configure_logging
from app.api.v1.api import api_router
from app.core.database import create_tables, create_database

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI, settings=settings):
    try:
        configure_logging()
        if isinstance(settings, TestConfig) or isinstance(settings, DevConfig):
            await create_database(settings.DATABASE_URL, settings.POSTGRES_DB)
            await create_tables()
        yield
    except Exception as e:
        logger.error(f"Error during application startup: {e}")
        raise

    finally:
        logger.info("Application shutdown complete.")


app = FastAPI(debug=True, title="OutOfSight", lifespan=lifespan)
app.add_middleware(CorrelationIdMiddleware)
app.include_router(router=api_router, prefix=settings.API_V1_STR)

os.environ['STARTUP_TIME'] = datetime.now(timezone.utc).isoformat()

if __name__ == '__main__':
    import unicorn

    unicorn.run('main.app', reload=True, log_level="debug")
