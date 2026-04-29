"""
Тестирование сервисов с использованием pytest и PostgreSQL.
"""
# pylint: disable=redefined-outer-name, import-error
from datetime import date, time

from sqlalchemy.sql import Delete, Select
import pytest

from app.models import Attendance, Comment, Group, Lesson, Mark, Schedule, ScheduleGroupLink, Student
from app.services import (
    AttendanceService,
    CommentService,
    GroupService,
    LessonService,
    MarkService,
    ScheduleGroupLinkService,
    ScheduleService,
    StudentService,
)


SERVICE_CASES = [
    {
        "name": "group",
        "service_cls": GroupService,
        "model_cls": Group,
        "create_valid": {"name": "СМ1-21Б", "speciality": "24.03.01_Информатика"},
        "create_invalid": {"name": ""},
        "select_valid": {"name": "СМ1-21Б"},
        "select_invalid": {"unknown_field": "data"},
        "update_valid": {"id": 1, "speciality": "24.03.01_Обновление"},
        "update_invalid": {"id": 1},
        "delete_valid": {"name": "СМ1-21Б"},
        "delete_invalid": {"speciality": "24.03.01_Информатика"},
    },
    {
        "name": "student",
        "service_cls": StudentService,
        "model_cls": Student,
        "create_valid": {
            "group_id": 1,
            "surname": "Петров",
            "first_name": "Петр",
            "bmstu_email": "petrov@student.bmstu.ru",
        },
        "create_invalid": {"group_id": 1, "surname": "", "first_name": "Петр"},
        "select_valid": {"group_id": 1},
        "select_invalid": {"unknown_field": "data"},
        "update_valid": {"id": 1, "patronymic": "Петрович"},
        "update_invalid": {"id": 1},
        "delete_valid": {"group_id": 1},
        "delete_invalid": {"surname": "Петров"},
    },
    {
        "name": "schedule",
        "service_cls": ScheduleService,
        "model_cls": Schedule,
        "create_valid": {
            "odd_or_even": "even",
            "type": "семинар",
            "is_assessment": False,
            "day": "вт",
            "time": time(8, 45),
        },
        "create_invalid": {
            "odd_or_even": "even",
            "type": "семинар",
            "day": "вт",
        },
        "select_valid": {"day": "вт"},
        "select_invalid": {"unknown_field": "data"},
        "update_valid": {"id": 1, "is_assessment": True, "type": "лекция"},
        "update_invalid": {"is_assessment": True},
        "delete_valid": {"day": "вт"},
        "delete_invalid": {"is_assessment": False},
    },
    {
        "name": "schedule_group_link",
        "service_cls": ScheduleGroupLinkService,
        "model_cls": ScheduleGroupLink,
        "create_valid": {"group_id": 1, "schedule_id": 1},
        "create_invalid": {"group_id": 1},
        "select_valid": {"group_id": 1},
        "select_invalid": {"unknown_field": "data"},
        "update_valid": {"group_id": 1, "schedule_id": 2},
        "update_invalid": {},
        "delete_valid": {"group_id": 1},
        "delete_invalid": {},
    },
    {
        "name": "lesson",
        "service_cls": LessonService,
        "model_cls": Lesson,
        "create_valid": {"schedule_id": 1, "topic": "SQLAlchemy", "date": date(2026, 4, 19)},
        "create_invalid": {"schedule_id": 1, "topic": "SQLAlchemy"},
        "select_valid": {"schedule_id": 1},
        "select_invalid": {"unknown_field": "data"},
        "update_valid": {"schedule_id": 1, "date": date(2026, 4, 19), "topic": "Pydantic"},
        "update_invalid": {"schedule_id": 1, "date": date(2026, 4, 19)},
        "delete_valid": {"schedule_id": 1},
        "delete_invalid": {"date": date(2026, 4, 19)},
    },
    {
        "name": "attendance",
        "service_cls": AttendanceService,
        "model_cls": Attendance,
        "create_valid": {"student_id": 1, "lesson_id": 1, "is_visited": True},
        "create_invalid": {"student_id": 1, "is_visited": True},
        "select_valid": {},
        "select_invalid": {"student_id": None},
        "update_valid": {"student_id": 1, "lesson_id": 1, "is_visited": False},
        "update_invalid": {"student_id": 1, "lesson_id": 1},
        "delete_valid": {"id": 1},
        "delete_invalid": {"is_visited": None},
    },
    {
        "name": "mark",
        "service_cls": MarkService,
        "model_cls": Mark,
        "create_valid": {"student_id": 1, "lesson_id": 1, "data": 5},
        "create_invalid": {"student_id": 1, "lesson_id": 1},
        "select_valid": {},
        "select_invalid": {"data": None},
        "update_valid": {"student_id": 1, "lesson_id": 1, "data": 4},
        "update_invalid": {"student_id": 1, "lesson_id": 1},
        "delete_valid": {"id": 1},
        "delete_invalid": {"data": 5},
    },
    {
        "name": "comment",
        "service_cls": CommentService,
        "model_cls": Comment,
        "create_valid": {"student_id": 1, "lesson_id": 1, "data": "Отличная работа"},
        "create_invalid": {"student_id": 1, "lesson_id": 1, "data": ""},
        "select_valid": {},
        "select_invalid": {"data": None},
        "update_valid": {"student_id": 1, "lesson_id": 1, "data": "Комментарий обновлен"},
        "update_invalid": {"student_id": 1, "lesson_id": 1},
        "delete_valid": {"id": 1},
        "delete_invalid": {"data": "Отличная работа"},
    },
]


