# mark.py
"""Модель оценок."""
# pylint: disable=unsubscriptable-object

from datetime import datetime
from typing import Optional

from sqlalchemy import ForeignKey, Integer, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship, Session

from app.database import Base, get_session


class Mark(Base):
    """Реализация модели."""
    __tablename__ = "marks"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False, index=True)
    data: Mapped[int] = mapped_column(Integer, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, server_default=func.now())

    student: Mapped["Student"] = relationship(back_populates="marks")
    lesson: Mapped["Lesson"] = relationship(back_populates="marks")


class MarkCRUD:
    """CRUD для Mark"""

    @staticmethod
    def crud_marks(action: str, mark_id: Optional[int] = None, student_id: Optional[int] = None, lesson_id: Optional[int] = None, data: Optional[int] = None, session: Optional[Session] = None):
        close_session = False
        if session is None:
            session = next(get_session())
            close_session = True
        try:
            from sqlalchemy import select
            if action == "create":
                if not all([student_id, lesson_id, data]): raise ValueError("Нужно: student_id, lesson_id, data")
                mark = Mark(student_id=student_id, lesson_id=lesson_id, data=data)
                session.add(mark)
                session.commit()
                session.refresh(mark)
                return mark
            elif action == "read":
                if mark_id:
                    result = session.execute(select(Mark).where(Mark.id == mark_id))
                    return result.scalar_one_or_none()
                elif student_id:
                    result = session.execute(select(Mark).where(Mark.student_id == student_id))
                    return list(result.scalars().all())
                elif lesson_id:
                    result = session.execute(select(Mark).where(Mark.lesson_id == lesson_id))
                    return list(result.scalars().all())
                return list(session.execute(select(Mark)).scalars().all())
            elif action == "update":
                if not mark_id: raise ValueError("Нужно: mark_id")
                result = session.execute(select(Mark).where(Mark.id == mark_id))
                mark = result.scalar_one_or_none()
                if mark:
                    if data is not None: mark.data = data
                    mark.updated_at = datetime.utcnow()
                    session.commit()
                    session.refresh(mark)
                return mark
            elif action == "delete":
                if not mark_id: raise ValueError("Нужно: mark_id")
                result = session.execute(select(Mark).where(Mark.id == mark_id))
                mark = result.scalar_one_or_none()
                if mark:
                    session.delete(mark)
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