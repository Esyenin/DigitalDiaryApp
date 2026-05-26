from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget


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


def make_link_button(text: str) -> QPushButton:
    button = QPushButton(text)
    button.setObjectName("LinkButton")
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setFlat(True)
    return button


def make_table_row(values: list[QWidget | str], object_name: str = "TableRow") -> QFrame:
    row = QFrame()
    row.setObjectName(object_name)
    layout = QHBoxLayout(row)
    layout.setContentsMargins(12, 10, 12, 10)
    layout.setSpacing(16)
    for value in values:
        widget = value if isinstance(value, QWidget) else QLabel(str(value))
        widget.setMinimumWidth(90)
        layout.addWidget(widget, stretch=1)
    return row
