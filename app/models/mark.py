"""
Модель оценок студентов за занятие.
"""
from sqlalchemy import ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base


class Mark(Base):
    """
    Реализация модели.
    Хранит в себе свой id, дату создания записи, дату обновления записи, id студента, id занятия, оценку.
    Имеет связь с базами данных занятий и студентов.
    """

    # Столбцы модели
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"))
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id", ondelete="CASCADE"))
    data: Mapped[int] = mapped_column(Integer)

    # Связь с занятием в календаре (One-to-One)
    lesson: Mapped["Lesson"] = relationship(back_populates="marks")
    # Связь со студентом (One-to-One)
    student: Mapped["Student"] = relationship(back_populates="marks")
