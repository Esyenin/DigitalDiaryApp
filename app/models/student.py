# student.py
"""Модель студентов."""
# pylint: disable=unsubscriptable-object

from datetime import datetime
from typing import List, Optional

from sqlalchemy import ForeignKey, String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship, Session

from app.database import Base, get_session


class Student(Base):
    """Реализация модели."""
    __tablename__ = "students"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"), nullable=False, index=True)
    surname: Mapped[str] = mapped_column(String(128), nullable=False)
    first_name: Mapped[str] = mapped_column(String(128), nullable=False)
    patronymic: Mapped[Optional[str]] = mapped_column(String(128))
    personal_data: Mapped[Optional[str]] = mapped_column(String(16), unique=True, index=True)
    bmstu_email: Mapped[Optional[str]] = mapped_column(String(128))

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, server_default=func.now())

    group: Mapped["Group"] = relationship(back_populates="students")
    attendances: Mapped[List["Attendance"]] = relationship(back_populates="student", cascade="all, delete")
    marks: Mapped[List["Mark"]] = relationship(back_populates="student", cascade="all, delete")
    comments: Mapped[List["Comment"]] = relationship(back_populates="student", cascade="all, delete")


class StudentCRUD:
    """CRUD для Student"""

    @staticmethod
    def crud_students(action: str, student_id: Optional[int] = None, group_id: Optional[int] = None, surname: Optional[str] = None, first_name: Optional[str] = None, patronymic: Optional[str] = None, personal_data: Optional[str] = None, bmstu_email: Optional[str] = None, session: Optional[Session] = None):
        close_session = False
        if session is None:
            session = next(get_session())
            close_session = True
        try:
            from sqlalchemy import select
            if action == "create":
                if not all([group_id, surname, first_name]): raise ValueError("Нужно: group_id, surname, first_name")
                student = Student(group_id=group_id, surname=surname, first_name=first_name, patronymic=patronymic, personal_data=personal_data, bmstu_email=bmstu_email)
                session.add(student)
                session.commit()
                session.refresh(student)
                return student
            elif action == "read":
                if student_id:
                    result = session.execute(select(Student).where(Student.id == student_id))
                    return result.scalar_one_or_none()
                return list(session.execute(select(Student)).scalars().all())
            elif action == "update":
                if not student_id: raise ValueError("Нужно: student_id")
                result = session.execute(select(Student).where(Student.id == student_id))
                student = result.scalar_one_or_none()
                if student:
                    if group_id: student.group_id = group_id
                    if surname: student.surname = surname
                    if first_name: student.first_name = first_name
                    if patronymic: student.patronymic = patronymic
                    if personal_data: student.personal_data = personal_data
                    if bmstu_email: student.bmstu_email = bmstu_email
                    student.updated_at = datetime.utcnow()
                    session.commit()
                    session.refresh(student)
                return student
            elif action == "delete":
                if not student_id: raise ValueError("Нужно: student_id")
                result = session.execute(select(Student).where(Student.id == student_id))
                student = result.scalar_one_or_none()
                if student:
                    session.delete(student)
                    session.commit()
                    return True
                return False
            else:
                raise ValueError(f"Неизвестное: {action}")
        except Exception as e:
            session.rollback()
            raise e
        finally:
            if close_session:
                session.close()