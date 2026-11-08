"""Normalized teaching records. Attempts and corrections are append-only."""

from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import (Boolean, CheckConstraint, Date, DateTime, ForeignKey,
                        Numeric, String, Text, UniqueConstraint, false)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import TypeDecorator

from app.models.base import Base


class UTCDateTime(TypeDecorator):
    """Aware UTC in Python and PostgreSQL; naive UTC on SQLite disk."""
    impl = DateTime
    cache_ok = True

    def load_dialect_impl(self, dialect):
        return dialect.type_descriptor(DateTime(timezone=dialect.name == "postgresql"))

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("An explicit timezone is required.")
        value = value.astimezone(timezone.utc)
        return value.replace(tzinfo=None) if dialect.name == "sqlite" else value

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def utc_now():
    return datetime.now(timezone.utc)


class AssessmentEvent(Base):
    __tablename__ = "assessment_events"
    __table_args__ = (
        CheckConstraint("max_points >= 0"),
        CheckConstraint("category IN ('seminar_start','seminar_end','lab','checkpoint','additional')"),
        CheckConstraint("attempt_policy IN ('best','latest')"),
        CheckConstraint("max_attempts IS NULL OR max_attempts > 0"),
    )
    module_id: Mapped[int] = mapped_column(ForeignKey("teaching_modules.id", ondelete="RESTRICT"))
    lesson_id: Mapped[int | None] = mapped_column(ForeignKey("lessons.id", ondelete="RESTRICT"))
    title: Mapped[str] = mapped_column(String(256))
    category: Mapped[str] = mapped_column(String(32))
    custom_type: Mapped[str | None] = mapped_column(String(128))
    max_points: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    required: Mapped[bool] = mapped_column(Boolean)
    conditions: Mapped[str] = mapped_column(Text, default="")
    due_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    attempt_policy: Mapped[str] = mapped_column(String(16))
    max_attempts: Mapped[int | None]


class Consultation(Base):
    __tablename__ = "consultations"
    starts_at: Mapped[datetime] = mapped_column(UTCDateTime())
    title: Mapped[str] = mapped_column(String(256), default="Consultation")


class ConsultationVisit(Base):
    __tablename__ = "consultation_visits"
    __table_args__ = (UniqueConstraint("consultation_id", "student_id"),)
    consultation_id: Mapped[int] = mapped_column(ForeignKey("consultations.id", ondelete="RESTRICT"))
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="RESTRICT"))
    purpose: Mapped[str] = mapped_column(String(128))
    question: Mapped[str] = mapped_column(Text, default="")
    comment: Mapped[str] = mapped_column(Text, default="")


class LabWork(Base):
    __tablename__ = "lab_works"
    event_id: Mapped[int] = mapped_column(ForeignKey("assessment_events.id", ondelete="RESTRICT"), unique=True)
    title: Mapped[str] = mapped_column(String(256))


class ChecklistVersion(Base):
    __tablename__ = "checklist_versions"
    __table_args__ = (UniqueConstraint("lab_id", "revision"), CheckConstraint("revision > 0"))
    lab_id: Mapped[int] = mapped_column(ForeignKey("lab_works.id", ondelete="RESTRICT"))
    revision: Mapped[int]


class ChecklistCriterion(Base):
    __tablename__ = "checklist_criteria"
    __table_args__ = (UniqueConstraint("version_id", "position"), CheckConstraint("position > 0"))
    version_id: Mapped[int] = mapped_column(ForeignKey("checklist_versions.id", ondelete="RESTRICT"))
    position: Mapped[int]
    label: Mapped[str] = mapped_column(String(512))


class AssessmentAttempt(Base):
    __tablename__ = "assessment_attempts"
    __table_args__ = (
        UniqueConstraint("event_id", "student_id", "attempt_number"),
        CheckConstraint("attempt_number > 0"), CheckConstraint("points >= 0"),
        CheckConstraint("passed OR points = 0"),
    )
    event_id: Mapped[int] = mapped_column(ForeignKey("assessment_events.id", ondelete="RESTRICT"))
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="RESTRICT"))
    attempt_number: Mapped[int]
    operation_key: Mapped[str] = mapped_column(String(64), unique=True)
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime())
    work_completed: Mapped[bool] = mapped_column(Boolean)
    defended: Mapped[bool] = mapped_column(Boolean)
    passed: Mapped[bool] = mapped_column(Boolean)
    finalized: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    points: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    checklist_version_id: Mapped[int | None] = mapped_column(ForeignKey("checklist_versions.id", ondelete="RESTRICT"))
    consultation_visit_id: Mapped[int | None] = mapped_column(ForeignKey("consultation_visits.id", ondelete="RESTRICT"))
    additional_answer: Mapped[str] = mapped_column(Text, default="")
    question_passed: Mapped[bool | None] = mapped_column(Boolean)
    comment: Mapped[str] = mapped_column(Text, default="")


