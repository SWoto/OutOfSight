import logging
from uuid import UUID
from typing import Annotated
from fastapi import APIRouter, status, Request, Depends, HTTPException, BackgroundTasks
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import ValidationError

from app.core.configs import settings
from app.core.database import get_db_session
from app.schemas import PostPutUserSchema, ReturnUserSchema, PatchUserSchema, LoginUserSchema, ReturnUserWithRoleIDSchema, PostPutUserWithRoleIDSchema, ReturnUserWithRoleObjSchema
from app.models import UsersModel, RolesModel
from app.core.security import get_hashed_password
from app.core.auth import authenticate_user, Token, create_access_token, create_confirmation_token, send_user_confirmation_email, validate_token, get_current_user, blacklist_token

router = APIRouter()

logger = logging.getLogger(__name__)


@router.post('/signup', status_code=status.HTTP_201_CREATED, response_model=ReturnUserWithRoleObjSchema, tags=["Users", "Authentication"], summary="User Signup", description="Register a new user.")
async def post_user(user: PostPutUserSchema, request: Request, background_tasks: BackgroundTasks, db: Annotated[AsyncSession, Depends(get_db_session)]):
    post_data = user.model_dump()
    new_user = UsersModel(**post_data)

    # Always add default user. To have higher auth, someone with higher than the one to be added, has to change the target user
    min_role = await RolesModel.find_by_authority(settings.MIN_ROLE, db)
    new_user.role_id = min_role.id

    if await UsersModel.find_by_email(new_user.email, db):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    if not await RolesModel.find_by_id(new_user.role_id, db):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Provided role id does not exist")

    db.add(new_user)
    await db.commit()

    # TODO: Add task for message brokers
    background_tasks.add_task(
        send_user_confirmation_email,
        email=new_user.email,
        confirmation_url=request.url_for(
            "get_confirmation_email",
            token=create_confirmation_token(str(new_user.id)),
        )
    )

    # new query to get role info
    return await UsersModel.find_by_email(new_user.email, db)


@router.get('/confirm/{token}', status_code=status.HTTP_202_ACCEPTED, tags=["Users", "Authentication"], summary="Email Confirmation", description="Confirm a user's email address using the token.")
async def get_confirmation_email(token: str, db: Annotated[AsyncSession, Depends(get_db_session)]):
    payload = await validate_token(token, "confirmation_token")
    user = await get_current_user(payload, db)

    if not user.get_confirmed():
        async with db as session:
            requested_user = await UsersModel.find_by_id(user.id, session)
            requested_user.confirm_register()
            await session.commit()

    await blacklist_token(payload)

    return {"detail": "User confirmed"}


@router.post('/login',  tags=["Users", "Authentication"], summary="User Login", description="Authenticate a user and return an access token.")
async def login_user(request: Request, form_data: Annotated[OAuth2PasswordRequestForm, Depends()], db: Annotated[AsyncSession, Depends(get_db_session)]):
    user_info = {"email": form_data.username, "password": form_data.password}

    try:
        LoginUserSchema(**user_info)
    except ValidationError as exc:
        logger.exception(repr(exc.errors()[0]['type']))
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Username has to be an email and password an string.")

    user = await authenticate_user(**user_info, db=db)

    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Incorrect username (e-mail) or password")
    if not user.confirmed:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="E-mail pending confirmation")

    return Token(access_token=create_access_token(subject=str(user.id)), token_type="bearer")


# TODO: Add administrator access to this or change own
@router.get('/{id}', status_code=status.HTTP_200_OK, response_model=ReturnUserSchema, tags=["Users"], summary="Get User by ID", description="Retrieve a user's details by their ID.")
async def get_user_by_id(id: UUID, db: Annotated[AsyncSession, Depends(get_db_session)]):
    requested_user = await UsersModel.find_by_id(id, db)
    if not requested_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User does not exists")

    return requested_user


@router.get('/', status_code=status.HTTP_200_OK, response_model=ReturnUserSchema, tags=["Users"], summary="Get User by bearer token", description="Retrieve a user's details by bearer token.")
async def get_user_by_token(current_user: Annotated[UsersModel, Depends(get_current_user)]):
    return current_user


# TODO: Add administrator access to this
@router.put('/{id}', status_code=status.HTTP_202_ACCEPTED, response_model=ReturnUserSchema, tags=["Users"], summary="Update all user data", description="Get existing user and replace all of its data from provided information")
async def put_user(id: UUID, user: PostPutUserSchema, db: Annotated[AsyncSession, Depends(get_db_session)]):
    # Given that PostPutUserSchema is more restrictive then patch, first pass through PostPutUserSchema then sends to PatchUserSchema.
    return await patch_user(id, user, db)


# TODO: Add administrator access to this
@router.patch('/{id}', status_code=status.HTTP_202_ACCEPTED, response_model=ReturnUserSchema, tags=["Users"], summary="Patch user data", description="Get existing user and replace with the provided information")
async def patch_user(id: UUID, user: PatchUserSchema, db: Annotated[AsyncSession, Depends(get_db_session)]):
    requested_user = await get_user_by_id(id, db)

    new_data = user.model_dump()
    for key in new_data:
        if new_data[key] and new_data[key] != "":
            if key == 'password':
                new_data[key] = get_hashed_password(new_data[key])
            setattr(requested_user, key, new_data[key])

    await db.commit()

    return await UsersModel.find_by_id(id, db)


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Users"], summary="Delete user", description="Get existing user from ID and deletes it")
async def delete_user_by_id(id: UUID, db: Annotated[AsyncSession, Depends(get_db_session)]):
    requested_user = await get_user_by_id(id, db)

    await delete_user_by_token(requested_user, db)


@router.delete("/", status_code=status.HTTP_204_NO_CONTENT, tags=["Users"], summary="Delete user", description="Get existing user from ID and deletes it")
async def delete_user_by_token(current_user: Annotated[UsersModel, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db_session)]):
    requested_user = await UsersModel.find_by_id(current_user.id, db)
    await requested_user.delete_from_db(db)

    return
