"""Headless teaching forms against a fresh, isolated repository database."""

import os
from datetime import date, timezone
from decimal import Decimal
from time import monotonic
from types import SimpleNamespace
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog,
    QDialogButtonBox, QLineEdit, QMessageBox, QTextEdit)
from sqlalchemy import select, text

from app.models import (AssessmentAttempt, AssessmentEvent, Consultation,
    ConsultationVisit, IndividualPlan, PlanEntry, PlanStage, ResultCorrection)
from app.ui.data import repository as repository_module
from app.ui.windows.teaching_workspace import DefenseDialog, TeachingWorkspace


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    font_path = Path('C:/Windows/Fonts/arial.ttf')
    if font_path.exists():
        font_id = QFontDatabase.addApplicationFont(str(font_path))
        families = QFontDatabase.applicationFontFamilies(font_id)
        if families:
            app.setFont(QFont(families[0], 9))
    monkeypatch.setattr(repository_module, 'DATABASE_URL', f"sqlite:///{tmp_path / 'test_teaching_ui.db'}")
    repo = repository_module.DiaryRepository()
    group = repo.create_group('UI group', None)
    student = repo.create_student(group, 'Ada', 'Lovelace')
    year = repo.academic_action('create_year', name='2030', start_date=date(2030, 1, 1), end_date=date(2031, 1, 1))
    term = repo.academic_action('create_term', year_id=year.id, name='Spring', start_date=date(2030, 1, 7), total_weeks=17)
    discipline = repo.academic_action('create_discipline', name='Programming')
    offering = repo.academic_action('create_offering', term_id=term.id, discipline_id=discipline.id,
                                    name='Course UI', group_ids=[group.id])
    module = repo.academic_action('create_module', offering_id=offering.id, name='Module UI', position=1,
                                 start_date=date(2030, 1, 7), end_date=date(2030, 2, 7))
    widget = TeachingWorkspace(SimpleNamespace(repository=repo), offering_id=offering.id, student_id=student.id)
    widget.test_module = module
    yield widget
    widget.close()
    repo.session.close()
    app.processEvents()


def submit(monkeypatch, values):
    def execute(dialog):
        for key, desired in values.items():
            field = dialog.findChild(QComboBox, key)
            if field is not None:
                index = field.findData(desired)
                assert index >= 0, key
                field.setCurrentIndex(index)
                continue
            field = dialog.findChild(QCheckBox, key)
            if field is not None:
                field.setChecked(desired)
                continue
            field = dialog.findChild(QTextEdit, key)
            if field is not None:
                field.setPlainText(str(desired))
                continue
            field = dialog.findChild(QLineEdit, key)
            assert field is not None, key
            field.setText(str(desired))
        dialog.findChild(QDialogButtonBox).accepted.emit()
        return dialog.result()
    monkeypatch.setattr(QDialog, 'exec', execute)


def create_event(workspace, category='checkpoint'):
    return workspace.repo.teaching_action('create_event', module_id=workspace.test_module.id,
        title='Assessment UI', category=category, max_points=Decimal('12.50'), required=True, attempt_policy='best')


def test_workspace_read_only_and_archived_names(workspace):
    repo = workspace.repo
    before = repo.session.scalar(text('SELECT total_changes()'))
    workspace.refresh()
    workspace.course_changed()
    assert repo.session.scalar(text('SELECT total_changes()')) == before
    assert 'Lovelace Ada' in workspace.student.currentText()
    assert 'UI group' in workspace.student.currentText()
    student = repo.session.get(repository_module.Student, workspace.student.currentData())
    repo.archive_student(student, reason='Graduated')
    workspace.reload_context(workspace.offering.currentData(), student.id)
    assert 'archived' in workspace.student.currentText()
    assert workspace.student.currentData() == student.id


def test_create_event_decimal_deadline_and_attempt(workspace, monkeypatch):
    submit(monkeypatch, {'title': 'Precise points', 'max_points': '12.50', 'attempt_policy': 'best', 'required': True, 'has_due': True})
    workspace.create_event()
    event = workspace.repo.session.scalar(select(AssessmentEvent))
    assert event.max_points == Decimal('12.50')
    assert event.due_at.tzinfo == timezone.utc
    submit(monkeypatch, {'event_id': event.id, 'points': '11.25', 'work_completed': True, 'passed': True})
    workspace.record_attempt()
    attempt = workspace.repo.session.scalar(select(AssessmentAttempt))
    assert attempt.points == Decimal('11.25')
    assert len(attempt.operation_key) == 32
    assert '11.25' in workspace.totals.text()
    submit(monkeypatch, {'attempt_id': attempt.id, 'points': '12.50', 'passed': True, 'reason': 'Reviewed'})
    workspace.correct_result()
    correction = workspace.repo.session.scalar(select(ResultCorrection))
    assert correction.reason == 'Reviewed'
    assert attempt.points == Decimal('11.25')


