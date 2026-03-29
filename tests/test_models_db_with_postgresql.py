"""
Тестирование базы данных postgreSQL с использованием pytest.
Проверяет создание таблиц, корректность связей и работу с сессиями.
"""
# pylint: disable=redefined-outer-name, import-error
from datetime import date, time
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
import pytest

# Импорты моделей и настроек проекта
from app.models.base import Base
from app.models.attendance import Attendance
from app.models.comment import Comment
from app.models.group import Group
from app.models.lesson import Lesson
from app.models.mark import Mark
from app.models.schedule import Schedule
from app.models.schedule_group_link import ScheduleGroupLink
from app.models.student import Student
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
    my_schedule1 = Schedule(
        odd_or_even="odd",
        type="семинар",
        day="вт",
        time=time(
            hour=8,
            minute=45
        )
    )
    my_schedule2 = Schedule(
        odd_or_even="even",
        type="лекция",
        is_assessment=True,
        day="пн",
        time=time(
            hour=10,
            minute=30
        )
    )

    db_session.add(my_schedule1)
    db_session.add(my_schedule2)
    db_session.flush()

    # Получение данных из базы данных
    db_schedule1 = db_session.get(Schedule, my_schedule1.id)
    db_schedule2 = db_session.get(Schedule, my_schedule2.id)

    # Проверка
    assert db_schedule1 is not None
    assert db_schedule1.id == my_schedule1.id
    assert db_schedule1.odd_or_even == my_schedule1.odd_or_even
    assert db_schedule1.type == my_schedule1.type
    assert db_schedule1.is_assessment == my_schedule1.is_assessment
    assert db_schedule1.day == my_schedule1.day
    assert db_schedule1.time == my_schedule1.time

    assert db_schedule2 is not None
    assert db_schedule2.id == my_schedule2.id
    assert db_schedule2.odd_or_even == my_schedule2.odd_or_even
    assert db_schedule2.type == my_schedule2.type
    assert db_schedule2.is_assessment == my_schedule2.is_assessment
    assert db_schedule2.day == my_schedule2.day
    assert db_schedule2.time == my_schedule2.time

    # Вывод
    print(f" Удалось успешно создать расписание:\n\t{db_schedule1}\n\t{db_schedule2}")


