from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout


class StudentCard(QFrame):
    clicked = Signal(object)
    edit_clicked = Signal(object)
    delete_clicked = Signal(object)

    def __init__(self, student, name_text: str, group_name: str, parent=None) -> None:
        super().__init__(parent)
        self.student = student
        self.setObjectName("SettingsCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(16)

        icon = QLabel("S")
        icon.setObjectName("RoundIconMuted")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setFixedSize(54, 54)

        text_box = QVBoxLayout()
        title = QLabel(name_text)
        title.setObjectName("SettingsCardTitle")
        group = QLabel(group_name)
        group.setObjectName("SmallPill")
        group.setAlignment(Qt.AlignmentFlag.AlignCenter)
        group.setFixedWidth(86)
        text_box.addWidget(title)
        text_box.addWidget(group, alignment=Qt.AlignmentFlag.AlignLeft)

        edit_button = QPushButton("Edit")
        edit_button.setObjectName("CardEditButton")
        delete_button = QPushButton("Delete")
        delete_button.setObjectName("CardDeleteButton")
        edit_button.clicked.connect(lambda: self.edit_clicked.emit(self.student))
        delete_button.clicked.connect(lambda: self.delete_clicked.emit(self.student))

        layout.addWidget(icon)
        layout.addLayout(text_box)
        layout.addStretch()
        layout.addWidget(edit_button)
        layout.addWidget(delete_button)

    def mousePressEvent(self, event):  # noqa: N802 - Qt method name
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.student)
        super().mousePressEvent(event)
