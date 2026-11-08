"""Versioned, typed full-database XLSX snapshots, independent of Smart Import."""
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

from openpyxl import Workbook, load_workbook
from sqlalchemy import Boolean, Date, DateTime, Integer, Numeric, String, Time, select, text

from app.models import Base
from app.models.education import UTCDateTime
from app.ui.data.membership_migration import set_membership_import_mode
from app.ui.data.academic_migration import _education_guards
from app.ui.data.schedule_migration import (
    _install_postgresql_history_guards, _install_sqlite_history_guards,
)


MANIFEST = "_diary_archive"
MAGIC = "DigitalDiaryApp full teaching archive"
VERSION = 1


def _tables():
    tables = list(Base.metadata.sorted_tables)
    # There is no FK from lessons to schedule-group links, but the guards require them.
    links = next(t for t in tables if t.name == "schedulegrouplinks")
    tables.remove(links)
    tables.insert(tables.index(next(t for t in tables if t.name == "lessons")), links)
    criteria = next(t for t in tables if t.name == 'checklist_criteria')
    tables.remove(criteria)
    tables.insert(tables.index(next(t for t in tables if t.name == 'assessment_attempts')), criteria)
    return tables


def _kind(column):
    typ = column.type
    if isinstance(typ, UTCDateTime):
        return "utc_datetime"
    for cls, name in ((Boolean, "boolean"), (Integer, "integer"),
                      (Numeric, "decimal"), (DateTime, "datetime"),
                      (Date, "date"), (Time, "time"), (String, "string")):
        if isinstance(typ, cls):
            return name
    raise ValueError(f"Unsupported archive type: {column}")


def _schema():
    return [(t.name, c.name, _kind(c), bool(c.nullable)) for t in _tables() for c in t.columns]


def _encode(value, column):
    if value is None:
        return "\\N"
    kind = _kind(column)
    if kind == "string":
        return "\\E" if value == "" else "\\" + value if value.startswith("\\") else value
    if kind == "boolean":
        return bool(value)
    return value.isoformat() if isinstance(value, (date, datetime, time)) else str(value)


def _decode(value, column):
    if value == "\\N":
        if not column.nullable:
            raise ValueError(f"NULL in required column {column}")
        return None
    kind = _kind(column)
    if kind == "string":
        if not isinstance(value, str):
            raise ValueError(f"Expected text in {column}")
        value = "" if value == "\\E" else value[1:] if value.startswith("\\\\") else value
        if column.type.length and len(value) > column.type.length:
            raise ValueError(f"Text too long in {column}")
        return value
    if kind == "boolean":
        if type(value) is not bool:
            raise ValueError(f"Expected boolean in {column}")
        return value
    if not isinstance(value, str):
        raise ValueError(f"Expected typed text in {column}")
    if kind == "integer":
        result = int(value)
        if str(result) != value:
            raise ValueError(f"Invalid integer in {column}")
        return result
    if kind == "decimal":
        result = Decimal(value)
        if not result.is_finite() or result != result.quantize(Decimal(1).scaleb(-column.type.scale)):
            raise ValueError(f"Invalid decimal precision in {column}")
        if abs(result) >= Decimal(10) ** (column.type.precision - column.type.scale):
            raise ValueError(f"Decimal overflow in {column}")
        return result
    result = {"date": date.fromisoformat, "time": time.fromisoformat,
              "datetime": datetime.fromisoformat, "utc_datetime": datetime.fromisoformat}[kind](value)
    if kind == "utc_datetime":
        if result.tzinfo is None:
            raise ValueError(f"Timezone required in {column}")
        return result.astimezone(timezone.utc)
    return result


def _append(sheet, values):
    from openpyxl.cell import WriteOnlyCell
    cells = []
    for value in values:
        cell = WriteOnlyCell(sheet, value=value)
        if isinstance(value, str):
            if len(value) > 32767:
                raise ValueError("Excel cell text exceeds 32767 characters.")
            cell.data_type = "s"  # Never interpret user strings beginning with '=' as formulas.
        cells.append(cell)
    sheet.append(cells)


