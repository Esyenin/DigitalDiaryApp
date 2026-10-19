"""
Модель группы студентов. Является core-моделью.
"""
from typing import List, Optional
from sqlalchemy import String, false
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base

MAX_LEN = {
    "name": 16,
    "speciality": 128
}

class Group(Base):
    """
    Реализация модели.
    Хранит в себе свой id, дату создания записи, дату обновления записи, название группы, специальность.
    Имеет связь с базами данных студентов и занятий в расписании.
    """

    # Столбцы модели
    name: Mapped[str] = mapped_column(String(MAX_LEN["name"]), unique=True)
    speciality: Mapped[Optional[str]] = mapped_column(String(MAX_LEN["speciality"]))
    is_archived: Mapped[bool] = mapped_column(default=False, server_default=false())
    archive_reason: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # Связи с занятиями в расписании (One-to-Many)
    schedule_links: Mapped[List["ScheduleGroupLink"]] = relationship(
        back_populates="group",
        cascade="all, delete-orphan",
    )
    # Связи со студентами (One-to-Many)
    students: Mapped[List["Student"]] = relationship(
        back_populates="group",
        cascade="all, delete-orphan",
    )
    memberships: Mapped[List["GroupMembership"]] = relationship(back_populates="group")
