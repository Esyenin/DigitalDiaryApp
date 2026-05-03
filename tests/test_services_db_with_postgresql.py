"""
Тестирование сервисов с использованием pytest и PostgreSQL.
"""
# pylint: disable=redefined-outer-name, import-error
from datetime import date, time
import logging

from sqlalchemy.sql import Delete, Select
import pytest

from app.models import Attendance, Comment, Group, Lesson, Mark, Schedule, ScheduleGroupLink, Student
from app.services import (
    AttendanceService,
    CommentService,
    GroupService,
    LessonService,
    MarkService,
    OrmService,
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
        "update_valid": {"speciality": "24.03.01_Обновление"},
        "update_invalid": {},
        "delete_valid": {"name": "СМ1-21Б"},
        "delete_invalid": {},
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
        "update_valid": {"patronymic": "Петрович"},
        "update_invalid": {},
        "delete_valid": {"group_id": 1, "surname": "Петров"},
        "delete_invalid": {},
    },
    {
        "name": "schedule",
        "service_cls": ScheduleService,
        "model_cls": Schedule,
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
        "select_valid": {"day": "вт"},
        "select_invalid": {"unknown_field": "data"},
        "update_valid": {"is_assessment": True, "type": "лекция"},
        "update_invalid": {},
        "delete_valid": {"day": "вт"},
        "delete_invalid": {},
    },
    {
        "name": "schedule_group_link",
        "service_cls": ScheduleGroupLinkService,
        "model_cls": ScheduleGroupLink,
        "create_valid": {"group_id": 1, "schedule_id": 1},
        "create_invalid": {"group_id": 1},
        "select_valid": {"group_id": 1},
        "select_invalid": {"unknown_field": "data"},
        "update_valid": None,
        "update_invalid": {},
        "delete_valid": {"group_id": 1, "schedule_id": 1},
        "delete_invalid": {},
    },
    {
        "name": "lesson",
        "service_cls": LessonService,
        "model_cls": Lesson,
        "create_valid": {"schedule_id": 1, "topic": "SQLAlchemy", "date": date(2026, 4, 19)},
        "create_invalid": {"schedule_id": 1, "topic": "", "date": date(2026, 4, 19)},
        "select_valid": {"schedule_id": 1},
        "select_invalid": {"unknown_field": "data"},
        "update_valid": {"topic": "Pydantic"},
        "update_invalid": {},
        "delete_valid": {"schedule_id": 1},
        "delete_invalid": {},
    },
    {
        "name": "attendance",
        "service_cls": AttendanceService,
        "model_cls": Attendance,
        "create_valid": {"student_id": 1, "lesson_id": 1, "is_visited": True},
        "create_invalid": {"student_id": 1, "lesson_id": None},
        "select_valid": {"student_id": 1},
        "select_invalid": {"unknown_field": "data"},
        "update_valid": {"is_visited": False},
        "update_invalid": {},
        "delete_valid": {"student_id": 1, "lesson_id": 1},
        "delete_invalid": {},
    },
    {
        "name": "mark",
        "service_cls": MarkService,
        "model_cls": Mark,
        "create_valid": {"student_id": 1, "lesson_id": 1, "data": 5},
        "create_invalid": {"student_id": 1, "lesson_id": 1},
        "select_valid": {"student_id": 1},
        "select_invalid": {"unknown_field": "data"},
        "update_valid": {"data": 4},
        "update_invalid": {},
        "delete_valid": {"student_id": 1, "lesson_id": 1},
        "delete_invalid": {},
    },
    {
        "name": "comment",
        "service_cls": CommentService,
        "model_cls": Comment,
        "create_valid": {"student_id": 1, "lesson_id": 1, "data": "Отличная работа"},
        "create_invalid": {"student_id": 1, "lesson_id": 1, "data": ""},
        "select_valid": {"student_id": 1},
        "select_invalid": {"unknown_field": "data"},
        "update_valid": {"data": "Комментарий обновлен"},
        "update_invalid": {},
        "delete_valid": {"student_id": 1, "lesson_id": 1},
        "delete_invalid": {},
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
    created_from_model = service.create(model_cls(**case["create_valid"]))

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
    assert type(service.get(case["select_valid"])) is Select
    assert service.build_select(case["select_invalid"]) is None


@pytest.mark.parametrize("case", SERVICE_CASES, ids=[case["name"] for case in SERVICE_CASES])
def test_service_update_validation(case):
    """
    Сервис применяет обновление к ORM-объекту и отклоняет пустой payload.
    """
    service = case["service_cls"]()
    model_obj = case["model_cls"](**case["create_valid"])

    updated_obj = service.apply_update(model_obj, case["update_valid"])

    if case["update_valid"] is None:
        assert updated_obj is None
        assert service.update(
            case["model_cls"](**case["create_valid"]),
            case["update_invalid"],
        ) is None
        return

    assert updated_obj is model_obj
    for key, value in case["update_valid"].items():
        assert getattr(updated_obj, key) == value

    assert service.update(case["model_cls"](**case["create_valid"]), case["update_valid"]) is not None
    assert service.apply_update(model_obj, case["update_invalid"]) is None


@pytest.mark.parametrize("case", SERVICE_CASES, ids=[case["name"] for case in SERVICE_CASES])
def test_service_delete_validation(case):
    """
    Сервис строит Delete для корректных данных и отклоняет пустой фильтр.
    """
    service = case["service_cls"]()

    assert type(service.build_delete(case["delete_valid"])) is Delete
    assert type(service.delete(case["delete_valid"])) is Delete
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

    db_group = db_session.scalar(group_service.build_select({"id": group.id}))
    db_student = db_session.scalar(student_service.build_select({"id": student.id}))
    db_schedule = db_session.scalar(schedule_service.build_select({"id": schedule.id}))
    db_link = db_session.scalar(link_service.build_select({"id": link.id}))
    db_lesson = db_session.scalar(lesson_service.build_select({"id": lesson.id}))
    db_attendance = db_session.scalar(attendance_service.build_select({"id": attendance.id}))
    db_mark = db_session.scalar(mark_service.build_select({"id": mark.id}))
    db_comment = db_session.scalar(comment_service.build_select({"id": comment.id}))

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
        {"patronymic": "Иванович"},
    )
    assert updated_student.patronymic == "Иванович"

    delete_stmt = comment_service.build_delete(
        {"student_id": student.id, "lesson_id": lesson.id}
    )
    db_session.execute(delete_stmt)
    db_session.flush()

    deleted_comment = db_session.scalar(
        comment_service.build_select(
            {"student_id": student.id, "lesson_id": lesson.id}
        )
    )
    assert deleted_comment is None


