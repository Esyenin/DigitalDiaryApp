"""Complete offscreen teacher workflow using actual Qt forms and services."""
import os
import tempfile
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from pypdf import PdfReader
from PySide6.QtCore import QDateTime, QTimeZone, Qt
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDateTimeEdit,
    QDialog, QDialogButtonBox, QFileDialog, QInputDialog, QLabel, QLineEdit, QMessageBox, QTextEdit)
from sqlalchemy import select, text

from app.models import (AssessmentAttempt, AssessmentEvent, AttendanceRevision, BehaviorEvent,
                        ConsultationVisit, LabWork, SeatAssignment, Student)
from app.services.journal_activity import ActivityService
from app.ui.data import repository as repository_module
from app.ui.windows.journal_workspace import JournalWorkspace
from app.ui.windows.reports_workspace import ReportsWorkspace
from app.ui.windows.seating_workspace import SeatingWorkspace, SeatItem
from app.ui.windows.sql_workspace import SQLWorkspace
from app.ui.windows.teaching_workspace import DefenseDialog, TeachingWorkspace
from app.ui.windows.ui_MainWindowsUI import MainWindow
from tests.test_journal_analytics import journal, make_lesson


def submit(monkeypatch, values):
    def execute(dialog):
        for key, expected in values.items():
            if isinstance(expected, datetime):
                field = dialog.findChild(QDateTimeEdit, key)
                assert field is not None, key
                field.setDateTime(QDateTime.fromSecsSinceEpoch(int(expected.timestamp()), QTimeZone.utc()))
                continue
            for cls in (QComboBox,QCheckBox,QTextEdit,QLineEdit):
                field = dialog.findChild(cls, key)
                if field is not None:
                    if cls is QComboBox:
                        index = field.findData(expected)
                        assert index >= 0, (key, expected)
                        field.setCurrentIndex(index)
                    elif cls is QCheckBox:
                        field.setChecked(expected)
                    elif cls is QTextEdit:
                        field.setPlainText(str(expected))
                    else:
                        field.setText(str(expected))
                    break
            else:
                raise AssertionError(key)
        dialog.findChild(QDialogButtonBox).accepted.emit()
        assert dialog.result() == QDialog.DialogCode.Accepted
        return dialog.result()
    monkeypatch.setattr(QDialog, 'exec', execute)


