"""Add academic context without interpreting or rewriting legacy records."""

import sqlite3
from pathlib import Path
from uuid import uuid4

from sqlalchemy import inspect

from app.models import Base


def ensure_academic_schema(engine):
    if engine.dialect.name not in {"sqlite", "postgresql"}:
        raise RuntimeError("Academic migration requires SQLite or PostgreSQL.")
    with engine.connect() as connection:
        if engine.dialect.name == "sqlite":
            connection.exec_driver_sql("BEGIN IMMEDIATE")
        else:
            connection.begin()
            if inspect(connection).has_table("schedules"):
                connection.exec_driver_sql("LOCK TABLE schedules IN ACCESS EXCLUSIVE MODE")
        try:
            if engine.dialect.name == "sqlite":
                _backup_before_academic_upgrade(connection)
            Base.metadata.create_all(connection)
            event_columns = {item["name"] for item in inspect(connection).get_columns("assessment_events")}
            if "custom_type" not in event_columns:
                connection.exec_driver_sql(
                    "ALTER TABLE assessment_events ADD COLUMN custom_type VARCHAR(128)"
                )
            attempt_columns = {item["name"] for item in inspect(connection).get_columns("assessment_attempts")}
            if "finalized" not in attempt_columns:
                connection.exec_driver_sql(
                    "ALTER TABLE assessment_attempts ADD COLUMN finalized BOOLEAN NOT NULL DEFAULT false"
                )
            lesson_columns = {item["name"] for item in inspect(connection).get_columns("lessons")}
            if "roster_time_basis" not in lesson_columns:
                connection.exec_driver_sql(
                    "ALTER TABLE lessons ADD COLUMN roster_time_basis VARCHAR(24) NOT NULL DEFAULT 'unknown'"
                )
            columns = {item["name"] for item in inspect(connection).get_columns("schedules")}
            if "offering_id" not in columns:
                connection.exec_driver_sql(
                    "ALTER TABLE schedules ADD COLUMN offering_id INTEGER "
                    "REFERENCES course_offerings(id) ON DELETE RESTRICT"
                )
            if engine.dialect.name == "sqlite":
                connection.exec_driver_sql("""
                    CREATE TRIGGER IF NOT EXISTS schedule_academic_context
                    BEFORE UPDATE OF offering_id ON schedules
                    WHEN NEW.offering_id IS NOT OLD.offering_id BEGIN
                    SELECT RAISE(ABORT, 'historical academic context is immutable') WHERE
                    OLD.revision > 1 OR OLD.effective_until IS NOT NULL OR EXISTS (
                      SELECT 1 FROM lessons WHERE schedule_id = OLD.id);
                    END
                """)
                for table in ("academic_years", "course_offerings", "course_offering_groups", "teaching_modules"):
                    connection.exec_driver_sql(f"""
                        CREATE TRIGGER IF NOT EXISTS {table}_immutable
                        BEFORE UPDATE ON {table} BEGIN
                        SELECT RAISE(ABORT, 'academic configuration is immutable'); END
                    """)
                connection.exec_driver_sql("""
                    CREATE TRIGGER IF NOT EXISTS academic_term_guard
                    BEFORE UPDATE ON academic_terms BEGIN
                    SELECT RAISE(ABORT, 'academic term is immutable') WHERE
                      NEW.year_id IS NOT OLD.year_id OR NEW.start_date IS NOT OLD.start_date
                      OR NEW.total_weeks IS NOT OLD.total_weeks OR NEW.name IS NOT OLD.name
                      OR NEW.origin IS NOT OLD.origin OR OLD.status = 'closed';
                    END
                """)
            else:
                connection.exec_driver_sql("""
                    CREATE OR REPLACE FUNCTION guard_academic_context() RETURNS trigger AS $$
                    BEGIN
                      IF NEW.offering_id IS DISTINCT FROM OLD.offering_id AND (
                        OLD.revision > 1 OR OLD.effective_until IS NOT NULL OR EXISTS (
                          SELECT 1 FROM lessons WHERE schedule_id = OLD.id)) THEN
                        RAISE EXCEPTION 'historical academic context is immutable';
                      END IF;
                      RETURN NEW;
                    END; $$ LANGUAGE plpgsql
                """)
                connection.exec_driver_sql("DROP TRIGGER IF EXISTS schedule_academic_context ON schedules")
                connection.exec_driver_sql("""
                    CREATE TRIGGER schedule_academic_context BEFORE UPDATE OF offering_id ON schedules
                    FOR EACH ROW EXECUTE FUNCTION guard_academic_context()
                """)
                connection.exec_driver_sql("""
                    CREATE OR REPLACE FUNCTION guard_academic_configuration() RETURNS trigger AS $$
                    BEGIN RAISE EXCEPTION 'academic configuration is immutable'; END;
                    $$ LANGUAGE plpgsql
                """)
                for table in ("academic_years", "course_offerings", "course_offering_groups", "teaching_modules"):
                    connection.exec_driver_sql(f"DROP TRIGGER IF EXISTS {table}_immutable ON {table}")
                    connection.exec_driver_sql(f"CREATE TRIGGER {table}_immutable BEFORE UPDATE ON {table} "
                                               "FOR EACH ROW EXECUTE FUNCTION guard_academic_configuration()")
                connection.exec_driver_sql("""
                    CREATE OR REPLACE FUNCTION guard_academic_term() RETURNS trigger AS $$
                    BEGIN
                      IF (NEW.year_id, NEW.start_date, NEW.total_weeks, NEW.name, NEW.origin)
                         IS DISTINCT FROM
                         (OLD.year_id, OLD.start_date, OLD.total_weeks, OLD.name, OLD.origin)
                         OR OLD.status = 'closed' THEN
                        RAISE EXCEPTION 'academic term is immutable';
                      END IF;
                      RETURN NEW;
                    END; $$ LANGUAGE plpgsql
                """)
                connection.exec_driver_sql("DROP TRIGGER IF EXISTS academic_term_guard ON academic_terms")
                connection.exec_driver_sql("CREATE TRIGGER academic_term_guard BEFORE UPDATE ON academic_terms "
                                           "FOR EACH ROW EXECUTE FUNCTION guard_academic_term()")
            _education_guards(connection)
            connection.commit()
        except BaseException:
            connection.rollback()
            raise


