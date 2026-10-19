"""
Модель конкретных занятий в течение года.
"""
from datetime import date
from typing import List, Optional
from sqlalchemy import Boolean, Date, ForeignKey, String, UniqueConstraint, false
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base


MAX_LEN = {
    "topic": 512
}


class Lesson(Base):
    """
    Реализация модели.
    Хранит в себе свой id, дату создания записи, дату обновления записи, id занятия в расписания, тему, дату.
    Имеет связь с базами данных занятий в расписании, посещений, оценок и комментариев.
    """

    __table_args__ = (
        UniqueConstraint("schedule_id", "date", name="uq_lesson_schedule_date"),
    )

    # Столбцы модели
    schedule_id: Mapped[int] = mapped_column(ForeignKey("schedules.id", ondelete="CASCADE"))
    topic: Mapped[Optional[str]] = mapped_column(String(MAX_LEN["topic"]))
    date: Mapped[date] = mapped_column(Date)
    participants_complete: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    roster_origin: Mapped[str] = mapped_column(String(24), default="unfixed", server_default="unfixed")

    # Связь с занятием в расписании (Many-to-One)
    schedule: Mapped["Schedule"] = relationship(back_populates="lessons")
    # Связи с посещениями студентов (One-to-Many)
    attendances: Mapped[List["Attendance"]] = relationship(
        back_populates="lesson",
        cascade="all, delete",
    )
    # Связи с оценками студентов (One-to-Many)
    marks: Mapped[List["Mark"]] = relationship(
        back_populates="lesson",
        cascade="all, delete",
    )
    # Связи с комментариями к студентам (One-to-Many)
    comments: Mapped[List["Comment"]] = relationship(
        back_populates="lesson",
        cascade="all, delete",
    )
    participants: Mapped[List["LessonParticipant"]] = relationship(back_populates="lesson")
