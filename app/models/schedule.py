# schedule.py
"""Модель занятий в расписании."""
# pylint: disable=unsubscriptable-object

from datetime import datetime, time
from typing import List, Optional

from sqlalchemy import Boolean, String, Time, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship, Session

from app.database import Base, get_session


class Schedule(Base):
    """Реализация модели."""
    __tablename__ = "schedules"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    odd_or_even: Mapped[str] = mapped_column(String(16), nullable=False)
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    is_assessment: Mapped[bool] = mapped_column(Boolean, default=False)
    day: Mapped[str] = mapped_column(String(16), nullable=False)
    time: Mapped[time] = mapped_column(Time, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, server_default=func.now())

    group_links: Mapped[List["ScheduleGroupLink"]] = relationship(back_populates="schedule", cascade="all, delete-orphan")
    lessons: Mapped[List["Lesson"]] = relationship(back_populates="schedule", cascade="all, delete-orphan")


class ScheduleCRUD:
    """CRUD для Schedule"""

    @staticmethod
    def crud_schedules(action: str, schedule_id: Optional[int] = None, odd_or_even: Optional[str] = None, schedule_type: Optional[str] = None, is_assessment: Optional[bool] = None, day: Optional[str] = None, time: Optional[time] = None, session: Optional[Session] = None):
        close_session = False
        if session is None:
            session = next(get_session())
            close_session = True
        try:
            from sqlalchemy import select
            if action == "create":
                if not all([odd_or_even, schedule_type, day, time]): raise ValueError("Нужно: odd_or_even, schedule_type, day, time")
                schedule = Schedule(odd_or_even=odd_or_even, type=schedule_type, is_assessment=is_assessment or False, day=day, time=time)
                session.add(schedule)
                session.commit()
                session.refresh(schedule)
                return schedule
            elif action == "read":
                if schedule_id:
                    result = session.execute(select(Schedule).where(Schedule.id == schedule_id))
                    return result.scalar_one_or_none()
                return list(session.execute(select(Schedule)).scalars().all())
            elif action == "update":
                if not schedule_id: raise ValueError("Нужно: schedule_id")
                result = session.execute(select(Schedule).where(Schedule.id == schedule_id))
                schedule = result.scalar_one_or_none()
                if schedule:
                    if odd_or_even: schedule.odd_or_even = odd_or_even
                    if schedule_type: schedule.type = schedule_type
                    if is_assessment is not None: schedule.is_assessment = is_assessment
                    if day: schedule.day = day
                    if time: schedule.time = time
                    schedule.updated_at = datetime.utcnow()
                    session.commit()
                    session.refresh(schedule)
                return schedule
            elif action == "delete":
                if not schedule_id: raise ValueError("Нужно: schedule_id")
                result = session.execute(select(Schedule).where(Schedule.id == schedule_id))
                schedule = result.scalar_one_or_none()
                if schedule:
                    session.delete(schedule)
                    session.commit()
                    return True
                return False
            else:
                raise ValueError(f"Неизвестное: {action}")
        except Exception as e:
            session.rollback()
            raise e
        finally:
            if close_session:
                session.close()