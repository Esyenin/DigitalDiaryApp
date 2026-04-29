"""
Ассоциативная модель для связи Групп и Расписания.
"""
from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base


class ScheduleGroupLink(Base):
    """
    Реализация модели.
    Хранит в себе свой id, дату создания записи, дату обновления записи, id группы, id занятия в расписании.
    Имеет связь с базами данных групп и занятий в расписании.
    """

    __table_args__ = (
        UniqueConstraint("group_id", "schedule_id", name="uq_schedule_group_link"),
    )

    # Столбцы модели
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"))
    schedule_id: Mapped[int] = mapped_column(ForeignKey("schedules.id", ondelete="CASCADE"))

    # Связь с группой (Many-to-One)
    group: Mapped["Group"] = relationship(back_populates="schedule_links")
    # Связь с занятием в расписании (Many-to-One)
    schedule: Mapped["Schedule"] = relationship(back_populates="group_links")
