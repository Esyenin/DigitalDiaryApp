"""
Тесты ORM-фасада на SQLAlchemy-сессии, подключенной к PostgreSQL.

Файл проверяет, что `OrmService` умеет работать со всеми сервисами сущностей
через единый интерфейс, корректно определяет нужный сервис по входным данным
и выполняет создание, чтение, обновление и удаление записей.
"""
# pylint: disable=redefined-outer-name, import-error, protected-access
from datetime import date
from datetime import time
import logging

import pytest
from sqlalchemy.orm import sessionmaker

from app.models import (
    Attendance,
    Comment,
    Group,
    Lesson,
    Mark,
    Schedule,
    ScheduleGroupLink,
    Student,
)
from app.services import (
    AmbiguousServiceError,
    AttendanceService,
    CommentService,
    GroupService,
    LessonService,
    MarkService,
    OrmService,
    ScheduleGroupLinkService,
    ScheduleService,
    StudentService,
    UnknownServiceError,
)
from app.schemas.attendance import (
    AttendanceCreateSchema,
    AttendanceDeleteSchema,
    AttendanceFilterSchema,
    AttendanceUpdateSchema,
)
from app.schemas.comment import (
    CommentCreateSchema,
    CommentDeleteSchema,
    CommentFilterSchema,
    CommentUpdateSchema,
)
from app.schemas.group import (
    GroupCreateSchema,
    GroupDeleteSchema,
    GroupFilterSchema,
    GroupUpdateSchema,
)
from app.schemas.lesson import (
    LessonCreateSchema,
    LessonDeleteSchema,
    LessonFilterSchema,
    LessonUpdateSchema,
)
from app.schemas.mark import (
    MarkCreateSchema,
    MarkDeleteSchema,
    MarkFilterSchema,
    MarkUpdateSchema,
)
from app.schemas.schedule import (
    ScheduleCreateSchema,
    ScheduleDeleteSchema,
    ScheduleFilterSchema,
    ScheduleUpdateSchema,
)
from app.schemas.schedule_group_link import (
    ScheduleGroupLinkCreateSchema,
    ScheduleGroupLinkDeleteSchema,
    ScheduleGroupLinkFilterSchema,
    ScheduleGroupLinkUpdateSchema,
)
from app.schemas.student import (
    StudentCreateSchema,
    StudentDeleteSchema,
    StudentFilterSchema,
    StudentUpdateSchema,
)


def _seed_group(db_session):
    """
    Создает группу, необходимую для тестов связанных сущностей.

    :param db_session: SQLAlchemy-сессия тестовой базы данных.

    :return: ORM-объект `Group`, добавленный в сессию и получивший первичный ключ.
    """
    group = Group(
        name=f"IU7-{_next_seed_number(db_session)}",
        speciality="09.03.01_Informatics",
    )
    db_session.add(group)
    db_session.flush()
    return group


def _next_seed_number(db_session):
    """
    Возвращает следующий уникальный номер для тестовых данных.

    :param db_session: SQLAlchemy-сессия, в `info` которой хранится счетчик
        текущего теста.

    :return: Целое число, которое можно использовать в уникальных строковых полях.
    """
    next_number = db_session.info.get("ormservice_test_number", 30) + 1
    db_session.info["ormservice_test_number"] = next_number
    return next_number


def _seed_schedule(db_session):
    """
    Создает расписание для тестов зависимых сущностей.

    :param db_session: SQLAlchemy-сессия тестовой базы данных.

    :return: ORM-объект `Schedule`, добавленный в сессию и получивший первичный
        ключ.
    """
    schedule = Schedule(
        odd_or_even="odd",
        type="seminar",
        day="mon",
        time=time(10, 15),
    )
    db_session.add(schedule)
    db_session.flush()
    return schedule


def _seed_student(db_session):
    """
    Создает студента вместе с группой, к которой он относится.

    :param db_session: SQLAlchemy-сессия тестовой базы данных.

    :return: ORM-объект `Student`, добавленный в сессию и связанный с созданной
        группой.
    """
    group = _seed_group(db_session)
    student = Student(
        group_id=group.id,
        surname="Ivanov",
        first_name="Ivan",
        bmstu_email="ivanov@student.bmstu.ru",
    )
    db_session.add(student)
    db_session.flush()
    return student


