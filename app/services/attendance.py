"""
Сервис для сущности Attendance.
"""
from app.models.attendance import Attendance
from app.schemas.attendance import (
    AttendanceCreateSchema,
    AttendanceDeleteSchema,
    AttendanceFilterSchema,
    AttendanceUpdateSchema,
)
from app.services.base import BaseService


class AttendanceService(BaseService[Attendance]):
    """
    Сервис подготовки операций над моделью Attendance.
    """

    model = Attendance
    create_schema = AttendanceCreateSchema
    select_schema = AttendanceFilterSchema
    update_schema = AttendanceUpdateSchema
    delete_schema = AttendanceDeleteSchema
    schema_fields = frozenset({"student_id", "lesson_id", "is_visited"})
