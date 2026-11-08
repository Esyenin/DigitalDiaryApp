"""Academic upgrades preserve legacy identities and never reinterpret marks."""

from sqlalchemy import create_engine

from app.ui.data.academic_migration import ensure_academic_schema


def test_upgrade_adds_roster_basis_without_rewriting_legacy_rows(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test_legacy_education.db'}")
    with engine.begin() as c:
        # Minimal legacy schema, before academic context and roster time basis.
        c.exec_driver_sql("CREATE TABLE schedules (id INTEGER PRIMARY KEY, revision INTEGER, effective_until DATE)")
        c.exec_driver_sql("CREATE TABLE lessons (id INTEGER PRIMARY KEY, schedule_id INTEGER, date DATE, topic TEXT, participants_complete BOOLEAN)")
        c.exec_driver_sql("CREATE TABLE marks (id INTEGER PRIMARY KEY, lesson_id INTEGER, student_id INTEGER, score INTEGER)")
        c.exec_driver_sql("INSERT INTO schedules VALUES (41,1,NULL)")
        c.exec_driver_sql("INSERT INTO lessons VALUES (72,41,'2025-01-01','Legacy topic',0)")
        c.exec_driver_sql("INSERT INTO marks VALUES (93,72,21,5)")
    ensure_academic_schema(engine)
    backups = list(tmp_path.glob("test_legacy_education.db.pre-academic-*.bak"))
    assert len(backups) == 1
    ensure_academic_schema(engine)
    assert list(tmp_path.glob("test_legacy_education.db.pre-academic-*.bak")) == backups
    backup_engine = create_engine(f"sqlite:///{backups[0]}")
    with backup_engine.connect() as c:
        assert c.exec_driver_sql("SELECT id, topic FROM lessons").one() == (72, "Legacy topic")
        assert "roster_time_basis" not in {row[1] for row in c.exec_driver_sql("PRAGMA table_info(lessons)")}
        assert c.exec_driver_sql("SELECT id, score FROM marks").one() == (93, 5)
    backup_engine.dispose()
    with engine.connect() as c:
        assert c.exec_driver_sql("SELECT id, topic, roster_time_basis FROM lessons").one() == (72, "Legacy topic", "unknown")
        assert c.exec_driver_sql("SELECT id, score FROM marks").one() == (93, 5)
        assert c.exec_driver_sql("SELECT id, offering_id FROM schedules").one() == (41, None)
        assert c.exec_driver_sql("SELECT COUNT(*) FROM assessment_attempts").scalar() == 0
    engine.dispose()


def test_fresh_schema_and_memory_do_not_create_academic_backups(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test_fresh.db'}")
    ensure_academic_schema(engine)
    ensure_academic_schema(engine)
    engine.dispose()
    memory = create_engine("sqlite:///:memory:")
    with memory.begin() as c:
        c.exec_driver_sql("CREATE TABLE schedules (id INTEGER PRIMARY KEY, revision INTEGER, effective_until DATE)")
    ensure_academic_schema(memory)
    memory.dispose()
    assert not list(tmp_path.glob("*.bak"))


def test_upgrade_existing_attempts_does_not_infer_finalization(tmp_path):
    from sqlalchemy import MetaData
    from app.models import Base
    from tests.test_education_guards import seed_education

    engine = create_engine(f"sqlite:///{tmp_path / 'test_old_attempts.db'}")
    metadata = MetaData()
    for table in Base.metadata.sorted_tables:
        table.to_metadata(metadata)
    table = metadata.tables["assessment_attempts"]
    table._columns.remove(table.c.finalized)
    events = metadata.tables["assessment_events"]
    if "custom_type" in events.c:
        events._columns.remove(events.c.custom_type)
    metadata.create_all(engine)
    seed_education(engine)
    with engine.begin() as c:
        # Raw SQL represents a pre-finalization schema: no ORM finalized default.
        c.exec_driver_sql("INSERT INTO assessment_attempts (id,event_id,student_id,attempt_number,operation_key,occurred_at,work_completed,defended,passed,points,additional_answer,comment) VALUES (91,1,1,1,'old','2026-02-01',TRUE,TRUE,TRUE,5,'','')")
    ensure_academic_schema(engine)
    ensure_academic_schema(engine)
    with engine.connect() as c:
        assert c.exec_driver_sql("SELECT id,points,finalized FROM assessment_attempts").one() == (91, 5, False)
        assert c.exec_driver_sql("SELECT custom_type FROM assessment_events WHERE id=1").scalar() is None
    assert len(list(tmp_path.glob("test_old_attempts.db.pre-academic-*.bak"))) == 1
    engine.dispose()