def _seed_lesson(db_session):
    """
    Создает занятие вместе с расписанием, к которому оно относится.

    :param db_session: SQLAlchemy-сессия тестовой базы данных.

    :return: ORM-объект `Lesson`, добавленный в сессию и связанный с созданным
        расписанием.
    """
    schedule = _seed_schedule(db_session)
    lesson = Lesson(
        schedule_id=schedule.id,
        topic="SQLAlchemy ORM",
        date=date(2026, 4, 19),
    )
    db_session.add(lesson)
    db_session.flush()
    return lesson


def _seed_student_and_lesson(db_session):
    """
    Создает пару объектов для сущностей, зависящих от студента и занятия.

    :param db_session: SQLAlchemy-сессия тестовой базы данных.

    :return: Словарь с ORM-объектами `student` и `lesson`, которые уже добавлены
        в сессию и имеют первичные ключи.
    """
    return {
        "student": _seed_student(db_session),
        "lesson": _seed_lesson(db_session),
    }


def _empty_context(_db_session):
    """
    Возвращает пустой контекст для сущностей без внешних зависимостей.

    :param _db_session: SQLAlchemy-сессия. Параметр не используется, но сохраняет
        общий интерфейс функций подготовки контекста.

    :return: Пустой словарь контекста.
    """
    return {}


def _group_create_data(_context):
    """
    Формирует данные для создания группы.

    :param _context: Контекст зависимостей. Для группы не используется.

    :return: Словарь с полями, достаточными для создания `Group`.
    """
    return {"name": "IU7-42", "speciality": "09.03.01_Informatics"}


def _student_create_data(context):
    """
    Формирует данные для создания студента.

    :param context: Словарь зависимостей с объектом `group`.

    :return: Словарь с полями, достаточными для создания `Student`.
    """
    group = context["group"]
    return {
        "group_id": group.id,
        "surname": "Petrov",
        "first_name": "Petr",
        "bmstu_email": "petrov@student.bmstu.ru",
    }


def _schedule_create_data(_context):
    """
    Формирует данные для создания расписания.

    :param _context: Контекст зависимостей. Для расписания не используется.

    :return: Словарь с полями, достаточными для создания `Schedule`.
    """
    return {
        "odd_or_even": "even",
        "type": "lecture",
        "day": "tue",
        "time": time(8, 45),
    }


def _schedule_group_link_create_data(context):
    """
    Формирует данные для создания связи группы и расписания.

    :param context: Словарь зависимостей с объектами `group` и `schedule`.

    :return: Словарь с внешними ключами для создания `ScheduleGroupLink`.
    """
    return {
        "group_id": context["group"].id,
        "schedule_id": context["schedule"].id,
    }


def _lesson_create_data(context):
    """
    Формирует данные для создания занятия.

    :param context: Словарь зависимостей с объектом `schedule`.

    :return: Словарь с полями, достаточными для создания `Lesson`.
    """
    return {
        "schedule_id": context["schedule"].id,
        "topic": "Pydantic",
        "date": date(2026, 4, 20),
    }


def _student_lesson_create_data(context):
    """
    Формирует общие внешние ключи студента и занятия.

    :param context: Словарь зависимостей с объектами `student` и `lesson`.

    :return: Словарь с `student_id` и `lesson_id`.
    """
    return {
        "student_id": context["student"].id,
        "lesson_id": context["lesson"].id,
    }


def _attendance_create_data(context):
    """
    Формирует данные для создания посещаемости.

    :param context: Словарь зависимостей с объектами `student` и `lesson`.

    :return: Словарь с внешними ключами и значением посещения.
    """
    return _student_lesson_create_data(context) | {"is_visited": True}


def _mark_create_data(context):
    """
    Формирует данные для создания оценки.

    :param context: Словарь зависимостей с объектами `student` и `lesson`.

    :return: Словарь с внешними ключами и значением оценки.
    """
    return _student_lesson_create_data(context) | {"data": 5}


def _comment_create_data(context):
    """
    Формирует данные для создания комментария.

    :param context: Словарь зависимостей с объектами `student` и `lesson`.

    :return: Словарь с внешними ключами и текстом комментария.
    """
    return _student_lesson_create_data(context) | {"data": "Great work"}


def _context_with_group(db_session):
    """
    Создает контекст с группой.

    :param db_session: SQLAlchemy-сессия тестовой базы данных.

    :return: Словарь с объектом `group`.
    """
    return {"group": _seed_group(db_session)}


