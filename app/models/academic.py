"""Academic context; legacy lessons remain explicitly unassigned."""

from datetime import date

from sqlalchemy import CheckConstraint, Date, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AcademicYear(Base):
    __tablename__ = "academic_years"
    __table_args__ = (CheckConstraint("end_date > start_date"),)

    name: Mapped[str] = mapped_column(String(128), unique=True)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)


class AcademicTerm(Base):
    __tablename__ = "academic_terms"
    __table_args__ = (
        UniqueConstraint("year_id", "name"),
        CheckConstraint("total_weeks BETWEEN 1 AND 52"),
        CheckConstraint("status IN ('open', 'closed')"),
    )

    year_id: Mapped[int] = mapped_column(ForeignKey("academic_years.id", ondelete="RESTRICT"))
    name: Mapped[str] = mapped_column(String(128))
    start_date: Mapped[date] = mapped_column(Date)
    total_weeks: Mapped[int]
    status: Mapped[str] = mapped_column(String(16), default="open", server_default="open")
    origin: Mapped[str] = mapped_column(String(32), default="recorded", server_default="recorded")


class Discipline(Base):
    __tablename__ = "disciplines"
    name: Mapped[str] = mapped_column(String(256), unique=True)


class CourseOffering(Base):
    __tablename__ = "course_offerings"
    __table_args__ = (UniqueConstraint("term_id", "discipline_id", "name"),)

    term_id: Mapped[int] = mapped_column(ForeignKey("academic_terms.id", ondelete="RESTRICT"))
    discipline_id: Mapped[int] = mapped_column(ForeignKey("disciplines.id", ondelete="RESTRICT"))
    name: Mapped[str] = mapped_column(String(128))


class CourseOfferingGroup(Base):
    __tablename__ = "course_offering_groups"
    __table_args__ = (UniqueConstraint("offering_id", "group_id"),)

    offering_id: Mapped[int] = mapped_column(ForeignKey("course_offerings.id", ondelete="RESTRICT"))
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id", ondelete="RESTRICT"))


class TeachingModule(Base):
    __tablename__ = "teaching_modules"
    __table_args__ = (
        UniqueConstraint("offering_id", "position"),
        CheckConstraint("position > 0"),
        CheckConstraint("end_date > start_date"),
    )

    offering_id: Mapped[int] = mapped_column(ForeignKey("course_offerings.id", ondelete="RESTRICT"))
    name: Mapped[str] = mapped_column(String(128))
    position: Mapped[int]
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)


class AcademicSelection(Base):
    __tablename__ = "academic_selection"
    __table_args__ = (CheckConstraint("id = 1"),)

    term_id: Mapped[int] = mapped_column(ForeignKey("academic_terms.id", ondelete="RESTRICT"))
