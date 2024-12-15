from fastapi import APIRouter, status

from datetime import datetime, timezone

router = APIRouter()


# TODO: check what happens without the status code
@router.get('/', status_code=status.HTTP_200_OK)
async def get_live():
    current_date = datetime.now(timezone.utc).isoformat()
    return current_date
