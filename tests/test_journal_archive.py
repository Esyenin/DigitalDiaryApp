"""Versioned journal archives use temporary databases and real restore guards."""
from copy import deepcopy
from uuid import uuid4

import pytest
from openpyxl import load_workbook
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from app.models import Base, Attendance, AttendanceRevision, Lesson, Student
from app.services.attendance_proof import ProofService
from app.services.journal_activity import ActivityService
from app.ui.data import repository as repository_module
from app.ui.data.teaching_archive import (export_archive, preview_archive,
    restore_archive, _validate, _decode, _encode, MANIFEST, NEW_TABLES, VERSION,
    V1_MISSING_COLUMNS)
from app.ui.data.activity_migration import ensure_activity_schema
from app.ui.data.proof_migration import ensure_proof_schema
from tests.test_teaching_archive import graph
from tests.test_attendance_proof import PNG


@pytest.fixture
def repos(tmp_path, monkeypatch):
    opened = []
    def create():
        monkeypatch.setattr(repository_module, 'DATABASE_URL',
            'sqlite:///' + str(tmp_path / ('test_' + uuid4().hex + '.db')))
        repo = repository_module.DiaryRepository()
        ensure_activity_schema(repo.engine)
        ensure_proof_schema(repo.engine)
        opened.append(repo)
        return repo
    yield create
    for repo in opened:
        repo.close()
        repo.engine.dispose()


def journal(repo):
    graph(repo)
    lesson = repo.session.scalar(select(Lesson))
    student = repo.session.scalar(select(Student))
    activity = ActivityService(repo.session)
    room = activity.create_room('Room')
    layout = activity.create_layout(room.id, 'Version 1', [
        dict(label='A', x=0.1, y=12.3456789012345), dict(label='B', x=90, y=20)])
    activity.attach_layout(lesson.id, layout.id)
    seats = activity.seating(lesson.id)['seats']
    activity.assign_seat(lesson.id, student.id, seats[0].id, 'Initial', 'seat1')
    activity.assign_seat(lesson.id, student.id, seats[1].id, 'Correction', 'seat2')
    category = activity.create_category('Helping', 'positive')
    behavior = activity.record_behavior(student.id, lesson.id, category.id, 'Helpful', 'teacher', 'behavior')
    activity.correct_behavior(behavior.id, student.id, 'Clarified')
    attendance = repo.session.scalar(select(Attendance))
    revision = AttendanceRevision(attendance_id=attendance.id, status='excused',
        reason='Medical', source='teacher', operation_key='excused')
    repo.session.add(revision)
    repo.session.flush()
    ProofService(repo.session).attach(revision.id, 'evidence.png', PNG)
    repo.session.commit()


def test_full_journal_roundtrip(repos, tmp_path):
    source, target = repos(), repos()
    journal(source)
    data = preview_archive(export_archive(source.session, tmp_path / 'full.xlsx'))
    assert data['seats'][0]['x'] == 0.1
    assert len(data['seat_assignments']) == 2
    restore_archive(target, data)
    second = preview_archive(export_archive(target.session, tmp_path / 'second.xlsx'))
    assert second == data
    assert ProofService(target.session).read(data['proof_documents'][0]['id'])[2] == PNG
    target.session.rollback()
    with pytest.raises(DBAPIError):
        target.session.execute(text("UPDATE proof_chunks SET data_text='bad'"))
    target.session.rollback()
    with pytest.raises(DBAPIError):
        target.session.execute(text('DELETE FROM behavior_corrections'))
    target.session.rollback()


