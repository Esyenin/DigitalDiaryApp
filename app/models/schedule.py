"""
Модель занятий в расписании.
"""
from datetime import time
from typing import List
from sqlalchemy import Boolean, String, Time, false
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

    # Столбцы модели
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
