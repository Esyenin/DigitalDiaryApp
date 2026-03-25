"""
Ассоциативная модель для связи Групп и Расписания.
"""
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from ..database import Base


class ScheduleGroupLink(Base):
    """
    Реализация модели.
    Хранит в себе свой id, дату создания записи, дату обновления записи, id группы, id занятия в расписании.
    Имеет связь с базами данных групп и занятий в расписании.
    """

    # Столбцы модели
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"))
    schedule_id: Mapped[int] = mapped_column(ForeignKey("schedules.id", ondelete="CASCADE"))

    # Связь с группой (One-to-One)
    group: Mapped["Group"] = relationship(back_populates="schedule_links")
    # Связь с занятием в расписании (One-to-One)
    schedule: Mapped["Schedule"] = relationship(back_populates="group_links")