def test_ormservice_resolves_services_and_logs_unknown(db_session, caplog):
    """
    OrmService находит конкретные сервисы по разным пользовательским ключам.
    """
    orm_service = OrmService(db_session)

    assert isinstance(orm_service.service("group"), GroupService)
    assert isinstance(orm_service.service("groups"), GroupService)
    assert isinstance(orm_service.service(Group), GroupService)
    assert isinstance(orm_service.service(Group(name="ИУ7-31")), GroupService)
    assert isinstance(
        orm_service.service("schedule_group_link"),
        ScheduleGroupLinkService,
    )

    with caplog.at_level(logging.ERROR):
        assert orm_service.service("unknown") is None

    assert "Unknown ORM service name" in caplog.text


def test_ormservice_crud_flow(db_session):
    """
    OrmService выполняет CRUD через конкретные сервисы и текущую сессию.
    """
    orm_service = OrmService(db_session)
    group = orm_service.create(
        "group",
        {"name": "РЛ6-41", "speciality": "09.03.01_Информатика"},
    )

    assert type(group) is Group
    assert group.id is not None

    db_group = orm_service.get_one(Group, {"name": "РЛ6-41"})
    assert db_group.id == group.id

    updated_group = orm_service.update_one(
        "groups",
        {"id": group.id},
        {"speciality": "09.03.01_Обновление"},
    )
    assert updated_group.speciality == "09.03.01_Обновление"

    groups = orm_service.get("group", {"speciality": "09.03.01_Обновление"})
    assert groups == [group]

    deleted_count = orm_service.delete("group", {"id": group.id})
    assert deleted_count == 1
    assert orm_service.get_one("group", {"id": group.id}) is None


def test_ormservice_rejects_invalid_payload_and_logs(db_session, caplog):
    """
    OrmService возвращает None и пишет лог при некорректных данных.
    """
    orm_service = OrmService(db_session)

    with caplog.at_level(logging.WARNING):
        assert orm_service.create("group", {"name": ""}) is None

    assert "Create payload rejected by GroupService" in caplog.text