def export_archive(session, path) -> Path:
    """Export all metadata tables without committing or changing the source database."""
    path = Path(path)
    if session.new or session.dirty or session.deleted:
        raise ValueError("Save pending edits before exporting an archive.")
    workbook = Workbook(write_only=True)
    manifest = workbook.create_sheet(MANIFEST)
    _append(manifest, [MAGIC, VERSION])
    _append(manifest, ["table", "column", "type", "nullable"])
    for row in _schema():
        _append(manifest, row)
    with session.no_autoflush:
        for table in _tables():
            if len(table.name) > 31:
                raise ValueError("Archive sheet name exceeds Excel limits.")
            sheet = workbook.create_sheet(table.name)
            _append(sheet, list(table.columns.keys()))
            for index, row in enumerate(session.execute(select(table).order_by(*table.primary_key.columns)).mappings(), 2):
                if table.name == 'assessment_attempts' and not row['finalized']:
                    raise ValueError('Archive contains an unfinalized assessment attempt.')
                if index > 1048576:
                    raise ValueError(f"Table {table.name} exceeds Excel row limits.")
                _append(sheet, [_encode(row[c.name], c) for c in table.columns])
    workbook.save(path)
    return path


def preview_archive(path):
    """Return fully typed rows, None for ordinary workbooks, or reject corrupt archives."""
    workbook = load_workbook(path, read_only=True, data_only=False, keep_links=False)
    try:
        if MANIFEST not in workbook.sheetnames:
            return None
        manifest = [tuple(row) + (None,) * (4 - len(row)) for row in workbook[MANIFEST].values]
        if manifest != [(MAGIC, VERSION, None, None), ("table", "column", "type", "nullable"), *_schema()]:
            raise ValueError("Unsupported archive version or altered schema manifest.")
        if workbook.sheetnames != [MANIFEST, *[t.name for t in _tables()]]:
            raise ValueError("Archive sheets are missing, unexpected, or out of order.")
        data = {}
        for table in _tables():
            rows = iter(workbook[table.name].iter_rows())
            header = next(rows, ())
            if tuple(c.value for c in header) != tuple(table.columns.keys()):
                raise ValueError(f"Altered columns in {table.name}")
            data[table.name] = []
            for row in rows:
                if len(row) != len(table.columns) or any(c.data_type == "f" for c in row):
                    raise ValueError(f"Invalid row or formula in {table.name}")
                try:
                    data[table.name].append({c.name: _decode(cell.value, c) for c, cell in zip(table.columns, row)})
                except (ValueError, TypeError, InvalidOperation) as exc:
                    raise ValueError(f"Invalid archive data in {table.name}: {exc}") from exc
        _validate(data)
        return data
    finally:
        workbook.close()


