import logging
from uuid import UUID
from typing import Annotated, List
from fastapi import APIRouter, status, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.schemas import RoleWithAuthoritySchema, ReturnRoleWithAuthoritySchema
from app.core.database import get_db_session
from app.models import RolesModel

router = APIRouter()

logger = logging.getLogger(__name__)


@router.post('/', status_code=status.HTTP_201_CREATED, response_model=ReturnRoleWithAuthoritySchema, tags=["Roles", "Authentication"], summary="Create Role", description="Create a new role to be atributed to users")
async def post_role(role: RoleWithAuthoritySchema, session: Annotated[AsyncSession, Depends(get_db_session)]):
    post_data = role.model_dump()
    new_role = RolesModel(**post_data)

    if await RolesModel.find_by_authority(new_role.authority, session):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Authority level already registered")

    session.add(new_role)
    await session.commit()

    return new_role


@router.get('/', response_model=List[ReturnRoleWithAuthoritySchema], tags=["Roles", "Authentication"], summary="Get All Roles", description="Get all roles, sorted by minimum to maximum authority")
async def get_all_roles(db: Annotated[AsyncSession, Depends(get_db_session)]):
    query = select(RolesModel)
    result = await db.execute(query)
    return result.scalars().all()


@router.get('/{id}', response_model=ReturnRoleWithAuthoritySchema, tags=["Roles", "Authentication"], summary="Get All Roles", description="Get all roles, sorted by minimum to maximum authority")
async def get_role_by_id(id: UUID, db: Annotated[AsyncSession, Depends(get_db_session)]):
    requested_obj = await RolesModel.find_by_id(id, db)
    if not requested_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Role does not exists")

    return requested_obj


@router.put('/{id}', status_code=status.HTTP_202_ACCEPTED, response_model=ReturnRoleWithAuthoritySchema, tags=["Roles", "Authentication"], summary="Change Role Information", description="Put role data, replacing authority and name.")
async def put_role(id: UUID, role: RoleWithAuthoritySchema, db: Annotated[AsyncSession, Depends(get_db_session)]):

    requested_obj = await get_role_by_id(id, db)

    new_data = role.model_dump()
    for key in new_data:
        setattr(requested_obj, key, new_data[key])

    await db.commit()

    return await RolesModel.find_by_id(id, db)


@router.delete('/{id}', status_code=status.HTTP_204_NO_CONTENT, tags=["Roles", "Authentication"], summary="Delete Role", description="Delete role from database.")
async def delete_role(id: UUID, db: Annotated[AsyncSession, Depends(get_db_session)]):
    requested_obj = await get_role_by_id(id, db)
    await requested_obj.delete_from_db(db)

    return
