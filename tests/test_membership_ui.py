"""Headless Qt smoke coverage for archived and historical student views."""

import os

import pytest

from app.ui.data import repository as repository_module


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
