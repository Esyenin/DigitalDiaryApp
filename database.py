"""
Реализация баз данных для приложения (подробнее смотри pdf-диаграмму)
"""
from datetime import datetime
from typing import List, Optional
from sqlalchemy  import create_engine, ForeignKey, func, String, Integer, Boolean, select, DateTime, event
from sqlalchemy.orm import DeclarativeBase, declared_attr, Mapped, mapped_column, relationship, sessionmaker
from config import settings

DATABASE_URL = settings.get_db_url()

# Базовый класс для всех моделей
class Base(DeclarativeBase):
    # Класс абстрактный, чтобы не создавать отдельную таблицу для него
    __abstract__ = True

    # Базовые столбцы модели
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    # Автоматическое добавление 's' в конец название модели
    @declared_attr.directive
    def __tablename__(cls) -> str:
        return cls.__name__.lower() + 's'

class Group(Base):  # ya natural
    # Столбцы модели
    name: Mapped[str] = mapped_column(String(16))

    # Связи
    students: Mapped[List["Student"]] = relationship(back_populates="groups", cascade="all, delete-orphan")
    schedules: Mapped[List["Schedule"]] = relationship(back_populates="groups", cascade="all, delete-orphan")


class Student(Base):
    # Столбцы модели
    id_group: Mapped[int] = mapped_column(ForeignKey("groups.id"))
    surname: Mapped[str] = mapped_column(String(128))
    first_name: Mapped[str] = mapped_column(String(128))
    patronymic: Mapped[Optional[str]] = mapped_column(String(128))

    # Связи
    groups: Mapped["Group"] = relationship(back_populates="students")
    attendances: Mapped[List["Attendance"]] = relationship(back_populates="students", cascade="all, delete")
    marks: Mapped[List["Mark"]] = relationship(back_populates="students", cascade="all, delete")
    comments: Mapped[List["Comment"]] = relationship(back_populates="students", cascade="all, delete")


class Schedule(Base):
    # Столбцы модели
    id_group: Mapped[int] = mapped_column(ForeignKey("groups.id"))
    odd_or_even: Mapped[str] = mapped_column(String(16))
    day: Mapped[datetime] = mapped_column(DateTime)
    time: Mapped[datetime] = mapped_column(DateTime)

    # Связи
    groups: Mapped["Group"] = relationship(back_populates="schedules")
    lessons: Mapped[List["Lesson"]] = relationship(back_populates="schedules", cascade="all, delete-orphan")


class Lesson(Base):
    id_schedule: Mapped[int] = mapped_column(ForeignKey("schedules.id"))
    type: Mapped[str] = mapped_column(String(64))
    topic: Mapped[str] = mapped_column(String(512))
    is_assessment: Mapped[bool] = mapped_column(default=False)
    date: Mapped[datetime] = mapped_column(DateTime)

    # Связи
    schedules: Mapped["Schedule"] = relationship(back_populates="lessons")
    attendances: Mapped[List["Attendance"]] = relationship(back_populates="lessons", cascade="all, delete")
    marks: Mapped[List["Mark"]] = relationship(back_populates="lessons", cascade="all, delete")
    comments: Mapped[List["Comment"]] = relationship(back_populates="lessons", cascade="all, delete")


class Attendance(Base):
    id_student: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"))
    id_lesson: Mapped[int] = mapped_column(ForeignKey("lessons.id", ondelete="CASCADE"))
    is_visited: Mapped[bool] = mapped_column(default=True)

    # Связи
    lessons: Mapped["Lesson"] = relationship(back_populates="attendances")
    students: Mapped["Student"] = relationship(back_populates="attendances")


class Mark(Base):
    id_student: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"))
    id_lesson: Mapped[int] = mapped_column(ForeignKey("lessons.id", ondelete="CASCADE"))
    data: Mapped[int] = mapped_column(Integer)

    # Связи
    lessons: Mapped["Lesson"] = relationship(back_populates="marks")
    students: Mapped["Student"] = relationship(back_populates="marks")


class Comment(Base):
    id_student: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"))
    id_lesson: Mapped[int] = mapped_column(ForeignKey("lessons.id", ondelete="CASCADE"))
    data: Mapped[str] = mapped_column(String(4096))

    # Связи
    lessons: Mapped["Lesson"] = relationship(back_populates="comments")
    students: Mapped["Student"] = relationship(back_populates="comments")

test_engine = create_engine("sqlite:///:memory:")

@event.listens_for(test_engine, "connect")
def set_sqlite_pragma(dbapi_conn, connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

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
