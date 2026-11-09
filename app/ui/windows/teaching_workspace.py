"""Embedded teaching workflows. All writes go through repository actions."""

from datetime import datetime, timezone
from decimal import Decimal
from time import monotonic
from uuid import uuid4

from PySide6.QtCore import QDate, QDateTime, QTimeZone, Qt, QTimer
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDateEdit, QDateTimeEdit,
    QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMessageBox, QPushButton, QScrollArea,
    QSpinBox, QTabWidget, QTextEdit, QVBoxLayout, QWidget)
from sqlalchemy import select

from app.models import (AssessmentAttempt, AssessmentEvent, AttendanceRevision,
    ChecklistCriterion, ChecklistVersion, Consultation, ConsultationVisit,
    AcademicTerm, AcademicYear, CourseOffering, CourseOfferingGroup, CriterionAnswer, Discipline, Group, IndividualPlan, LabWork, Lesson,
    LessonDisposition, NonTeachingDay, PlanEntry, PlanStage, ResultCorrection,
    Schedule, Student, TeachingModule)
from app.ui.data.repository import RepositoryError


def utc_editor():
    editor = QDateTimeEdit(QDateTime.currentDateTimeUtc())
    editor.setTimeZone(QTimeZone.utc())
    editor.setCalendarPopup(True)
    editor.setDisplayFormat("yyyy-MM-dd HH:mm 'UTC'")
    return editor


def value(field):
    if isinstance(field, QComboBox):
        return field.currentData()
    if isinstance(field, QCheckBox):
        return field.isChecked()
    if isinstance(field, QDateTimeEdit):
        return datetime.fromtimestamp(field.dateTime().toMSecsSinceEpoch() / 1000, timezone.utc)
    if isinstance(field, QDateEdit):
        return field.date().toPython()
    if isinstance(field, QSpinBox):
        return field.value()
    if isinstance(field, QTextEdit):
        return field.toPlainText()
    return field.text().strip()


def choices(items):
    box = QComboBox()
    box.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
    box.setMinimumContentsLength(12)
    for label, key in items:
        box.addItem(str(label), key)
    return box


def options(*names):
    return choices([(name.replace('_', ' ').title(), name) for name in names])


def spin(minimum=1, maximum=10000):
    field = QSpinBox()
    field.setRange(minimum, maximum)
    return field


