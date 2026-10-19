"""Id-preserving upgrade for group membership and lesson participation."""

import sqlite3
from datetime import date
from pathlib import Path
from uuid import uuid4

from sqlalchemy import inspect, text

from app.models import Base


def _add_missing_columns(connection) -> None:
    specifications = {
        "students": {
            "status": "VARCHAR(16) NOT NULL DEFAULT 'active'",
            "archived_at": "DATE",
            "archive_reason": "VARCHAR(512)",
        },
        "groups": {
            "is_archived": "BOOLEAN NOT NULL DEFAULT false",
            "archive_reason": "VARCHAR(512)",
        },
        "lessons": {
            "participants_complete": "BOOLEAN NOT NULL DEFAULT false",
            "roster_origin": "VARCHAR(24) NOT NULL DEFAULT 'legacy_unknown'",
        },
        "lessonparticipants": {
            "group_id": "INTEGER REFERENCES groups(id)",
        },
    }
    for table, fields in specifications.items():
        if not inspect(connection).has_table(table):
            continue
        existing = {column["name"] for column in inspect(connection).get_columns(table)}
        for name, definition in fields.items():
            if name not in existing:
                connection.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")


def _sqlite_guards(connection) -> None:
    connection.exec_driver_sql("""
        CREATE TRIGGER IF NOT EXISTS membership_overlap_insert
        BEFORE INSERT ON groupmemberships BEGIN
        SELECT RAISE(ABORT, 'overlapping group memberships') WHERE EXISTS (
          SELECT 1 FROM groupmemberships WHERE student_id = NEW.student_id
          AND start_date < COALESCE(NEW.end_date, '9999-12-31')
          AND NEW.start_date < COALESCE(end_date, '9999-12-31'));
        END
    """)
    connection.exec_driver_sql("""
        CREATE TRIGGER IF NOT EXISTS membership_update_guard
        BEFORE UPDATE ON groupmemberships BEGIN
        SELECT RAISE(ABORT, 'membership history is immutable') WHERE
          NEW.student_id IS NOT OLD.student_id OR NEW.group_id IS NOT OLD.group_id
          OR NEW.start_date IS NOT OLD.start_date OR NEW.origin IS NOT OLD.origin
          OR NEW.known_from IS NOT OLD.known_from
          OR (OLD.end_date IS NOT NULL AND NEW.end_date IS NOT OLD.end_date)
          OR (NEW.end_date IS NOT NULL AND NEW.end_date < NEW.start_date);
        SELECT RAISE(ABORT, 'overlapping group memberships') WHERE EXISTS (
          SELECT 1 FROM groupmemberships WHERE student_id = NEW.student_id
          AND id != OLD.id
          AND start_date < COALESCE(NEW.end_date, '9999-12-31')
          AND NEW.start_date < COALESCE(end_date, '9999-12-31'));
        END
    """)
    connection.exec_driver_sql("""
        CREATE TRIGGER IF NOT EXISTS membership_delete_guard
        BEFORE DELETE ON groupmemberships BEGIN
        SELECT RAISE(ABORT, 'membership history cannot be deleted'); END
    """)
    connection.exec_driver_sql("""
        CREATE TRIGGER IF NOT EXISTS student_membership_insert
        AFTER INSERT ON students BEGIN
        INSERT INTO groupmemberships (student_id, group_id, start_date, origin, known_from)
        VALUES (NEW.id, NEW.group_id, date('now'), 'recorded', date('now'));
        END
    """)
    connection.exec_driver_sql("""
        CREATE TRIGGER IF NOT EXISTS student_group_update
        BEFORE UPDATE OF group_id ON students WHEN NEW.group_id != OLD.group_id BEGIN
        SELECT RAISE(ABORT, 'transfer requires a membership period') WHERE NOT EXISTS (
          SELECT 1 FROM groupmemberships WHERE student_id = OLD.id
          AND group_id = NEW.group_id AND start_date <= date('now') AND end_date IS NULL);
        SELECT RAISE(ABORT, 'cannot transfer to an archived group') WHERE EXISTS (
          SELECT 1 FROM groups WHERE id = NEW.group_id AND is_archived = 1);
        END
    """)
    connection.exec_driver_sql("""
        CREATE TRIGGER IF NOT EXISTS student_status_insert
        BEFORE INSERT ON students WHEN NEW.status != 'active' OR NEW.archived_at IS NOT NULL BEGIN
        SELECT RAISE(ABORT, 'create an active student before archiving'); END
    """)
    connection.exec_driver_sql("""
        CREATE TRIGGER IF NOT EXISTS student_status_update
        BEFORE UPDATE OF status, archived_at, archive_reason ON students BEGIN
        SELECT RAISE(ABORT, 'invalid student status') WHERE
          NEW.status NOT IN ('active', 'archived');
        SELECT RAISE(ABORT, 'archived students cannot be reactivated') WHERE
          OLD.status = 'archived' AND NEW.status != 'archived';
        SELECT RAISE(ABORT, 'active student cannot have an archive date') WHERE
          NEW.status = 'active' AND NEW.archived_at IS NOT NULL;
        SELECT RAISE(ABORT, 'archive requires closing membership') WHERE
          NEW.status = 'archived' AND (
            NEW.archived_at IS NULL OR NEW.archived_at > date('now')
            OR COALESCE(TRIM(NEW.archive_reason), '') = '' OR EXISTS (
              SELECT 1 FROM groupmemberships WHERE student_id = OLD.id AND end_date IS NULL
            )
          );
        END
    """)
    connection.exec_driver_sql("""
        CREATE TRIGGER IF NOT EXISTS student_delete_history
        BEFORE DELETE ON students BEGIN
        SELECT RAISE(ABORT, 'archive students instead of deleting them'); END
    """)
    connection.exec_driver_sql("""
        CREATE TRIGGER IF NOT EXISTS group_delete_history
        BEFORE DELETE ON groups BEGIN
        SELECT RAISE(ABORT, 'archive groups instead of deleting them'); END
    """)
    connection.exec_driver_sql("""
        CREATE TRIGGER IF NOT EXISTS group_archive_guard
        BEFORE UPDATE OF is_archived ON groups WHEN NEW.is_archived = 1 BEGIN
        SELECT RAISE(ABORT, 'group is still in use') WHERE EXISTS (
          SELECT 1 FROM students WHERE group_id = OLD.id AND status = 'active'
        ) OR EXISTS (
          SELECT 1 FROM schedulegrouplinks AS link
          JOIN schedules AS schedule ON schedule.id = link.schedule_id
          WHERE link.group_id = OLD.id AND (
            schedule.effective_until IS NULL OR schedule.effective_until > date('now')
          )
        );
        END
    """)
    connection.exec_driver_sql("""
        CREATE TRIGGER IF NOT EXISTS participant_update_guard
        BEFORE UPDATE ON lessonparticipants BEGIN
        SELECT RAISE(ABORT, 'lesson participation is immutable'); END
    """)
    connection.exec_driver_sql("""
        CREATE TRIGGER IF NOT EXISTS participant_insert_guard
        BEFORE INSERT ON lessonparticipants BEGIN
        SELECT RAISE(ABORT, 'fixed lesson roster is immutable') WHERE EXISTS (
          SELECT 1 FROM lessons WHERE id = NEW.lesson_id AND participants_complete = 1
        );
        SELECT RAISE(ABORT, 'participant group is not linked to the lesson') WHERE
          NEW.group_id IS NOT NULL AND NOT EXISTS (
            SELECT 1 FROM lessons AS lesson
            JOIN schedulegrouplinks AS link ON link.schedule_id = lesson.schedule_id
            WHERE lesson.id = NEW.lesson_id AND link.group_id = NEW.group_id
          );
        END
    """)
    connection.exec_driver_sql("""
        CREATE TRIGGER IF NOT EXISTS participant_delete_guard
        BEFORE DELETE ON lessonparticipants BEGIN
        SELECT RAISE(ABORT, 'lesson participation is immutable'); END
    """)
    connection.exec_driver_sql("""
        CREATE TRIGGER IF NOT EXISTS lesson_roster_guard
        BEFORE UPDATE OF participants_complete, roster_origin ON lessons BEGIN
        SELECT RAISE(ABORT, 'fixed lesson roster is immutable') WHERE
            OLD.participants_complete = 1 AND (
                NEW.participants_complete != 1 OR NEW.roster_origin IS NOT OLD.roster_origin
            );
        SELECT RAISE(ABORT, 'lesson results require roster participants') WHERE
          NEW.participants_complete = 1 AND OLD.participants_complete = 0
          AND (
            EXISTS (SELECT 1 FROM attendances AS result WHERE result.lesson_id = OLD.id
                    AND NOT EXISTS (SELECT 1 FROM lessonparticipants AS participant
                                    WHERE participant.lesson_id = OLD.id
                                    AND participant.student_id = result.student_id))
            OR EXISTS (SELECT 1 FROM marks AS result WHERE result.lesson_id = OLD.id
                    AND NOT EXISTS (SELECT 1 FROM lessonparticipants AS participant
                                    WHERE participant.lesson_id = OLD.id
                                    AND participant.student_id = result.student_id))
            OR EXISTS (SELECT 1 FROM comments AS result WHERE result.lesson_id = OLD.id
                    AND NOT EXISTS (SELECT 1 FROM lessonparticipants AS participant
                                    WHERE participant.lesson_id = OLD.id
                                    AND participant.student_id = result.student_id))
          );
        END
    """)
    lesson_protected = (
        "COALESCE(TRIM(OLD.topic), '') != '' "
        "OR OLD.participants_complete = 1 "
        "OR EXISTS (SELECT 1 FROM lessonparticipants WHERE lesson_id = OLD.id) "
        "OR EXISTS (SELECT 1 FROM attendances WHERE lesson_id = OLD.id) "
        "OR EXISTS (SELECT 1 FROM marks WHERE lesson_id = OLD.id) "
        "OR EXISTS (SELECT 1 FROM comments WHERE lesson_id = OLD.id)"
    )
    connection.exec_driver_sql(f"""
        CREATE TRIGGER IF NOT EXISTS lesson_history_delete
        BEFORE DELETE ON lessons BEGIN
        SELECT RAISE(ABORT, 'lesson history cannot be deleted') WHERE {lesson_protected};
        END
    """)
    connection.exec_driver_sql(f"""
        CREATE TRIGGER IF NOT EXISTS lesson_history_move
        BEFORE UPDATE OF schedule_id, date ON lessons BEGIN
        SELECT RAISE(ABORT, 'lesson history cannot be moved') WHERE
          (NEW.schedule_id IS NOT OLD.schedule_id OR NEW.date IS NOT OLD.date)
          AND ({lesson_protected});
        END
    """)
    for table in ("attendances", "marks", "comments"):
        for action in ("INSERT", "UPDATE"):
            connection.exec_driver_sql(f"""
                CREATE TRIGGER IF NOT EXISTS {table}_roster_{action.lower()}
                BEFORE {action} ON {table} BEGIN
                SELECT RAISE(ABORT, 'student is outside fixed lesson roster') WHERE
                  EXISTS (SELECT 1 FROM lessons WHERE id = NEW.lesson_id
                          AND participants_complete = 1)
                  AND NOT EXISTS (
                    SELECT 1 FROM lessonparticipants
                    WHERE lesson_id = NEW.lesson_id AND student_id = NEW.student_id
                  );
                END
            """)


