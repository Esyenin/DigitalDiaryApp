"""
Пакет сервисов проекта.
"""
from app.services.attendance import AttendanceService
from app.services.base import BaseService
from app.services.comment import CommentService
from app.services.group import GroupService
from app.services.lesson import LessonService
from app.services.mark import MarkService
from app.services.schedule import ScheduleService
from app.services.schedule_group_links import ScheduleGroupLinkService
from app.services.student import StudentService

__all__ = [
    "BaseService",
    "GroupService",
    "StudentService",
    "ScheduleService",
    "ScheduleGroupLinkService",
    "LessonService",
    "AttendanceService",
    "MarkService",
    "CommentService",
]