def _validate(data):
    """Cross-table invariants not expressible by a single SQL CHECK constraint."""
    tables = _tables()
    if set(data) != {t.name for t in tables}:
        raise ValueError("Archive must include every registered table.")
    by = {}
    for table in tables:
        by[table.name] = {}
        for row in data[table.name]:
            if set(row) != set(table.columns.keys()):
                raise ValueError(f"Altered columns in {table.name}")
            for col in table.columns:
                value = row[col.name]
                expected = {'integer': int, 'boolean': bool, 'string': str, 'decimal': Decimal,
                            'date': date, 'time': time, 'datetime': datetime, 'utc_datetime': datetime}[_kind(col)]
                if value is not None and type(value) is not expected:
                    raise ValueError(f'Invalid typed value in {col}')
                if _decode(_encode(row[col.name], col), col) != row[col.name]:
                    raise ValueError(f"Invalid typed value in {col}")
            if type(row['id']) is not int or row['id'] <= 0 or row['id'] in by[table.name]:
                raise ValueError(f"Invalid or duplicate ID in {table.name}")
            by[table.name][row['id']] = row
    def parent(table, ident):
        try:
            return by[table][ident]
        except KeyError as exc:
            raise ValueError(f"Missing reference {table}:{ident}") from exc
    for table in tables:
        for row in data[table.name]:
            for fk in table.foreign_keys:
                if row[fk.parent.name] is not None:
                    parent(fk.column.table.name, row[fk.parent.name])
    def term_for(offering_id):
        return parent('academic_terms', parent('course_offerings', offering_id)['term_id'])
    def bounds(term):
        return term['start_date'], term['start_date'] + timedelta(weeks=term['total_weeks'])
    for term in data['academic_terms']:
        if term['status'] not in {'open', 'closed'}:
            raise ValueError('Unknown academic term status.')
        year = parent('academic_years', term['year_id'])
        start, end = bounds(term)
        if start.weekday() or not year['start_date'] <= start < end <= year['end_date']:
            raise ValueError('Term is outside its academic year or not Monday-aligned.')
    for module in data['teaching_modules']:
        start, end = bounds(term_for(module['offering_id']))
        if not start <= module['start_date'] < module['end_date'] <= end:
            raise ValueError('Module is outside its term.')
        if any(other['id'] != module['id'] and other['offering_id'] == module['offering_id']
               and other['start_date'] < module['end_date'] and module['start_date'] < other['end_date']
               for other in data['teaching_modules']):
            raise ValueError('Module periods overlap.')
    offering_groups = {}
    for link in data['course_offering_groups']:
        offering_groups.setdefault(link['offering_id'], set()).add(link['group_id'])
    schedule_groups = {}
    for link in data['schedulegrouplinks']:
        schedule_groups.setdefault(link['schedule_id'], set()).add(link['group_id'])
    for schedule in data['schedules']:
        if schedule['offering_id'] is not None:
            groups = schedule_groups.get(schedule['id'], set())
            if not groups or not groups <= offering_groups.get(schedule['offering_id'], set()):
                raise ValueError('Schedule has missing groups or groups outside its offering.')
    for lesson in data['lessons']:
        schedule = parent('schedules', lesson['schedule_id'])
        if lesson['date'] < schedule['effective_from'] or (schedule['effective_until'] and lesson['date'] >= schedule['effective_until']):
            raise ValueError('Lesson is outside schedule revision.')
        if schedule.get('offering_id'):
            start, end = bounds(term_for(schedule['offering_id']))
            if not start <= lesson['date'] < end:
                raise ValueError('Lesson is outside its academic term.')
        basis = lesson.get('roster_time_basis', 'unknown')
        completed_at = lesson.get('roster_completed_at')
        if basis not in {'unknown', 'utc'}:
            raise ValueError('Unknown roster time basis.')
        if basis == 'utc' and (not lesson['participants_complete'] or completed_at is None):
            raise ValueError('UTC roster basis requires a completed roster and timestamp.')
        # Legacy fixed rosters may have neither a timestamp nor a known time basis.
        # Lesson dates are local calendar dates, not UTC instants. Without a
        # recorded lesson timezone, allow the one-day UTC/local boundary.
        if basis == 'utc' and completed_at.date() + timedelta(days=1) < lesson['date']:
            raise ValueError('Roster completion precedes the lesson date.')
    seminar_slots = set()
    cancelled_events = {c['event_id'] for c in data['event_cancellations']}
    for event in data['assessment_events']:
        module = parent('teaching_modules', event['module_id'])
        if event['lesson_id'] is not None:
            lesson = parent('lessons', event['lesson_id'])
            schedule = parent('schedules', lesson['schedule_id'])
            if schedule['offering_id'] != module['offering_id'] or not module['start_date'] <= lesson['date'] < module['end_date']:
                raise ValueError('Assessment lesson does not belong to its module.')
        if event['category'] in {'seminar_start', 'seminar_end'} and event['id'] not in cancelled_events:
            slot = (event['lesson_id'], event['category'])
            if event['lesson_id'] is None or slot in seminar_slots:
                raise ValueError('Seminar assessment requires a unique lesson slot.')
            seminar_slots.add(slot)
    for lab in data['lab_works']:
        if parent('assessment_events', lab['event_id'])['category'] != 'lab':
            raise ValueError('Lab work requires a lab assessment.')
    for attempt in data['assessment_attempts']:
        if not attempt['finalized']:
            raise ValueError('Archive contains an unfinalized assessment attempt.')
        event = parent('assessment_events', attempt['event_id'])
        if attempt['points'] > event['max_points'] or (event['max_attempts'] is not None and attempt['attempt_number'] > event['max_attempts']):
            raise ValueError('Assessment attempt exceeds event limits.')
        if not attempt['passed'] and attempt['points'] != 0:
            raise ValueError('Failed attempt has points.')
        if attempt['passed'] and not attempt['work_completed']:
            raise ValueError('Passed assessment requires completed work.')
        term = term_for(parent('teaching_modules', event['module_id'])['offering_id'])
        start, end = bounds(term)
        offering_id = parent('teaching_modules', event['module_id'])['offering_id']
        eligible = any(m['student_id'] == attempt['student_id']
                       and m['group_id'] in offering_groups.get(offering_id, set())
                       and m['start_date'] < end and (m['end_date'] is None or start < m['end_date'])
                       and (m['origin'] != 'migrated_unknown' or m['known_from'] < end)
                       for m in data['groupmemberships'])
        evidence = any(p['student_id'] == attempt['student_id']
                       and parent('schedules', parent('lessons', p['lesson_id'])['schedule_id'])['offering_id'] == offering_id
                       for p in data['lessonparticipants'])
        if not (eligible or evidence):
            raise ValueError('Student is not eligible for assessment.')
        version = attempt['checklist_version_id']
        if version is not None:
            lab = parent('lab_works', parent('checklist_versions', version)['lab_id'])
            if lab['event_id'] != event['id']:
                raise ValueError('Checklist belongs to a different assessment.')
        if attempt['consultation_visit_id'] is not None and parent('consultation_visits', attempt['consultation_visit_id'])['student_id'] != attempt['student_id']:
            raise ValueError('Consultation visit belongs to a different student.')
        answers = [a for a in data['criterion_answers'] if a['attempt_id'] == attempt['id']]
        labs = [lab for lab in data['lab_works'] if lab['event_id'] == event['id']]
        if event['category'] == 'lab':
            if not labs:
                raise ValueError('Lab attempt requires lab work.')
            criteria = {c['id'] for c in data['checklist_criteria'] if c['version_id'] == version}
            if version is None or not criteria or {a['criterion_id'] for a in answers} != criteria:
                raise ValueError('Lab attempt requires a complete versioned checklist.')
            if attempt['passed'] and not (attempt['work_completed'] and attempt['defended'] and attempt['question_passed'] is True and all(a['satisfied'] for a in answers)):
                raise ValueError('Passed lab attempt has unmet defense requirements.')
        elif version is not None or answers:
            raise ValueError('Non-lab attempt has checklist answers.')
    for answer in data['criterion_answers']:
        attempt = parent('assessment_attempts', answer['attempt_id'])
        if parent('checklist_criteria', answer['criterion_id'])['version_id'] != attempt['checklist_version_id']:
            raise ValueError('Answer does not belong to the attempt checklist.')
    numbers = {}
    for attempt in data['assessment_attempts']:
        numbers.setdefault((attempt['event_id'], attempt['student_id']), []).append(attempt['attempt_number'])
    if any(sorted(values) != list(range(1, len(values) + 1)) for values in numbers.values()):
        raise ValueError('Assessment attempt sequence has gaps or duplicates.')
    for correction in data['result_corrections']:
        attempt = parent('assessment_attempts', correction['attempt_id'])
        event = parent('assessment_events', attempt['event_id'])
        if event['category'] == 'lab' and correction['passed'] and not attempt['passed']:
            raise ValueError('Failed lab requires a new defense, not a passing correction.')
        if correction['points'] > event['max_points'] or (not correction['passed'] and correction['points']):
            raise ValueError('Invalid correction score.')
        if not correction['reason'].strip() or not correction['source'].strip():
            raise ValueError('Correction requires reason and source.')
    for cancellation in data['event_cancellations']:
        if any(a['event_id'] == cancellation['event_id'] for a in data['assessment_attempts']):
            raise ValueError('Cancelled assessment has attempts.')
    for day in data['non_teaching_days']:
        start, end = bounds(parent('academic_terms', day['term_id']))
        if not start <= day['date'] < end:
            raise ValueError('Non-teaching day is outside its term.')
    for entry in data['plan_entries']:
        plan = parent('individual_plans', parent('plan_stages', entry['stage_id'])['plan_id'])
        if entry['consultation_visit_id'] is not None and parent('consultation_visits', entry['consultation_visit_id'])['student_id'] != plan['student_id']:
            raise ValueError('Plan consultation belongs to another student.')
    for attendance in data['attendances']:
        revisions = [r for r in data['attendance_revisions'] if r['attendance_id'] == attendance['id']]
        if revisions:
            latest = max(revisions, key=lambda r: r['id'])
            if attendance['is_visited'] != (latest['status'] in {'present', 'late'}):
                raise ValueError('Attendance projection contradicts its latest revision.')
        for revision in revisions:
            if not revision['reason'].strip() or not revision['source'].strip():
                raise ValueError('Attendance revision requires reason and source.')
            if revision['late_seconds'] is not None and revision['late_seconds'] < 0:
                raise ValueError('Negative lateness is invalid.')
            if revision['status'] == 'late':
                lesson = parent('lessons', attendance['lesson_id'])
                completed = lesson['roster_completed_at']
                arrival = revision['arrived_at']
                if (arrival is None or not lesson['participants_complete']
                        or lesson['roster_time_basis'] != 'utc' or completed is None):
                    raise ValueError('Late attendance requires arrival and known UTC roll-call completion.')
                completed = completed.replace(tzinfo=timezone.utc) if completed.tzinfo is None else completed.astimezone(timezone.utc)
                seconds = max(0, int((arrival - completed).total_seconds()))
                if seconds <= 0 or revision['late_seconds'] != seconds:
                    raise ValueError('Late attendance duration contradicts its timestamps.')
            if revision['status'] in {'absent', 'excused'} and revision['arrived_at'] is not None:
                raise ValueError('Absent or excused attendance cannot have an arrival timestamp.')
    dispositions = {}
    for disposition in data['lesson_dispositions']:
        dispositions.setdefault(disposition['lesson_id'], []).append(disposition)
    for entries in dispositions.values():
        ordered = sorted(entries, key=lambda r: r['id'])
        if any(entry['status'] == 'moved' for entry in ordered[:-1]):
            raise ValueError('A moved lesson cannot have subsequent dispositions.')
        held = False
        for entry in ordered:
            lesson = parent('lessons', entry['lesson_id'])
            if not entry['reason'].strip():
                raise ValueError('Lesson disposition requires a reason.')
            if entry['status'] == 'moved':
                replacement = parent('lessons', entry['replacement_lesson_id'])
                source_schedule = parent('schedules', lesson['schedule_id'])
                target_schedule = parent('schedules', replacement['schedule_id'])
                if replacement['id'] == lesson['id'] or (
                    source_schedule['id'] != target_schedule['id'] and
                    (source_schedule['offering_id'] is None or source_schedule['offering_id'] != target_schedule['offering_id'])
                ):
                    raise ValueError('Replacement lesson has incompatible academic context.')
            elif entry['replacement_lesson_id'] is not None:
                raise ValueError('Only moved lessons can have a replacement.')
            if entry['status'] != 'held':
                protected = held or lesson['participants_complete'] or any(
                    row['lesson_id'] == lesson['id'] for table in
                    ('lessonparticipants', 'attendances', 'marks', 'comments') for row in data[table])
                events = {row['id'] for row in data['assessment_events'] if row['lesson_id'] == lesson['id']}
                protected = protected or any(row['event_id'] in events and row['occurred_at'] <= entry['occurred_at']
                                            for row in data['assessment_attempts'])
                if protected:
                    raise ValueError('A conducted or filled lesson cannot be cancelled or moved in an archive.')
            held = held or entry['status'] == 'held'


