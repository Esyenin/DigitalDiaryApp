"""
Реализация архитектуры базы данных для приложения (электронный дневник).
Используется SQLAlchemy 2.0 с декларативным стилем описания моделей.
Подробное описание моделей и их связи смотри в pdf-диаграмме.
"""
from datetime import datetime
from typing import List, Optional
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Time,
    create_engine,
    func,
    select
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    declared_attr,
    mapped_column,
    relationship,
    sessionmaker
)
from config import settings


# URL-адрес базы данных
DATABASE_URL = settings.get_db_url()


class Base(DeclarativeBase):
    """
    Абстрактный базовый класс.
    Содержит общие поля (id, даты создания и обновления) и логику именования таблиц.
    """

    # Абстрактность
    __abstract__ = True

    # Базовые столбцы модели
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    @declared_attr.directive
    def __tablename__(cls) -> str:
        """Автоматическое именование таблиц во множественном числе (добавление 's')."""
        return cls.__name__.lower() + 's'

    def __repr__(self) -> str:
        """Автоматическое текстовое представление всех моделей."""
        cols = []
        for col in self.__table__.columns.keys():
            cols.append(f"{col}={getattr(self, col)}")
        return f"<{self.__class__.__name__}({', '.join(cols[:4])})>"


class Group(Base):
    """Модель учебной группы."""

    # Столбцы модели
    name: Mapped[str] = mapped_column(String(16))
    speciality: Mapped[Optional[str]] = mapped_column(String(128))

    # Связи с занятиями в расписании (One-to-Many)
    schedule_links: Mapped[List["ScheduleGroupLink"]] = relationship(back_populates="group", cascade="all, delete-orphan")
    # Связи со студентами (One-to-Many)
    students: Mapped[List["Student"]] = relationship(back_populates="group", cascade="all, delete-orphan")


class Student(Base):
    """Модель студента."""

    # Столбцы модели
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"))
    surname: Mapped[str] = mapped_column(String(128))
    first_name: Mapped[str] = mapped_column(String(128))
    patronymic: Mapped[Optional[str]] = mapped_column(String(128))
    personal_data: Mapped[Optional[str]] = mapped_column(String(16))
    bmstu_email: Mapped[Optional[str]] = mapped_column(String(128))

    # Связь с группой (One-to-One)
    group: Mapped["Group"] = relationship(back_populates="students")
    # Связи с посещенными занятиями (One-to-Many)
    attendances: Mapped[List["Attendance"]] = relationship(back_populates="student", cascade="all, delete")
    # Связи с полученными оценками (One-to-Many)
    marks: Mapped[List["Mark"]] = relationship(back_populates="student", cascade="all, delete")
    # Связи с полученными комментариями (One-to-Many)
    comments: Mapped[List["Comment"]] = relationship(back_populates="student", cascade="all, delete")


class ScheduleGroupLink(Base):
    """Ассоциативная модель для связи Групп и Расписания."""

    # Столбцы модели
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"))
    schedule_id: Mapped[int] = mapped_column(ForeignKey("schedules.id", ondelete="CASCADE"))

    # Связь с группой (One-to-One)
    group: Mapped["Group"] = relationship(back_populates="schedule_links")
    # Связь с занятием в расписании (One-to-One)
    schedule: Mapped["Schedule"] = relationship(back_populates="group_links")


class Schedule(Base):
    """Модель правила расписания (шаблон занятия)."""

    # Столбцы модели
    odd_or_even: Mapped[str] = mapped_column(String(16))
    day: Mapped[datetime] = mapped_column(DateTime)
    time: Mapped[datetime] = mapped_column(Time)

    # Связи с группами на занятии (One-to-Many)
    group_links: Mapped[List["ScheduleGroupLink"]] = relationship(back_populates="schedule", cascade="all, delete-orphan")
    # Связи с занятиями в календаре (One-to-Many)
    lessons: Mapped[List["Lesson"]] = relationship(back_populates="schedule", cascade="all, delete-orphan")


class Lesson(Base):
    """Модель конкретного занятия в течение года"""

    # Столбцы модели
    schedule_id: Mapped[int] = mapped_column(ForeignKey("schedules.id"))
    type: Mapped[str] = mapped_column(String(64))
    topic: Mapped[Optional[str]] = mapped_column(String(512))
    is_assessment: Mapped[bool] = mapped_column(Boolean, default=False)
    date: Mapped[datetime] = mapped_column(DateTime)

    # Связь с занятием в расписании (One-to-One)
    schedule: Mapped["Schedule"] = relationship(back_populates="lessons")
    # Связи с посещениями студентов (One-to-Many)
    attendances: Mapped[List["Attendance"]] = relationship(back_populates="lesson", cascade="all, delete")
    # Связи с оценками студентов (One-to-Many)
    marks: Mapped[List["Mark"]] = relationship(back_populates="lesson", cascade="all, delete")
    # Связи с комментариями к студентам (One-to-Many)
    comments: Mapped[List["Comment"]] = relationship(back_populates="lesson", cascade="all, delete")


