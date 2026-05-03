"""
Тестирование Pydantic-схем проекта.
"""
# pylint: disable=import-error
from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Any

import pytest
from pydantic import BaseModel, ValidationError

from app.models.attendance import Attendance
from app.models.comment import MAX_LEN as COMMENT_MAX_LEN, Comment
from app.models.group import MAX_LEN as GROUP_MAX_LEN, Group
from app.models.lesson import MAX_LEN as LESSON_MAX_LEN, Lesson
from app.models.mark import Mark
from app.models.schedule import MAX_LEN as SCHEDULE_MAX_LEN, Schedule
from app.models.schedule_group_link import ScheduleGroupLink
from app.models.student import MAX_LEN as STUDENT_MAX_LEN, Student
from app.schemas.attendance import (
    AttendanceCreateSchema,
    AttendanceDeleteSchema,
    AttendanceFilterSchema,
    AttendanceReadSchema,
    AttendanceUpdateSchema,
)
from app.schemas.comment import (
    CommentCreateSchema,
    CommentDeleteSchema,
    CommentFilterSchema,
    CommentReadSchema,
    CommentUpdateSchema,
)
from app.schemas.group import (
    GroupCreateSchema,
    GroupDeleteSchema,
    GroupFilterSchema,
    GroupReadSchema,
    GroupUpdateSchema,
    is_group_name_formatted,
    is_speciality_formatted,
)
from app.schemas.lesson import (
    LessonCreateSchema,
    LessonDeleteSchema,
    LessonFilterSchema,
    LessonReadSchema,
    LessonUpdateSchema,
)
from app.schemas.mark import (
    MarkCreateSchema,
    MarkDeleteSchema,
    MarkFilterSchema,
    MarkReadSchema,
    MarkUpdateSchema,
)
from app.schemas.schedule import (
    ScheduleCreateSchema,
    ScheduleDeleteSchema,
    ScheduleFilterSchema,
    ScheduleReadSchema,
    ScheduleUpdateSchema,
)
from app.schemas.schedule_group_link import (
    ScheduleGroupLinkCreateSchema,
    ScheduleGroupLinkDeleteSchema,
    ScheduleGroupLinkFilterSchema,
    ScheduleGroupLinkReadSchema,
    ScheduleGroupLinkUpdateSchema,
)
from app.schemas.student import (
    StudentCreateSchema,
    StudentDeleteSchema,
    StudentFilterSchema,
    StudentReadSchema,
    StudentUpdateSchema,
)


Payload = dict[str, Any] | BaseModel | object
SchemaType = type[BaseModel]


@dataclass(frozen=True)
class PayloadSet:
    """
    Набор валидных и невалидных данных для одной схемы.
    """

    valid: tuple[Payload, ...]
    invalid: tuple[Payload, ...]


@dataclass(frozen=True)
class EntitySchemaCase:
    """
    Полный набор схем и payload-ов для одной сущности.
    """

    create_schema: SchemaType
    filter_schema: SchemaType
    update_schema: SchemaType
    delete_schema: SchemaType
    read_schema: SchemaType
    create: PayloadSet
    filter: PayloadSet
    update: PayloadSet
    delete: PayloadSet
    read: PayloadSet


BASE_READ_FIELDS = {
    "id": 1,
    "created_at": datetime(2026, 4, 19, 10, 0, 0),
    "updated_at": datetime(2026, 4, 19, 10, 5, 0),
}
SERVICE_FILTER_FIELDS = {
    "id": BASE_READ_FIELDS["id"],
    "created_at": BASE_READ_FIELDS["created_at"],
    "updated_at": BASE_READ_FIELDS["updated_at"],
}

def make_length_cases(max_len_by_field: dict[str, int]) -> dict[str, str]:
    """
    Формирует граничные строки из лимитов модели.
    """
    return {
        case_name: "С" * length
        for field_name, max_len in max_len_by_field.items()
        for case_name, length in (
            (f"max_{field_name}", max_len),
            (f"too_long_{field_name}", max_len + 1),
        )
    }


GROUP_LENGTH_CASES = make_length_cases(GROUP_MAX_LEN)
STUDENT_LENGTH_CASES = make_length_cases(STUDENT_MAX_LEN)
SCHEDULE_LENGTH_CASES = make_length_cases(SCHEDULE_MAX_LEN)
LESSON_LENGTH_CASES = make_length_cases(LESSON_MAX_LEN)
COMMENT_LENGTH_CASES = make_length_cases(COMMENT_MAX_LEN)

STUDENT_MINIMAL = {
    "group_id": 1,
    "surname": "Петров",
    "first_name": "Петр",
}
STUDENT_FULL = {
    **STUDENT_MINIMAL,
    "patronymic": "Петрович",
    "personal_data": "21У001",
    "bmstu_email": "petrov@bmstu.ru",
}
SCHEDULE_MINIMAL = {
    "odd_or_even": "even",
    "type": "семинар",
    "day": "вт",
    "time": time(8, 45),
}
SCHEDULE_FULL = {
    **SCHEDULE_MINIMAL,
    "is_assessment": False,
}
SCHEDULE_GROUP_LINK_BASE = {
    "group_id": 1,
    "schedule_id": 2,
}
LESSON_MINIMAL = {
    "schedule_id": 1,
    "date": date(2026, 4, 19),
}
LESSON_FULL = {
    **LESSON_MINIMAL,
    "topic": "SQLAlchemy",
}
ATTENDANCE_MINIMAL = {
    "student_id": 1,
    "lesson_id": 2,
}
ATTENDANCE_FULL = {
    **ATTENDANCE_MINIMAL,
    "is_visited": True,
}
MARK_BASE = {
    "student_id": 1,
    "lesson_id": 2,
    "data": 5,
}
COMMENT_MINIMAL = {
    "student_id": 1,
    "lesson_id": 2,
}
COMMENT_FULL = {
    **COMMENT_MINIMAL,
    "data": "Отличная работа",
}


