"""Idempotent, additive activity schema with database-level history guards."""
from app.models.base import Base
from app.models import journal_activity as models
from sqlalchemy import inspect


def ensure_activity_schema(engine):
    if engine.dialect.name not in ('sqlite', 'postgresql'):
        raise RuntimeError('Activity history requires SQLite or PostgreSQL.')
    tables = [getattr(models, name).__table__ for name in (
        'Classroom', 'SeatingLayout', 'Seat', 'LessonLayout', 'SeatAssignment',
        'BehaviorCategory', 'BehaviorEvent', 'BehaviorCorrection')]
    with engine.connect() as c:
        if engine.dialect.name == 'sqlite':
            c.exec_driver_sql('BEGIN IMMEDIATE')
        else:
            c.begin()
            # Serialize schema installation even before the activity tables exist.
            c.exec_driver_sql('SELECT pg_advisory_xact_lock(214731, 81001)')
        try:
            Base.metadata.create_all(c, tables=tables)
            if 'sealed' not in {col['name'] for col in inspect(c).get_columns('seating_layouts')}:
                c.exec_driver_sql('ALTER TABLE seating_layouts ADD COLUMN sealed BOOLEAN NOT NULL DEFAULT true')
            install_activity_guards(c)
            c.commit()
        except BaseException:
            c.rollback()
            raise


