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

#TODO: Add generic API_STR
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/users/login"
)

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
    payload = {} # More about at: https://datatracker.ietf.org/doc/html/rfc7519#section-4.1.3
    timezone_offset = -3.0  # America/Sao_Paulo
    tzinfo = timezone(timedelta(hours=timezone_offset))
    now = datetime.now(tz=tzinfo)
    expires_on = now + life_time
    logger.debug(f"Creating {token_type} token", extra={
                 "id": subject, "experis_on": expires_on})
    
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

async def send_user_confirmation_email(email: EmailStr, confirmation_url: HttpUrl):
    subject = "Successfully signed up to OOS - Confirm your email"
    body = (
        f"Hi {email}! You have successfully signed up to the OutOfSight (OOS)."
        " Please confirm your email by clicking on the"
        f" following link: {confirmation_url}. \n"
        "Note: This link is valid only for 30 minutes."
    )
    payload = {'subject': subject, 'body': body}

    if isinstance(settings, DevConfig) or isinstance(settings, TestConfig):
        logger.debug("User confirmation email data:", extra={**payload})
        
    #TODO: Add some MQTT handler here
    pass

async def validate_token(token: Annotated[str, Depends(oauth2_scheme)], type: Literal["access_token", "confirmation_token"] = "access_token") -> Optional[dict]:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=settings.ALGORITHM)
    except ExpiredSignatureError as e:
        logger.error(f"Token has expired", exc_info=e)
        raise create_credentials_exception("Token has experied") from e
    except JWTError as e:
        logger.error(f"Invalid Token: {e}")
        raise create_credentials_exception("Invalid Token") from e
    
    jti = payload.get("jti")
    if not jti:
        logger.info("Token with invalid 'jti' field")
        raise create_credentials_exception("Invalid Token")
    
    jti_in_redit = jwt_redis_blocklist.get(jti)
    if jti_in_redit is not None:
        logger.info("Token with blacklisted jti")
        raise create_credentials_exception("Invalid Token")
    
    user_id = payload.get("sub")
    if not user_id:
        logger.info("Token is missing 'sub' field")
        raise create_credentials_exception("Invalid Token")
    
    token_type = payload.get("type")
    if not token_type or token_type != type:
        logger.info(f"Token was incorrect type. Expects: {type}, Received:{token_type}")
        raise create_credentials_exception("Invalid Token Type")

    return payload

async def get_current_user(payload: Annotated[dict, Depends(validate_token)], db: Annotated[AsyncSession, Depends(get_db_session)]) -> Optional[UsersModel]:
    user_id = payload.get("sub")
    user = await UsersModel.find_by_id(user_id, db)
    if not user:
        raise create_credentials_exception("User not found")
    
    return user

async def blacklist_token(payload: Annotated[dict, Depends(validate_token)]):
    jti = payload.get("jti")
    token_type = payload.get("type")
    experis_on = timedelta(minutes=settings.CONFIRMATION_TOKEN_EXPIRE_MINUTES) if token_type == "confirmation_token" else timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    jwt_redis_blocklist.set(jti, "blacklisted", ex=experis_on)
