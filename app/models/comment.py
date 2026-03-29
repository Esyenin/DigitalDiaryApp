"""
Модель комментариев для студентов за конкретные занятия в течение года
"""
# pylint: disable=unsubscriptable-object
from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base


class Comment(Base):
    """
    Реализация модели.
    Хранит в себе свой id, дату создания записи, дату обновления записи, id студента, id занятия, комментарий.
    Имеет связь с базами данных студентов и занятий.
    """

    # Столбцы модели
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"))
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id", ondelete="CASCADE"))
    data: Mapped[str] = mapped_column(String(4096))

    # Связь с занятием в календаре (One-to-One)
    lesson: Mapped["Lesson"] = relationship(back_populates="comments")
    # Связь со студентом (One-to-One)
    student: Mapped["Student"] = relationship(back_populates="comments")
