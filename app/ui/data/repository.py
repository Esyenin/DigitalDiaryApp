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
from sqlalchemy import create_engine, delete, event, select, text
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
    Lesson,
    Mark,
    Schedule,
    ScheduleGroupLink,
    Student,
)
from app.ui.data.calendar import SemesterSettings, day_index, week_type_for_number


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
    _deferred_import_key = "__deferred_import__"
    _model_by_sheet = {
        "groups": Group,
        "schedules": Schedule,
        "students": Student,
        "schedule_group_links": ScheduleGroupLink,
        "lessons": Lesson,
        "attendances": Attendance,
        "marks": Mark,
        "comments": Comment,
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
        Base.metadata.create_all(bind=self.engine)
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

    def list_groups(self) -> list[Group]:
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
        return list(self.session.scalars(stmt).all())

    def list_students(self, group_id: int | None = None) -> list[Student]:
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

    def list_schedules(self) -> list[Schedule]:
        self.refresh()
        stmt = (
            select(Schedule)
            .options(
                selectinload(Schedule.group_links).selectinload(ScheduleGroupLink.group),
                selectinload(Schedule.lessons),
            )
            .order_by(Schedule.day, Schedule.time)
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
        students: dict[int, Student] = {}
        for link in lesson.schedule.group_links:
            for student in link.group.students:
                students[student.id] = student
        return sorted(students.values(), key=lambda item: (item.surname, item.first_name))

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
        group = self.get_group(student.group_id)
        if group is None:
            return []

        lesson_ids: set[int] = set()
        for link in group.schedule_links:
            for lesson in link.schedule.lessons:
                lesson_ids.add(lesson.id)

        lessons = [
            lesson
            for lesson_id in lesson_ids
            if (lesson := self.get_lesson(lesson_id)) is not None
        ]
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

    def lesson_attendance_summary(self, lesson: Lesson) -> dict[str, int]:
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
            "absent": max(total - present, 0),
            "rate": round(present / total * 100) if total else 0,
        }

    def group_stats(self, group: Group) -> dict[str, int | str]:
        students = list(group.students)
        lessons = self._completed_lessons_for_group(group)
        lesson_ids = {lesson.id for lesson in lessons}
        assessment_lessons = [
            lesson for lesson in lessons if lesson.schedule.is_assessment
        ]
        assessment_ids = {lesson.id for lesson in assessment_lessons}
        lab_ids = {
            lesson.id
            for lesson in assessment_lessons
            if lesson.schedule.type == "Lab Work"
        }
        test_ids = {
            lesson.id
            for lesson in assessment_lessons
            if lesson.schedule.type == "Control Work"
        }

        attendance_slots = len(students) * len(lessons)
        present = sum(
            1
            for student in students
            for item in student.attendances
            if item.lesson_id in lesson_ids and item.is_visited
        )
        attendance_rate = (
            round(present / attendance_slots * 100) if attendance_slots else 0
        )

        overall_slots = len(students) * len(assessment_lessons)
        lab_slots = len(students) * len(lab_ids)
        test_slots = len(students) * len(test_ids)
        overall_sum = sum(
            mark.data
            for student in students
            for mark in student.marks
            if mark.lesson_id in assessment_ids
        )
        lab_sum = sum(
            mark.data
            for student in students
            for mark in student.marks
            if mark.lesson_id in lab_ids
        )
        test_sum = sum(
            mark.data
            for student in students
            for mark in student.marks
            if mark.lesson_id in test_ids
        )
        overall = round(overall_sum / overall_slots) if overall_slots else 0
        lab_average = round(lab_sum / lab_slots) if lab_slots else 0
        test_average = round(test_sum / test_slots) if test_slots else "-"
        return {
            "overall": overall,
            "lab": lab_average,
            "test": test_average,
            "attendance": attendance_rate,
            "students": len(students),
            "status": self._performance_status(
                overall,
                attendance_rate,
                overall_slots,
                attendance_slots,
            ),
        }

    def student_stats(self, student: Student) -> dict[str, int | str]:
        lessons = self._completed_lessons_for_student(student)
        lesson_ids = {lesson.id for lesson in lessons}
        assessment_lessons = [
            lesson for lesson in lessons if lesson.schedule.is_assessment
        ]
        assessment_ids = {lesson.id for lesson in assessment_lessons}
        lab_ids = {
            lesson.id
            for lesson in assessment_lessons
            if lesson.schedule.type == "Lab Work"
        }
        test_ids = {
            lesson.id
            for lesson in assessment_lessons
            if lesson.schedule.type == "Control Work"
        }

        present = sum(
            1
            for attendance_item in student.attendances
            if attendance_item.lesson_id in lesson_ids and attendance_item.is_visited
        )
        attendance = round(present / len(lessons) * 100) if lessons else 0
        overall_sum = sum(
            mark.data for mark in student.marks if mark.lesson_id in assessment_ids
        )
        lab_sum = sum(mark.data for mark in student.marks if mark.lesson_id in lab_ids)
        test_sum = sum(mark.data for mark in student.marks if mark.lesson_id in test_ids)
        return {
            "overall": (
                round(overall_sum / len(assessment_lessons))
                if assessment_lessons
                else "-"
            ),
            "lab": round(lab_sum / len(lab_ids)) if lab_ids else "-",
            "test": round(test_sum / len(test_ids)) if test_ids else "-",
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
        if student.group is None:
            return []
        return self._completed_lessons_for_group(student.group)

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
        self.session.delete(group)
        self._commit_or_raise("Group was not deleted.")

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
        self.session.delete(student)
        self._commit_or_raise("Student was not deleted.")

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
    ) -> Schedule:
        self._ensure_schedule_available(
            groups,
            day,
            lesson_time,
            week_type,
            lesson_type,
        )
        schedule = Schedule(
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
    ) -> None:
        self._ensure_schedule_available(
            groups,
            day,
            lesson_time,
            week_type,
            lesson_type,
            current_schedule_id=schedule.id,
        )
        regenerate_lessons = (
            schedule.day != day or schedule.odd_or_even != week_type
        )
        schedule.day = day
        schedule.time = lesson_time
        schedule.odd_or_even = week_type
        schedule.type = lesson_type
        schedule.is_assessment = is_assessment
        for link in list(schedule.group_links):
            self.session.delete(link)
        self.session.flush()
        for group in groups:
            self.session.add(ScheduleGroupLink(group_id=group.id, schedule_id=schedule.id))
        if regenerate_lessons:
            for lesson in list(schedule.lessons):
                self.session.delete(lesson)
            self.session.flush()
        self.ensure_lessons_for_schedule(schedule, topic, settings)
        self._commit_or_raise("Schedule template was not updated.")

    def delete_schedule(self, schedule: Schedule) -> None:
        self.session.delete(schedule)
        self._commit_or_raise("Schedule template was not deleted.")

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

        # Новый Smart Import вместо старого _preview_smart_import.
        #
        # Важно:
        # preview здесь ничего не пишет в БД.
        # Он только сообщает старому import dialog, что файл принят
        # и при подтверждении нужно запускать новый smart importer.
        if strategy == "smart":
            return self._deferred_import_preview(
                source_path=source_path,
                strategy=strategy,
                mode=mode,
                importer="smart",
                description=(
                    "Smart import will automatically scan the workbook and import "
                    "recognized groups/students or supported multi-sheet data."
                ),
            )

        # Новый Table Import вместо старого _preview_template_import.
        #
        # Сохраняем старое условие:
        # раньше template и strict без sheet/range уходили в template/table-preview.
        if strategy == "template" or (
                strategy == "strict" and not sheet_name and not cell_range
        ):
            return self._deferred_import_preview(
                source_path=source_path,
                strategy=strategy,
                mode=mode,
                importer="table",
                description=(
                    "Table import will search human-readable tables and import "
                    "recognized groups, students and marks."
                ),
            )

        # Стандартный импорт оставляем старым.
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

        return ImportPreview(
            source_path=source_path,
            strategy=strategy,
            mode=mode,
            data=data,
            warnings=warnings,
            errors=errors,
        )
    def _deferred_import_preview(
        self,
        *,
        source_path: Path,
        strategy: str,
        mode: str,
        importer: str,
        description: str,
    ) -> ImportPreview:
        """
        Возвращает preview-заглушку для новых импортёров.

        Старый UI ожидает ImportPreview, но новые importers сами читают файл
        и сами пишут в БД только на этапе import_from_preview.
        Поэтому preview здесь нужен только для совместимости со старым dialog.
        """
        return ImportPreview(
            source_path=source_path,
            strategy=strategy,
            mode=mode,
            data={
                self._deferred_import_key: [
                    {
                        "importer": importer,
                        "description": description,
                    }
                ]
            },
            warnings=[
                description,
                "Import will be executed after confirmation.",
            ],
            errors=[],
        )
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
    def _deferred_importer_from_preview(self, preview: ImportPreview) -> str | None:
        deferred_rows = preview.data.get(self._deferred_import_key)

        if not deferred_rows:
            return None

        first_row = deferred_rows[0]

        importer = first_row.get("importer")
        if isinstance(importer, str):
            return importer

        return None
    def _import_smart_from_preview(self, preview: ImportPreview) -> dict[str, int]:
        """
        Новый Smart Import, запускаемый через старый import dialog.

        Заменяет старый strategy == "smart".
        """
        if preview.mode == "replace":
            self.clear_database()

        result = import_xlsx_with_multisheet_smart_import(preview.source_path)

        if not result.is_valid:
            raise RepositoryError(
                self._format_external_import_report(
                    title="Smart import failed.",
                    created=result.created,
                    warnings=result.warnings,
                    errors=result.errors,
                )
            )

        self.refresh()

        return {
            entity_type: count
            for entity_type, count in result.created.items()
            if count
        }

    def _import_table_from_preview(self, preview: ImportPreview) -> dict[str, int]:
        """
        Новый Table Import, запускаемый через старый import dialog.

        Заменяет старый template/table import.
        """
        if preview.mode == "replace":
            self.clear_database()

        result = import_xlsx_with_human_table_import(preview.source_path)

        if not result.is_valid:
            raise RepositoryError(
                self._format_external_import_report(
                    title="Table import failed.",
                    created=result.created,
                    warnings=result.warnings,
                    errors=result.errors,
                )
            )

        self.refresh()

        return {
            entity_type: count
            for entity_type, count in result.created.items()
            if count
        }
    @staticmethod
    def _format_external_import_report(
        *,
        title: str,
        created: dict[str, int],
        warnings: list[str],
        errors: list[str],
    ) -> str:
        lines: list[str] = [title]

        if created:
            lines.append("")
            lines.append("Создано:")
            for entity_type, count in created.items():
                lines.append(f"{entity_type}: {count}")

        if warnings:
            lines.append("")
            lines.append("Предупреждения:")
            for warning in warnings:
                lines.append(f"- {warning}")

        if errors:
            lines.append("")
            lines.append("Ошибки:")
            for error in errors:
                lines.append(f"- {error}")

        return "\n".join(lines)
    def import_from_preview(self, preview: ImportPreview) -> dict[str, int]:
        deferred_importer = self._deferred_importer_from_preview(preview)

        if deferred_importer == "smart":
            return self._import_smart_from_preview(preview)

        if deferred_importer == "table":
            return self._import_table_from_preview(preview)

        if preview.errors:
            raise RepositoryError(preview.errors[0])
        if preview.total_rows == 0:
            raise RepositoryError("The selected import does not contain rows.")

        replace_existing = preview.mode == "replace"
        imported_counts = {sheet_name: 0 for sheet_name in preview.data}
        try:
            if replace_existing:
                self._clear_database_in_session()

            for sheet_name in XLSX_SHEETS_ORDER:
                rows = preview.data.get(sheet_name, [])
                model = self._model_by_sheet.get(sheet_name)
                if model is None:
                    continue
                for row in rows:
                    normalized = self._prepare_import_row(sheet_name, model, row)
                    if not normalized:
                        continue
                    existing = None
                    if not replace_existing:
                        existing = self._find_import_target(sheet_name, normalized)
                    if existing is None:
                        self.session.add(model(**normalized))
                    else:
                        self._update_import_target(existing, normalized)
                    imported_counts[sheet_name] += 1
                self.session.flush()

            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            raise RepositoryError(self._integrity_message(exc)) from exc
        except (SQLAlchemyError, ValueError, TypeError) as exc:
            self.session.rollback()
            raise RepositoryError(f"Import failed: {exc}") from exc

        self.session.expire_all()
        return {name: count for name, count in imported_counts.items() if count}

    def clear_database(self) -> None:
        try:
            self._clear_database_in_session()
            self.session.commit()
        except SQLAlchemyError as exc:
            self.session.rollback()
            raise RepositoryError("Database was not cleared.") from exc
        self.session.expire_all()

    def _clear_database_in_session(self) -> None:
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
            if value is None and column.name in {"id", "created_at", "updated_at"}:
                continue
            normalized[column.name] = cls._normalize_import_value(
                model,
                column.name,
                value,
            )
        return normalized

    @staticmethod
    def _normalize_import_value(
        model: type[Base],
        column_name: str,
        value: object,
    ) -> object:
        if value is None:
            return None
        if column_name in {"id", "group_id", "schedule_id", "student_id", "lesson_id"}:
            return int(value)
        if model is Mark and column_name == "data":
            return int(value)
        if column_name in {"is_assessment", "is_visited"}:
            if isinstance(value, bool):
                return value
            if isinstance(value, (int, float)):
                return bool(value)
            return str(value).strip().lower() in {"1", "true", "yes", "y", "да"}
        if column_name == "date":
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
        row_id = row.get("id")
        if row_id is not None:
            target = self.session.get(model, row_id)
            if target is not None:
                return target

        if sheet_name == "groups":
            return self.session.scalar(
                select(Group).where(Group.name == row.get("name"))
            )
        if sheet_name == "students":
            return self.session.scalar(
                select(Student).where(
                    Student.group_id == row.get("group_id"),
                    Student.first_name == row.get("first_name"),
                    Student.surname == row.get("surname"),
                )
            )
        if sheet_name == "schedules":
            return self.session.scalar(
                select(Schedule).where(
                    Schedule.day == row.get("day"),
                    Schedule.time == row.get("time"),
                    Schedule.odd_or_even == row.get("odd_or_even"),
                    Schedule.type == row.get("type"),
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

    @staticmethod
    def _update_import_target(target: Base, row: dict[str, object]) -> None:
        for field_name, value in row.items():
            if field_name == "id":
                continue
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