@pytest.mark.parametrize("case", SERVICE_CASES, ids=[case["name"] for case in SERVICE_CASES])
def test_service_create_validation_positive(case):
    """
    Сервис создает ORM-объект из словаря, схемы и уже созданной модели.
    """
    service = case["service_cls"]()
    model_cls = case["model_cls"]
    schema_instance = service.create_schema.model_validate(case["create_valid"])

    created_from_dict = service.create_instance(case["create_valid"])
    created_from_schema = service.create_instance(schema_instance)
    created_from_model = service.create_instance(model_cls(**case["create_valid"]))

    assert type(created_from_dict) is model_cls
    assert type(created_from_schema) is model_cls
    assert type(created_from_model) is model_cls


@pytest.mark.parametrize("case", SERVICE_CASES, ids=[case["name"] for case in SERVICE_CASES])
def test_service_create_validation_negative(case):
    """
    Сервис возвращает None для некорректных данных создания.
    """
    service = case["service_cls"]()

    assert service.create_instance(case["create_invalid"]) is None


@pytest.mark.parametrize("case", SERVICE_CASES, ids=[case["name"] for case in SERVICE_CASES])
def test_service_select_validation(case):
    """
    Сервис строит Select для корректных данных и отклоняет некорректные.
    """
    service = case["service_cls"]()

    assert type(service.build_select(case["select_valid"])) is Select
    assert service.build_select(case["select_invalid"]) is None


@pytest.mark.parametrize("case", SERVICE_CASES, ids=[case["name"] for case in SERVICE_CASES])
def test_service_update_validation(case):
    """
    Сервис применяет обновление к ORM-объекту и отклоняет пустой payload.
    """
    service = case["service_cls"]()
    model_obj = case["model_cls"](**case["create_valid"])

    if case["name"] == "schedule_group_link":
        assert service.apply_update(model_obj, case["update_valid"]) is None
        assert service.apply_update(model_obj, case["update_invalid"]) is None
        return

    updated_obj = service.apply_update(model_obj, case["update_valid"])

    assert updated_obj is model_obj
    for key, value in case["update_valid"].items():
        if key in service.update_lookup_fields:
            continue

        assert getattr(updated_obj, key) == value

    assert (
        service.apply_update(
            case["model_cls"](**case["create_valid"]),
            case["update_valid"],
        )
        is not None
    )
    assert service.apply_update(model_obj, case["update_invalid"]) is None


