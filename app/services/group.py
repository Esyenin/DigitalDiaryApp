"""
Сервис для сущности Group.
"""
from app.models.group import Group
from app.schemas.group import (
    GroupCreateSchema,
    GroupDeleteSchema,
    GroupFilterSchema,
    GroupUpdateSchema,
)
from app.services.base import BaseService


class GroupService(BaseService[Group]):
    """
    Сервис подготовки операций над моделью Group.
    """

    model = Group
    create_schema = GroupCreateSchema
    select_schema = GroupFilterSchema
    update_schema = GroupUpdateSchema
    delete_schema = GroupDeleteSchema
    schema_fields = frozenset({"name", "speciality"})
