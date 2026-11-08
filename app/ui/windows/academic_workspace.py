"""Academic configuration embedded in the existing main window."""

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (QComboBox, QDateEdit, QDialog, QDialogButtonBox,
                               QFormLayout, QLabel, QLineEdit,
                               QListWidget, QListWidgetItem, QMessageBox, QPushButton,
                               QSpinBox, QTabWidget, QVBoxLayout, QWidget)
from sqlalchemy import select

from app.models import (AcademicYear, AcademicTerm, Discipline, CourseOffering,
                        TeachingModule)


class AcademicWorkspace(QWidget):
    models = (("Academic years", AcademicYear), ("Terms", AcademicTerm),
              ("Disciplines", Discipline), ("Courses", CourseOffering),
              ("Modules", TeachingModule))

    def __init__(self, window):
        super().__init__()
        self.window = window
        self.repo = window.repository
        self.setObjectName("DetailPage")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        title = QLabel("Academic structure")
        title.setObjectName("DetailTitle")
        layout.addWidget(title)
        self.tabs = QTabWidget()
        self.lists = {}
        for name, model in self.models:
            page = QWidget()
            page_layout = QVBoxLayout(page)
            listing = QListWidget()
            listing.setObjectName("Academic" + model.__name__)
            self.lists[model] = listing
            page_layout.addWidget(listing)
            add = QPushButton("Add " + model.__name__)
            add.clicked.connect(lambda checked=False, current=model: self.create(current))
            page_layout.addWidget(add)
            if model is AcademicTerm:
                choose = QPushButton("Use selected term in calendar")
                choose.clicked.connect(self.select_term)
                page_layout.addWidget(choose)
                close = QPushButton("Close selected term")
                close.clicked.connect(self.close_term)
                page_layout.addWidget(close)
            self.tabs.addTab(page, name)
        layout.addWidget(self.tabs)
        self.refresh()

    def refresh(self):
        for model, listing in self.lists.items():
            listing.clear()
            for row in self.repo.session.scalars(select(model).order_by(model.id)):
                detail = row.name
                if model is AcademicTerm:
                    detail += f" | {row.start_date} | {row.total_weeks} weeks | {row.status}"
                if model is CourseOffering:
                    term = self.repo.session.get(AcademicTerm, row.term_id)
                    discipline = self.repo.session.get(Discipline, row.discipline_id)
                    detail += f" | {discipline.name} | {term.name}"
                if model is TeachingModule:
                    detail += f" | {row.start_date} - {row.end_date} | #{row.position}"
                item = QListWidgetItem(detail)
                item.setData(Qt.ItemDataRole.UserRole, row.id)
                listing.addItem(item)

    def create(self, model):
        from app.ui.data.repository import RepositoryError

        dialog = QDialog(self)
        dialog.setWindowTitle("Add " + model.__name__)
        form = QFormLayout(dialog)
        name = QLineEdit()
        form.addRow("Name", name)
        fields = {}

        def choice(key, label, entity):
            box = QComboBox()
            for row in self.repo.session.scalars(select(entity).order_by(entity.id)):
                box.addItem(f"{row.id}: {row.name}", row.id)
            fields[key] = box
            form.addRow(label, box)

        def calendar(key, label):
            field = QDateEdit(QDate.currentDate())
            field.setCalendarPopup(True)
            fields[key] = field
            form.addRow(label, field)

        if model is AcademicTerm:
            choice("year_id", "Academic year", AcademicYear)
        if model is CourseOffering:
            choice("term_id", "Term", AcademicTerm)
            choice("discipline_id", "Discipline", Discipline)
            groups = QListWidget()
            for group in self.repo.list_groups():
                item = QListWidgetItem(group.name)
                item.setData(Qt.ItemDataRole.UserRole, group.id)
                item.setCheckState(Qt.CheckState.Unchecked)
                groups.addItem(item)
            fields["groups"] = groups
            form.addRow("Groups", groups)
        if model is TeachingModule:
            choice("offering_id", "Course", CourseOffering)
            position = QSpinBox()
            position.setRange(1, 100)
            fields["position"] = position
            form.addRow("Position", position)
        if model in {AcademicYear, AcademicTerm, TeachingModule}:
            calendar("start_date", "Start (inclusive)")
        if model in {AcademicYear, TeachingModule}:
            calendar("end_date", "End (exclusive)")
        if model is AcademicTerm:
            weeks = QSpinBox()
            weeks.setRange(1, 52)
            weeks.setValue(17)
            fields["total_weeks"] = weeks
            form.addRow("Weeks", weeks)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        form.addRow(buttons)
        buttons.rejected.connect(dialog.reject)

        def save():
            values = {"name": name.text()}
            for key, field in fields.items():
                if isinstance(field, QComboBox):
                    values[key] = field.currentData()
                elif isinstance(field, QDateEdit):
                    values[key] = field.date().toPython()
                elif isinstance(field, QSpinBox):
                    values[key] = field.value()
                else:
                    values["group_ids"] = [field.item(i).data(Qt.ItemDataRole.UserRole)
                                           for i in range(field.count())
                                           if field.item(i).checkState() == Qt.CheckState.Checked]
            action = {AcademicYear: "create_year", AcademicTerm: "create_term", Discipline: "create_discipline",
                      CourseOffering: "create_offering", TeachingModule: "create_module"}[model]
            try:
                self.repo.academic_action(action, **values)
            except RepositoryError as exc:
                QMessageBox.warning(dialog, "Academic structure", str(exc))
                return
            dialog.accept()
        buttons.accepted.connect(save)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh()

    def select_term(self):
        item = self.lists[AcademicTerm].currentItem()
        if item is None:
            return
        self.repo.academic_action("select_term", item.data(Qt.ItemDataRole.UserRole))
        self.window.semester_settings = self.repo.academic_calendar()
        from app.ui.data.calendar import clamp_week_start
        self.window.selected_week_start = clamp_week_start(self.window.selected_week_start, self.window.semester_settings)
        self.window._populate_semester_inputs()
        self.window.refresh_all()

    def close_term(self):
        from app.ui.data.repository import RepositoryError
        item = self.lists[AcademicTerm].currentItem()
        if item is None:
            return
        if QMessageBox.question(self, "Close term", "Close this term and protect its history? This cannot be undone.") != QMessageBox.StandardButton.Yes:
            return
        try:
            self.repo.academic_action("close_term", item.data(Qt.ItemDataRole.UserRole))
        except RepositoryError as exc:
            QMessageBox.warning(self, "Close term", str(exc))
            return
        self.refresh()
