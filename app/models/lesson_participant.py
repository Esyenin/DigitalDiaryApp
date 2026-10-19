"""Proven or frozen participation in a particular lesson."""

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class LessonParticipant(Base):
    __table_args__ = (
        UniqueConstraint("lesson_id", "student_id", name="uq_lesson_participant"),
    )

    lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id", ondelete="RESTRICT"))
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="RESTRICT"))
    group_id: Mapped[int | None] = mapped_column(ForeignKey("groups.id", ondelete="RESTRICT"), nullable=True)
    source: Mapped[str] = mapped_column(String(24), default="snapshot")

    lesson: Mapped["Lesson"] = relationship(back_populates="participants")
    student: Mapped["Student"] = relationship(back_populates="lesson_participations")
