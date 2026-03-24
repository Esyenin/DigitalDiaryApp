"""
Реализация баз данных для приложения (подробнее смотри pdf-диаграмму)
"""
from datetime import datetime
from typing import List, Optional
from sqlalchemy import create_engine, ForeignKey, func, String, Integer, Boolean, select, DateTime
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

class Group(Base):
    # Столбцы модели
    name: Mapped[str] = mapped_column(String(16))

    # Связи
    students: Mapped[List["Student"]] = relationship(back_populates="group", cascade="all, delete-orphan")
    schedules: Mapped[List["Schedule"]] = relationship(back_populates="group", cascade="all, delete-orphan")


class Student(Base):
    # Столбцы модели
    id_group: Mapped[int] = mapped_column(ForeignKey("groups.id"))
    surname: Mapped[str] = mapped_column(String(128))
    first_name: Mapped[str] = mapped_column(String(128))
    patronymic: Mapped[Optional[str]] = mapped_column(String(128))

    # Связи
    group: Mapped["Group"] = relationship(back_populates="students")


class Schedule(Base):
    # Столбцы модели
    id_group: Mapped[int] = mapped_column(ForeignKey("groups.id"))
    odd_or_even: Mapped[str] = mapped_column(String(16))
    day: Mapped[datetime] = mapped_column(DateTime)
    time: Mapped[datetime] = mapped_column(DateTime)

    # Связи
    group: Mapped["Group"] = relationship(back_populates="schedules")


test_engine = create_engine("sqlite:///:memory:")
TestSessionLocal = sessionmaker(bind=test_engine)


def test():
    # Создаем таблицы в тестовой БД на основе ваших моделей
    Base.metadata.create_all(bind=test_engine)

    # Создаем новую сессию
    with TestSessionLocal() as session:
        try:
            print("--- Запуск теста БД ---")

            # 1. Создаем группу
            new_group = Group(name="ПИ-201")
            session.add(new_group)
            session.flush()  # Чтобы получить id группы для связей

            # 2. Создаем студента
            new_student = Student(
                id_group=new_group.id,
                surname="Иванов",
                first_name="Иван",
                patronymic="Иванович"
            )
            session.add(new_student)

            # 3. Создаем запись в расписании
            # Используем datetime.now() для теста времени
            now = datetime.now()
            new_schedule = Schedule(
                id_group=new_group.id,
                odd_or_even="odd",
                day=now,
                time=now
            )
            session.add(new_schedule)

            # Сохраняем всё в базу
            session.commit()
            print("✅ Данные успешно добавлены и закомичены.")

            # --- ПРОВЕРКИ (Assertions) ---

            # Проверяем студента и его связь с группой
            stmt = select(Student).where(Student.surname == "Иванов")
            student_from_db = session.scalars(stmt).first()

            assert student_from_db is not None, "Студент не найден в БД"
            assert student_from_db.group.name == "ПИ-201", "Ошибка связи: Неверное имя группы у студента"
            print(f"✅ Связь Student -> Group работает (Группа: {student_from_db.group.name})")

            # Проверяем обратную связь: Группа -> Список студентов
            assert len(new_group.students) == 1, "Ошибка связи: Студент не отображается в списке группы"
            print(f"✅ Связь Group -> Students работает (В группе {len(new_group.students)} чел.)")

            # Проверяем автоматические колонки (Base)
            assert student_from_db.created_at is not None, "Ошибка: created_at не заполнился"
            print(f"✅ Базовые колонки (created_at) работают. Время создания: {student_from_db.created_at}")

            print("\n--- Все тесты успешно пройдены! ---")

        except Exception as e:
            session.rollback()
            print(f"❌ Тест провален из-за ошибки: {e}")
            raise e
        finally:
            # Удаляем таблицы после теста
            Base.metadata.drop_all(bind=test_engine)


if __name__ == "__main__":
    test()
