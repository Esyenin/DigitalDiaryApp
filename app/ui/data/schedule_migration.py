"""Transactional, id-preserving upgrade of legacy schedule rows."""

import sqlite3
from pathlib import Path
from uuid import uuid4

from sqlalchemy import inspect, text

from app.models import Base


VERSION_COLUMNS = {"series_key", "revision", "effective_from", "effective_until"}


def _install_sqlite_history_guards(connection) -> None:
    statements = (
        "CREATE TRIGGER IF NOT EXISTS schedule_history_update BEFORE UPDATE ON schedules "
        "WHEN OLD.effective_until IS NOT NULL OR EXISTS "
        "(SELECT 1 FROM lessons WHERE schedule_id = OLD.id) BEGIN "
        "SELECT RAISE(ABORT, 'historical schedule version is immutable') WHERE "
        "NEW.series_key IS NOT OLD.series_key OR NEW.revision IS NOT OLD.revision OR "
        "NEW.effective_from IS NOT OLD.effective_from OR "
        "NEW.odd_or_even IS NOT OLD.odd_or_even OR NEW.type IS NOT OLD.type OR "
        "NEW.is_assessment IS NOT OLD.is_assessment OR NEW.day IS NOT OLD.day OR "
        "NEW.time IS NOT OLD.time OR "
        "(OLD.effective_until IS NOT NULL AND NEW.effective_until IS NOT OLD.effective_until) OR "
        "(NEW.effective_until IS NOT NULL AND EXISTS "
        "(SELECT 1 FROM lessons WHERE schedule_id = OLD.id AND date >= NEW.effective_until)); END",
        "CREATE TRIGGER IF NOT EXISTS schedule_history_delete BEFORE DELETE ON schedules "
        "WHEN OLD.effective_until IS NOT NULL OR EXISTS "
        "(SELECT 1 FROM lessons WHERE schedule_id = OLD.id) BEGIN "
        "SELECT RAISE(ABORT, 'historical schedule version cannot be deleted'); END",
        "CREATE TRIGGER IF NOT EXISTS schedule_link_history_insert BEFORE INSERT ON schedulegrouplinks "
        "WHEN EXISTS (SELECT 1 FROM schedules WHERE id = NEW.schedule_id AND "
        "(effective_until IS NOT NULL OR EXISTS "
        "(SELECT 1 FROM lessons WHERE schedule_id = NEW.schedule_id))) BEGIN "
        "SELECT RAISE(ABORT, 'historical group links are immutable'); END",
        "CREATE TRIGGER IF NOT EXISTS schedule_link_history_update BEFORE UPDATE ON schedulegrouplinks "
        "WHEN EXISTS (SELECT 1 FROM schedules WHERE id = OLD.schedule_id AND "
        "(effective_until IS NOT NULL OR EXISTS "
        "(SELECT 1 FROM lessons WHERE schedule_id = OLD.schedule_id))) BEGIN "
        "SELECT RAISE(ABORT, 'historical group links are immutable'); END",
        "CREATE TRIGGER IF NOT EXISTS schedule_link_history_delete BEFORE DELETE ON schedulegrouplinks "
        "WHEN EXISTS (SELECT 1 FROM schedules WHERE id = OLD.schedule_id AND "
        "(effective_until IS NOT NULL OR EXISTS "
        "(SELECT 1 FROM lessons WHERE schedule_id = OLD.schedule_id))) BEGIN "
        "SELECT RAISE(ABORT, 'historical group links are immutable'); END",
        "CREATE TRIGGER IF NOT EXISTS lesson_version_insert BEFORE INSERT ON lessons BEGIN "
        "SELECT RAISE(ABORT, 'lesson date is outside schedule version') WHERE NOT EXISTS "
        "(SELECT 1 FROM schedules WHERE id = NEW.schedule_id AND "
        "effective_from <= NEW.date AND "
        "(effective_until IS NULL OR NEW.date < effective_until)); END",
        "CREATE TRIGGER IF NOT EXISTS lesson_version_update BEFORE UPDATE OF schedule_id, date ON lessons BEGIN "
        "SELECT RAISE(ABORT, 'lesson date is outside schedule version') WHERE NOT EXISTS "
        "(SELECT 1 FROM schedules WHERE id = NEW.schedule_id AND "
        "effective_from <= NEW.date AND "
        "(effective_until IS NULL OR NEW.date < effective_until)); END",
    )
    for statement in statements:
        connection.exec_driver_sql(statement)


