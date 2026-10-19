from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from pathlib import Path
from app.io_tools.application.multisheet_smart_import import (
    import_xlsx_with_multisheet_smart_import,
)
from app.io_tools.application.human_table_import import (
    import_xlsx_with_human_table_import,
)

from pydantic import ValidationError
from openpyxl import load_workbook
from sqlalchemy import create_engine, delete, event, func, or_, select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, selectinload, sessionmaker

from app.database import DATABASE_URL
from app.io_tools import ImportExportService
from app.io_tools.application import ImportRequest
from app.io_tools.engine.operation_result import TabularImportResult
from app.io_tools.engine.processing_models import (
    DataProcessingResult,
    ImportProcessingResult,
    StrictImportResult,
)
from app.io_tools.tabular.entity_schema_rules import (
    CREATE_SCHEMA_BY_ENTITY,
    STRICT_CREATE_SCHEMA_BY_ENTITY,
)
from app.io_tools.tabular.field_aliases import (
    build_direct_alias_index,
    build_reference_alias_index,
    normalize_tabular_header,
)
from app.io_tools.tabular.models import ExtractedTable
from app.io_tools.xlsx_config import XLSX_SHEETS_ORDER
from app.io_tools.xlsx_config import XLSX_COLUMNS_BY_SHEET
from app.io_tools.xlsx_config import XLSX_REQUIRED_COLUMNS_BY_SHEET
from app.models import (
    Attendance,
    Base,
    Comment,
    Group,
    GroupMembership,
    Lesson,
    LessonParticipant,
    Mark,
    Schedule,
    ScheduleGroupLink,
    Student,
)
from app.ui.data.calendar import SemesterSettings, day_index, week_type_for_number
from app.ui.data.schedule_migration import ensure_schedule_schema
from app.ui.data.membership_migration import ensure_membership_schema, set_membership_import_mode


class RepositoryError(Exception):
    """User-facing data error raised by the UI repository."""


@dataclass(slots=True)
class ImportPreview:
    source_path: Path
    strategy: str
    mode: str
    data: dict[str, list[dict[str, object]]]
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def row_counts(self) -> dict[str, int]:
        return {
            sheet_name: len(rows)
            for sheet_name, rows in self.data.items()
            if rows
        }

    @property
    def total_rows(self) -> int:
        return sum(self.row_counts.values())


