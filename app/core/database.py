import logging
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncEngine,
    AsyncSession
)
from sqlalchemy.exc import ProgrammingError, OperationalError
from sqlalchemy import text
from typing import AsyncGenerator

from app.core.configs import settings

logger = logging.getLogger(__name__)

engine: AsyncEngine = create_async_engine(
    settings.DATABASE_URL, echo=settings.SQLALCHEMY_ECHO)

Session: AsyncSession = sessionmaker(
    bind=engine, autoflush=False, expire_on_commit=False, class_=AsyncSession)


async def database_exists(base_url: str, database_name: str) -> bool:
    logger.debug(f"Checking if database '{database_name}' exists")
    temp_engine = create_async_engine(base_url, echo=False)
    async with temp_engine.connect() as conn:
        try:
            result = await conn.execute(text(f"SELECT 1 FROM pg_database WHERE datname = :dbname"), {'dbname': database_name})
            exists = result.scalar() is not None
            logger.debug(f"Database '{database_name}' exist status: {exists}")
            return exists
        except (ProgrammingError, OperationalError) as e:
            logger.error(f"Error checking database existence: {e}")
            return False


async def create_database(base_url: str, database_name: str) -> bool:
    engine_url = str(base_url)
    base_url = engine_url.rsplit('/', 1)[0] + '/postgres'

    if not await database_exists(base_url, database_name):
        logger.warning(
            f"Database '{database_name}' does not exist, creating it")
        temp_engine = create_async_engine(
            base_url, base_url, isolation_level="AUTOCOMMIT", echo=True)
        async with temp_engine.connect() as conn:
            try:
                await conn.execute(text(f"CREATE DATABASE {database_name}"))
                logger.info(f"Database '{database_name}' created successfully")
                return True
            except Exception as e:
                logger.error(
                    f"Failed to create database '{database_name}': {e}")
    else:
        logger.info(f"Database '{database_name}' already exists")

    return False


async def create_tables() -> None:
    logger.info("Creating tables in the database")
    async with engine.begin() as conn:
        await conn.run_sync(settings.DBBaseModel.metadata.create_all)
        logger.info("Tables created successfully")


async def drop_tables() -> None:
    logger.warning("Dropping all tables in the database")
    async with engine.begin() as conn:
        await conn.run_sync(settings.DBBaseModel.metadata.drop_all)
        logger.warning("Tables dropped successfully")


async def get_db_session() -> AsyncGenerator:
    async with Session() as session:
        yield session
