"""
Реализация архитектуры базы данных для приложения (электронный дневник).
Используется SQLAlchemy 2.0 с декларативным стилем описания моделей.
Подробное описание моделей и их связи смотри в pdf-диаграмме.
"""
from datetime import datetime
from typing import List, Optional
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Time,
    func
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    declared_attr,
    mapped_column,
    relationship
)
from config import settings


# URL-адрес базы данных
DATABASE_URL = settings.get_db_url()


class Base(DeclarativeBase):
    """
    Абстрактный базовый класс.
    Содержит общие поля (id, даты создания и обновления) и логику именования таблиц.
    """

    # Абстрактность
    __abstract__ = True

    # Базовые столбцы модели
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    @declared_attr.directive
    def __tablename__(self) -> str:
        """Автоматическое именование таблиц во множественном числе (добавление 's')."""
        return self.__name__.lower() + 's'

    def __repr__(self) -> str:
        """Автоматическое текстовое представление всех моделей."""
        cols = []
        for col in self.__table__.columns.keys():
            cols.append(f"{col}={getattr(self, col)}")
        return f"<{self.__class__.__name__}({', '.join(cols[:4])})>"


class Group(Base):
    """Модель учебной группы."""

    # Столбцы модели
    name: Mapped[str] = mapped_column(String(16))
    speciality: Mapped[Optional[str]] = mapped_column(String(128))

    # Связи с занятиями в расписании (One-to-Many)
    schedule_links: Mapped[List["ScheduleGroupLink"]] = relationship(back_populates="group",
                                                                     cascade="all, delete-orphan")
    # Связи со студентами (One-to-Many)
    students: Mapped[List["Student"]] = relationship(back_populates="group", cascade="all, delete-orphan")


class Student(Base):
    """Модель студента."""

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


class ScheduleGroupLink(Base):
    """Ассоциативная модель для связи Групп и Расписания."""

    # Столбцы модели
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"))
    schedule_id: Mapped[int] = mapped_column(ForeignKey("schedules.id", ondelete="CASCADE"))

    # Связь с группой (One-to-One)
    group: Mapped["Group"] = relationship(back_populates="schedule_links")
    # Связь с занятием в расписании (One-to-One)
    schedule: Mapped["Schedule"] = relationship(back_populates="group_links")


class Schedule(Base):
    """Модель правила расписания (шаблон занятия)."""

    # Столбцы модели
    odd_or_even: Mapped[str] = mapped_column(String(16))
    day: Mapped[datetime] = mapped_column(DateTime)
    time: Mapped[datetime] = mapped_column(Time)

    # Связи с группами на занятии (One-to-Many)
    group_links: Mapped[List["ScheduleGroupLink"]] = relationship(back_populates="schedule",
                                                                  cascade="all, delete-orphan")
    # Связи с занятиями в календаре (One-to-Many)
    lessons: Mapped[List["Lesson"]] = relationship(back_populates="schedule", cascade="all, delete-orphan")


class Lesson(Base):
    """Модель конкретного занятия в течение года"""

    # Столбцы модели
    schedule_id: Mapped[int] = mapped_column(ForeignKey("schedules.id"))
    type: Mapped[str] = mapped_column(String(64))
    topic: Mapped[Optional[str]] = mapped_column(String(512))
    is_assessment: Mapped[bool] = mapped_column(Boolean, default=False)
    date: Mapped[datetime] = mapped_column(DateTime)

    # Связь с занятием в расписании (One-to-One)
    schedule: Mapped["Schedule"] = relationship(back_populates="lessons")
    # Связи с посещениями студентов (One-to-Many)
    attendances: Mapped[List["Attendance"]] = relationship(back_populates="lesson", cascade="all, delete")
    # Связи с оценками студентов (One-to-Many)
    marks: Mapped[List["Mark"]] = relationship(back_populates="lesson", cascade="all, delete")
    # Связи с комментариями к студентам (One-to-Many)
    comments: Mapped[List["Comment"]] = relationship(back_populates="lesson", cascade="all, delete")


class Attendance(Base):
    """Модель посещения занятий"""

    # Столбцы модели
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"))
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id", ondelete="CASCADE"))
    is_visited: Mapped[bool] = mapped_column(Boolean, default=True)

    # Связь с занятием в календаре (One-to-One)
    lesson: Mapped["Lesson"] = relationship(back_populates="attendances")
    # Связь со студентом (One-to-One)
    student: Mapped["Student"] = relationship(back_populates="attendances")


class Mark(Base):
    """Модель отметок за занятия"""

    # Столбцы модели
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"))
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id", ondelete="CASCADE"))
    data: Mapped[int] = mapped_column(Integer)

    # Связь с занятием в календаре (One-to-One)
    lesson: Mapped["Lesson"] = relationship(back_populates="marks")
    # Связь со студентом (One-to-One)
    student: Mapped["Student"] = relationship(back_populates="marks")


class Comment(Base):
    """Модель комментариев для ученика за занятие"""

    # Столбцы модели
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"))
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id", ondelete="CASCADE"))
    data: Mapped[str] = mapped_column(String(4096))

    # Связь с занятием в календаре (One-to-One)
    lesson: Mapped["Lesson"] = relationship(back_populates="comments")
    # Связь со студентом (One-to-One)
    student: Mapped["Student"] = relationship(back_populates="comments")
