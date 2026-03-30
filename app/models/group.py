# group.py
"""Модель группы студентов."""
# pylint: disable=unsubscriptable-object

from datetime import datetime
from typing import List, Optional

from sqlalchemy import String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship, Session

from app.database import Base, get_session


class Group(Base):
    """Реализация модели."""
    __tablename__ = "groups"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(16), nullable=False)
    speciality: Mapped[Optional[str]] = mapped_column(String(128))

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, server_default=func.now())

    schedule_links: Mapped[List["ScheduleGroupLink"]] = relationship(back_populates="group", cascade="all, delete-orphan")
    students: Mapped[List["Student"]] = relationship(back_populates="group", cascade="all, delete-orphan")


class GroupCRUD:
    """CRUD для Group"""

    @staticmethod
    def crud_groups(action: str, group_id: Optional[int] = None, name: Optional[str] = None, speciality: Optional[str] = None, session: Optional[Session] = None):
        close_session = False
        if session is None:
            session = next(get_session())
            close_session = True
        try:
            from sqlalchemy import select
            if action == "create":
                if not name: raise ValueError("Нужно: name")
                group = Group(name=name, speciality=speciality)
                session.add(group)
                session.commit()
                session.refresh(group)
                return group
            elif action == "read":
                if group_id:
                    result = session.execute(select(Group).where(Group.id == group_id))
                    return result.scalar_one_or_none()
                return list(session.execute(select(Group)).scalars().all())
            elif action == "update":
                if not group_id: raise ValueError("Нужно: group_id")
                result = session.execute(select(Group).where(Group.id == group_id))
                group = result.scalar_one_or_none()
                if group:
                    if name: group.name = name
                    if speciality: group.speciality = speciality
                    group.updated_at = datetime.utcnow()
                    session.commit()
                    session.refresh(group)
                return group
            elif action == "delete":
                if not group_id: raise ValueError("Нужно: group_id")
                result = session.execute(select(Group).where(Group.id == group_id))
                group = result.scalar_one_or_none()
                if group:
                    session.delete(group)
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