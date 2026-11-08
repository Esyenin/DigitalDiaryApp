"""Headless Qt smoke coverage for archived and historical student views."""

import os

import pytest

from app.ui.data import repository as repository_module


def test_lesson_page_is_read_only_until_confirmed(tmp_path, monkeypatch):
    from datetime import date, time
    from sqlalchemy import text
    from PySide6.QtWidgets import QApplication, QMessageBox, QPushButton
    from app.models import Lesson, Schedule, ScheduleGroupLink
    from app.ui.windows.ui_MainWindowsUI import MainWindow

    monkeypatch.setattr(repository_module, "DATABASE_URL", f"sqlite:///{tmp_path / 'lesson_ui.db'}")
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    repo = window.repository
    try:
        group = repo.create_group("Preview", None)
        repo.create_student(group, "Ivan", "Ivanov")
        schedule = Schedule(day=date.today().strftime("%A"), time=time(10),
                            odd_or_even="even", type="Seminar", effective_from=date.today())
        repo.session.add(schedule)
        repo.session.flush()
        repo.session.add(ScheduleGroupLink(schedule_id=schedule.id, group_id=group.id))
        repo.session.flush()
        lesson = Lesson(schedule_id=schedule.id, date=date.today())
        repo.session.add(lesson)
        repo.session.commit()
        before = repo.session.scalar(text("SELECT total_changes()"))
        stats = repo.group_stats(group)
        window.show_lesson_detail(lesson)
        window.show_lesson_detail(lesson, push_history=False)
        assert repo.session.scalar(text("SELECT total_changes()")) == before
        assert repo.group_stats(group) == stats
        assert not lesson.participants_complete
        assert any(button.text() == "Complete roll call"
                   for button in window.detail_page.findChildren(QPushButton))
        monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.No)
        window.complete_lesson_roll_call(lesson)
        assert not lesson.participants_complete
        monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Yes)
        window.complete_lesson_roll_call(lesson)
        assert lesson.participants_complete
        assert lesson.roster_completed_at is not None
    finally:
        window.close()
        app.processEvents()


@pytest.mark.skipif(os.environ.get("QT_QPA_PLATFORM") != "offscreen", reason="Requires offscreen Qt")
def test_student_history_and_archive_views(tmp_path, monkeypatch):
    from PySide6.QtWidgets import QApplication, QLabel

    from app.ui.windows.ui_MainWindowsUI import MainWindow

    monkeypatch.setattr(repository_module, "DATABASE_URL", f"sqlite:///{tmp_path / 'ui.db'}")
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        group = window.repository.create_group("UI-1", None)
        student = window.repository.create_student(group, "Ivan", "Ivanov")
        window.show_student_detail(student)
        labels = [item.text() for item in window.detail_page.findChildren(QLabel)]
        assert any("UI-1" in label for label in labels)
        window.repository.archive_student(student, reason="Graduated")
        window.show_archived_students = True
        window.render_settings_students()
        assert student.id in {
            item.id for item in window.repository.list_students(include_archived=True)
        }
        window.show_student_detail(student)
        labels = [item.text() for item in window.detail_page.findChildren(QLabel)]
        assert any("Graduated" in label for label in labels)
    finally:
        window.close()
        app.processEvents()
