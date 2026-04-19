"""
Сервис для сущности Lesson.
"""
from app.models.lesson import Lesson
from app.schemas.lesson import (
    LessonCreateSchema,
    LessonDeleteSchema,
    LessonFilterSchema,
    LessonUpdateSchema,
)
from app.services.base import BaseService


class LessonService(BaseService[Lesson]):
    """
    Сервис подготовки операций над моделью Lesson.
    """

    model = Lesson
    create_schema = LessonCreateSchema
    select_schema = LessonFilterSchema
    update_schema = LessonUpdateSchema
    delete_schema = LessonDeleteSchema
    schema_fields = frozenset({"schedule_id", "topic", "date"})