def test_create_schedule_group_link(db_session):
    """Проверка связи между Группой и Расписанием."""

    # Подготовка данных
    my_group = Group(name="МТ10-11")
    my_schedule = Schedule(
        odd_or_even="even",
        type="семинар",
        day="вт",
        time=time(
            hour=12,
            minute=0
        )
    )

    db_session.add_all([my_group, my_schedule])
    db_session.flush()

    my_link = ScheduleGroupLink(
        group_id=my_group.id,
        schedule_id=my_schedule.id
    )

    db_session.add(my_link)
    db_session.flush()

    # Получение данных из базы данных
    db_link = db_session.get(ScheduleGroupLink, my_link.id)

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
        type="лекция",
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
        date=date(2026, 4, 1),
    )
    my_lesson2 = Lesson(
        schedule_id=my_schedule.id,
        topic="Информатика",
        date=date(2026, 4, 1),
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
    assert db_lesson1.topic == my_lesson1.topic
    assert db_lesson1.date == my_lesson1.date

    assert db_lesson2 is not None
    assert db_lesson2.id == my_lesson2.id
    assert db_lesson2.schedule_id == my_schedule.id
    assert db_lesson2.topic == my_lesson2.topic
    assert db_lesson2.date == my_lesson2.date

    # Вывод
    print(f" Успешно созданы занятие в календаре:\n\t{db_lesson1}\n\t{db_lesson2}")


def test_create_attendance_mark_comments(db_session):
    """Комплексная проверка посещаемости, оценок и комментариев."""

    # Подготовка данных
    my_group = Group(name="ИУ7-31")
    db_session.add(my_group)
    db_session.flush()

    my_student = Student(group_id=my_group.id, surname="Петров", first_name="Петр")
    my_schedule = Schedule(odd_or_even="odd", type="Семинар", day="чт", time=time(13, 50))
    db_session.add_all([my_student, my_schedule])
    db_session.flush()

    my_lesson = Lesson(schedule_id=my_schedule.id, date=date(2026, 3, 1))
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


def test_simulate_db_app(db_session):
    """
    Проверка связей базы данных
    Полная симуляция работы базы данных
    """

    # Создание групп
    my_group_1 = Group(name="ИУ7-31")
    my_group_2 = Group(name="СМ1-21Б")

    db_session.add(my_group_1)
    db_session.add(my_group_2)
    db_session.flush()

    # Создание студентов
    my_student1_g1 = Student(group_id=my_group_1.id, surname="Петров", first_name="Петр")
    my_student2_g1 = Student(group_id=my_group_1.id, surname="Иванов", first_name="Иван")
    my_student1_g2 = Student(group_id=my_group_2.id, surname="Сидоров", first_name="Гриша")
    my_student2_g2 = Student(group_id=my_group_2.id, surname="Попов", first_name="Алексей")

    db_session.add(my_student1_g1)
    db_session.add(my_student2_g1)
    db_session.add(my_student1_g2)
    db_session.add(my_student2_g2)
    db_session.flush()

    # Создание расписаний
    my_schedule1 = Schedule(odd_or_even="even", type="Семинар", is_assessment=True, day="вт",
                            time=time(hour=12,minute=0))
    my_schedule2 = Schedule(odd_or_even="odd", type="Семинар", day="ср", time=time(hour=8, minute=30))
    my_schedule3 = Schedule(odd_or_even="odd", type="Семинар", day="пт", time=time(hour=16, minute=50))

    db_session.add(my_schedule1)
    db_session.add(my_schedule2)
    db_session.add(my_schedule3)
    db_session.flush()

    # Создание связей групп и расписаний
    my_link1_g1 = ScheduleGroupLink(group_id=my_group_1.id,schedule_id=my_schedule1.id)
    my_link2_g1 = ScheduleGroupLink(group_id=my_group_1.id, schedule_id=my_schedule2.id)
    my_link1_g2 = ScheduleGroupLink(group_id=my_group_2.id, schedule_id=my_schedule1.id)
    my_link2_g2 = ScheduleGroupLink(group_id=my_group_2.id, schedule_id=my_schedule3.id)

    db_session.add(my_link1_g1)
    db_session.add(my_link2_g1)
    db_session.add(my_link1_g2)
    db_session.add(my_link2_g2)
    db_session.flush()

    # Создание занятий
    my_lesson1 = Lesson(schedule_id=my_schedule1.id, date=date(2026, 4, 1))
    my_lesson2 = Lesson(schedule_id=my_schedule2.id, date=date(2026, 5, 1))
    my_lesson3 = Lesson(schedule_id=my_schedule3.id, date=date(2026, 6, 1))

    db_session.add(my_lesson1)
    db_session.add(my_lesson2)
    db_session.add(my_lesson3)
    db_session.flush()

    # Создание посещений
    my_attendance_s1_g1_l1 = Attendance(student_id=my_student1_g1.id, lesson_id=my_lesson1.id, is_visited=True)
    my_attendance_s2_g1_l1 = Attendance(student_id=my_student2_g1.id, lesson_id=my_lesson1.id)
    my_attendance_s1_g2_l1 = Attendance(student_id=my_student1_g2.id, lesson_id=my_lesson1.id, is_visited=True)
    my_attendance_s2_g2_l1 = Attendance(student_id=my_student2_g2.id, lesson_id=my_lesson1.id)

    my_attendance_s1_g1_l2 = Attendance(student_id=my_student1_g1.id, lesson_id=my_lesson2.id, is_visited=True)
    my_attendance_s2_g1_l2 = Attendance(student_id=my_student2_g1.id, lesson_id=my_lesson2.id, is_visited=True)

    my_attendance_s1_g2_l3 = Attendance(student_id=my_student1_g2.id, lesson_id=my_lesson3.id, is_visited=True)
    my_attendance_s2_g2_l3 = Attendance(student_id=my_student2_g2.id, lesson_id=my_lesson3.id)

    db_session.add_all([my_attendance_s1_g1_l1, my_attendance_s2_g1_l1, my_attendance_s1_g2_l1, my_attendance_s2_g2_l1])
    db_session.add_all([my_attendance_s1_g1_l2, my_attendance_s2_g1_l2])
    db_session.add_all([my_attendance_s1_g2_l3, my_attendance_s2_g2_l3])
    db_session.flush()

    # Создание оценок
    my_mark_s1_g1_l1 = Mark(student_id=my_student1_g1.id, lesson_id=my_lesson1.id, data=5)
    my_mark_s1_g2_l1 = Mark(student_id=my_student1_g2.id, lesson_id=my_lesson1.id, data=4)
    my_mark_s1_g1_l2 = Mark(student_id=my_student1_g1.id, lesson_id=my_lesson2.id, data=3)
    my_mark_s2_g1_l2 = Mark(student_id=my_student2_g1.id, lesson_id=my_lesson2.id, data=3)
    my_mark_s1_g2_l3 = Mark(student_id=my_student1_g2.id, lesson_id=my_lesson3.id, data=2)

    db_session.add(my_mark_s1_g1_l1)
    db_session.add(my_mark_s1_g2_l1)
    db_session.add(my_mark_s1_g1_l2)
    db_session.add(my_mark_s2_g1_l2)
    db_session.add(my_mark_s1_g2_l3)
    db_session.flush()

    # Создание комментариев
    my_comment_s1_g1_l1 = Comment(student_id=my_student1_g1.id, lesson_id=my_lesson1.id,
                                  data="Отличная работа на семинаре")
    db_session.add(my_comment_s1_g1_l1)
    db_session.flush()

    # --- ИТОГОВЫЕ ПРОВЕРКИ СВЯЗЕЙ ---

    # 1. Проверяем, что занятие my_lesson1 (по расписанию my_schedule1) видят обе группы
    db_lesson1 = db_session.get(Lesson, my_lesson1.id)
    groups_on_lesson1 = [link.group.name for link in db_lesson1.schedule.group_links]
    assert "ИУ7-31" in groups_on_lesson1
    assert "СМ1-21Б" in groups_on_lesson1

    # 2. Проверяем посещаемость для my_lesson1 (должно быть 4 записи)
    assert len(db_lesson1.attendances) == 4
    visited_count = len([a for a in db_lesson1.attendances if a.is_visited])
    assert visited_count == 2  # Петров и Сидоров

    # 3. Проверяем "путь" от оценки до названия группы через студента
    db_mark_s1_g1_l1 = db_session.get(Mark, my_mark_s1_g1_l1.id)
    assert db_mark_s1_g1_l1.student.group.name == "ИУ7-31"

    # 4. Проверяем каскадное удаление: удалим вторую группу и проверим связи
    db_session.delete(my_group_2)
    db_session.flush()

    # 5. Студенты группы 2 должны исчезнуть
    check_student = db_session.get(Student, my_student1_g2.id)
    assert check_student is None

    # 6. Связи в ScheduleGroupLink для этой группы тоже должны удалиться автоматически
    remaining_links = db_session.execute(
        select(ScheduleGroupLink).where(ScheduleGroupLink.group_id == my_group_2.id)
    ).scalars().all()
    assert len(remaining_links) == 0

    # Вывод
    print(" Полная симуляция работы БД пройдена.")