class CriterionAnswer(Base):
    __tablename__ = "criterion_answers"
    __table_args__ = (UniqueConstraint("attempt_id", "criterion_id"),)
    attempt_id: Mapped[int] = mapped_column(ForeignKey("assessment_attempts.id", ondelete="RESTRICT"))
    criterion_id: Mapped[int] = mapped_column(ForeignKey("checklist_criteria.id", ondelete="RESTRICT"))
    satisfied: Mapped[bool] = mapped_column(Boolean)


class ResultCorrection(Base):
    __tablename__ = "result_corrections"
    __table_args__ = (CheckConstraint("points >= 0"),)
    attempt_id: Mapped[int] = mapped_column(ForeignKey("assessment_attempts.id", ondelete="RESTRICT"))
    points: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    passed: Mapped[bool] = mapped_column(Boolean)
    reason: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(128))
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    operation_key: Mapped[str] = mapped_column(String(64), unique=True)


class EventCancellation(Base):
    __tablename__ = "event_cancellations"
    event_id: Mapped[int] = mapped_column(ForeignKey("assessment_events.id", ondelete="RESTRICT"), unique=True)
    reason: Mapped[str] = mapped_column(Text)
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)


class AttendanceRevision(Base):
    __tablename__ = "attendance_revisions"
    __table_args__ = (CheckConstraint("status IN ('absent','present','late','excused')"),)
    attendance_id: Mapped[int] = mapped_column(ForeignKey("attendances.id", ondelete="RESTRICT"))
    status: Mapped[str] = mapped_column(String(16))
    arrived_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    late_seconds: Mapped[int | None]
    reason: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(128))
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    operation_key: Mapped[str] = mapped_column(String(64), unique=True)


class NonTeachingDay(Base):
    __tablename__ = "non_teaching_days"
    __table_args__ = (UniqueConstraint("term_id", "date"),)
    term_id: Mapped[int] = mapped_column(ForeignKey("academic_terms.id", ondelete="RESTRICT"))
    date: Mapped[date] = mapped_column(Date)
    reason: Mapped[str] = mapped_column(Text)


class LessonDisposition(Base):
    __tablename__ = "lesson_dispositions"
    __table_args__ = (CheckConstraint("status IN ('cancelled','holiday','moved','held')"),)
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id", ondelete="RESTRICT"))
    status: Mapped[str] = mapped_column(String(16))
    replacement_lesson_id: Mapped[int | None] = mapped_column(ForeignKey("lessons.id", ondelete="RESTRICT"))
    reason: Mapped[str] = mapped_column(Text)
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)


class IndividualPlan(Base):
    __tablename__ = "individual_plans"
    __table_args__ = (CheckConstraint("kind IN ('coursework','diploma','project')"),)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="RESTRICT"))
    offering_id: Mapped[int | None] = mapped_column(ForeignKey("course_offerings.id", ondelete="RESTRICT"))
    title: Mapped[str] = mapped_column(String(256))
    kind: Mapped[str] = mapped_column(String(16))


class PlanStage(Base):
    __tablename__ = "plan_stages"
    __table_args__ = (UniqueConstraint("plan_id", "position"), CheckConstraint("position > 0"))
    plan_id: Mapped[int] = mapped_column(ForeignKey("individual_plans.id", ondelete="RESTRICT"))
    position: Mapped[int]
    title: Mapped[str] = mapped_column(String(512))


class PlanEntry(Base):
    __tablename__ = "plan_entries"
    stage_id: Mapped[int] = mapped_column(ForeignKey("plan_stages.id", ondelete="RESTRICT"))
    completed: Mapped[bool] = mapped_column(Boolean)
    comment: Mapped[str] = mapped_column(Text)
    consultation_visit_id: Mapped[int | None] = mapped_column(ForeignKey("consultation_visits.id", ondelete="RESTRICT"))
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)


class TeachingAudit(Base):
    __tablename__ = "teaching_audit"
    action: Mapped[str] = mapped_column(String(64))
    entity_type: Mapped[str] = mapped_column(String(64))
    entity_id: Mapped[int]
    reason: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(128))
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
