"""Immutable classroom templates and append-only journal activity."""
from sqlalchemy import Boolean, CheckConstraint, ForeignKey, String, Text, UniqueConstraint, true
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base
from app.models.education import UTCDateTime, utc_now
from datetime import datetime


class Classroom(Base):
    __tablename__ = 'classrooms'
    name: Mapped[str] = mapped_column(String(128), unique=True)


class SeatingLayout(Base):
    __tablename__ = 'seating_layouts'
    __table_args__ = (UniqueConstraint('room_id', 'revision'), CheckConstraint('revision > 0'))
    room_id: Mapped[int] = mapped_column(ForeignKey('classrooms.id', ondelete='RESTRICT'))
    name: Mapped[str] = mapped_column(String(128))
    revision: Mapped[int]
    sealed: Mapped[bool] = mapped_column(Boolean, default=False, server_default=true())


class Seat(Base):
    __tablename__ = 'seats'
    __table_args__ = (UniqueConstraint('layout_id', 'label'), CheckConstraint('x >= 0 AND y >= 0 AND x <= 10000 AND y <= 10000'))
    layout_id: Mapped[int] = mapped_column(ForeignKey('seating_layouts.id', ondelete='RESTRICT'))
    label: Mapped[str] = mapped_column(String(64))
    x: Mapped[float]
    y: Mapped[float]


class LessonLayout(Base):
    __tablename__ = 'lesson_layouts'
    lesson_id: Mapped[int] = mapped_column(ForeignKey('lessons.id', ondelete='RESTRICT'), unique=True)
    layout_id: Mapped[int] = mapped_column(ForeignKey('seating_layouts.id', ondelete='RESTRICT'))


class SeatAssignment(Base):
    __tablename__ = 'seat_assignments'
    lesson_id: Mapped[int] = mapped_column(ForeignKey('lessons.id', ondelete='RESTRICT'))
    student_id: Mapped[int] = mapped_column(ForeignKey('students.id', ondelete='RESTRICT'))
    seat_id: Mapped[int | None] = mapped_column(ForeignKey('seats.id', ondelete='RESTRICT'))
    previous_id: Mapped[int | None] = mapped_column(ForeignKey('seat_assignments.id', ondelete='RESTRICT'), unique=True)
    reason: Mapped[str] = mapped_column(Text)
    operation_key: Mapped[str] = mapped_column(String(64), unique=True)
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)


class BehaviorCategory(Base):
    __tablename__ = 'behavior_categories'
    __table_args__ = (CheckConstraint("polarity IN ('positive','negative')"),)
    name: Mapped[str] = mapped_column(String(128), unique=True)
    polarity: Mapped[str] = mapped_column(String(16))


class BehaviorEvent(Base):
    __tablename__ = 'behavior_events'
    student_id: Mapped[int] = mapped_column(ForeignKey('students.id', ondelete='RESTRICT'))
    lesson_id: Mapped[int] = mapped_column(ForeignKey('lessons.id', ondelete='RESTRICT'))
    category_id: Mapped[int] = mapped_column(ForeignKey('behavior_categories.id', ondelete='RESTRICT'))
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    comment: Mapped[str] = mapped_column(Text, default='')
    source: Mapped[str] = mapped_column(String(128))
    operation_key: Mapped[str] = mapped_column(String(64), unique=True)


class BehaviorCorrection(Base):
    __tablename__ = 'behavior_corrections'
    event_id: Mapped[int] = mapped_column(ForeignKey('behavior_events.id', ondelete='RESTRICT'))
    student_id: Mapped[int] = mapped_column(ForeignKey('students.id', ondelete='RESTRICT'))
    reason: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(128))
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
