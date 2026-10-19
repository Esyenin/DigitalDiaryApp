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

    def apply_update(self, db_obj, data):
        if isinstance(db_obj, ScheduleGroupLink) and db_obj.schedule is not None and (
            db_obj.schedule.effective_until is not None or db_obj.schedule.lessons
        ):
            return None
        return super().apply_update(db_obj, data)
