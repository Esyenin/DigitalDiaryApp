# schedule_group_link.py
"""Ассоциативная модель для связи Групп и Расписания."""
# pylint: disable=unsubscriptable-object

from datetime import datetime
from typing import Optional

from sqlalchemy import ForeignKey, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship, Session

from app.database import Base, get_session


class ScheduleGroupLink(Base):
    """Реализация модели."""
    __tablename__ = "schedule_group_links"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"), nullable=False, index=True)
    schedule_id: Mapped[int] = mapped_column(ForeignKey("schedules.id", ondelete="CASCADE"), nullable=False, index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, server_default=func.now())

    group: Mapped["Group"] = relationship(back_populates="schedule_links")
    schedule: Mapped["Schedule"] = relationship(back_populates="group_links")


class ScheduleGroupLinkCRUD:
    """CRUD для ScheduleGroupLink"""

    @staticmethod
    def crud_schedule_group_links(action: str, link_id: Optional[int] = None, group_id: Optional[int] = None, schedule_id: Optional[int] = None, session: Optional[Session] = None):
        close_session = False
        if session is None:
            session = next(get_session())
            close_session = True
        try:
            from sqlalchemy import select
            if action == "create":
                if not all([group_id, schedule_id]): raise ValueError("Нужно: group_id, schedule_id")
                link = ScheduleGroupLink(group_id=group_id, schedule_id=schedule_id)
                session.add(link)
                session.commit()
                session.refresh(link)
                return link
            elif action == "read":
                if link_id:
                    result = session.execute(select(ScheduleGroupLink).where(ScheduleGroupLink.id == link_id))
                    return result.scalar_one_or_none()
                return list(session.execute(select(ScheduleGroupLink)).scalars().all())
            elif action == "update":
                if not link_id: raise ValueError("Нужно: link_id")
                result = session.execute(select(ScheduleGroupLink).where(ScheduleGroupLink.id == link_id))
                link = result.scalar_one_or_none()
                if link:
                    if group_id: link.group_id = group_id
                    if schedule_id: link.schedule_id = schedule_id
                    link.updated_at = datetime.utcnow()
                    session.commit()
                    session.refresh(link)
                return link
            elif action == "delete":
                if not link_id: raise ValueError("Нужно: link_id")
                result = session.execute(select(ScheduleGroupLink).where(ScheduleGroupLink.id == link_id))
                link = result.scalar_one_or_none()
                if link:
                    session.delete(link)
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