class Attendance(Base):
    """Модель посещения занятий"""

    # Столбцы модели
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"))
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id", ondelete="CASCADE"))
    is_visited: Mapped[bool] = mapped_column(Boolean, default=True)

    # Связь с занятием в календаре (One-to-One)
    lesson: Mapped["Lesson"] = relationship(back_populates="attendances")
    # Связь со студентом (One-to-One)
    student: Mapped["Student"] = relationship(back_populates="attendances")


class Mark(Base):
    """Модель отметок за занятия"""

    # Столбцы модели
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"))
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id", ondelete="CASCADE"))
    data: Mapped[int] = mapped_column(Integer)

    # Связь с занятием в календаре (One-to-One)
    lesson: Mapped["Lesson"] = relationship(back_populates="marks")
    # Связь со студентом (One-to-One)
    student: Mapped["Student"] = relationship(back_populates="marks")


class Comment(Base):
    """Модель комментариев для ученика за занятие"""

    # Столбцы модели
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"))
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id", ondelete="CASCADE"))
    data: Mapped[str] = mapped_column(String(4096))

    # Связь с занятием в календаре (One-to-One)
    lesson: Mapped["Lesson"] = relationship(back_populates="comments")
    # Связь со студентом (One-to-One)
    student: Mapped["Student"] = relationship(back_populates="comments")

test_engine = create_engine("sqlite:///:memory:")
TestSessionLocal = sessionmaker(bind=test_engine)

def test_relationships():
    Base.metadata.create_all(bind=test_engine)
    
    with TestSessionLocal() as session:
        try:
            print("🧪 Запуск теста связей БД...")

            # 1. Создаём группу
            group = Group(name="ПИ-201")
            session.add(group)
            session.flush()

            # 2. Создаём студента
            student = Student(
                id_group=group.id,
                surname="Иванов",
                first_name="Иван",
                patronymic="Иванович"
            )
            session.add(student)
            session.flush()

            # 3. Создаём расписание
            now = datetime.now()
            schedule = Schedule(
                id_group=group.id,
                odd_or_even="odd",
                day=now,
                time=now
            )
            session.add(schedule)
            session.flush()

            # 4. Создаём урок
            lesson = Lesson(
                id_schedule=schedule.id,
                type="lecture",
                topic="Введение в БД",
                date=now
            )
            session.add(lesson)
            session.flush()

            # 5. Создаём посещаемость, оценку, комментарий
            attendance = Attendance(id_student=student.id, id_lesson=lesson.id, is_visited=True)
            mark = Mark(id_student=student.id, id_lesson=lesson.id, data=5)
            comment = Comment(id_student=student.id, id_lesson=lesson.id, data="Молодец!")
            session.add_all([attendance, mark, comment])

            session.commit()
            print("✅ Данные добавлены и закомичены")

            # === ПРОВЕРКИ ===

            # 1. Student → Group
            stmt = select(Student).where(Student.surname == "Иванов")
            db_student = session.scalars(stmt).first()
            assert db_student is not None
            assert db_student.groups.name == "ПИ-201"
            print("✅ Student.group → Group работает")

            # 2. Group → Students (обратная связь)
            db_group = session.get(Group, group.id)
            assert len(db_group.students) == 1
            assert db_group.students[0].surname == "Иванов"
            print("✅ Group.students → List[Student] работает")

            # 3. Schedule → Group и обратно
            db_schedule = session.get(Schedule, schedule.id)
            assert db_schedule.groups.id == group.id
            assert schedule in db_group.schedules
            print("✅ Schedule ↔ Group связи работают")

            # 4. Lesson → Schedule
            db_lesson = session.get(Lesson, lesson.id)
            assert db_lesson.schedules.id == schedule.id
            print("✅ Lesson.schedule → Schedule работает")

            # 5. Студент → коллекции (Attendance, Mark, Comment)
            assert len(db_student.attendances) == 1
            assert len(db_student.marks) == 1
            assert len(db_student.comments) == 1
            assert db_student.marks[0].data == 5
            assert db_student.comments[0].data == "Молодец!"
            print("✅ Student → [Attendance, Mark, Comment] коллекции работают")

            # 6. Урок → коллекции
            assert len(db_lesson.attendances) == 1
            assert len(db_lesson.marks) == 1
            assert db_lesson.attendances[0].is_visited is True
            print("✅ Lesson → [Attendance, Mark, Comment] коллекции работают")

            # 7. Проверка created_at из базового класса
            assert db_student.created_at is not None
            print(f"✅ Базовые поля (created_at) работают: {db_student.created_at}")

            # 8. Тест каскадного удаления (опционально)
            session.delete(db_group)
            session.commit()
            session.expunge_all()  # Очищает кэш сессии, чтобы следующие запросы шли в БД
            assert session.get(Student, student.id) is None  # студент удалён каскадом
            assert session.get(Schedule, schedule.id) is None  # расписание тоже
            print("✅ Cascade delete работает")

            print("\n🎉 Все тесты пройдены успешно!")

        except Exception as e:
            session.rollback()
            print(f"❌ Ошибка в тесте: {e}")
            raise
        finally:
            Base.metadata.drop_all(bind=test_engine)


if __name__ == "__main__":
    test_relationships()