def _backup_before_academic_upgrade(connection):
    """Snapshot an existing file while BEGIN IMMEDIATE excludes other writers."""
    inspector = inspect(connection)
    missing = any(
        inspector.has_table(table) and field not in {
            column["name"] for column in inspector.get_columns(table)
        }
        for table, field in (("schedules", "offering_id"),
                             ("lessons", "roster_time_basis"),
                             ("assessment_attempts", "finalized"))
    )
    if not missing:
        return
    # SQLite resolves URI/file paths here and returns an empty path for memory.
    filename = next((row[2] for row in connection.exec_driver_sql("PRAGMA database_list")
                     if row[1] == "main"), "")
    if not filename:
        return
    path = Path(filename)
    backup_path = path.with_name(f"{path.name}.pre-academic-{uuid4().hex}.bak")
    with sqlite3.connect(path) as source, sqlite3.connect(backup_path) as destination:
        source.backup(destination)


def _education_guards(connection):
    """Install repeatable guards without touching existing teaching records.

    PostgreSQL writers lock the term before checking it, serializing closure and
    sibling configuration. SQLite's single writer provides the same ordering.
    """
    pg = connection.dialect.name == "postgresql"

    def guard(table, suffix, operation, checks, term=None):
        name = f"education_{table}_{suffix}"
        if pg:
            body = ""
            if term:
                ids = f"({term})"
                if operation == "UPDATE":
                    ids += f", ({term.replace('NEW.', 'OLD.')})"
                body += f"PERFORM id FROM academic_terms WHERE id IN ({ids}) ORDER BY id FOR UPDATE;\n"
            if operation == "INSERT" and table == "attendance_revisions":
                body += "PERFORM id FROM attendances WHERE id=NEW.attendance_id FOR UPDATE;\n"
            if operation == "INSERT" and table == "lesson_dispositions":
                body += "PERFORM id FROM lessons WHERE id=NEW.lesson_id FOR UPDATE;\n"
            for predicate, message in checks:
                body += f"IF {predicate} THEN RAISE EXCEPTION '{message}'; END IF;\n"
            body += "IF TG_OP = 'DELETE' THEN RETURN OLD; END IF; RETURN NEW;"
            connection.exec_driver_sql(
                f"CREATE OR REPLACE FUNCTION {name}() RETURNS trigger AS $$ BEGIN {body} END; $$ LANGUAGE plpgsql"
            )
            connection.exec_driver_sql(f"DROP TRIGGER IF EXISTS {name} ON {table}")
            connection.exec_driver_sql(f"CREATE TRIGGER {name} BEFORE {operation} ON {table} "
                                       f"FOR EACH ROW EXECUTE FUNCTION {name}()")
        else:
            body = " ".join(f"SELECT RAISE(ABORT, '{message}') WHERE {predicate};"
                            for predicate, message in checks)
            connection.exec_driver_sql(f"DROP TRIGGER IF EXISTS {name}")
            connection.exec_driver_sql(f"CREATE TRIGGER {name} BEFORE {operation} ON {table} BEGIN {body} END")

    immutable = (
        "academic_years", "disciplines", "course_offerings", "course_offering_groups",
        "teaching_modules", "assessment_events", "assessment_attempts", "consultations",
        "consultation_visits", "lab_works", "checklist_versions", "checklist_criteria",
        "criterion_answers", "result_corrections", "event_cancellations",
        "attendance_revisions", "non_teaching_days", "lesson_dispositions",
        "individual_plans", "plan_stages", "plan_entries", "teaching_audit",
    )
    for table in immutable:
        for operation in ("UPDATE", "DELETE"):
            predicate = "TRUE"
            if operation == "UPDATE":
                different = "IS DISTINCT FROM" if pg else "IS NOT"
                predicate = " OR ".join(
                    f"NEW.{column['name']} {different} OLD.{column['name']}"
                    for column in inspect(connection).get_columns(table)
                )
            guard(table, operation.lower(), operation, [(predicate, "academic history is immutable")])
        # Replace the earlier unconditional academic guards as well: SQLite
        # services acquire the writer lock with an exact SET id=id operation.
        if table in ("academic_years", "course_offerings", "course_offering_groups", "teaching_modules"):
            connection.exec_driver_sql(f"DROP TRIGGER IF EXISTS {table}_immutable" + (f" ON {table}" if pg else ""))
    guard("academic_terms", "delete", "DELETE", [("TRUE", "academic history is immutable")])

    offering_term = "SELECT term_id FROM course_offerings WHERE id = NEW.offering_id"
    module_term = ("SELECT o.term_id FROM teaching_modules m JOIN course_offerings o "
                   "ON o.id = m.offering_id WHERE m.id = NEW.module_id")
    event_term = ("SELECT o.term_id FROM assessment_events e JOIN teaching_modules m ON m.id = e.module_id "
                  "JOIN course_offerings o ON o.id = m.offering_id WHERE e.id = NEW.event_id")
    attempt_term = ("SELECT o.term_id FROM assessment_attempts a JOIN assessment_events e ON e.id = a.event_id "
                    "JOIN teaching_modules m ON m.id = e.module_id JOIN course_offerings o ON o.id = m.offering_id "
                    "WHERE a.id = NEW.attempt_id")
    lesson_term = ("SELECT s.offering_id FROM lessons l JOIN schedules s ON s.id = l.schedule_id "
                   "WHERE l.id = NEW.lesson_id")
    lesson_term = f"SELECT term_id FROM course_offerings WHERE id = ({lesson_term})"
    terms = {
        "course_offerings": "NEW.term_id", "course_offering_groups": offering_term,
        "teaching_modules": offering_term, "assessment_events": module_term,
        "assessment_attempts": event_term, "event_cancellations": event_term,
        "result_corrections": attempt_term, "criterion_answers": attempt_term,
        "non_teaching_days": "NEW.term_id", "lesson_dispositions": lesson_term,
        "individual_plans": offering_term,
        "lab_works": event_term,
        "checklist_versions": "SELECT o.term_id FROM lab_works w JOIN assessment_events e ON e.id=w.event_id JOIN teaching_modules m ON m.id=e.module_id JOIN course_offerings o ON o.id=m.offering_id WHERE w.id=NEW.lab_id",
        "checklist_criteria": "SELECT o.term_id FROM checklist_versions v JOIN lab_works w ON w.id=v.lab_id JOIN assessment_events e ON e.id=w.event_id JOIN teaching_modules m ON m.id=e.module_id JOIN course_offerings o ON o.id=m.offering_id WHERE v.id=NEW.version_id",
        "plan_stages": "SELECT o.term_id FROM individual_plans p JOIN course_offerings o ON o.id=p.offering_id WHERE p.id=NEW.plan_id",
        "plan_entries": "SELECT o.term_id FROM plan_stages st JOIN individual_plans p ON p.id=st.plan_id JOIN course_offerings o ON o.id=p.offering_id WHERE st.id=NEW.stage_id",
        "attendance_revisions": "SELECT o.term_id FROM attendances a JOIN lessons l ON l.id=a.lesson_id JOIN schedules s ON s.id=l.schedule_id JOIN course_offerings o ON o.id=s.offering_id WHERE a.id=NEW.attendance_id",
    }
    checks = {table: [] for table in terms}
    term_end = "t.start_date + t.total_weeks * 7" if pg else "date(t.start_date, '+' || (t.total_weeks * 7) || ' days')"
    checks["teaching_modules"] += [
        (f"NOT EXISTS (SELECT 1 FROM course_offerings o JOIN academic_terms t ON t.id=o.term_id WHERE o.id=NEW.offering_id AND NEW.start_date >= t.start_date AND NEW.end_date <= {term_end})", "module outside term"),
        ("EXISTS (SELECT 1 FROM teaching_modules WHERE offering_id=NEW.offering_id AND start_date < NEW.end_date AND NEW.start_date < end_date)", "module periods overlap"),
    ]
    from app.models import ScheduleGroupLink
    checks["course_offering_groups"] += [
        ("EXISTS (SELECT 1 FROM schedules WHERE offering_id=NEW.offering_id)", "used offering group set is immutable"),
        ("EXISTS (SELECT 1 FROM groups WHERE id=NEW.group_id AND is_archived)", "cannot add archived offering group"),
    ]
    checks["assessment_events"] += [
        ("NEW.lesson_id IS NOT NULL AND NEW.category IN ('seminar_start','seminar_end') AND EXISTS (SELECT 1 FROM assessment_events e WHERE e.lesson_id=NEW.lesson_id AND e.category=NEW.category AND NOT EXISTS (SELECT 1 FROM event_cancellations cancelled WHERE cancelled.event_id=e.id))", "active seminar test slot already configured"),
        ("NEW.lesson_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM lessons l JOIN schedules s ON s.id=l.schedule_id JOIN teaching_modules m ON m.id=NEW.module_id WHERE l.id=NEW.lesson_id AND s.offering_id=m.offering_id AND l.date >= m.start_date AND l.date < m.end_date)", "event lesson and module context mismatch"),
    ]
    eligible = """EXISTS (SELECT 1 FROM assessment_events e JOIN teaching_modules m ON m.id=e.module_id
        JOIN course_offerings o ON o.id=m.offering_id JOIN academic_terms t ON t.id=o.term_id
        JOIN course_offering_groups g ON g.offering_id=m.offering_id
        JOIN groupmemberships gm ON gm.group_id=g.group_id
        WHERE e.id=NEW.event_id AND gm.student_id=NEW.student_id
        AND gm.start_date < TERM_END
        AND (gm.end_date IS NULL OR t.start_date < gm.end_date)
        AND (gm.end_date IS NULL OR gm.start_date < gm.end_date)
        AND (gm.origin != 'migrated_unknown' OR gm.known_from < TERM_END))""".replace("TERM_END", term_end)
    evidence = "EXISTS (SELECT 1 FROM assessment_events e JOIN teaching_modules m ON m.id=e.module_id JOIN schedules s ON s.offering_id=m.offering_id JOIN lessons l ON l.schedule_id=s.id JOIN lessonparticipants p ON p.lesson_id=l.id WHERE e.id=NEW.event_id AND p.student_id=NEW.student_id)"
    prior_result = """EXISTS (
        SELECT 1 FROM assessment_attempts a
        JOIN assessment_events previous_event ON previous_event.id=a.event_id
        JOIN teaching_modules previous_module ON previous_module.id=previous_event.module_id
        JOIN assessment_events current_event ON current_event.id=NEW.event_id
        JOIN teaching_modules current_module ON current_module.id=current_event.module_id
        WHERE a.student_id=NEW.student_id AND a.finalized
        AND previous_module.offering_id=current_module.offering_id)"""
    checks["assessment_attempts"] += [
        ("NEW.finalized", "attempt must be inserted as a draft"),
        ("NEW.passed AND NOT NEW.work_completed", "passed assessment requires completed work"),
        ("EXISTS (SELECT 1 FROM assessment_events WHERE id=NEW.event_id AND category='lab') AND (NEW.checklist_version_id IS NULL OR (NEW.passed AND (NOT NEW.defended OR NEW.question_passed IS NULL OR NOT NEW.question_passed)))", "lab attempt requires checklist and defense"),
        (f"NOT ({eligible} OR {evidence} OR {prior_result})", "student not eligible for assessment"),
        ("EXISTS (SELECT 1 FROM event_cancellations WHERE event_id=NEW.event_id)", "assessment is cancelled"),
        ("EXISTS (SELECT 1 FROM assessment_events WHERE id=NEW.event_id AND (NEW.points > max_points OR (max_attempts IS NOT NULL AND NEW.attempt_number > max_attempts)))", "assessment score or attempt limit exceeded"),
        ("NEW.checklist_version_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM checklist_versions v JOIN lab_works w ON w.id=v.lab_id WHERE v.id=NEW.checklist_version_id AND w.event_id=NEW.event_id)", "attempt checklist mismatch"),
        ("NEW.consultation_visit_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM consultation_visits WHERE id=NEW.consultation_visit_id AND student_id=NEW.student_id)", "consultation student mismatch"),
    ]
    checks["event_cancellations"] += [("EXISTS (SELECT 1 FROM assessment_attempts WHERE event_id=NEW.event_id)", "cannot cancel assessment with attempts")]
    checks["result_corrections"] += [
        ("NOT EXISTS (SELECT 1 FROM assessment_attempts WHERE id=NEW.attempt_id AND finalized)", "cannot correct unfinished attempt"),
        ("NEW.passed AND EXISTS (SELECT 1 FROM assessment_attempts a JOIN assessment_events e ON e.id=a.event_id WHERE a.id=NEW.attempt_id AND e.category='lab' AND NOT a.passed)", "failed lab defense requires a new attempt"),
        ("EXISTS (SELECT 1 FROM assessment_attempts a JOIN assessment_events e ON e.id=a.event_id WHERE a.id=NEW.attempt_id AND NEW.points > e.max_points) OR (NOT NEW.passed AND NEW.points != 0)", "invalid corrected score"),
        ("trim(NEW.reason) = '' OR trim(NEW.source) = ''", "correction requires reason and source"),
    ]
    checks["criterion_answers"] += [
        ("EXISTS (SELECT 1 FROM assessment_attempts WHERE id=NEW.attempt_id AND finalized)", "finalized attempt answers are immutable"),
        ("NOT EXISTS (SELECT 1 FROM assessment_attempts a JOIN checklist_criteria c ON c.version_id=a.checklist_version_id WHERE a.id=NEW.attempt_id AND c.id=NEW.criterion_id)", "criterion does not belong to attempt checklist")]
    checks["lab_works"] += [("NOT EXISTS (SELECT 1 FROM assessment_events WHERE id=NEW.event_id AND category='lab')", "lab requires lab assessment")]
    checks["checklist_criteria"] += [("EXISTS (SELECT 1 FROM assessment_attempts WHERE checklist_version_id=NEW.version_id)", "used checklist is immutable")]
    checks["lesson_dispositions"] += [("NEW.replacement_lesson_id IS NOT NULL AND (NEW.replacement_lesson_id=NEW.lesson_id OR NOT EXISTS (SELECT 1 FROM lessons a JOIN schedules sa ON sa.id=a.schedule_id JOIN lessons b ON b.id=NEW.replacement_lesson_id JOIN schedules sb ON sb.id=b.schedule_id WHERE a.id=NEW.lesson_id AND (sa.offering_id=sb.offering_id OR (sa.id=sb.id AND sa.offering_id IS NULL))))", "replacement lesson context mismatch")]
    today = "CURRENT_DATE" if pg else "date('now','localtime')"
    checks["lesson_dispositions"] += [
        ("EXISTS (SELECT 1 FROM lesson_dispositions WHERE lesson_id=NEW.lesson_id AND status='moved')", "original lesson already moved; change replacement instead"),
        (f"NEW.status != 'held' AND (EXISTS (SELECT 1 FROM lessons WHERE id=NEW.lesson_id AND (participants_complete OR date < {today})) OR EXISTS (SELECT 1 FROM lessonparticipants WHERE lesson_id=NEW.lesson_id) OR EXISTS (SELECT 1 FROM attendances WHERE lesson_id=NEW.lesson_id) OR EXISTS (SELECT 1 FROM marks WHERE lesson_id=NEW.lesson_id) OR EXISTS (SELECT 1 FROM comments WHERE lesson_id=NEW.lesson_id) OR EXISTS (SELECT 1 FROM assessment_events e JOIN assessment_attempts a ON a.event_id=e.id WHERE e.lesson_id=NEW.lesson_id AND a.finalized) OR EXISTS (SELECT 1 FROM lesson_dispositions WHERE lesson_id=NEW.lesson_id AND status='held'))", "conducted or filled lesson cannot be cancelled or moved"),
        (f"NEW.status='held' AND EXISTS (SELECT 1 FROM lessons WHERE id=NEW.lesson_id AND date > {today})", "future lesson cannot be marked held"),
    ]
    checks["non_teaching_days"] += [(f"NOT EXISTS (SELECT 1 FROM academic_terms t WHERE t.id=NEW.term_id AND NEW.date >= t.start_date AND NEW.date < {term_end})", "non teaching day outside term")]
    checks["plan_entries"] += [("NEW.consultation_visit_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM plan_stages s JOIN individual_plans p ON p.id=s.plan_id JOIN consultation_visits v ON v.student_id=p.student_id WHERE s.id=NEW.stage_id AND v.id=NEW.consultation_visit_id)", "plan consultation student mismatch")]
    checks["attendance_revisions"] += [
        ("trim(NEW.reason)='' OR trim(NEW.source)=''", "attendance revision requires reason and source"),
        ("NEW.late_seconds IS NOT NULL AND NEW.late_seconds < 0", "late seconds cannot be negative"),
    ]
    for table, term in terms.items():
        guard(table, "insert", "INSERT", [(f"EXISTS (SELECT 1 FROM academic_terms WHERE id=({term}) AND status='closed')", "academic term is closed")] + checks[table], term)

    different = "IS DISTINCT FROM" if pg else "IS NOT"
    attempt_fields = [column["name"] for column in inspect(connection).get_columns("assessment_attempts")]
    any_change = " OR ".join(f"NEW.{field} {different} OLD.{field}" for field in attempt_fields)
    content_change = " OR ".join(f"NEW.{field} {different} OLD.{field}" for field in attempt_fields
                                 if field not in {"finalized", "updated_at"})
    finalizing = "NOT OLD.finalized AND NEW.finalized"
    is_lab = "EXISTS (SELECT 1 FROM assessment_events WHERE id=NEW.event_id AND category='lab')"
    guard("assessment_attempts", "update", "UPDATE", [
        (f"({any_change}) AND NOT ({finalizing} AND NOT ({content_change}))", "academic history is immutable"),
        (f"({finalizing}) AND EXISTS (SELECT 1 FROM academic_terms WHERE id=({event_term}) AND status='closed')", "academic term is closed"),
        (f"({finalizing}) AND NEW.passed AND NOT NEW.work_completed", "passed assessment requires completed work"),
        (f"({finalizing}) AND {is_lab} AND (NEW.checklist_version_id IS NULL OR NOT EXISTS (SELECT 1 FROM checklist_criteria WHERE version_id=NEW.checklist_version_id) OR EXISTS (SELECT 1 FROM checklist_criteria c WHERE c.version_id=NEW.checklist_version_id AND NOT EXISTS (SELECT 1 FROM criterion_answers a WHERE a.attempt_id=NEW.id AND a.criterion_id=c.id)) OR EXISTS (SELECT 1 FROM criterion_answers a WHERE a.attempt_id=NEW.id AND NOT EXISTS (SELECT 1 FROM checklist_criteria c WHERE c.id=a.criterion_id AND c.version_id=NEW.checklist_version_id)))", "lab checklist answers must be complete and nonempty"),
        (f"({finalizing}) AND {is_lab} AND NEW.passed AND (NOT NEW.defended OR NEW.question_passed IS NULL OR NOT NEW.question_passed OR EXISTS (SELECT 1 FROM criterion_answers WHERE attempt_id=NEW.id AND NOT satisfied))", "passed lab requires successful defense and all criteria"),
    ], event_term)

    end = "NEW.start_date + NEW.total_weeks * 7" if pg else "date(NEW.start_date, '+' || (NEW.total_weeks * 7) || ' days')"
    not_monday = "EXTRACT(ISODOW FROM NEW.start_date) != 1" if pg else "strftime('%w', NEW.start_date) != '1'"
    guard("academic_terms", "insert", "INSERT", [
        (not_monday, "academic term must start on Monday"),
        (f"NOT EXISTS (SELECT 1 FROM academic_years y WHERE y.id=NEW.year_id AND NEW.start_date >= y.start_date AND {end} <= y.end_date)", "term outside academic year")])
    for table in ("schedules", "schedule_group_links", "lessons", "attendances", "marks", "comments"):
        # The actual link table name is defined explicitly by the existing model.
        if table == "schedule_group_links":
            from app.models import ScheduleGroupLink
            table = ScheduleGroupLink.__tablename__
        if table == "schedules":
            term = offering_term
        elif table in ("lessons", "schedulegrouplinks"):
            term = "SELECT o.term_id FROM schedules s JOIN course_offerings o ON o.id=s.offering_id WHERE s.id=NEW.schedule_id"
        else:
            term = lesson_term
        for operation in ("INSERT", "UPDATE"):
            closed = f"EXISTS (SELECT 1 FROM academic_terms WHERE id=({term}) AND status='closed')"
            if operation == "UPDATE":
                closed += f" OR EXISTS (SELECT 1 FROM academic_terms WHERE id=({term.replace('NEW.', 'OLD.')}) AND status='closed')"
            guard(table, f"closed_{operation.lower()}", operation, [
                (closed, "academic term is closed")], term)
    from app.models import ScheduleGroupLink
    link_table = ScheduleGroupLink.__tablename__
    for operation in ("INSERT", "UPDATE"):
        guard(link_table, f"context_{operation.lower()}", operation, [
            ("EXISTS (SELECT 1 FROM schedules s WHERE s.id=NEW.schedule_id AND s.offering_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM course_offering_groups g WHERE g.offering_id=s.offering_id AND g.group_id=NEW.group_id))", "schedule group outside offering")])
        guard("schedules", f"context_{operation.lower()}", operation, [
            (f"NEW.offering_id IS NOT NULL AND EXISTS (SELECT 1 FROM {link_table} l WHERE l.schedule_id=NEW.id AND NOT EXISTS (SELECT 1 FROM course_offering_groups g WHERE g.offering_id=NEW.offering_id AND g.group_id=l.group_id))", "schedule groups outside offering")])

    different = "IS DISTINCT FROM" if pg else "IS NOT"
    changed_lesson = f"(NEW.schedule_id {different} OLD.schedule_id OR NEW.date {different} OLD.date)"
    guard("lessons", "event_context", "UPDATE", [
        (f"{changed_lesson} AND EXISTS (SELECT 1 FROM assessment_events e JOIN assessment_attempts a ON a.event_id=e.id WHERE e.lesson_id=OLD.id AND a.finalized)", "lesson with finalized assessments cannot be moved"),
        (f"{changed_lesson} AND EXISTS (SELECT 1 FROM assessment_events e JOIN teaching_modules m ON m.id=e.module_id WHERE e.lesson_id=OLD.id AND NOT EXISTS (SELECT 1 FROM schedules s WHERE s.id=NEW.schedule_id AND s.offering_id=m.offering_id AND NEW.date >= m.start_date AND NEW.date < m.end_date))", "lesson move conflicts with assessment module context"),
    ])
    guard("groups", "academic_archive", "UPDATE", [
        (f"NEW.is_archived AND NEW.is_archived {different} OLD.is_archived AND EXISTS (SELECT 1 FROM course_offering_groups g JOIN course_offerings o ON o.id=g.offering_id JOIN academic_terms t ON t.id=o.term_id WHERE g.group_id=OLD.id AND t.status='open')", "group used by open academic course cannot be archived"),
    ])
    guard("lessons", "roster_basis", "UPDATE", [
        (f"OLD.participants_complete AND NEW.roster_time_basis {different} OLD.roster_time_basis", "fixed roster time basis is immutable")])
    latest = "SELECT status IN ('present','late') FROM attendance_revisions WHERE attendance_id=OLD.id ORDER BY id DESC LIMIT 1"
    guard("attendances", "projection", "UPDATE", [
        (f"EXISTS (SELECT 1 FROM attendance_revisions WHERE attendance_id=OLD.id) AND (NEW.id {different} OLD.id OR NEW.student_id {different} OLD.student_id OR NEW.lesson_id {different} OLD.lesson_id OR NEW.is_visited {different} ({latest}))", "attendance projection must match latest revision")])
    guard("attendances", "revision_delete", "DELETE", [
        ("EXISTS (SELECT 1 FROM attendance_revisions WHERE attendance_id=OLD.id)", "attendance with revisions cannot be deleted")])

    # Raw SQL updates deliberately omit updated_at: revisions change the cached
    # boolean, not the timestamp of the original legacy attendance record.
    sync = """UPDATE attendances SET is_visited=(
        SELECT status IN ('present','late') FROM attendance_revisions
        WHERE attendance_id=NEW.attendance_id ORDER BY id DESC LIMIT 1)
        WHERE id=NEW.attendance_id;"""
    name = "education_attendance_revisions_projection"
    if pg:
        connection.exec_driver_sql(f"CREATE OR REPLACE FUNCTION {name}() RETURNS trigger AS $$ BEGIN {sync} RETURN NEW; END; $$ LANGUAGE plpgsql")
        connection.exec_driver_sql(f"DROP TRIGGER IF EXISTS {name} ON attendance_revisions")
        connection.exec_driver_sql(f"CREATE TRIGGER {name} AFTER INSERT ON attendance_revisions FOR EACH ROW EXECUTE FUNCTION {name}()")
    else:
        connection.exec_driver_sql(f"DROP TRIGGER IF EXISTS {name}")
        connection.exec_driver_sql(f"CREATE TRIGGER {name} AFTER INSERT ON attendance_revisions BEGIN {sync} END")
