"""
Модель комментариев для студентов за конкретные занятия в течение года
"""
# pylint: disable=unsubscriptable-object
from typing import Optional

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base

MAX_LEN = {
    "data": 4096
}


class Comment(Base):
    """
    Реализация модели.
    Хранит в себе свой id, дату создания записи, дату обновления записи, id студента, id занятия, комментарий.
    Имеет связь с базами данных студентов и занятий.
    """

    __table_args__ = (
        UniqueConstraint("student_id", "lesson_id", name="uq_comment_student_lesson"),
    )

    # Столбцы модели
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"))
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id", ondelete="CASCADE"))
    data: Mapped[Optional[str]] = mapped_column(String(MAX_LEN["data"]))

    # Связь с занятием в календаре (Many-to-One)
    lesson: Mapped["Lesson"] = relationship(back_populates="comments")
    # Связь со студентом (Many-to-One)
    student: Mapped["Student"] = relationship(back_populates="comments")
