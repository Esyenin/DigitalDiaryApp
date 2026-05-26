from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout


class ScheduleTemplateCard(QFrame):
    edit_clicked = Signal(object)
    delete_clicked = Signal(object)

    def __init__(self, schedule, topic: str, groups_text: str, parent=None) -> None:
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
        subject = QLabel(topic)
        subject.setObjectName("SettingsCardText")

        text_box.addWidget(title)
        text_box.addWidget(groups)
        text_box.addWidget(subject)

        edit_button = QPushButton("Edit")
        edit_button.setObjectName("CardEditButton")
        delete_button = QPushButton("Delete")
        delete_button.setObjectName("CardDeleteButton")
        edit_button.clicked.connect(lambda: self.edit_clicked.emit(self.schedule))
        delete_button.clicked.connect(lambda: self.delete_clicked.emit(self.schedule))

        layout.addLayout(text_box)
        layout.addStretch()
        layout.addWidget(edit_button)
        layout.addWidget(delete_button)
