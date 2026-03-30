# app/models/__init__.py
"""
Импорт всех моделей для регистрации в SQLAlchemy.
ВАЖНО: Порядок импорта имеет значение!
"""

# Сначала модели без зависимостей
from .group import Group
from .schedule import Schedule

# Затем модели с зависимостями
from .schedule_group_link import ScheduleGroupLink
from .student import Student
from .lesson import Lesson

# Потом модели, которые ссылаются на предыдущие
from .attendance import Attendance
from .mark import Mark
from .comment import Comment

__all__ = [
    "Group",
    "Schedule",
    "ScheduleGroupLink",
    "Student",
    "Lesson",
    "Attendance",
    "Mark",
    "Comment",
]