SCHEMA_CASES_BY_ENTITY: dict[str, EntitySchemaCase] = {
    "group": EntitySchemaCase(
        create_schema=GroupCreateSchema,
        filter_schema=GroupFilterSchema,
        update_schema=GroupUpdateSchema,
        delete_schema=GroupDeleteSchema,
        read_schema=GroupReadSchema,
        create=PayloadSet(
            valid=(
                {"name": "обезьянки"},
                Group(name="группа 1"),
                {"name": "ИУ1-21Б"},
                Group(name="СМ7-21Б"),
                {**BASE_READ_FIELDS, "name": "ИУ1-21Б"},
                Group(**BASE_READ_FIELDS, name="СМ7-21Б"),
                Group(name="группа 1", speciality=None),
                {"name": "обезьянки", "speciality": None},
                {"name": "СМ1-21Б", "speciality": "24.03.01_Информатика"},
                Group(name="СМ3-21Б", speciality="1.1.1_База"),
                {"name": GROUP_LENGTH_CASES["max_name"]},
                Group(name=GROUP_LENGTH_CASES["max_name"]),
                {
                    "name": "СМ1-21Б",
                    "speciality": GROUP_LENGTH_CASES["max_speciality"],
                },
                Group(
                    name="СМ1-21Б",
                    speciality=GROUP_LENGTH_CASES["max_speciality"],
                ),
            ),
            invalid=(
                {},
                Group(),
                {"name": 123},
                Group(name=1),
                {"name": None},
                Group(name=None),
                {"name": "обезьянки", "speciality": 123},
                Group(name="группа 1", speciality=1),
                {"name": ""},
                Group(name=""),
                {"name": "  "},
                Group(name="  "),
                {"name": "обезьянки", "speciality": "  "},
                Group(name="группа 1", speciality="   "),
                {"speciality": "24.03.01_Информатика"},
                Group(speciality="1.1.1_База"),
                {"name": GROUP_LENGTH_CASES["too_long_name"]},
                Group(name=GROUP_LENGTH_CASES["too_long_name"]),
                {"speciality": GROUP_LENGTH_CASES["too_long_speciality"]},
                Group(speciality=GROUP_LENGTH_CASES["too_long_speciality"]),
                {
                    "name": GROUP_LENGTH_CASES["too_long_name"],
                    "speciality": GROUP_LENGTH_CASES["too_long_speciality"],
                },
                Group(
                    name=GROUP_LENGTH_CASES["too_long_name"],
                    speciality=GROUP_LENGTH_CASES["too_long_speciality"],
                ),
                {"unknown_field": "value"},
            ),
        ),
        filter=PayloadSet(
            valid=(
                {},
                {"id": 1},
                Group(id=1),
                {"name": "СМ1-21Б"},
                Group(name="ИУ7-31"),
                {"speciality": None},
                {"speciality": "24.03.01_Информатика"},
                Group(speciality="09.03.01_Информатика"),
                {"id": 1, "name": "СМ1-21Б"},
                Group(id=1, name="ИУ7-31"),
                {"created_at": BASE_READ_FIELDS["created_at"]},
                {"updated_at": BASE_READ_FIELDS["updated_at"]},
                {
                    "id": 1,
                    "created_at": BASE_READ_FIELDS["created_at"],
                    "updated_at": BASE_READ_FIELDS["updated_at"],
                },
                {"name": "СМ1-21Б", "speciality": "24.03.01_Информатика"},
                Group(name="ИУ7-31", speciality="09.03.01_Информатика"),
                {"id": 1, "name": "СМ1-21Б", "speciality": "24.03.01_Информатика"},
                Group(id=1, name="ИУ7-31", speciality="09.03.01_Информатика"),
                {"name": GROUP_LENGTH_CASES["max_name"]},
                {"speciality": GROUP_LENGTH_CASES["max_speciality"]},
            ),
            invalid=(
                {"id": None},
                {"id": "not-id"},
                {"name": ""},
                Group(name=""),
                {"name": 123},
                Group(name=1),
                {"name": None},
                {"speciality": 123},
                Group(speciality=1),
                {"name": GROUP_LENGTH_CASES["too_long_name"]},
                Group(name=GROUP_LENGTH_CASES["too_long_name"]),
                {"speciality": GROUP_LENGTH_CASES["too_long_speciality"]},
                Group(speciality=GROUP_LENGTH_CASES["too_long_speciality"]),
                {
                    "name": GROUP_LENGTH_CASES["too_long_name"],
                    "speciality": GROUP_LENGTH_CASES["too_long_speciality"],
                },
                Group(
                    name=GROUP_LENGTH_CASES["too_long_name"],
                    speciality=GROUP_LENGTH_CASES["too_long_speciality"],
                ),
                {"unknown_field": "value"},
            ),
        ),
        update=PayloadSet(
            valid=(
                {"name": "ИУ7-31"},
                Group(name="ИУ7-31"),
                {"speciality": None},
                {"speciality": "09.03.01_Информатика"},
                Group(speciality="09.03.01_Информатика"),
                {"name": "ИУ7-31", "speciality": "09.03.01_Информатика"},
                Group(name="ИУ7-34", speciality="09.03.01_Информатика"),
                {"name": GROUP_LENGTH_CASES["max_name"]},
                {"speciality": GROUP_LENGTH_CASES["max_speciality"]},
            ),
            invalid=(
                {},
                Group(),
                {"id": 1},
                Group(id=1),
                {"name": 123, "speciality": "09.03.01_Информатика"},
                Group(name=1, speciality="09.03.01_Информатика"),
                {"name": "ИУ7-31", "speciality": 123},
                Group(name="ИУ7-31", speciality=1),
                {"name": None},
                Group(name=None),
                {"name": ""},
                Group(name=""),
                {"speciality": ""},
                Group(speciality=""),
                {"name": "   "},
                Group(name="   "),
                {"speciality": "   "},
                Group(speciality="   "),
                {"name": GROUP_LENGTH_CASES["too_long_name"]},
                Group(name=GROUP_LENGTH_CASES["too_long_name"]),
                {"speciality": GROUP_LENGTH_CASES["too_long_speciality"]},
                Group(speciality=GROUP_LENGTH_CASES["too_long_speciality"]),
                {
                    "name": GROUP_LENGTH_CASES["too_long_name"],
                    "speciality": GROUP_LENGTH_CASES["too_long_speciality"],
                },
                Group(
                    name=GROUP_LENGTH_CASES["too_long_name"],
                    speciality=GROUP_LENGTH_CASES["too_long_speciality"],
                ),
                {"unknown_field": "value"},
            ),
        ),
        delete=PayloadSet(
            valid=(
                {"id": 1},
                Group(id=1),
                {"name": "СМ1-21Б"},
                Group(name="ИУ7-31"),
                {"speciality": None},
                {"speciality": "24.03.01_Информатика"},
                Group(speciality="09.03.01_Информатика"),
                {"id": 1, "name": "СМ1-21Б"},
                Group(id=1, name="ИУ7-31"),
                {"created_at": BASE_READ_FIELDS["created_at"]},
                {"updated_at": BASE_READ_FIELDS["updated_at"]},
                {
                    "id": 1,
                    "created_at": BASE_READ_FIELDS["created_at"],
                    "updated_at": BASE_READ_FIELDS["updated_at"],
                },
                {"name": "СМ1-21Б", "speciality": "24.03.01_Информатика"},
                Group(name="ИУ7-31", speciality="09.03.01_Информатика"),
                {"name": GROUP_LENGTH_CASES["max_name"]},
            ),
            invalid=(
                {},
                Group(),
                {"id": None},
                Group(id=None),
                {"id": "not-id"},
                {"name": ""},
                Group(name=""),
                {"name": "   "},
                Group(name="   "),
                {"name": 123},
                Group(name=1),
                {"name": None},
                Group(name=None),
                {"speciality": 123},
                Group(speciality=123),
                {"name": GROUP_LENGTH_CASES["too_long_name"]},
                Group(name=GROUP_LENGTH_CASES["too_long_name"]),
                {"unknown_field": "value"},
            ),
        ),
        read=PayloadSet(
            valid=(
                BASE_READ_FIELDS,
            ),
            invalid=(
                {},
                Group(),
                {"id": 1, "created_at": BASE_READ_FIELDS["created_at"]},
                Group(id=1, created_at=BASE_READ_FIELDS["created_at"]),
                {**BASE_READ_FIELDS, "name": "СМ1-21Б"},
                {**BASE_READ_FIELDS, "speciality": "24.03.01_Информатика"},
            ),
        ),
    ),
    "student": EntitySchemaCase(
        create_schema=StudentCreateSchema,
        filter_schema=StudentFilterSchema,
        update_schema=StudentUpdateSchema,
        delete_schema=StudentDeleteSchema,
        read_schema=StudentReadSchema,
        create=PayloadSet(
            valid=(
                STUDENT_MINIMAL,
                Student(**STUDENT_MINIMAL),
                STUDENT_FULL,
                Student(**STUDENT_FULL),
                {**BASE_READ_FIELDS, **STUDENT_MINIMAL},
                Student(**BASE_READ_FIELDS, **STUDENT_MINIMAL),
                {**STUDENT_MINIMAL, "patronymic": None},
                Student(**STUDENT_MINIMAL, patronymic=None),
                {**STUDENT_MINIMAL, "personal_data": None, "bmstu_email": None},
                Student(**STUDENT_MINIMAL, personal_data=None, bmstu_email=None),
                {
                    "group_id": 1,
                    "surname": STUDENT_LENGTH_CASES["max_surname"],
                    "first_name": STUDENT_LENGTH_CASES["max_first_name"],
                    "patronymic": STUDENT_LENGTH_CASES["max_patronymic"],
                    "personal_data": STUDENT_LENGTH_CASES["max_personal_data"],
                    "bmstu_email": STUDENT_LENGTH_CASES["max_bmstu_email"],
                },
                Student(
                    group_id=1,
                    surname=STUDENT_LENGTH_CASES["max_surname"],
                    first_name=STUDENT_LENGTH_CASES["max_first_name"],
                    patronymic=STUDENT_LENGTH_CASES["max_patronymic"],
                    personal_data=STUDENT_LENGTH_CASES["max_personal_data"],
                    bmstu_email=STUDENT_LENGTH_CASES["max_bmstu_email"],
                ),
            ),
            invalid=(
                {},
                Student(),
                {"surname": "Петров", "first_name": "Петр"},
                Student(surname="Петров", first_name="Петр"),
                {"group_id": 1, "first_name": "Петр"},
                Student(group_id=1, first_name="Петр"),
                {"group_id": 1, "surname": "Петров"},
                Student(group_id=1, surname="Петров"),
                {"group_id": None, "surname": "Петров", "first_name": "Петр"},
                Student(group_id=None, surname="Петров", first_name="Петр"),
                {"group_id": "not-id", "surname": "Петров", "first_name": "Петр"},
                Student(group_id="not-id", surname="Петров", first_name="Петр"),
                {"group_id": 1, "surname": None, "first_name": "Петр"},
                Student(group_id=1, surname=None, first_name="Петр"),
                {"group_id": 1, "surname": 123, "first_name": "Петр"},
                Student(group_id=1, surname=123, first_name="Петр"),
                {"group_id": 1, "surname": "Петров", "first_name": None},
                Student(group_id=1, surname="Петров", first_name=None),
                {"group_id": 1, "surname": "Петров", "first_name": 123},
                Student(group_id=1, surname="Петров", first_name=123),
                {"group_id": 1, "surname": "", "first_name": "Петр"},
                Student(group_id=1, surname="", first_name="Петр"),
                {"group_id": 1, "surname": "   ", "first_name": "Петр"},
                Student(group_id=1, surname="   ", first_name="Петр"),
                {"group_id": 1, "surname": "Петров", "first_name": ""},
                Student(group_id=1, surname="Петров", first_name=""),
                {"group_id": 1, "surname": "Петров", "first_name": "   "},
                Student(group_id=1, surname="Петров", first_name="   "),
                {**STUDENT_MINIMAL, "patronymic": 123},
                Student(**STUDENT_MINIMAL, patronymic=123),
                {**STUDENT_MINIMAL, "personal_data": 123},
                Student(**STUDENT_MINIMAL, personal_data=123),
                {**STUDENT_MINIMAL, "bmstu_email": 123},
                Student(**STUDENT_MINIMAL, bmstu_email=123),
                {**STUDENT_MINIMAL, "patronymic": ""},
                Student(**STUDENT_MINIMAL, patronymic=""),
                {**STUDENT_MINIMAL, "personal_data": "   "},
                Student(**STUDENT_MINIMAL, personal_data="   "),
                {**STUDENT_MINIMAL, "bmstu_email": ""},
                Student(**STUDENT_MINIMAL, bmstu_email=""),
                {**STUDENT_MINIMAL, "surname": STUDENT_LENGTH_CASES["too_long_surname"]},
                Student(**{**STUDENT_MINIMAL, "surname": STUDENT_LENGTH_CASES["too_long_surname"]}),
                {**STUDENT_MINIMAL, "first_name": STUDENT_LENGTH_CASES["too_long_first_name"]},
                Student(**{**STUDENT_MINIMAL, "first_name": STUDENT_LENGTH_CASES["too_long_first_name"]}),
                {**STUDENT_MINIMAL, "patronymic": STUDENT_LENGTH_CASES["too_long_patronymic"]},
                Student(**STUDENT_MINIMAL, patronymic=STUDENT_LENGTH_CASES["too_long_patronymic"]),
                {**STUDENT_MINIMAL, "personal_data": STUDENT_LENGTH_CASES["too_long_personal_data"]},
                Student(**STUDENT_MINIMAL, personal_data=STUDENT_LENGTH_CASES["too_long_personal_data"]),
                {**STUDENT_MINIMAL, "bmstu_email": STUDENT_LENGTH_CASES["too_long_bmstu_email"]},
                Student(**STUDENT_MINIMAL, bmstu_email=STUDENT_LENGTH_CASES["too_long_bmstu_email"]),
                {
                    "group_id": "not-id",
                    "surname": STUDENT_LENGTH_CASES["too_long_surname"],
                    "first_name": "",
                },
                Student(
                    group_id="not-id",
                    surname=STUDENT_LENGTH_CASES["too_long_surname"],
                    first_name="",
                ),
                {"unknown_field": "data", **STUDENT_MINIMAL},
            ),
        ),
        filter=PayloadSet(
            valid=(
                {},
                {"id": 1},
                Student(id=1),
                {"group_id": 1, "surname": "Петров"},
                Student(group_id=1, surname="Петров"),
                {"group_id": None},
                Student(group_id=None),
                {"surname": None},
                Student(surname=None),
                {"patronymic": None},
                Student(patronymic=None),
                {"personal_data": None},
                Student(personal_data=None),
                {"bmstu_email": None},
                Student(bmstu_email=None),
                STUDENT_FULL,
                Student(**STUDENT_FULL),
                {"created_at": BASE_READ_FIELDS["created_at"]},
                {"updated_at": BASE_READ_FIELDS["updated_at"]},
                {
                    "id": 1,
                    "created_at": BASE_READ_FIELDS["created_at"],
                    "updated_at": BASE_READ_FIELDS["updated_at"],
                    **STUDENT_FULL,
                },
                {
                    "surname": STUDENT_LENGTH_CASES["max_surname"],
                    "first_name": STUDENT_LENGTH_CASES["max_first_name"],
                    "patronymic": STUDENT_LENGTH_CASES["max_patronymic"],
                    "personal_data": STUDENT_LENGTH_CASES["max_personal_data"],
                    "bmstu_email": STUDENT_LENGTH_CASES["max_bmstu_email"],
                },
                Student(
                    surname=STUDENT_LENGTH_CASES["max_surname"],
                    first_name=STUDENT_LENGTH_CASES["max_first_name"],
                    patronymic=STUDENT_LENGTH_CASES["max_patronymic"],
                    personal_data=STUDENT_LENGTH_CASES["max_personal_data"],
                    bmstu_email=STUDENT_LENGTH_CASES["max_bmstu_email"],
                ),
            ),
            invalid=(
                {"id": "not-id"},
                Student(id="not-id"),
                {"created_at": "not-datetime"},
                {"updated_at": "not-datetime"},
                {"group_id": "not-id"},
                Student(group_id="not-id"),
                {"surname": ""},
                Student(surname=""),
                {"surname": "   "},
                Student(surname="   "),
                {"surname": 123},
                Student(surname=123),
                {"first_name": ""},
                Student(first_name=""),
                {"first_name": "   "},
                Student(first_name="   "),
                {"first_name": 123},
                Student(first_name=123),
                {"patronymic": ""},
                Student(patronymic=""),
                {"patronymic": "   "},
                Student(patronymic="   "),
                {"patronymic": 123},
                Student(patronymic=123),
                {"personal_data": ""},
                Student(personal_data=""),
                {"personal_data": "   "},
                Student(personal_data="   "),
                {"personal_data": 123},
                Student(personal_data=123),
                {"bmstu_email": ""},
                Student(bmstu_email=""),
                {"bmstu_email": "   "},
                Student(bmstu_email="   "),
                {"bmstu_email": 123},
                Student(bmstu_email=123),
                {"surname": STUDENT_LENGTH_CASES["too_long_surname"]},
                Student(surname=STUDENT_LENGTH_CASES["too_long_surname"]),
                {"first_name": STUDENT_LENGTH_CASES["too_long_first_name"]},
                Student(first_name=STUDENT_LENGTH_CASES["too_long_first_name"]),
                {"patronymic": STUDENT_LENGTH_CASES["too_long_patronymic"]},
                Student(patronymic=STUDENT_LENGTH_CASES["too_long_patronymic"]),
                {"personal_data": STUDENT_LENGTH_CASES["too_long_personal_data"]},
                Student(personal_data=STUDENT_LENGTH_CASES["too_long_personal_data"]),
                {"bmstu_email": STUDENT_LENGTH_CASES["too_long_bmstu_email"]},
                Student(bmstu_email=STUDENT_LENGTH_CASES["too_long_bmstu_email"]),
                {
                    "group_id": "not-id",
                    "surname": STUDENT_LENGTH_CASES["too_long_surname"],
                    "first_name": "",
                },
                Student(
                    group_id="not-id",
                    surname=STUDENT_LENGTH_CASES["too_long_surname"],
                    first_name="",
                ),
                {"unknown_field": "data"},
            ),
        ),
        update=PayloadSet(
            valid=(
                {"group_id": 2},
                Student(group_id=2),
                {"surname": "Сидоров"},
                Student(surname="Сидоров"),
                {"first_name": "Алексей"},
                Student(first_name="Алексей"),
                {"patronymic": None},
                Student(patronymic=None),
                {"personal_data": None},
                Student(personal_data=None),
                {"bmstu_email": None},
                Student(bmstu_email=None),
                {"surname": "Сидоров", "first_name": "Алексей"},
                Student(surname="Сидоров", first_name="Алексей"),
                {**BASE_READ_FIELDS, "first_name": "Алексей"},
                Student(**BASE_READ_FIELDS, first_name="Алексей"),
                {"surname": STUDENT_LENGTH_CASES["max_surname"]},
                Student(surname=STUDENT_LENGTH_CASES["max_surname"]),
                {"first_name": STUDENT_LENGTH_CASES["max_first_name"]},
                Student(first_name=STUDENT_LENGTH_CASES["max_first_name"]),
                {"patronymic": STUDENT_LENGTH_CASES["max_patronymic"]},
                Student(patronymic=STUDENT_LENGTH_CASES["max_patronymic"]),
                {"personal_data": STUDENT_LENGTH_CASES["max_personal_data"]},
                Student(personal_data=STUDENT_LENGTH_CASES["max_personal_data"]),
                {"bmstu_email": STUDENT_LENGTH_CASES["max_bmstu_email"]},
                Student(bmstu_email=STUDENT_LENGTH_CASES["max_bmstu_email"]),
            ),
            invalid=(
                {},
                Student(),
                {"id": 1},
                Student(id=1),
                {"group_id": None},
                Student(group_id=None),
                {"group_id": "not-id"},
                Student(group_id="not-id"),
                {"surname": None},
                Student(surname=None),
                {"surname": ""},
                Student(surname=""),
                {"surname": "   "},
                Student(surname="   "),
                {"surname": 123},
                Student(surname=123),
                {"first_name": None},
                Student(first_name=None),
                {"first_name": ""},
                Student(first_name=""),
                {"first_name": "   "},
                Student(first_name="   "),
                {"first_name": 123},
                Student(first_name=123),
                {"patronymic": ""},
                Student(patronymic=""),
                {"patronymic": "   "},
                Student(patronymic="   "),
                {"patronymic": 123},
                Student(patronymic=123),
                {"personal_data": ""},
                Student(personal_data=""),
                {"personal_data": "   "},
                Student(personal_data="   "),
                {"personal_data": 123},
                Student(personal_data=123),
                {"bmstu_email": ""},
                Student(bmstu_email=""),
                {"bmstu_email": "   "},
                Student(bmstu_email="   "),
                {"bmstu_email": 123},
                Student(bmstu_email=123),
                {"surname": STUDENT_LENGTH_CASES["too_long_surname"]},
                Student(surname=STUDENT_LENGTH_CASES["too_long_surname"]),
                {"first_name": STUDENT_LENGTH_CASES["too_long_first_name"]},
                Student(first_name=STUDENT_LENGTH_CASES["too_long_first_name"]),
                {"patronymic": STUDENT_LENGTH_CASES["too_long_patronymic"]},
                Student(patronymic=STUDENT_LENGTH_CASES["too_long_patronymic"]),
                {"personal_data": STUDENT_LENGTH_CASES["too_long_personal_data"]},
                Student(personal_data=STUDENT_LENGTH_CASES["too_long_personal_data"]),
                {"bmstu_email": STUDENT_LENGTH_CASES["too_long_bmstu_email"]},
                Student(bmstu_email=STUDENT_LENGTH_CASES["too_long_bmstu_email"]),
                {
                    "group_id": None,
                    "surname": STUDENT_LENGTH_CASES["too_long_surname"],
                    "first_name": "",
                },
                Student(
                    group_id=None,
                    surname=STUDENT_LENGTH_CASES["too_long_surname"],
                    first_name="",
                ),
                {"unknown_field": "data"},
            ),
        ),
        delete=PayloadSet(
            valid=(
                {"id": 1},
                Student(id=1),
                {"group_id": 1},
                Student(group_id=1),
                {"created_at": BASE_READ_FIELDS["created_at"]},
                {"updated_at": BASE_READ_FIELDS["updated_at"]},
                {"surname": "Петров"},
                Student(surname="Петров"),
                STUDENT_FULL,
                Student(**STUDENT_FULL),
                {"id": None},
                Student(id=None),
                {"group_id": None},
                Student(group_id=None),
                {"surname": None},
                Student(surname=None),
                {"patronymic": None},
                Student(patronymic=None),
                {"personal_data": None},
                Student(personal_data=None),
                {"bmstu_email": None},
                Student(bmstu_email=None),
                {"surname": STUDENT_LENGTH_CASES["max_surname"]},
                Student(surname=STUDENT_LENGTH_CASES["max_surname"]),
                {"first_name": STUDENT_LENGTH_CASES["max_first_name"]},
                Student(first_name=STUDENT_LENGTH_CASES["max_first_name"]),
                {"patronymic": STUDENT_LENGTH_CASES["max_patronymic"]},
                Student(patronymic=STUDENT_LENGTH_CASES["max_patronymic"]),
                {"personal_data": STUDENT_LENGTH_CASES["max_personal_data"]},
                Student(personal_data=STUDENT_LENGTH_CASES["max_personal_data"]),
                {"bmstu_email": STUDENT_LENGTH_CASES["max_bmstu_email"]},
                Student(bmstu_email=STUDENT_LENGTH_CASES["max_bmstu_email"]),
            ),
            invalid=(
                {},
                Student(),
                {"id": "not-id"},
                Student(id="not-id"),
                {"created_at": "not-datetime"},
                {"updated_at": "not-datetime"},
                {"group_id": "not-id"},
                Student(group_id="not-id"),
                {"surname": ""},
                Student(surname=""),
                {"surname": "   "},
                Student(surname="   "),
                {"surname": 123},
                Student(surname=123),
                {"first_name": ""},
                Student(first_name=""),
                {"first_name": "   "},
                Student(first_name="   "),
                {"first_name": 123},
                Student(first_name=123),
                {"patronymic": ""},
                Student(patronymic=""),
                {"patronymic": "   "},
                Student(patronymic="   "),
                {"patronymic": 123},
                Student(patronymic=123),
                {"personal_data": ""},
                Student(personal_data=""),
                {"personal_data": "   "},
                Student(personal_data="   "),
                {"personal_data": 123},
                Student(personal_data=123),
                {"bmstu_email": ""},
                Student(bmstu_email=""),
                {"bmstu_email": "   "},
                Student(bmstu_email="   "),
                {"bmstu_email": 123},
                Student(bmstu_email=123),
                {"surname": STUDENT_LENGTH_CASES["too_long_surname"]},
                Student(surname=STUDENT_LENGTH_CASES["too_long_surname"]),
                {"first_name": STUDENT_LENGTH_CASES["too_long_first_name"]},
                Student(first_name=STUDENT_LENGTH_CASES["too_long_first_name"]),
                {"patronymic": STUDENT_LENGTH_CASES["too_long_patronymic"]},
                Student(patronymic=STUDENT_LENGTH_CASES["too_long_patronymic"]),
                {"personal_data": STUDENT_LENGTH_CASES["too_long_personal_data"]},
                Student(personal_data=STUDENT_LENGTH_CASES["too_long_personal_data"]),
                {"bmstu_email": STUDENT_LENGTH_CASES["too_long_bmstu_email"]},
                Student(bmstu_email=STUDENT_LENGTH_CASES["too_long_bmstu_email"]),
                {"unknown_field": "data"},
            ),
        ),
        read=PayloadSet(
            valid=(
                BASE_READ_FIELDS,
            ),
            invalid=(
                {**BASE_READ_FIELDS, "group_id": 1},
                {**BASE_READ_FIELDS, "surname": "Петров"},
            ),
        ),
    ),
    "schedule": EntitySchemaCase(
        create_schema=ScheduleCreateSchema,
        filter_schema=ScheduleFilterSchema,
        update_schema=ScheduleUpdateSchema,
        delete_schema=ScheduleDeleteSchema,
        read_schema=ScheduleReadSchema,
        create=PayloadSet(
            valid=(
                SCHEDULE_MINIMAL,
                Schedule(**SCHEDULE_MINIMAL),
                SCHEDULE_FULL,
                Schedule(**SCHEDULE_FULL),
                {**BASE_READ_FIELDS, **SCHEDULE_MINIMAL},
                Schedule(**BASE_READ_FIELDS, **SCHEDULE_MINIMAL),
                {
                    "odd_or_even": SCHEDULE_LENGTH_CASES["max_odd_or_even"],
                    "type": SCHEDULE_LENGTH_CASES["max_type"],
                    "day": SCHEDULE_LENGTH_CASES["max_day"],
                    "time": time(10, 15),
                },
                Schedule(
                    odd_or_even=SCHEDULE_LENGTH_CASES["max_odd_or_even"],
                    type=SCHEDULE_LENGTH_CASES["max_type"],
                    day=SCHEDULE_LENGTH_CASES["max_day"],
                    time=time(10, 15),
                ),
            ),
            invalid=(
                {},
                Schedule(),
                {"type": "семинар", "day": "вт", "time": time(8, 45)},
                Schedule(type="семинар", day="вт", time=time(8, 45)),
                {"odd_or_even": "even", "day": "вт", "time": time(8, 45)},
                Schedule(odd_or_even="even", day="вт", time=time(8, 45)),
                {"odd_or_even": "even", "type": "семинар", "time": time(8, 45)},
                Schedule(odd_or_even="even", type="семинар", time=time(8, 45)),
                {"odd_or_even": "even", "type": "семинар", "day": "вт"},
                Schedule(odd_or_even="even", type="семинар", day="вт"),
                {**SCHEDULE_MINIMAL, "odd_or_even": None},
                Schedule(**{**SCHEDULE_MINIMAL, "odd_or_even": None}),
                {**SCHEDULE_MINIMAL, "type": None},
                Schedule(**{**SCHEDULE_MINIMAL, "type": None}),
                {**SCHEDULE_MINIMAL, "day": None},
                Schedule(**{**SCHEDULE_MINIMAL, "day": None}),
                {**SCHEDULE_MINIMAL, "time": None},
                Schedule(**{**SCHEDULE_MINIMAL, "time": None}),
                {**SCHEDULE_MINIMAL, "odd_or_even": 123},
                Schedule(**{**SCHEDULE_MINIMAL, "odd_or_even": 123}),
                {**SCHEDULE_MINIMAL, "type": 123},
                Schedule(**{**SCHEDULE_MINIMAL, "type": 123}),
                {**SCHEDULE_MINIMAL, "day": 123},
                Schedule(**{**SCHEDULE_MINIMAL, "day": 123}),
                {**SCHEDULE_MINIMAL, "time": "not-time"},
                Schedule(**{**SCHEDULE_MINIMAL, "time": "not-time"}),
                {**SCHEDULE_MINIMAL, "is_assessment": None},
                Schedule(**{**SCHEDULE_MINIMAL, "is_assessment": None}),
                {**SCHEDULE_MINIMAL, "is_assessment": "not-bool"},
                Schedule(**{**SCHEDULE_MINIMAL, "is_assessment": "not-bool"}),
                {**SCHEDULE_MINIMAL, "odd_or_even": ""},
                Schedule(**{**SCHEDULE_MINIMAL, "odd_or_even": ""}),
                {**SCHEDULE_MINIMAL, "odd_or_even": "   "},
                Schedule(**{**SCHEDULE_MINIMAL, "odd_or_even": "   "}),
                {**SCHEDULE_MINIMAL, "type": ""},
                Schedule(**{**SCHEDULE_MINIMAL, "type": ""}),
                {**SCHEDULE_MINIMAL, "type": "   "},
                Schedule(**{**SCHEDULE_MINIMAL, "type": "   "}),
                {**SCHEDULE_MINIMAL, "day": ""},
                Schedule(**{**SCHEDULE_MINIMAL, "day": ""}),
                {**SCHEDULE_MINIMAL, "day": "   "},
                Schedule(**{**SCHEDULE_MINIMAL, "day": "   "}),
                {**SCHEDULE_MINIMAL, "odd_or_even": SCHEDULE_LENGTH_CASES["too_long_odd_or_even"]},
                Schedule(**{**SCHEDULE_MINIMAL, "odd_or_even": SCHEDULE_LENGTH_CASES["too_long_odd_or_even"]}),
                {**SCHEDULE_MINIMAL, "type": SCHEDULE_LENGTH_CASES["too_long_type"]},
                Schedule(**{**SCHEDULE_MINIMAL, "type": SCHEDULE_LENGTH_CASES["too_long_type"]}),
                {**SCHEDULE_MINIMAL, "day": SCHEDULE_LENGTH_CASES["too_long_day"]},
                Schedule(**{**SCHEDULE_MINIMAL, "day": SCHEDULE_LENGTH_CASES["too_long_day"]}),
                {
                    "odd_or_even": SCHEDULE_LENGTH_CASES["too_long_odd_or_even"],
                    "type": "",
                    "day": SCHEDULE_LENGTH_CASES["too_long_day"],
                    "time": "not-time",
                },
                Schedule(
                    odd_or_even=SCHEDULE_LENGTH_CASES["too_long_odd_or_even"],
                    type="",
                    day=SCHEDULE_LENGTH_CASES["too_long_day"],
                    time="not-time",
                ),
                {"unknown_field": "data", **SCHEDULE_MINIMAL},
            ),
        ),
        filter=PayloadSet(
            valid=(
                {},
                {"id": 1},
                Schedule(id=1),
                {"odd_or_even": "even"},
                Schedule(odd_or_even="even"),
                {"type": "семинар"},
                Schedule(type="семинар"),
                {"is_assessment": True},
                Schedule(is_assessment=True),
                {"is_assessment": None},
                Schedule(is_assessment=None),
                {"day": "вт"},
                Schedule(day="вт"),
                {"time": time(8, 45)},
                Schedule(time=time(8, 45)),
                {"created_at": BASE_READ_FIELDS["created_at"]},
                {"updated_at": BASE_READ_FIELDS["updated_at"]},
                {
                    "id": 1,
                    "created_at": BASE_READ_FIELDS["created_at"],
                    "updated_at": BASE_READ_FIELDS["updated_at"],
                    **SCHEDULE_FULL,
                },
                {
                    "odd_or_even": SCHEDULE_LENGTH_CASES["max_odd_or_even"],
                    "type": SCHEDULE_LENGTH_CASES["max_type"],
                    "day": SCHEDULE_LENGTH_CASES["max_day"],
                },
                Schedule(
                    odd_or_even=SCHEDULE_LENGTH_CASES["max_odd_or_even"],
                    type=SCHEDULE_LENGTH_CASES["max_type"],
                    day=SCHEDULE_LENGTH_CASES["max_day"],
                ),
            ),
            invalid=(
                {"id": "not-id"},
                Schedule(id="not-id"),
                {"created_at": "not-datetime"},
                {"updated_at": "not-datetime"},
                {"odd_or_even": ""},
                Schedule(odd_or_even=""),
                {"odd_or_even": "   "},
                Schedule(odd_or_even="   "),
                {"odd_or_even": 123},
                Schedule(odd_or_even=123),
                {"type": ""},
                Schedule(type=""),
                {"type": "   "},
                Schedule(type="   "),
                {"type": 123},
                Schedule(type=123),
                {"is_assessment": "not-bool"},
                Schedule(is_assessment="not-bool"),
                {"day": ""},
                Schedule(day=""),
                {"day": "   "},
                Schedule(day="   "),
                {"day": 123},
                Schedule(day=123),
                {"time": "not-time"},
                Schedule(time="not-time"),
                {"odd_or_even": SCHEDULE_LENGTH_CASES["too_long_odd_or_even"]},
                Schedule(odd_or_even=SCHEDULE_LENGTH_CASES["too_long_odd_or_even"]),
                {"type": SCHEDULE_LENGTH_CASES["too_long_type"]},
                Schedule(type=SCHEDULE_LENGTH_CASES["too_long_type"]),
                {"day": SCHEDULE_LENGTH_CASES["too_long_day"]},
                Schedule(day=SCHEDULE_LENGTH_CASES["too_long_day"]),
                {
                    "odd_or_even": SCHEDULE_LENGTH_CASES["too_long_odd_or_even"],
                    "type": "",
                    "day": 123,
                },
                Schedule(
                    odd_or_even=SCHEDULE_LENGTH_CASES["too_long_odd_or_even"],
                    type="",
                    day=123,
                ),
                {"unknown_field": "data"},
            ),
        ),
        update=PayloadSet(
            valid=(
                {"odd_or_even": "odd"},
                Schedule(odd_or_even="odd"),
                {"type": "лекция"},
                Schedule(type="лекция"),
                {"is_assessment": True},
                Schedule(is_assessment=True),
                {"is_assessment": None},
                Schedule(is_assessment=None),
                {"day": "ср"},
                Schedule(day="ср"),
                {"time": time(10, 15)},
                Schedule(time=time(10, 15)),
                {"odd_or_even": None},
                Schedule(odd_or_even=None),
                {"type": None},
                Schedule(type=None),
                {"day": None},
                Schedule(day=None),
                {"time": None},
                Schedule(time=None),
                {**BASE_READ_FIELDS, "is_assessment": True},
                Schedule(**BASE_READ_FIELDS, is_assessment=True),
                {"odd_or_even": SCHEDULE_LENGTH_CASES["max_odd_or_even"]},
                Schedule(odd_or_even=SCHEDULE_LENGTH_CASES["max_odd_or_even"]),
                {"type": SCHEDULE_LENGTH_CASES["max_type"]},
                Schedule(type=SCHEDULE_LENGTH_CASES["max_type"]),
                {"day": SCHEDULE_LENGTH_CASES["max_day"]},
                Schedule(day=SCHEDULE_LENGTH_CASES["max_day"]),
            ),
            invalid=(
                {},
                Schedule(),
                {"id": 1},
                Schedule(id=1),
                {"created_at": BASE_READ_FIELDS["created_at"]},
                {"updated_at": BASE_READ_FIELDS["updated_at"]},
                {"odd_or_even": ""},
                Schedule(odd_or_even=""),
                {"odd_or_even": "   "},
                Schedule(odd_or_even="   "),
                {"odd_or_even": 123},
                Schedule(odd_or_even=123),
                {"type": ""},
                Schedule(type=""),
                {"type": "   "},
                Schedule(type="   "),
                {"type": 123},
                Schedule(type=123),
                {"is_assessment": "not-bool"},
                Schedule(is_assessment="not-bool"),
                {"day": ""},
                Schedule(day=""),
                {"day": "   "},
                Schedule(day="   "),
                {"day": 123},
                Schedule(day=123),
                {"time": "not-time"},
                Schedule(time="not-time"),
                {"odd_or_even": SCHEDULE_LENGTH_CASES["too_long_odd_or_even"]},
                Schedule(odd_or_even=SCHEDULE_LENGTH_CASES["too_long_odd_or_even"]),
                {"type": SCHEDULE_LENGTH_CASES["too_long_type"]},
                Schedule(type=SCHEDULE_LENGTH_CASES["too_long_type"]),
                {"day": SCHEDULE_LENGTH_CASES["too_long_day"]},
                Schedule(day=SCHEDULE_LENGTH_CASES["too_long_day"]),
                {
                    "odd_or_even": SCHEDULE_LENGTH_CASES["too_long_odd_or_even"],
                    "type": "",
                    "day": 123,
                },
                Schedule(
                    odd_or_even=SCHEDULE_LENGTH_CASES["too_long_odd_or_even"],
                    type="",
                    day=123,
                ),
                {"unknown_field": "data"},
            ),
        ),
        delete=PayloadSet(
            valid=(
                {"id": 1},
                Schedule(id=1),
                {"id": None},
                Schedule(id=None),
                {"odd_or_even": "even"},
                Schedule(odd_or_even="even"),
                {"type": "семинар"},
                Schedule(type="семинар"),
                {"day": "вт"},
                Schedule(day="вт"),
                {"time": time(8, 45)},
                Schedule(time=time(8, 45)),
                {"created_at": BASE_READ_FIELDS["created_at"]},
                {"updated_at": BASE_READ_FIELDS["updated_at"]},
                {"is_assessment": False},
                Schedule(is_assessment=False),
                {"is_assessment": None},
                Schedule(is_assessment=None),
                SCHEDULE_FULL,
                Schedule(**SCHEDULE_FULL),
                {"odd_or_even": None},
                Schedule(odd_or_even=None),
                {"type": None},
                Schedule(type=None),
                {"day": None},
                Schedule(day=None),
                {"time": None},
                Schedule(time=None),
                {"odd_or_even": SCHEDULE_LENGTH_CASES["max_odd_or_even"]},
                Schedule(odd_or_even=SCHEDULE_LENGTH_CASES["max_odd_or_even"]),
                {"type": SCHEDULE_LENGTH_CASES["max_type"]},
                Schedule(type=SCHEDULE_LENGTH_CASES["max_type"]),
                {"day": SCHEDULE_LENGTH_CASES["max_day"]},
                Schedule(day=SCHEDULE_LENGTH_CASES["max_day"]),
            ),
            invalid=(
                {},
                Schedule(),
                {"id": "not-id"},
                Schedule(id="not-id"),
                {"created_at": "not-datetime"},
                {"updated_at": "not-datetime"},
                {"odd_or_even": ""},
                Schedule(odd_or_even=""),
                {"odd_or_even": "   "},
                Schedule(odd_or_even="   "),
                {"odd_or_even": 123},
                Schedule(odd_or_even=123),
                {"type": ""},
                Schedule(type=""),
                {"type": "   "},
                Schedule(type="   "),
                {"type": 123},
                Schedule(type=123),
                {"is_assessment": "not-bool"},
                Schedule(is_assessment="not-bool"),
                {"day": ""},
                Schedule(day=""),
                {"day": "   "},
                Schedule(day="   "),
                {"day": 123},
                Schedule(day=123),
                {"time": "not-time"},
                Schedule(time="not-time"),
                {"odd_or_even": SCHEDULE_LENGTH_CASES["too_long_odd_or_even"]},
                Schedule(odd_or_even=SCHEDULE_LENGTH_CASES["too_long_odd_or_even"]),
                {"type": SCHEDULE_LENGTH_CASES["too_long_type"]},
                Schedule(type=SCHEDULE_LENGTH_CASES["too_long_type"]),
                {"day": SCHEDULE_LENGTH_CASES["too_long_day"]},
                Schedule(day=SCHEDULE_LENGTH_CASES["too_long_day"]),
                {"unknown_field": "data"},
            ),
        ),
        read=PayloadSet(
            valid=(
                BASE_READ_FIELDS,
            ),
            invalid=(
                {**BASE_READ_FIELDS, "day": "вт"},
                {**BASE_READ_FIELDS, "time": time(8, 45)},
            ),
        ),
    ),
    "schedule_group_link": EntitySchemaCase(
        create_schema=ScheduleGroupLinkCreateSchema,
        filter_schema=ScheduleGroupLinkFilterSchema,
        update_schema=ScheduleGroupLinkUpdateSchema,
        delete_schema=ScheduleGroupLinkDeleteSchema,
        read_schema=ScheduleGroupLinkReadSchema,
        create=PayloadSet(
            valid=(
                SCHEDULE_GROUP_LINK_BASE,
                ScheduleGroupLink(**SCHEDULE_GROUP_LINK_BASE),
                {**BASE_READ_FIELDS, **SCHEDULE_GROUP_LINK_BASE},
                ScheduleGroupLink(**BASE_READ_FIELDS, **SCHEDULE_GROUP_LINK_BASE),
            ),
            invalid=(
                {"group_id": 1},
                ScheduleGroupLink(group_id=1),
                {"schedule_id": 2},
                ScheduleGroupLink(schedule_id=2),
                {},
                ScheduleGroupLink(),
                {"group_id": None, "schedule_id": 2},
                ScheduleGroupLink(group_id=None, schedule_id=2),
                {"group_id": 1, "schedule_id": None},
                ScheduleGroupLink(group_id=1, schedule_id=None),
                {"group_id": "not-id", "schedule_id": 2},
                ScheduleGroupLink(group_id="not-id", schedule_id=2),
                {"group_id": 1, "schedule_id": "not-id"},
                ScheduleGroupLink(group_id=1, schedule_id="not-id"),
                {"group_id": "not-id", "schedule_id": None},
                ScheduleGroupLink(group_id="not-id", schedule_id=None),
                {"unknown_field": "data", **SCHEDULE_GROUP_LINK_BASE},
            ),
        ),
        filter=PayloadSet(
            valid=(
                {},
                {"id": 1},
                ScheduleGroupLink(id=1),
                {"group_id": 1},
                ScheduleGroupLink(group_id=1),
                {"schedule_id": 2},
                ScheduleGroupLink(schedule_id=2),
                {"group_id": None},
                ScheduleGroupLink(group_id=None),
                {"schedule_id": None},
                ScheduleGroupLink(schedule_id=None),
                SCHEDULE_GROUP_LINK_BASE,
                ScheduleGroupLink(**SCHEDULE_GROUP_LINK_BASE),
                {"created_at": BASE_READ_FIELDS["created_at"]},
                {"updated_at": BASE_READ_FIELDS["updated_at"]},
                {
                    "id": 1,
                    "created_at": BASE_READ_FIELDS["created_at"],
                    "updated_at": BASE_READ_FIELDS["updated_at"],
                    **SCHEDULE_GROUP_LINK_BASE,
                },
            ),
            invalid=(
                {"id": "not-id"},
                ScheduleGroupLink(id="not-id"),
                {"created_at": "not-datetime"},
                {"updated_at": "not-datetime"},
                {"group_id": "not-id"},
                ScheduleGroupLink(group_id="not-id"),
                {"schedule_id": "not-id"},
                ScheduleGroupLink(schedule_id="not-id"),
                {"group_id": "not-id", "schedule_id": "not-id"},
                ScheduleGroupLink(group_id="not-id", schedule_id="not-id"),
                {"unknown_field": "data"},
            ),
        ),
        update=PayloadSet(
            valid=(),
            invalid=(
                {},
                ScheduleGroupLink(),
                {"group_id": 1, "schedule_id": 2},
                ScheduleGroupLink(group_id=1, schedule_id=2),
                {"schedule_id": 5},
                ScheduleGroupLink(schedule_id=5),
                {"group_id": 1},
                ScheduleGroupLink(group_id=1),
                {"group_id": 1, "schedule_id": None},
                ScheduleGroupLink(group_id=1, schedule_id=None),
                {"unknown_field": "data"},
            ),
        ),
        delete=PayloadSet(
            valid=(
                {"id": 1},
                ScheduleGroupLink(id=1),
                {"id": None},
                ScheduleGroupLink(id=None),
                {"group_id": 1},
                ScheduleGroupLink(group_id=1),
                {"schedule_id": 2},
                ScheduleGroupLink(schedule_id=2),
                {"created_at": BASE_READ_FIELDS["created_at"]},
                {"updated_at": BASE_READ_FIELDS["updated_at"]},
                {"group_id": 1, "schedule_id": None},
                ScheduleGroupLink(group_id=1, schedule_id=None),
                {"group_id": None},
                ScheduleGroupLink(group_id=None),
                {"schedule_id": None},
                ScheduleGroupLink(schedule_id=None),
                SCHEDULE_GROUP_LINK_BASE,
                ScheduleGroupLink(**SCHEDULE_GROUP_LINK_BASE),
            ),
            invalid=(
                {},
                ScheduleGroupLink(),
                {"id": "not-id"},
                ScheduleGroupLink(id="not-id"),
                {"created_at": "not-datetime"},
                {"updated_at": "not-datetime"},
                {"group_id": "not-id"},
                ScheduleGroupLink(group_id="not-id"),
                {"schedule_id": "not-id"},
                ScheduleGroupLink(schedule_id="not-id"),
                {"group_id": "not-id", "schedule_id": "not-id"},
                ScheduleGroupLink(group_id="not-id", schedule_id="not-id"),
                {"unknown_field": "data"},
            ),
        ),
        read=PayloadSet(
            valid=(
                BASE_READ_FIELDS,
            ),
            invalid=(
                {**BASE_READ_FIELDS, "group_id": 1},
                {**BASE_READ_FIELDS, "schedule_id": 2},
            ),
        ),
    ),
    "lesson": EntitySchemaCase(
        create_schema=LessonCreateSchema,
        filter_schema=LessonFilterSchema,
        update_schema=LessonUpdateSchema,
        delete_schema=LessonDeleteSchema,
        read_schema=LessonReadSchema,
        create=PayloadSet(
            valid=(
                LESSON_FULL,
                Lesson(**LESSON_FULL),
                LESSON_MINIMAL,
                Lesson(**LESSON_MINIMAL),
                {**BASE_READ_FIELDS, **LESSON_MINIMAL},
                Lesson(**BASE_READ_FIELDS, **LESSON_MINIMAL),
                {**LESSON_MINIMAL, "topic": None},
                Lesson(**LESSON_MINIMAL, topic=None),
                {**LESSON_MINIMAL, "topic": LESSON_LENGTH_CASES["max_topic"]},
                Lesson(**LESSON_MINIMAL, topic=LESSON_LENGTH_CASES["max_topic"]),
            ),
            invalid=(
                {},
                Lesson(),
                {"topic": "SQLAlchemy", "date": date(2026, 4, 19)},
                Lesson(topic="SQLAlchemy", date=date(2026, 4, 19)),
                {"schedule_id": 1, "topic": "SQLAlchemy"},
                Lesson(schedule_id=1, topic="SQLAlchemy"),
                {"schedule_id": None, "date": date(2026, 4, 19)},
                Lesson(schedule_id=None, date=date(2026, 4, 19)),
                {"schedule_id": "not-id", "date": date(2026, 4, 19)},
                Lesson(schedule_id="not-id", date=date(2026, 4, 19)),
                {"schedule_id": 1, "date": None},
                Lesson(schedule_id=1, date=None),
                {"schedule_id": 1, "date": "not-date"},
                Lesson(schedule_id=1, date="not-date"),
                {**LESSON_MINIMAL, "topic": ""},
                Lesson(**LESSON_MINIMAL, topic=""),
                {**LESSON_MINIMAL, "topic": "   "},
                Lesson(**LESSON_MINIMAL, topic="   "),
                {**LESSON_MINIMAL, "topic": 123},
                Lesson(**LESSON_MINIMAL, topic=123),
                {**LESSON_MINIMAL, "topic": LESSON_LENGTH_CASES["too_long_topic"]},
                Lesson(**LESSON_MINIMAL, topic=LESSON_LENGTH_CASES["too_long_topic"]),
                {
                    "schedule_id": "not-id",
                    "date": "not-date",
                    "topic": LESSON_LENGTH_CASES["too_long_topic"],
                },
                Lesson(
                    schedule_id="not-id",
                    date="not-date",
                    topic=LESSON_LENGTH_CASES["too_long_topic"],
                ),
                {"unknown_field": "data", **LESSON_MINIMAL},
            ),
        ),
        filter=PayloadSet(
            valid=(
                {},
                {"id": 1},
                Lesson(id=1),
                {"schedule_id": 1, "topic": "SQLAlchemy"},
                Lesson(schedule_id=1, topic="SQLAlchemy"),
                {"schedule_id": None},
                Lesson(schedule_id=None),
                {"topic": None},
                Lesson(topic=None),
                {"date": None},
                Lesson(date=None),
                {"date": date(2026, 4, 19)},
                Lesson(date=date(2026, 4, 19)),
                {"created_at": BASE_READ_FIELDS["created_at"]},
                {"updated_at": BASE_READ_FIELDS["updated_at"]},
                {**BASE_READ_FIELDS, **LESSON_FULL},
                Lesson(**BASE_READ_FIELDS, **LESSON_FULL),
                {"topic": LESSON_LENGTH_CASES["max_topic"]},
                Lesson(topic=LESSON_LENGTH_CASES["max_topic"]),
            ),
            invalid=(
                {"id": "not-id"},
                Lesson(id="not-id"),
                {"created_at": "not-datetime"},
                {"updated_at": "not-datetime"},
                {"schedule_id": "not-id"},
                Lesson(schedule_id="not-id"),
                {"topic": ""},
                Lesson(topic=""),
                {"topic": "   "},
                Lesson(topic="   "),
                {"topic": 123},
                Lesson(topic=123),
                {"date": "not-date"},
                Lesson(date="not-date"),
                {"topic": LESSON_LENGTH_CASES["too_long_topic"]},
                Lesson(topic=LESSON_LENGTH_CASES["too_long_topic"]),
                {"schedule_id": "not-id", "topic": "", "date": "not-date"},
                Lesson(schedule_id="not-id", topic="", date="not-date"),
                {"unknown_field": "data"},
            ),
        ),
        update=PayloadSet(
            valid=(
                {"schedule_id": 1, "date": date(2026, 4, 19), "topic": "Pydantic"},
                Lesson(schedule_id=1, date=date(2026, 4, 19), topic="Pydantic"),
                {"schedule_id": 1},
                Lesson(schedule_id=1),
                {"date": date(2026, 4, 19)},
                Lesson(date=date(2026, 4, 19)),
                {"schedule_id": None},
                Lesson(schedule_id=None),
                {"topic": None},
                Lesson(topic=None),
                {"date": None},
                Lesson(date=None),
                {**BASE_READ_FIELDS, "topic": "Pydantic"},
                Lesson(**BASE_READ_FIELDS, topic="Pydantic"),
                {"topic": LESSON_LENGTH_CASES["max_topic"]},
                Lesson(topic=LESSON_LENGTH_CASES["max_topic"]),
            ),
            invalid=(
                {},
                Lesson(),
                {"id": 1},
                Lesson(id=1),
                {"created_at": BASE_READ_FIELDS["created_at"]},
                {"updated_at": BASE_READ_FIELDS["updated_at"]},
                {"schedule_id": "not-id"},
                Lesson(schedule_id="not-id"),
                {"date": "not-date"},
                Lesson(date="not-date"),
                {"topic": ""},
                Lesson(topic=""),
                {"topic": "   "},
                Lesson(topic="   "),
                {"topic": 123},
                Lesson(topic=123),
                {"topic": LESSON_LENGTH_CASES["too_long_topic"]},
                Lesson(topic=LESSON_LENGTH_CASES["too_long_topic"]),
                {"schedule_id": "not-id", "topic": "", "date": "not-date"},
                Lesson(schedule_id="not-id", topic="", date="not-date"),
                {"unknown_field": "data"},
            ),
        ),
        delete=PayloadSet(
            valid=(
                {"id": 1},
                Lesson(id=1),
                {"id": None},
                Lesson(id=None),
                {"schedule_id": 1},
                Lesson(schedule_id=1),
                {"created_at": BASE_READ_FIELDS["created_at"]},
                {"updated_at": BASE_READ_FIELDS["updated_at"]},
                {"date": date(2026, 4, 19)},
                Lesson(date=date(2026, 4, 19)),
                {"schedule_id": None},
                Lesson(schedule_id=None),
                {"topic": None},
                Lesson(topic=None),
                {"date": None},
                Lesson(date=None),
                LESSON_FULL,
                Lesson(**LESSON_FULL),
                {"topic": LESSON_LENGTH_CASES["max_topic"]},
                Lesson(topic=LESSON_LENGTH_CASES["max_topic"]),
            ),
            invalid=(
                {},
                Lesson(),
                {"id": "not-id"},
                Lesson(id="not-id"),
                {"created_at": "not-datetime"},
                {"updated_at": "not-datetime"},
                {"schedule_id": "not-id"},
                Lesson(schedule_id="not-id"),
                {"date": "not-date"},
                Lesson(date="not-date"),
                {"topic": ""},
                Lesson(topic=""),
                {"topic": "   "},
                Lesson(topic="   "),
                {"topic": 123},
                Lesson(topic=123),
                {"topic": LESSON_LENGTH_CASES["too_long_topic"]},
                Lesson(topic=LESSON_LENGTH_CASES["too_long_topic"]),
                {"unknown_field": "data"},
            ),
        ),
        read=PayloadSet(
            valid=(
                BASE_READ_FIELDS,
            ),
            invalid=(
                {**BASE_READ_FIELDS, "schedule_id": 1},
                {**BASE_READ_FIELDS, "date": date(2026, 4, 19)},
            ),
        ),
    ),
    "attendance": EntitySchemaCase(
        create_schema=AttendanceCreateSchema,
        filter_schema=AttendanceFilterSchema,
        update_schema=AttendanceUpdateSchema,
        delete_schema=AttendanceDeleteSchema,
        read_schema=AttendanceReadSchema,
        create=PayloadSet(
            valid=(
                ATTENDANCE_FULL,
                Attendance(**ATTENDANCE_FULL),
                ATTENDANCE_MINIMAL,
                Attendance(**ATTENDANCE_MINIMAL),
                {**BASE_READ_FIELDS, **ATTENDANCE_MINIMAL},
                Attendance(**BASE_READ_FIELDS, **ATTENDANCE_MINIMAL),
                {**ATTENDANCE_MINIMAL, "is_visited": False},
                Attendance(**ATTENDANCE_MINIMAL, is_visited=False),
            ),
            invalid=(
                {"student_id": 1, "is_visited": True},
                Attendance(student_id=1, is_visited=True),
                {"lesson_id": 2, "is_visited": True},
                Attendance(lesson_id=2, is_visited=True),
                {},
                Attendance(),
                {"student_id": None, "lesson_id": 2},
                Attendance(student_id=None, lesson_id=2),
                {"student_id": 1, "lesson_id": None},
                Attendance(student_id=1, lesson_id=None),
                {"student_id": "not-id", "lesson_id": 2},
                Attendance(student_id="not-id", lesson_id=2),
                {"student_id": 1, "lesson_id": "not-id"},
                Attendance(student_id=1, lesson_id="not-id"),
                {**ATTENDANCE_MINIMAL, "is_visited": None},
                Attendance(**ATTENDANCE_MINIMAL, is_visited=None),
                {**ATTENDANCE_MINIMAL, "is_visited": "not-bool"},
                Attendance(**ATTENDANCE_MINIMAL, is_visited="not-bool"),
                {"student_id": "not-id", "lesson_id": None, "is_visited": "not-bool"},
                Attendance(student_id="not-id", lesson_id=None, is_visited="not-bool"),
                {"unknown_field": "data", **ATTENDANCE_MINIMAL},
            ),
        ),
        filter=PayloadSet(
            valid=(
                {},
                {"id": 1},
                Attendance(id=1),
                {"student_id": 1},
                Attendance(student_id=1),
                {"lesson_id": 2},
                Attendance(lesson_id=2),
                {"student_id": 1, "lesson_id": 2},
                Attendance(student_id=1, lesson_id=2),
                {"created_at": BASE_READ_FIELDS["created_at"]},
                {"updated_at": BASE_READ_FIELDS["updated_at"]},
                {"student_id": None},
                Attendance(student_id=None),
                {"lesson_id": None},
                Attendance(lesson_id=None),
                {"is_visited": None},
                Attendance(is_visited=None),
                {"is_visited": False},
                Attendance(is_visited=False),
                {**BASE_READ_FIELDS, **ATTENDANCE_FULL},
            ),
            invalid=(
                {"id": "not-id"},
                Attendance(id="not-id"),
                {"created_at": "not-datetime"},
                {"updated_at": "not-datetime"},
                {"student_id": "not-id"},
                Attendance(student_id="not-id"),
                {"lesson_id": "not-id"},
                Attendance(lesson_id="not-id"),
                {"is_visited": "not-bool"},
                Attendance(is_visited="not-bool"),
                {"student_id": "not-id", "lesson_id": "not-id", "is_visited": "not-bool"},
                Attendance(student_id="not-id", lesson_id="not-id", is_visited="not-bool"),
                {"unknown_field": "data"},
            ),
        ),
        update=PayloadSet(
            valid=(
                {"is_visited": False},
                Attendance(is_visited=False),
                {"is_visited": True},
                Attendance(is_visited=True),
                {**BASE_READ_FIELDS, "is_visited": True},
                Attendance(**BASE_READ_FIELDS, is_visited=True),
            ),
            invalid=(
                {},
                Attendance(),
                {"id": 1},
                Attendance(id=1),
                {"created_at": BASE_READ_FIELDS["created_at"]},
                {"updated_at": BASE_READ_FIELDS["updated_at"]},
                {"is_visited": None},
                Attendance(is_visited=None),
                {"is_visited": "not-bool"},
                Attendance(is_visited="not-bool"),
                {"student_id": 1},
                Attendance(student_id=1),
                {"lesson_id": 2},
                Attendance(lesson_id=2),
                {"unknown_field": "data"},
            ),
        ),
        delete=PayloadSet(
            valid=(
                {"id": 1},
                Attendance(id=1),
                {"id": None},
                Attendance(id=None),
                {"student_id": 1},
                Attendance(student_id=1),
                {"lesson_id": 2},
                Attendance(lesson_id=2),
                {"student_id": 1, "lesson_id": 2},
                Attendance(student_id=1, lesson_id=2),
                {"created_at": BASE_READ_FIELDS["created_at"]},
                {"updated_at": BASE_READ_FIELDS["updated_at"]},
                {"is_visited": None},
                Attendance(is_visited=None),
                {"is_visited": False},
                Attendance(is_visited=False),
                ATTENDANCE_FULL,
                Attendance(**ATTENDANCE_FULL),
                {"student_id": None},
                Attendance(student_id=None),
                {"lesson_id": None},
                Attendance(lesson_id=None),
            ),
            invalid=(
                {},
                Attendance(),
                {"id": "not-id"},
                Attendance(id="not-id"),
                {"created_at": "not-datetime"},
                {"updated_at": "not-datetime"},
                {"student_id": "not-id"},
                Attendance(student_id="not-id"),
                {"lesson_id": "not-id"},
                Attendance(lesson_id="not-id"),
                {"is_visited": "not-bool"},
                Attendance(is_visited="not-bool"),
                {"student_id": "not-id", "lesson_id": "not-id", "is_visited": "not-bool"},
                Attendance(student_id="not-id", lesson_id="not-id", is_visited="not-bool"),
                {"unknown_field": "data"},
            ),
        ),
        read=PayloadSet(
            valid=(
                BASE_READ_FIELDS,
            ),
            invalid=(
                {**BASE_READ_FIELDS, "student_id": 1},
                {**BASE_READ_FIELDS, "is_visited": True},
            ),
        ),
    ),
    "mark": EntitySchemaCase(
        create_schema=MarkCreateSchema,
        filter_schema=MarkFilterSchema,
        update_schema=MarkUpdateSchema,
        delete_schema=MarkDeleteSchema,
        read_schema=MarkReadSchema,
        create=PayloadSet(
            valid=(
                MARK_BASE,
                Mark(**MARK_BASE),
                {**BASE_READ_FIELDS, **MARK_BASE},
                Mark(**BASE_READ_FIELDS, **MARK_BASE),
                {**MARK_BASE, "data": 0},
                Mark(student_id=1, lesson_id=2, data=0),
            ),
            invalid=(
                {"student_id": 1, "lesson_id": 2},
                Mark(student_id=1, lesson_id=2),
                {"student_id": 1, "data": 5},
                Mark(student_id=1, data=5),
                {"lesson_id": 2, "data": 5},
                Mark(lesson_id=2, data=5),
                {},
                Mark(),
                {"student_id": None, "lesson_id": 2, "data": 5},
                Mark(student_id=None, lesson_id=2, data=5),
                {"student_id": 1, "lesson_id": None, "data": 5},
                Mark(student_id=1, lesson_id=None, data=5),
                {"student_id": 1, "lesson_id": 2, "data": None},
                Mark(student_id=1, lesson_id=2, data=None),
                {"student_id": "not-id", "lesson_id": 2, "data": 5},
                Mark(student_id="not-id", lesson_id=2, data=5),
                {"student_id": 1, "lesson_id": "not-id", "data": 5},
                Mark(student_id=1, lesson_id="not-id", data=5),
                {"student_id": 1, "lesson_id": 2, "data": "not-mark"},
                Mark(student_id=1, lesson_id=2, data="not-mark"),
                {"student_id": "not-id", "lesson_id": None, "data": "not-mark"},
                Mark(student_id="not-id", lesson_id=None, data="not-mark"),
                {"unknown_field": "data", **MARK_BASE},
            ),
        ),
        filter=PayloadSet(
            valid=(
                {},
                {"id": 1},
                Mark(id=1),
                {"student_id": 1},
                Mark(student_id=1),
                {"lesson_id": 2},
                Mark(lesson_id=2),
                {"student_id": 1, "lesson_id": 2},
                Mark(student_id=1, lesson_id=2),
                {"created_at": BASE_READ_FIELDS["created_at"]},
                {"updated_at": BASE_READ_FIELDS["updated_at"]},
                {"data": None},
                Mark(data=None),
                {"student_id": None},
                Mark(student_id=None),
                {"lesson_id": None},
                Mark(lesson_id=None),
                {"data": 5},
                Mark(data=5),
                {**BASE_READ_FIELDS, **MARK_BASE},
            ),
            invalid=(
                {"id": "not-id"},
                Mark(id="not-id"),
                {"created_at": "not-datetime"},
                {"updated_at": "not-datetime"},
                {"student_id": "not-id"},
                Mark(student_id="not-id"),
                {"lesson_id": "not-id"},
                Mark(lesson_id="not-id"),
                {"data": "not-mark"},
                Mark(data="not-mark"),
                {"student_id": "not-id", "lesson_id": "not-id", "data": "not-mark"},
                Mark(student_id="not-id", lesson_id="not-id", data="not-mark"),
                {"unknown_field": "data"},
            ),
        ),
        update=PayloadSet(
            valid=(
                {"data": 4},
                Mark(data=4),
                {"data": 5},
                Mark(data=5),
                {**BASE_READ_FIELDS, "data": 5},
                Mark(**BASE_READ_FIELDS, data=5),
            ),
            invalid=(
                {},
                Mark(),
                {"id": 1},
                Mark(id=1),
                {"created_at": BASE_READ_FIELDS["created_at"]},
                {"updated_at": BASE_READ_FIELDS["updated_at"]},
                {"data": None},
                Mark(data=None),
                {"data": "not-mark"},
                Mark(data="not-mark"),
                {"student_id": 1},
                Mark(student_id=1),
                {"lesson_id": 2},
                Mark(lesson_id=2),
                {"unknown_field": "data"},
            ),
        ),
        delete=PayloadSet(
            valid=(
                {"id": 1},
                Mark(id=1),
                {"id": None},
                Mark(id=None),
                {"student_id": 1},
                Mark(student_id=1),
                {"lesson_id": 2},
                Mark(lesson_id=2),
                {"student_id": 1, "lesson_id": 2},
                Mark(student_id=1, lesson_id=2),
                {"created_at": BASE_READ_FIELDS["created_at"]},
                {"updated_at": BASE_READ_FIELDS["updated_at"]},
                {"data": 5},
                Mark(data=5),
                {"data": None},
                Mark(data=None),
                {"student_id": None},
                Mark(student_id=None),
                {"lesson_id": None},
                Mark(lesson_id=None),
                MARK_BASE,
                Mark(**MARK_BASE),
            ),
            invalid=(
                {},
                Mark(),
                {"id": "not-id"},
                Mark(id="not-id"),
                {"created_at": "not-datetime"},
                {"updated_at": "not-datetime"},
                {"student_id": "not-id"},
                Mark(student_id="not-id"),
                {"lesson_id": "not-id"},
                Mark(lesson_id="not-id"),
                {"data": "not-mark"},
                Mark(data="not-mark"),
                {"student_id": "not-id", "lesson_id": "not-id", "data": "not-mark"},
                Mark(student_id="not-id", lesson_id="not-id", data="not-mark"),
                {"unknown_field": "data"},
            ),
        ),
        read=PayloadSet(
            valid=(
                BASE_READ_FIELDS,
            ),
            invalid=(
                {**BASE_READ_FIELDS, "student_id": 1},
                {**BASE_READ_FIELDS, "data": 5},
            ),
        ),
    ),
    "comment": EntitySchemaCase(
        create_schema=CommentCreateSchema,
        filter_schema=CommentFilterSchema,
        update_schema=CommentUpdateSchema,
        delete_schema=CommentDeleteSchema,
        read_schema=CommentReadSchema,
        create=PayloadSet(
            valid=(
                COMMENT_FULL,
                Comment(**COMMENT_FULL),
                COMMENT_MINIMAL,
                Comment(**COMMENT_MINIMAL),
                {**BASE_READ_FIELDS, **COMMENT_MINIMAL},
                Comment(**BASE_READ_FIELDS, **COMMENT_MINIMAL),
                {**COMMENT_MINIMAL, "data": None},
                Comment(**COMMENT_MINIMAL, data=None),
                {**COMMENT_MINIMAL, "data": COMMENT_LENGTH_CASES["max_data"]},
                Comment(**COMMENT_MINIMAL, data=COMMENT_LENGTH_CASES["max_data"]),
            ),
            invalid=(
                {"student_id": 1, "data": "Отличная работа"},
                Comment(student_id=1, data="Отличная работа"),
                {"lesson_id": 2, "data": "Отличная работа"},
                Comment(lesson_id=2, data="Отличная работа"),
                {},
                Comment(),
                {"student_id": None, "lesson_id": 2, "data": "Отличная работа"},
                Comment(student_id=None, lesson_id=2, data="Отличная работа"),
                {"student_id": 1, "lesson_id": None, "data": "Отличная работа"},
                Comment(student_id=1, lesson_id=None, data="Отличная работа"),
                {"student_id": "not-id", "lesson_id": 2, "data": "Отличная работа"},
                Comment(student_id="not-id", lesson_id=2, data="Отличная работа"),
                {"student_id": 1, "lesson_id": "not-id", "data": "Отличная работа"},
                Comment(student_id=1, lesson_id="not-id", data="Отличная работа"),
                {"student_id": 1, "lesson_id": 2, "data": ""},
                Comment(student_id=1, lesson_id=2, data=""),
                {"student_id": 1, "lesson_id": 2, "data": "   "},
                Comment(student_id=1, lesson_id=2, data="   "),
                {"student_id": 1, "lesson_id": 2, "data": 123},
                Comment(student_id=1, lesson_id=2, data=123),
                {**COMMENT_MINIMAL, "data": COMMENT_LENGTH_CASES["too_long_data"]},
                Comment(**COMMENT_MINIMAL, data=COMMENT_LENGTH_CASES["too_long_data"]),
                {
                    "student_id": "not-id",
                    "lesson_id": None,
                    "data": COMMENT_LENGTH_CASES["too_long_data"],
                },
                Comment(
                    student_id="not-id",
                    lesson_id=None,
                    data=COMMENT_LENGTH_CASES["too_long_data"],
                ),
                {"unknown_field": "data", **COMMENT_MINIMAL},
            ),
        ),
        filter=PayloadSet(
            valid=(
                {},
                {"id": 1},
                Comment(id=1),
                {"student_id": 1},
                Comment(student_id=1),
                {"lesson_id": 2},
                Comment(lesson_id=2),
                {"lesson_id": 2, "data": "Отличная работа"},
                Comment(lesson_id=2, data="Отличная работа"),
                {"created_at": BASE_READ_FIELDS["created_at"]},
                {"updated_at": BASE_READ_FIELDS["updated_at"]},
                {"data": None},
                Comment(data=None),
                {"student_id": None},
                Comment(student_id=None),
                {"lesson_id": None},
                Comment(lesson_id=None),
                COMMENT_FULL,
                Comment(**COMMENT_FULL),
                {**BASE_READ_FIELDS, **COMMENT_FULL},
                {"data": COMMENT_LENGTH_CASES["max_data"]},
                Comment(data=COMMENT_LENGTH_CASES["max_data"]),
            ),
            invalid=(
                {"id": "not-id"},
                Comment(id="not-id"),
                {"created_at": "not-datetime"},
                {"updated_at": "not-datetime"},
                {"student_id": "not-id"},
                Comment(student_id="not-id"),
                {"lesson_id": "not-id"},
                Comment(lesson_id="not-id"),
                {"data": ""},
                Comment(data=""),
                {"data": "   "},
                Comment(data="   "),
                {"data": 123},
                Comment(data=123),
                {"data": COMMENT_LENGTH_CASES["too_long_data"]},
                Comment(data=COMMENT_LENGTH_CASES["too_long_data"]),
                {
                    "student_id": "not-id",
                    "lesson_id": "not-id",
                    "data": COMMENT_LENGTH_CASES["too_long_data"],
                },
                Comment(
                    student_id="not-id",
                    lesson_id="not-id",
                    data=COMMENT_LENGTH_CASES["too_long_data"],
                ),
                {"unknown_field": "data"},
            ),
        ),
        update=PayloadSet(
            valid=(
                {"data": "Комментарий обновлен"},
                Comment(data="Комментарий обновлен"),
                {"data": None},
                Comment(data=None),
                {**BASE_READ_FIELDS, "data": "Комментарий обновлен"},
                Comment(**BASE_READ_FIELDS, data="Комментарий обновлен"),
                {"data": COMMENT_LENGTH_CASES["max_data"]},
                Comment(data=COMMENT_LENGTH_CASES["max_data"]),
            ),
            invalid=(
                {},
                Comment(),
                {"id": 1},
                Comment(id=1),
                {"created_at": BASE_READ_FIELDS["created_at"]},
                {"updated_at": BASE_READ_FIELDS["updated_at"]},
                {"data": ""},
                Comment(data=""),
                {"data": "   "},
                Comment(data="   "),
                {"data": 123},
                Comment(data=123),
                {"data": COMMENT_LENGTH_CASES["too_long_data"]},
                Comment(data=COMMENT_LENGTH_CASES["too_long_data"]),
                {"student_id": 1},
                Comment(student_id=1),
                {"lesson_id": 2},
                Comment(lesson_id=2),
                {"unknown_field": "data"},
            ),
        ),
        delete=PayloadSet(
            valid=(
                {"id": 1},
                Comment(id=1),
                {"id": None},
                Comment(id=None),
                {"student_id": 1},
                Comment(student_id=1),
                {"lesson_id": 2},
                Comment(lesson_id=2),
                {"created_at": BASE_READ_FIELDS["created_at"]},
                {"updated_at": BASE_READ_FIELDS["updated_at"]},
                {"data": "Отличная работа"},
                Comment(data="Отличная работа"),
                {"data": None},
                Comment(data=None),
                {"student_id": None},
                Comment(student_id=None),
                {"lesson_id": None},
                Comment(lesson_id=None),
                COMMENT_FULL,
                Comment(**COMMENT_FULL),
                {"data": COMMENT_LENGTH_CASES["max_data"]},
                Comment(data=COMMENT_LENGTH_CASES["max_data"]),
            ),
            invalid=(
                {},
                Comment(),
                {"id": "not-id"},
                Comment(id="not-id"),
                {"created_at": "not-datetime"},
                {"updated_at": "not-datetime"},
                {"student_id": "not-id"},
                Comment(student_id="not-id"),
                {"lesson_id": "not-id"},
                Comment(lesson_id="not-id"),
                {"student_id": 1, "data": ""},
                Comment(student_id=1, data=""),
                {"data": "   "},
                Comment(data="   "),
                {"data": 123},
                Comment(data=123),
                {"data": COMMENT_LENGTH_CASES["too_long_data"]},
                Comment(data=COMMENT_LENGTH_CASES["too_long_data"]),
                {
                    "student_id": "not-id",
                    "lesson_id": "not-id",
                    "data": COMMENT_LENGTH_CASES["too_long_data"],
                },
                Comment(
                    student_id="not-id",
                    lesson_id="not-id",
                    data=COMMENT_LENGTH_CASES["too_long_data"],
                ),
                {"unknown_field": "data"},
            ),
        ),
        read=PayloadSet(
            valid=(
                BASE_READ_FIELDS,
            ),
            invalid=(
                {**BASE_READ_FIELDS, "student_id": 1},
                {**BASE_READ_FIELDS, "data": "Отличная работа"},
            ),
        ),
    ),
}


