# attendance.py
"""Модель посещения занятий."""
# pylint: disable=unsubscriptable-object

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, ForeignKey, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship, Session

from app.database import Base, get_session


class Attendance(Base):
    """Реализация модели."""
    __tablename__ = "attendances"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False, index=True)
    is_visited: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, server_default=func.now())

    student: Mapped["Student"] = relationship(back_populates="attendances")
    lesson: Mapped["Lesson"] = relationship(back_populates="attendances")


class AttendanceCRUD:
    """CRUD для Attendance"""

    @staticmethod
    def crud_attendances(action: str, attendance_id: Optional[int] = None, student_id: Optional[int] = None, lesson_id: Optional[int] = None, is_visited: Optional[bool] = None, session: Optional[Session] = None):
        close_session = False
        if session is None:
            session = next(get_session())
            close_session = True
        try:
            from sqlalchemy import select
            if action == "create":
                if not all([student_id, lesson_id]): raise ValueError("Нужно: student_id, lesson_id")
                attendance = Attendance(student_id=student_id, lesson_id=lesson_id, is_visited=is_visited or False)
                session.add(attendance)
                session.commit()
                session.refresh(attendance)
                return attendance
            elif action == "read":
                if attendance_id:
                    result = session.execute(select(Attendance).where(Attendance.id == attendance_id))
                    return result.scalar_one_or_none()
                elif student_id and lesson_id:
                    result = session.execute(select(Attendance).where(Attendance.student_id == student_id, Attendance.lesson_id == lesson_id))
                    return list(result.scalars().all())
                elif student_id:
                    result = session.execute(select(Attendance).where(Attendance.student_id == student_id))
                    return list(result.scalars().all())
                elif lesson_id:
                    result = session.execute(select(Attendance).where(Attendance.lesson_id == lesson_id))
                    return list(result.scalars().all())
                return list(session.execute(select(Attendance)).scalars().all())
            elif action == "update":
                if not attendance_id: raise ValueError("Нужно: attendance_id")
                result = session.execute(select(Attendance).where(Attendance.id == attendance_id))
                attendance = result.scalar_one_or_none()
                if attendance:
                    if is_visited is not None: attendance.is_visited = is_visited
                    attendance.updated_at = datetime.utcnow()
                    session.commit()
                    session.refresh(attendance)
                return attendance
            elif action == "delete":
                if not attendance_id: raise ValueError("Нужно: attendance_id")
                result = session.execute(select(Attendance).where(Attendance.id == attendance_id))
                attendance = result.scalar_one_or_none()
                if attendance:
                    session.delete(attendance)
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