"""
Модель посещения конкретных занятий в течение года студентами
"""
# pylint: disable=unsubscriptable-object
from sqlalchemy import Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base


class Attendance(Base):
    """
    Реализация модели.
    Хранит в себе свой id, дату создания записи, дату обновления записи, id студента, id занятия, посетил/не посетил.
    Имеет связь с базами данных студентов и занятий.
    """
    # Столбцы модели
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"))
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id", ondelete="CASCADE"))
    is_visited: Mapped[bool] = mapped_column(Boolean, default=False)

    # Связь с занятием в календаре (One-to-One)
    lesson: Mapped["Lesson"] = relationship(back_populates="attendances")
    # Связь со студентом (One-to-One)
    student: Mapped["Student"] = relationship(back_populates="attendances")
