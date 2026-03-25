"""
Модель группы студентов. Является core-моделью.
"""
from typing import List, Optional
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from ..database import Base


class Group(Base):
    """
    Реализация модели.
    Хранит в себе свой id, дату создания записи, дату обновления записи, название группы, специальность.
    Имеет связь с базами данных студентов и занятий в расписании.
    """

    # Столбцы модели
    name: Mapped[str] = mapped_column(String(16))
    speciality: Mapped[Optional[str]] = mapped_column(String(128))

    # Связи с занятиями в расписании (One-to-Many)
    schedule_links: Mapped[List["ScheduleGroupLink"]] = relationship(back_populates="group",
                                                                     cascade="all, delete-orphan")
    # Связи со студентами (One-to-Many)
    students: Mapped[List["Student"]] = relationship(back_populates="group", cascade="all, delete-orphan")
