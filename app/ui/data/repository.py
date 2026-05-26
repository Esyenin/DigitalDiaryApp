from __future__ import annotations

from datetime import date, time, timedelta

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, selectinload, sessionmaker

from app.database import DATABASE_URL
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
from app.ui.data.calendar import DAY_NAMES, SemesterSettings, day_index, week_type_for_number


class DiaryRepository:
    """Thin UI-facing repository over the existing SQLAlchemy models."""

    def __init__(self) -> None:
        self.engine = create_engine(DATABASE_URL)
        Base.metadata.create_all(bind=self.engine)
        self.session_factory = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.session: Session = self.session_factory()

    def close(self) -> None:
        self.session.close()

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
            self.ensure_lessons_for_schedule(schedule, self.schedule_topic(schedule), settings)
        self.session.commit()

    def ensure_lessons_for_schedule(
        self,
        schedule: Schedule,
        topic: str,
        settings: SemesterSettings,
    ) -> None:
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
                    Lesson(schedule_id=schedule.id, topic=topic, date=lesson_date)
                )
            elif not lesson.topic:
                lesson.topic = topic

    def ensure_attendance_and_marks(self) -> None:
        """Kept for older UI calls; records are now created only by teacher input."""
        self.session.commit()

    def list_groups(self) -> list[Group]:
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
        return self.session.scalar(
            self._lesson_options(select(Lesson).where(Lesson.id == lesson_id))
        )

    def list_schedules(self) -> list[Schedule]:
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
        return list(self.session.scalars(self._lesson_options(select(Lesson))).all())

    def lessons_for_week(self, week_start: date, week_type: str | None) -> list[Lesson]:
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

        self.session.commit()
        self.session.expire_all()


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
        marks = [mark.data for student in students for mark in student.marks]
        lab_marks = [
            mark.data
            for student in students
            for mark in student.marks
            if mark.lesson.schedule.type == "Lab Work"
        ]
        attendances = [item for student in students for item in student.attendances]
        present = sum(1 for item in attendances if item.is_visited)
        attendance_rate = round(present / len(attendances) * 100) if attendances else 0
        overall = round(sum(marks) / len(marks)) if marks else 0
        lab_average = round(sum(lab_marks) / len(lab_marks)) if lab_marks else 0
        test_marks = [
            mark.data
            for student in students
            for mark in student.marks
            if mark.lesson.schedule.type == "Control Work"
        ]
        test_average = round(sum(test_marks) / len(test_marks)) if test_marks else "-"
        return {
            "overall": overall,
            "lab": lab_average,
            "test": test_average,
            "attendance": attendance_rate,
            "students": len(students),
        }

    def student_stats(self, student: Student) -> dict[str, int | str]:
        marks = [mark.data for mark in student.marks]
        lab_marks = [
            mark.data for mark in student.marks if mark.lesson.schedule.type == "Lab Work"
        ]
        test_marks = [
            mark.data
            for mark in student.marks
            if mark.lesson.schedule.type == "Control Work"
        ]
        present = sum(1 for attendance in student.attendances if attendance.is_visited)
        attendance = (
            round(present / len(student.attendances) * 100)
            if student.attendances
            else 0
        )
        return {
            "overall": round(sum(marks) / len(marks)) if marks else "-",
            "lab": round(sum(lab_marks) / len(lab_marks)) if lab_marks else "-",
            "test": round(sum(test_marks) / len(test_marks)) if test_marks else "-",
            "attendance": attendance,
        }

    def create_group(self, name: str, speciality: str | None = None) -> Group:
        group = Group(name=name.strip(), speciality=(speciality or "").strip() or None)
        self.session.add(group)
        self.session.commit()
        return group

    def update_group(self, group: Group, name: str, speciality: str | None) -> None:
        group.name = name.strip()
        group.speciality = (speciality or "").strip() or None
        self.session.commit()

    def delete_group(self, group: Group) -> None:
        self.session.delete(group)
        self.session.commit()

    def create_student(
        self,
        group: Group,
        first_name: str,
        surname: str,
        email: str | None = None,
    ) -> Student:
        student = Student(
            group_id=group.id,
            first_name=first_name.strip(),
            surname=surname.strip(),
            patronymic=None,
            personal_data=None,
            bmstu_email=(email or "").strip() or None,
        )
        self.session.add(student)
        self.session.commit()
        return student

    def update_student(
        self,
        student: Student,
        group: Group,
        first_name: str,
        surname: str,
        email: str | None,
    ) -> None:
        student.group_id = group.id
        student.first_name = first_name.strip()
        student.surname = surname.strip()
        student.bmstu_email = (email or "").strip() or None
        self.session.commit()

    def delete_student(self, student: Student) -> None:
        self.session.delete(student)
        self.session.commit()

    def create_schedule(
        self,
        topic: str,
        groups: list[Group],
        day: str,
        lesson_time: time,
        week_type: str,
        lesson_type: str,
        is_assessment: bool,
        settings: SemesterSettings,
    ) -> Schedule:
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
        self.session.commit()
        return schedule

    def update_schedule(
        self,
        schedule: Schedule,
        topic: str,
        groups: list[Group],
        day: str,
        lesson_time: time,
        week_type: str,
        lesson_type: str,
        is_assessment: bool,
        settings: SemesterSettings,
    ) -> None:
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
        for lesson in list(schedule.lessons):
            self.session.delete(lesson)
        self.session.flush()
        self.ensure_lessons_for_schedule(schedule, topic, settings)
        self.session.commit()

    def delete_schedule(self, schedule: Schedule) -> None:
        self.session.delete(schedule)
        self.session.commit()

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
