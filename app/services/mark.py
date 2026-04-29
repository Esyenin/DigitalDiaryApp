"""
Сервис для сущности Mark.
"""
from app.models.mark import Mark
from app.schemas.mark import (
    MarkCreateSchema,
    MarkDeleteSchema,
    MarkFilterSchema,
    MarkUpdateSchema,
)
from app.services.base import BaseService


class MarkService(BaseService[Mark]):
    """
    Сервис подготовки операций над моделью Mark.
    """

    model = Mark
    create_schema = MarkCreateSchema
    select_schema = MarkFilterSchema
    update_schema = MarkUpdateSchema
    delete_schema = MarkDeleteSchema
    schema_fields = frozenset({"student_id", "lesson_id", "data"})
    update_lookup_fields = frozenset({"id", "student_id", "lesson_id"})