def install_activity_guards(connection):
    """Install guards on an existing connection without committing or creating tables."""
    c = connection
    if c.dialect.name not in ('sqlite', 'postgresql'):
        raise RuntimeError('Activity history requires SQLite or PostgreSQL.')
    tables = [getattr(models, name).__table__ for name in (
        'Classroom', 'SeatingLayout', 'Seat', 'LessonLayout', 'SeatAssignment',
        'BehaviorCategory', 'BehaviorEvent', 'BehaviorCorrection')]
    pg = c.dialect.name == 'postgresql'

    def guard(table, suffix, operation, checks, lock=''):
        name = f'activity_{table}_{suffix}'
        c.exec_driver_sql(f'DROP TRIGGER IF EXISTS {name} ON {table}' if pg else f'DROP TRIGGER IF EXISTS {name}')
        if pg:
            body = ' '.join(f"IF {condition} THEN RAISE EXCEPTION '{message}'; END IF;" for condition, message in checks)
            c.exec_driver_sql(f"CREATE OR REPLACE FUNCTION {name}() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN {lock} {body} RETURN {'OLD' if operation == 'DELETE' else 'NEW'}; END $$")
            c.exec_driver_sql(f'CREATE TRIGGER {name} BEFORE {operation} ON {table} FOR EACH ROW EXECUTE FUNCTION {name}()')
        else:
            body = ' '.join(f"SELECT RAISE(ABORT, '{message}') WHERE {condition};" for condition, message in checks)
            c.exec_driver_sql(f'CREATE TRIGGER {name} BEFORE {operation} ON {table} BEGIN {body} END')

    for table in tables:
        for op in ('UPDATE', 'DELETE'):
            condition = '1=1'
            if table.name == 'seating_layouts' and op == 'UPDATE':
                condition = ('OLD.sealed OR NOT NEW.sealed OR NEW.id<>OLD.id OR NEW.room_id<>OLD.room_id '
                             'OR NEW.revision<>OLD.revision OR NEW.name<>OLD.name')
            guard(table.name, op.lower(), op, [(condition, 'activity records are immutable')])
    guard('seats', 'insert', 'INSERT', [(
        'EXISTS (SELECT 1 FROM seating_layouts WHERE id=NEW.layout_id AND sealed) OR EXISTS (SELECT 1 FROM lesson_layouts WHERE layout_id=NEW.layout_id)', 'saved layout is immutable')],
        'PERFORM id FROM seating_layouts WHERE id=NEW.layout_id FOR UPDATE;' if pg else '')
    lesson = 'NEW.lesson_id'
    closed = f"EXISTS (SELECT 1 FROM lessons l JOIN schedules s ON s.id=l.schedule_id JOIN course_offerings o ON o.id=s.offering_id JOIN academic_terms t ON t.id=o.term_id WHERE l.id={lesson} AND t.status='closed')"
    member = f'EXISTS (SELECT 1 FROM lessons WHERE id={lesson} AND participants_complete) AND NOT EXISTS (SELECT 1 FROM lessonparticipants WHERE lesson_id={lesson} AND student_id=NEW.student_id)'
    eligible = f'''NOT EXISTS (SELECT 1 FROM lessonparticipants WHERE lesson_id={lesson} AND student_id=NEW.student_id)
        AND NOT EXISTS (SELECT 1 FROM lessons l JOIN schedulegrouplinks sg ON sg.schedule_id=l.schedule_id
        JOIN groupmemberships gm ON gm.group_id=sg.group_id JOIN students st ON st.id=gm.student_id
        WHERE l.id={lesson} AND gm.student_id=NEW.student_id AND gm.start_date<=l.date
        AND (gm.end_date IS NULL OR gm.end_date>l.date)
        AND (gm.origin<>'migrated_unknown' OR gm.known_from<=l.date))'''
    for table in ('lesson_layouts', 'seat_assignments', 'behavior_events'):
        checks = [(closed, 'academic term is closed')]
        if table == 'lesson_layouts':
            checks += [('NOT EXISTS (SELECT 1 FROM seating_layouts WHERE id=NEW.layout_id AND sealed)', 'layout must be sealed')]
        if table != 'lesson_layouts':
            checks += [(member, 'student is outside fixed roster'), (eligible, 'student has no dated participation evidence')]
        if table == 'behavior_events':
            checks += [("length(trim(NEW.source))=0 OR length(trim(NEW.operation_key))=0", 'source and operation key are required')]
        if table == 'seat_assignments':
            checks += [
                ("length(trim(NEW.reason))=0 OR length(trim(NEW.operation_key))=0", 'reason and operation key are required'),
                ('NOT EXISTS (SELECT 1 FROM lesson_layouts WHERE lesson_id=NEW.lesson_id)', 'lesson has no layout'),
                ('NEW.seat_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM seats s JOIN lesson_layouts l ON l.layout_id=s.layout_id WHERE l.lesson_id=NEW.lesson_id AND s.id=NEW.seat_id)', 'seat belongs to another layout'),
                ('(NEW.previous_id IS NULL AND EXISTS (SELECT 1 FROM seat_assignments WHERE lesson_id=NEW.lesson_id AND student_id=NEW.student_id)) OR (NEW.previous_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM seat_assignments a WHERE a.id=NEW.previous_id AND a.lesson_id=NEW.lesson_id AND a.student_id=NEW.student_id AND NOT EXISTS (SELECT 1 FROM seat_assignments n WHERE n.previous_id=a.id)))', 'stale seat revision'),
                ('NEW.seat_id IS NOT NULL AND EXISTS (SELECT 1 FROM seat_assignments a WHERE a.lesson_id=NEW.lesson_id AND a.seat_id=NEW.seat_id AND a.student_id<>NEW.student_id AND NOT EXISTS (SELECT 1 FROM seat_assignments n WHERE n.previous_id=a.id))', 'seat is occupied')]
        guard(table, 'insert', 'INSERT', checks,
              (f'PERFORM id FROM lessons WHERE id={lesson} FOR UPDATE;' +
               ('PERFORM id FROM seating_layouts WHERE id=NEW.layout_id FOR UPDATE;' if table == 'lesson_layouts' else '')) if pg else '')
    correction_lesson = '(SELECT lesson_id FROM behavior_events WHERE id=NEW.event_id)'
    guard('behavior_corrections', 'insert', 'INSERT', [
        (closed.replace('NEW.lesson_id', correction_lesson), 'academic term is closed'),
        (member.replace('NEW.lesson_id', correction_lesson), 'student is outside fixed roster'),
        (eligible.replace('NEW.lesson_id', correction_lesson), 'student has no dated participation evidence'),
        ("length(trim(NEW.reason))=0 OR length(trim(NEW.source))=0", 'correction reason and source are required')],
        'PERFORM id FROM behavior_events WHERE id=NEW.event_id FOR UPDATE;' if pg else '')