def test_form_error_keeps_dialog_open(workspace, monkeypatch):
    create_event(workspace)
    warnings = []
    monkeypatch.setattr(QMessageBox, 'warning', lambda *args: warnings.append(args[-1]))
    submit(monkeypatch, {'points': '99', 'passed': True, 'work_completed': True})
    workspace.record_attempt()
    assert warnings
    assert workspace.repo.session.scalar(select(AssessmentAttempt)) is None


def test_consultation_visit_and_plan_progress(workspace, monkeypatch):
    submit(monkeypatch, {'title': 'Consultation UI'})
    workspace.create_consultation()
    consultation = workspace.repo.session.scalar(select(Consultation))
    assert consultation.starts_at.tzinfo == timezone.utc
    submit(monkeypatch, {'purpose': 'Defense', 'question': 'Explain loops', 'comment': 'Prepared'})
    workspace.register_visit()
    visit = workspace.repo.session.scalar(select(ConsultationVisit))
    assert visit.student_id == workspace.student.currentData()
    submit(monkeypatch, {'title': 'Individual project'})
    workspace.create_plan()
    plan = workspace.repo.session.scalar(select(IndividualPlan))
    submit(monkeypatch, {'plan_id': plan.id, 'title': 'Prototype'})
    workspace.add_stage()
    stage = workspace.repo.session.scalar(select(PlanStage))
    submit(monkeypatch, {'stage_id': stage.id, 'completed': True, 'comment': 'Reviewed', 'consultation_visit_id': visit.id})
    workspace.record_progress()
    entry = workspace.repo.session.scalar(select(PlanEntry))
    assert entry.completed and entry.consultation_visit_id == visit.id
    event = create_event(workspace)
    submit(monkeypatch, {'event_id': event.id, 'points': '4.25', 'passed': True,
                        'work_completed': True, 'consultation_visit_id': visit.id})
    workspace.record_attempt()
    attempt = workspace.repo.session.scalar(select(AssessmentAttempt))
    assert attempt.consultation_visit_id == visit.id


def test_defense_version_answers_and_timer(workspace, monkeypatch, tmp_path):
    from app.models import ChecklistVersion
    event = create_event(workspace, 'lab')
    lab = workspace.repo.teaching_action('create_lab', event_id=event.id, title='Lab UI')
    workspace.repo.teaching_action('create_checklist', lab_id=lab.id, criteria=['Correct output', 'Explanation'])
    versions = workspace.rows(ChecklistVersion)
    dialog = DefenseDialog(workspace, lab, versions)
    dialog.resize(760, 560)
    dialog.show()
    QApplication.processEvents()
    assert dialog.width() <= 800 and dialog.height() <= 600
    assert dialog.rect().contains(dialog.clock.geometry())
    assert dialog.rect().contains(dialog.findChild(QDialogButtonBox).geometry())
    assert dialog.grab().save(str(tmp_path / 'defense.png'))
    dialog.start_timer()
    dialog.deadline = monotonic() + 30
    dialog.tick()
    assert 'Last minute' in dialog.clock.text()
    warnings = []
    monkeypatch.setattr(QMessageBox, 'warning', lambda *args: warnings.append(args[-1]))
    dialog.save()
    assert warnings and workspace.repo.session.scalar(select(AssessmentAttempt)) is None
    for field in dialog.criteria.values():
        field.setCurrentIndex(1)
    dialog.completed.setChecked(True)
    dialog.defended.setChecked(True)
    dialog.passed.setChecked(True)
    dialog.question_passed.setChecked(True)
    dialog.answer.setPlainText('Explanation')
    dialog.points.setText('12.50')
    dialog.save()
    assert dialog.result() == QDialog.DialogCode.Accepted
    attempt = workspace.repo.session.scalar(select(AssessmentAttempt))
    assert attempt.checklist_version_id == versions[0].id
    assert not dialog.timer.isActive()


