"""Time-bounded membership of one student in a group."""

from datetime import date

from sqlalchemy import CheckConstraint, Date, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class GroupMembership(Base):
    __table_args__ = (
        CheckConstraint(
            "end_date IS NULL OR end_date >= start_date",
            name="ck_group_membership_period",
        ),
    )

    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="RESTRICT"))
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id", ondelete="RESTRICT"))
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    origin: Mapped[str] = mapped_column(String(24), default="recorded")
    known_from: Mapped[date] = mapped_column(Date)

    student: Mapped["Student"] = relationship(back_populates="memberships")
    group: Mapped["Group"] = relationship(back_populates="memberships")