def schema_params(operation_name: str, payload_kind: str) -> list[pytest.ParameterSet]:
    """
    Собирает параметры теста из общего реестра схем.
    """
    params = []
    for entity_name, case in SCHEMA_CASES_BY_ENTITY.items():
        schema_class = getattr(case, f"{operation_name}_schema")
        payloads = getattr(case, operation_name)
        for index, payload in enumerate(getattr(payloads, payload_kind), start=1):
            params.append(
                pytest.param(
                    schema_class,
                    payload,
                    id=f"{entity_name}-{operation_name}-{payload_kind}-{index}",
                )
            )

    return params


def payload_to_dict(payload: Payload) -> dict[str, Any]:
    """
    Приводит dict, Pydantic-схему или ORM-объект к словарю переданных полей.
    """
    if isinstance(payload, BaseModel):
        return payload.model_dump(exclude_unset=True)

    if isinstance(payload, dict):
        return payload

    return {
        key: value
        for key, value in payload.__dict__.items()
        if not key.startswith("_")
    }


def assert_payload_values(
    schema: BaseModel,
    payload: Payload,
    ignored_fields: set[str] | None = None,
) -> None:
    """
    Проверяет, что схема сохранила значения, переданные в payload.
    """
    ignored_fields = ignored_fields or set()
    for key, value in payload_to_dict(payload).items():
        if key in ignored_fields:
            continue

        assert getattr(schema, key) == value