def _context_with_group_and_schedule(db_session):
    """
    Создает контекст с группой и расписанием.

    :param db_session: SQLAlchemy-сессия тестовой базы данных.

    :return: Словарь с объектами `group` и `schedule`.
    """
    return {
        "group": _seed_group(db_session),
        "schedule": _seed_schedule(db_session),
    }


def _context_with_schedule(db_session):
    """
    Создает контекст с расписанием.

    :param db_session: SQLAlchemy-сессия тестовой базы данных.

    :return: Словарь с объектом `schedule`.
    """
    return {"schedule": _seed_schedule(db_session)}


ORM_SERVICE_CASES = [
    {
        "name": "group",
        "model_cls": Group,
        "service_cls": GroupService,
        "create_schema": GroupCreateSchema,
        "filter_schema": GroupFilterSchema,
        "update_schema": GroupUpdateSchema,
        "delete_schema": GroupDeleteSchema,
        "prepare": _empty_context,
        "create_data": _group_create_data,
        "select_field": "name",
        "update_data": {"speciality": "09.03.02_Applied"},
        "expected_updates": {"speciality": "09.03.02_Applied"},
    },
    {
        "name": "student",
        "model_cls": Student,
        "service_cls": StudentService,
        "create_schema": StudentCreateSchema,
        "filter_schema": StudentFilterSchema,
        "update_schema": StudentUpdateSchema,
        "delete_schema": StudentDeleteSchema,
        "prepare": _context_with_group,
        "create_data": _student_create_data,
        "select_field": "surname",
        "update_data": {"patronymic": "Petrovich"},
        "expected_updates": {"patronymic": "Petrovich"},
    },
    {
        "name": "schedule",
        "model_cls": Schedule,
        "service_cls": ScheduleService,
        "create_schema": ScheduleCreateSchema,
        "filter_schema": ScheduleFilterSchema,
        "update_schema": ScheduleUpdateSchema,
        "delete_schema": ScheduleDeleteSchema,
        "prepare": _empty_context,
        "create_data": _schedule_create_data,
        "select_field": "day",
        "update_data": {"is_assessment": True, "type": "practice"},
        "expected_updates": {"is_assessment": True, "type": "practice"},
    },
    {
        "name": "schedule_group_link",
        "model_cls": ScheduleGroupLink,
        "service_cls": ScheduleGroupLinkService,
        "create_schema": ScheduleGroupLinkCreateSchema,
        "filter_schema": ScheduleGroupLinkFilterSchema,
        "update_schema": ScheduleGroupLinkUpdateSchema,
        "delete_schema": ScheduleGroupLinkDeleteSchema,
        "prepare": _context_with_group_and_schedule,
        "create_data": _schedule_group_link_create_data,
        "select_field": "group_id",
        "update_data": None,
        "expected_updates": None,
    },
    {
        "name": "lesson",
        "model_cls": Lesson,
        "service_cls": LessonService,
        "create_schema": LessonCreateSchema,
        "filter_schema": LessonFilterSchema,
        "update_schema": LessonUpdateSchema,
        "delete_schema": LessonDeleteSchema,
        "prepare": _context_with_schedule,
        "create_data": _lesson_create_data,
        "select_field": "topic",
        "update_data": {"topic": "SQLAlchemy"},
        "expected_updates": {"topic": "SQLAlchemy"},
    },
    {
        "name": "attendance",
        "model_cls": Attendance,
        "service_cls": AttendanceService,
        "create_schema": AttendanceCreateSchema,
        "filter_schema": AttendanceFilterSchema,
        "update_schema": AttendanceUpdateSchema,
        "delete_schema": AttendanceDeleteSchema,
        "prepare": _seed_student_and_lesson,
        "create_data": _attendance_create_data,
        "select_field": "student_id",
        "update_data": {"is_visited": False},
        "expected_updates": {"is_visited": False},
    },
    {
        "name": "mark",
        "model_cls": Mark,
        "service_cls": MarkService,
        "create_schema": MarkCreateSchema,
        "filter_schema": MarkFilterSchema,
        "update_schema": MarkUpdateSchema,
        "delete_schema": MarkDeleteSchema,
        "prepare": _seed_student_and_lesson,
        "create_data": _mark_create_data,
        "select_field": "student_id",
        "update_data": {"data": 4},
        "expected_updates": {"data": 4},
    },
    {
        "name": "comment",
        "model_cls": Comment,
        "service_cls": CommentService,
        "create_schema": CommentCreateSchema,
        "filter_schema": CommentFilterSchema,
        "update_schema": CommentUpdateSchema,
        "delete_schema": CommentDeleteSchema,
        "prepare": _seed_student_and_lesson,
        "create_data": _comment_create_data,
        "select_field": "student_id",
        "update_data": {"data": "Updated comment"},
        "expected_updates": {"data": "Updated comment"},
    },
]


