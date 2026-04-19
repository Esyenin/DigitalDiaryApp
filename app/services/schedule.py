"""
Сервис для сущности Schedule.
"""
from app.models.schedule import Schedule
from app.schemas.schedule import (
    ScheduleCreateSchema,
    ScheduleDeleteSchema,
    ScheduleFilterSchema,
    ScheduleUpdateSchema,
)
from app.services.base import BaseService


class ScheduleService(BaseService[Schedule]):
    """
    Сервис подготовки операций над моделью Schedule.
    """

    model = Schedule
    create_schema = ScheduleCreateSchema
    select_schema = ScheduleFilterSchema
    update_schema = ScheduleUpdateSchema
    delete_schema = ScheduleDeleteSchema
    schema_fields = frozenset(
        {"odd_or_even", "type", "is_assessment", "day", "time"}
    )
