from __future__ import annotations

from html import escape

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout

from app.models.lesson import Lesson


class LessonCard(QFrame):
    clicked = Signal(object)
    group_clicked = Signal(object)

    def __init__(self, lesson: Lesson, groups_text: str | None = None, parent=None):
        super().__init__(parent)
        self.lesson = lesson
        self.groups_text = groups_text or self._groups_text()
        self.groups_by_id = {
            str(link.group.id): link.group
            for link in sorted(
                self.lesson.schedule.group_links,
                key=lambda item: item.group.name,
            )
        }

        self.setObjectName("LessonCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(210)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(22, 18, 22, 18)
        main_layout.setSpacing(18)

        top_layout = QHBoxLayout()
        top_layout.setSpacing(8)

        self.time_label = QLabel(self._time_text())
        self.time_label.setObjectName("LessonCardTime")

        self.marker = QLabel()
        self.marker.setObjectName("LessonCardMarker")
        self.marker.setFixedSize(16, 16)
        self.marker.setStyleSheet(
            "border-radius: 8px; background-color: "
            + ("#2f80ed" if self.lesson.schedule.is_assessment else "#12c75b")
            + ";"
        )

        top_layout.addWidget(self.time_label)
        top_layout.addStretch()
        top_layout.addWidget(self.marker)

        self.group_label = QLabel()
        self.group_label.setObjectName("LessonCardGroups")
        self.group_label.setTextFormat(Qt.TextFormat.RichText)
        self.group_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        self.group_label.setOpenExternalLinks(False)
        self.group_label.setWordWrap(True)
        self.group_label.linkActivated.connect(self._emit_group_clicked)
        self.group_label.setText(self._group_links_text())

        self.topic_label = QLabel(self.lesson.topic or "Untitled lesson")
        self.topic_label.setObjectName("LessonCardTopic")
        self.topic_label.setWordWrap(True)

        self.type_label = QLabel(self.lesson.schedule.type)
        self.type_label.setObjectName("LessonCardType")
        self.type_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        main_layout.addLayout(top_layout)
        main_layout.addWidget(self.group_label)
        main_layout.addWidget(self.topic_label)
        main_layout.addStretch()
        main_layout.addWidget(self.type_label, alignment=Qt.AlignmentFlag.AlignLeft)

    def mousePressEvent(self, event):  # noqa: N802 - Qt method name
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.lesson)
        super().mousePressEvent(event)

    def _time_text(self) -> str:
        lesson_time = self.lesson.schedule.time
        return lesson_time.strftime("%H:%M") if lesson_time else "No time"

    def _groups_text(self) -> str:
        group_names = [link.group.name for link in self.lesson.schedule.group_links]
        return ", ".join(group_names) if group_names else "No groups"

    def _group_links_text(self) -> str:
        if not self.groups_by_id:
            return escape(self.groups_text)
        links = [
            f'<a href="{group_id}">{escape(group.name)}</a>'
            for group_id, group in self.groups_by_id.items()
        ]
        return ", ".join(links)

    def _emit_group_clicked(self, group_id: str) -> None:
        group = self.groups_by_id.get(group_id)
        if group is not None:
            self.group_clicked.emit(group)
