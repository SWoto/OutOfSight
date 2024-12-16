from fastapi import APIRouter

from api.v1.endpoints import status

api_router = APIRouter()
api_router.include_router(status.router,
                          prefix='/status', tags=['Status'])