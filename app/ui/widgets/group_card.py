from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from app.ui.widgets.card_helpers import make_metric


class GroupCard(QFrame):
    clicked = Signal(object)
    edit_clicked = Signal(object)
    delete_clicked = Signal(object)

    def __init__(
        self,
        group,
        stats: dict[str, object],
        *,
        compact: bool = False,
        actions: bool = False,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.group = group
        self.setObjectName("GroupCardCompact" if compact else "GroupCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(18)

        header = QHBoxLayout()
        icon = QLabel("G")
        icon.setObjectName("RoundIcon")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setFixedSize(54, 54)

        title_box = QVBoxLayout()
        name = QLabel(group.name)
        name.setObjectName("GroupCardTitle")
        count = QLabel(f"{stats.get('students', 0)} students")
        count.setObjectName("GroupCardSubtitle")
        title_box.addWidget(name)
        title_box.addWidget(count)

        header.addWidget(icon)
        header.addLayout(title_box)
        header.addStretch()

        if actions:
            edit_button = QPushButton("Edit")
            edit_button.setObjectName("CardEditButton")
            delete_button = QPushButton("Delete")
            delete_button.setObjectName("CardDeleteButton")
            edit_button.clicked.connect(lambda: self.edit_clicked.emit(self.group))
            delete_button.clicked.connect(lambda: self.delete_clicked.emit(self.group))
            header.addWidget(edit_button)
            header.addWidget(delete_button)
        else:
            arrow = QLabel(">")
            arrow.setObjectName("CardArrow")
            header.addWidget(arrow)

        layout.addLayout(header)

        if not compact:
            metrics = QHBoxLayout()
            metrics.setSpacing(14)
            metrics.addWidget(make_metric("Overall Avg", stats.get("overall", "-"), "MetricBlue"))
            metrics.addWidget(make_metric("Lab Avg", stats.get("lab", "-"), "MetricGreen"))
            metrics.addWidget(make_metric("Test Avg", stats.get("test", "-"), "MetricRed"))
            metrics.addWidget(make_metric("Attendance", f"{stats.get('attendance', 0)}%", "MetricPurple"))
            layout.addLayout(metrics)

            badge = QLabel("Excellent")
            badge.setObjectName("DarkBadge")
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            badge.setFixedWidth(88)
            layout.addWidget(badge, alignment=Qt.AlignmentFlag.AlignLeft)

    def mousePressEvent(self, event):  # noqa: N802 - Qt method name
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.group)
        super().mousePressEvent(event)
