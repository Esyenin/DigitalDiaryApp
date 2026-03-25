"""
Тестирование базы данных PostgreSQL с использованием pytest.
Проверяет создание таблиц, корректность связей и работу с сессиями.
"""
# pylint: disable=redefined-outer-name, import-error
from datetime import datetime, time
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import pytest

# Импорты моделей и настроек проекта
from database import Base, Group, Student, ScheduleGroupLink, Schedule, Lesson, Attendance, Mark, Comment
from config import settings

# Глобальный URL для подключения к тестовой БД
DB_URL = settings.get_db_url()


@pytest.fixture(scope="session")
def engine():
    """Создает движок SQLAlchemy для всей тестовой сессии."""

    # Создание движка и генерация таблиц
    engine = create_engine(DB_URL)
    Base.metadata.create_all(bind=engine)
    # Возврат функцией значения
    yield engine


@pytest.fixture(scope="function")
def db_session(engine):
    """
    Создает изолированную сессию для каждого отдельного теста.
    Использует транзакцию с откатом (rollback), чтобы база оставалась чистой.
    """

    # Подключение к базе данных
    connection = engine.connect()
    # Открытие транзакции
    transaction = connection.begin()

    # Открытие конкретной сессии
    session = sessionmaker(bind=connection)()

    # Возврат функцией значения
    yield session

    # Закрытие сессии
    session.close()
    # Откат транзакций
    transaction.rollback()
    # Закрытие подключения
    connection.close()


# --- ТЕСТЫ ---

def test_postgresql_connection(db_session):
    """Проверка физической записи и генерации ID в Postgres."""

    # Подготовка данных
    group = Group(name="СМ1-11Б")
    db_session.add(group)
    db_session.flush()

    # Проверка
    assert group.id is not None
    assert group.name is not None
    assert db_session.query(Group).count() == 1

    # Вывод
    print(" Соединение с базой данных успешно установлено")


def test_create_group(db_session):
    """Проверка создания группы"""

    # Подготовка данных
    my_group = Group(
        name="СМ1-21Б",
        speciality="24.03.01"
    )
    db_session.add(my_group)
    db_session.flush()

    # Получение данных из базы данных
    db_group = db_session.get(Group, my_group.id)

    # Проверка
    assert db_group is not None
    assert db_group.id is not None
    assert db_group.name == "СМ1-21Б"
    assert db_group.speciality == "24.03.01"

    # Вывод
    print(f" Удалось успешно создать группу:\n\t{db_group}")


def test_create_student(db_session):
    """Проверка базового создания группы и привязки студента."""

    # Подготовка данных
    my_group = Group(
        name="СМ1-21Б",
        speciality="24.03.01"
    )
    db_session.add(my_group)
    db_session.flush()

    my_student1 = Student(
        group_id=my_group.id,
        surname="Попов",
        first_name="Андрей",
    )

    my_student2 = Student(
        group_id=my_group.id,
        surname="Иванов",
        first_name="Иван",
        patronymic="Иванович",
        personal_data="00М000",
        bmstu_email="ivamov@gmail.com"
    )

    db_session.add(my_student1)
    db_session.add(my_student2)
    db_session.flush()

    # Получение данных из базы данных
    db_group = db_session.get(Group, my_group.id)
    db_student1 = db_session.get(Student, my_student1.id)
    db_student2 = db_session.get(Student, my_student2.id)

    # Проверка
    assert db_student1 is not None
    assert db_student1.id is not None
    assert db_student1.group_id == my_group.id
    assert db_student1.surname == my_student1.surname
    assert db_student1.first_name == my_student1.first_name
    assert not db_student1.patronymic
    assert not db_student1.personal_data
    assert not db_student1.bmstu_email

    assert db_student2 is not None
    assert db_student2.id is not None
    assert db_student2.group_id == my_group.id
    assert db_student2.surname == my_student2.surname
    assert db_student2.first_name == my_student2.first_name
    assert db_student2.patronymic == my_student2.patronymic
    assert db_student2.personal_data == my_student2.personal_data
    assert db_student2.bmstu_email == my_student2.bmstu_email

    # Вывод
    print(f" Удалось успешно создать группу, добавить 2-ух студентов:\n\t{db_group}\n\t{db_student1}\n\t{db_student2}")


def test_create_schedule(db_session):
    """Проверка базового создания расписания."""

    # Подготовка данных
    my_schedule = Schedule(
        odd_or_even="odd",
        day="пн",
        time=time(
            hour=10,
            minute=30
        )
    )

    db_session.add(my_schedule)
    db_session.flush()

    # Получение данных из базы данных
    db_schedule = db_session.get(Schedule, my_schedule.id)

    # Проверка
    assert db_schedule is not None
    assert db_schedule.id == my_schedule.id
    assert db_schedule.odd_or_even == my_schedule.odd_or_even
    assert db_schedule.day == my_schedule.day
    assert db_schedule.time == my_schedule.time

    # Вывод
    print(f" Удалось успешно создать расписание:\n\t{db_schedule}")