def _case_ids():
    """
    Собирает человекочитаемые имена параметризованных тестов.

    :return: Список строковых идентификаторов, по одному на каждый тестовый кейс.
    """
    return [case["name"] for case in ORM_SERVICE_CASES]


def _prepared_case_data(db_session, case):
    """
    Подготавливает данные создания для конкретного тестового кейса.

    :param db_session: SQLAlchemy-сессия тестовой базы данных.
    :param case: Описание сущности из `ORM_SERVICE_CASES`.

    :return: Словарь данных, который можно передать в create-операцию фасада.
    """
    context = case["prepare"](db_session)
    return case["create_data"](context)


def _copy_with_variant(data, variant):
    """
    Создает измененную копию тестового payload.

    :param data: Исходный словарь данных создания.
    :param variant: Номер варианта, который используется для уникализации
        значений в полях с ограничениями уникальности.

    :return: Новый словарь с теми же полями, но с безопасно измененными значениями
        в уникальных или часто повторяющихся полях.
    """
    copied = dict(data)

    if "name" in copied:
        copied["name"] = f"IU7-{40 + variant}"
    if "day" in copied:
        copied["day"] = f"d{variant}"
    if "date" in copied:
        copied["date"] = date(2026, 4, 20 + variant)
    if "surname" in copied:
        copied["surname"] = f"Petrov{variant}"
    if "bmstu_email" in copied:
        copied["bmstu_email"] = f"petrov{variant}@student.bmstu.ru"
    if "data" in copied and isinstance(copied["data"], str):
        copied["data"] = f"{copied['data']} {variant}"

    return copied


def _assert_fields(obj, expected):
    """
    Проверяет, что ORM-объект содержит ожидаемые значения полей.

    :param obj: ORM-объект, поля которого нужно проверить.
    :param expected: Словарь ожидаемых значений в формате имя поля - значение.

    :return: `None`. Проверка выполняется через assert-выражения pytest.
    """
    for field_name, value in expected.items():
        assert getattr(obj, field_name) == value


@pytest.mark.parametrize("case", ORM_SERVICE_CASES, ids=_case_ids())
def test_ormservice_create_accepts_dict_schema_and_model(case, db_session):
    """
    Проверяет создание всех сущностей через разные типы payload.

    :param case: Описание сущности из параметризованного набора.
    :param db_session: SQLAlchemy-сессия тестовой базы данных.

    :return: `None`. Тест падает, если фасад не создает объект из словаря,
        Pydantic-схемы или ORM-объекта.
    """
    orm_service = OrmService(db_session, auto_commit=False)
    model_cls = case["model_cls"]
    create_schema = case["create_schema"]

    dict_data = _copy_with_variant(_prepared_case_data(db_session, case), 1)
    schema_data = _copy_with_variant(_prepared_case_data(db_session, case), 2)
    model_data = _copy_with_variant(_prepared_case_data(db_session, case), 3)

    created_from_dict = orm_service.create(dict_data)
    created_from_schema = orm_service.create(create_schema(**schema_data))
    created_from_model = orm_service.create(model_cls(**model_data))

    assert type(created_from_dict) is model_cls
    assert type(created_from_schema) is model_cls
    assert type(created_from_model) is model_cls
    assert created_from_dict.id is not None
    assert created_from_schema.id is not None
    assert created_from_model.id is not None


