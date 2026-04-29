"""
Модель студентов.
"""
from typing import List, Optional
from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base


MAX_LEN = {
    "surname": 128,
    "first_name": 128,
    "patronymic": 128,
    "personal_data": 16,
    "bmstu_email": 128
}


class Student(Base):
    """
    Реализация модели.
    Хранит в себе свой id, дату создания записи, дату обновления записи, id группы, фамилию, имя, отчество,
    номер зачетки, корпоративную почту.
    Имеет связь с базами данных групп и занятий в расписании.
    """

    # Столбцы модели
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"))
    surname: Mapped[str] = mapped_column(String(MAX_LEN["surname"]))
    first_name: Mapped[str] = mapped_column(String(MAX_LEN["first_name"]))
    patronymic: Mapped[Optional[str]] = mapped_column(String(MAX_LEN["patronymic"]))
    personal_data: Mapped[Optional[str]] = mapped_column(String(MAX_LEN["personal_data"]))
    bmstu_email: Mapped[Optional[str]] = mapped_column(String(MAX_LEN["bmstu_email"]))

    # Связь с группой (Many-to-One)
    group: Mapped["Group"] = relationship(back_populates="students")
    # Связи с посещенными занятиями (One-to-Many)
    attendances: Mapped[List["Attendance"]] = relationship(
        back_populates="student",
        cascade="all, delete",
    )
    # Связи с полученными оценками (One-to-Many)
    marks: Mapped[List["Mark"]] = relationship(
        back_populates="student",
        cascade="all, delete",
    )
    # Связи с полученными комментариями (One-to-Many)
    comments: Mapped[List["Comment"]] = relationship(
        back_populates="student",
        cascade="all, delete",
    )
