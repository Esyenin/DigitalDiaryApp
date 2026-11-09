"""Unified read-only views; all calculations come from JournalAnalytics."""
from datetime import date

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QDateEdit,
    QFormLayout, QHeaderView, QLabel, QMessageBox, QPushButton, QTableWidget,
    QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget)
from sqlalchemy import select

from app.models import AcademicTerm, CourseOffering, Discipline, Group, Student
from app.services.journal_analytics import JournalAnalytics


class JournalWorkspace(QWidget):
    def __init__(self, window, *, student_id=None, group_id=None, offering_id=None, term_id=None):
        super().__init__()
        self.window, self.repo = window, window.repository
        self.setObjectName('DetailPage')
        body = QVBoxLayout(self)
        title = QLabel('Journal analytics')
        title.setObjectName('DetailTitle')
        body.addWidget(title)
        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        self.mode = QComboBox()
        self.mode.addItems(['Student', 'Group', 'Discipline'])
        self.entity = QComboBox()
        self.term = QComboBox()
        self.term.addItem('All periods', None)
        for term in self.repo.session.scalars(select(AcademicTerm).order_by(AcademicTerm.start_date)):
            self.term.addItem(f'{term.name} | {term.start_date} | {term.status}', term.id)
        self.as_of = QDateEdit(QDate.currentDate())
        self.as_of.setCalendarPopup(True)
        self.range_enabled = QCheckBox('Date range')
        self.start = QDateEdit(QDate.currentDate())
        self.end = QDateEdit(QDate.currentDate())
        for control in (self.start, self.end):
            control.setCalendarPopup(True)
            control.setEnabled(False)
        self.range_enabled.toggled.connect(self.start.setEnabled)
        self.range_enabled.toggled.connect(self.end.setEnabled)
        form.addRow('View', self.mode)
        form.addRow('Record', self.entity)
        form.addRow('Period', self.term)
        form.addRow('As of', self.as_of)
        form.addRow(self.range_enabled)
        form.addRow('From', self.start)
        form.addRow('Through', self.end)
        body.addLayout(form)
        self.overview = QLabel()
        self.overview.setWordWrap(True)
        body.addWidget(self.overview)
        self.tabs = QTabWidget()
        self.tabs.setUsesScrollButtons(True)
        self.tables = {}
        for name in ('Results', 'Events and attempts', 'Attendance', 'Behavior', 'Membership', 'Legacy marks'):
            table = QTableWidget()
            table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
            table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
            table.setWordWrap(True)
            table.cellDoubleClicked.connect(lambda row, col, current=table: self.open_record(current, row))
            self.tables[name] = table
            self.tabs.addTab(table, name)
        body.addWidget(self.tabs, 1)
        refresh = QPushButton('Refresh dated view')
        refresh.clicked.connect(self.refresh)
        body.addWidget(refresh)
        self.mode.currentIndexChanged.connect(self.reload_entities)
        selected = student_id
        if group_id is not None:
            self.mode.setCurrentIndex(1)
            selected = group_id
        elif offering_id is not None:
            self.mode.setCurrentIndex(2)
            selected = offering_id
        self.reload_entities()
        if term_id is not None:
            self.term.setCurrentIndex(self.term.findData(term_id))
        if selected is not None:
            self.entity.setCurrentIndex(self.entity.findData(selected))
        self.refresh()

    def reload_entities(self):
        self.entity.clear()
        model = (Student, Group, CourseOffering)[self.mode.currentIndex()]
        for row in self.repo.session.scalars(select(model).order_by(model.id)):
            if model is Student:
                group = self.repo.session.get(Group, row.group_id)
                label = f'{row.surname} {row.first_name} {row.patronymic or ""} | {group.name} | {row.status}'
            elif model is CourseOffering:
                term = self.repo.session.get(AcademicTerm, row.term_id)
                discipline = self.repo.session.get(Discipline, row.discipline_id)
                label = f'{discipline.name} | {term.name} | {row.name}'
            else:
                label = row.name + (' | archived' if row.is_archived else '')
            self.entity.addItem(label, row.id)

    def fill(self, name, headings, rows):
        table = self.tables[name]
        table.clear()
        table.setColumnCount(len(headings))
        table.setHorizontalHeaderLabels(headings)
        table.setRowCount(len(rows))
        for index, (values, context) in enumerate(rows):
            for column, value in enumerate(values):
                item = QTableWidgetItem('-' if value is None else str(value))
                item.setData(Qt.ItemDataRole.UserRole, context)
                table.setItem(index, column, item)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setStretchLastSection(True)
        table.resizeRowsToContents()

    def refresh(self):
        key = self.entity.currentData()
        if key is None:
            self.overview.setText('No records')
            for table in self.tables.values():
                table.setRowCount(0)
            return
        filters = dict(term_id=self.term.currentData(), as_of=self.as_of.date().toPython())
        if self.range_enabled.isChecked():
            filters.update(start_date=self.start.date().toPython(), end_date=self.end.date().toPython())
            if filters['start_date'] > filters['end_date']:
                QMessageBox.warning(self, 'Journal', 'Date range is reversed.')
                return
        self.repo.refresh()
        analytics = JournalAnalytics(self.repo.session)
        try:
            if self.mode.currentIndex() == 0:
                students = [analytics.student(key, **filters)]
                overview = students[0]['name']
            elif self.mode.currentIndex() == 1:
                data = analytics.group(key, **filters)
                students = data['students']
                overview = f"{data['name']} | Students: {len(students)} | Debtors: {data['debtors_count']}"
                if not data['membership_complete']:
                    overview += ' | Incomplete historical roster'
            else:
                filters.pop('term_id')
                data = analytics.offering(key, **filters)
                students = data['students']
                overview = f"{data['name']} | {data['year_name']} / {data['term_name']} | Students: {len(students)}"
        except ValueError as exc:
            QMessageBox.warning(self, 'Journal', str(exc))
            return
        self.overview.setText(overview)
        results, events, attendance, behavior, membership, legacy = [], [], [], [], [], []
        warnings = set()
        for student in students:
            context = (student['id'], None)
            warnings.update(student['warnings'])
            for course in student['courses']:
                context_course = (student['id'], course['id'])
                results.append(([student['name'], course['name'], course['year_name'] + ' / ' + course['term_name'],
                                 'Course total', course['earned'], course['maximum'], len(course['debts']),
                                 'Known' if course['history_complete'] else 'Incomplete'], context_course))
                for module in course['modules']:
                    results.append(([student['name'], course['name'], '', module['name'], module['earned'],
                                     module['maximum'], '', ''], context_course))
                for event in course['event_results']:
                    events.append(([student['name'], course['name'], event['title'], event['category'],
                                    f"{event['earned']} / {event['maximum']}", event['passed'],
                                    'Pending deadline' if event['pending'] else 'Outstanding' if event['debt'] else 'Complete',
                                    event['attempts']], context_course))
                for attempt in course['attempts']:
                    events.append(([student['name'], course['name'], f"Attempt #{attempt['number']} / event {attempt['event_id']}",
                                    str(attempt['occurred_at']), attempt['points'], attempt['passed'],
                                    f"Completed {attempt['work_completed']}; defended {attempt['defended']}",
                                    f"Checklist {attempt['checklist_version_id']}; visit {attempt['consultation_visit_id']}"], context_course))
            for record in student['attendance']['records']:
                attendance.append(([student['name'], record['date'], record['status'], record['arrived_at'],
                                    record['late_seconds'], record['reason'], record['source'],
                                    'Known' if record['complete'] else 'Incomplete'], context))
            for record in student['behavior']:
                behavior.append(([student['name'], record['occurred_at'], record['polarity'], record['category'],
                                  record['comment'], record['source'], record['corrected']], context))
            for record in student['memberships']:
                membership.append(([student['name'], record['group'], record['start'], record['end'],
                                    record['known_from'], record['origin']], context))
            for record in student['legacy_marks']:
                legacy.append(([student['name'], record['lesson_date'], record['topic'], record['value'],
                                record['group_name'], 'Unclassified legacy mark'], context))
        self.fill('Results', ['Student','Discipline','Period','Module','Earned','Maximum','Debts','History'], results)
        self.fill('Events and attempts', ['Student','Discipline','Event / attempt','Type / date','Points','Passed','State','Attempts / context'], events)
        self.fill('Attendance', ['Student','Date','State','Arrival UTC','Late seconds','Reason','Source','History'], attendance)
        self.fill('Behavior', ['Student','UTC time','Type','Category','Comment','Source','Corrected'], behavior)
        self.fill('Membership', ['Student','Group','From','Until exclusive','Known from','Origin'], membership)
        self.fill('Legacy marks', ['Student','Lesson date','Topic','Stored mark','Groups','Provenance'], legacy)
        if warnings:
            self.overview.setText(overview + '\n' + '\n'.join(sorted(warnings)))

    def open_record(self, table, row):
        item = table.item(row, 0)
        if item is None:
            return
        student_id, offering_id = item.data(Qt.ItemDataRole.UserRole)
        if offering_id is not None:
            self.window.show_teaching_workspace(offering_id=offering_id, student_id=student_id)
        else:
            self.window.show_student_detail(self.repo.get_student(student_id))