def _install_postgresql_history_guards(connection) -> None:
    connection.exec_driver_sql("""
        CREATE OR REPLACE FUNCTION guard_schedule_history() RETURNS trigger AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                IF OLD.effective_until IS NOT NULL OR EXISTS
                    (SELECT 1 FROM lessons WHERE schedule_id = OLD.id) THEN
                    RAISE EXCEPTION 'historical schedule version cannot be deleted';
                END IF;
                RETURN OLD;
            END IF;
            IF OLD.effective_until IS NOT NULL OR EXISTS
                (SELECT 1 FROM lessons WHERE schedule_id = OLD.id) THEN
                IF (NEW.series_key, NEW.revision, NEW.effective_from, NEW.odd_or_even,
                    NEW.type, NEW.is_assessment, NEW.day, NEW.time) IS DISTINCT FROM
                   (OLD.series_key, OLD.revision, OLD.effective_from, OLD.odd_or_even,
                    OLD.type, OLD.is_assessment, OLD.day, OLD.time)
                   OR (OLD.effective_until IS NOT NULL AND
                       NEW.effective_until IS DISTINCT FROM OLD.effective_until)
                   OR (NEW.effective_until IS NOT NULL AND EXISTS
                       (SELECT 1 FROM lessons WHERE schedule_id = OLD.id
                        AND date >= NEW.effective_until)) THEN
                    RAISE EXCEPTION 'historical schedule version is immutable';
                END IF;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """)
    connection.exec_driver_sql("""
        CREATE OR REPLACE FUNCTION guard_schedule_link_history() RETURNS trigger AS $$
        DECLARE target_id integer;
        BEGIN
            target_id := CASE WHEN TG_OP = 'INSERT' THEN NEW.schedule_id ELSE OLD.schedule_id END;
            IF EXISTS (SELECT 1 FROM schedules WHERE id = target_id AND
                (effective_until IS NOT NULL OR EXISTS
                (SELECT 1 FROM lessons WHERE schedule_id = target_id))) THEN
                RAISE EXCEPTION 'historical group links are immutable';
            END IF;
            IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """)
    connection.exec_driver_sql("""
        CREATE OR REPLACE FUNCTION guard_lesson_version() RETURNS trigger AS $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM schedules WHERE id = NEW.schedule_id AND
                effective_from <= NEW.date AND
                (effective_until IS NULL OR NEW.date < effective_until)) THEN
                RAISE EXCEPTION 'lesson date is outside schedule version';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """)
    for name, table, events, function in (
        ("schedule_history_update", "schedules", "UPDATE", "guard_schedule_history"),
        ("schedule_history_delete", "schedules", "DELETE", "guard_schedule_history"),
        ("schedule_link_history_insert", "schedulegrouplinks", "INSERT", "guard_schedule_link_history"),
        ("schedule_link_history_update", "schedulegrouplinks", "UPDATE", "guard_schedule_link_history"),
        ("schedule_link_history_delete", "schedulegrouplinks", "DELETE", "guard_schedule_link_history"),
        ("lesson_version_insert", "lessons", "INSERT", "guard_lesson_version"),
        ("lesson_version_update", "lessons", "UPDATE OF schedule_id, date", "guard_lesson_version"),
    ):
        connection.exec_driver_sql(f"DROP TRIGGER IF EXISTS {name} ON {table}")
        connection.exec_driver_sql(
            f"CREATE TRIGGER {name} BEFORE {events} ON {table} "
            f"FOR EACH ROW EXECUTE FUNCTION {function}()"
        )


def _backup_legacy_sqlite(engine) -> None:
    source_path = Path(engine.url.database).resolve()
    if not source_path.exists():
        return
    backup_path = source_path.with_name(
        f"{source_path.name}.pre-schedule-version-{uuid4().hex}.bak"
    )
    with sqlite3.connect(source_path) as source, sqlite3.connect(backup_path) as backup:
        source.backup(backup)


