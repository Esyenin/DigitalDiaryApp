"""
Модель студентов.
"""
from typing import List, Optional
from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from ..database import Base


class Student(Base):
    """
    Реализация модели.
    Хранит в себе свой id, дату создания записи, дату обновления записи, id группы, фамилию, имя, отчество,
    номер зачетки, корпоративную почту.
    Имеет связь с базами данных групп и занятий в расписании.
    """

    # Столбцы модели
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"))
    surname: Mapped[str] = mapped_column(String(128))
    first_name: Mapped[str] = mapped_column(String(128))
    patronymic: Mapped[Optional[str]] = mapped_column(String(128))
    personal_data: Mapped[Optional[str]] = mapped_column(String(16))
    bmstu_email: Mapped[Optional[str]] = mapped_column(String(128))

    # Связь с группой (One-to-One)
    group: Mapped["Group"] = relationship(back_populates="students")
    # Связи с посещенными занятиями (One-to-Many)
    attendances: Mapped[List["Attendance"]] = relationship(back_populates="student", cascade="all, delete")
    # Связи с полученными оценками (One-to-Many)
    marks: Mapped[List["Mark"]] = relationship(back_populates="student", cascade="all, delete")
    # Связи с полученными комментариями (One-to-Many)
    comments: Mapped[List["Comment"]] = relationship(back_populates="student", cascade="all, delete")