def _postgresql_guards(connection) -> None:
    connection.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS btree_gist")
    if not connection.execute(text(
        "SELECT 1 FROM pg_constraint WHERE conname = 'ex_group_membership_period' "
        "AND conrelid = 'groupmemberships'::regclass"
    )).scalar():
        connection.exec_driver_sql(
            "ALTER TABLE groupmemberships ADD CONSTRAINT ex_group_membership_period "
            "EXCLUDE USING gist (student_id WITH =, "
            "daterange(start_date, end_date, '[)') WITH &&)"
        )


    connection.exec_driver_sql("""
        CREATE OR REPLACE FUNCTION guard_membership_change() RETURNS trigger AS $$
        BEGIN
          IF TG_OP = 'DELETE' THEN
            RAISE EXCEPTION 'membership history cannot be deleted';
          END IF;
          IF (NEW.student_id, NEW.group_id, NEW.start_date, NEW.origin, NEW.known_from)
             IS DISTINCT FROM
             (OLD.student_id, OLD.group_id, OLD.start_date, OLD.origin, OLD.known_from)
             OR (OLD.end_date IS NOT NULL AND NEW.end_date IS DISTINCT FROM OLD.end_date)
             OR (NEW.end_date IS NOT NULL AND NEW.end_date < NEW.start_date) THEN
            RAISE EXCEPTION 'membership history is immutable';
          END IF;
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """)
    connection.exec_driver_sql("""
        CREATE OR REPLACE FUNCTION guard_student_history() RETURNS trigger AS $$
        BEGIN
          IF TG_OP = 'DELETE' THEN
            RAISE EXCEPTION 'archive students instead of deleting them';
          END IF;
          IF NEW.group_id IS DISTINCT FROM OLD.group_id AND NOT EXISTS (
            SELECT 1 FROM groupmemberships WHERE student_id = OLD.id
            AND group_id = NEW.group_id AND start_date <= CURRENT_DATE AND end_date IS NULL
          ) THEN
            RAISE EXCEPTION 'transfer requires a membership period';
          END IF;
          IF NEW.group_id IS DISTINCT FROM OLD.group_id AND EXISTS (
            SELECT 1 FROM groups WHERE id = NEW.group_id AND is_archived
          ) THEN
            RAISE EXCEPTION 'cannot transfer to an archived group';
          END IF;
          IF OLD.status = 'archived' AND NEW.status != 'archived' THEN
            RAISE EXCEPTION 'archived students cannot be reactivated';
          END IF;
          IF NEW.status NOT IN ('active', 'archived') THEN
            RAISE EXCEPTION 'invalid student status';
          END IF;
          IF NEW.status = 'active' AND NEW.archived_at IS NOT NULL THEN
            RAISE EXCEPTION 'active student cannot have an archive date';
          END IF;
          IF NEW.status = 'archived' AND (
            NEW.archived_at IS NULL OR NEW.archived_at > CURRENT_DATE
            OR COALESCE(BTRIM(NEW.archive_reason), '') = '' OR EXISTS (
              SELECT 1 FROM groupmemberships WHERE student_id = OLD.id AND end_date IS NULL
            )
          ) THEN
            RAISE EXCEPTION 'archive requires closing membership';
          END IF;
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """)
    connection.exec_driver_sql("""
        CREATE OR REPLACE FUNCTION guard_student_insert() RETURNS trigger AS $$
        BEGIN
          IF NEW.status != 'active' OR NEW.archived_at IS NOT NULL THEN
            RAISE EXCEPTION 'create an active student before archiving';
          END IF;
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """)
    connection.exec_driver_sql("""
        CREATE OR REPLACE FUNCTION create_student_membership() RETURNS trigger AS $$
        BEGIN
          INSERT INTO groupmemberships (student_id, group_id, start_date, origin, known_from)
          VALUES (NEW.id, NEW.group_id, CURRENT_DATE, 'recorded', CURRENT_DATE);
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """)
    connection.exec_driver_sql("""
        CREATE OR REPLACE FUNCTION guard_group_delete() RETURNS trigger AS $$
        BEGIN
          RAISE EXCEPTION 'archive groups instead of deleting them';
        END;
        $$ LANGUAGE plpgsql
    """)
    connection.exec_driver_sql("""
        CREATE OR REPLACE FUNCTION guard_group_archive() RETURNS trigger AS $$
        BEGIN
          IF NEW.is_archived AND (
            EXISTS (SELECT 1 FROM students WHERE group_id = OLD.id AND status = 'active')
            OR EXISTS (
              SELECT 1 FROM schedulegrouplinks AS link
              JOIN schedules AS schedule ON schedule.id = link.schedule_id
              WHERE link.group_id = OLD.id AND (
                schedule.effective_until IS NULL OR schedule.effective_until > CURRENT_DATE
              )
            )
          ) THEN
            RAISE EXCEPTION 'group is still in use';
          END IF;
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """)
    connection.exec_driver_sql("""
        CREATE OR REPLACE FUNCTION guard_participant_change() RETURNS trigger AS $$
        BEGIN
          RAISE EXCEPTION 'lesson participation is immutable';
        END;
        $$ LANGUAGE plpgsql
    """)
    connection.exec_driver_sql("""
        CREATE OR REPLACE FUNCTION guard_participant_insert() RETURNS trigger AS $$
        BEGIN
          IF EXISTS (SELECT 1 FROM lessons WHERE id = NEW.lesson_id AND participants_complete)
          THEN
            RAISE EXCEPTION 'fixed lesson roster is immutable';
          END IF;
          IF NEW.group_id IS NOT NULL AND NOT EXISTS (
            SELECT 1 FROM lessons AS lesson
            JOIN schedulegrouplinks AS link ON link.schedule_id = lesson.schedule_id
            WHERE lesson.id = NEW.lesson_id AND link.group_id = NEW.group_id
          ) THEN
            RAISE EXCEPTION 'participant group is not linked to the lesson';
          END IF;
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """)
    connection.exec_driver_sql("""
        CREATE OR REPLACE FUNCTION guard_result_roster() RETURNS trigger AS $$
        BEGIN
          IF EXISTS (SELECT 1 FROM lessons WHERE id = NEW.lesson_id AND participants_complete)
             AND NOT EXISTS (
               SELECT 1 FROM lessonparticipants
               WHERE lesson_id = NEW.lesson_id AND student_id = NEW.student_id
             ) THEN
            RAISE EXCEPTION 'student is outside fixed lesson roster';
          END IF;
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """)
    connection.exec_driver_sql("""
        CREATE OR REPLACE FUNCTION guard_lesson_roster() RETURNS trigger AS $$
        BEGIN
          IF OLD.participants_complete AND (
            NOT NEW.participants_complete OR NEW.roster_origin IS DISTINCT FROM OLD.roster_origin
          ) THEN
            RAISE EXCEPTION 'fixed lesson roster is immutable';
          END IF;
          IF NEW.participants_complete AND NOT OLD.participants_complete AND EXISTS (
            SELECT 1 FROM (
              SELECT student_id FROM attendances WHERE lesson_id = OLD.id
              UNION SELECT student_id FROM marks WHERE lesson_id = OLD.id
              UNION SELECT student_id FROM comments WHERE lesson_id = OLD.id
            ) AS result
            WHERE NOT EXISTS (
              SELECT 1 FROM lessonparticipants AS participant
              WHERE participant.lesson_id = OLD.id
              AND participant.student_id = result.student_id
            )
          ) THEN
            RAISE EXCEPTION 'lesson results require roster participants';
          END IF;
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """)
    connection.exec_driver_sql("""
        CREATE OR REPLACE FUNCTION guard_lesson_history() RETURNS trigger AS $$
        BEGIN
          IF COALESCE(BTRIM(OLD.topic), '') <> ''
             OR OLD.participants_complete
             OR EXISTS (SELECT 1 FROM lessonparticipants WHERE lesson_id = OLD.id)
             OR EXISTS (SELECT 1 FROM attendances WHERE lesson_id = OLD.id)
             OR EXISTS (SELECT 1 FROM marks WHERE lesson_id = OLD.id)
             OR EXISTS (SELECT 1 FROM comments WHERE lesson_id = OLD.id) THEN
            RAISE EXCEPTION 'lesson history cannot be deleted or moved';
          END IF;
          RETURN OLD;
        END;
        $$ LANGUAGE plpgsql
    """)
    for name, table, events, function in (
        ("membership_update_guard", "groupmemberships", "UPDATE", "guard_membership_change"),
        ("membership_delete_guard", "groupmemberships", "DELETE", "guard_membership_change"),
        ("student_group_update", "students", "UPDATE OF group_id, status, archived_at, archive_reason", "guard_student_history"),
        ("student_status_insert", "students", "INSERT", "guard_student_insert"),
        ("student_delete_history", "students", "DELETE", "guard_student_history"),
        ("student_membership_insert", "students", "INSERT", "create_student_membership"),
        ("group_delete_history", "groups", "DELETE", "guard_group_delete"),
        ("group_archive_guard", "groups", "UPDATE OF is_archived", "guard_group_archive"),
        ("participant_update_guard", "lessonparticipants", "UPDATE", "guard_participant_change"),
        ("participant_delete_guard", "lessonparticipants", "DELETE", "guard_participant_change"),
        ("participant_insert_guard", "lessonparticipants", "INSERT", "guard_participant_insert"),
        ("lesson_roster_guard", "lessons", "UPDATE OF participants_complete, roster_origin", "guard_lesson_roster"),
        ("lesson_history_delete", "lessons", "DELETE", "guard_lesson_history"),
        ("lesson_history_move", "lessons", "UPDATE OF schedule_id, date", "guard_lesson_history"),
    ):
        connection.exec_driver_sql(f"DROP TRIGGER IF EXISTS {name} ON {table}")
        connection.exec_driver_sql(
            f"CREATE TRIGGER {name} AFTER {events} ON {table} "
            f"FOR EACH ROW EXECUTE FUNCTION {function}()"
            if name == "student_membership_insert" else
            f"CREATE TRIGGER {name} BEFORE {events} ON {table} "
            f"FOR EACH ROW EXECUTE FUNCTION {function}()"
        )
    for table in ("attendances", "marks", "comments"):
        for action in ("INSERT", "UPDATE"):
            name = f"{table}_roster_{action.lower()}"
            connection.exec_driver_sql(f"DROP TRIGGER IF EXISTS {name} ON {table}")
            connection.exec_driver_sql(
                f"CREATE TRIGGER {name} BEFORE {action} ON {table} "
                "FOR EACH ROW EXECUTE FUNCTION guard_result_roster()"
            )


