"""
Пакет со всеми Pydantic-схемами проекта.
"""
from app.schemas.attendance import (
    AttendanceBaseSchema,
    AttendanceCreateSchema,
    AttendanceDeleteSchema,
    AttendanceFilterSchema,
    AttendanceUpdateSchema,
)
from app.schemas.base import AppBaseSchema, IdSchema, TimestampSchema
from app.schemas.comment import (
    CommentBaseSchema,
    CommentCreateSchema,
    CommentDeleteSchema,
    CommentFilterSchema,
    CommentUpdateSchema,
)
from app.schemas.group import (
    GroupBaseSchema,
    GroupCreateSchema,
    GroupDeleteSchema,
    GroupFilterSchema,
    GroupUpdateSchema,
    is_group_name_formatted,
    is_speciality_formatted,
)
from app.schemas.lesson import (
    LessonBaseSchema,
    LessonCreateSchema,
    LessonDeleteSchema,
    LessonFilterSchema,
    LessonUpdateSchema,
)
from app.schemas.mark import (
    MarkBaseSchema,
    MarkCreateSchema,
    MarkDeleteSchema,
    MarkFilterSchema,
    MarkUpdateSchema,
)
from app.schemas.schedule import (
    ScheduleBaseSchema,
    ScheduleCreateSchema,
    ScheduleDeleteSchema,
    ScheduleFilterSchema,
    ScheduleUpdateSchema,
)
from app.schemas.schedule_group_link import (
    ScheduleGroupLinkBaseSchema,
    ScheduleGroupLinkCreateSchema,
    ScheduleGroupLinkDeleteSchema,
    ScheduleGroupLinkFilterSchema,
    ScheduleGroupLinkUpdateSchema,
)
from app.schemas.student import (
    StudentBaseSchema,
    StudentCreateSchema,
    StudentDeleteSchema,
    StudentFilterSchema,
    StudentUpdateSchema,
)

__all__ = [
    "AppBaseSchema",
    "IdSchema",
    "TimestampSchema",
    "GroupBaseSchema",
    "GroupCreateSchema",
    "GroupUpdateSchema",
    "GroupFilterSchema",
    "GroupDeleteSchema",
    "StudentBaseSchema",
    "StudentCreateSchema",
    "StudentUpdateSchema",
    "StudentFilterSchema",
    "StudentDeleteSchema",
    "ScheduleBaseSchema",
    "ScheduleCreateSchema",
    "ScheduleUpdateSchema",
    "ScheduleFilterSchema",
    "ScheduleDeleteSchema",
    "ScheduleGroupLinkBaseSchema",
    "ScheduleGroupLinkCreateSchema",
    "ScheduleGroupLinkUpdateSchema",
    "ScheduleGroupLinkFilterSchema",
    "ScheduleGroupLinkDeleteSchema",
    "LessonBaseSchema",
    "LessonCreateSchema",
    "LessonUpdateSchema",
    "LessonFilterSchema",
    "LessonDeleteSchema",
    "AttendanceBaseSchema",
    "AttendanceCreateSchema",
    "AttendanceUpdateSchema",
    "AttendanceFilterSchema",
    "AttendanceDeleteSchema",
    "MarkBaseSchema",
    "MarkCreateSchema",
    "MarkUpdateSchema",
    "MarkFilterSchema",
    "MarkDeleteSchema",
    "CommentBaseSchema",
    "CommentCreateSchema",
    "CommentUpdateSchema",
    "CommentFilterSchema",
    "CommentDeleteSchema",
    "is_group_name_formatted",
    "is_speciality_formatted",
]