class DiaryRepository:
    """Thin UI-facing repository over the existing SQLAlchemy models."""

    _smart_entity_types = ("groups", "students")
    _model_by_sheet = {
        "groups": Group,
        "schedules": Schedule,
        "students": Student,
        "schedule_group_links": ScheduleGroupLink,
        "lessons": Lesson,
        "attendances": Attendance,
        "marks": Mark,
        "comments": Comment,
        "group_memberships": GroupMembership,
        "lesson_participants": LessonParticipant,
    }
    _import_references = {
        "students": {"group_id": "groups"},
        "schedule_group_links": {"group_id": "groups", "schedule_id": "schedules"},
        "lessons": {"schedule_id": "schedules"},
        "attendances": {"student_id": "students", "lesson_id": "lessons"},
        "marks": {"student_id": "students", "lesson_id": "lessons"},
        "comments": {"student_id": "students", "lesson_id": "lessons"},
        "group_memberships": {"student_id": "students", "group_id": "groups"},
        "lesson_participants": {"student_id": "students", "lesson_id": "lessons", "group_id": "groups"},
    }
    _delete_order = (
        Comment,
        Mark,
        Attendance,
        Lesson,
        ScheduleGroupLink,
        Student,
        Schedule,
        Group,
    )
    def import_human_table_xlsx(self, file_path: str | Path) -> str:
        """
        Импортирует человеческий Excel-файл.

        Например:
        - Лист1: группа | специальность и фамилия | имя
        - Лист2: студент | оценки
        """
        result = import_xlsx_with_human_table_import(file_path)

        report_lines: list[str] = ["Создано:"]

        for entity_type, count in result.created.items():
            report_lines.append(f"{entity_type}: {count}")

        if result.warnings:
            report_lines.append("")
            report_lines.append("Предупреждения:")
            for warning in result.warnings:
                report_lines.append(f"- {warning}")

        if result.errors:
            report_lines.append("")
            report_lines.append("Ошибки:")
            for error in result.errors:
                report_lines.append(f"- {error}")

        report = "\n".join(report_lines)

        if not result.is_valid:
            raise RepositoryError(report)

        self.refresh()

        return report
    def import_multisheet_smart_xlsx(self, file_path: str | Path) -> str:
        """
        Импортирует XLSX-книгу целиком через multi-sheet smart import.

        Этот режим нужен для файлов с листами:
        groups, schedules, students, schedule_group_links,
        lessons, attendances, marks, comments.
        """
        self._reject_legacy_schedule_workbook(Path(file_path), allow_versioned=False)
        result = import_xlsx_with_multisheet_smart_import(file_path)

        report_lines: list[str] = []

        report_lines.append("Создано:")
        for entity_type, count in result.created.items():
            report_lines.append(f"{entity_type}: {count}")

        if result.warnings:
            report_lines.append("")
            report_lines.append("Предупреждения:")
            for warning in result.warnings:
                report_lines.append(f"- {warning}")

        if result.errors:
            report_lines.append("")
            report_lines.append("Ошибки:")
            for error in result.errors:
                report_lines.append(f"- {error}")

        report = "\n".join(report_lines)

        if not result.is_valid:
            raise RepositoryError(report)

        return report

    def __init__(self) -> None:
        self.engine = create_engine(DATABASE_URL)
        if DATABASE_URL.startswith("sqlite"):
            event.listen(self.engine, "connect", self._enable_sqlite_foreign_keys)
        ensure_schedule_schema(self.engine)
        ensure_membership_schema(self.engine)
        self.session_factory = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.session: Session = self.session_factory()
        self.import_export_service = ImportExportService()
        self._direct_alias_index = build_direct_alias_index()
        self._reference_alias_index = build_reference_alias_index()

    @staticmethod
    def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    def close(self) -> None:
        self.session.close()

    def refresh(self) -> None:
        self.session.expire_all()

    def seed_demo_data(self, settings: SemesterSettings) -> None:
        groups = {
            "SM1-21B": self._get_or_create_group("SM1-21B", "Software engineering"),
            "IBM5-23B": self._get_or_create_group("IBM5-23B", "Business informatics"),
            "IBM5-24B": self._get_or_create_group("IBM5-24B", "Business informatics"),
            "CS2-22A": self._get_or_create_group("CS2-22A", "Computer science"),
        }
        self.session.commit()

        demo_students = {
            "SM1-21B": [
                ("Johnson", "Alex"),
                ("Garcia", "Maria"),
                ("Smith", "John"),
                ("Wilson", "Emma"),
                ("Brown", "Oliver"),
            ],
            "IBM5-23B": [
                ("Davis", "Mia"),
                ("Miller", "Noah"),
                ("Taylor", "Sophia"),
                ("Anderson", "Lucas"),
            ],
            "IBM5-24B": [
                ("Thomas", "Ava"),
                ("Moore", "Ethan"),
                ("Jackson", "Isabella"),
                ("White", "Liam"),
            ],
            "CS2-22A": [
                ("Harris", "Charlotte"),
                ("Martin", "Benjamin"),
                ("Thompson", "Amelia"),
            ],
        }
        for group_name, students in demo_students.items():
            for surname, first_name in students:
                self._get_or_create_student(groups[group_name], surname, first_name)
        self.session.commit()

        schedule_specs = [
            {
                "topic": "Graph Theory Applications",
                "groups": ["CS2-22A"],
                "day": "Monday",
                "time": time(10, 0),
                "week_type": "even",
                "type": "Seminar",
                "is_assessment": False,
            },
            {
                "topic": "SQL Query Optimization",
                "groups": ["SM1-21B"],
                "day": "Wednesday",
                "time": time(14, 30),
                "week_type": "even",
                "type": "Seminar",
                "is_assessment": False,
            },
            {
                "topic": "Design Patterns Implementation",
                "groups": ["IBM5-23B", "IBM5-24B"],
                "day": "Wednesday",
                "time": time(16, 10),
                "week_type": "even",
                "type": "Lab Work",
                "is_assessment": True,
            },
            {
                "topic": "Database Design Fundamentals",
                "groups": ["SM1-21B"],
                "day": "Wednesday",
                "time": time(14, 30),
                "week_type": "odd",
                "type": "Lab Work",
                "is_assessment": True,
            },
            {
                "topic": "Web Development with React",
                "groups": ["SM1-21B"],
                "day": "Friday",
                "time": time(12, 0),
                "week_type": "odd",
                "type": "Lab Work",
                "is_assessment": True,
            },
            {
                "topic": "Algorithms and Data Structures",
                "groups": ["CS2-22A"],
                "day": "Monday",
                "time": time(10, 0),
                "week_type": "odd",
                "type": "Control Work",
                "is_assessment": True,
            },
        ]

        for spec in schedule_specs:
            schedule = self._get_or_create_schedule(spec)
            for group_name in spec["groups"]:
                self._get_or_create_schedule_link(groups[group_name], schedule)
            self.session.flush()
            self.ensure_lessons_for_schedule(schedule, spec["topic"], settings)

        self.session.commit()

    def ensure_lessons_for_semester(self, settings: SemesterSettings) -> None:
        for schedule in self.list_schedules():
            self.ensure_lessons_for_schedule(schedule, None, settings)
        self._commit_or_raise("Lessons were not generated for the semester.")

    def ensure_lessons_for_schedule(
        self,
        schedule: Schedule,
        topic: str | None,
        settings: SemesterSettings,
    ) -> None:
        default_topic = (topic or "").strip() or None
        for week_offset in range(settings.total_weeks):
            week_number = week_offset + 1
            if week_type_for_number(week_number) != schedule.odd_or_even:
                continue
            lesson_date = settings.start_date + timedelta(
                weeks=week_offset,
                days=day_index(schedule.day),
            )
            if lesson_date < schedule.effective_from or (
                schedule.effective_until is not None
                and lesson_date >= schedule.effective_until
            ):
                continue
            lesson = self.session.scalar(
                select(Lesson).where(
                    Lesson.schedule_id == schedule.id,
                    Lesson.date == lesson_date,
                )
            )
            if lesson is None:
                self.session.add(
                    Lesson(schedule_id=schedule.id, topic=default_topic, date=lesson_date)
                )

    def ensure_attendance_and_marks(self) -> None:
        """Kept for older UI calls; records are now created only by teacher input."""
        self.session.commit()

    def list_groups(self, *, include_archived: bool = False) -> list[Group]:
        self.refresh()
        stmt = (
            select(Group)
            .options(
                selectinload(Group.students).selectinload(Student.attendances),
                selectinload(Group.students)
                .selectinload(Student.marks)
                .selectinload(Mark.lesson)
                .selectinload(Lesson.schedule),
                selectinload(Group.students).selectinload(Student.comments),
                selectinload(Group.schedule_links)
                .selectinload(ScheduleGroupLink.schedule)
                .selectinload(Schedule.lessons),
            )
            .order_by(Group.name)
        )
        if not include_archived:
            stmt = stmt.where(Group.is_archived.is_(False))
        return list(self.session.scalars(stmt).all())

    def list_students(
        self, group_id: int | None = None, *, include_archived: bool = False
    ) -> list[Student]:
        self.refresh()
        stmt = (
            select(Student)
            .options(
                selectinload(Student.group),
                selectinload(Student.attendances),
                selectinload(Student.marks)
                .selectinload(Mark.lesson)
                .selectinload(Lesson.schedule),
                selectinload(Student.comments),
            )
            .order_by(Student.surname, Student.first_name)
        )
        if group_id is not None:
            stmt = stmt.where(Student.group_id == group_id)
        if not include_archived:
            stmt = stmt.where(Student.status == "active")
        return list(self.session.scalars(stmt).all())

    def get_group(self, group_id: int) -> Group | None:
        self.refresh()
        stmt = (
            select(Group)
            .where(Group.id == group_id)
            .options(
                selectinload(Group.students).selectinload(Student.attendances),
                selectinload(Group.students)
                .selectinload(Student.marks)
                .selectinload(Mark.lesson)
                .selectinload(Lesson.schedule),
                selectinload(Group.students).selectinload(Student.comments),
                selectinload(Group.schedule_links)
                .selectinload(ScheduleGroupLink.schedule)
                .selectinload(Schedule.lessons),
            )
        )
        return self.session.scalar(stmt)

    def get_student(self, student_id: int) -> Student | None:
        self.refresh()
        stmt = (
            select(Student)
            .where(Student.id == student_id)
            .options(
                selectinload(Student.group)
                .selectinload(Group.schedule_links)
                .selectinload(ScheduleGroupLink.schedule)
                .selectinload(Schedule.lessons),
                selectinload(Student.attendances)
                .selectinload(Attendance.lesson)
                .selectinload(Lesson.schedule),
                selectinload(Student.marks)
                .selectinload(Mark.lesson)
                .selectinload(Lesson.schedule),
                selectinload(Student.comments)
                .selectinload(Comment.lesson)
                .selectinload(Lesson.schedule),
            )
        )
        return self.session.scalar(stmt)

    def get_lesson(self, lesson_id: int) -> Lesson | None:
        self.refresh()
        return self.session.scalar(
            self._lesson_options(select(Lesson).where(Lesson.id == lesson_id))
        )

    def list_schedules(self, *, include_history: bool = False) -> list[Schedule]:
        self.refresh()
        stmt = (
            select(Schedule)
            .options(
                selectinload(Schedule.group_links).selectinload(ScheduleGroupLink.group),
                selectinload(Schedule.lessons),
            )
            .order_by(Schedule.day, Schedule.time)
        )
        if not include_history:
            stmt = stmt.where(
                or_(Schedule.effective_until.is_(None), Schedule.effective_until > date.today())
            )
        return list(self.session.scalars(stmt).all())

    def list_lessons(self) -> list[Lesson]:
        self.refresh()
        return list(self.session.scalars(self._lesson_options(select(Lesson))).all())

    def lessons_for_week(self, week_start: date, week_type: str | None) -> list[Lesson]:
        self.refresh()
        week_end = week_start + timedelta(days=6)
        stmt = self._lesson_options(
            select(Lesson)
            .join(Lesson.schedule)
            .where(Lesson.date >= week_start, Lesson.date <= week_end)
            .order_by(Lesson.date, Schedule.time)
        )
        if week_type is not None:
            stmt = stmt.where(Schedule.odd_or_even == week_type)
        return list(self.session.scalars(stmt).all())

    def _lesson_options(self, stmt):
        return stmt.options(
            selectinload(Lesson.schedule)
            .selectinload(Schedule.group_links)
            .selectinload(ScheduleGroupLink.group)
            .selectinload(Group.students),
            selectinload(Lesson.attendances).selectinload(Attendance.student),
            selectinload(Lesson.marks).selectinload(Mark.student),
            selectinload(Lesson.comments).selectinload(Comment.student),
        )

    def students_for_lesson(self, lesson: Lesson) -> list[Student]:
        if lesson.roster_origin == "unfixed" and lesson.date <= date.today():
            group_ids = {link.group_id for link in lesson.schedule.group_links}
            memberships = self.session.scalars(select(GroupMembership).where(
                GroupMembership.group_id.in_(group_ids),
                GroupMembership.start_date <= lesson.date,
                GroupMembership.known_from <= lesson.date,
                or_(GroupMembership.end_date.is_(None), GroupMembership.end_date > lesson.date),
            )).all() if group_ids else []
            if memberships:
                existing_ids = {item.student_id for item in lesson.participants}
                for membership in memberships:
                    if membership.student_id not in existing_ids:
                        self.session.add(LessonParticipant(
                            lesson_id=lesson.id, student_id=membership.student_id,
                            group_id=membership.group_id, source="snapshot"
                        ))
                self.session.flush()
                lesson.participants_complete = True
                lesson.roster_origin = "snapshot"
                self._commit_or_raise("Lesson participants could not be fixed.")
        ids = {item.student_id for item in lesson.participants}
        if lesson.roster_origin == "unfixed" and lesson.date > date.today():
            group_ids = {link.group_id for link in lesson.schedule.group_links}
            if group_ids:
                ids.update(self.session.scalars(select(GroupMembership.student_id).where(
                    GroupMembership.group_id.in_(group_ids),
                    GroupMembership.start_date <= lesson.date,
                    GroupMembership.known_from <= date.today(),
                    or_(GroupMembership.end_date.is_(None), GroupMembership.end_date > lesson.date),
                )).all())
        if not lesson.participants_complete:
            ids.update(item.student_id for item in lesson.attendances)
            ids.update(item.student_id for item in lesson.marks)
            ids.update(item.student_id for item in lesson.comments)
        students = [self.session.get(Student, student_id) for student_id in ids]
        return sorted(
            (student for student in students if student is not None),
            key=lambda item: (item.surname, item.first_name),
        )

    def schedule_groups_text(self, schedule: Schedule) -> str:
        names = [link.group.name for link in schedule.group_links]
        return ", ".join(sorted(names)) if names else "No groups"

    def lesson_groups_text(self, lesson: Lesson) -> str:
        return self.schedule_groups_text(lesson.schedule)

    def schedule_topic(self, schedule: Schedule) -> str:
        lessons = sorted(schedule.lessons, key=lambda item: item.date)
        for lesson in lessons:
            if lesson.topic:
                return lesson.topic
        return "Untitled lesson"

    def update_lesson_topic(self, lesson: Lesson, topic: str | None) -> None:
        cleaned_topic = (topic or "").strip() or None
        if cleaned_topic is not None and len(cleaned_topic) > 512:
            raise RepositoryError("Lesson topic must be 512 characters or shorter.")
        lesson.topic = cleaned_topic
        self._commit_or_raise("Lesson topic was not updated.")

    def full_student_name(self, student: Student) -> str:
        return f"{student.first_name} {student.surname}"

    def attendance_for(self, lesson: Lesson, student: Student) -> Attendance | None:
        for attendance in lesson.attendances:
            if attendance.student_id == student.id:
                return attendance
        return None

    def mark_for(self, lesson: Lesson, student: Student) -> Mark | None:
        for mark in lesson.marks:
            if mark.student_id == student.id:
                return mark
        return None

    def comment_for(self, lesson: Lesson, student: Student) -> Comment | None:
        for comment in lesson.comments:
            if comment.student_id == student.id:
                return comment
        return None

    def lessons_for_student(self, student: Student) -> list[Lesson]:
        lesson_ids = {item.lesson_id for item in student.lesson_participations}
        lesson_ids.update(item.lesson_id for item in student.attendances)
        lesson_ids.update(item.lesson_id for item in student.marks)
        lesson_ids.update(item.lesson_id for item in student.comments)
        for membership in student.memberships:
            for link in membership.group.schedule_links:
                for lesson in link.schedule.lessons:
                    if (membership.start_date <= lesson.date
                            and (membership.end_date is None or lesson.date < membership.end_date)
                            and membership.known_from <= lesson.date
                            and lesson.roster_origin == "unfixed"):
                        lesson_ids.add(lesson.id)
        lessons = [lesson for lesson_id in lesson_ids if (lesson := self.get_lesson(lesson_id))]
        return sorted(lessons, key=lambda item: (item.date, item.schedule.time))

    def save_lesson_student_record(
        self,
        lesson: Lesson,
        student: Student,
        *,
        attended: bool,
        comment_text: str,
        mark_value: int | None,
    ) -> None:
        if lesson.participants_complete and student.id not in {
            item.student_id for item in lesson.participants
        }:
            raise RepositoryError("Student is not in the fixed lesson roster.")
        if not any(item.student_id == student.id for item in lesson.participants):
            group_ids = {link.group_id for link in lesson.schedule.group_links}
            known_groups = {item.group_id for item in student.memberships
                            if item.group_id in group_ids
                            and item.start_date <= lesson.date
                            and (item.end_date is None or item.end_date > lesson.date)
                            and item.known_from <= lesson.date}
            self.session.add(LessonParticipant(
                lesson_id=lesson.id, student_id=student.id,
                group_id=next(iter(known_groups)) if len(known_groups) == 1 else None,
                source="evidence"
            ))
        attendance = self.session.scalar(
            select(Attendance).where(
                Attendance.lesson_id == lesson.id,
                Attendance.student_id == student.id,
            )
        )
        if attendance is None:
            self.session.add(
                Attendance(
                    lesson_id=lesson.id,
                    student_id=student.id,
                    is_visited=attended,
                )
            )
        else:
            attendance.is_visited = attended

        comment = self.session.scalar(
            select(Comment).where(
                Comment.lesson_id == lesson.id,
                Comment.student_id == student.id,
            )
        )
        cleaned_comment = comment_text.strip()
        if cleaned_comment:
            if comment is None:
                self.session.add(
                    Comment(
                        lesson_id=lesson.id,
                        student_id=student.id,
                        data=cleaned_comment,
                    )
                )
            else:
                comment.data = cleaned_comment
        elif comment is not None:
            self.session.delete(comment)

        if lesson.schedule.is_assessment:
            mark = self.session.scalar(
                select(Mark).where(
                    Mark.lesson_id == lesson.id,
                    Mark.student_id == student.id,
                )
            )
            if mark_value is None:
                if mark is not None:
                    self.session.delete(mark)
            elif mark is None:
                self.session.add(
                    Mark(
                        lesson_id=lesson.id,
                        student_id=student.id,
                        data=mark_value,
                    )
                )
            else:
                mark.data = mark_value

        self._commit_or_raise("Lesson record was not saved.")

    def lesson_attendance_summary(self, lesson: Lesson) -> dict[str, int | str]:
        students = self.students_for_lesson(lesson)
        present = 0
        for student in students:
            attendance = self.attendance_for(lesson, student)
            if attendance is not None and attendance.is_visited:
                present += 1
        total = len(students)
        return {
            "total": total,
            "present": present,
            "absent": max(total - present, 0) if lesson.participants_complete else "-",
            "rate": round(present / total * 100) if total and lesson.participants_complete else "-",
        }

    def _group_participant_ids(self, lesson: Lesson, group_id: int) -> set[int]:
        participant_ids = {item.student_id for item in lesson.participants
                           if item.group_id == group_id}
        unresolved_ids = {item.student_id for item in lesson.participants
                          if item.group_id is None}
        unresolved_ids.update(item.student_id for item in lesson.attendances)
        unresolved_ids.update(item.student_id for item in lesson.marks)
        unresolved_ids.update(item.student_id for item in lesson.comments)
        unresolved_ids.difference_update(
            item.student_id for item in lesson.participants if item.group_id is not None
        )
        if len(lesson.schedule.group_links) == 1:
            return participant_ids | unresolved_ids
        known_ids = set(self.session.scalars(select(GroupMembership.student_id).where(
            GroupMembership.group_id == group_id,
            GroupMembership.start_date <= lesson.date,
            GroupMembership.known_from <= lesson.date,
            or_(GroupMembership.end_date.is_(None), GroupMembership.end_date > lesson.date),
        )).all())
        return participant_ids | (unresolved_ids & known_ids)

    def group_stats(self, group: Group) -> dict[str, int | str]:
        students = [student for student in group.students if student.status == "active"]
        lessons = self._completed_lessons_for_group(group)
        all_marks: list[int] = []
        lab_marks: list[int] = []
        test_marks: list[int] = []
        present = attendance_slots = 0
        complete = True
        for lesson in lessons:
            ids = self._group_participant_ids(lesson, group.id)
            complete = complete and lesson.participants_complete
            if lesson.participants_complete:
                attendance_slots += len(ids)
                present += sum(item.is_visited for item in lesson.attendances if item.student_id in ids)
            if lesson.schedule.is_assessment:
                scores = [mark.data for mark in lesson.marks if mark.student_id in ids]
                all_marks.extend(scores)
                if lesson.schedule.type == "Lab Work":
                    lab_marks.extend(scores)
                if lesson.schedule.type == "Control Work":
                    test_marks.extend(scores)
        attendance_rate = (
            round(present / attendance_slots * 100) if attendance_slots else 0
        ) if complete else "-"
        overall = round(sum(all_marks) / len(all_marks)) if all_marks else 0
        lab_average = round(sum(lab_marks) / len(lab_marks)) if lab_marks else 0
        test_average = round(sum(test_marks) / len(test_marks)) if test_marks else "-"
        return {
            "overall": overall,
            "lab": lab_average,
            "test": test_average,
            "attendance": attendance_rate,
            "students": len(students),
            "status": self._performance_status(
                overall, attendance_rate if isinstance(attendance_rate, int) else 0,
                len(all_marks), attendance_slots,
            ) if complete else "Incomplete history",
        }

    def student_stats(self, student: Student) -> dict[str, int | str]:
        lessons = self._completed_lessons_for_student(student)
        uncertain_legacy_history = any(
            membership.origin == "migrated_unknown"
            and any(
                lesson.date < membership.known_from and lesson.date <= date.today()
                for link in membership.group.schedule_links
                for lesson in link.schedule.lessons
            )
            for membership in student.memberships
        )
        all_scores: list[int] = []
        lab_scores: list[int] = []
        test_scores: list[int] = []
        present = 0
        for lesson in lessons:
            present += any(
                item.student_id == student.id and item.is_visited for item in lesson.attendances
            )
            if lesson.schedule.is_assessment:
                scores = [item.data for item in lesson.marks if item.student_id == student.id]
                all_scores.extend(scores)
                if lesson.schedule.type == "Lab Work":
                    lab_scores.extend(scores)
                if lesson.schedule.type == "Control Work":
                    test_scores.extend(scores)
        attendance = (
            round(present / len(lessons) * 100) if lessons else 0
        ) if (not uncertain_legacy_history
              and all(lesson.participants_complete for lesson in lessons)) else "-"
        return {
            "overall": round(sum(all_scores) / len(all_scores)) if all_scores else "-",
            "lab": round(sum(lab_scores) / len(lab_scores)) if lab_scores else "-",
            "test": round(sum(test_scores) / len(test_scores)) if test_scores else "-",
            "attendance": attendance,
        }

    def _completed_lessons_for_group(self, group: Group) -> list[Lesson]:
        lesson_by_id: dict[int, Lesson] = {}
        for link in group.schedule_links:
            for lesson in link.schedule.lessons:
                if lesson.date <= date.today():
                    lesson_by_id[lesson.id] = lesson
        return sorted(
            lesson_by_id.values(),
            key=lambda item: (item.date, item.schedule.time),
        )

    def _completed_lessons_for_student(self, student: Student) -> list[Lesson]:
        return [lesson for lesson in self.lessons_for_student(student) if lesson.date <= date.today()]

    @staticmethod
    def _performance_status(
        average: int | str,
        attendance: int,
        score_slots: int,
        attendance_slots: int,
    ) -> str:
        if not score_slots and not attendance_slots:
            return "No data"
        numeric_average = average if isinstance(average, int) else 0
        if score_slots:
            score = round(numeric_average * 0.65 + attendance * 0.35)
        else:
            score = attendance
        if score >= 85:
            return "Excellent"
        if score >= 70:
            return "Good"
        if score >= 50:
            return "Watch"
        return "At risk"

    def create_group(self, name: str, speciality: str | None = None) -> Group:
        clean_name = name.strip()
        clean_speciality = (speciality or "").strip() or None
        self._validate_group_values(clean_name, clean_speciality)
        self._ensure_group_name_available(clean_name)
        group = Group(name=clean_name, speciality=clean_speciality)
        self.session.add(group)
        self._commit_or_raise("Group was not created.")
        return group

    def update_group(self, group: Group, name: str, speciality: str | None) -> None:
        clean_name = name.strip()
        clean_speciality = (speciality or "").strip() or None
        self._validate_group_values(clean_name, clean_speciality)
        self._ensure_group_name_available(clean_name, current_group_id=group.id)
        group.name = clean_name
        group.speciality = clean_speciality
        self._commit_or_raise("Group was not updated.")

    def delete_group(self, group: Group) -> None:
        self.archive_group(group)

    def archive_group(self, group: Group, reason: str | None = None) -> None:
        if any(student.status == "active" for student in group.students) or any(
            link.schedule.effective_until is None
            or link.schedule.effective_until > date.today()
            for link in group.schedule_links
        ):
            raise RepositoryError("Group is still used by active students or schedules.")
        group.is_archived = True
        group.archive_reason = (reason or "").strip() or None
        self._commit_or_raise("Group was not archived.")

    def create_student(
        self,
        group: Group,
        first_name: str,
        surname: str,
        email: str | None = None,
    ) -> Student:
        clean_first_name = first_name.strip()
        clean_surname = surname.strip()
        clean_email = (email or "").strip() or None
        self._validate_student_values(clean_first_name, clean_surname, clean_email)
        self._ensure_student_available(group.id, clean_first_name, clean_surname)
        student = Student(
            group_id=group.id,
            first_name=clean_first_name,
            surname=clean_surname,
            patronymic=None,
            personal_data=None,
            bmstu_email=clean_email,
        )
        self.session.add(student)
        self._commit_or_raise("Student was not created.")
        return student

    def update_student(
        self,
        student: Student,
        group: Group,
        first_name: str,
        surname: str,
        email: str | None,
    ) -> None:
        if group.id != student.group_id:
            raise RepositoryError("Use Transfer with an effective date to change the student's group.")
        clean_first_name = first_name.strip()
        clean_surname = surname.strip()
        clean_email = (email or "").strip() or None
        self._validate_student_values(clean_first_name, clean_surname, clean_email)
        self._ensure_student_available(
            group.id,
            clean_first_name,
            clean_surname,
            current_student_id=student.id,
        )
        student.group_id = group.id
        student.first_name = clean_first_name
        student.surname = clean_surname
        student.bmstu_email = clean_email
        self._commit_or_raise("Student was not updated.")

    def delete_student(self, student: Student) -> None:
        self.archive_student(student, reason="Archived from student list")

    def membership_history(self, student: Student) -> list[GroupMembership]:
        return list(self.session.scalars(
            select(GroupMembership)
            .where(GroupMembership.student_id == student.id)
            .order_by(GroupMembership.start_date, GroupMembership.id)
        ).all())

    def transfer_student(
        self, student: Student, group: Group, effective_date: date, *, as_of: date | None = None
    ) -> None:
        today = as_of or date.today()
        if student.status != "active" or group.is_archived:
            raise RepositoryError("Only active students and groups can be used for a transfer.")
        if effective_date > today:
            raise RepositoryError("Future transfers are not supported; choose today or an earlier date.")
        try:
            if self.engine.dialect.name == "sqlite":
                self.session.execute(text("UPDATE students SET id = id WHERE id = :id"), {"id": student.id})
            else:
                self.session.execute(select(Student.id).where(Student.id == student.id).with_for_update()).first()
            self.session.refresh(student)
            if student.status != "active":
                raise RepositoryError("Student was archived by another operation.")
            if student.group_id == group.id:
                self.session.rollback()
                return
            current = self.session.scalar(select(GroupMembership).where(
                GroupMembership.student_id == student.id,
                GroupMembership.end_date.is_(None),
            ))
            if current is None or current.group_id != student.group_id:
                raise RepositoryError("Current group membership is inconsistent.")
            if effective_date < current.start_date:
                raise RepositoryError("Transfer date predates the current membership.")
            current.end_date = effective_date
            self.session.flush()
            self.session.add(GroupMembership(
                student_id=student.id, group_id=group.id,
                start_date=effective_date, known_from=effective_date, origin="recorded",
            ))
            self.session.flush()
            student.group_id = group.id
            self._commit_or_raise("Student transfer was not saved.")
        except (RepositoryError, SQLAlchemyError) as exc:
            self.session.rollback()
            if isinstance(exc, RepositoryError):
                raise
            raise RepositoryError("Student transfer was not saved.") from exc

    def archive_student(
        self, student: Student, *, reason: str, effective_date: date | None = None
    ) -> None:
        cutoff = effective_date or date.today()
        if cutoff > date.today():
            raise RepositoryError("Future archiving is not supported.")
        if student.status != "active":
            raise RepositoryError("Student is already archived.")
        try:
            if self.engine.dialect.name == "sqlite":
                self.session.execute(text("UPDATE students SET id = id WHERE id = :id"), {"id": student.id})
            else:
                self.session.execute(select(Student.id).where(Student.id == student.id).with_for_update()).first()
            self.session.refresh(student)
            current = self.session.scalar(select(GroupMembership).where(
                GroupMembership.student_id == student.id,
                GroupMembership.end_date.is_(None),
            ))
            if current is None or cutoff < current.start_date:
                raise RepositoryError("Student membership cannot be closed at that date.")
            current.end_date = cutoff
            self.session.flush()
            student.status = "archived"
            student.archived_at = cutoff
            student.archive_reason = reason.strip() or "Archived"
            self._commit_or_raise("Student was not archived.")
        except (RepositoryError, SQLAlchemyError) as exc:
            self.session.rollback()
            if isinstance(exc, RepositoryError):
                raise
            raise RepositoryError("Student was not archived.") from exc

    def create_schedule(
        self,
        topic: str | None,
        groups: list[Group],
        day: str,
        lesson_time: time,
        week_type: str,
        lesson_type: str,
        is_assessment: bool,
        settings: SemesterSettings,
        *,
        effective_from: date | None = None,
    ) -> Schedule:
        if effective_from is not None and effective_from <= date.today():
            raise RepositoryError("Choose a future effective date for the schedule.")
        self._ensure_schedule_available(
            groups,
            day,
            lesson_time,
            week_type,
            lesson_type,
            effective_from=effective_from or date(1900, 1, 1),
        )
        schedule = Schedule(
            effective_from=effective_from or date(1900, 1, 1),
            odd_or_even=week_type,
            type=lesson_type,
            is_assessment=is_assessment,
            day=day,
            time=lesson_time,
        )
        self.session.add(schedule)
        self.session.flush()
        for group in groups:
            self.session.add(ScheduleGroupLink(group_id=group.id, schedule_id=schedule.id))
        self.ensure_lessons_for_schedule(schedule, topic, settings)
        self._commit_or_raise("Schedule template was not created.")
        return schedule

    def update_schedule(
        self,
        schedule: Schedule,
        topic: str | None,
        groups: list[Group],
        day: str,
        lesson_time: time,
        week_type: str,
        lesson_type: str,
        is_assessment: bool,
        settings: SemesterSettings,
        *,
        as_of: date | None = None,
        effective_from: date | None = None,
    ) -> Schedule:
        old_group_ids = {link.group_id for link in schedule.group_links}
        new_group_ids = {group.id for group in groups}
        changed = (
            schedule.day != day
            or schedule.time != lesson_time
            or schedule.odd_or_even != week_type
            or schedule.type != lesson_type
            or schedule.is_assessment != is_assessment
            or old_group_ids != new_group_ids
        )
        if not changed:
            return schedule
        cutoff = as_of or date.today()
        if effective_from is None or effective_from <= cutoff:
            raise RepositoryError("Choose a future effective date for schedule changes.")
        if schedule.effective_until is not None or effective_from <= schedule.effective_from:
            raise RepositoryError("Only the latest schedule version can be changed.")
        try:
            self._lock_schedule_for_edit(schedule, effective_from)
            if schedule.effective_until is not None:
                raise RepositoryError("This schedule version has already been changed.")
            self._reject_conflicting_future_lessons(schedule, effective_from)
            self._ensure_schedule_available(
                groups, day, lesson_time, week_type, lesson_type,
                current_schedule_id=schedule.id, effective_from=effective_from,
            )
            for lesson in list(schedule.lessons):
                if lesson.date >= effective_from:
                    self.session.delete(lesson)
            self.session.flush()
            schedule.effective_until = effective_from
            self.session.flush()
            next_schedule = Schedule(
                series_key=schedule.series_key,
                revision=schedule.revision + 1,
                effective_from=effective_from,
                odd_or_even=week_type,
                type=lesson_type,
                is_assessment=is_assessment,
                day=day,
                time=lesson_time,
            )
            self.session.add(next_schedule)
            self.session.flush()
            for group_id in new_group_ids:
                self.session.add(ScheduleGroupLink(group_id=group_id, schedule_id=next_schedule.id))
            self.ensure_lessons_for_schedule(next_schedule, topic, settings)
            self._commit_or_raise("Schedule template was not updated.")
            return next_schedule
        except RepositoryError:
            self.session.rollback()
            raise
        except SQLAlchemyError as exc:
            self.session.rollback()
            raise RepositoryError("Schedule template was not updated.") from exc

    def delete_schedule(
        self,
        schedule: Schedule,
        *,
        as_of: date | None = None,
        effective_from: date | None = None,
    ) -> None:
        cutoff = as_of or date.today()
        try:
            self._lock_schedule_for_edit(schedule, effective_from or cutoff + timedelta(days=1))
            if schedule.effective_until is not None:
                raise RepositoryError("This schedule version is already closed.")
            has_history = self.session.scalar(
                select(Lesson.id)
                .where(Lesson.schedule_id == schedule.id, Lesson.date <= cutoff)
                .limit(1)
            ) is not None
            if has_history:
                if effective_from is None or effective_from <= cutoff:
                    raise RepositoryError("Choose a future effective date to deactivate this schedule.")
                self._reject_conflicting_future_lessons(schedule, effective_from)
                for lesson in list(schedule.lessons):
                    if lesson.date >= effective_from:
                        self.session.delete(lesson)
                self.session.flush()
                schedule.effective_until = effective_from
                self._commit_or_raise("Schedule template was not deactivated.")
            else:
                self._reject_conflicting_future_lessons(schedule, cutoff + timedelta(days=1))
                self.session.delete(schedule)
                self._commit_or_raise("Schedule template was not deleted.")
        except RepositoryError:
            self.session.rollback()
            raise
        except SQLAlchemyError as exc:
            self.session.rollback()
            raise RepositoryError("Schedule template was not deleted.") from exc

    def _reject_conflicting_future_lessons(
        self, schedule: Schedule, effective_from: date
    ) -> None:
        dates = self.session.scalars(
            select(Lesson.date)
            .where(
                Lesson.schedule_id == schedule.id,
                Lesson.date >= effective_from,
                or_(
                    Lesson.topic.is_not(None) & (func.trim(Lesson.topic) != ""),
                    Lesson.attendances.any(),
                    Lesson.marks.any(),
                    Lesson.comments.any(),
                ),
            )
            .order_by(Lesson.date)
        ).all()
        if dates:
            formatted = ", ".join(sorted({item.isoformat() for item in dates}))
            raise RepositoryError(f"Filled future lessons prevent this change: {formatted}.")

    def _lock_schedule_for_edit(self, schedule: Schedule, effective_from: date) -> None:
        if self.engine.dialect.name == "sqlite":
            self.session.execute(
                text("UPDATE schedules SET id = id WHERE id = :id"), {"id": schedule.id}
            )
        else:
            self.session.execute(
                select(Schedule.id).where(Schedule.id == schedule.id).with_for_update()
            ).first()
            self.session.execute(
                select(Lesson.id)
                .where(Lesson.schedule_id == schedule.id, Lesson.date >= effective_from)
                .with_for_update()
            ).all()
        self.session.refresh(schedule)

    def _commit_or_raise(self, fallback_message: str) -> None:
        try:
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            raise RepositoryError(self._integrity_message(exc)) from exc
        except SQLAlchemyError as exc:
            self.session.rollback()
            raise RepositoryError(fallback_message) from exc
        self.session.expire_all()

    @staticmethod
    def _integrity_message(exc: IntegrityError) -> str:
        message = str(exc.orig)
        if "overlapping group memberships" in message or "ex_group_membership_period" in message:
            return "The student's group membership periods are overlapping."
        if "membership history is immutable" in message:
            return "Recorded group membership history cannot be changed."
        if "archive requires closing membership" in message:
            return "Close the student's current membership before archiving."
        if "groups.name" in message or "UNIQUE constraint failed: groups.name" in message:
            return "A group with this name already exists."
        if "uq_lesson_schedule_date" in message or "lessons.schedule_id, lessons.date" in message:
            return "A lesson for this schedule and date already exists."
        if "uq_schedule_group_link" in message:
            return "This group is already attached to this schedule template."
        if "uq_attendance_student_lesson" in message:
            return "Attendance for this student and lesson already exists."
        if "uq_mark_student_lesson" in message:
            return "Score for this student and lesson already exists."
        if "uq_comment_student_lesson" in message:
            return "Comment for this student and lesson already exists."
        return "The database rejected this change because it duplicates existing data."

    @staticmethod
    def _validate_group_values(name: str, speciality: str | None) -> None:
        if not name:
            raise RepositoryError("Group name is required.")
        if len(name) > 16:
            raise RepositoryError("Group name must be 16 characters or shorter.")
        if speciality is not None and len(speciality) > 128:
            raise RepositoryError("Speciality must be 128 characters or shorter.")

    @staticmethod
    def _validate_student_values(
        first_name: str,
        surname: str,
        email: str | None,
    ) -> None:
        if not first_name or not surname:
            raise RepositoryError("First name and surname are required.")
        if len(first_name) > 128 or len(surname) > 128:
            raise RepositoryError("Student name fields must be 128 characters or shorter.")
        if email is not None and len(email) > 128:
            raise RepositoryError("Email must be 128 characters or shorter.")

    def _ensure_group_name_available(
        self,
        name: str,
        *,
        current_group_id: int | None = None,
    ) -> None:
        existing = self.session.scalar(select(Group).where(Group.name == name))
        if existing is not None and existing.id != current_group_id:
            raise RepositoryError("A group with this name already exists.")

    def _ensure_student_available(
        self,
        group_id: int,
        first_name: str,
        surname: str,
        *,
        current_student_id: int | None = None,
    ) -> None:
        existing = self.session.scalar(
            select(Student).where(
                Student.group_id == group_id,
                Student.first_name == first_name,
                Student.surname == surname,
            )
        )
        if existing is not None and existing.id != current_student_id:
            raise RepositoryError(
                "This student already exists in the selected group."
            )

    def _ensure_schedule_available(
        self,
        groups: list[Group],
        day: str,
        lesson_time: time,
        week_type: str,
        lesson_type: str,
        *,
        current_schedule_id: int | None = None,
        effective_from: date | None = None,
    ) -> None:
        selected_group_ids = {group.id for group in groups}
        schedules = self.session.scalars(
            select(Schedule)
            .where(
                Schedule.day == day,
                Schedule.time == lesson_time,
                Schedule.odd_or_even == week_type,
                Schedule.type == lesson_type,
            )
            .options(selectinload(Schedule.group_links))
        ).all()
        for schedule in schedules:
            if schedule.id == current_schedule_id:
                continue
            if effective_from is not None and (
                schedule.effective_until is not None
                and schedule.effective_until <= effective_from
            ):
                continue
            group_ids = {link.group_id for link in schedule.group_links}
            if group_ids == selected_group_ids:
                raise RepositoryError(
                    "An identical schedule template already exists."
                )

    def export_to_xlsx(self, file_path: str | Path) -> Path:
        self.refresh()
        payload = {
            sheet_name: self.session.scalars(
                select(model).order_by(model.id)
            ).all()
            for sheet_name, model in self._model_by_sheet.items()
        }
        return self.import_export_service.export_to_xlsx(payload, file_path)

    def preview_import_from_xlsx(
            self,
            file_path: str | Path,
            *,
            strategy: str,
            mode: str = "merge",
            sheet_name: str | None = None,
            cell_range: str | None = None,
            entity_type: str | None = None,
    ) -> ImportPreview:
        source_path = Path(file_path)
        if strategy == "smart":
            return self._preview_smart_import(source_path, mode)
        self._reject_legacy_schedule_workbook(source_path)
        if strategy == "template" or (
                strategy == "strict" and not sheet_name and not cell_range
        ):
            return self._preview_template_import(source_path, mode)

        request = ImportRequest(
            source_path=source_path,
            format_name="xlsx",
            strategy_name=strategy,
            destination_name="return",
            sheet_name=sheet_name or None,
            cell_range=cell_range or None,
            entity_type=entity_type or None,
        )
        result = self.import_export_service.import_data(request)
        data, warnings, errors = self._payload_from_import_result(result)
        if strategy == "standard" and not errors:
            for sheet_name, rows in data.items():
                model = self._model_by_sheet[sheet_name]
                for row_number, row in enumerate(rows, start=2):
                    try:
                        normalized = self._normalize_import_row(model, row)
                        if sheet_name in {"group_memberships", "lesson_participants"}:
                            self._validate_history_import_row(sheet_name, normalized)
                        else:
                            self._schema_for_import_entity(sheet_name).model_validate(normalized)
                    except (ValidationError, ValueError, TypeError) as exc:
                        errors.append(f"{sheet_name}, row {row_number}: {exc}")

        return ImportPreview(
            source_path=source_path,
            strategy=strategy,
            mode=mode,
            data=data,
            warnings=warnings,
            errors=errors,
        )

    @staticmethod
    def _reject_legacy_schedule_workbook(
        source_path: Path, *, allow_versioned: bool = True
    ) -> None:
        workbook = load_workbook(source_path, read_only=True, data_only=True)
        try:
            core = {"odd_or_even", "type", "day", "time"}
            version = {"series_key", "revision", "effective_from", "effective_until"}
            for sheet in workbook.worksheets:
                for values in sheet.iter_rows(values_only=True):
                    headers = {str(value).strip().lower() for value in values if value is not None}
                    if core <= headers:
                        if not allow_versioned or not version <= headers:
                            raise RepositoryError(
                                "Schedule import requires versioned columns: "
                                "series_key, revision, effective_from, effective_until. "
                                "The legacy format could overwrite lesson history."
                            )
        finally:
            workbook.close()
    def _preview_smart_import(self, source_path: Path, mode: str) -> ImportPreview:
        data: dict[str, list[dict[str, object]]] = {
            entity_type: [] for entity_type in self._smart_entity_types
        }
        warnings: list[str] = []
        errors: list[str] = []

        for table in self._read_detected_tables(source_path, warnings):
            entity_type = self._select_smart_entity(table)
            if entity_type is None:
                continue
            payloads, table_warnings = self._smart_payloads_from_table(
                entity_type,
                table,
            )
            data[entity_type].extend(payloads)
            warnings.extend(table_warnings)

        if not any(data.values()):
            warnings.append("Smart import did not find groups or students.")

        source_groups = {
            row.get("id"): row.get("name")
            for row in data["groups"] if row.get("id") is not None
        }
        for row_number, row in enumerate(data["students"], start=1):
            group_name = row.get("group_name") or source_groups.get(row.get("group_id"))
            group_id = row.get("group_id")
            if group_name:
                group_id = self.session.scalar(
                    select(Group.id).where(Group.name == str(group_name).strip())
                )
            elif group_id is not None:
                try:
                    group_id = int(group_id)
                except (TypeError, ValueError):
                    errors.append(f"Smart student row {row_number}: invalid group id.")
                    continue
            try:
                self._find_smart_student_target({**row, "group_id": group_id})
            except ValueError as exc:
                errors.append(f"Smart student row {row_number}: {exc}")

        return ImportPreview(
            source_path=source_path,
            strategy="smart",
            mode=mode,
            data=data,
            warnings=warnings,
            errors=errors,
        )

    def _preview_template_import(self, source_path: Path, mode: str) -> ImportPreview:
        data: dict[str, list[dict[str, object]]] = {
            entity_type: [] for entity_type in XLSX_SHEETS_ORDER
        }
        warnings: list[str] = []
        errors: list[str] = []

        for table in self._read_detected_tables(source_path, warnings):
            entity_type = self._select_template_entity(table)
            if entity_type is None:
                continue
            payloads, table_warnings = self._template_payloads_from_table(
                entity_type,
                table,
            )
            data[entity_type].extend(payloads)
            warnings.extend(table_warnings)

        if not any(data.values()):
            warnings.append("Template import did not find matching model tables.")

        return ImportPreview(
            source_path=source_path,
            strategy="template",
            mode=mode,
            data=data,
            warnings=warnings,
            errors=errors,
        )

    def _read_detected_tables(
        self,
        source_path: Path,
        warnings: list[str],
    ) -> list[ExtractedTable]:
        importer = self.import_export_service.import_dispatcher.xlsx_importer
        regions = importer.find_table_candidates(source_path, min_score=0.35)
        seen: set[tuple[str, str]] = set()
        tables: list[ExtractedTable] = []

        for region in sorted(
            regions,
            key=lambda item: (item.sheet.lower(), item.min_row, item.min_col),
        ):
            key = (region.sheet, region.range)
            if key in seen:
                continue
            seen.add(key)
            try:
                tables.append(
                    importer.read_table_range(
                        source_path,
                        region.sheet,
                        region.range,
                    )
                )
            except ValueError as exc:
                warnings.append(
                    f"Skipped table {region.sheet}!{region.range}: {exc}"
                )

        return tables

    def _select_smart_entity(self, table: ExtractedTable) -> str | None:
        scored = [
            (self._smart_header_score(entity_type, table.headers), entity_type)
            for entity_type in self._smart_entity_types
        ]
        score, entity_type = max(scored, key=lambda item: item[0])
        return entity_type if score > 0 else None

    def _smart_header_score(
        self,
        entity_type: str,
        headers: tuple[str, ...],
    ) -> float:
        direct_index = self._direct_alias_index.get(entity_type, {})
        reference_index = self._reference_alias_index.get(entity_type, {})
        direct_fields: set[str] = set()
        reference_fields: set[str] = set()

        for header in headers:
            normalized_header = normalize_tabular_header(header)
            if normalized_header in direct_index:
                direct_fields.add(direct_index[normalized_header])
            if normalized_header in reference_index:
                reference_key, field_name = reference_index[normalized_header]
                reference_fields.add(f"{reference_key}.{field_name}")

        if entity_type == "groups":
            if "name" not in direct_fields:
                return 0
        elif entity_type == "students":
            has_group = "group_id" in direct_fields or "group.name" in reference_fields
            if not {"surname", "first_name"}.issubset(direct_fields) or not has_group:
                return 0

        matched_count = len(direct_fields) + len(reference_fields)
        return matched_count / max(len(headers), 1)

    def _smart_payloads_from_table(
        self,
        entity_type: str,
        table: ExtractedTable,
    ) -> tuple[list[dict[str, object]], list[str]]:
        direct_index = self._direct_alias_index.get(entity_type, {})
        reference_index = self._reference_alias_index.get(entity_type, {})
        payloads: list[dict[str, object]] = []
        warnings: list[str] = []

        for row_number, row in enumerate(table.rows, start=2):
            payload: dict[str, object] = {}
            for header, raw_value in row.items():
                value = self._clean_import_cell(raw_value)
                if value is None:
                    continue

                normalized_header = normalize_tabular_header(header)
                if normalized_header in direct_index:
                    payload[direct_index[normalized_header]] = value
                    continue

                if normalized_header in reference_index:
                    reference_key, field_name = reference_index[normalized_header]
                    if entity_type == "students" and reference_key == "group" and field_name == "name":
                        payload["group_name"] = value

            if entity_type == "groups":
                if not payload.get("name"):
                    warnings.append(
                        f"Skipped {table.sheet}!{table.range} row {row_number}: group name is required."
                    )
                    continue
                schema = CREATE_SCHEMA_BY_ENTITY["groups"]
                try:
                    validated = schema.model_validate(payload)
                except ValidationError as exc:
                    warnings.append(
                        f"Skipped {table.sheet}!{table.range} row {row_number}: "
                        + "; ".join(error["msg"] for error in exc.errors())
                    )
                    continue
                payloads.append(validated.model_dump(exclude_unset=True))
                continue

            missing = [
                field_name
                for field_name in ("surname", "first_name")
                if not payload.get(field_name)
            ]
            if not payload.get("group_id") and not payload.get("group_name"):
                missing.append("group_id/group")
            if missing:
                warnings.append(
                    f"Skipped {table.sheet}!{table.range} row {row_number}: "
                    f"missing required {', '.join(missing)}."
                )
                continue
            payloads.append(payload)

        return payloads, warnings

    def _select_template_entity(self, table: ExtractedTable) -> str | None:
        headers = set(table.headers)
        if {"student_id", "lesson_id", "data"}.issubset(headers):
            sheet_name = table.sheet.lower()
            if "comment" in sheet_name:
                return "comments"
            if "mark" in sheet_name or "score" in sheet_name:
                return "marks"
            data_values = [
                row.get("data")
                for row in table.rows
                if self._clean_import_cell(row.get("data")) is not None
            ]
            if any(not self._can_parse_int(value) for value in data_values):
                return "comments"
            return "marks"

        best_score = 0.0
        best_entity: str | None = None

        for entity_type in XLSX_SHEETS_ORDER:
            known_headers = set(XLSX_COLUMNS_BY_SHEET[entity_type])
            required_headers = set(XLSX_REQUIRED_COLUMNS_BY_SHEET[entity_type])
            if not headers or not headers.issubset(known_headers):
                continue
            if not required_headers.issubset(headers):
                continue

            score = len(headers) / max(len(known_headers), 1)
            if table.sheet.lower() == entity_type.lower():
                score += 1
            if score > best_score:
                best_score = score
                best_entity = entity_type

        return best_entity

    @staticmethod
    def _can_parse_int(value: object) -> bool:
        try:
            int(value)
        except (TypeError, ValueError):
            return False
        return True

    def _template_payloads_from_table(
        self,
        entity_type: str,
        table: ExtractedTable,
    ) -> tuple[list[dict[str, object]], list[str]]:
        model = self._model_by_sheet[entity_type]
        schema = self._schema_for_import_entity(entity_type)
        required_fields = XLSX_REQUIRED_COLUMNS_BY_SHEET[entity_type]
        payloads: list[dict[str, object]] = []
        warnings: list[str] = []

        for row_number, row in enumerate(table.rows, start=2):
            try:
                normalized = self._normalize_import_row(model, row)
            except (ValueError, TypeError) as exc:
                warnings.append(
                    f"Skipped {table.sheet}!{table.range} row {row_number}: {exc}"
                )
                continue

            missing = [
                field_name
                for field_name in required_fields
                if normalized.get(field_name) in (None, "")
            ]
            if missing:
                warnings.append(
                    f"Skipped {table.sheet}!{table.range} row {row_number}: "
                    f"missing required {', '.join(missing)}."
                )
                continue

            try:
                schema.model_validate(normalized)
            except ValidationError as exc:
                warnings.append(
                    f"Skipped {table.sheet}!{table.range} row {row_number}: "
                    + "; ".join(error["msg"] for error in exc.errors())
                )
                continue
            payloads.append(normalized)

        return payloads, warnings

    @staticmethod
    def _schema_for_import_entity(entity_type: str):
        schema = CREATE_SCHEMA_BY_ENTITY.get(entity_type)
        if schema is not None:
            return schema
        return STRICT_CREATE_SCHEMA_BY_ENTITY[entity_type]

    @staticmethod
    def _clean_import_cell(value: object) -> object | None:
        if value is None:
            return None
        if isinstance(value, str):
            value = value.strip()
            if not value:
                return None
        return value
    def import_from_preview(self, preview: ImportPreview) -> dict[str, int]:
        if preview.errors:
            raise RepositoryError(preview.errors[0])
        if preview.total_rows == 0:
            raise RepositoryError("The selected import does not contain rows.")

        history_sheets = ("group_memberships", "lesson_participants")
        history_restore = any(name in preview.data for name in history_sheets)
        if history_restore:
            expected = set(XLSX_SHEETS_ORDER) | set(history_sheets)
            if preview.strategy != "standard" or set(preview.data) != expected:
                raise RepositoryError("History restoration requires a complete standard workbook.")

        schedule_sheets = {
            "schedules", "schedule_group_links", "lessons", "attendances", "marks", "comments"
        }
        if any(preview.data.get(name) for name in schedule_sheets):
            if preview.strategy == "smart" or not preview.data.get("schedules"):
                raise RepositoryError("Schedule data requires a complete versioned workbook.")
            for row in preview.data["schedules"]:
                if any(row.get(field) in (None, "") for field in (
                    "series_key", "revision", "effective_from"
                )):
                    raise RepositoryError("Legacy schedule rows cannot be imported safely.")
            if any(self.session.scalar(select(model.id).limit(1)) is not None
                   for model in self._model_by_sheet.values()):
                raise RepositoryError(
                    "Versioned schedule data can only be imported into an empty database."
                )

        replace_existing = preview.mode == "replace"
        if replace_existing and self.session.scalar(select(Lesson.id).limit(1)) is not None:
            raise RepositoryError("Replacing this database would delete lesson history.")
        if replace_existing and any(
            self.session.scalar(select(model.id).limit(1)) is not None
            for model in self._model_by_sheet.values()
        ):
            raise RepositoryError(
                "Replacing a populated database would delete history; restore into an empty database."
            )
        imported_counts = {sheet_name: 0 for sheet_name in preview.data}
        imported_ids: dict[str, dict[int, int]] = {
            sheet_name: {} for sheet_name in (*XLSX_SHEETS_ORDER, *history_sheets)
        }
        try:
            if history_restore:
                self.session.rollback()
                connection = self.session.connection()
                if self.engine.dialect.name == "sqlite":
                    connection.exec_driver_sql("BEGIN IMMEDIATE")
                else:
                    connection.exec_driver_sql("LOCK TABLE students IN ACCESS EXCLUSIVE MODE")
                if any(self.session.scalar(select(model.id).limit(1)) is not None
                       for model in self._model_by_sheet.values()):
                    raise RepositoryError("History can only be restored into an empty database.")
            if replace_existing:
                self._clear_database_in_session()

            if history_restore:
                set_membership_import_mode(self.session.connection(), enabled=True)

            for sheet_name in (*XLSX_SHEETS_ORDER, *history_sheets):
                rows = preview.data.get(sheet_name, [])
                model = self._model_by_sheet.get(sheet_name)
                if model is None:
                    continue
                for row in rows:
                    normalized = self._prepare_import_row(sheet_name, model, row)
                    if not normalized:
                        continue
                    source_id = normalized.pop("id", None)
                    for field_name, parent_sheet in self._import_references.get(sheet_name, {}).items():
                        source_reference = normalized.get(field_name)
                        if source_reference in imported_ids[parent_sheet]:
                            normalized[field_name] = imported_ids[parent_sheet][source_reference]
                    existing = None
                    if not replace_existing:
                        if preview.strategy == "smart" and sheet_name == "students":
                            existing = self._find_smart_student_target(normalized)
                        else:
                            if sheet_name == "students" and source_id is not None:
                                id_match = self.session.get(Student, source_id)
                                if id_match is not None and (
                                    id_match.surname == normalized.get("surname")
                                    and id_match.first_name == normalized.get("first_name")
                                    and (not normalized.get("bmstu_email") or
                                         not id_match.bmstu_email or
                                         id_match.bmstu_email == normalized["bmstu_email"])
                                ):
                                    existing = id_match
                            if existing is None:
                                existing = self._find_import_target(sheet_name, normalized)
                    if existing is None:
                        existing = model(**normalized)
                        self.session.add(existing)
                    else:
                        self._update_import_target(existing, normalized)
                    self.session.flush()
                    if source_id is not None:
                        previous_id = imported_ids[sheet_name].setdefault(source_id, existing.id)
                        if previous_id != existing.id:
                            raise ValueError(
                                f"Conflicting source id {source_id} in {sheet_name}."
                            )
                    imported_counts[sheet_name] += 1

            if history_restore:
                self._validate_restored_history()
                set_membership_import_mode(self.session.connection(), enabled=False)

            for lesson in self.session.scalars(select(Lesson).options(selectinload(Lesson.schedule))):
                if lesson.date < lesson.schedule.effective_from or (
                    lesson.schedule.effective_until is not None
                    and lesson.date >= lesson.schedule.effective_until
                ):
                    raise ValueError(
                        f"Lesson {lesson.id} is outside schedule version period."
                    )

            self.session.commit()
        except RepositoryError:
            self.session.rollback()
            raise
        except IntegrityError as exc:
            self.session.rollback()
            raise RepositoryError(self._integrity_message(exc)) from exc
        except (SQLAlchemyError, ValueError, TypeError) as exc:
            self.session.rollback()
            raise RepositoryError(f"Import failed: {exc}") from exc

        self.session.expire_all()
        return {name: count for name, count in imported_counts.items() if count}

    def _validate_restored_history(self) -> None:
        for student in self.session.scalars(select(Student).options(selectinload(Student.memberships))):
            current = [item for item in student.memberships if item.end_date is None]
            if student.status == "active":
                if student.archived_at is not None or len(current) != 1 or current[0].group_id != student.group_id:
                    raise ValueError(f"Active student {student.id} has no matching open membership.")
            elif student.status == "archived":
                if (current or student.archived_at is None
                        or not (student.archive_reason or "").strip()):
                    raise ValueError(f"Archived student {student.id} has an invalid membership.")
            else:
                raise ValueError(f"Student {student.id} has an unknown status.")
        evidence = set(self.session.execute(
            select(Attendance.lesson_id, Attendance.student_id)
        ).all())
        evidence.update(self.session.execute(select(Mark.lesson_id, Mark.student_id)).all())
        evidence.update(self.session.execute(select(Comment.lesson_id, Comment.student_id)).all())
        participants = set(self.session.execute(
            select(LessonParticipant.lesson_id, LessonParticipant.student_id)
        ).all())
        if not evidence <= participants:
            raise ValueError("Result records are missing lesson participation evidence.")

    def clear_database(self) -> None:
        try:
            self._clear_database_in_session()
            self.session.commit()
        except RepositoryError:
            self.session.rollback()
            raise
        except SQLAlchemyError as exc:
            self.session.rollback()
            raise RepositoryError("Database was not cleared.") from exc
        self.session.expire_all()

    def _clear_database_in_session(self) -> None:
        if self.session.scalar(select(Lesson.id).limit(1)) is not None or self.session.scalar(
            select(Schedule.id).where(Schedule.effective_until.is_not(None)).limit(1)
        ) is not None:
            raise RepositoryError("Database contains lesson history; clearing it is not allowed.")
        for model in self._delete_order:
            self.session.execute(delete(model))
        if DATABASE_URL.startswith("sqlite"):
            sequence_exists = self.session.scalar(
                text(
                    "SELECT name FROM sqlite_master "
                    "WHERE type='table' AND name='sqlite_sequence'"
                )
            )
            if sequence_exists:
                table_names = ", ".join(
                    f"'{model.__tablename__}'" for model in self._delete_order
                )
                self.session.execute(
                    text(f"DELETE FROM sqlite_sequence WHERE name IN ({table_names})")
                )

    @staticmethod
    def _payload_from_import_result(
        result: object,
    ) -> tuple[dict[str, list[dict[str, object]]], list[str], list[str]]:
        if isinstance(result, TabularImportResult):
            return result.data, result.warnings, result.errors
        if isinstance(result, (ImportProcessingResult, StrictImportResult)):
            return (
                {result.entity_type: list(result.create_payloads)},
                list(result.warnings),
                list(result.errors),
            )
        if isinstance(result, DataProcessingResult):
            return (
                {result.entity_type: list(result.create_payloads)},
                list(result.warnings),
                list(result.errors),
            )
        raise RepositoryError("Unsupported import result.")

    @classmethod
    def _normalize_import_row(
        cls,
        model: type[Base],
        row: dict[str, object],
    ) -> dict[str, object]:
        normalized: dict[str, object] = {}
        for column in model.__table__.columns:
            if column.name not in row:
                continue
            value = row[column.name]
            if value == "":
                value = None
            if value is None and (
                column.name == "id" or column.nullable
                or column.name in {"created_at", "updated_at"}
            ):
                continue
            normalized[column.name] = cls._normalize_import_value(
                model,
                column.name,
                value,
            )
        return normalized

    @staticmethod
    def _validate_history_import_row(sheet_name: str, row: dict[str, object]) -> None:
        missing = [name for name in XLSX_REQUIRED_COLUMNS_BY_SHEET[sheet_name]
                   if row.get(name) is None]
        if missing:
            raise ValueError("Missing required values: " + ", ".join(missing))
        if sheet_name == "group_memberships":
            end = row.get("end_date")
            if end is not None and end < row["start_date"]:
                raise ValueError("Membership end predates its start.")
            if row["origin"] not in {"recorded", "migrated_unknown"}:
                raise ValueError("Unknown membership origin.")
        elif row["source"] not in {"snapshot", "evidence"}:
            raise ValueError("Unknown participant source.")

    @staticmethod
    def _normalize_import_value(
        model: type[Base],
        column_name: str,
        value: object,
    ) -> object:
        if value is None:
            return None
        if column_name in {"id", "group_id", "schedule_id", "student_id", "lesson_id", "revision"}:
            return int(value)
        if model is Mark and column_name == "data":
            return int(value)
        if column_name in {"is_assessment", "is_visited", "is_archived", "participants_complete"}:
            if isinstance(value, bool):
                return value
            normalized = str(value).strip().lower()
            if normalized in {"1", "true", "yes", "y", "да"}:
                return True
            if normalized in {"0", "false", "no", "n", "нет"}:
                return False
            raise ValueError(f"Invalid boolean value: {value!r}")
        if column_name in {"date", "effective_from", "effective_until", "start_date", "end_date", "known_from", "archived_at"}:
            if isinstance(value, datetime):
                return value.date()
            if isinstance(value, date):
                return value
            return date.fromisoformat(str(value).strip())
        if column_name == "time":
            if isinstance(value, datetime):
                return value.time().replace(microsecond=0)
            if isinstance(value, time):
                return value.replace(microsecond=0)
            text_value = str(value).strip()
            for fmt in ("%H:%M:%S", "%H:%M"):
                try:
                    return datetime.strptime(text_value, fmt).time()
                except ValueError:
                    continue
            raise ValueError(f"Invalid time value: {value!r}")
        if column_name in {"created_at", "updated_at"}:
            if isinstance(value, datetime):
                return value
            return datetime.fromisoformat(str(value).strip())
        return value

    def _prepare_import_row(
        self,
        sheet_name: str,
        model: type[Base],
        row: dict[str, object],
    ) -> dict[str, object]:
        group_name = None
        if sheet_name == "students":
            group_name = row.get("group_name")

        normalized = self._normalize_import_row(model, row)
        if sheet_name == "students" and normalized.get("group_id") is None:
            if group_name is None:
                raise ValueError("Student row does not contain group_id or group name.")
            group = self._get_or_create_group_by_name(str(group_name))
            normalized["group_id"] = group.id
        return normalized

    def _get_or_create_group_by_name(self, name: str) -> Group:
        clean_name = name.strip()
        self._validate_group_values(clean_name, None)
        group = self.session.scalar(select(Group).where(Group.name == clean_name))
        if group is None:
            group = Group(name=clean_name, speciality=None)
            self.session.add(group)
            self.session.flush()
        return group

    def _find_import_target(
        self,
        sheet_name: str,
        row: dict[str, object],
    ) -> Base | None:
        model = self._model_by_sheet[sheet_name]
        if sheet_name == "groups":
            return self.session.scalar(
                select(Group).where(Group.name == row.get("name"))
            )
        if sheet_name == "students":
            exact = self.session.scalar(
                select(Student).where(
                    Student.group_id == row.get("group_id"),
                    Student.first_name == row.get("first_name"),
                    Student.surname == row.get("surname"),
                )
            )
            if exact is not None:
                return exact
            if self.session.scalar(select(Student.id).where(
                Student.first_name == row.get("first_name"),
                Student.surname == row.get("surname"),
            ).limit(1)) is not None:
                raise ValueError(
                    "Student with this name belongs to another group; a transfer date is required."
                )
            return None
        if sheet_name == "schedules":
            return self.session.scalar(
                select(Schedule).where(
                    Schedule.series_key == row.get("series_key"),
                    Schedule.revision == row.get("revision"),
                )
            )
        if sheet_name == "schedule_group_links":
            return self.session.scalar(
                select(ScheduleGroupLink).where(
                    ScheduleGroupLink.group_id == row.get("group_id"),
                    ScheduleGroupLink.schedule_id == row.get("schedule_id"),
                )
            )
        if sheet_name == "lessons":
            return self.session.scalar(
                select(Lesson).where(
                    Lesson.schedule_id == row.get("schedule_id"),
                    Lesson.date == row.get("date"),
                )
            )
        if sheet_name == "attendances":
            return self.session.scalar(
                select(Attendance).where(
                    Attendance.student_id == row.get("student_id"),
                    Attendance.lesson_id == row.get("lesson_id"),
                )
            )
        if sheet_name == "marks":
            return self.session.scalar(
                select(Mark).where(
                    Mark.student_id == row.get("student_id"),
                    Mark.lesson_id == row.get("lesson_id"),
                )
            )
        if sheet_name == "comments":
            return self.session.scalar(
                select(Comment).where(
                    Comment.student_id == row.get("student_id"),
                    Comment.lesson_id == row.get("lesson_id"),
                )
            )
        return None

    def _find_smart_student_target(self, row: dict[str, object]) -> Student | None:
        strong_matches: list[Student] = []
        for field_name in ("personal_data", "bmstu_email"):
            value = row.get(field_name)
            if not value:
                continue
            column = getattr(Student, field_name)
            matches = self.session.scalars(select(Student).where(column == value)).all()
            if len(matches) > 1:
                raise ValueError(f"multiple students have the same {field_name}.")
            strong_matches.extend(matches)

        if len({student.id for student in strong_matches}) > 1:
            raise ValueError("student number and email identify different students.")
        strong_match = strong_matches[0] if strong_matches else None
        patronymic = row.get("patronymic")
        if (
            strong_match is not None
            and patronymic
            and strong_match.patronymic
            and strong_match.patronymic != patronymic
        ):
            raise ValueError("patronymic conflicts with the identified student.")

        name_matches: list[Student] = []
        if row.get("group_id") and row.get("surname") and row.get("first_name"):
            name_matches = self.session.scalars(
                select(Student).where(
                    Student.group_id == row["group_id"],
                    Student.surname == row["surname"],
                    Student.first_name == row["first_name"],
                )
            ).all()
            if patronymic and name_matches:
                name_matches = [
                    student for student in name_matches
                    if student.patronymic == patronymic
                ]
                if not name_matches and strong_match is None:
                    raise ValueError(
                        "patronymic differs from existing students with this name and group; "
                        "add a student number or email."
                    )

        if strong_match is not None:
            if name_matches and strong_match.id not in {student.id for student in name_matches}:
                raise ValueError("name and group identify a different student.")
            return strong_match
        if len(name_matches) > 1:
            raise ValueError("multiple students match the name and group; add a student number or email.")
        if name_matches:
            return name_matches[0]
        if row.get("surname") and row.get("first_name") and self.session.scalar(
            select(Student.id).where(
                Student.surname == row["surname"],
                Student.first_name == row["first_name"],
            ).limit(1)
        ) is not None:
            raise ValueError("Student may already belong to another group; a transfer date is required.")
        return None

    @staticmethod
    def _update_import_target(target: Base, row: dict[str, object]) -> None:
        for field_name, value in row.items():
            if field_name == "id" or value is None:
                continue
            if isinstance(target, Student) and field_name == "group_id" and value != target.group_id:
                raise ValueError(
                    "Student group differs from the database; transfer date is required."
                )
            if hasattr(target, field_name):
                setattr(target, field_name, value)

    def _import_row_exists(self, sheet_name: str, row: dict[str, object]) -> bool:
        model = self._model_by_sheet[sheet_name]
        row_id = row.get("id")
        if row_id is not None and self.session.get(model, row_id) is not None:
            return True
        if sheet_name == "groups":
            return self.session.scalar(
                select(Group.id).where(Group.name == row.get("name"))
            ) is not None
        if sheet_name == "students":
            return self.session.scalar(
                select(Student.id).where(
                    Student.group_id == row.get("group_id"),
                    Student.first_name == row.get("first_name"),
                    Student.surname == row.get("surname"),
                )
            ) is not None
        if sheet_name == "schedules":
            return self.session.scalar(
                select(Schedule.id).where(
                    Schedule.day == row.get("day"),
                    Schedule.time == row.get("time"),
                    Schedule.odd_or_even == row.get("odd_or_even"),
                    Schedule.type == row.get("type"),
                )
            ) is not None
        if sheet_name == "schedule_group_links":
            return self.session.scalar(
                select(ScheduleGroupLink.id).where(
                    ScheduleGroupLink.group_id == row.get("group_id"),
                    ScheduleGroupLink.schedule_id == row.get("schedule_id"),
                )
            ) is not None
        if sheet_name == "lessons":
            return self.session.scalar(
                select(Lesson.id).where(
                    Lesson.schedule_id == row.get("schedule_id"),
                    Lesson.date == row.get("date"),
                )
            ) is not None
        if sheet_name == "attendances":
            return self.session.scalar(
                select(Attendance.id).where(
                    Attendance.student_id == row.get("student_id"),
                    Attendance.lesson_id == row.get("lesson_id"),
                )
            ) is not None
        if sheet_name == "marks":
            return self.session.scalar(
                select(Mark.id).where(
                    Mark.student_id == row.get("student_id"),
                    Mark.lesson_id == row.get("lesson_id"),
                )
            ) is not None
        if sheet_name == "comments":
            return self.session.scalar(
                select(Comment.id).where(
                    Comment.student_id == row.get("student_id"),
                    Comment.lesson_id == row.get("lesson_id"),
                )
            ) is not None
        return False

    def _get_or_create_group(self, name: str, speciality: str) -> Group:
        group = self.session.scalar(select(Group).where(Group.name == name))
        if group is None:
            group = Group(name=name, speciality=speciality)
            self.session.add(group)
            self.session.flush()
        return group

    def _get_or_create_student(
        self,
        group: Group,
        surname: str,
        first_name: str,
    ) -> Student:
        student = self.session.scalar(
            select(Student).where(
                Student.group_id == group.id,
                Student.surname == surname,
                Student.first_name == first_name,
            )
        )
        if student is None:
            student = Student(
                group_id=group.id,
                surname=surname,
                first_name=first_name,
                patronymic=None,
                personal_data=None,
                bmstu_email=f"{first_name.lower()}.{surname.lower()}@bmstu.example",
            )
            self.session.add(student)
            self.session.flush()
        return student

    def _get_or_create_schedule(self, spec: dict[str, object]) -> Schedule:
        schedule = self.session.scalar(
            select(Schedule).where(
                Schedule.day == spec["day"],
                Schedule.time == spec["time"],
                Schedule.odd_or_even == spec["week_type"],
                Schedule.type == spec["type"],
            )
        )
        if schedule is None:
            schedule = Schedule(
                odd_or_even=spec["week_type"],
                type=spec["type"],
                is_assessment=bool(spec["is_assessment"]),
                day=spec["day"],
                time=spec["time"],
            )
            self.session.add(schedule)
            self.session.flush()
        return schedule

    def _get_or_create_schedule_link(
        self,
        group: Group,
        schedule: Schedule,
    ) -> ScheduleGroupLink:
        link = self.session.scalar(
            select(ScheduleGroupLink).where(
                ScheduleGroupLink.group_id == group.id,
                ScheduleGroupLink.schedule_id == schedule.id,
            )
        )
        if link is None:
            link = ScheduleGroupLink(group_id=group.id, schedule_id=schedule.id)
            self.session.add(link)
            self.session.flush()
        return link