class TeachingWorkspace(QWidget):
    def __init__(self, window, *, offering_id=None, student_id=None, lesson_id=None):
        super().__init__()
        self.window, self.repo = window, window.repository
        self.lesson_id = lesson_id
        self.setObjectName("DetailPage")
        layout = QVBoxLayout(self)
        title = QLabel("Teaching process")
        title.setObjectName("DetailTitle")
        layout.addWidget(title)
        form = QFormLayout()
        self.offering = QComboBox()
        self.student = QComboBox()
        self.student.setEditable(True)
        self.student.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.student.completer().setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.student.completer().setFilterMode(Qt.MatchFlag.MatchContains)
        self.module = QComboBox()
        for box in (self.offering, self.student, self.module):
            box.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            box.setMinimumContentsLength(12)
            box.currentTextChanged.connect(box.setToolTip)
        form.addRow("Course", self.offering)
        form.addRow("Student / group", self.student)
        form.addRow("Module", self.module)
        layout.addLayout(form)
        self.totals = QLabel()
        self.totals.setWordWrap(True)
        layout.addWidget(self.totals)
        self.tabs = QTabWidget()
        self.tabs.setUsesScrollButtons(True)
        layout.addWidget(self.tabs)
        self.lists = {}
        pages = [
            ("Results", [("Create module", self.create_module), ("Create event", self.create_event),
                         ("Record attempt", self.record_attempt), ("Cancel event", self.cancel_event)]),
            ("History", [("Correct result", self.correct_result)]),
            ("Laboratories", [("Create lab", self.create_lab), ("New checklist version", self.create_checklist),
                              ("Defense", self.defend)]),
            ("Consultations", [("Create consultation", self.create_consultation), ("Register visit", self.register_visit)]),
            ("Plans", [("Create plan", self.create_plan), ("Add stage", self.add_stage), ("Record progress", self.record_progress)]),
            ("Calendar / attendance", [("Non-teaching day", self.add_holiday), ("Lesson status", self.lesson_status),
                                      ("Attendance revision", self.attendance_dialog)]),
        ]
        for name, commands in pages:
            page = QWidget()
            page_layout = QVBoxLayout(page)
            listing = QListWidget()
            listing.setWordWrap(True)
            self.lists[name] = listing
            page_layout.addWidget(listing)
            # A wrapping-free vertical command strip also fits narrow windows.
            for label, callback in commands:
                button = QPushButton(label)
                button.clicked.connect(lambda checked=False, fn=callback: fn())
                page_layout.addWidget(button)
            if name == 'Results' and lesson_id is not None:
                for category, label in [('seminar_start', 'Seminar start test'), ('seminar_end', 'Seminar end test')]:
                    button = QPushButton(label)
                    button.clicked.connect(lambda checked=False, c=category: self.create_event(category=c))
                    page_layout.addWidget(button)
            self.tabs.addTab(page, name)
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.refresh)
        layout.addWidget(refresh)
        analytics = QPushButton('Discipline journal and statistics')
        analytics.clicked.connect(lambda checked=False: self.window.show_journal_workspace(offering_id=self.offering.currentData()))
        layout.addWidget(analytics)
        self.reload_context(offering_id, student_id)
        self.offering.currentIndexChanged.connect(self.course_changed)
        self.student.currentIndexChanged.connect(self.refresh)
        self.module.currentIndexChanged.connect(self.refresh)
        self.refresh()

    def rows(self, model, *conditions):
        return list(self.repo.session.scalars(select(model).where(*conditions).order_by(model.id)))

    def student_label(self, student):
        group = self.repo.session.get(Group, student.group_id)
        return (f"{student.surname} {student.first_name} {student.patronymic or ''} | "
                f"{group.name if group else '?'} | {student.status} [#{student.id}]")

    def offering_label(self, offering):
        term = self.repo.session.get(AcademicTerm, offering.term_id)
        year = self.repo.session.get(AcademicYear, term.year_id)
        discipline = self.repo.session.get(Discipline, offering.discipline_id)
        groups = [self.repo.session.get(Group, link.group_id).name
                  for link in self.rows(CourseOfferingGroup, CourseOfferingGroup.offering_id == offering.id)]
        return f'{discipline.name} | {year.name} / {term.name} | {offering.name} | {", ".join(groups)}'

    def reload_context(self, offering_id=None, student_id=None):
        for box, rows, selected, label in (
            (self.offering, self.rows(CourseOffering), offering_id, self.offering_label),
            (self.student, self.rows(Student), student_id, self.student_label),
        ):
            box.blockSignals(True)
            box.clear()
            for row in rows:
                box.addItem(label(row), row.id)
            if selected is not None:
                box.setCurrentIndex(box.findData(selected))
            box.blockSignals(False)
        self.course_changed()

    def course_changed(self):
        self.module.blockSignals(True)
        self.module.clear()
        self.module.addItem("All modules", None)
        for row in self.rows(TeachingModule, TeachingModule.offering_id == self.offering.currentData()):
            self.module.addItem(row.name, row.id)
        self.module.blockSignals(False)
        self.refresh()

    def warning(self, error):
        QMessageBox.warning(self, "Teaching process", str(error))

    def form(self, title, fields, action, *, fixed=None, transform=None, academic=False):
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.setMinimumWidth(420)
        dialog.resize(560, 500)
        outer = QVBoxLayout(dialog)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        form = QFormLayout(content)
        for key, (label, field) in fields.items():
            field.setObjectName(key)
            form.addRow(label, field)
        scroll.setWidget(content)
        outer.addWidget(scroll)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        outer.addWidget(buttons)
        buttons.rejected.connect(dialog.reject)
        operation_key = uuid4().hex

        def save():
            try:
                data = {key: value(field) for key, (_, field) in fields.items()}
                data.update(fixed or {})
                if transform:
                    data = transform(data)
                if action in {"record_attempt", "correct_result", "record_attendance"}:
                    data["operation_key"] = operation_key
                method = self.repo.academic_action if academic else self.repo.teaching_action
                method(action, **data)
            except (RepositoryError, ValueError, ArithmeticError) as exc:
                self.warning(exc)
                return
            dialog.accept()
        buttons.accepted.connect(save)
        accepted = dialog.exec() == QDialog.DialogCode.Accepted
        if accepted:
            self.course_changed()
        return accepted

    def entity(self, model, *conditions, optional=False, label=None):
        items = [("None", None)] if optional else []
        for row in self.rows(model, *conditions):
            text = label(row) if label else getattr(row, "title", getattr(row, "name", str(row.id)))
            items.append((f"{text} [#{row.id}]", row.id))
        return choices(items)

    def event_choice(self, category=None):
        modules = [row.id for row in self.rows(TeachingModule, TeachingModule.offering_id == self.offering.currentData())]
        conditions = [AssessmentEvent.module_id.in_(modules)]
        if self.module.currentData() is not None:
            conditions.append(AssessmentEvent.module_id == self.module.currentData())
        if category:
            conditions.append(AssessmentEvent.category == category)
        return self.entity(AssessmentEvent, *conditions)

    def lesson_choice(self, optional=False):
        schedules = [row.id for row in self.rows(Schedule, Schedule.offering_id == self.offering.currentData())]
        box = self.entity(Lesson, Lesson.schedule_id.in_(schedules), optional=optional,
                          label=lambda r: f"{r.date} | {r.topic or ''}")
        if self.lesson_id is not None:
            box.setCurrentIndex(box.findData(self.lesson_id))
        return box

    def visits(self):
        return self.entity(ConsultationVisit, ConsultationVisit.student_id == self.student.currentData(),
                           optional=True, label=lambda r: f"{r.consultation_id}: {r.purpose} | {r.question}")

    def refresh(self):
        if not hasattr(self, "lists"):
            return
        for listing in self.lists.values():
            listing.clear()
        offering, student = self.offering.currentData(), self.student.currentData()
        summary = {}
        self.totals.setText('No course or student selected')
        if offering is not None and student is not None:
            try:
                summary = self.repo.teaching_summary(offering, student, module_id=self.module.currentData())
            except RepositoryError as exc:
                self.totals.setText(str(exc))
            else:
                self.totals.setText(f"Earned: {summary['earned']} / {summary['maximum']} | Remaining: {summary['remaining']} | "
                                    f"Debts: {', '.join(d['title'] for d in summary['debts']) or 'None'}")
        def add(tab, text, key=None):
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, key)
            self.lists[tab].addItem(item)
        for module in summary.get("modules", []):
            add("Results", f"{module['name']}: {module['earned']} / {module['maximum']} | Remaining {module['remaining']}")
        event_ids = [event['id'] for event in summary.get("events", [])]
        for event in summary.get("events", []):
            model = self.repo.session.get(AssessmentEvent, event['id'])
            custom_type = getattr(model, 'custom_type', None)
            type_label = f' [{custom_type}]' if custom_type else ''
            add("Results", f"{event['title']}{type_label}: {event['earned']} / {event['maximum']} | "
                f"{'Passed' if event['passed'] else 'Not passed'} | Debt: {event['debt']}", event['id'])
        attempts = self.rows(AssessmentAttempt, AssessmentAttempt.student_id == student, AssessmentAttempt.event_id.in_(event_ids))
        for attempt in attempts:
            event = self.repo.session.get(AssessmentEvent, attempt.event_id)
            add("History", f"{event.title} | #{attempt.attempt_number} | {attempt.occurred_at} | "
                f"{attempt.points} | Passed: {attempt.passed} | {attempt.comment}", attempt.id)
            for answer in self.rows(CriterionAnswer, CriterionAnswer.attempt_id == attempt.id):
                criterion = self.repo.session.get(ChecklistCriterion, answer.criterion_id)
                add("History", f"  {criterion.label}: {'Yes' if answer.satisfied else 'No'}")
            if attempt.additional_answer:
                add("History", f"  Additional answer: {attempt.additional_answer} | Passed: {attempt.question_passed}")
            for correction in self.rows(ResultCorrection, ResultCorrection.attempt_id == attempt.id):
                add("History", f"  Correction {correction.occurred_at}: {correction.points} | Passed {correction.passed} | "
                    f"{correction.reason} | {correction.source}")
        for lab in self.rows(LabWork, LabWork.event_id.in_(event_ids)):
            add("Laboratories", lab.title, lab.id)
            for version in self.rows(ChecklistVersion, ChecklistVersion.lab_id == lab.id):
                criteria = self.rows(ChecklistCriterion, ChecklistCriterion.version_id == version.id)
                add("Laboratories", f"  Version {version.revision}: " + '; '.join(c.label for c in criteria))
        for consultation in self.rows(Consultation):
            add("Consultations", f"{consultation.starts_at} | {consultation.title}", consultation.id)
            for visit in self.rows(ConsultationVisit, ConsultationVisit.consultation_id == consultation.id,
                                   ConsultationVisit.student_id == student):
                selected_student = self.repo.session.get(Student, student)
                add("Consultations", f"  {self.student_label(selected_student)} | {visit.purpose} | {visit.question} | {visit.comment}", visit.id)
        for plan in self.rows(IndividualPlan, IndividualPlan.student_id == student):
            add("Plans", f"{plan.title} | {plan.kind}", plan.id)
            for stage in sorted(self.rows(PlanStage, PlanStage.plan_id == plan.id), key=lambda r: r.position):
                add("Plans", f"  {stage.position}. {stage.title}", stage.id)
                for entry in self.rows(PlanEntry, PlanEntry.stage_id == stage.id):
                    add("Plans", f"    {entry.occurred_at} | Completed {entry.completed} | {entry.comment}")
        course = self.repo.session.get(CourseOffering, offering) if offering is not None else None
        for day in self.rows(NonTeachingDay, NonTeachingDay.term_id == course.term_id) if course else []:
            add("Calendar / attendance", f"{day.date}: {day.reason}")
        lessons = self.lesson_choice()
        ids = [lessons.itemData(i) for i in range(lessons.count())]
        for record in self.rows(LessonDisposition, LessonDisposition.lesson_id.in_(ids)):
            add("Calendar / attendance", f"Lesson #{record.lesson_id}: {record.status} | {record.reason} | "
                f"Replacement #{record.replacement_lesson_id}")
        from app.models import Attendance
        attendances = [r.id for r in self.rows(Attendance, Attendance.student_id == student, Attendance.lesson_id.in_(ids))]
        for record in self.rows(AttendanceRevision, AttendanceRevision.attendance_id.in_(attendances)):
            add("Calendar / attendance", f"{record.occurred_at}: {record.previous_status or 'unknown'} -> {record.status} | Arrival {record.arrived_at} | "
                f"Late seconds {record.late_seconds} | {record.reason} | {record.source}")

    def create_module(self):
        start, end = QDateEdit(QDate.currentDate()), QDateEdit(QDate.currentDate().addDays(7))
        for field in (start, end):
            field.setCalendarPopup(True)
        self.form("Create module", {"name": ("Name", QLineEdit()), "position": ("Position", spin()),
            "start_date": ("Start inclusive", start), "end_date": ("End exclusive", end)}, "create_module",
            fixed={"offering_id": self.offering.currentData()}, academic=True)

    def create_event(self, category=None):
        due = utc_editor()
        enabled = QCheckBox()
        due.setEnabled(False)
        enabled.toggled.connect(due.setEnabled)
        category_field = options('checkpoint', 'lab', 'additional', 'seminar_start', 'seminar_end')
        if category is not None:
            category_field.setCurrentIndex(category_field.findData(category))
        custom_type = QLineEdit()
        custom_type.setMaxLength(128)
        custom_type.setEnabled(category_field.currentData() == 'additional')
        category_field.currentIndexChanged.connect(
            lambda _: custom_type.setEnabled(category_field.currentData() == 'additional'))
        policy = choices([('Choose attempt policy', None), ('Best', 'best'), ('Latest', 'latest')])
        def convert(data):
            if data['category'] in {'seminar_start', 'seminar_end'} and data['lesson_id'] is None:
                raise ValueError('Select a concrete lesson for a seminar test.')
            if data['attempt_policy'] is None:
                raise ValueError('Choose best or latest attempt policy.')
            data['due_at'] = data['due_at'] if data.pop('has_due') else None
            data['max_attempts'] = data['max_attempts'] or None
            data['max_points'] = Decimal(data['max_points'])
            data['custom_type'] = (data['custom_type'] or None) if data['category'] == 'additional' else None
            return data
        self.form("Create assessment event", {
            "module_id": ("Module", self.entity(TeachingModule, TeachingModule.offering_id == self.offering.currentData())),
            "title": ("Title", QLineEdit()), "category": ("Category", category_field),
            "custom_type": ("Additional event type", custom_type),
            "max_points": ("Maximum points", QLineEdit()), "required": ("Required", QCheckBox()),
            "attempt_policy": ("Attempt policy", policy), "max_attempts": ("Attempt limit (0 unlimited)", spin(0)),
            "conditions": ("Conditions", QTextEdit()), "has_due": ("Deadline", enabled), "due_at": ("Due at UTC", due),
            "lesson_id": ("Lesson", self.lesson_choice(optional=True))}, "create_event", transform=convert)

    def attempt_fields(self):
        return {"points": ("Points", QLineEdit('0.00')), "work_completed": ("Work completed", QCheckBox()),
                "defended": ("Defended", QCheckBox()), "passed": ("Passed", QCheckBox()),
                "comment": ("Comment", QTextEdit()), "consultation_visit_id": ("Consultation visit", self.visits())}

    def record_attempt(self):
        fields = {"event_id": ("Event", self.event_choice()), **self.attempt_fields()}
        self.form("Record assessment attempt", fields, "record_attempt", fixed={"student_id": self.student.currentData()},
                  transform=lambda d: {**d, 'points': Decimal(d['points'])})

    def correct_result(self):
        events = self.event_choice()
        ids = [events.itemData(i) for i in range(events.count())]
        attempts = self.entity(AssessmentAttempt, AssessmentAttempt.student_id == self.student.currentData(),
            AssessmentAttempt.event_id.in_(ids), label=lambda r: f"Event #{r.event_id} attempt {r.attempt_number}: {r.points}")
        self.form("Append result correction", {"attempt_id": ("Attempt", attempts), "points": ("Points", QLineEdit('0.00')),
            "passed": ("Passed", QCheckBox()), "reason": ("Reason", QTextEdit())}, "correct_result",
            transform=lambda d: {**d, 'points': Decimal(d['points'])})

    def cancel_event(self):
        self.form("Cancel event", {"event_id": ("Event", self.event_choice()), "reason": ("Reason", QTextEdit())}, 'cancel_event')

    def create_lab(self):
        self.form("Create laboratory", {"event_id": ("Lab event", self.event_choice('lab')), "title": ("Title", QLineEdit())}, 'create_lab')

    def lab_choice(self):
        events = self.event_choice('lab')
        ids = [events.itemData(i) for i in range(events.count())]
        return self.entity(LabWork, LabWork.event_id.in_(ids))

    def create_checklist(self):
        self.form("New checklist version", {"lab_id": ("Lab", self.lab_choice()),
            "criteria": ("Criteria (one per line)", QTextEdit())}, 'create_checklist',
            transform=lambda d: {**d, 'criteria': [s.strip() for s in d['criteria'].splitlines() if s.strip()]})

    def defend(self):
        lab = self.lab_choice()
        dialog = QDialog(self)
        dialog.setWindowTitle('Select laboratory')
        form = QFormLayout(dialog)
        form.addRow('Lab', lab)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        form.addRow(buttons)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        row = self.repo.session.get(LabWork, lab.currentData())
        if row is None:
            self.warning('Select a laboratory.')
            return
        versions = self.rows(ChecklistVersion, ChecklistVersion.lab_id == row.id)
        if not versions:
            self.warning('Create a checklist version before defense.')
            return
        DefenseDialog(self, row, versions).exec()
        self.refresh()

    def create_consultation(self):
        self.form('Create consultation', {'starts_at': ('Starts at UTC', utc_editor()),
            'title': ('Title', QLineEdit('Consultation'))}, 'create_consultation')

    def register_visit(self):
        self.form('Register consultation visit', {'consultation_id': ('Consultation', self.entity(Consultation,
            label=lambda r: f'{r.starts_at} | {r.title}')), 'purpose': ('Purpose', QLineEdit()),
            'question': ('Question', QTextEdit()), 'comment': ('Comment', QTextEdit())}, 'register_visit',
            fixed={'student_id': self.student.currentData()})

    def create_plan(self):
        self.form('Create individual plan', {'title': ('Title', QLineEdit()), 'kind': ('Kind', options('coursework', 'diploma', 'project'))},
            'create_plan', fixed={'student_id': self.student.currentData(), 'offering_id': self.offering.currentData()})

    def plan_choice(self):
        return self.entity(IndividualPlan, IndividualPlan.student_id == self.student.currentData())

    def add_stage(self):
        self.form('Add plan stage', {'plan_id': ('Plan', self.plan_choice()), 'title': ('Title', QLineEdit()),
            'position': ('Position', spin())}, 'add_plan_stage')

    def record_progress(self):
        plans = [r.id for r in self.rows(IndividualPlan, IndividualPlan.student_id == self.student.currentData())]
        self.form('Record plan progress', {'stage_id': ('Stage', self.entity(PlanStage, PlanStage.plan_id.in_(plans),
            label=lambda r: f'Plan #{r.plan_id} | {r.position}. {r.title}')), 'completed': ('Completed', QCheckBox()),
            'comment': ('Comment', QTextEdit()), 'consultation_visit_id': ('Visit', self.visits())}, 'record_plan_entry')

    def add_holiday(self):
        key = self.offering.currentData()
        course = self.repo.session.get(CourseOffering, key) if key is not None else None
        if course is None:
            self.warning('Select a course.')
            return
        day = QDateEdit(QDate.currentDate().addDays(1))
        day.setCalendarPopup(True)
        self.form('Add non-teaching day', {'day': ('Date', day), 'reason': ('Reason', QTextEdit())},
            'add_non_teaching_day', fixed={'term_id': course.term_id})

    def lesson_status(self):
        day = QDateEdit(QDate.currentDate().addDays(1))
        day.setCalendarPopup(True)
        self.form('Lesson disposition', {'lesson_id': ('Lesson', self.lesson_choice()),
            'status': ('Status', options('cancelled', 'holiday', 'moved', 'held')),
            'reason': ('Reason', QTextEdit()), 'new_date': ('Move to', day)}, 'set_lesson_disposition',
            transform=lambda d: {**d, 'new_date': d['new_date'] if d['status'] == 'moved' else None})

    def attendance_dialog(self):
        self.open_attendance_dialog(self.lesson_id, self.student.currentData())

    def open_attendance_dialog(self, lesson_id, student_id):
        lesson = self.lesson_choice()
        if lesson_id is not None:
            if lesson.findData(lesson_id) < 0:
                row = self.repo.session.get(Lesson, lesson_id)
                if row is not None:
                    lesson.addItem(f'{row.date} [#{row.id}]', row.id)
            lesson.setCurrentIndex(lesson.findData(lesson_id))
        arrival = utc_editor()
        self.form('Attendance revision', {'lesson_id': ('Lesson', lesson),
            'mode': ('Mode', choices([('Correction', 'correction'), ('Arrival registration', 'arrival')])),
            'status': ('Status', options('present', 'absent', 'late', 'excused')),
            'reason': ('Reason', QTextEdit()), 'arrived_at': ('Arrived at UTC (late)', arrival)}, 'record_attendance',
            fixed={'student_id': student_id},
            transform=lambda d: {**d, 'arrived_at': d['arrived_at'] if d['status'] == 'late' else None})


