# comment.py
"""Модель комментариев."""
# pylint: disable=unsubscriptable-object

from datetime import datetime
from typing import Optional, Literal, Any

from sqlalchemy import ForeignKey, String, DateTime, func, select
from sqlalchemy.orm import Mapped, mapped_column, relationship, Session

from app.database import Base, get_session


class Comment(Base):
    """Реализация модели."""
    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False, index=True)
    data: Mapped[str] = mapped_column(String(4096), nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, server_default=func.now())

    student: Mapped["Student"] = relationship(back_populates="comments")
    lesson: Mapped["Lesson"] = relationship(back_populates="comments")


class CommentCRUD:
    """CRUD для Comment"""

    @staticmethod
    def crud_comments(action: Literal["create", "read", "update", "delete"], comment_id: Optional[int] = None, student_id: Optional[int] = None, lesson_id: Optional[int] = None, data: Optional[str] = None, session: Optional[Session] = None) -> Any:
        close_session = False
        if session is None:
            session = next(get_session())
            close_session = True
        try:
            if action == "create":
                if not all([student_id, lesson_id, data]): raise ValueError("Нужно: student_id, lesson_id, data")
                comment = Comment(student_id=student_id, lesson_id=lesson_id, data=data)
                session.add(comment)
                session.commit()
                session.refresh(comment)
                return comment
            elif action == "read":
                if comment_id:
                    result = session.execute(select(Comment).where(Comment.id == comment_id))
                    return result.scalar_one_or_none()
                elif student_id:
                    result = session.execute(select(Comment).where(Comment.student_id == student_id))
                    return list(result.scalars().all())
                elif lesson_id:
                    result = session.execute(select(Comment).where(Comment.lesson_id == lesson_id))
                    return list(result.scalars().all())
                return list(session.execute(select(Comment)).scalars().all())
            elif action == "update":
                if not all([comment_id, data]): raise ValueError("Нужно: comment_id, data")
                result = session.execute(select(Comment).where(Comment.id == comment_id))
                comment = result.scalar_one_or_none()
                if comment:
                    comment.data = data
                    comment.updated_at = datetime.utcnow()
                    session.commit()
                    session.refresh(comment)
                return comment
            elif action == "delete":
                if not comment_id: raise ValueError("Нужно: comment_id")
                result = session.execute(select(Comment).where(Comment.id == comment_id))
                comment = result.scalar_one_or_none()
                if comment:
                    session.delete(comment)
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