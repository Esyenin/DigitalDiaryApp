"""Additive proof migration and database-level append-only guards."""
from pathlib import Path
import sqlite3
from uuid import uuid4

from sqlalchemy import inspect

from app.models.attendance_proof import ProofDocument, ProofChunk


def ensure_proof_schema(engine):
    if engine.dialect.name not in {'sqlite', 'postgresql'}:
        raise ValueError('Proof migration supports SQLite and PostgreSQL only.')
    with engine.connect() as connection:
        if engine.dialect.name == 'sqlite':
            connection.exec_driver_sql('BEGIN IMMEDIATE')
        else:
            connection.begin()
            connection.exec_driver_sql("SELECT pg_advisory_xact_lock(73925112)")
        try:
            tables = set(inspect(connection).get_table_names())
            if tables and not {'proof_documents', 'proof_chunks'} <= tables:
                _backup(engine)
            ProofDocument.__table__.create(connection, checkfirst=True)
            ProofChunk.__table__.create(connection, checkfirst=True)
            install_proof_guards(connection)
            connection.commit()
        except Exception:
            connection.rollback()
            raise


def _backup(engine):
    """Back up SQLite locally; PostgreSQL backups are administrator-managed.

    PostgreSQL additive DDL runs in the migration transaction. No external
    executable or filesystem dump is required by application startup.
    """
    if engine.dialect.name == 'sqlite':
        if engine.url.database in {None, '', ':memory:'}:
            return
        path = Path(engine.url.database).resolve()
        target = path.with_name(path.name + '.pre-proof-' + uuid4().hex + '.bak')
        with sqlite3.connect(path) as source, sqlite3.connect(target) as backup:
            source.backup(backup)


def install_proof_guards(connection):
    pg = connection.dialect.name == 'postgresql'
    def guard(table, suffix, operation, condition):
        name = 'proof_' + table + '_' + suffix
        if pg:
            connection.exec_driver_sql(f"""CREATE OR REPLACE FUNCTION {name}() RETURNS trigger AS $$
                BEGIN IF {condition} THEN RAISE EXCEPTION 'immutable or invalid attendance proof'; END IF;
                RETURN {'OLD' if operation == 'DELETE' else 'NEW'}; END; $$ LANGUAGE plpgsql""")
            connection.exec_driver_sql(f'DROP TRIGGER IF EXISTS {name} ON {table}')
            connection.exec_driver_sql(f'CREATE TRIGGER {name} BEFORE {operation} ON {table} FOR EACH ROW EXECUTE FUNCTION {name}()')
        else:
            connection.exec_driver_sql(f'DROP TRIGGER IF EXISTS {name}')
            connection.exec_driver_sql(f"""CREATE TRIGGER {name} BEFORE {operation} ON {table}
                WHEN {condition} BEGIN SELECT RAISE(ABORT, 'immutable or invalid attendance proof'); END""")

    valid_revision = "EXISTS (SELECT 1 FROM attendance_revisions r WHERE r.id=NEW.revision_id AND r.status='excused')"
    closed = """EXISTS (SELECT 1 FROM attendance_revisions r JOIN attendances a ON a.id=r.attendance_id
        JOIN lessons l ON l.id=a.lesson_id JOIN schedules s ON s.id=l.schedule_id
        JOIN course_offerings o ON o.id=s.offering_id JOIN academic_terms t ON t.id=o.term_id
        WHERE r.id=NEW.revision_id AND t.status='closed')"""
    guard('proof_documents', 'insert', 'INSERT', f'NEW.sealed OR NOT ({valid_revision}) OR ({closed})')
    different = 'IS DISTINCT FROM' if pg else 'IS NOT'
    immutable = ' OR '.join(f'NEW.{c.name} {different} OLD.{c.name}'
        for c in ProofDocument.__table__.columns if c.name not in {'sealed', 'updated_at'})
    guard('proof_documents', 'update', 'UPDATE',
          f'OLD.sealed OR NOT NEW.sealed OR ({immutable}) OR ({closed}) OR NOT EXISTS (SELECT 1 FROM proof_chunks WHERE document_id=OLD.id)')
    guard('proof_documents', 'delete', 'DELETE', 'true')
    # Lock the document row on PostgreSQL so sealing cannot race chunk insertion.
    if pg:
        connection.exec_driver_sql("""CREATE OR REPLACE FUNCTION proof_chunk_lock() RETURNS trigger AS $$ BEGIN
            PERFORM id FROM proof_documents WHERE id=NEW.document_id FOR UPDATE;
            RETURN NEW; END; $$ LANGUAGE plpgsql""")
        connection.exec_driver_sql('DROP TRIGGER IF EXISTS proof_a_chunk_lock ON proof_chunks')
        connection.exec_driver_sql('CREATE TRIGGER proof_a_chunk_lock BEFORE INSERT ON proof_chunks FOR EACH ROW EXECUTE FUNCTION proof_chunk_lock()')
    guard('proof_chunks', 'insert', 'INSERT',
          'NOT EXISTS (SELECT 1 FROM proof_documents WHERE id=NEW.document_id AND NOT sealed)')
    guard('proof_chunks', 'update', 'UPDATE', 'true')
    guard('proof_chunks', 'delete', 'DELETE', 'true')
