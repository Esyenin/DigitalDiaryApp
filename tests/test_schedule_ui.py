import os
from datetime import date, time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QDateEdit, QDialog

from app.models import Schedule
from app.ui.data import repository as repository_module
from app.ui.windows.ui_MainWindowsUI import MainWindow


def test_schedule_editor_requires_visible_effective_date(tmp_path, monkeypatch):
    monkeypatch.setattr(
        repository_module, "DATABASE_URL", f"sqlite:///{tmp_path / 'test_schedule_ui.db'}"
    )
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        schedule = Schedule(day="Monday", time=time(10), odd_or_even="even", type="Seminar")
        window.repository.session.add(schedule)
        window.repository.session.commit()
        found = []

        def inspect_dialog(dialog):
            date_inputs = dialog.findChildren(QDateEdit)
            assert len(date_inputs) == 1
            assert date_inputs[0].date().toPython() > date.today()
            found.append(True)
            return QDialog.DialogCode.Rejected

        monkeypatch.setattr(QDialog, "exec", inspect_dialog)
        window.show_schedule_dialog(schedule)
        window.delete_schedule(schedule)
        assert found == [True, True]
    finally:
        window.close()
        window.repository.engine.dispose()
        del app