def test_v1_exact_schema_upgrade(repos, tmp_path):
    source, target = repos(), repos()
    graph(source)
    path = export_archive(source.session, tmp_path / 'old.xlsx')
    wb = load_workbook(path)
    manifest = list(wb[MANIFEST].values)
    del wb[MANIFEST]
    sheet = wb.create_sheet(MANIFEST, 0)
    sheet.append([manifest[0][0], 1])
    for row in manifest[1:]:
        if row[0] not in NEW_TABLES and row[1] not in V1_MISSING_COLUMNS.get(row[0], ()):
            sheet.append(row)
    for table, missing in V1_MISSING_COLUMNS.items():
        sheet = wb[table]
        for index in range(sheet.max_column, 0, -1):
            if sheet.cell(1, index).value in missing:
                sheet.delete_cols(index)
    for name in NEW_TABLES:
        del wb[name]
    wb.save(path)
    wb.close()
    data = preview_archive(path)
    assert all(not data[name] for name in NEW_TABLES)
    assert data['attendance_revisions']
    assert all(row[name] is None for row in data['attendance_revisions']
               for name in V1_MISSING_COLUMNS['attendance_revisions'])
    restore_archive(target, data)
    assert preview_archive(export_archive(target.session, tmp_path / 'upgraded.xlsx')) == data
    wb = load_workbook(path)
    wb[MANIFEST].delete_rows(3)
    wb.save(path)
    wb.close()
    with pytest.raises(ValueError, match='manifest'):
        preview_archive(path)


def test_existing_sqlite_upgrade_backs_up_before_changes_and_keeps_ids(repos, monkeypatch):
    from pathlib import Path
    source = repos()
    graph(source)
    url = source.engine.url.render_as_string(hide_password=False)
    tables = [table for table in Base.metadata.sorted_tables if table.name not in NEW_TABLES]
    def snapshot(session):
        return {table.name: [tuple(row) for row in session.execute(select(*[
            column for column in table.columns if column.name not in V1_MISSING_COLUMNS.get(table.name, ())
        ]).order_by(table.c.id))] for table in tables}
    before = snapshot(source.session)
    source.close()
    # Only this fixture's newly created private database is downgraded. No
    # application URL, global test engine or existing data file is used.
    with source.engine.begin() as connection:
        names = connection.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='trigger'").scalars().all()
        quote = source.engine.dialect.identifier_preparer.quote
        for name in names:
            connection.exec_driver_sql('DROP TRIGGER ' + quote(name))
        for table, columns in V1_MISSING_COLUMNS.items():
            for column in columns:
                connection.exec_driver_sql(f'ALTER TABLE {quote(table)} DROP COLUMN {quote(column)}')
        for table in reversed(Base.metadata.sorted_tables):
            if table.name in NEW_TABLES:
                table.drop(connection)
    source.engine.dispose()
    monkeypatch.setattr(repository_module, 'DATABASE_URL', url)
    upgraded = repository_module.DiaryRepository()
    try:
        assert snapshot(upgraded.session) == before
        assert all(row[0] is None for row in upgraded.session.execute(
            select(Base.metadata.tables['assessment_events'].c.configured_at)))
        path = Path(upgraded.engine.url.database)
        backups = list(path.parent.glob(path.name + '.pre-journal-*.bak'))
        assert len(backups) == 1
        import sqlite3
        with sqlite3.connect(backups[0]) as connection:
            old_tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            assert not old_tables.intersection(NEW_TABLES)
        upgraded.close()
        repeated = repository_module.DiaryRepository()
        try:
            assert snapshot(repeated.session) == before
            assert len(list(path.parent.glob(path.name + '.pre-journal-*.bak'))) == 1
        finally:
            repeated.close()
            repeated.engine.dispose()
    finally:
        upgraded.close()
        upgraded.engine.dispose()


@pytest.mark.parametrize('mutation', ['hash', 'filename', 'encoding', 'unsealed', 'chain',
    'seat', 'source', 'participant', 'coordinates'])
def test_corrupt_journal_rejected_before_writes(repos, tmp_path, mutation):
    source, target = repos(), repos()
    journal(source)
    data = preview_archive(export_archive(source.session, tmp_path / 'full.xlsx'))
    if mutation == 'hash':
        data['proof_documents'][0]['sha256'] = '0' * 64
    elif mutation == 'filename':
        data['proof_documents'][0]['filename'] = '../evidence.png'
    elif mutation == 'encoding':
        data['proof_chunks'][0]['data_text'] = '!bad'
    elif mutation == 'unsealed':
        data['proof_documents'][0]['sealed'] = False
    elif mutation == 'chain':
        data['seat_assignments'][1]['previous_id'] = None
    elif mutation == 'seat':
        data['seat_assignments'][0]['seat_id'] = 999999
    elif mutation == 'source':
        data['behavior_corrections'][0]['source'] = ' '
    elif mutation == 'participant':
        data['behavior_corrections'][0]['student_id'] = 999999
    else:
        data['seats'][0]['x'] = float('nan')
    with pytest.raises(ValueError):
        restore_archive(target, data)
    assert all(target.session.scalar(select(t.c.id).limit(1)) is None for t in Base.metadata.sorted_tables)


