from __future__ import annotations

from datetime import date

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout


class ScheduleTemplateCard(QFrame):
    edit_clicked = Signal(object)
    delete_clicked = Signal(object)

    def __init__(self, schedule, groups_text: str, parent=None) -> None:
        super().__init__(parent)
        self.schedule = schedule
        self.setObjectName("SettingsCard")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(18)

        text_box = QVBoxLayout()
        text_box.setSpacing(8)

        title = QLabel(
            f"{schedule.day} at {schedule.time.strftime('%H:%M')}  "
            f"{schedule.odd_or_even} week  {schedule.type}"
        )
        title.setObjectName("SettingsCardTitle")
        groups = QLabel(f"Groups: {groups_text}")
        groups.setObjectName("SettingsCardSubtitle")
        until = schedule.effective_until.isoformat() if schedule.effective_until else "ongoing"
        period = QLabel(
            f"Version {schedule.revision}: {schedule.effective_from.isoformat()} to {until}"
        )
        period.setObjectName("SettingsCardSubtitle")
        text_box.addWidget(title)
        text_box.addWidget(groups)
        text_box.addWidget(period)

        edit_button = QPushButton("Edit")
        edit_button.setObjectName("CardEditButton")
        has_history = any(lesson.date <= date.today() for lesson in schedule.lessons)
        delete_button = QPushButton("Deactivate" if has_history else "Delete")
        delete_button.setObjectName("CardDeleteButton")
        edit_button.clicked.connect(lambda: self.edit_clicked.emit(self.schedule))
        delete_button.clicked.connect(lambda: self.delete_clicked.emit(self.schedule))
        if schedule.effective_until is not None:
            edit_button.setEnabled(False)
            delete_button.setEnabled(False)

        layout.addLayout(text_box)
        layout.addStretch()
        layout.addWidget(edit_button)
        layout.addWidget(delete_button)