@pytest.mark.parametrize("case", ORM_SERVICE_CASES, ids=_case_ids())
def test_ormservice_get_update_delete_by_schema(case, db_session):
    """
    Проверяет чтение, обновление и удаление всех сущностей через схемы.

    :param case: Описание сущности из параметризованного набора.
    :param db_session: SQLAlchemy-сессия тестовой базы данных.

    :return: `None`. Тест падает, если фасад неверно определяет сервис по схеме,
        не находит созданный объект, неверно обновляет его или не удаляет.
    """
    orm_service = OrmService(db_session, auto_commit=False)
    create_data = _prepared_case_data(db_session, case)
    created = orm_service.create(case["create_schema"](**create_data))

    assert type(created) is case["model_cls"]

    filter_schema = case["filter_schema"]
    found = orm_service.get(filter_schema(id=created.id))
    assert found == [created]

    if case["update_data"] is None:
        update_result = orm_service.update(
            filter_schema(id=created.id),
            {},
        )
        assert update_result is None
    else:
        update_schema = case["update_schema"]
        updated = orm_service.update(
            filter_schema(id=created.id),
            update_schema(**case["update_data"]),
        )
        assert updated == [created]
        _assert_fields(created, case["expected_updates"])

    deleted_count = orm_service.delete(case["delete_schema"](id=created.id))
    assert deleted_count == 1
    assert orm_service.get(filter_schema(id=created.id)) == []


@pytest.mark.parametrize("case", ORM_SERVICE_CASES, ids=_case_ids())
def test_ormservice_delete_accepts_transient_model_filter(case, db_session):
    """
    Проверяет удаление через ORM-объект, используемый как фильтр.

    :param case: Описание сущности из параметризованного набора.
    :param db_session: SQLAlchemy-сессия тестовой базы данных.

    :return: `None`. Тест падает, если фасад не может удалить запись по объекту,
        который содержит только фильтрующие поля.
    """
    orm_service = OrmService(db_session, auto_commit=False)
    create_data = _prepared_case_data(db_session, case)
    created = orm_service.create(create_data)

    delete_filter = case["model_cls"](id=created.id)

    assert orm_service.delete(delete_filter) == 1
    assert orm_service.get(case["filter_schema"](id=created.id)) == []


@pytest.mark.parametrize("case", ORM_SERVICE_CASES, ids=_case_ids())
def test_ormservice_rejects_invalid_create_payloads(case, db_session):
    """
    Проверяет отказ фасада при невалидных данных создания.

    :param case: Описание сущности из параметризованного набора.
    :param db_session: SQLAlchemy-сессия тестовой базы данных.

    :return: `None`. Тест падает, если фасад создает объект, который не проходит
        схему создания соответствующего сервиса.
    """
    orm_service = OrmService(db_session, auto_commit=False)
    invalid_data = _prepared_case_data(db_session, case)
    invalid_data.pop(next(iter(invalid_data)))

    assert orm_service.create(case["model_cls"](**invalid_data)) is None


def test_ormservice_discovers_entity_services(db_session):
    """
    Проверяет автоматическое обнаружение сервисов сущностей.

    :param db_session: SQLAlchemy-сессия тестовой базы данных.

    :return: `None`. Тест падает, если фасад не зарегистрировал сервисы по моделям
        и схемам без ручного публичного списка.
    """
    orm_service = OrmService(db_session, auto_commit=False)

    assert isinstance(orm_service._services_by_model[Group], GroupService)
    assert isinstance(
        orm_service._services_by_model[ScheduleGroupLink],
        ScheduleGroupLinkService,
    )
    assert isinstance(
        orm_service._services_by_schema[ScheduleCreateSchema],
        ScheduleService,
    )


def test_ormservice_new_crud_flow(db_session):
    """
    Проверяет полный CRUD-сценарий через автоматическое определение сервиса.

    :param db_session: SQLAlchemy-сессия тестовой базы данных.

    :return: `None`. Тест падает, если создание, чтение, обновление или удаление
        расписания через единый фасад работает некорректно.
    """
    orm_service = OrmService(db_session, auto_commit=False)
    schedule = orm_service.create(
        {
            "odd_or_even": "even",
            "type": "seminar",
            "day": "mon",
            "time": time(8, 45),
        }
    )

    assert type(schedule) is Schedule
    assert schedule.id is not None

    db_schedule = orm_service.get(Schedule(day="mon"))[0]
    assert db_schedule.id == schedule.id

    updated_schedule = orm_service.update(
        {"id": schedule.id},
        {"type": "lecture"},
    )[0]
    assert updated_schedule.type == "lecture"

    schedules = orm_service.get({"type": "lecture"})
    assert schedules == [schedule]

    deleted_count = orm_service.delete(Schedule(id=schedule.id))
    assert deleted_count == 1
    assert orm_service.get(Schedule(id=schedule.id)) == []