@pytest.mark.parametrize(("schema_class", "payload"), schema_params("create", "valid"))
def test_create_schema_accepts_valid_payload(schema_class: SchemaType, payload: Payload):
    """
    Схема создания принимает корректные данные.
    """
    schema = schema_class.model_validate(payload_to_dict(payload))

    assert_payload_values(schema, payload, {"id", "created_at", "updated_at"})


@pytest.mark.parametrize(("schema_class", "payload"), schema_params("create", "invalid"))
def test_create_schema_rejects_invalid_payload(schema_class: SchemaType, payload: Payload):
    """
    Схема создания отклоняет некорректные данные.
    """
    with pytest.raises(ValidationError):
        schema_class.model_validate(payload_to_dict(payload))


@pytest.mark.parametrize(("schema_class", "payload"), schema_params("filter", "valid"))
def test_filter_schema_accepts_valid_payload(schema_class: SchemaType, payload: Payload):
    """
    Схема фильтра принимает корректные данные.
    """
    schema = schema_class.model_validate(payload_to_dict(payload))

    assert_payload_values(schema, payload)


@pytest.mark.parametrize(("schema_class", "payload"), schema_params("filter", "invalid"))
def test_filter_schema_rejects_invalid_payload(schema_class: SchemaType, payload: Payload):
    """
    Схема фильтра отклоняет некорректные данные.
    """
    with pytest.raises(ValidationError):
        schema_class.model_validate(payload_to_dict(payload))