@pytest.mark.parametrize("case", SERVICE_CASES, ids=[case["name"] for case in SERVICE_CASES])
def test_service_delete_validation(case):
    """
    Сервис строит Delete для корректных данных и отклоняет пустой фильтр.
    """
    service = case["service_cls"]()

    assert type(service.build_delete(case["delete_valid"])) is Delete
    assert service.build_delete(case["delete_invalid"]) is None


def test_services_db_flow(db_session):
    """
    Проверка полного цикла работы сервисов на связанной цепочке сущностей.
    """
    group_service = GroupService()
    student_service = StudentService()
    schedule_service = ScheduleService()
    link_service = ScheduleGroupLinkService()
    lesson_service = LessonService()
    attendance_service = AttendanceService()
    mark_service = MarkService()
    comment_service = CommentService()

    group = group_service.create_instance(
        {"name": "ИУ7-31", "speciality": "09.03.01_Информатика"}
    )
    schedule = schedule_service.create_instance(
        {
            "odd_or_even": "odd",
            "type": "семинар",
            "is_assessment": False,
            "day": "пн",
            "time": time(10, 15),
        }
    )

    db_session.add_all([group, schedule])
    db_session.flush()

    student = student_service.create_instance(
        {
            "group_id": group.id,
            "surname": "Иванов",
            "first_name": "Иван",
            "bmstu_email": "ivanov@student.bmstu.ru",
        }
    )
    link = link_service.create_instance(
        {"group_id": group.id, "schedule_id": schedule.id}
    )

    db_session.add_all([student, link])
    db_session.flush()

    lesson = lesson_service.create_instance(
        {
            "schedule_id": schedule.id,
            "topic": "SQLAlchemy ORM",
            "date": date(2026, 4, 19),
        }
    )
    db_session.add(lesson)
    db_session.flush()

    attendance = attendance_service.create_instance(
        {"student_id": student.id, "lesson_id": lesson.id, "is_visited": True}
    )
    mark = mark_service.create_instance(
        {"student_id": student.id, "lesson_id": lesson.id, "data": 5}
    )
    comment = comment_service.create_instance(
        {
            "student_id": student.id,
            "lesson_id": lesson.id,
            "data": "Отличный ответ",
        }
    )

    db_session.add_all([attendance, mark, comment])
    db_session.flush()

    db_group = db_session.scalar(group_service.build_select({"name": "ИУ7-31"}))
    db_student = db_session.scalar(student_service.build_select({"surname": "Иванов"}))
    db_schedule = db_session.scalar(schedule_service.build_select({"day": "пн"}))
    db_link = db_session.scalar(link_service.build_select({"group_id": group.id}))
    db_lesson = db_session.scalar(lesson_service.build_select({"topic": "SQLAlchemy ORM"}))
    db_attendance = db_session.scalar(
        attendance_service.build_select(
            {"student_id": student.id, "lesson_id": lesson.id, "is_visited": True}
        )
    )
    db_mark = db_session.scalar(
        mark_service.build_select(
            {"student_id": student.id, "lesson_id": lesson.id, "data": 5}
        )
    )
    db_comment = db_session.scalar(
        comment_service.build_select(
            {"student_id": student.id, "lesson_id": lesson.id, "data": "Отличный ответ"}
        )
    )

    assert db_group.id == group.id
    assert db_student.group_id == group.id
    assert db_schedule.id == schedule.id
    assert db_link.schedule_id == schedule.id
    assert db_lesson.schedule_id == schedule.id
    assert db_attendance.lesson_id == lesson.id
    assert db_mark.data == 5
    assert db_comment.data == "Отличный ответ"

    updated_student = student_service.apply_update(
        db_student,
        {"id": db_student.id, "patronymic": "Иванович"},
    )
    assert updated_student.patronymic == "Иванович"

    delete_stmt = comment_service.build_delete(
        {"student_id": student.id, "lesson_id": lesson.id, "data": "Отличный ответ"}
    )
    db_session.execute(delete_stmt)
    db_session.flush()

    deleted_comment = db_session.scalar(
        comment_service.build_select(
            {"student_id": student.id, "lesson_id": lesson.id, "data": "Отличный ответ"}
        )
    )
    assert deleted_comment is None