def test_failed_defense_preserves_attempted_fact(workspace, monkeypatch):
    from app.models import ChecklistVersion
    event = create_event(workspace, 'lab')
    lab = workspace.repo.teaching_action('create_lab', event_id=event.id, title='Failed defense')
    workspace.repo.teaching_action('create_checklist', lab_id=lab.id, criteria=['Correct implementation'])
    dialog = DefenseDialog(workspace, lab, workspace.rows(ChecklistVersion))
    warnings = []
    monkeypatch.setattr(QMessageBox, 'warning', lambda *args: warnings.append(args[-1]))
    for field in dialog.criteria.values():
        field.setCurrentIndex(2)
    dialog.completed.setChecked(True)
    dialog.defended.setChecked(True)
    dialog.passed.setChecked(False)
    dialog.points.setText('0.00')
    dialog.answer.setPlainText('Could not explain the implementation')
    dialog.save()
    assert not warnings
    assert dialog.result() == QDialog.DialogCode.Accepted
    attempt = workspace.repo.session.scalar(select(AssessmentAttempt))
    assert attempt.work_completed is True
    assert attempt.defended is True
    assert attempt.passed is False
    assert attempt.points == Decimal('0.00')
    assert attempt.additional_answer == 'Could not explain the implementation'


def test_cancel_event_and_calendar_fields(workspace, monkeypatch):
    event = create_event(workspace)
    submit(monkeypatch, {'event_id': event.id, 'reason': 'Replaced'})
    workspace.cancel_event()
    assert workspace.repo.teaching_summary(workspace.offering.currentData(), workspace.student.currentData())['events'] == []
    calls = []
    monkeypatch.setattr(workspace, 'form', lambda *args, **kwargs: calls.append((args, kwargs)))
    workspace.lesson_status()
    data = calls[-1][1]['transform']({'status': 'held', 'new_date': date(2030, 2, 1)})
    assert data['new_date'] is None
    workspace.open_attendance_dialog(None, workspace.student.currentData())
    transform = calls[-1][1]['transform']
    assert transform({'status': 'present', 'arrived_at': 'unused'})['arrived_at'] is None


def test_failed_save_can_retry_same_dialog(workspace, monkeypatch):
    create_event(workspace)
    warnings = []
    monkeypatch.setattr(QMessageBox, 'warning', lambda *args: warnings.append(args[-1]))

    def execute(dialog):
        points = dialog.findChild(QLineEdit, 'points')
        dialog.findChild(QCheckBox, 'passed').setChecked(True)
        dialog.findChild(QCheckBox, 'work_completed').setChecked(True)
        buttons = dialog.findChild(QDialogButtonBox)
        points.setText('100.00')
        buttons.accepted.emit()
        assert dialog.result() != QDialog.DialogCode.Accepted
        points.setText('9.50')
        buttons.accepted.emit()
        return dialog.result()

    monkeypatch.setattr(QDialog, 'exec', execute)
    workspace.record_attempt()
    assert warnings
    attempts = workspace.rows(AssessmentAttempt)
    assert len(attempts) == 1 and attempts[0].points == Decimal('9.50')


def test_all_workflow_tabs_available_without_writes(workspace, tmp_path):
    before = workspace.repo.session.scalar(text('SELECT total_changes()'))
    workspace.resize(800, 600)
    workspace.show()
    QApplication.processEvents()
    for index in range(workspace.tabs.count()):
        workspace.tabs.setCurrentIndex(index)
        QApplication.processEvents()
        page = workspace.tabs.currentWidget()
        assert page.width() > 0 and page.height() > 0
        from PySide6.QtWidgets import QPushButton
        for button in page.findChildren(QPushButton):
            assert page.rect().contains(button.geometry())
            assert button.fontMetrics().horizontalAdvance(button.text()) < button.width()
        assert workspace.grab().save(str(tmp_path / f'tab_{index}.png'))
    assert workspace.tabs.count() == 6
    assert workspace.size().width() == 800 and workspace.size().height() == 600
    assert workspace.repo.session.scalar(text('SELECT total_changes()')) == before


@pytest.mark.parametrize('category', ['seminar_start', 'seminar_end'])
def test_seminar_lesson_context_saves(workspace, monkeypatch, category):
    from datetime import time
    from app.models import Lesson, Schedule
    repo = workspace.repo
    schedule = Schedule(offering_id=workspace.offering.currentData(), day='Monday', time=time(10),
                        type='Seminar', odd_or_even='both', effective_from=date(2030, 1, 7))
    repo.session.add(schedule)
    repo.session.flush()
    lesson = Lesson(schedule_id=schedule.id, date=date(2030, 1, 7))
    repo.session.add(lesson)
    repo.session.commit()
    workspace.lesson_id = lesson.id
    submit(monkeypatch, {'title': category, 'max_points': '3.75', 'attempt_policy': 'latest'})
    workspace.create_event(category=category)
    event = repo.session.scalar(select(AssessmentEvent))
    assert event.category == category and event.lesson_id == lesson.id
    assert event.max_points == Decimal('3.75') and event.attempt_policy == 'latest'
    assert event.due_at is None