@pytest.mark.parametrize(("schema_class", "payload"), schema_params("update", "valid"))
def test_update_schema_accepts_valid_payload(schema_class: SchemaType, payload: Payload):
    """
    Схема обновления принимает корректные данные.
    """
    schema = schema_class.model_validate(payload_to_dict(payload))

    assert_payload_values(schema, payload, {"id", "created_at", "updated_at"})


@pytest.mark.parametrize(("schema_class", "payload"), schema_params("update", "invalid"))
def test_update_schema_rejects_invalid_payload(schema_class: SchemaType, payload: Payload):
    """
    Схема обновления отклоняет некорректные данные.
    """
    with pytest.raises(ValidationError):
        schema_class.model_validate(payload_to_dict(payload))


@pytest.mark.parametrize(("schema_class", "payload"), schema_params("delete", "valid"))
def test_delete_schema_accepts_valid_payload(schema_class: SchemaType, payload: Payload):
    """
    Схема удаления принимает корректные данные.
    """
    schema = schema_class.model_validate(payload_to_dict(payload))

    assert_payload_values(schema, payload)


@pytest.mark.parametrize(("schema_class", "payload"), schema_params("delete", "invalid"))
def test_delete_schema_rejects_invalid_payload(schema_class: SchemaType, payload: Payload):
    """
    Схема удаления отклоняет некорректные данные.
    """
    with pytest.raises(ValidationError):
        schema_class.model_validate(payload_to_dict(payload))


