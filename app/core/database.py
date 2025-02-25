import asyncio
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
from app.models import RolesModel, UsersModel, FileStatusModel

logger = logging.getLogger(__name__)

engine: AsyncEngine = create_async_engine(
    settings.DATABASE_URL, echo=settings.SQLALCHEMY_ECHO)

Session: AsyncSession = sessionmaker(
    bind=engine, autoflush=False, expire_on_commit=False, class_=AsyncSession)


async def validate_db_connection(base_url: str) -> bool:
    temp_engine = create_async_engine(base_url, echo=False)
    try:
        conn = await temp_engine.connect()
        await conn.close()
        return True
    except (asyncio.TimeoutError, asyncio.CancelledError) as e:
        logger.error(
            f"Failed to connect to the database. Please check database connection information and ensure it is working. "
            f"Example: Try using pgAdmin. Error: {e}"
        )
    except Exception as e:
        logger.error(f"Unexpected error while connecting to the database: {e}")
    return False


async def database_exists(base_url: str, database_name: str) -> bool:
    logger.debug(f"Checking if database '{database_name}' exists")

    if not await validate_db_connection(base_url):
        raise Exception("Could not establish a connection with the database.")

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
            base_url, isolation_level="AUTOCOMMIT", echo=True)
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


async def initialize_default_values() -> None:
    logger.info("Initializing default values in the database")
    async with Session() as session:
        if not await RolesModel.find_by_authority(settings.MIN_ROLE, session):
            logger.debug("Did not find default role, creating it")
            role_min = RolesModel(authority=settings.MIN_ROLE, name="Default")
            session.add(role_min)
            await session.commit()

        if not await RolesModel.find_by_authority(settings.MAX_ROLE, session):
            logger.debug("Did not find superuser role, creating it")
            role_max = RolesModel(
                authority=settings.MAX_ROLE, name="SuperUser")
            session.add(role_max)
            await session.commit()

        if not await UsersModel.find_by_email(settings.ADMIN_DEFAULT_EMAIL, session):
            logger.debug("Did not find admin user, creating it")
            role_admin = await RolesModel.find_by_authority(
                settings.MAX_ROLE, session)
            admin = UsersModel(nickname="SWoto", email=settings.ADMIN_DEFAULT_EMAIL,
                               password=settings.ADMIN_DEFAULT_PASSWORD, role_id=role_admin.id, confirmed=True)
            session.add(admin)
            await session.commit()

        await FileStatusModel().initialize_default_statuses(session)


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