def restore_archive(repository, data):
    """Restore IDs once into an empty database; all DDL and inserts are transactional."""
    session = repository.session
    if session.new or session.dirty or session.deleted:
        raise ValueError('Restore requires a session without pending edits.')
    _validate(data)
    session.rollback()
    try:
        connection = session.connection()
        if connection.dialect.name == 'sqlite':
            connection.exec_driver_sql('BEGIN IMMEDIATE')
        else:
            names = ', '.join(connection.dialect.identifier_preparer.quote(t.name) for t in _tables())
            connection.exec_driver_sql(f'LOCK TABLE {names} IN ACCESS EXCLUSIVE MODE')
        if any(session.scalar(select(t.c.id).limit(1)) is not None for t in _tables()):
            raise ValueError('Full archive restore requires an empty database.')
        set_membership_import_mode(connection, enabled=True)
        # Closed/revised schedules reject even their original group links. Suspend
        # only this INSERT guard in the locked empty restore; DDL rolls back too.
        connection.exec_driver_sql('DROP TRIGGER IF EXISTS schedule_link_history_insert' + (
            ' ON schedulegrouplinks' if connection.dialect.name == 'postgresql' else ''))
        # A historical cancellation must not become invalid merely because time
        # has passed. _validate checks its immutable graph before this locked replay.
        connection.exec_driver_sql('DROP TRIGGER IF EXISTS education_lesson_dispositions_insert' + (
            ' ON lesson_dispositions' if connection.dialect.name == 'postgresql' else ''))
        for table in _tables():
            if table.name == 'event_cancellations':
                continue  # Replayed immediately after each corresponding event below.
            if data[table.name]:
                rows = data[table.name]
                if table.name == 'academic_terms':
                    # Stage closed terms as open only within the locked, empty restore
                    # transaction. Keep every insert guard active; close them before commit.
                    rows = [dict(row, status='open') for row in rows]
                elif table.name == 'groups':
                    # Historical offering links can legitimately reference archived groups.
                    rows = [dict(row, is_archived=False) for row in rows]
                elif table.name == 'assessment_attempts':
                    rows = [dict(row, finalized=False) for row in rows]
                if table.name == 'assessment_events':
                    # Restore cancelled events first, immediately followed by their
                    # cancellations, before inserting their active replacements.
                    cancelled = {r['event_id']: r for r in data['event_cancellations']}
                    for row in sorted(rows, key=lambda r: r['id'] not in cancelled):
                        connection.execute(table.insert(), row)
                        if row['id'] in cancelled:
                            connection.execute(Base.metadata.tables['event_cancellations'].insert(), cancelled[row['id']])
                else:
                    connection.execute(table.insert(), rows)
            if table.name == 'criterion_answers':
                # Finalize only after the complete answer set exists. The same
                # database guard as interactive defense validates the transition.
                attempts = Base.metadata.tables['assessment_attempts']
                for row in data['assessment_attempts']:
                    connection.execute(attempts.update().where(attempts.c.id == row['id']).values(
                        finalized=True, updated_at=row['updated_at']))
        repository._validate_restored_history()
        _education_guards(connection)
        set_membership_import_mode(connection, enabled=False)
        if connection.dialect.name == 'sqlite':
            _install_sqlite_history_guards(connection)
        else:
            _install_postgresql_history_guards(connection)
        terms = Base.metadata.tables['academic_terms']
        for row in data['academic_terms']:
            if row['status'] == 'closed':
                connection.execute(terms.update().where(terms.c.id == row['id']).values(
                    status='closed', updated_at=row['updated_at']))
        groups = Base.metadata.tables['groups']
        for row in data['groups']:
            if row['is_archived']:
                connection.execute(groups.update().where(groups.c.id == row['id']).values(
                    is_archived=True, updated_at=row['updated_at']))
        if connection.dialect.name == 'postgresql':
            for table in _tables():
                # Restart is transactional, unlike setval(), and rolls back with the restore.
                sequence = connection.scalar(text('SELECT pg_get_serial_sequence(:table, :column)'), {'table': table.name, 'column': 'id'})
                if sequence:
                    maximum = max((r['id'] for r in data[table.name]), default=0) + 1
                    quoted = '.'.join(connection.dialect.identifier_preparer.quote(p.strip('"')) for p in sequence.split('.'))
                    connection.exec_driver_sql(f'ALTER SEQUENCE {quoted} RESTART WITH {maximum}')
        session.commit()
    except BaseException:
        session.rollback()
        raise
    session.expire_all()
    return {name: len(rows) for name, rows in data.items()}
