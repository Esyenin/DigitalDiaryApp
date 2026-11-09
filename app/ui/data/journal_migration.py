"""Snapshot existing SQLite data before metadata can create new journal tables."""
from pathlib import Path
import sqlite3
from uuid import uuid4

from sqlalchemy import inspect


def prepare_journal_upgrade(engine):
    if engine.dialect.name != 'sqlite' or engine.url.database in {None, '', ':memory:'}:
        return
    path = Path(engine.url.database).resolve()
    if not path.is_file():
        return
    with engine.connect() as connection:
        tables = set(inspect(connection).get_table_names())
        fields = {row['name'] for row in inspect(connection).get_columns('attendance_revisions')} if 'attendance_revisions' in tables else set()
        event_fields = {row['name'] for row in inspect(connection).get_columns('assessment_events')} if 'assessment_events' in tables else set()
    if 'students' not in tables or ({'classrooms', 'proof_documents', 'behavior_events'} <= tables
        and 'previous_status' in fields and 'configured_at' in event_fields):
        return
    target = path.with_name(path.name + '.pre-journal-' + uuid4().hex + '.bak')
    with sqlite3.connect(path) as source, sqlite3.connect(target) as backup:
        source.backup(backup)