def set_membership_import_mode(connection, *, enabled: bool) -> None:
    """Suppress automatic first memberships inside an isolated restore transaction."""
    if connection.dialect.name == "sqlite":
        if enabled:
            names = ["student_membership_insert", "student_status_insert", "participant_insert_guard"]
            names.extend(
                f"{table}_roster_{action}"
                for table in ("attendances", "marks", "comments")
                for action in ("insert", "update")
            )
            for name in names:
                connection.exec_driver_sql(f"DROP TRIGGER {name}")
        else:
            _sqlite_guards(connection)
    else:
        if enabled:
            connection.exec_driver_sql("LOCK TABLE students IN ACCESS EXCLUSIVE MODE")
            connection.exec_driver_sql("DROP TRIGGER student_membership_insert ON students")
            connection.exec_driver_sql("DROP TRIGGER student_status_insert ON students")
            connection.exec_driver_sql("DROP TRIGGER participant_insert_guard ON lessonparticipants")
            for table in ("attendances", "marks", "comments"):
                for action in ("insert", "update"):
                    connection.exec_driver_sql(
                        f"DROP TRIGGER {table}_roster_{action} ON {table}"
                    )
        else:
            _postgresql_guards(connection)


def ensure_membership_schema(engine, *, as_of: date | None = None) -> None:
    if engine.dialect.name not in {"sqlite", "postgresql"}:
        raise RuntimeError("Membership migration supports only SQLite and PostgreSQL.")
    migration_date = as_of or date.today()
    inspector = inspect(engine)
    legacy = inspector.has_table("students") and (
        "status" not in {column["name"] for column in inspector.get_columns("students")}
        or not inspector.has_table("groupmemberships")
    )
    if legacy and engine.dialect.name == "sqlite":
        path = Path(engine.url.database).resolve()
        if path.exists():
            backup_path = path.with_name(f"{path.name}.pre-membership-{uuid4().hex}.bak")
            with sqlite3.connect(path) as source, sqlite3.connect(backup_path) as backup:
                source.backup(backup)

    with engine.connect() as connection:
        if engine.dialect.name == "sqlite":
            connection.exec_driver_sql("BEGIN IMMEDIATE")
        else:
            connection.begin()
            if inspector.has_table("students"):
                connection.exec_driver_sql("LOCK TABLE students IN ACCESS EXCLUSIVE MODE")
        try:
            if not inspect(connection).has_table("students"):
                Base.metadata.create_all(bind=connection)
            else:
                _add_missing_columns(connection)
                Base.metadata.create_all(bind=connection)
            if legacy:
                connection.execute(text(
                    "INSERT INTO groupmemberships "
                    "(student_id, group_id, start_date, origin, known_from) "
                    "SELECT id, group_id, '1900-01-01', 'migrated_unknown', :today FROM students"
                ), {"today": migration_date.isoformat()})
                connection.execute(text(
                    "INSERT INTO lessonparticipants (lesson_id, student_id, source) "
                    "SELECT lesson_id, student_id, 'evidence' FROM ("
                    "SELECT lesson_id, student_id FROM attendances UNION "
                    "SELECT lesson_id, student_id FROM marks UNION "
                    "SELECT lesson_id, student_id FROM comments) AS evidence"
                ))
            if engine.dialect.name == "sqlite":
                _sqlite_guards(connection)
            else:
                _postgresql_guards(connection)
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