def test_event_form_geometry_and_explicit_policy(workspace, monkeypatch, tmp_path):
    from PySide6.QtWidgets import QScrollArea, QPushButton
    def execute(dialog):
        dialog.resize(760, 560)
        dialog.show()
        QApplication.processEvents()
        assert dialog.width() <= 800 and dialog.height() <= 600
        assert dialog.rect().contains(dialog.findChild(QDialogButtonBox).geometry())
        assert dialog.findChild(QLineEdit, 'max_points').text() == ''
        assert dialog.findChild(QComboBox, 'attempt_policy').currentData() is None
        assert dialog.findChild(QScrollArea).widgetResizable()
        assert dialog.grab().save(str(tmp_path / 'event_form.png'))
        dialog.reject()
        return dialog.result()
    monkeypatch.setattr(QDialog, 'exec', execute)
    workspace.create_event()


@pytest.mark.parametrize('category,expected', [('additional', 'Oral examination'), ('checkpoint', None)])
def test_additional_event_custom_type(workspace, monkeypatch, category, expected):
    submit(monkeypatch, {'category': category, 'title': 'Assessment', 'custom_type': 'Oral examination',
                        'max_points': '7.50', 'attempt_policy': 'best'})
    workspace.create_event()
    event = workspace.repo.session.scalar(select(AssessmentEvent))
    assert event.custom_type == expected
    listing = workspace.lists['Results']
    labels = [listing.item(i).text() for i in range(listing.count())]
    assert any('Oral examination' in label for label in labels) == (expected is not None)


@pytest.mark.parametrize('status,mode', [('late', 'arrival'), ('late', 'correction'), ('present', 'correction')])
def test_fixed_roster_absence_revision(workspace, monkeypatch, status, mode):
    from datetime import datetime, time, timedelta
    from app.models import Attendance, AttendanceRevision, Lesson, LessonParticipant, Schedule, ScheduleGroupLink
    repo = workspace.repo
    schedule = Schedule(day='Monday', time=time(10), type='Seminar', odd_or_even='both', effective_from=date.today())
    repo.session.add(schedule)
    repo.session.flush()
    student_id = workspace.student.currentData()
    student = repo.session.get(repository_module.Student, student_id)
    repo.session.add(ScheduleGroupLink(schedule_id=schedule.id, group_id=student.group_id))
    repo.session.flush()
    lesson = Lesson(schedule_id=schedule.id, date=date.today())
    repo.session.add(lesson)
    repo.session.flush()
    repo.session.add(LessonParticipant(lesson_id=lesson.id, student_id=student_id, group_id=student.group_id))
    repo.session.add(Attendance(lesson_id=lesson.id, student_id=student_id, is_visited=False))
    repo.session.flush()
    completed = datetime.now(timezone.utc) - timedelta(minutes=5)
    lesson.participants_complete = True
    lesson.roster_completed_at = completed
    lesson.roster_time_basis = 'utc'
    repo.session.commit()
    submit(monkeypatch, {'status': status, 'mode': mode, 'reason': 'Teacher reviewed attendance'})
    workspace.open_attendance_dialog(lesson.id, student_id)
    revision = repo.session.scalar(select(AttendanceRevision))
    assert revision.status == status
    if status == 'late':
        assert revision.late_seconds >= 299
        assert revision.arrived_at is not None
    else:
        assert revision.arrived_at is None
        assert revision.late_seconds is None
    assert revision.reason == 'Teacher reviewed attendance'


def test_consultation_without_any_course(tmp_path, monkeypatch):
    monkeypatch.setattr(repository_module, 'DATABASE_URL', f"sqlite:///{tmp_path / 'test_no_course.db'}")
    app = QApplication.instance() or QApplication([])
    repo = repository_module.DiaryRepository()
    group = repo.create_group('Independent', None)
    student = repo.create_student(group, 'Grace', 'Hopper')
    page = TeachingWorkspace(SimpleNamespace(repository=repo), student_id=student.id)
    try:
        assert page.offering.count() == 0
        submit(monkeypatch, {'title': 'Open consultation'})
        page.create_consultation()
        submit(monkeypatch, {'purpose': 'Advice', 'question': 'Project scope'})
        page.register_visit()
        assert page.lists['Consultations'].count() == 2
        assert 'Hopper Grace' in page.lists['Consultations'].item(1).text()
        submit(monkeypatch, {'title': 'Independent project'})
        page.create_plan()
        assert page.lists['Plans'].count() == 1
        assert repo.session.scalar(select(ConsultationVisit)).student_id == student.id
    finally:
        page.close()
        repo.session.close()
        app.processEvents()