def test_end_to_end_teacher_journal_and_transfer_history(journal, tmp_path, monkeypatch):
    from app.ui.windows import reports_workspace
    monkeypatch.setattr(reports_workspace,'TemporaryDirectory',lambda **kwargs: tempfile.TemporaryDirectory(dir=tmp_path,**kwargs))
    source, term, course, module, groups, students = journal
    current = make_lesson(source, course, groups)
    source.academic_action('select_term', term.id)
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    repo = window.repository
    warnings = []
    monkeypatch.setattr(QMessageBox, 'warning', lambda *args: warnings.append(str(args[-1])))
    monkeypatch.setattr(QMessageBox, 'question', lambda *args: QMessageBox.StandardButton.Yes)
    try:
        window.show_teaching_workspace(offering_id=course.id,student_id=students[0].id,lesson_id=current.id)
        teaching = window.detail_page.findChild(TeachingWorkspace)
        submit(monkeypatch, dict(title='Beginning test',max_points='100',required=True,attempt_policy='best'))
        teaching.create_event(category='seminar_start')
        beginning = repo.session.scalar(select(AssessmentEvent))
        assert beginning.lesson_id == current.id
        completed = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(minutes=7)
        class Clock(datetime):
            @classmethod
            def now(cls,tz=None):
                return completed if tz else completed.replace(tzinfo=None)
        monkeypatch.setattr(repository_module,'datetime',Clock)
        current = repo.get_lesson(current.id)
        window.show_lesson_detail(current)
        window.complete_lesson_roll_call(current)
        assert current.participants_complete

        window.show_seating_workspace(current.id)
        seating = window.detail_page.findChild(SeatingWorkspace)
        monkeypatch.setattr(QInputDialog,'getText',lambda *a,**k:('Room 101',True))
        seating.new_room()
        seating.new_draft()
        monkeypatch.setattr(QInputDialog,'getText',lambda *a,**k:('A1',True))
        seating.add_seat()
        item = next(item for item in seating.scene.items() if isinstance(item,SeatItem))
        item.setPos(170,110)
        monkeypatch.setattr(QInputDialog,'getText',lambda *a,**k:('Two-person classroom',True))
        seating.save_draft()
        seating.attach()
        monkeypatch.setattr(QInputDialog,'getItem',lambda *a,**k:(a[3][0],True))
        monkeypatch.setattr(QInputDialog,'getText',lambda *a,**k:('Initial assignment',True))
        item = next(item for item in seating.scene.items() if isinstance(item,SeatItem))
        seating.change_assignment(item,False)
        assignment = repo.session.scalar(select(SeatAssignment))
        assert assignment.student_id == students[0].id

        window.show_teaching_workspace(offering_id=course.id,student_id=students[0].id,lesson_id=current.id)
        teaching = window.detail_page.findChild(TeachingWorkspace)
        submit(monkeypatch,dict(mode='arrival',status='late',reason='Late arrival',arrived_at=completed+timedelta(minutes=7)))
        teaching.open_attendance_dialog(current.id,students[0].id)
        revision = repo.session.scalar(select(AttendanceRevision))
        assert revision.status == 'late' and revision.late_seconds == 420
        window.record_behavior_for_student(current,repo.get_student(students[0].id),'Plagiarism')
        assert repo.session.scalar(select(BehaviorEvent)).student_id == students[0].id
        submit(monkeypatch,dict(event_id=beginning.id,points='90',work_completed=True,passed=True))
        teaching.record_attempt()
        submit(monkeypatch,dict(title='Laboratory',max_points='20',required=True,attempt_policy='best'))
        teaching.create_event(category='lab')
        submit(monkeypatch,dict(title='Laboratory 1'))
        teaching.create_lab()
        submit(monkeypatch,dict(criteria='Runs correctly\nExplains the algorithm'))
        teaching.create_checklist()

        def defense(passed, visit_id=None):
            def execute(dialog):
                if isinstance(dialog,DefenseDialog):
                    for field in dialog.criteria.values():
                        field.setCurrentIndex(field.findData(passed))
                    dialog.completed.setChecked(True)
                    dialog.defended.setChecked(True)
                    dialog.passed.setChecked(passed)
                    dialog.question_passed.setChecked(passed)
                    dialog.answer.setPlainText('Explained the algorithm' if passed else 'Needs more preparation')
                    dialog.points.setText('10' if passed else '0')
                    if visit_id is not None:
                        dialog.visit.setCurrentIndex(dialog.visit.findData(visit_id))
                    dialog.save()
                else:
                    dialog.accept()
                assert dialog.result() == QDialog.DialogCode.Accepted
                return dialog.result()
            monkeypatch.setattr(QDialog,'exec',execute)
            teaching.defend()
        defense(False)
        submit(monkeypatch,dict(title='Retake consultation'))
        teaching.create_consultation()
        submit(monkeypatch,dict(purpose='Laboratory retake',question='Clarify recursion',comment='Second defense'))
        teaching.register_visit()
        visit = repo.session.scalar(select(ConsultationVisit))
        defense(True,visit.id)
        assert repo.teaching_summary(course.id,students[0].id)['earned'] == Decimal(100)
        assert len(list(repo.session.scalars(select(AssessmentAttempt)))) == 3
        window.show_student_detail(repo.get_student(students[0].id))
        labels = [label.text() for label in window.detail_page.findChildren(QLabel)]
        assert any('Programming' in label for label in labels)
        window.show_journal_workspace(student_id=students[0].id,term_id=term.id)
        journal_view = window.detail_page.findChild(JournalWorkspace)
        assert journal_view.tables['Results'].rowCount() >= 2
        window.show_reports_workspace()
        reports = window.detail_page.findChild(ReportsWorkspace)
        reports.term.setCurrentIndex(reports.term.findData(term.id))
        path = tmp_path/'curator_acceptance.pdf'
        monkeypatch.setattr(QFileDialog,'getSaveFileName',lambda *a,**k:(str(path),'PDF'))
        before = repo.session.scalar(text('SELECT total_changes()'))
        reports.export()
        assert path.read_bytes().startswith(b'%PDF-')
        assert '100.00/120.00' in ''.join(page.extract_text() for page in PdfReader(path).pages)
        assert repo.session.scalar(text('SELECT total_changes()')) == before
        window.show_sql_workspace()
        sql = window.detail_page.findChild(SQLWorkspace)
        sql.editor.setPlainText('SELECT count(*) AS attempts FROM assessment_attempts WHERE finalized = 1')
        sql.run_query()
        assert sql.result['rows'] == [(3,)]
        sql.editor.setPlainText('DELETE FROM assessment_attempts')
        sql.run_query()
        assert sql.result is None

        original_ids = [row.id for row in repo.session.scalars(select(AssessmentAttempt))]
        student = repo.get_student(students[0].id)
        repo.transfer_student(student,repo.get_group(groups[1].id),date.today())
        repo.archive_student(student,reason='Archived after transfer')
        assert ActivityService(repo.session).seating(current.id)['assignments'][0].student_id == student.id
        assert ActivityService(repo.session).behavior_for_student(student.id)[0]['category'] == 'Plagiarism'
        assert list(repo.session.scalars(select(AssessmentAttempt.id))) == original_ids
        assert repo.journal_student(student.id,term_id=term.id)['courses'][0]['earned'] == 100
        assert not warnings, warnings
    finally:
        window.close()
        window.repository.engine.dispose()
        app.processEvents()