def test_create_schedule_group_link(db_session):
    """Проверка связи между Группой и Расписанием."""

    # Подготовка данных
    my_group = Group(name="МТ10-11")
    my_schedule = Schedule(
        odd_or_even="even",
        day="вт",
        time=time(
            hour=12,
            minute=0
        )
    )

    db_session.add_all([my_group, my_schedule])
    db_session.flush()

    link = ScheduleGroupLink(
        group_id=my_group.id,
        schedule_id=my_schedule.id
    )

    db_session.add(link)
    db_session.flush()

    # Получение данных из базы данных
    db_link = db_session.get(ScheduleGroupLink, link.id)

    # Проверка
    assert db_link is not None
    assert db_link.id is not None
    assert db_link.schedule_id == my_schedule.id
    assert db_link.group_id == my_group.id
    assert db_link.group.name == my_group.name
    assert db_link.schedule.day == my_schedule.day

    # Вывод
    print(f" Успешная связь Группы и Расписания:\n\t{db_link}")


def test_create_lesson(db_session):
    """Проверка создания конкретного занятия."""

    # Подготовка данных
    my_schedule = Schedule(
        odd_or_even="odd",
        day="ср",
        time=time(
            hour=8,
            minute=30
        )
    )
    db_session.add(my_schedule)
    db_session.flush()

    my_lesson1 = Lesson(
        schedule_id=my_schedule.id,
        type="Семинар",
        date=datetime(2026, 4, 1, 8, 30),
    )
    my_lesson2 = Lesson(
        schedule_id=my_schedule.id,
        type="Лекция",
        topic="Информатика",
        date=datetime(2026, 4, 1, 10, 30),
        is_assessment=True
    )
    db_session.add(my_lesson1)
    db_session.add(my_lesson2)
    db_session.flush()

    # Получение данных из базы данных
    db_lesson1 = db_session.get(Lesson, my_lesson1.id)
    db_lesson2 = db_session.get(Lesson, my_lesson2.id)

    # Проверка
    assert db_lesson1 is not None
    assert db_lesson1.id == my_lesson1.id
    assert db_lesson1.schedule_id == my_schedule.id
    assert db_lesson1.type == my_lesson1.type
    assert db_lesson1.topic == my_lesson1.topic
    assert db_lesson1.date == my_lesson1.date
    assert db_lesson1.is_assessment == my_lesson1.is_assessment

    assert db_lesson2 is not None
    assert db_lesson2.id == my_lesson2.id
    assert db_lesson2.schedule_id == my_schedule.id
    assert db_lesson2.type == my_lesson2.type
    assert db_lesson2.topic == my_lesson2.topic
    assert db_lesson2.date == my_lesson2.date
    assert db_lesson2.is_assessment == my_lesson2.is_assessment

    # Вывод
    print(f" Успешно созданы занятие в календаре:\n\t{db_lesson1}\n\t{db_lesson2}")


def test_create_attendance_mark_comments(db_session):
    """Комплексная проверка посещаемости, оценок и комментариев."""

    # Подготовка данных
    my_group = Group(name="ИУ7-31")
    db_session.add(my_group)
    db_session.flush()

    my_student = Student(group_id=my_group.id, surname="Петров", first_name="Петр")
    my_schedule = Schedule(odd_or_even="odd", day="чт", time=time(13, 50))
    db_session.add_all([my_student, my_schedule])
    db_session.flush()

    my_lesson = Lesson(schedule_id=my_schedule.id, type="Семинар", date=datetime.now())
    db_session.add(my_lesson)
    db_session.flush()

    my_attendance = Attendance(student_id=my_student.id, lesson_id=my_lesson.id, is_visited=True)
    my_mark = Mark(student_id=my_student.id, lesson_id=my_lesson.id, data=5)
    my_comment = Comment(student_id=my_student.id, lesson_id=my_lesson.id, data="Отличный ответ у доски")

    db_session.add_all([my_attendance, my_mark, my_comment])
    db_session.flush()

    # Получение данных из базы данных
    db_attendance = db_session.get(Attendance, my_attendance.id)
    db_mark = db_session.get(Mark, my_mark.id)
    db_comment = db_session.get(Comment, my_comment.id)

    # Проверка
    assert db_attendance is not None
    assert db_attendance.id == my_attendance.id
    assert db_attendance.is_visited == my_attendance.is_visited

    assert db_mark is not None
    assert db_mark.id == my_mark.id
    assert db_mark.data == my_mark.data

    assert db_comment is not None
    assert db_comment.id == my_comment.id
    assert db_comment.data == my_comment.data

    # Вывод
    print(f" Успешно проставлены посещаемость, оценки и оставлен комментарий:"
          f"\n\t{db_attendance}\n\t{db_mark}\n\t{db_comment}")