@pytest.mark.parametrize(("schema_class", "payload"), schema_params("read", "valid"))
def test_read_schema_accepts_valid_payload(schema_class: SchemaType, payload: Payload):
    """
    Read-схема корректно валидирует данные чтения.
    """
    schema = schema_class.model_validate(payload_to_dict(payload))

    assert_payload_values(schema, payload)


@pytest.mark.parametrize(("schema_class", "payload"), schema_params("read", "invalid"))
def test_read_schema_rejects_invalid_payload(schema_class: SchemaType, payload: Payload):
    """
    Read-схема отклоняет некорректные данные чтения.
    """
    with pytest.raises(ValidationError):
        schema_class.model_validate(payload_to_dict(payload))


def test_is_group_name_formatted():
    """
    Helper для формата названия группы работает корректно.
    """
    values = {
        "СМ1-21Б": True,
        "ИУ7-31": True,
        "AA1-11": False,
        "не группа": False,
    }

    for value, expected in values.items():
        assert is_group_name_formatted(value) is expected


def test_is_speciality_formatted():
    """
    Helper для формата специальности работает корректно.
    """
    values = {
        "24.03.01_Информатика": True,
        "09.03.02_Программирование": True,
        "24.03.01": False,
        "специальность": False,
    }

    for value, expected in values.items():
        assert is_speciality_formatted(value) is expected


