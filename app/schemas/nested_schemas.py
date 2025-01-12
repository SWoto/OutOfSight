from pydantic import UUID4
from typing import List, Optional

from app.schemas import ReturnUserSchema, PostPutUserSchema, PlainRoleSchema, ReturnRoleSchema


class ReturnUserWithRoleIDSchema(ReturnUserSchema):
    role_id: UUID4


class PostPutUserWithRoleIDSchema(PostPutUserSchema):
    role_id: Optional[UUID4] = None


class ReturnUserWithRoleObjSchema(ReturnUserSchema):
    role: ReturnRoleSchema


class ReturnRoleWithUsersObjSchema(ReturnRoleSchema):
    users: List[ReturnUserSchema]