class DefenseDialog(QDialog):
    """A checklist version is captured with the attempt, never edited in place."""
    def __init__(self, workspace, lab, versions):
        super().__init__(workspace)
        self.workspace, self.lab = workspace, lab
        self.student_id = workspace.student.currentData()
        self.operation_key = uuid4().hex
        self.setWindowTitle('Laboratory defense')
        self.resize(560, 540)
        outer = QVBoxLayout(self)
        outer.addWidget(QLabel(workspace.student.currentText()))
        self.version = choices([(f'Version {v.revision}', v.id) for v in versions])
        self.version.setCurrentIndex(len(versions) - 1)
        outer.addWidget(self.version)
        self.duration = spin(1, 180)
        self.duration.setValue(10)
        timer_row = QHBoxLayout()
        timer_row.addWidget(QLabel('Minutes'))
        timer_row.addWidget(self.duration)
        start = QPushButton('Start / restart timer')
        timer_row.addWidget(start)
        outer.addLayout(timer_row)
        self.clock = QLabel('Not started')
        outer.addWidget(self.clock)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.content = QWidget()
        self.body = QVBoxLayout(self.content)
        self.fields = QFormLayout()
        self.fields.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        self.body.addLayout(self.fields)
        scroll.setWidget(self.content)
        outer.addWidget(scroll)
        self.criteria = {}
        self.version.currentIndexChanged.connect(self.load_criteria)
        self.load_criteria()
        self.answer = QTextEdit()
        self.answer.setMaximumHeight(80)
        self.question_passed = QCheckBox('Additional question passed')
        self.completed = QCheckBox('Work completed')
        self.defended = QCheckBox('Defense attempted')
        self.passed = QCheckBox('Defense passed')
        self.points = QLineEdit('0.00')
        self.comment = QTextEdit()
        self.comment.setMaximumHeight(80)
        self.visit = workspace.visits()
        form = QFormLayout()
        form.addRow('Additional answer', self.answer)
        form.addRow(self.question_passed)
        form.addRow(self.completed)
        form.addRow(self.defended)
        form.addRow(self.passed)
        form.addRow('Points', self.points)
        form.addRow('Comment', self.comment)
        form.addRow('Consultation visit', self.visit)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        self.body.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        outer.addWidget(buttons)
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)
        self.timer = QTimer(self)
        self.timer.setInterval(250)
        self.timer.timeout.connect(self.tick)
        self.deadline = None
        start.clicked.connect(self.start_timer)
        self.finished.connect(lambda _: self.timer.stop())

    def load_criteria(self):
        while self.fields.rowCount():
            self.fields.removeRow(0)
        self.criteria.clear()
        for row in sorted(self.workspace.rows(ChecklistCriterion, ChecklistCriterion.version_id == self.version.currentData()),
                          key=lambda r: r.position):
            field = choices([('Not assessed', None), ('Yes', True), ('No', False)])
            self.fields.addRow(row.label, field)
            self.criteria[row.id] = field

    def start_timer(self):
        self.deadline = monotonic() + self.duration.value() * 60
        self.timer.start()
        self.tick()

    def tick(self):
        seconds = max(0, int(self.deadline - monotonic()))
        self.clock.setText(f'{seconds // 60:02}:{seconds % 60:02}' + (' | Last minute' if 0 < seconds <= 60 else ' | Time expired' if seconds == 0 else ''))
        self.clock.setStyleSheet('color: #b91c1c; font-weight: bold' if seconds <= 60 else '')
        if seconds == 0:
            self.timer.stop()

    def save(self):
        answers = {key: box.currentData() for key, box in self.criteria.items()}
        if any(answer is None for answer in answers.values()):
            self.workspace.warning('Assess every criterion explicitly.')
            return
        try:
            self.workspace.repo.teaching_action('record_attempt', event_id=self.lab.event_id,
                student_id=self.student_id, points=Decimal(self.points.text()), work_completed=self.completed.isChecked(),
                defended=self.defended.isChecked(), passed=self.passed.isChecked(), operation_key=self.operation_key,
                checklist_version_id=self.version.currentData(), answers=answers,
                additional_answer=self.answer.toPlainText(), question_passed=self.question_passed.isChecked(),
                comment=self.comment.toPlainText(), consultation_visit_id=self.visit.currentData())
        except (RepositoryError, ValueError, ArithmeticError) as exc:
            self.workspace.warning(exc)
            return
        self.accept()
