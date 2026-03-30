# lesson.py
"""Модель конкретных занятий."""
# pylint: disable=unsubscriptable-object

from datetime import datetime, date
from typing import List, Optional

from sqlalchemy import Date, ForeignKey, String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship, Session

from app.database import Base, get_session


class Lesson(Base):
    """Реализация модели."""
    __tablename__ = "lessons"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    schedule_id: Mapped[int] = mapped_column(ForeignKey("schedules.id", ondelete="CASCADE"), nullable=False, index=True)
    topic: Mapped[Optional[str]] = mapped_column(String(512))
    date: Mapped[date] = mapped_column(Date, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, server_default=func.now())

    schedule: Mapped["Schedule"] = relationship(back_populates="lessons")
    attendances: Mapped[List["Attendance"]] = relationship(back_populates="lesson", cascade="all, delete")
    marks: Mapped[List["Mark"]] = relationship(back_populates="lesson", cascade="all, delete")
    comments: Mapped[List["Comment"]] = relationship(back_populates="lesson", cascade="all, delete")


class LessonCRUD:
    """CRUD для Lesson"""

    @staticmethod
    def crud_lessons(action: str, lesson_id: Optional[int] = None, schedule_id: Optional[int] = None, topic: Optional[str] = None, date: Optional[date] = None, session: Optional[Session] = None):
        close_session = False
        if session is None:
            session = next(get_session())
            close_session = True
        try:
            from sqlalchemy import select
            if action == "create":
                if not all([schedule_id, date]): raise ValueError("Нужно: schedule_id, date")
                lesson = Lesson(schedule_id=schedule_id, topic=topic, date=date)
                session.add(lesson)
                session.commit()
                session.refresh(lesson)
                return lesson
            elif action == "read":
                if lesson_id:
                    result = session.execute(select(Lesson).where(Lesson.id == lesson_id))
                    return result.scalar_one_or_none()
                return list(session.execute(select(Lesson)).scalars().all())
            elif action == "update":
                if not lesson_id: raise ValueError("Нужно: lesson_id")
                result = session.execute(select(Lesson).where(Lesson.id == lesson_id))
                lesson = result.scalar_one_or_none()
                if lesson:
                    if schedule_id: lesson.schedule_id = schedule_id
                    if topic: lesson.topic = topic
                    if date: lesson.date = date
                    lesson.updated_at = datetime.utcnow()
                    session.commit()
                    session.refresh(lesson)
                return lesson
            elif action == "delete":
                if not lesson_id: raise ValueError("Нужно: lesson_id")
                result = session.execute(select(Lesson).where(Lesson.id == lesson_id))
                lesson = result.scalar_one_or_none()
                if lesson:
                    session.delete(lesson)
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