def test_ormservice_resolves_payload_by_schema(db_session):
    """
    Проверяет определение сервиса по Pydantic-схемам.

    :param db_session: SQLAlchemy-сессия тестовой базы данных.

    :return: `None`. Тест падает, если фасад не может использовать класс схемы
        как точный признак нужной сущности.
    """
    orm_service = OrmService(db_session, auto_commit=False)
    schedule = orm_service.create(
        ScheduleCreateSchema(
            odd_or_even="even",
            type="seminar",
            day="mon",
            time=time(8, 45),
        )
    )

    assert type(schedule) is Schedule
    assert schedule.id is not None

    schedules = orm_service.get(ScheduleFilterSchema(id=schedule.id))
    assert schedules == [schedule]

    updated = orm_service.update(
        ScheduleFilterSchema(id=schedule.id),
        ScheduleUpdateSchema(type="lecture"),
    )
    assert updated == [schedule]
    assert schedule.type == "lecture"

    deleted_count = orm_service.delete(ScheduleDeleteSchema(id=schedule.id))
    assert deleted_count == 1
    assert orm_service.get(ScheduleFilterSchema(id=schedule.id)) == []


def test_ormservice_works_with_direct_orm_object(db_session):
    """
    Проверяет работу фасада с прямой передачей ORM-объекта.

    :param db_session: SQLAlchemy-сессия тестовой базы данных.

    :return: `None`. Тест падает, если фасад не определяет сервис по классу
        ORM-объекта или неверно применяет create, update и delete.
    """
    orm_service = OrmService(db_session, auto_commit=False)
    schedule = Schedule(
        odd_or_even="odd",
        type="seminar",
        day="wed",
        time=time(10, 15),
    )

    created = orm_service.create(schedule)
    assert created is schedule
    assert schedule.id is not None

    updated = orm_service.update(schedule, {"type": "practice"})
    assert updated == [schedule]
    assert schedule.type == "practice"

    deleted_count = orm_service.delete(schedule)
    assert deleted_count == 1


def test_ormservice_supports_session_factory_context_manager(db_session):
    """
    Проверяет работу фасада с фабрикой сессий и context manager.

    :param db_session: SQLAlchemy-сессия тестовой базы данных, чей bind
        используется для создания новой сессии через фабрику.

    :return: `None`. Тест падает, если фасад не может сам создать сессию или
        корректно работать внутри блока `with`.
    """
    factory = sessionmaker(bind=db_session.get_bind())

    with OrmService(
        session_factory=factory,
        auto_commit=False,
        close_on_exit=True,
    ) as orm_service:
        schedule = orm_service.create(
            ScheduleCreateSchema(
                odd_or_even="even",
                type="seminar",
                day="thu",
                time=time(14, 0),
            )
        )

        assert type(schedule) is Schedule
        assert schedule.id is not None


def test_ormservice_raises_for_unknown_and_ambiguous_payloads(db_session):
    """
    Проверяет ошибки для неизвестных и неоднозначных словарей.

    :param db_session: SQLAlchemy-сессия тестовой базы данных.

    :return: `None`. Тест падает, если фасад не отличает payload без подходящего
        сервиса от payload, который подходит нескольким сервисам сразу.
    """
    orm_service = OrmService(db_session, auto_commit=False)

    with pytest.raises(UnknownServiceError):
        orm_service.create({"unknown_field": "data"})

    with pytest.raises(AmbiguousServiceError):
        orm_service.get({"id": 1})


def test_ormservice_rejects_invalid_known_payload_and_logs(
    db_session,
    caplog,
):
    """
    Проверяет отказ и логирование при невалидном payload известной модели.

    :param db_session: SQLAlchemy-сессия тестовой базы данных.
    :param caplog: Pytest-фикстура для проверки записей логирования.

    :return: `None`. Тест падает, если фасад не возвращает `None` при отклонении
        данных или не пишет диагностическое сообщение в лог.
    """
    orm_service = OrmService(db_session, auto_commit=False)
    invalid_schedule = Schedule(
        odd_or_even="",
        type="seminar",
        day="fri",
        time=time(12, 0),
    )

    with caplog.at_level(logging.WARNING):
        assert orm_service.create(invalid_schedule) is None

    assert "Create rejected" in caplog.text
