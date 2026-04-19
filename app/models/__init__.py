"""
Пакет моделей проекта.

Импорты из этого файла обеспечивают регистрацию всех ORM-моделей
в `Base.metadata`.
"""
from app.models.attendance import Attendance
from app.models.base import Base
from app.models.comment import Comment
from app.models.group import Group
from app.models.lesson import Lesson
from app.models.mark import Mark
from app.models.schedule import Schedule
from app.models.schedule_group_link import ScheduleGroupLink
from app.models.student import Student

__all__ = [
    "Base",
    "Group",
    "Student",
    "Schedule",
    "ScheduleGroupLink",
    "Lesson",
    "Attendance",
    "Mark",
    "Comment",
]
