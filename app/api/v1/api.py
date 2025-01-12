from fastapi import APIRouter

from app.api.v1.endpoints import status
from app.api.v1.endpoints import users
from app.api.v1.endpoints import roles


api_router = APIRouter()
api_router.include_router(status.router,
                          prefix='/status', tags=['Status'])
api_router.include_router(users.router, prefix='/user', tags=['Users'])
api_router.include_router(roles.router, prefix='/role', tags=['Roles'])