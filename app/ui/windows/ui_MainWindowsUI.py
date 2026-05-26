from __future__ import annotations

from datetime import date, time, timedelta
from html import escape
from pathlib import Path
import sys

from PySide6.QtCore import QSettings, Qt, QTime
from PySide6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from app.models import Group, Lesson, Schedule, Student
from app.ui.data.calendar import (
    DAY_NAMES,
    DEFAULT_SEMESTER_START,
    DEFAULT_SEMESTER_WEEKS,
    SemesterSettings,
    clamp_week_start,
    day_index,
    format_input_date,
    format_long_date,
    format_short_date,
    format_week_range,
    monday_for,
    parse_date_input,
    parse_week_count,
    week_number_for,
    week_type_for_number,
    week_type_label,
)
from app.ui.data.repository import DiaryRepository, ImportPreview, RepositoryError
from app.ui.generated.MainWindowUI import Ui_MainWindow
from app.ui.widgets.card_helpers import make_link_button, make_metric, make_table_row
from app.ui.widgets.group_card import GroupCard
from app.ui.widgets.lesson_card import LessonCard
from app.ui.widgets.schedule_template_card import ScheduleTemplateCard
from app.ui.widgets.student_card import StudentCard


def clear_layout(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        child_layout = item.layout()
        if widget is not None:
            widget.setParent(None)
            widget.deleteLater()
        elif child_layout is not None:
            clear_layout(child_layout)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.repository = DiaryRepository()
        self.settings_store = QSettings("DigitalDiaryApp", "TeacherDigitalDiary")
        self.semester_settings = self._load_semester_settings()
        self.selected_week_start = clamp_week_start(
            monday_for(date.today()),
            self.semester_settings,
        )
        self.student_filter_group_id: int | None = None
        self.detail_page: QWidget | None = None
        self.navigation_history: list[tuple[str, object | None]] = []
        self.current_route: tuple[str, object | None] = ("main", "schedule")
        self.current_theme = str(self.settings_store.value("ui/theme", "light"))
        if self.current_theme not in {"light", "dark"}:
            self.current_theme = "light"
        self._groups_grid_columns: int | None = None
        self._settings_groups_grid_columns: int | None = None
        self._ui_ready = False

        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.ui.sourceWidget.setVisible(True)
        self.ui.mainWidget.setCurrentWidget(self.ui.pageSchedule)

        self._configure_menubar()
        self._apply_styles()
        self._apply_layout_visuals()
        self._configure_inputs()
        self._connect_actions()
        self._populate_semester_inputs()
        self.refresh_all()
        self._ui_ready = True

    def closeEvent(self, event):  # noqa: N802 - Qt method name
        self.repository.close()
        super().closeEvent(event)

    def resizeEvent(self, event):  # noqa: N802 - Qt method name
        super().resizeEvent(event)
        if not getattr(self, "_ui_ready", False):
            return

        self._apply_responsive_margins()
        groups_columns = self._grid_columns(compact=False)
        settings_groups_columns = self._grid_columns(compact=True)
        if groups_columns != self._groups_grid_columns:
            self.render_groups()
        if settings_groups_columns != self._settings_groups_grid_columns:
            self.render_settings_groups()

    def refresh_all(self) -> None:
        self.render_schedule()
        self.render_groups()
        self.render_settings_schedules()
        self.render_settings_groups()
        self.render_settings_students()
        self.update_semester_info_label()
        self._sync_nav_state()

    def _load_semester_settings(self) -> SemesterSettings:
        start_text = self.settings_store.value("semester/start_date", "")
        weeks_text = self.settings_store.value("semester/total_weeks", "")
        try:
            start_date = parse_date_input(str(start_text))
            total_weeks = parse_week_count(str(weeks_text))
            if start_date.weekday() != 0:
                raise ValueError
        except (TypeError, ValueError):
            return SemesterSettings(DEFAULT_SEMESTER_START, DEFAULT_SEMESTER_WEEKS)
        return SemesterSettings(start_date, total_weeks)

    def _save_semester_settings(self) -> None:
        self.settings_store.setValue(
            "semester/start_date",
            format_input_date(self.semester_settings.start_date),
        )
        self.settings_store.setValue(
            "semester/total_weeks",
            str(self.semester_settings.total_weeks),
        )
        self.settings_store.sync()

    def _configure_menubar(self) -> None:
        self.ui.menu.setTitle("Settings")
        self.ui.menu.clear()

        self.ui.action.setText("Import database...")
        self.ui.action_3.setText("Export database...")
        self.ui.action_4.setText("")
        #self.ui.action_5.setText("Multi-sheet smart import...")
        #self.ui.action_6.setText("Human table import...")
        self._update_theme_button_text()

        self.ui.menu.addAction(self.ui.action)
        #self.ui.menu.addAction(self.ui.action_6)
        #self.ui.menu.addAction(self.ui.action_5)
        self.ui.menu.addAction(self.ui.action_3)
        self.ui.menu.addSeparator()
        self.ui.menu.addAction(self.ui.action_4)

    def _configure_inputs(self) -> None:
        self._replace_semester_text_edits()
        for text_box in (
            self.ui.settingsSemesterActionDateTextBox,
            self.ui.settingsSemesterActionTextBox,
        ):
            text_box.setFixedHeight(42)
            text_box.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Fixed,
            )

        self.ui.settingsSemesterActionDateTextBox.setPlaceholderText("YYYY-MM-DD")
        self.ui.settingsSemesterActionTextBox.setPlaceholderText("17")

    def _replace_semester_text_edits(self) -> None:
        replacements = (
            (
                "settingsSemesterActionDateTextBox",
                self.ui.settingsSemesterActionDate,
            ),
            (
                "settingsSemesterActionTextBox",
                self.ui.settingsSemesterActionWeekInput,
            ),
        )
        for attribute_name, layout in replacements:
            old_widget = getattr(self.ui, attribute_name)
            index = layout.indexOf(old_widget)
            if index < 0:
                continue
            new_widget = QLineEdit(old_widget.parent())
            new_widget.setObjectName(old_widget.objectName())
            layout.removeWidget(old_widget)
            old_widget.setParent(None)
            old_widget.deleteLater()
            layout.insertWidget(index, new_widget)
            setattr(self.ui, attribute_name, new_widget)

    def _connect_actions(self) -> None:
        self.ui.mainButtonSchedule.clicked.connect(
            lambda: self._show_main_page(self.ui.pageSchedule)
        )
        self.ui.mainButtonGroups.clicked.connect(
            lambda: self._show_main_page(self.ui.pageGroups)
        )
        self.ui.mainButtonSettings.clicked.connect(self._show_settings_home)

        self.ui.settingsAlternativeButtonSchedule.clicked.connect(
            lambda: self._show_settings_page(self.ui.pageSettingsSchedule)
        )
        self.ui.settingsAlternativeButtonGroups.clicked.connect(
            lambda: self._show_settings_page(self.ui.pageSettingsGroups)
        )
        self.ui.settingsAlternativeButtonStudents.clicked.connect(
            lambda: self._show_settings_page(self.ui.pageSettingsStudents)
        )
        self.ui.settingsAlternativeButtonSemester.clicked.connect(
            lambda: self._show_settings_page(self.ui.pageSettingsSemester)
        )

        self.ui.scheduleDateButtonLeft.clicked.connect(lambda: self.move_week(-1))
        self.ui.scheduleDateButtonRight.clicked.connect(lambda: self.move_week(1))
        self.ui.scheduleDateButtonToday.clicked.connect(self.go_to_today)

        self.ui.settingsSemesterActionWeekChangeButtonIncrease.clicked.connect(
            lambda: self.change_semester_week_input(1)
        )
        self.ui.settingsSemesterActionWeekChangeButtonDecrease.clicked.connect(
            lambda: self.change_semester_week_input(-1)
        )
        self.ui.settingsSemesterActionSaveButton.clicked.connect(
            self.apply_semester_settings
        )

        self.ui.settingsScheduleChangeActionButton.clicked.connect(
            lambda: self.show_schedule_dialog()
        )
        self.ui.settingsGroupsChangeActionButton.clicked.connect(
            lambda: self.show_group_dialog()
        )
        self.ui.settingsStudentsChangeActionButton.clicked.connect(
            lambda: self.show_student_dialog()
        )
        self.ui.settingsStudentsChangeChooseButton.clicked.connect(
            self.show_student_filter_menu
        )
        self.ui.action.triggered.connect(self.show_import_dialog)
        self.ui.action_6.triggered.connect(self.import_human_table_xlsx)
        self.ui.action_5.triggered.connect(self.import_multisheet_smart_xlsx)
        self.ui.action_3.triggered.connect(self.export_database)
        self.ui.action_4.triggered.connect(self.toggle_theme)

    def import_human_table_xlsx(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Choose XLSX file for human table import",
            "",
            "Excel files (*.xlsx);;All files (*.*)",
        )

        if not file_path:
            return

        try:
            report = self.repository.import_human_table_xlsx(file_path)
        except RepositoryError as exc:
            QMessageBox.critical(
                self,
                "Human table import error",
                str(exc),
            )
            return
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Human table import error",
                f"Unexpected error:\n{exc}",
            )
            return

        QMessageBox.information(
            self,
            "Human table import",
            f"Import finished successfully.\n\n{report}",
        )

        self.repository.refresh()
        self.refresh_all()
    def import_multisheet_smart_xlsx(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Choose XLSX file for multi-sheet smart import",
            "",
            "Excel files (*.xlsx);;All files (*.*)",
        )

        if not file_path:
            return

        reply = QMessageBox.question(
            self,
            "Умный импорт всей книги",
            "Этот импорт рассчитан на пустую базу. "
            "Если эти данные уже импортировались раньше, появится ошибка дубликатов.\n\n"
            "Перед запуском лучше очистить базу данных.\n\n"
            "Продолжить импорт?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            report = self.repository.import_multisheet_smart_xlsx(file_path)
        except RepositoryError as exc:
            QMessageBox.critical(
                self,
                "Multi-sheet smart import error",
                str(exc),
            )
            return
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Multi-sheet smart import error",
                f"Unexpected error:\n{exc}",
            )
            return

        QMessageBox.information(
            self,
            "Multi-sheet smart import",
            f"Import finished successfully.\n\n{report}",
        )

        self.repository.refresh()
        self.refresh_all()

    def _show_main_page(self, page: QWidget) -> None:
        self.repository.refresh()
        self.refresh_all()
        self.ui.mainWidget.setCurrentWidget(page)
        if page == self.ui.pageSchedule:
            self.current_route = ("main", "schedule")
        elif page == self.ui.pageGroups:
            self.current_route = ("main", "groups")
        elif page == self.ui.pageSettings:
            current_settings = self.ui.settingsWidget.currentWidget()
            self.current_route = ("settings", self._settings_route_name(current_settings))
        self._sync_nav_state()

    def _show_settings_home(self) -> None:
        self.repository.refresh()
        self.refresh_all()
        self.ui.mainWidget.setCurrentWidget(self.ui.pageSettings)
        self.ui.settingsWidget.setCurrentWidget(self.ui.pageSettingsSchedule)
        self.current_route = ("settings", "schedule")
        self._sync_nav_state()

    def _show_settings_page(self, page: QWidget) -> None:
        self.repository.refresh()
        self.refresh_all()
        self.ui.settingsWidget.setCurrentWidget(page)
        self.current_route = ("settings", self._settings_route_name(page))
        self._sync_nav_state()

    def _settings_route_name(self, page: QWidget) -> str:
        if page == self.ui.pageSettingsGroups:
            return "groups"
        if page == self.ui.pageSettingsStudents:
            return "students"
        if page == self.ui.pageSettingsSemester:
            return "semester"
        return "schedule"

    def _sync_nav_state(self) -> None:
        active_main = {
            self.ui.mainButtonSchedule: self.ui.mainWidget.currentWidget()
            == self.ui.pageSchedule,
            self.ui.mainButtonGroups: self.ui.mainWidget.currentWidget()
            == self.ui.pageGroups,
            self.ui.mainButtonSettings: self.ui.mainWidget.currentWidget()
            == self.ui.pageSettings,
        }
        for button, active in active_main.items():
            self._set_active_property(button, active)

        active_settings = {
            self.ui.settingsAlternativeButtonSchedule: self.ui.settingsWidget.currentWidget()
            == self.ui.pageSettingsSchedule,
            self.ui.settingsAlternativeButtonGroups: self.ui.settingsWidget.currentWidget()
            == self.ui.pageSettingsGroups,
            self.ui.settingsAlternativeButtonStudents: self.ui.settingsWidget.currentWidget()
            == self.ui.pageSettingsStudents,
            self.ui.settingsAlternativeButtonSemester: self.ui.settingsWidget.currentWidget()
            == self.ui.pageSettingsSemester,
        }
        for button, active in active_settings.items():
            self._set_active_property(button, active)

    def _set_active_property(self, widget: QWidget, active: bool) -> None:
        widget.setProperty("active", active)
        widget.style().unpolish(widget)
        widget.style().polish(widget)

    def move_week(self, delta: int) -> None:
        next_week = self.selected_week_start + timedelta(weeks=delta)
        self.selected_week_start = clamp_week_start(next_week, self.semester_settings)
        self.render_schedule()

    def go_to_today(self) -> None:
        self.selected_week_start = clamp_week_start(
            monday_for(date.today()),
            self.semester_settings,
        )
        self.render_schedule()

    def change_semester_week_input(self, delta: int) -> None:
        try:
            current = parse_week_count(
                self.ui.settingsSemesterActionTextBox.text() or "1"
            )
        except ValueError:
            current = self.semester_settings.total_weeks
        current = max(1, min(52, current + delta))
        self.ui.settingsSemesterActionTextBox.setText(str(current))

    def apply_semester_settings(self) -> None:
        try:
            start_date = parse_date_input(
                self.ui.settingsSemesterActionDateTextBox.text()
            )
            total_weeks = parse_week_count(
                self.ui.settingsSemesterActionTextBox.text()
            )
        except ValueError as exc:
            QMessageBox.warning(self, "Semester settings", str(exc))
            return

        if start_date.weekday() != 0:
            QMessageBox.warning(
                self,
                "Semester settings",
                "Semester start date must be a Monday.",
            )
            return

        self.semester_settings = SemesterSettings(start_date, total_weeks)
        self._save_semester_settings()
        self.selected_week_start = clamp_week_start(
            self.selected_week_start,
            self.semester_settings,
        )
        try:
            self.repository.ensure_lessons_for_semester(self.semester_settings)
        except RepositoryError as exc:
            QMessageBox.warning(self, "Semester settings", str(exc))
            return
        self._populate_semester_inputs()
        self.refresh_all()

    def _populate_semester_inputs(self) -> None:
        self.ui.settingsSemesterActionDateTextBox.setText(
            format_input_date(self.semester_settings.start_date)
        )
        self.ui.settingsSemesterActionTextBox.setText(
            str(self.semester_settings.total_weeks)
        )

    def update_semester_info_label(self) -> None:
        self.ui.settingsSemesterTip2Label.setText(
            "Current Semester Information\n\n"
            f"Start Date: {format_long_date(self.semester_settings.start_date)}\n\n"
            f"End Date: {format_long_date(self.semester_settings.end_date)}\n\n"
            f"Total Weeks: {self.semester_settings.total_weeks}"
        )

    def render_schedule(self) -> None:
        week_number = week_number_for(self.selected_week_start, self.semester_settings)
        week_type = week_type_for_number(week_number)

        self.ui.scheduleDateLabelsDateLabelWeek.setText(
            f"Week {week_number}" if week_number else "Outside Semester"
        )
        self.ui.scheduleDateLabelsDateLabelDate.setText(
            format_week_range(self.selected_week_start)
        )
        self.ui.scheduleDateLabelsOddityLabel.setText(week_type_label(week_type))
        self.ui.scheduleDateButtonLeft.setEnabled(
            self.selected_week_start > self.semester_settings.first_week_start
        )
        self.ui.scheduleDateButtonRight.setEnabled(
            self.selected_week_start < self.semester_settings.last_week_start
        )

        clear_layout(self.ui.scheduleLessonsLesson)
        lessons_by_day: dict[int, list[Lesson]] = {index: [] for index in range(7)}
        for lesson in self.repository.lessons_for_week(
            self.selected_week_start,
            week_type,
        ):
            lessons_by_day[lesson.date.weekday()].append(lesson)

        today = date.today()
        for column, day_name in enumerate(DAY_NAMES):
            current_day = self.selected_week_start + timedelta(days=column)
            header = QLabel(f"{day_name.upper()}\n{current_day.day}")
            header.setObjectName(
                "ScheduleDayHeaderActive"
                if current_day == today
                else "ScheduleDayHeader"
            )
            header.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.ui.scheduleLessonsLesson.addWidget(header, 0, column)

            day_container = QWidget()
            day_container.setObjectName("ScheduleDayColumn")
            day_layout = QVBoxLayout(day_container)
            day_layout.setContentsMargins(0, 0, 0, 0)
            day_layout.setSpacing(14)
            day_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

            day_lessons = sorted(
                lessons_by_day[column],
                key=lambda item: item.schedule.time,
            )
            if day_lessons:
                for lesson in day_lessons:
                    card = LessonCard(lesson, self.repository.lesson_groups_text(lesson))
                    card.clicked.connect(self.show_lesson_detail)
                    card.group_clicked.connect(self.show_group_detail)
                    day_layout.addWidget(card)
            else:
                empty = QLabel("No lessons")
                empty.setObjectName("NoLessonsCard")
                empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
                day_layout.addWidget(empty)
            day_layout.addStretch()
            self.ui.scheduleLessonsLesson.addWidget(day_container, 1, column)
            self.ui.scheduleLessonsLesson.setColumnStretch(column, 1)

    def render_groups(self) -> None:
        clear_layout(self.ui.groupsFreeSpace)
        scroll, grid = self._make_scroll_grid()
        groups = self.repository.list_groups()
        columns = self._grid_columns(compact=False)
        self._groups_grid_columns = columns
        for index, group in enumerate(groups):
            card = GroupCard(group, self.repository.group_stats(group))
            card.clicked.connect(self.show_group_detail)
            grid.addWidget(card, index // columns, index % columns)
        for column in range(columns):
            grid.setColumnStretch(column, 1)
        grid.setRowStretch((len(groups) + columns - 1) // columns, 1)
        self._add_single_widget(self.ui.groupsFreeSpace, scroll)

    def render_settings_schedules(self) -> None:
        clear_layout(self.ui.settingsScheduleFreeSpace)
        scroll, layout = self._make_scroll_vbox()
        schedules = sorted(
            self.repository.list_schedules(),
            key=lambda item: (day_index(item.day), item.time),
        )
        for schedule in schedules:
            card = ScheduleTemplateCard(
                schedule,
                self.repository.schedule_groups_text(schedule),
            )
            card.edit_clicked.connect(self.show_schedule_dialog)
            card.delete_clicked.connect(self.delete_schedule)
            layout.addWidget(card)
        layout.addStretch()
        self._add_single_widget(self.ui.settingsScheduleFreeSpace, scroll)

    def render_settings_groups(self) -> None:
        clear_layout(self.ui.settingsGroupsFreeSpace)
        scroll, grid = self._make_scroll_grid()
        groups = self.repository.list_groups()
        columns = self._grid_columns(compact=True)
        self._settings_groups_grid_columns = columns
        for index, group in enumerate(groups):
            card = GroupCard(
                group,
                self.repository.group_stats(group),
                compact=True,
                actions=True,
            )
            card.clicked.connect(self.show_group_detail)
            card.edit_clicked.connect(self.show_group_dialog)
            card.delete_clicked.connect(self.delete_group)
            grid.addWidget(card, index // columns, index % columns)
        for column in range(columns):
            grid.setColumnStretch(column, 1)
        grid.setRowStretch((len(groups) + columns - 1) // columns, 1)
        self._add_single_widget(self.ui.settingsGroupsFreeSpace, scroll)

    def render_settings_students(self) -> None:
        clear_layout(self.ui.settingsStudentsFreeSpace)
        scroll, layout = self._make_scroll_vbox()
        students = self.repository.list_students(self.student_filter_group_id)
        for student in students:
            card = StudentCard(
                student,
                self.repository.full_student_name(student),
                student.group.name,
            )
            card.clicked.connect(self.show_student_detail)
            card.edit_clicked.connect(self.show_student_dialog)
            card.delete_clicked.connect(self.delete_student)
            layout.addWidget(card)
        layout.addStretch()
        self._add_single_widget(self.ui.settingsStudentsFreeSpace, scroll)

    def show_student_filter_menu(self) -> None:
        menu = QMenu(self)
        all_action = menu.addAction("All Groups")
        all_action.triggered.connect(lambda: self.set_student_filter(None, "All Groups"))
        for group in self.repository.list_groups():
            action = menu.addAction(group.name)
            action.triggered.connect(
                lambda checked=False, current=group: self.set_student_filter(
                    current.id,
                    current.name,
                )
            )
        menu.exec(self.ui.settingsStudentsChangeChooseButton.mapToGlobal(
            self.ui.settingsStudentsChangeChooseButton.rect().bottomLeft()
        ))

    def set_student_filter(self, group_id: int | None, label: str) -> None:
        self.student_filter_group_id = group_id
        self.ui.settingsStudentsChangeChooseButton.setText(label)
        self.render_settings_students()

    def _push_current_route(self) -> None:
        if self.current_route is None:
            return
        if self.navigation_history and self.navigation_history[-1] == self.current_route:
            return
        self.navigation_history.append(self.current_route)

    def _go_back(self) -> None:
        if not self.navigation_history:
            self._show_main_page(self.ui.pageSchedule)
            return
        route = self.navigation_history.pop()
        self._restore_route(route)

    def _restore_route(self, route: tuple[str, object | None]) -> None:
        route_type, route_value = route
        if route_type == "lesson" and route_value is not None:
            lesson = self.repository.get_lesson(int(route_value))
            if lesson is not None:
                self.show_lesson_detail(lesson, push_history=False)
                return
        if route_type == "group" and route_value is not None:
            group = self.repository.get_group(int(route_value))
            if group is not None:
                self.show_group_detail(group, push_history=False)
                return
        if route_type == "student" and route_value is not None:
            student = self.repository.get_student(int(route_value))
            if student is not None:
                self.show_student_detail(student, push_history=False)
                return
        if route_type == "settings":
            self._show_main_page(self.ui.pageSettings)
            settings_page = {
                "groups": self.ui.pageSettingsGroups,
                "students": self.ui.pageSettingsStudents,
                "semester": self.ui.pageSettingsSemester,
            }.get(str(route_value), self.ui.pageSettingsSchedule)
            self._show_settings_page(settings_page)
            return
        if route_value == "groups":
            self._show_main_page(self.ui.pageGroups)
            return
        self._show_main_page(self.ui.pageSchedule)

    def show_lesson_detail(self, lesson: Lesson, *, push_history: bool = True) -> None:
        if push_history:
            self._push_current_route()
        current_lesson = self.repository.get_lesson(lesson.id)
        if current_lesson is None:
            QMessageBox.warning(self, "Lesson", "Lesson was not found.")
            return
        lesson = current_lesson

        page = QWidget()
        page.setObjectName("DetailPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(84, 32, 84, 36)
        layout.setSpacing(22)

        back = QPushButton("<  Back")
        back.setObjectName("BackButton")
        back.clicked.connect(self._go_back)
        layout.addWidget(back, alignment=Qt.AlignmentFlag.AlignLeft)

        header = QFrame()
        header.setObjectName("DetailHeader")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(28, 24, 28, 24)
        header_layout.setSpacing(12)

        top = QHBoxLayout()
        title = QLabel(lesson.topic or "Untitled lesson")
        title.setObjectName("DetailTitle")
        title.setWordWrap(True)
        type_label = QLabel(lesson.schedule.type)
        type_label.setObjectName("DarkBadgeLarge")
        type_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        edit_button = QPushButton("Edit")
        edit_button.setObjectName("CardEditButton")
        edit_button.clicked.connect(lambda: self.show_lesson_topic_dialog(lesson))
        top.addWidget(title)
        top.addStretch()
        top.addWidget(type_label)
        top.addWidget(edit_button)

        meta = QLabel(
            f"{format_long_date(lesson.date)} ({DAY_NAMES[lesson.date.weekday()]})  "
            f"{lesson.schedule.time.strftime('%H:%M')}"
        )
        meta.setObjectName("DetailMeta")
        groups = self._make_group_links_label(
            "Groups: ",
            [link.group for link in lesson.schedule.group_links],
        )

        header_layout.addLayout(top)
        header_layout.addWidget(meta)
        header_layout.addWidget(groups)
        layout.addWidget(header)

        summary = self.repository.lesson_attendance_summary(lesson)
        stats = QHBoxLayout()
        stats.setSpacing(18)
        stats.addWidget(make_metric("Total Students", summary["total"], "MetricWhite"))
        stats.addWidget(make_metric("Present", summary["present"], "MetricGreen"))
        stats.addWidget(make_metric("Absent", summary["absent"], "MetricRed"))
        stats.addWidget(make_metric("Attendance Rate", f"{summary['rate']}%", "MetricBlue"))
        layout.addLayout(stats)

        table = self._make_table("Student Details")
        table_layout = table.layout()
        table_layout.addWidget(
            make_table_row(
                ["Student Name", "Group", "Attendance", "Comment", "Score", "Actions"],
                "TableHeader",
            )
        )
        for student in self.repository.students_for_lesson(lesson):
            table_layout.addWidget(self._make_lesson_student_row(lesson, student))
        layout.addWidget(table)
        layout.addStretch()
        self.current_route = ("lesson", lesson.id)
        self._show_detail_page(page)

    def show_group_detail(self, group: Group, *, push_history: bool = True) -> None:
        if push_history:
            self._push_current_route()
        current_group = self.repository.get_group(group.id)
        if current_group is None:
            QMessageBox.warning(self, "Group", "Group was not found.")
            return
        group = current_group

        page = QWidget()
        page.setObjectName("DetailPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(84, 32, 84, 36)
        layout.setSpacing(22)

        back = QPushButton("<  Back")
        back.setObjectName("BackButton")
        back.clicked.connect(self._go_back)
        layout.addWidget(back, alignment=Qt.AlignmentFlag.AlignLeft)

        header = QFrame()
        header.setObjectName("DetailHeader")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(28, 24, 28, 24)
        title = QLabel(f"Group {group.name}")
        title.setObjectName("DetailTitle")
        subtitle = QLabel(f"{len(group.students)} students")
        subtitle.setObjectName("DetailMeta")
        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)
        layout.addWidget(header)

        stats_data = self.repository.group_stats(group)
        stats = QHBoxLayout()
        stats.setSpacing(18)
        stats.addWidget(make_metric("Group Average", stats_data["overall"], "MetricBlue"))
        stats.addWidget(make_metric("Lab Work Average", stats_data["lab"], "MetricGreen"))
        stats.addWidget(make_metric("Test Average", stats_data["test"], "MetricRed"))
        stats.addWidget(make_metric("Attendance Rate", f"{stats_data['attendance']}%", "MetricPurple"))
        layout.addLayout(stats)

        table = self._make_table("Students")
        table_layout = table.layout()
        table_layout.addWidget(
            make_table_row(
                ["Name", "Overall Average", "Lab Average", "Test Average", "Attendance", "Actions"],
                "TableHeader",
            )
        )
        for student in sorted(group.students, key=lambda item: (item.surname, item.first_name)):
            stats = self.repository.student_stats(student)
            name = make_link_button(self.repository.full_student_name(student))
            name.clicked.connect(lambda checked=False, current=student: self.show_student_detail(current))
            profile = make_link_button("View Profile")
            profile.clicked.connect(lambda checked=False, current=student: self.show_student_detail(current))
            table_layout.addWidget(
                make_table_row(
                    [
                        name,
                        stats["overall"],
                        stats["lab"],
                        stats["test"],
                        f"{stats['attendance']}%",
                        profile,
                    ]
                )
            )
        layout.addWidget(table)

        lessons_box = self._make_table("Group Lessons")
        lessons_layout = lessons_box.layout()
        for link in sorted(
            group.schedule_links,
            key=lambda item: (day_index(item.schedule.day), item.schedule.time),
        ):
            schedule = link.schedule
            held_count = sum(1 for lesson in schedule.lessons if lesson.date <= date.today())
            lessons_layout.addWidget(
                self._make_group_lesson_row(
                    schedule,
                    held_count,
                )
            )
        layout.addWidget(lessons_box)
        self.current_route = ("group", group.id)
        self._show_detail_page(page)

    def _make_group_lesson_row(
        self,
        schedule: Schedule,
        held_count: int,
    ) -> QFrame:
        row = QFrame()
        row.setObjectName("SettingsCard")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(22, 16, 22, 16)
        text = QVBoxLayout()
        title = QLabel(
            f"{schedule.day} {schedule.time.strftime('%H:%M')}  {schedule.type}"
        )
        title.setObjectName("SettingsCardTitle")
        info = QLabel(
            f"{schedule.time.strftime('%H:%M')} on {schedule.day}s "
            f"({schedule.odd_or_even} weeks)"
        )
        info.setObjectName("SettingsCardSubtitle")
        text.addWidget(title)
        text.addWidget(info)
        text.addWidget(self._make_lesson_date_strip(schedule))

        lessons = sorted(schedule.lessons, key=lambda item: item.date)
        if lessons:
            selected_lesson = next(
                (lesson for lesson in lessons if lesson.date >= date.today()),
                lessons[-1],
            )
            open_button = QPushButton("Open lesson")
            open_button.setObjectName("CardEditButton")
            open_button.clicked.connect(
                lambda checked=False, current=selected_lesson: self.show_lesson_detail(current)
            )
        else:
            open_button = QLabel("No lessons")
            open_button.setObjectName("SettingsCardSubtitle")

        badge = QLabel(f"{held_count} lessons held")
        badge.setObjectName("DarkBadge")
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setFixedWidth(130)
        layout.addLayout(text)
        layout.addStretch()
        layout.addWidget(open_button)
        layout.addWidget(badge)
        return row

    def _make_lesson_date_strip(self, schedule: Schedule) -> QWidget:
        lessons = sorted(schedule.lessons, key=lambda item: item.date)
        if not lessons:
            empty = QLabel("No generated lessons yet")
            empty.setObjectName("SettingsCardText")
            return empty

        scroll = QScrollArea()
        scroll.setObjectName("LessonDateScroll")
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFixedHeight(82)

        body = QWidget()
        body.setObjectName("LessonDateScrollBody")
        layout = QHBoxLayout(body)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        for lesson in lessons:
            button = QPushButton(
                f"{lesson.date.strftime('%b %d')}\n{lesson.topic or 'Untitled lesson'}"
            )
            button.setObjectName("LessonDateButton")
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(
                lambda checked=False, current=lesson: self.show_lesson_detail(current)
            )
            layout.addWidget(button)
        layout.addStretch()
        scroll.setWidget(body)
        return scroll

    def show_student_detail(self, student: Student, *, push_history: bool = True) -> None:
        if push_history:
            self._push_current_route()
        current_student = self.repository.get_student(student.id)
        if current_student is None:
            QMessageBox.warning(self, "Student", "Student was not found.")
            return
        student = current_student

        page = QWidget()
        page.setObjectName("DetailPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(84, 32, 84, 36)
        layout.setSpacing(22)

        back = QPushButton("<  Back")
        back.setObjectName("BackButton")
        back.clicked.connect(self._go_back)
        layout.addWidget(back, alignment=Qt.AlignmentFlag.AlignLeft)

        header = QFrame()
        header.setObjectName("DetailHeader")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(28, 24, 28, 24)
        header_layout.setSpacing(12)

        title = QLabel(self.repository.full_student_name(student))
        title.setObjectName("DetailTitle")
        group_link = self._make_group_links_label("Group: ", [student.group])
        email = QLabel(f"Email: {student.bmstu_email or '-'}")
        email.setObjectName("DetailMeta")

        header_layout.addWidget(title)
        header_layout.addWidget(group_link)
        header_layout.addWidget(email)
        layout.addWidget(header)

        stats_data = self.repository.student_stats(student)
        stats = QHBoxLayout()
        stats.setSpacing(18)
        stats.addWidget(make_metric("Overall Average", stats_data["overall"], "MetricBlue"))
        stats.addWidget(make_metric("Lab Average", stats_data["lab"], "MetricGreen"))
        stats.addWidget(make_metric("Test Average", stats_data["test"], "MetricRed"))
        stats.addWidget(make_metric("Attendance", f"{stats_data['attendance']}%", "MetricPurple"))
        layout.addLayout(stats)

        records = self._make_table("Lesson Records")
        records_layout = records.layout()
        records_layout.addWidget(
            make_table_row(
                ["Date", "Lesson", "Type", "Attendance", "Score", "Comment"],
                "TableHeader",
            )
        )
        lessons = self.repository.lessons_for_student(student)
        if lessons:
            for lesson in lessons:
                records_layout.addWidget(self._make_student_lesson_row(student, lesson))
        else:
            empty = QLabel("No lessons for this student yet.")
            empty.setObjectName("SettingsCardSubtitle")
            records_layout.addWidget(empty)
        layout.addWidget(records)
        layout.addStretch()
        self.current_route = ("student", student.id)
        self._show_detail_page(page)

    def _make_lesson_student_row(self, lesson: Lesson, student: Student) -> QFrame:
        attendance = self.repository.attendance_for(lesson, student)
        comment = self.repository.comment_for(lesson, student)
        mark = self.repository.mark_for(lesson, student)

        student_button = make_link_button(self.repository.full_student_name(student))
        student_button.clicked.connect(
            lambda checked=False, current=student: self.show_student_detail(current)
        )

        group_button = make_link_button(student.group.name)
        group_button.clicked.connect(
            lambda checked=False, current=student.group: self.show_group_detail(current)
        )

        attendance_input = QCheckBox("Present")
        attendance_input.setObjectName("InlineCheckBox")
        attendance_input.setChecked(attendance is not None and attendance.is_visited)

        comment_input = QLineEdit(comment.data if comment is not None and comment.data else "")
        comment_input.setObjectName("InlineTextInput")
        comment_input.setPlaceholderText("Comment")
        comment_input.setMinimumWidth(220)

        mark_input = QLineEdit(str(mark.data) if mark is not None else "")
        mark_input.setObjectName("ScoreInput")
        mark_input.setPlaceholderText("0-100")
        mark_input.setMaxLength(3)
        mark_input.setEnabled(lesson.schedule.is_assessment)
        if not lesson.schedule.is_assessment:
            mark_input.setText("-")

        actions = QWidget()
        actions_layout = QHBoxLayout(actions)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(8)
        profile_button = make_link_button("Profile")
        profile_button.clicked.connect(
            lambda checked=False, current=student: self.show_student_detail(current)
        )
        actions_layout.addWidget(profile_button)

        save_current_row = (
            lambda *args, current_lesson=lesson, current_student=student: (
                self._save_lesson_student_result(
                    current_lesson,
                    current_student,
                    attendance_input,
                    comment_input,
                    mark_input,
                )
            )
        )
        attendance_input.toggled.connect(save_current_row)
        comment_input.editingFinished.connect(save_current_row)
        mark_input.editingFinished.connect(save_current_row)

        return make_table_row(
            [
                student_button,
                group_button,
                attendance_input,
                comment_input,
                mark_input,
                actions,
            ]
        )

    def _make_student_lesson_row(self, student: Student, lesson: Lesson) -> QFrame:
        attendance = self.repository.attendance_for(lesson, student)
        mark = self.repository.mark_for(lesson, student)
        comment = self.repository.comment_for(lesson, student)

        lesson_button = make_link_button(lesson.topic or "Untitled lesson")
        lesson_button.clicked.connect(
            lambda checked=False, current=lesson: self.show_lesson_detail(current)
        )

        return make_table_row(
            [
                format_short_date(lesson.date),
                lesson_button,
                lesson.schedule.type,
                "Present" if attendance is not None and attendance.is_visited else "Not set",
                mark.data if mark is not None else "-",
                comment.data if comment is not None and comment.data else "-",
            ]
        )

    def _save_lesson_student_result(
        self,
        lesson: Lesson,
        student: Student,
        attendance_input: QCheckBox,
        comment_input: QLineEdit,
        mark_input: QLineEdit,
    ) -> None:
        mark_value: int | None = None
        if lesson.schedule.is_assessment:
            mark_text = mark_input.text().strip()
            if mark_text:
                try:
                    mark_value = int(mark_text)
                except ValueError:
                    QMessageBox.warning(self, "Lesson", "Score must be a number from 0 to 100.")
                    return
                if mark_value < 0 or mark_value > 100:
                    QMessageBox.warning(self, "Lesson", "Score must be between 0 and 100.")
                    return

        try:
            self.repository.save_lesson_student_record(
                lesson,
                student,
                attended=attendance_input.isChecked(),
                comment_text=comment_input.text(),
                mark_value=mark_value,
            )
        except RepositoryError as exc:
            QMessageBox.warning(self, "Lesson", str(exc))
            return
        self.repository.refresh()

    def _show_students_settings_page(self) -> None:
        self._show_main_page(self.ui.pageSettings)
        self._show_settings_page(self.ui.pageSettingsStudents)

    def _make_group_links_label(self, prefix: str, groups: list[Group]) -> QLabel:
        label = QLabel()
        label.setObjectName("DetailMeta")
        label.setTextFormat(Qt.TextFormat.RichText)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        label.setOpenExternalLinks(False)
        label.setWordWrap(True)
        if groups:
            links = ", ".join(
                f'<a href="{group.id}">{escape(group.name)}</a>'
                for group in sorted(groups, key=lambda item: item.name)
            )
            label.setText(f"{escape(prefix)}{links}")
            label.linkActivated.connect(self._show_group_by_id)
        else:
            label.setText(f"{escape(prefix)}No groups")
        return label

    def _show_group_by_id(self, group_id: str) -> None:
        try:
            group = self.repository.get_group(int(group_id))
        except ValueError:
            group = None
        if group is not None:
            self.show_group_detail(group)

    def _show_detail_page(self, page: QWidget) -> None:
        page.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        scroll = QScrollArea()
        scroll.setObjectName("DetailScroll")
        scroll.setWidgetResizable(True)
        scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        scroll.setWidget(page)

        if self.detail_page is not None:
            self.ui.mainWidget.removeWidget(self.detail_page)
            self.detail_page.deleteLater()
        self.detail_page = scroll
        self.ui.mainWidget.addWidget(scroll)
        self.ui.mainWidget.setCurrentWidget(scroll)
        self._sync_nav_state()

    def show_lesson_topic_dialog(self, lesson: Lesson) -> None:
        current_lesson = self.repository.get_lesson(lesson.id)
        if current_lesson is None:
            QMessageBox.warning(self, "Lesson", "Lesson was not found.")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Lesson topic")
        form = QFormLayout(dialog)
        topic_input = QLineEdit(current_lesson.topic or "")
        form.addRow("Topic", topic_input)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        form.addRow(buttons)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        try:
            self.repository.update_lesson_topic(current_lesson, topic_input.text())
        except RepositoryError as exc:
            QMessageBox.warning(self, "Lesson", str(exc))
            return
        self.refresh_all()
        refreshed_lesson = self.repository.get_lesson(current_lesson.id)
        if refreshed_lesson is not None:
            self.show_lesson_detail(refreshed_lesson, push_history=False)

    def show_schedule_dialog(self, schedule: Schedule | None = None) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Schedule Template")
        form = QFormLayout(dialog)

        day_input = QComboBox()
        day_input.addItems(DAY_NAMES)
        time_input = QTimeEdit()
        time_input.setDisplayFormat("HH:mm")
        week_input = QComboBox()
        week_input.addItems(["even", "odd"])
        type_input = QComboBox()
        type_input.addItems(["Seminar", "Lab Work", "Control Work"])
        assessment_input = QCheckBox("Assessment lesson")
        group_input = QListWidget()
        group_input.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)

        groups = self.repository.list_groups()
        selected_group_ids = set()
        if schedule is not None:
            day_input.setCurrentText(schedule.day)
            time_input.setTime(QTime(schedule.time.hour, schedule.time.minute))
            week_input.setCurrentText(schedule.odd_or_even)
            type_input.setCurrentText(schedule.type)
            assessment_input.setChecked(schedule.is_assessment)
            selected_group_ids = {link.group_id for link in schedule.group_links}

        for group in groups:
            item = QListWidgetItem(group.name)
            item.setData(Qt.ItemDataRole.UserRole, group)
            if group.id in selected_group_ids:
                item.setSelected(True)
            group_input.addItem(item)

        form.addRow("Day", day_input)
        form.addRow("Time", time_input)
        form.addRow("Week", week_input)
        form.addRow("Type", type_input)
        form.addRow("", assessment_input)
        form.addRow("Groups", group_input)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        form.addRow(buttons)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        selected_groups = [
            item.data(Qt.ItemDataRole.UserRole)
            for item in group_input.selectedItems()
        ]
        if not selected_groups:
            QMessageBox.warning(self, "Schedule Template", "Select at least one group.")
            return

        lesson_time = time(time_input.time().hour(), time_input.time().minute())
        try:
            if schedule is None:
                self.repository.create_schedule(
                    None,
                    selected_groups,
                    day_input.currentText(),
                    lesson_time,
                    week_input.currentText(),
                    type_input.currentText(),
                    assessment_input.isChecked(),
                    self.semester_settings,
                )
            else:
                self.repository.update_schedule(
                    schedule,
                    None,
                    selected_groups,
                    day_input.currentText(),
                    lesson_time,
                    week_input.currentText(),
                    type_input.currentText(),
                    assessment_input.isChecked(),
                    self.semester_settings,
                )
        except RepositoryError as exc:
            QMessageBox.warning(self, "Schedule Template", str(exc))
            return
        self.refresh_all()

    def delete_schedule(self, schedule: Schedule) -> None:
        if self._confirm("Delete schedule template?"):
            try:
                self.repository.delete_schedule(schedule)
            except RepositoryError as exc:
                QMessageBox.warning(self, "Schedule Template", str(exc))
                return
            self.refresh_all()

    def show_group_dialog(self, group: Group | None = None) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Group")
        form = QFormLayout(dialog)
        name_input = QLineEdit(group.name if group is not None else "")
        speciality_input = QLineEdit(group.speciality or "" if group is not None else "")
        form.addRow("Name", name_input)
        form.addRow("Speciality", speciality_input)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        form.addRow(buttons)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        if not name_input.text().strip():
            QMessageBox.warning(self, "Group", "Group name is required.")
            return
        try:
            if group is None:
                self.repository.create_group(name_input.text(), speciality_input.text())
            else:
                self.repository.update_group(group, name_input.text(), speciality_input.text())
        except RepositoryError as exc:
            QMessageBox.warning(self, "Group", str(exc))
            return
        self.refresh_all()

    def delete_group(self, group: Group) -> None:
        if self._confirm(f"Delete group {group.name}?"):
            try:
                self.repository.delete_group(group)
            except RepositoryError as exc:
                QMessageBox.warning(self, "Group", str(exc))
                return
            self.refresh_all()

    def show_student_dialog(self, student: Student | None = None) -> None:
        groups = self.repository.list_groups()
        if not groups:
            QMessageBox.warning(self, "Student", "Create a group first.")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Student")
        form = QFormLayout(dialog)
        group_input = QComboBox()
        for group in groups:
            group_input.addItem(group.name, group)
        first_name_input = QLineEdit(student.first_name if student is not None else "")
        surname_input = QLineEdit(student.surname if student is not None else "")
        email_input = QLineEdit(student.bmstu_email or "" if student is not None else "")

        if student is not None:
            for index in range(group_input.count()):
                if group_input.itemData(index).id == student.group_id:
                    group_input.setCurrentIndex(index)
                    break

        form.addRow("Group", group_input)
        form.addRow("First Name", first_name_input)
        form.addRow("Surname", surname_input)
        form.addRow("Email", email_input)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        form.addRow(buttons)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        if not first_name_input.text().strip() or not surname_input.text().strip():
            QMessageBox.warning(self, "Student", "First name and surname are required.")
            return
        group = group_input.currentData()
        try:
            if student is None:
                self.repository.create_student(
                    group,
                    first_name_input.text(),
                    surname_input.text(),
                    email_input.text(),
                )
            else:
                self.repository.update_student(
                    student,
                    group,
                    first_name_input.text(),
                    surname_input.text(),
                    email_input.text(),
                )
            self.repository.ensure_attendance_and_marks()
        except RepositoryError as exc:
            QMessageBox.warning(self, "Student", str(exc))
            return
        self.refresh_all()

    def delete_student(self, student: Student) -> None:
        if self._confirm(f"Delete student {self.repository.full_student_name(student)}?"):
            try:
                self.repository.delete_student(student)
            except RepositoryError as exc:
                QMessageBox.warning(self, "Student", str(exc))
                return
            self.refresh_all()

    def _confirm(self, text: str) -> bool:
        return (
            QMessageBox.question(
                self,
                "Confirm",
                text,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            == QMessageBox.StandardButton.Yes
        )

    def export_database(self) -> None:
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export database",
            str(Path.cwd() / "digital_diary_export.xlsx"),
            "Excel files (*.xlsx)",
        )
        if not file_path:
            return
        try:
            exported_path = self.repository.export_to_xlsx(file_path)
        except (RepositoryError, ValueError) as exc:
            QMessageBox.warning(self, "Export database", str(exc))
            return
        QMessageBox.information(
            self,
            "Export database",
            f"Database exported to:\n{exported_path}",
        )

    def show_import_dialog(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Import database",
            str(Path.cwd()),
            "Excel files (*.xlsx)",
        )
        if not file_path:
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Import database")
        form = QFormLayout(dialog)

        path_input = QLineEdit(file_path)
        path_input.setReadOnly(True)

        strategy_input = QComboBox()
        strategy_input.addItem("Standard exported workbook", "standard")
        strategy_input.addItem("Smart groups/students search", "smart")
        strategy_input.addItem("Template table search", "template")

        form.addRow("File", path_input)
        form.addRow("Strategy", strategy_input)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        form.addRow(buttons)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        strategy = strategy_input.currentData()
        try:
            preview = self.repository.preview_import_from_xlsx(
                file_path,
                strategy=strategy,
                mode="merge",
            )
        except (RepositoryError, ValueError) as exc:
            QMessageBox.warning(self, "Import database", str(exc))
            return

        if preview.errors:
            QMessageBox.warning(
                self,
                "Import database",
                "\n".join(preview.errors[:8]),
            )
            return

        if not self._confirm_import_preview(preview):
            return

        try:
            counts = self.repository.import_from_preview(preview)
        except RepositoryError as exc:
            QMessageBox.warning(self, "Import database", str(exc))
            return
        self.refresh_all()
        QMessageBox.information(
            self,
            "Import database",
            "Imported rows:\n" + self._format_counts(counts),
        )

    def _confirm_import_preview(self, preview: ImportPreview) -> bool:
        text = self._format_import_preview(preview)
        return (
            QMessageBox.question(
                self,
                "Confirm import",
                text,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            == QMessageBox.StandardButton.Yes
        )

    @staticmethod
    def _format_counts(counts: dict[str, int]) -> str:
        if not counts:
            return "No new rows were imported."
        return "\n".join(f"{name}: {count}" for name, count in counts.items())

    def _format_import_preview(self, preview: ImportPreview) -> str:
        lines = [
            f"File: {preview.source_path}",
            f"Strategy: {preview.strategy}",
            (
                "Mode: replace current database"
                if preview.mode == "replace"
                else "Mode: merge and update existing rows"
            ),
            "",
            "Rows to import:",
        ]
        if preview.row_counts:
            lines.extend(
                f"{sheet_name}: {count}"
                for sheet_name, count in preview.row_counts.items()
            )
        else:
            lines.append("No rows")
        if preview.warnings:
            lines.extend(["", "Warnings:"])
            lines.extend(preview.warnings[:6])
        if preview.mode == "replace":
            lines.extend(["", "Current database will be cleared before import."])
        lines.extend(["", "Continue?"])
        return "\n".join(lines)

    def toggle_theme(self) -> None:
        self.current_theme = "dark" if self.current_theme == "light" else "light"
        self.settings_store.setValue("ui/theme", self.current_theme)
        self.settings_store.sync()
        self._update_theme_button_text()
        self._apply_styles()

    def _update_theme_button_text(self) -> None:
        if hasattr(self.ui, "action_4"):
            next_theme = "dark" if self.current_theme == "light" else "light"
            self.ui.action_4.setText(f"Switch to {next_theme} theme")

    def _theme_path(self, theme_name: str) -> Path:
        return Path(__file__).resolve().parents[1] / "themes" / f"{theme_name}.qss"

    def _make_table(self, title: str) -> QFrame:
        frame = QFrame()
        frame.setObjectName("DetailTable")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(10)
        label = QLabel(title)
        label.setObjectName("SectionTitle")
        layout.addWidget(label)
        return frame

    def _grid_columns(self, *, compact: bool) -> int:
        width = max(self.width(), self.ui.mainWidget.width())
        if width < 1200:
            return 1
        if compact and width >= 1700:
            return 3
        return 2

    def _make_scroll_vbox(self) -> tuple[QScrollArea, QVBoxLayout]:
        scroll = QScrollArea()
        scroll.setObjectName("ContentScroll")
        scroll.setWidgetResizable(True)
        scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        content = QWidget()
        content.setObjectName("ContentScrollBody")
        content.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 4, 0)
        layout.setSpacing(14)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(content)
        return scroll, layout

    def _make_scroll_grid(self) -> tuple[QScrollArea, QGridLayout]:
        scroll = QScrollArea()
        scroll.setObjectName("ContentScroll")
        scroll.setWidgetResizable(True)
        scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        content = QWidget()
        content.setObjectName("ContentScrollBody")
        content.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        layout = QGridLayout(content)
        layout.setContentsMargins(0, 0, 4, 0)
        layout.setHorizontalSpacing(20)
        layout.setVerticalSpacing(20)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(content)
        return scroll, layout

    def _add_single_widget(self, layout, widget: QWidget) -> None:
        if isinstance(layout, QFormLayout):
            layout.addRow(widget)
        else:
            layout.addWidget(widget)

    def _apply_styles(self) -> None:
        theme_path = self._theme_path(self.current_theme)
        if theme_path.exists():
            self.setStyleSheet(theme_path.read_text(encoding="utf-8"))
            return

        self.setStyleSheet(
            """
            QWidget {
                background-color: #ffffff;
                color: #07152d;
                font-family: "Segoe UI";
                font-size: 16px;
            }

            QMainWindow,
            QWidget#sourceWidget {
                background-color: #ffffff;
            }

            QStackedWidget#mainWidget,
            QWidget#pageSchedule,
            QWidget#pageGroups,
            QWidget#pageSettings,
            QWidget#DetailPage {
                background-color: #eaf2ff;
            }

            QStackedWidget#settingsWidget,
            QWidget#pageSettingsSchedule,
            QWidget#pageSettingsGroups,
            QWidget#pageSettingsStudents,
            QWidget#pageSettingsSemester {
                background: transparent;
            }

            QLabel {
                color: #07152d;
                background: transparent;
                font-size: 18px;
                font-weight: 400;
            }

            QPushButton {
                background-color: #e4e7ec;
                color: #1d2d46;
                border: none;
                border-radius: 8px;
                padding: 10px 18px;
                min-height: 42px;
                font-size: 17px;
            }

            QPushButton:hover {
                background-color: #d9dee7;
            }

            QPushButton#mainButtonSchedule,
            QPushButton#mainButtonGroups,
            QPushButton#mainButtonSettings {
                background-color: #e3e6eb;
                color: #1b2c46;
                min-height: 96px;
                font-size: 26px;
                border-radius: 8px;
            }

            QPushButton#mainButtonSchedule[active="true"],
            QPushButton#mainButtonGroups[active="true"],
            QPushButton#mainButtonSettings[active="true"] {
                background-color: #1f5cf4;
                color: #ffffff;
            }

            QPushButton#scheduleDateButtonLeft,
            QPushButton#scheduleDateButtonRight,
            QPushButton#scheduleDateButtonToday,
            QPushButton#BackButton {
                background-color: #ffffff;
                color: #050b18;
                border: 1px solid #dce1ea;
                min-height: 38px;
                font-size: 16px;
            }

            QPushButton#scheduleDateButtonLeft:disabled,
            QPushButton#scheduleDateButtonRight:disabled {
                color: #a0a9b8;
                background-color: #f7f8fb;
            }

            QLabel#scheduleDateLabelsDateLabelWeek {
                color: #284164;
                font-size: 16px;
            }

            QLabel#scheduleDateLabelsDateLabelDate {
                color: #000000;
                font-size: 24px;
            }

            QLabel#scheduleDateLabelsOddityLabel {
                background-color: #030416;
                color: #ffffff;
                border-radius: 9px;
                padding: 18px 30px;
                font-size: 22px;
            }

            QLabel#ScheduleDayHeader,
            QLabel#ScheduleDayHeaderActive {
                background-color: #ffffff;
                color: #213652;
                border: 1px solid #dfe4ec;
                border-radius: 10px;
                padding: 14px;
                min-height: 82px;
                font-size: 18px;
            }

            QLabel#ScheduleDayHeaderActive {
                background-color: #1f5cf4;
                color: #ffffff;
                border-color: #1f5cf4;
                font-weight: 700;
            }

            QWidget#ScheduleDayColumn {
                background: transparent;
            }

            QLabel#NoLessonsCard {
                background-color: #f4f7fd;
                color: #8b97aa;
                border: 1px solid #dfe4ec;
                border-radius: 10px;
                padding: 18px;
                min-height: 64px;
            }

            QFrame#LessonCard,
            QFrame#SettingsCard,
            QFrame#DetailHeader,
            QFrame#DetailTable {
                background-color: #ffffff;
                border: 1px solid #d8e0ec;
                border-radius: 10px;
            }

            QFrame#GroupCard,
            QFrame#GroupCardCompact {
                background-color: #fffaf0;
                border: 1px solid #e3d2ac;
                border-radius: 10px;
            }

            QFrame#GroupCardCompact {
                background-color: #fffdf7;
            }

            QFrame#LessonCard:hover,
            QFrame#GroupCard:hover,
            QFrame#GroupCardCompact:hover {
                border-color: #c9ad71;
            }

            QLabel#LessonCardTime {
                color: #07152d;
                font-size: 24px;
                font-weight: 700;
            }

            QLabel#LessonCardGroups,
            QLabel#LinkLabel {
                color: #075cff;
                font-size: 17px;
            }

            QLabel#LessonCardTopic {
                color: #10213a;
                font-size: 18px;
            }

            QLabel#LessonCardType,
            QLabel#SmallPill {
                background-color: #ffffff;
                color: #050b18;
                border: 1px solid #dfe4ec;
                border-radius: 8px;
                padding: 4px 10px;
                font-size: 14px;
            }

            QLabel#groupsTip1,
            QLabel#settingsCurrentLabelTip1,
            QLabel#settingsScheduleChangeLabelTip1,
            QLabel#settingsGroupsChangeLabelTip1,
            QLabel#settingsStudentsChangeLabelTip1,
            QLabel#settingsSemesterTip1Label {
                color: #07152d;
                font-size: 30px;
            }

            QLabel#groupsTip2,
            QLabel#settingsCurrentLabelTip2,
            QLabel#settingsSemesterActionDateLabelTip2,
            QLabel#settingsSemesterActionLabelTip2,
            QLabel#settingsSemesterTip2Label {
                color: #33445f;
                font-size: 18px;
            }

            QLabel#settingsSemesterActionDateLabelTip1,
            QLabel#settingsSemesterActionLabelTip1 {
                color: #07152d;
                font-size: 20px;
            }

            QPushButton#settingsAlternativeButtonSchedule,
            QPushButton#settingsAlternativeButtonGroups,
            QPushButton#settingsAlternativeButtonStudents,
            QPushButton#settingsAlternativeButtonSemester {
                background-color: #e8e8ec;
                color: #050b18;
                min-height: 46px;
                font-size: 18px;
                border-radius: 8px;
            }

            QPushButton#settingsAlternativeButtonSchedule[active="true"],
            QPushButton#settingsAlternativeButtonGroups[active="true"],
            QPushButton#settingsAlternativeButtonStudents[active="true"],
            QPushButton#settingsAlternativeButtonSemester[active="true"] {
                background-color: #ffffff;
                color: #050b18;
            }

            QPushButton#settingsScheduleChangeActionButton,
            QPushButton#settingsGroupsChangeActionButton,
            QPushButton#settingsStudentsChangeActionButton,
            QPushButton#settingsSemesterActionSaveButton,
            QPushButton#settingsSemesterActionWeekChangeButtonIncrease,
            QPushButton#settingsSemesterActionWeekChangeButtonDecrease {
                background-color: #030416;
                color: #ffffff;
                border-radius: 8px;
                min-height: 40px;
                font-size: 16px;
            }

            QPushButton#settingsSemesterActionWeekChangeButtonIncrease,
            QPushButton#settingsSemesterActionWeekChangeButtonDecrease {
                min-width: 48px;
                max-width: 58px;
                font-size: 24px;
            }

            QPushButton#CardEditButton {
                background-color: #ffffff;
                color: #050b18;
                border: 1px solid #dfe4ec;
                min-width: 70px;
                font-size: 14px;
            }

            QPushButton#CardDeleteButton {
                background-color: #ffffff;
                color: #e11d48;
                border: 1px solid #f2c8d1;
                min-width: 76px;
                font-size: 14px;
            }

            QPushButton#LinkButton {
                background: transparent;
                color: #075cff;
                border: none;
                padding: 0;
                min-height: 24px;
                font-size: 16px;
                text-align: left;
            }

            QPushButton#LinkButton:hover {
                color: #003fbd;
                text-decoration: underline;
            }

            QPushButton#PrimarySmallButton {
                background-color: #030416;
                color: #ffffff;
                border-radius: 8px;
                padding: 4px 12px;
                min-height: 28px;
                font-size: 14px;
            }

            QTextEdit,
            QLineEdit,
            QComboBox,
            QTimeEdit,
            QListWidget {
                background-color: #ffffff;
                color: #07152d;
                border: 1px solid #dce1ea;
                border-radius: 8px;
                padding: 8px;
                font-size: 16px;
                min-height: 34px;
            }

            QLineEdit#InlineTextInput,
            QLineEdit#ScoreInput {
                min-height: 28px;
                padding: 5px 8px;
                font-size: 14px;
            }

            QLineEdit#ScoreInput {
                max-width: 72px;
            }

            QCheckBox#InlineCheckBox {
                background: transparent;
                color: #07152d;
                font-size: 15px;
                spacing: 8px;
            }

            QTextEdit#settingsSemesterActionDateTextBox,
            QTextEdit#settingsSemesterActionTextBox {
                max-height: 44px;
            }

            QScrollArea#ContentScroll,
            QScrollArea#DetailScroll {
                background: transparent;
                border: none;
            }

            QWidget#ContentScrollBody {
                background: transparent;
            }

            QLabel#RoundIcon,
            QLabel#RoundIconMuted {
                background-color: #e4f7ef;
                color: #087f5b;
                border-radius: 27px;
                font-size: 20px;
                font-weight: 700;
            }

            QLabel#RoundIconMuted {
                background-color: #f0f2f6;
                color: #556070;
            }

            QLabel#GroupCardTitle,
            QLabel#SettingsCardTitle {
                color: #050b18;
                font-size: 24px;
            }

            QLabel#GroupCardSubtitle,
            QLabel#SettingsCardSubtitle,
            QLabel#SettingsCardText,
            QLabel#DetailMeta {
                color: #2b3d58;
                font-size: 16px;
            }

            QLabel#CardArrow {
                color: #98a2b3;
                font-size: 34px;
            }

            QLabel#DarkBadge,
            QLabel#DarkBadgeLarge {
                background-color: #030416;
                color: #ffffff;
                border-radius: 8px;
                padding: 5px 10px;
                font-size: 14px;
            }

            QLabel#DarkBadgeLarge {
                font-size: 16px;
                min-width: 96px;
                min-height: 34px;
            }

            QFrame#MetricBlue,
            QFrame#MetricGreen,
            QFrame#MetricRed,
            QFrame#MetricPurple,
            QFrame#MetricWhite {
                border-radius: 10px;
                border: 1px solid #d6e1f2;
                min-height: 110px;
            }

            QFrame#MetricBlue { background-color: #e7f1ff; }
            QFrame#MetricGreen { background-color: #e9faef; }
            QFrame#MetricRed { background-color: #fff0f0; }
            QFrame#MetricPurple { background-color: #f6edff; }
            QFrame#MetricWhite { background-color: #ffffff; }

            QLabel#MetricTitle {
                color: #33445f;
                font-size: 16px;
            }

            QLabel#MetricValue {
                color: #0f4eea;
                font-size: 34px;
            }

            QLabel#DetailTitle {
                color: #050b18;
                font-size: 36px;
            }

            QLabel#SectionTitle {
                color: #050b18;
                font-size: 26px;
                padding-bottom: 20px;
            }

            QFrame#TableHeader QLabel {
                color: #050b18;
                font-size: 18px;
                font-weight: 700;
            }

            QFrame#TableRow {
                background-color: #ffffff;
                border-top: 1px solid #e5e7eb;
            }

            QFrame#TableRow QLabel {
                font-size: 16px;
            }
            """
        )

    def _apply_layout_visuals(self) -> None:
        ui = self.ui

        ui.verticalLayout_2.setContentsMargins(0, 0, 0, 0)
        ui.verticalLayout_2.setSpacing(0)
        ui.mainLayout.setContentsMargins(0, 0, 0, 0)
        ui.mainLayout.setSpacing(0)
        ui.mainLayout.setStretch(0, 0)
        ui.mainLayout.setStretch(1, 1)

        ui.mainButtons.setContentsMargins(104, 48, 104, 28)
        ui.mainButtons.setSpacing(18)

        ui.verticalLayout_3.setContentsMargins(0, 0, 0, 0)
        ui.mainSchedule.setContentsMargins(120, 30, 120, 24)
        ui.mainSchedule.setSpacing(28)
        ui.mainSchedule.setStretch(0, 0)
        ui.mainSchedule.setStretch(1, 1)

        ui.scheduleDate.setContentsMargins(30, 28, 30, 28)
        ui.scheduleDate.setSpacing(24)
        ui.scheduleDate.setStretch(0, 0)
        ui.scheduleDate.setStretch(1, 1)
        ui.scheduleDateButton.setSpacing(14)
        ui.scheduleDate.setAlignment(
            ui.scheduleDateButton,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
        )
        ui.scheduleDate.setAlignment(
            ui.scheduleDateLabels,
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
        )
        ui.scheduleDateLabels.setSpacing(18)
        ui.scheduleDateLabels.setStretch(0, 1)
        ui.scheduleDateLabels.setStretch(1, 0)
        ui.scheduleDateLabelsDate.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        ui.scheduleDateLabelsOddity.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )

        ui.scheduleLessons.setContentsMargins(0, 0, 0, 0)
        ui.scheduleLessons.setAlignment(ui.scheduleLessonsLesson, Qt.AlignmentFlag.AlignTop)
        ui.scheduleLessonsLesson.setHorizontalSpacing(16)
        ui.scheduleLessonsLesson.setVerticalSpacing(16)

        ui.verticalLayout_11.setContentsMargins(0, 0, 0, 0)
        ui.mainGroups.setContentsMargins(104, 34, 104, 34)
        ui.mainGroups.setSpacing(24)
        ui.mainGroups.setStretch(0, 0)
        ui.mainGroups.setStretch(1, 1)
        ui.groupsTips.setSpacing(4)

        ui.verticalLayout_12.setContentsMargins(0, 0, 0, 0)
        ui.verticalLayout_12.setSpacing(28)
        ui.verticalLayout_12.setStretch(0, 0)
        ui.verticalLayout_12.setStretch(1, 1)
        ui.mainSettings.setContentsMargins(104, 34, 104, 0)
        ui.settingsCurrent.setSpacing(4)

        ui.settingsAlternative.setContentsMargins(104, 0, 104, 34)
        ui.settingsAlternative.setSpacing(24)
        ui.settingsAlternative.setStretch(0, 0)
        ui.settingsAlternative.setStretch(1, 1)
        ui.settingsAlternativeAction.setSpacing(0)

        for layout in (
            ui.verticalLayout_15,
            ui.verticalLayout_19,
            ui.verticalLayout_23,
            ui.verticalLayout_27,
        ):
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(0)

        ui.settingsScheduleMain.setContentsMargins(0, 8, 0, 0)
        ui.settingsScheduleMain.setSpacing(22)
        ui.settingsScheduleMain.setStretch(0, 0)
        ui.settingsScheduleMain.setStretch(1, 1)
        ui.settingsScheduleChange.setSpacing(18)
        ui.settingsScheduleChange.setStretch(0, 1)
        ui.settingsScheduleChange.setStretch(1, 0)
        ui.settingsScheduleChangeAction.setAlignment(
            ui.settingsScheduleChangeActionButton,
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop,
        )

        ui.settingsGroupsMain.setContentsMargins(0, 8, 0, 0)
        ui.settingsGroupsMain.setSpacing(22)
        ui.settingsGroupsMain.setStretch(0, 0)
        ui.settingsGroupsMain.setStretch(1, 1)
        ui.settingsGroupsChange.setSpacing(18)
        ui.settingsGroupsChange.setStretch(0, 1)
        ui.settingsGroupsChange.setStretch(1, 0)
        ui.settingsGroupsChangeAction.setAlignment(
            ui.settingsGroupsChangeActionButton,
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop,
        )

        ui.settingsStudentsMain.setContentsMargins(0, 8, 0, 0)
        ui.settingsStudentsMain.setSpacing(22)
        ui.settingsStudentsMain.setStretch(0, 0)
        ui.settingsStudentsMain.setStretch(1, 1)
        ui.settingsStudentsChange.setSpacing(18)
        ui.settingsStudentsChange.setStretch(0, 0)
        ui.settingsStudentsChange.setStretch(1, 1)
        ui.settingsStudentsChange.setStretch(2, 0)
        ui.settingsStudentsChangeChoose.setAlignment(
            ui.settingsStudentsChangeChooseButton,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
        )
        ui.settingsStudentsChangeAction.setAlignment(
            ui.settingsStudentsChangeActionButton,
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop,
        )

        ui.SettingsSemesterMain.setContentsMargins(0, 8, 0, 0)
        ui.SettingsSemesterMain.setSpacing(22)
        ui.SettingsSemesterMain.setStretch(0, 0)
        ui.SettingsSemesterMain.setStretch(1, 0)
        ui.SettingsSemesterMain.setStretch(2, 1)
        ui.settingsSemesterAction.setSpacing(18)
        ui.settingsSemesterAction.setStretch(0, 0)
        ui.settingsSemesterAction.setStretch(1, 0)
        ui.settingsSemesterAction.setStretch(2, 0)
        ui.settingsSemesterActionDate.setSpacing(8)
        ui.settingsSemesterActionWeek.setSpacing(14)
        ui.settingsSemesterActionWeek.setStretch(0, 1)
        ui.settingsSemesterActionWeek.setStretch(1, 0)
        ui.settingsSemesterActionWeekInput.setSpacing(8)
        ui.settingsSemesterActionWeekChange.setSpacing(8)
        ui.settingsSemesterActionWeekChange.setAlignment(
            ui.settingsSemesterActionWeekChangeButtonIncrease,
            Qt.AlignmentFlag.AlignLeft,
        )
        ui.settingsSemesterActionWeekChange.setAlignment(
            ui.settingsSemesterActionWeekChangeButtonDecrease,
            Qt.AlignmentFlag.AlignLeft,
        )
        ui.settingsSemesterActionSave.setAlignment(
            ui.settingsSemesterActionSaveButton,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
        )
        for label in (
            ui.settingsSemesterActionDateLabelTip1,
            ui.settingsSemesterActionDateLabelTip2,
            ui.settingsSemesterActionLabelTip1,
            ui.settingsSemesterActionLabelTip2,
            ui.settingsSemesterTip2Label,
        ):
            label.setWordWrap(True)
            label.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Preferred,
            )
        self._apply_responsive_margins()

    def _apply_responsive_margins(self) -> None:
        ui = self.ui
        width = max(self.width(), ui.mainWidget.width())
        outer_margin = 28 if width < 1000 else 56 if width < 1400 else 104
        schedule_margin = 24 if width < 1000 else 56 if width < 1400 else 120
        nav_top = 22 if width < 1000 else 34 if width < 1400 else 48

        ui.mainButtons.setContentsMargins(
            outer_margin,
            nav_top,
            outer_margin,
            max(18, nav_top // 2),
        )
        ui.mainSchedule.setContentsMargins(
            schedule_margin,
            24,
            schedule_margin,
            24,
        )
        ui.mainGroups.setContentsMargins(outer_margin, 28, outer_margin, 28)
        ui.mainSettings.setContentsMargins(outer_margin, 28, outer_margin, 0)
        ui.settingsAlternative.setContentsMargins(
            outer_margin,
            0,
            outer_margin,
            28,
        )


def main() -> None:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.showMaximized()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