def test_float_codec():
    from app.models.journal_activity import Seat
    column = Seat.__table__.c.x
    for value in (0.1, -0.0, 10000.0, 12.345678901234567):
        assert _decode(_encode(value, column), column) == value
    for value in ('nan', 'inf', '-inf'):
        with pytest.raises(ValueError):
            _decode(value, column)


def test_restore_error_rolls_back_data_and_guards(repos, tmp_path, monkeypatch):
    source, target = repos(), repos()
    journal(source)
    data = preview_archive(export_archive(source.session, tmp_path / 'full.xlsx'))
    def fail():
        raise ValueError('injected restore failure')
    original = target._validate_restored_history
    monkeypatch.setattr(target, '_validate_restored_history', fail)
    with pytest.raises(ValueError, match='injected'):
        restore_archive(target, data)
    assert all(target.session.scalar(select(t.c.id).limit(1)) is None for t in Base.metadata.sorted_tables)
    target.session.rollback()
    monkeypatch.setattr(target, '_validate_restored_history', original)
    restore_archive(target, data)
    assert preview_archive(export_archive(target.session, tmp_path / 'restored.xlsx')) == data


def test_future_attendance_archive_rejected(repos, tmp_path):
    from datetime import timedelta
    source = repos()
    graph(source)
    data = preview_archive(export_archive(source.session, tmp_path / 'full.xlsx'))
    data['lessons'][0]['date'] += timedelta(days=1)
    with pytest.raises(ValueError, match='future attendance'):
        _validate(data)


def test_multichunk_proof_xlsx_roundtrip(repos, tmp_path):
    import hashlib
    from PySide6.QtCore import QBuffer, QIODevice
    from PySide6.QtGui import QImage
    source, target = repos(), repos()
    journal(source)
    pixels = b''.join(hashlib.sha256(str(i).encode()).digest() for i in range(1024))[:30000]
    image = QImage(pixels, 100, 100, 300, QImage.Format_RGB888)
    buffer = QBuffer()
    buffer.open(QIODevice.WriteOnly)
    assert image.save(buffer, 'PNG')
    content = bytes(buffer.data())
    assert len(content) > 12000
    revision = source.session.scalar(select(AttendanceRevision).where(AttendanceRevision.status == 'excused'))
    doc = ProofService(source.session).attach(revision.id, 'large.png', content)
    source.session.commit()
    key = doc.id
    data = preview_archive(export_archive(source.session, tmp_path / 'large.xlsx'))
    assert sum(r['document_id'] == key for r in data['proof_chunks']) > 1
    assert max(len(r['data_text']) for r in data['proof_chunks']) <= 12000
    restore_archive(target, data)
    assert ProofService(target.session).read(key)[2] == content


def test_known_previous_state_replays_from_initial_projection(repos, tmp_path):
    source, target = repos(), repos()
    journal(source)
    data = preview_archive(export_archive(source.session, tmp_path / 'known.xlsx'))
    revisions = sorted(data['attendance_revisions'], key=lambda row: row['id'])
    assert revisions[-1]['status'] == 'excused'
    assert all(row['status'] == 'present' for row in revisions[:-1])
    revisions[0]['previous_status'] = 'present'
    for previous, revision in zip(revisions, revisions[1:]):
        revision['previous_status'] = previous['status']
    assert data['attendances'][0]['is_visited'] is False
    restore_archive(target, data)
    assert preview_archive(export_archive(target.session, tmp_path / 'restored.xlsx')) == data
    broken = deepcopy(data)
    broken['attendance_revisions'][1]['previous_status'] = 'absent'
    with pytest.raises(ValueError, match='revision chain'):
        _validate(broken)