def test_group_create_schema_ignores_service_fields():
    """
    GroupCreateSchema игнорирует служебные поля.
    """
    schema = GroupCreateSchema.model_validate(
        {
            "id": 10,
            "created_at": BASE_READ_FIELDS["created_at"],
            "updated_at": BASE_READ_FIELDS["updated_at"],
            "name": "ИУ7-31",
            "speciality": "09.03.01_Информатика",
        }
    )

    assert schema.model_dump(exclude_unset=True) == {
        "name": "ИУ7-31",
        "speciality": "09.03.01_Информатика",
    }



def test_group_update_schema_ignores_service_fields():
    """
    GroupUpdateSchema игнорирует служебные поля.
    """
    schema = GroupUpdateSchema.model_validate(
        {
            "id": 10,
            "created_at": BASE_READ_FIELDS["created_at"],
            "updated_at": BASE_READ_FIELDS["updated_at"],
            "name": "ИУ7-31",
        }
    )

    assert schema.model_dump(exclude_unset=True) == {
        "name": "ИУ7-31",
    }


@pytest.mark.parametrize(
    ("schema_class", "payload", "expected"),
    (
        (
            StudentCreateSchema,
            {
                "id": 1,
                "created_at": BASE_READ_FIELDS["created_at"],
                "updated_at": BASE_READ_FIELDS["updated_at"],
                "group_id": 1,
                "surname": "Петров",
                "first_name": "Петр",
            },
            {
                "group_id": 1,
                "surname": "Петров",
                "first_name": "Петр",
            },
        ),
        (
            ScheduleCreateSchema,
            {
                "id": 1,
                "created_at": BASE_READ_FIELDS["created_at"],
                "updated_at": BASE_READ_FIELDS["updated_at"],
                "odd_or_even": "even",
                "type": "семинар",
                "day": "вт",
                "time": time(8, 45),
            },
            {
                "odd_or_even": "even",
                "type": "семинар",
                "day": "вт",
                "time": time(8, 45),
            },
        ),
        (
            ScheduleGroupLinkCreateSchema,
            {
                "id": 1,
                "created_at": BASE_READ_FIELDS["created_at"],
                "updated_at": BASE_READ_FIELDS["updated_at"],
                "group_id": 1,
                "schedule_id": 2,
            },
            {
                "group_id": 1,
                "schedule_id": 2,
            },
        ),
        (
            LessonCreateSchema,
            {
                "id": 1,
                "created_at": BASE_READ_FIELDS["created_at"],
                "updated_at": BASE_READ_FIELDS["updated_at"],
                "schedule_id": 1,
                "date": date(2026, 4, 19),
            },
            {
                "schedule_id": 1,
                "date": date(2026, 4, 19),
            },
        ),
        (
            AttendanceCreateSchema,
            {
                "id": 1,
                "created_at": BASE_READ_FIELDS["created_at"],
                "updated_at": BASE_READ_FIELDS["updated_at"],
                "student_id": 1,
                "lesson_id": 2,
            },
            {
                "student_id": 1,
                "lesson_id": 2,
            },
        ),
        (
            MarkCreateSchema,
            {
                "id": 1,
                "created_at": BASE_READ_FIELDS["created_at"],
                "updated_at": BASE_READ_FIELDS["updated_at"],
                "student_id": 1,
                "lesson_id": 2,
                "data": 5,
            },
            {
                "student_id": 1,
                "lesson_id": 2,
                "data": 5,
            },
        ),
        (
            CommentCreateSchema,
            {
                "id": 1,
                "created_at": BASE_READ_FIELDS["created_at"],
                "updated_at": BASE_READ_FIELDS["updated_at"],
                "student_id": 1,
                "lesson_id": 2,
                "data": "Комментарий",
            },
            {
                "student_id": 1,
                "lesson_id": 2,
                "data": "Комментарий",
            },
        ),
    ),
)
def test_create_schema_ignores_service_fields(
    schema_class: SchemaType,
    payload: dict[str, Any],
    expected: dict[str, Any],
):
    """
    Create-схемы игнорируют служебные поля.
    """
    schema = schema_class.model_validate(payload)

    assert schema.model_dump(exclude_unset=True) == expected


