from datetime import datetime, timedelta, timezone
from typing import Optional, Annotated, Literal
import uuid
import logging
from pydantic import EmailStr, BaseModel, HttpUrl
from jose import ExpiredSignatureError, JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.core.configs import settings, DevConfig, TestConfig
from app.models.users import UsersModel
from app.core.security import check_password
from app.core.blocklist import jwt_redis_blocklist
from app.core.database import get_db_session

logger = logging.getLogger(__name__)


class Token(BaseModel):
    access_token: str
    token_type: str


oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/users/login"
)

TokenType = Literal["access_token", "confirmation_token"]


def is_valid_uuid(uuid_str, version):
    try:
        uuid.UUID(uuid_str, version=version)
        return True
    except ValueError:
        return False


def create_credentials_exception(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


async def authenticate_user(email: EmailStr, password: str, db: AsyncSession) -> Optional[UsersModel]:
    logger.debug("Authenticating user", extra={"email": email})
    user = await UsersModel.find_by_email(db=db, email=email)
    if (not user or
            not check_password(password, user.password)):
        return

    return user


def create_token(token_type: str, life_time: timedelta, subject: str) -> str:
    """
    Creates a JWT token with the specified type, lifetime, and subject.

    :param token_type: Type of the token (e.g., 'access_token', 'confirmation_token').
    :param life_time: Lifetime of the token.
    :param subject: Subject of the token (usually the user ID).
    :return: Encoded JWT token.
    """
    payload = {}  # More about at: https://datatracker.ietf.org/doc/html/rfc7519#section-4.1.3
    timezone_offset = settings.TIMEZONE_OFFSET  # America/Sao_Paulo
    tzinfo = timezone(timedelta(hours=timezone_offset))
    now = datetime.now(tz=tzinfo)
    expires_on = now + life_time
    logger.debug("Creating token",
                 extra={
                     "token_type": token_type,
                     "subject": subject,
                     "expires": expires_on
                 }
                 )

    payload['type'] = token_type
    payload['exp'] = expires_on
    payload['iat'] = now  # issued at
    payload['sub'] = subject
    payload['jti'] = str(uuid.uuid4())  # so we can blacklist

    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.ALGORITHM)


def create_access_token(subject: str) -> str:
    # https://jwt.io
    return create_token('access_token', timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES), subject=subject)


def create_confirmation_token(subject: str) -> str:
    return create_token('confirmation_token', timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES), subject=subject)


async def validate_token(token: Annotated[str, Depends(oauth2_scheme)], type: TokenType = "access_token") -> Optional[dict]:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET,
                             algorithms=settings.ALGORITHM)
    except ExpiredSignatureError as e:
        logger.error(f"Token has expired", exc_info=True)
        raise create_credentials_exception("Token has expired") from e
    except JWTError as e:
        logger.error(f"Invalid Token: {e}", exc_info=True)
        raise create_credentials_exception(f"Invalid Token: {str(e)}") from e

    jti = payload.get("jti")
    if not jti:
        logger.info("Token with invalid 'jti' field")
        raise create_credentials_exception("Invalid Token")

    jti_in_redis = jwt_redis_blocklist.get(jti)
    if jti_in_redis is not None:
        logger.info("Token with blacklisted jti")
        raise create_credentials_exception("Invalid Token")

    user_id = payload.get("sub")
    if not user_id:
        logger.info("Token is missing 'sub' field")
        raise create_credentials_exception("Invalid Token")
    if not is_valid_uuid(user_id, 4):
        logger.info("'sub' field is not a valid UUID4")
        raise create_credentials_exception("Invalid Token")

    token_type = payload.get("type")
    if not token_type or token_type != type:
        logger.info(
            f"Token was incorrect type. Expects: {type}, Received:{token_type}")
        raise create_credentials_exception("Invalid Token Type")

    return payload


async def get_current_user(payload: Annotated[dict, Depends(validate_token)], db: Annotated[AsyncSession, Depends(get_db_session)]) -> UsersModel:
    user_id = payload.get("sub")
    user = await UsersModel.find_by_id(user_id, db)
    if not user:
        raise create_credentials_exception("User not found")

    return user


async def blacklist_token(payload: Annotated[dict, Depends(validate_token)]):
    jti = payload.get("jti")
    token_type = payload.get("type")
    expires_on = timedelta(minutes=settings.CONFIRMATION_TOKEN_EXPIRE_MINUTES) if token_type == "confirmation_token" else timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    jwt_redis_blocklist.set(jti, "blacklisted", ex=expires_on)


class RoleChecker:
    """
    A dependency class to check if a user has the required role to access a resource.

    :param min_allowed_role: The minimum role authority required.
    :param allow_self: Whether to allow access if the user is accessing their own resource.
    """

    def __init__(self, min_allowed_role: int, allow_self: bool = False) -> None:
        self.min_allowed_role = min_allowed_role
        self.allow_self = allow_self

    # ID Received from the method query string
    def __call__(self, user: Annotated[UsersModel, Depends(get_current_user)], id: Optional[uuid.UUID] = None) -> None:
        is_self = id and user.id and user.id == id
        attends_min_role = user.role.authority > self.min_allowed_role

        if not (self.allow_self and is_self) and not attends_min_role:
            logger.debug(
                f"Access denied for user {user.id} with role authority {user.role.authority}. "
                f"min_allowed_role: {self.min_allowed_role}, allow_self: {self.allow_self}, "
                f"requested_id: {id}, user_id: {user.id}"
            )

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )
