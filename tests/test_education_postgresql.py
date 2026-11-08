"""Opt-in integration checks; never reuse or clear an existing database."""

import os

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError

from app.ui.data.academic_migration import ensure_academic_schema
from config import settings
from tests.test_education_guards import seed_education, attempt


@pytest.fixture(scope="module")
def pg_education():
    raw = os.environ.get("DIGITAL_DIARY_EDUCATION_POSTGRESQL_URL")
    if not raw:
        pytest.skip("No dedicated empty PostgreSQL education test database configured")
    url = make_url(raw)
    app_url = make_url(settings.get_db_url())
    if url.get_backend_name() != "postgresql" or not (url.database or "").startswith("test_"):
        pytest.fail("Education integration database must be PostgreSQL named test_*")
    if app_url.get_backend_name() == "postgresql" and app_url.database == url.database:
        pytest.fail("Education integration database cannot be the application database")
    engine = create_engine(url)
    try:
        if inspect(engine).get_table_names():
            pytest.fail("Education integration database must be empty; nothing was changed")
        ensure_academic_schema(engine)
        seed_education(engine)
        yield engine
    finally:
        # Do not destroy tables even in the explicitly allocated test database.
        engine.dispose()


def test_pg_direct_guards_and_allowed_noop(pg_education):
    with pg_education.connect() as c:
        tx = c.begin()
        c.exec_driver_sql("UPDATE assessment_events SET id=id WHERE id=1")
        attempt(c)
        with c.begin_nested() as nested:
            with pytest.raises(DBAPIError, match="immutable"):
                c.exec_driver_sql("UPDATE assessment_attempts SET points=9 WHERE id=1")
            nested.rollback()
        tx.rollback()


def test_pg_closed_term_and_module_overlap(pg_education):
    with pg_education.connect() as c:
        tx = c.begin()
        with c.begin_nested() as nested:
            with pytest.raises(DBAPIError, match="overlap"):
                c.exec_driver_sql("INSERT INTO teaching_modules (offering_id,name,position,start_date,end_date) VALUES (1,'Overlap',2,'2026-02-01','2026-04-01')")
            nested.rollback()
        c.exec_driver_sql("UPDATE academic_terms SET status='closed' WHERE id=1")
        with c.begin_nested() as nested:
            with pytest.raises(DBAPIError, match="closed"):
                attempt(c)
            nested.rollback()
        tx.rollback()


def test_pg_concurrent_module_inserts_serialize_on_term(pg_education):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    started = Event()

    def competing_insert():
        with pg_education.begin() as c:
            c.exec_driver_sql("SET LOCAL lock_timeout = '5s'")
            started.set()
            c.exec_driver_sql("INSERT INTO teaching_modules (offering_id,name,position,start_date,end_date) VALUES (1,'Competing',3,'2026-03-15','2026-04-15')")

    with ThreadPoolExecutor(max_workers=1) as pool:
        with pg_education.begin() as c:
            c.exec_driver_sql("INSERT INTO teaching_modules (offering_id,name,position,start_date,end_date) VALUES (1,'Winner',2,'2026-03-01','2026-04-01')")
            future = pool.submit(competing_insert)
            assert started.wait(3)
        with pytest.raises(DBAPIError, match="overlap"):
            future.result(timeout=10)


def test_pg_lab_finalize_requires_complete_answers(pg_education):
    from app.models import CriterionAnswer
    from tests.test_education_guards import lab_checklist

    with pg_education.connect() as c:
        tx = c.begin()
        lab_checklist(c)
        attempt(c, event_id=2, checklist_version_id=1, question_passed=True, finalize=False)
        with c.begin_nested() as nested:
            with pytest.raises(DBAPIError, match="complete and nonempty"):
                c.exec_driver_sql("UPDATE assessment_attempts SET finalized=TRUE WHERE id=1")
            nested.rollback()
        c.execute(CriterionAnswer.__table__.insert(), dict(attempt_id=1, criterion_id=1, satisfied=True))
        c.exec_driver_sql("UPDATE assessment_attempts SET finalized=TRUE WHERE id=1")
        with c.begin_nested() as nested:
            with pytest.raises(DBAPIError, match="immutable"):
                c.exec_driver_sql("UPDATE assessment_attempts SET finalized=FALSE WHERE id=1")
            nested.rollback()
        tx.rollback()
