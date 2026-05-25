from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


def make_metric(title: str, value: object, object_name: str = "MetricBox") -> QFrame:
    box = QFrame()
    box.setObjectName(object_name)
    layout = QVBoxLayout(box)
    layout.setContentsMargins(14, 12, 14, 12)
    layout.setSpacing(8)

    title_label = QLabel(title)
    title_label.setObjectName("MetricTitle")
    value_label = QLabel(str(value))
    value_label.setObjectName("MetricValue")

    layout.addWidget(title_label)
    layout.addWidget(value_label)
    return box


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


class StudentCard(QFrame):
    edit_clicked = Signal(object)
    delete_clicked = Signal(object)

    def __init__(self, student, name_text: str, group_name: str, parent=None) -> None:
        super().__init__(parent)
        self.student = student
        self.setObjectName("SettingsCard")

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


def make_table_row(values: list[QWidget | str], object_name: str = "TableRow") -> QFrame:
    row = QFrame()
    row.setObjectName(object_name)
    layout = QHBoxLayout(row)
    layout.setContentsMargins(12, 10, 12, 10)
    layout.setSpacing(16)
    for value in values:
        widget = value if isinstance(value, QWidget) else QLabel(str(value))
        widget.setMinimumWidth(120)
        layout.addWidget(widget, stretch=1)
    return row

