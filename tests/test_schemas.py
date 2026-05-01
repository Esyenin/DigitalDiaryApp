"""
Тестирование Pydantic-схем проекта.
"""
# pylint: disable=import-error
from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Any

import pytest
from pydantic import BaseModel, ValidationError

from app.models.comment import Comment
from app.models.group import MAX_LEN as GROUP_MAX_LEN, Group
from app.models.student import Student
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

GROUP_LENGTH_CASES = {
    "max_name": "С" * GROUP_MAX_LEN["name"],
    "too_long_name": "С" * (GROUP_MAX_LEN["name"] + 1),
    "max_speciality": "С" * GROUP_MAX_LEN["speciality"],
    "too_long_speciality": "С" * (GROUP_MAX_LEN["speciality"] + 1),
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
                {
                    "group_id": 1,
                    "surname": "Петров",
                    "first_name": "Петр",
                    "patronymic": "Петрович",
                },
            ),
            invalid=(
                {"group_id": 1, "surname": "", "first_name": "Петр"},
            ),
        ),
        filter=PayloadSet(
            valid=(
                {"group_id": 1, "surname": "Петров"},
                {"created_at": BASE_READ_FIELDS["created_at"]},
                {"updated_at": BASE_READ_FIELDS["updated_at"]},
            ),
            invalid=(
                {"surname": ""},
            ),
        ),
        update=PayloadSet(
            valid=(
                {"first_name": "Алексей"},
            ),
            invalid=(
                {},
                {"id": 1},
            ),
        ),
        delete=PayloadSet(
            valid=(
                {"id": 1},
                {"group_id": 1},
                {"created_at": BASE_READ_FIELDS["created_at"]},
                {"updated_at": BASE_READ_FIELDS["updated_at"]},
                {"surname": "Петров"},
            ),
            invalid=(
                {},
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
                {
                    "odd_or_even": "even",
                    "type": "семинар",
                    "is_assessment": False,
                    "day": "вт",
                    "time": time(8, 45),
                },
            ),
            invalid=(
                {"odd_or_even": "even", "type": "семинар", "day": "вт"},
            ),
        ),
        filter=PayloadSet(
            valid=(
                {"day": "вт"},
                {"created_at": BASE_READ_FIELDS["created_at"]},
                {"updated_at": BASE_READ_FIELDS["updated_at"]},
            ),
            invalid=(
                {"type": ""},
            ),
        ),
        update=PayloadSet(
            valid=(
                {"is_assessment": True},
            ),
            invalid=(
                {},
                {"id": 1},
            ),
        ),
        delete=PayloadSet(
            valid=(
                {"day": "вт"},
                {"created_at": BASE_READ_FIELDS["created_at"]},
                {"updated_at": BASE_READ_FIELDS["updated_at"]},
                {"is_assessment": False},
            ),
            invalid=(),
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
                {"group_id": 1, "schedule_id": 2},
            ),
            invalid=(
                {"group_id": 1},
            ),
        ),
        filter=PayloadSet(
            valid=(
                {},
                {"group_id": 1},
                {"created_at": BASE_READ_FIELDS["created_at"]},
                {"updated_at": BASE_READ_FIELDS["updated_at"]},
            ),
            invalid=(
                {"unknown_field": "data"},
            ),
        ),
        update=PayloadSet(
            valid=(),
            invalid=(
                {"group_id": 1, "schedule_id": 2},
                {"schedule_id": 5},
                {"group_id": 1, "schedule_id": None},
            ),
        ),
        delete=PayloadSet(
            valid=(
                {"group_id": 1},
                {"schedule_id": 2},
                {"created_at": BASE_READ_FIELDS["created_at"]},
                {"updated_at": BASE_READ_FIELDS["updated_at"]},
                {"group_id": 1, "schedule_id": None},
            ),
            invalid=(
                {},
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
                {"schedule_id": 1, "topic": "SQLAlchemy", "date": date(2026, 4, 19)},
                {"schedule_id": 1, "date": date(2026, 4, 19)},
            ),
            invalid=(
                {"schedule_id": 1, "topic": "SQLAlchemy"},
            ),
        ),
        filter=PayloadSet(
            valid=(
                {},
                {"schedule_id": 1, "topic": "SQLAlchemy"},
                {"created_at": BASE_READ_FIELDS["created_at"]},
                {"updated_at": BASE_READ_FIELDS["updated_at"]},
            ),
            invalid=(
                {"topic": ""},
            ),
        ),
        update=PayloadSet(
            valid=(
                {"schedule_id": 1, "date": date(2026, 4, 19), "topic": "Pydantic"},
                {"topic": None},
            ),
            invalid=(
                {},
                {"id": 1},
            ),
        ),
        delete=PayloadSet(
            valid=(
                {"id": 1},
                {"schedule_id": 1},
                {"created_at": BASE_READ_FIELDS["created_at"]},
                {"updated_at": BASE_READ_FIELDS["updated_at"]},
                {"date": date(2026, 4, 19)},
            ),
            invalid=(
                {},
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
                {"student_id": 1, "lesson_id": 2, "is_visited": True},
                {"student_id": 1, "lesson_id": 2},
            ),
            invalid=(
                {"student_id": 1, "is_visited": True},
            ),
        ),
        filter=PayloadSet(
            valid=(
                {},
                {"student_id": 1},
                {"created_at": BASE_READ_FIELDS["created_at"]},
                {"updated_at": BASE_READ_FIELDS["updated_at"]},
                {"student_id": None},
            ),
            invalid=(),
        ),
        update=PayloadSet(
            valid=(
                {"is_visited": False},
                {"is_visited": True},
            ),
            invalid=(
                {},
                {"id": 1},
            ),
        ),
        delete=PayloadSet(
            valid=(
                {"id": 1},
                {"student_id": 1, "lesson_id": 2},
                {"created_at": BASE_READ_FIELDS["created_at"]},
                {"updated_at": BASE_READ_FIELDS["updated_at"]},
                {"is_visited": None},
                {"is_visited": False},
            ),
            invalid=(
                {},
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
                {"student_id": 1, "lesson_id": 2, "data": 5},
            ),
            invalid=(
                {"student_id": 1, "lesson_id": 2},
            ),
        ),
        filter=PayloadSet(
            valid=(
                {},
                {"lesson_id": 2},
                {"created_at": BASE_READ_FIELDS["created_at"]},
                {"updated_at": BASE_READ_FIELDS["updated_at"]},
                {"data": None},
            ),
            invalid=(),
        ),
        update=PayloadSet(
            valid=(
                {"data": 4},
                {"data": 5},
            ),
            invalid=(
                {},
                {"id": 1},
            ),
        ),
        delete=PayloadSet(
            valid=(
                {"id": 1},
                {"student_id": 1, "lesson_id": 2},
                {"created_at": BASE_READ_FIELDS["created_at"]},
                {"updated_at": BASE_READ_FIELDS["updated_at"]},
                {"data": 5},
            ),
            invalid=(
                {},
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
                {"student_id": 1, "lesson_id": 2, "data": "Отличная работа"},
                {"student_id": 1, "lesson_id": 2},
            ),
            invalid=(
                {"student_id": 1, "lesson_id": 2, "data": ""},
            ),
        ),
        filter=PayloadSet(
            valid=(
                {},
                {"lesson_id": 2, "data": "Отличная работа"},
                {"created_at": BASE_READ_FIELDS["created_at"]},
                {"updated_at": BASE_READ_FIELDS["updated_at"]},
                {"data": None},
            ),
            invalid=(),
        ),
        update=PayloadSet(
            valid=(
                {"data": "Комментарий обновлен"},
                {"data": None},
            ),
            invalid=(
                {},
                {"id": 1},
            ),
        ),
        delete=PayloadSet(
            valid=(
                {"id": 1},
                {"student_id": 1},
                {"lesson_id": 2},
                {"created_at": BASE_READ_FIELDS["created_at"]},
                {"updated_at": BASE_READ_FIELDS["updated_at"]},
                {"data": "Отличная работа"},
            ),
            invalid=(
                {},
                {"student_id": 1, "data": ""},
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
        if not key.startswith("_") and value is not None
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
        (StudentFilterSchema, {"id": 1, "created_at": BASE_READ_FIELDS["created_at"], "updated_at": BASE_READ_FIELDS["updated_at"]}),
        (ScheduleFilterSchema, {"id": 1, "created_at": BASE_READ_FIELDS["created_at"], "updated_at": BASE_READ_FIELDS["updated_at"]}),
        (ScheduleGroupLinkFilterSchema, {"id": 1, "created_at": BASE_READ_FIELDS["created_at"], "updated_at": BASE_READ_FIELDS["updated_at"]}),
        (LessonFilterSchema, {"id": 1, "created_at": BASE_READ_FIELDS["created_at"], "updated_at": BASE_READ_FIELDS["updated_at"]}),
        (AttendanceFilterSchema, {"id": 1, "created_at": BASE_READ_FIELDS["created_at"], "updated_at": BASE_READ_FIELDS["updated_at"]}),
        (MarkFilterSchema, {"id": 1, "created_at": BASE_READ_FIELDS["created_at"], "updated_at": BASE_READ_FIELDS["updated_at"]}),
        (CommentFilterSchema, {"id": 1, "created_at": BASE_READ_FIELDS["created_at"], "updated_at": BASE_READ_FIELDS["updated_at"]}),
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
        (StudentDeleteSchema, {"id": 1, "created_at": BASE_READ_FIELDS["created_at"], "updated_at": BASE_READ_FIELDS["updated_at"]}),
        (ScheduleDeleteSchema, {"id": 1, "created_at": BASE_READ_FIELDS["created_at"], "updated_at": BASE_READ_FIELDS["updated_at"]}),
        (ScheduleGroupLinkDeleteSchema, {"id": 1, "created_at": BASE_READ_FIELDS["created_at"], "updated_at": BASE_READ_FIELDS["updated_at"]}),
        (LessonDeleteSchema, {"id": 1, "created_at": BASE_READ_FIELDS["created_at"], "updated_at": BASE_READ_FIELDS["updated_at"]}),
        (AttendanceDeleteSchema, {"id": 1, "created_at": BASE_READ_FIELDS["created_at"], "updated_at": BASE_READ_FIELDS["updated_at"]}),
        (MarkDeleteSchema, {"id": 1, "created_at": BASE_READ_FIELDS["created_at"], "updated_at": BASE_READ_FIELDS["updated_at"]}),
        (CommentDeleteSchema, {"id": 1, "created_at": BASE_READ_FIELDS["created_at"], "updated_at": BASE_READ_FIELDS["updated_at"]}),
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
