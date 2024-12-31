import logging
from typing import Annotated
from fastapi import APIRouter, status, Request, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.configs import settings, TestConfig
from app.core.database import get_db_session
from app.schemas import PlainUserSchema, PostPutUserSchema, ReturnUserSchema, PatchUserSchema
from app.models import UsersModel
from app.core.security import get_hashed_password

router = APIRouter()

logger = logging.getLogger(__name__)

@router.post('/signup', status_code=status.HTTP_201_CREATED, response_model=ReturnUserSchema, tags=["Users", "Authentication"], summary="User Signup", description="Register a new user.")
async def post_user(user: PostPutUserSchema, request:Request, db: Annotated[AsyncSession, Depends(get_db_session)]):
    post_data = user.model_dump()
    new_user = UsersModel(**post_data)

    async with db as session:
        if await UsersModel.find_by_email(new_user.email, session):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

        session.add(new_user)
        await session.commit()

        #TODO: Email stuff and handle validation

    return new_user

#TODO: Add administrator access to this or change own
@router.get('/{id}', status_code=status.HTTP_200_OK, response_model=ReturnUserSchema, tags=["Users"], summary="Get User by ID", description="Retrieve a user's details by their ID.")
async def get_user_by_id(id: int, db: Annotated[AsyncSession, Depends(get_db_session)]):
    requested_user = await UsersModel.find_by_id(id, db)
    if not requested_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User does not exists")

    return requested_user

#TODO: Add administrator access to this
@router.put('/{id}', status_code=status.HTTP_202_ACCEPTED, response_model=ReturnUserSchema, tags=["Users"], summary="Update all user data", description="Get exing user and replace all of its data from provided information")
async def put_user(id: int, user: PostPutUserSchema, db: Annotated[AsyncSession, Depends(get_db_session)]):
    new_data = user.model_dump()
    requested_user = await UsersModel.find_by_id(id, db)
    if not requested_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User does not exists")
    
    async with db as session:
        requested_user = await UsersModel.find_by_id(id, session)
        for key in new_data:
            if key == 'password':
                new_data[key] = get_hashed_password(new_data[key])
            setattr(requested_user, key, new_data[key])
        await session.commit()

    new_requested_user = await UsersModel.find_by_id(id, db)
    return new_requested_user


#TODO: Add administrator access to this
@router.patch('/{id}', status_code=status.HTTP_202_ACCEPTED, response_model=ReturnUserSchema, tags=["Users"], summary="Patch user data", description="Get exing user and replace with the provided information")
async def patch_user(id: int, user: PatchUserSchema, db: Annotated[AsyncSession, Depends(get_db_session)]):
    new_data = user.model_dump()
    requested_user = await UsersModel.find_by_id(id, db)
    if not requested_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User does not exist.")
    
    async with db as session:
        requested_user = await UsersModel.find_by_id(id, session)
        for key in new_data:
            if new_data[key] and new_data[key] != "":
                if key == 'password':
                    new_data[key] = get_hashed_password(new_data[key])
                setattr(requested_user, key, new_data[key])
        await session.commit()

    new_requested_user = await UsersModel.find_by_id(id, db)
    return new_requested_user