def _migrate(connection) -> None:
    inspector = inspect(connection)
    if not inspector.has_table("schedules"):
        Base.metadata.create_all(bind=connection)
    else:
        columns = {column["name"] for column in inspector.get_columns("schedules")}
        present = columns & VERSION_COLUMNS
        if present and present != VERSION_COLUMNS:
            raise RuntimeError("Schedule migration is incomplete; restore the backup before retrying.")
        if not present:
            for definition in (
                "series_key VARCHAR(36)",
                "revision INTEGER",
                "effective_from DATE",
                "effective_until DATE",
            ):
                connection.exec_driver_sql(f"ALTER TABLE schedules ADD COLUMN {definition}")
            ids = connection.execute(text("SELECT id FROM schedules")).scalars().all()
            for schedule_id in ids:
                earliest_lesson = connection.execute(
                    text("SELECT MIN(date) FROM lessons WHERE schedule_id = :schedule_id"),
                    {"schedule_id": schedule_id},
                ).scalar()
                start = min("1900-01-01", str(earliest_lesson)) if earliest_lesson else "1900-01-01"
                connection.execute(
                    text(
                        "UPDATE schedules SET series_key = :series_key, revision = 1, "
                        "effective_from = :effective_from WHERE id = :schedule_id"
                    ),
                    {
                        "series_key": str(uuid4()),
                        "schedule_id": schedule_id,
                        "effective_from": start,
                    },
                )

    Base.metadata.create_all(bind=connection)

    unique_names = {
        item["name"] for item in inspect(connection).get_unique_constraints("schedules")
    }
    if "uq_schedule_series_revision" not in unique_names:
        connection.exec_driver_sql(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_schedule_series_revision_idx "
            "ON schedules (series_key, revision)"
        )
    if connection.execute(text(
        "SELECT 1 FROM schedules WHERE series_key IS NULL OR revision IS NULL "
        "OR effective_from IS NULL LIMIT 1"
    )).scalar():
        raise RuntimeError("Schedule version backfill left incomplete rows.")
    if connection.dialect.name == "sqlite":
        for operation, exclusion in (("INSERT", ""), ("UPDATE", "AND id != OLD.id")):
            connection.exec_driver_sql(
                f"CREATE TRIGGER IF NOT EXISTS schedule_period_{operation.lower()} "
                f"BEFORE {operation} ON schedules BEGIN "
                "SELECT RAISE(ABORT, 'invalid schedule period') WHERE "
                "NEW.series_key IS NULL OR NEW.revision IS NULL OR "
                "NEW.revision < 1 OR "
                "NEW.effective_from IS NULL OR "
                "(NEW.effective_until IS NOT NULL AND NEW.effective_until <= NEW.effective_from); "
                "SELECT RAISE(ABORT, 'overlapping schedule periods') WHERE EXISTS ("
                "SELECT 1 FROM schedules WHERE series_key = NEW.series_key "
                f"{exclusion} AND effective_from < COALESCE(NEW.effective_until, '9999-12-31') "
                "AND NEW.effective_from < COALESCE(effective_until, '9999-12-31')); "
                "END"
            )
        _install_sqlite_history_guards(connection)
    elif connection.dialect.name == "postgresql":
        connection.exec_driver_sql("ALTER TABLE schedules ALTER COLUMN series_key SET NOT NULL")
        connection.exec_driver_sql("ALTER TABLE schedules ALTER COLUMN revision SET NOT NULL")
        connection.exec_driver_sql("ALTER TABLE schedules ALTER COLUMN effective_from SET NOT NULL")
        for constraint_name, expression in (
            ("ck_schedule_effective_period", "effective_until IS NULL OR effective_until > effective_from"),
            ("ck_schedule_revision_positive", "revision >= 1"),
        ):
            if not connection.execute(
                text("SELECT 1 FROM pg_constraint WHERE conname = :name "
                     "AND conrelid = 'schedules'::regclass"),
                {"name": constraint_name},
            ).scalar():
                connection.exec_driver_sql(
                    f"ALTER TABLE schedules ADD CONSTRAINT {constraint_name} CHECK ({expression})"
                )
        connection.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS btree_gist")
        if not connection.execute(
            text("SELECT 1 FROM pg_constraint WHERE conname = 'ex_schedule_period' "
                 "AND conrelid = 'schedules'::regclass")
        ).scalar():
            connection.exec_driver_sql(
                "ALTER TABLE schedules ADD CONSTRAINT ex_schedule_period "
                "EXCLUDE USING gist (series_key WITH =, "
                "daterange(effective_from, effective_until, '[)') WITH &&)"
            )
        _install_postgresql_history_guards(connection)


def ensure_schedule_schema(engine) -> None:
    if engine.dialect.name not in {"sqlite", "postgresql"}:
        raise RuntimeError("Schedule migrations support only SQLite and PostgreSQL.")
    if engine.dialect.name == "sqlite" and inspect(engine).has_table("schedules"):
        columns = {column["name"] for column in inspect(engine).get_columns("schedules")}
        if not (columns & VERSION_COLUMNS):
            _backup_legacy_sqlite(engine)

    with engine.connect() as connection:
        if engine.dialect.name == "sqlite":
            connection.exec_driver_sql("BEGIN IMMEDIATE")
        else:
            connection.begin()
            if inspect(connection).has_table("schedules"):
                connection.exec_driver_sql("LOCK TABLE schedules IN ACCESS EXCLUSIVE MODE")
        try:
            _migrate(connection)
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
