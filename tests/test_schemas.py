"""
Тестирование Pydantic-схем проекта.
"""
# pylint: disable=import-error
from datetime import datetime, date, time

import pytest
from pydantic import ValidationError

from app.schemas.group import (
    GroupCreateSchema,
    GroupDeleteSchema,
    GroupFilterSchema,
    GroupReadSchema,
    GroupUpdateSchema,
    is_group_name_formatted,
    is_speciality_formatted,
)
from app.schemas.student import (
    StudentCreateSchema,
    StudentDeleteSchema,
    StudentFilterSchema,
    StudentReadSchema,
    StudentUpdateSchema,
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
from app.schemas.lesson import (
    LessonCreateSchema,
    LessonDeleteSchema,
    LessonFilterSchema,
    LessonReadSchema,
    LessonUpdateSchema,
)
from app.schemas.attendance import (
    AttendanceCreateSchema,
    AttendanceDeleteSchema,
    AttendanceFilterSchema,
    AttendanceReadSchema,
    AttendanceUpdateSchema,
)
from app.schemas.mark import (
    MarkCreateSchema,
    MarkDeleteSchema,
    MarkFilterSchema,
    MarkReadSchema,
    MarkUpdateSchema,
)
from app.schemas.comment import (
    CommentCreateSchema,
    CommentDeleteSchema,
    CommentFilterSchema,
    CommentReadSchema,
    CommentUpdateSchema,
)


SCHEMA_CASES = [
    {
        "name": "group",
        "create_schema": GroupCreateSchema,
        "filter_schema": GroupFilterSchema,
        "update_schema": GroupUpdateSchema,
        "delete_schema": GroupDeleteSchema,
        "read_schema": GroupReadSchema,
        "create_valid": {"name": "СМ1-21Б", "speciality": "24.03.01_Информатика"},
        "create_invalid": {"name": ""},
        "filter_valid": {"speciality": "24.03.01_Информатика"},
        "filter_invalid": {"name": ""},
        "update_valid": {"name": "ИУ7-31"},
        "update_invalid": {},
        "delete_valid": {"name": "СМ1-21Б"},
        "delete_invalid": {},
        "read_valid": {
            "id": 1,
            "created_at": datetime(2026, 4, 19, 10, 0, 0),
            "updated_at": datetime(2026, 4, 19, 10, 5, 0),
            "name": "СМ1-21Б",
            "speciality": "24.03.01_Информатика",
        },
    },
    {
        "name": "student",
        "create_schema": StudentCreateSchema,
        "filter_schema": StudentFilterSchema,
        "update_schema": StudentUpdateSchema,
        "delete_schema": StudentDeleteSchema,
        "read_schema": StudentReadSchema,
        "create_valid": {
            "group_id": 1,
            "surname": "Петров",
            "first_name": "Петр",
            "patronymic": "Петрович",
        },
        "create_invalid": {"group_id": 1, "surname": "", "first_name": "Петр"},
        "filter_valid": {"group_id": 1, "surname": "Петров"},
        "filter_invalid": {"surname": ""},
        "update_valid": {"first_name": "Алексей"},
        "update_invalid": {},
        "delete_valid": {"group_id": 1},
        "delete_invalid": {},
        "read_valid": {
            "id": 1,
            "created_at": datetime(2026, 4, 19, 10, 0, 0),
            "updated_at": datetime(2026, 4, 19, 10, 5, 0),
            "group_id": 1,
            "surname": "Петров",
            "first_name": "Петр",
            "patronymic": "Петрович",
            "personal_data": "00М000",
            "bmstu_email": "petrov@student.bmstu.ru",
        },
    },
    {
        "name": "schedule",
        "create_schema": ScheduleCreateSchema,
        "filter_schema": ScheduleFilterSchema,
        "update_schema": ScheduleUpdateSchema,
        "delete_schema": ScheduleDeleteSchema,
        "read_schema": ScheduleReadSchema,
        "create_valid": {
            "odd_or_even": "even",
            "type": "семинар",
            "day": "вт",
            "time": time(8, 45),
        },
        "create_invalid": {
            "odd_or_even": "",
            "type": "семинар",
            "day": "вт",
            "time": time(8, 45),
        },
        "filter_valid": {"day": "вт"},
        "filter_invalid": {"type": ""},
        "update_valid": {"is_assessment": True},
        "update_invalid": {},
        "delete_valid": {"day": "вт"},
        "delete_invalid": {},
        "read_valid": {
            "id": 1,
            "created_at": datetime(2026, 4, 19, 10, 0, 0),
            "updated_at": datetime(2026, 4, 19, 10, 5, 0),
            "odd_or_even": "even",
            "type": "семинар",
            "is_assessment": False,
            "day": "вт",
            "time": time(8, 45),
        },
    },
    {
        "name": "schedule_group_link",
        "create_schema": ScheduleGroupLinkCreateSchema,
        "filter_schema": ScheduleGroupLinkFilterSchema,
        "update_schema": ScheduleGroupLinkUpdateSchema,
        "delete_schema": ScheduleGroupLinkDeleteSchema,
        "read_schema": ScheduleGroupLinkReadSchema,
        "create_valid": {"group_id": 1, "schedule_id": 2},
        "create_invalid": {"group_id": 1},
        "filter_valid": {"group_id": 1},
        "filter_invalid": {"unknown_field": "data"},
        "update_valid": {"schedule_id": 5},
        "update_invalid": {},
        "delete_valid": {"group_id": 1, "schedule_id": 2},
        "delete_invalid": {},
        "read_valid": {
            "id": 1,
            "created_at": datetime(2026, 4, 19, 10, 0, 0),
            "updated_at": datetime(2026, 4, 19, 10, 5, 0),
            "group_id": 1,
            "schedule_id": 2,
        },
    },
    {
        "name": "lesson",
        "create_schema": LessonCreateSchema,
        "filter_schema": LessonFilterSchema,
        "update_schema": LessonUpdateSchema,
        "delete_schema": LessonDeleteSchema,
        "read_schema": LessonReadSchema,
        "create_valid": {"schedule_id": 1, "topic": "SQLAlchemy", "date": date(2026, 4, 19)},
        "create_invalid": {"schedule_id": 1, "topic": "", "date": date(2026, 4, 19)},
        "filter_valid": {"schedule_id": 1, "topic": "SQLAlchemy"},
        "filter_invalid": {"topic": ""},
        "update_valid": {"date": date(2026, 4, 20)},
        "update_invalid": {},
        "delete_valid": {"schedule_id": 1},
        "delete_invalid": {},
        "read_valid": {
            "id": 1,
            "created_at": datetime(2026, 4, 19, 10, 0, 0),
            "updated_at": datetime(2026, 4, 19, 10, 5, 0),
            "schedule_id": 1,
            "topic": "SQLAlchemy",
            "date": date(2026, 4, 19),
        },
    },
    {
        "name": "attendance",
        "create_schema": AttendanceCreateSchema,
        "filter_schema": AttendanceFilterSchema,
        "update_schema": AttendanceUpdateSchema,
        "delete_schema": AttendanceDeleteSchema,
        "read_schema": AttendanceReadSchema,
        "create_valid": {"student_id": 1, "lesson_id": 2, "is_visited": True},
        "create_invalid": {"student_id": 1, "lesson_id": None},
        "filter_valid": {"student_id": 1},
        "filter_invalid": {"unknown_field": "data"},
        "update_valid": {"is_visited": False},
        "update_invalid": {},
        "delete_valid": {"student_id": 1, "lesson_id": 2},
        "delete_invalid": {},
        "read_valid": {
            "id": 1,
            "created_at": datetime(2026, 4, 19, 10, 0, 0),
            "updated_at": datetime(2026, 4, 19, 10, 5, 0),
            "student_id": 1,
            "lesson_id": 2,
            "is_visited": True,
        },
    },
    {
        "name": "mark",
        "create_schema": MarkCreateSchema,
        "filter_schema": MarkFilterSchema,
        "update_schema": MarkUpdateSchema,
        "delete_schema": MarkDeleteSchema,
        "read_schema": MarkReadSchema,
        "create_valid": {"student_id": 1, "lesson_id": 2, "data": 5},
        "create_invalid": {"student_id": 1, "lesson_id": 2},
        "filter_valid": {"lesson_id": 2},
        "filter_invalid": {"unknown_field": "data"},
        "update_valid": {"data": 4},
        "update_invalid": {},
        "delete_valid": {"student_id": 1, "lesson_id": 2},
        "delete_invalid": {},
        "read_valid": {
            "id": 1,
            "created_at": datetime(2026, 4, 19, 10, 0, 0),
            "updated_at": datetime(2026, 4, 19, 10, 5, 0),
            "student_id": 1,
            "lesson_id": 2,
            "data": 5,
        },
    },
    {
        "name": "comment",
        "create_schema": CommentCreateSchema,
        "filter_schema": CommentFilterSchema,
        "update_schema": CommentUpdateSchema,
        "delete_schema": CommentDeleteSchema,
        "read_schema": CommentReadSchema,
        "create_valid": {"student_id": 1, "lesson_id": 2, "data": "Отличная работа"},
        "create_invalid": {"student_id": 1, "lesson_id": 2, "data": ""},
        "filter_valid": {"lesson_id": 2, "data": "Отличная работа"},
        "filter_invalid": {"data": ""},
        "update_valid": {"data": "Комментарий обновлен"},
        "update_invalid": {},
        "delete_valid": {"student_id": 1, "lesson_id": 2},
        "delete_invalid": {},
        "read_valid": {
            "id": 1,
            "created_at": datetime(2026, 4, 19, 10, 0, 0),
            "updated_at": datetime(2026, 4, 19, 10, 5, 0),
            "student_id": 1,
            "lesson_id": 2,
            "data": "Отличная работа",
        },
    },
]


@pytest.mark.parametrize("case", SCHEMA_CASES, ids=[case["name"] for case in SCHEMA_CASES])
def test_create_schema_validation_positive(case):
    """
    Схема создания принимает корректные данные.
    """
    schema = case["create_schema"].model_validate(case["create_valid"])

    for key, value in case["create_valid"].items():
        assert getattr(schema, key) == value


@pytest.mark.parametrize("case", SCHEMA_CASES, ids=[case["name"] for case in SCHEMA_CASES])
def test_create_schema_validation_negative(case):
    """
    Схема создания отклоняет некорректные данные.
    """
    with pytest.raises(ValidationError):
        case["create_schema"].model_validate(case["create_invalid"])


@pytest.mark.parametrize("case", SCHEMA_CASES, ids=[case["name"] for case in SCHEMA_CASES])
def test_filter_schema_validation(case):
    """
    Схема фильтра принимает корректные данные и отклоняет ошибочные.
    """
    schema = case["filter_schema"].model_validate(case["filter_valid"])
    for key, value in case["filter_valid"].items():
        assert getattr(schema, key) == value

    with pytest.raises(ValidationError):
        case["filter_schema"].model_validate(case["filter_invalid"])


@pytest.mark.parametrize("case", SCHEMA_CASES, ids=[case["name"] for case in SCHEMA_CASES])
def test_update_schema_validation(case):
    """
    Схема обновления требует непустой и корректный payload.
    """
    schema = case["update_schema"].model_validate(case["update_valid"])
    for key, value in case["update_valid"].items():
        assert getattr(schema, key) == value

    with pytest.raises(ValidationError):
        case["update_schema"].model_validate(case["update_invalid"])


@pytest.mark.parametrize("case", SCHEMA_CASES, ids=[case["name"] for case in SCHEMA_CASES])
def test_delete_schema_validation(case):
    """
    Схема удаления требует непустой и корректный фильтр.
    """
    schema = case["delete_schema"].model_validate(case["delete_valid"])
    for key, value in case["delete_valid"].items():
        assert getattr(schema, key) == value

    with pytest.raises(ValidationError):
        case["delete_schema"].model_validate(case["delete_invalid"])


@pytest.mark.parametrize("case", SCHEMA_CASES, ids=[case["name"] for case in SCHEMA_CASES])
def test_read_schema_validation(case):
    """
    Read-схема корректно валидирует данные чтения.
    """
    schema = case["read_schema"].model_validate(case["read_valid"])

    assert schema.id == case["read_valid"]["id"]
    assert schema.created_at == case["read_valid"]["created_at"]
    assert schema.updated_at == case["read_valid"]["updated_at"]


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("СМ1-21Б", True),
        ("ИУ7-31", True),
        ("AA1-11", False),
        ("не группа", False),
    ],
)
def test_is_group_name_formatted(value, expected):
    """
    Helper для формата названия группы работает корректно.
    """
    assert is_group_name_formatted(value) is expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("24.03.01_Информатика", True),
        ("09.03.02_Программирование", True),
        ("24.03.01", False),
        ("специальность", False),
    ],
)
def test_is_speciality_formatted(value, expected):
    """
    Helper для формата специальности работает корректно.
    """
    assert is_speciality_formatted(value) is expected
