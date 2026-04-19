"""
Сервис для сущности ScheduleGroupLink.
"""
from app.models.schedule_group_link import ScheduleGroupLink
from app.schemas.schedule_group_link import (
    ScheduleGroupLinkCreateSchema,
    ScheduleGroupLinkDeleteSchema,
    ScheduleGroupLinkFilterSchema,
    ScheduleGroupLinkUpdateSchema,
)
from app.services.base import BaseService


class ScheduleGroupLinkService(BaseService[ScheduleGroupLink]):
    """
    Сервис подготовки операций над моделью ScheduleGroupLink.
    """

    model = ScheduleGroupLink
    create_schema = ScheduleGroupLinkCreateSchema
    select_schema = ScheduleGroupLinkFilterSchema
    update_schema = ScheduleGroupLinkUpdateSchema
    delete_schema = ScheduleGroupLinkDeleteSchema
    schema_fields = frozenset({"group_id", "schedule_id"})
