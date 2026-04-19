"""
Сервис для сущности Student.
"""
from app.models.student import Student
from app.schemas.student import (
    StudentCreateSchema,
    StudentDeleteSchema,
    StudentFilterSchema,
    StudentUpdateSchema,
)
from app.services.base import BaseService


class StudentService(BaseService[Student]):
    """
    Сервис подготовки операций над моделью Student.
    """

    model = Student
    create_schema = StudentCreateSchema
    select_schema = StudentFilterSchema
    update_schema = StudentUpdateSchema
    delete_schema = StudentDeleteSchema
    schema_fields = frozenset(
        {
            "group_id",
            "surname",
            "first_name",
            "patronymic",
            "personal_data",
            "bmstu_email",
        }
    )
