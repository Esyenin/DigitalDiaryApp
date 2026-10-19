"""
Модель занятий в расписании.
"""
from datetime import date, time
from typing import List
from uuid import uuid4
from sqlalchemy import Boolean, CheckConstraint, Date, Integer, String, Time, UniqueConstraint, false
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base


MAX_LEN = {
    "odd_or_even": 16,
    "type": 64,
    "day": 16
}


class Schedule(Base):
    """
    Реализация модели.
    Хранит в себе свой id, дату создания записи, дату обновления записи, четная/не четная неделя, тип занятия,
    оценочное/не оценочное, день недели, время занятия.
    Имеет связь с базами данных групп и занятий.
    """

    __table_args__ = (
        UniqueConstraint("series_key", "revision", name="uq_schedule_series_revision"),
        CheckConstraint(
            "effective_until IS NULL OR effective_until > effective_from",
            name="ck_schedule_effective_period",
        ),
        CheckConstraint("revision >= 1", name="ck_schedule_revision_positive"),
    )

    # Столбцы модели
    series_key: Mapped[str] = mapped_column(String(36), default=lambda: str(uuid4()))
    revision: Mapped[int] = mapped_column(Integer, default=1)
    effective_from: Mapped[date] = mapped_column(Date, default=date(1900, 1, 1))
    effective_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    odd_or_even: Mapped[str] = mapped_column(String(MAX_LEN["odd_or_even"]))
    type: Mapped[str] = mapped_column(String(MAX_LEN["type"]))
    is_assessment: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    day: Mapped[str] = mapped_column(String(MAX_LEN["day"]))
    time: Mapped[time] = mapped_column(Time)

    # Связи с группами на занятии (One-to-Many)
    group_links: Mapped[List["ScheduleGroupLink"]] = relationship(
        back_populates="schedule",
        cascade="all, delete-orphan",
    )
    # Связи с занятиями в календаре (One-to-Many)
    lessons: Mapped[List["Lesson"]] = relationship(
        back_populates="schedule",
        cascade="all, delete-orphan",
    )