@pytest.mark.parametrize(
    ("schema_class", "payload", "expected"),
    (
        (
            StudentUpdateSchema,
            {
                "id": 1,
                "created_at": BASE_READ_FIELDS["created_at"],
                "updated_at": BASE_READ_FIELDS["updated_at"],
                "first_name": "Алексей",
            },
            {"first_name": "Алексей"},
        ),
        (
            ScheduleUpdateSchema,
            {
                "id": 1,
                "created_at": BASE_READ_FIELDS["created_at"],
                "updated_at": BASE_READ_FIELDS["updated_at"],
                "is_assessment": True,
            },
            {"is_assessment": True},
        ),
        (
            LessonUpdateSchema,
            {
                "id": 1,
                "created_at": BASE_READ_FIELDS["created_at"],
                "updated_at": BASE_READ_FIELDS["updated_at"],
                "topic": None,
            },
            {"topic": None},
        ),
        (
            AttendanceUpdateSchema,
            {
                "id": 1,
                "created_at": BASE_READ_FIELDS["created_at"],
                "updated_at": BASE_READ_FIELDS["updated_at"],
                "is_visited": True,
            },
            {"is_visited": True},
        ),
        (
            MarkUpdateSchema,
            {
                "id": 1,
                "created_at": BASE_READ_FIELDS["created_at"],
                "updated_at": BASE_READ_FIELDS["updated_at"],
                "data": 5,
            },
            {"data": 5},
        ),
        (
            CommentUpdateSchema,
            {
                "id": 1,
                "created_at": BASE_READ_FIELDS["created_at"],
                "updated_at": BASE_READ_FIELDS["updated_at"],
                "data": "Комментарий обновлен",
            },
            {"data": "Комментарий обновлен"},
        ),
    ),
)
def test_update_schema_ignores_service_fields(
    schema_class: SchemaType,
    payload: dict[str, Any],
    expected: dict[str, Any],
):
    """
    Update-схемы игнорируют служебные поля.
    """
    schema = schema_class.model_validate(payload)

    assert schema.model_dump(exclude_unset=True) == expected


@pytest.mark.parametrize(
    ("schema_class", "payload"),
    (
        (StudentFilterSchema, SERVICE_FILTER_FIELDS),
        (ScheduleFilterSchema, SERVICE_FILTER_FIELDS),
        (ScheduleGroupLinkFilterSchema, SERVICE_FILTER_FIELDS),
        (LessonFilterSchema, SERVICE_FILTER_FIELDS),
        (AttendanceFilterSchema, SERVICE_FILTER_FIELDS),
        (MarkFilterSchema, SERVICE_FILTER_FIELDS),
        (CommentFilterSchema, SERVICE_FILTER_FIELDS),
    ),
)
def test_filter_schema_keeps_service_fields(
    schema_class: SchemaType,
    payload: dict[str, Any],
):
    """
    Filter-схемы учитывают служебные поля как поля фильтра.
    """
    schema = schema_class.model_validate(payload)

    assert schema.model_dump(exclude_unset=True) == payload


@pytest.mark.parametrize(
    ("schema_class", "payload"),
    (
        (StudentDeleteSchema, SERVICE_FILTER_FIELDS),
        (ScheduleDeleteSchema, SERVICE_FILTER_FIELDS),
        (ScheduleGroupLinkDeleteSchema, SERVICE_FILTER_FIELDS),
        (LessonDeleteSchema, SERVICE_FILTER_FIELDS),
        (AttendanceDeleteSchema, SERVICE_FILTER_FIELDS),
        (MarkDeleteSchema, SERVICE_FILTER_FIELDS),
        (CommentDeleteSchema, SERVICE_FILTER_FIELDS),
    ),
)
def test_delete_schema_keeps_service_fields(
    schema_class: SchemaType,
    payload: dict[str, Any],
):
    """
    Delete-схемы учитывают служебные поля как поля фильтра.
    """
    schema = schema_class.model_validate(payload)

    assert schema.model_dump(exclude_unset=True) == payload
