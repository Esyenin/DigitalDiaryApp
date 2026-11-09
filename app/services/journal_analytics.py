"""Read-only, dated journal views shared by cards, analytics and PDF reports."""

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

from sqlalchemy import or_, select

from app.models import (
    AcademicTerm, AcademicYear, AssessmentAttempt, AssessmentEvent, Attendance,
    AttendanceRevision, CourseOffering, CourseOfferingGroup, Discipline, Group,
    GroupMembership, Lesson, LessonDisposition, LessonParticipant, Mark,
    ResultCorrection, Schedule, ScheduleGroupLink, Student, TeachingModule,
)
from app.services.teaching import TeachingService


def cutoff_for(day):
    return datetime.combine(day, time.max).astimezone(timezone.utc)


def utc(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


class JournalAnalytics:
    """No commits, lazy snapshots or inferred percentages from incomplete rosters."""

    def __init__(self, session):
        self.session = session
        self.teaching = TeachingService(session)
        self._student_cache = {}
        self._course_rosters = {}

    def _get(self, model, key):
        item = self.session.get(model, key)
        if item is None:
            raise ValueError(f"{model.__name__} was not found.")
        return item

    def _rows(self, model, *conditions):
        return list(self.session.scalars(select(model).where(*conditions).order_by(model.id)))

    def _bounds(self, term_id, as_of, start_date, end_date):
        day = as_of or date.today()
        lower, upper = start_date, min(end_date or day, day)
        if term_id is not None:
            term = self._get(AcademicTerm, term_id)
            lower = max(lower or term.start_date, term.start_date)
            upper = min(upper, term.start_date + timedelta(weeks=term.total_weeks) - timedelta(days=1))
        if lower is not None and lower > upper:
            return day, lower, upper
        return day, lower, upper

    def _members(self, group_id, lower, upper):
        return self._rows(GroupMembership, GroupMembership.group_id == group_id,
            GroupMembership.start_date <= upper, GroupMembership.known_from <= upper,
            or_(GroupMembership.end_date.is_(None), GroupMembership.end_date > GroupMembership.start_date),
            or_(GroupMembership.end_date.is_(None), GroupMembership.end_date > (lower or date.min)))

    def _course_ids(self, course, lower, upper, day):
        cache_key = (course.id, lower, upper, day)
        if cache_key in self._course_rosters:
            return self._course_rosters[cache_key]
        term = self._get(AcademicTerm, course.term_id)
        lower = max(lower or term.start_date, term.start_date)
        upper = min(upper, term.start_date + timedelta(weeks=term.total_weeks) - timedelta(days=1))
        if lower > upper:
            return set()
        group_ids = [link.group_id for link in self._rows(CourseOfferingGroup, CourseOfferingGroup.offering_id == course.id)]
        ids = {row.student_id for group_id in group_ids for row in self._members(group_id, lower, upper)}
        ids.update(self.session.scalars(select(LessonParticipant.student_id).join(
            Lesson, Lesson.id == LessonParticipant.lesson_id).join(Schedule, Schedule.id == Lesson.schedule_id)
            .where(Schedule.offering_id == course.id, Lesson.date >= lower, Lesson.date <= upper)))
        ids.update(self.session.scalars(select(AssessmentAttempt.student_id).join(AssessmentEvent).join(TeachingModule)
            .where(TeachingModule.offering_id == course.id, AssessmentAttempt.finalized.is_(True),
                   AssessmentAttempt.occurred_at <= cutoff_for(day))))
        self._course_rosters[cache_key] = ids
        return ids

    def _history(self, student):
        rows = []
        for membership in self._rows(GroupMembership, GroupMembership.student_id == student.id):
            group = self._get(Group, membership.group_id)
            rows.append(dict(group_id=group.id, group=group.name, start=membership.start_date,
                             end=membership.end_date, known_from=membership.known_from, origin=membership.origin))
        return rows

    def _lesson_ids(self, student_id, lower, upper, offering_ids=None, group_id=None):
        stmt = select(Lesson).join(Schedule).where(Lesson.date <= upper)
        if lower is not None:
            stmt = stmt.where(Lesson.date >= lower)
        if offering_ids is not None:
            stmt = stmt.where(Schedule.offering_id.in_(offering_ids))
        if group_id is not None:
            stmt = stmt.where(Schedule.id.in_(select(ScheduleGroupLink.schedule_id).where(ScheduleGroupLink.group_id == group_id)))
        memberships = self._rows(GroupMembership, GroupMembership.student_id == student_id)
        participant_ids = set(self.session.scalars(select(LessonParticipant.lesson_id).where(LessonParticipant.student_id == student_id)))
        evidence_ids = set(self.session.scalars(select(Attendance.lesson_id).where(Attendance.student_id == student_id)))
        evidence_ids.update(self.session.scalars(select(Mark.lesson_id).where(Mark.student_id == student_id)))
        result = []
        for lesson in self.session.scalars(stmt.order_by(Lesson.date, Lesson.id)):
            if lesson.id in participant_ids or lesson.id in evidence_ids:
                result.append(lesson)
                continue
            if lesson.participants_complete:
                continue
            groups = {link.group_id for link in lesson.schedule.group_links}
            if any(row.group_id in groups and row.start_date <= lesson.date
                   and (row.end_date is None or row.end_date > lesson.date) for row in memberships):
                result.append(lesson)
        return result

    def attendance(self, student_id, *, as_of=None, start_date=None, end_date=None,
                   offering_ids=None, group_id=None, term_id=None):
        with self.session.no_autoflush:
            day, lower, upper = self._bounds(term_id, as_of, start_date, end_date)
            result = dict(present=0, late=0, excused=0, absent=0, unknown=0, total=0,
                          percentage=None, complete=True, late_seconds=0, records=[])
            if lower is not None and lower > upper:
                return result
            for lesson in self._lesson_ids(student_id, lower, upper, offering_ids, group_id):
                changes = self._rows(LessonDisposition, LessonDisposition.lesson_id == lesson.id)
                changes = [row for row in changes if utc(row.occurred_at) <= cutoff_for(day)]
                if changes and changes[-1].status in {'cancelled', 'holiday', 'moved'}:
                    continue
                participant = self.session.scalar(select(LessonParticipant).where(
                    LessonParticipant.lesson_id == lesson.id, LessonParticipant.student_id == student_id))
                membership = self.session.scalar(select(GroupMembership).where(
                    GroupMembership.student_id == student_id, GroupMembership.group_id.in_(
                        [link.group_id for link in lesson.schedule.group_links]),
                    GroupMembership.start_date <= lesson.date,
                    or_(GroupMembership.end_date.is_(None), GroupMembership.end_date > lesson.date)))
                if group_id is not None:
                    recorded_group = participant.group_id if participant is not None else None
                    if recorded_group is None and membership is not None and membership.known_from <= lesson.date:
                        recorded_group = membership.group_id
                    if recorded_group is not None and recorded_group != group_id:
                        continue
                    if recorded_group is None and len(lesson.schedule.group_links) > 1:
                        result['total'] += 1
                        result['unknown'] += 1
                        result['complete'] = False
                        continue
                roster_known = lesson.participants_complete and participant is not None
                if lesson.roster_completed_at is not None and lesson.roster_time_basis == 'utc':
                    roster_known = roster_known and utc(lesson.roster_completed_at) <= cutoff_for(day)
                elif day < date.today():
                    roster_known = False
                if membership and membership.origin == 'migrated_unknown' and membership.known_from > lesson.date and not participant:
                    roster_known = False
                attendance = self.session.scalar(select(Attendance).where(Attendance.lesson_id == lesson.id,
                                                                         Attendance.student_id == student_id))
                revisions = self._rows(AttendanceRevision, AttendanceRevision.attendance_id == attendance.id) if attendance else []
                dated = [row for row in revisions if utc(row.occurred_at) <= cutoff_for(day)]
                revision = dated[-1] if dated else None
                if revision is not None:
                    state = revision.status
                    arrival, late = revision.arrived_at, revision.late_seconds
                elif attendance is not None and not revisions:
                    state, arrival, late = ('present' if attendance.is_visited else 'absent'), None, None
                    roster_known = False
                else:
                    state, arrival, late = ('absent' if roster_known else 'unknown'), None, None
                result['total'] += 1
                result[state] += 1
                result['late_seconds'] += late or 0
                result['complete'] = result['complete'] and roster_known
                result['records'].append(dict(lesson_id=lesson.id, date=lesson.date, status=state,
                    arrived_at=arrival, late_seconds=late, complete=roster_known,
                    reason=revision.reason if revision else '', source=revision.source if revision else 'legacy/unknown'))
                result['records'][-1]['previous_status'] = revision.previous_status if revision else None
            if result['complete'] and result['total']:
                result['percentage'] = (Decimal(result['present'] + result['late']) * 100 / result['total']).quantize(Decimal('0.01'))
            return result

    def student(self, student_id, term_id=None, as_of=None, start_date=None, end_date=None, offering_ids=None):
        with self.session.no_autoflush:
            cache_key = (student_id, term_id, as_of, start_date, end_date,
                         tuple(sorted(offering_ids)) if offering_ids is not None else None)
            if cache_key in self._student_cache:
                return self._student_cache[cache_key]
            student = self._get(Student, student_id)
            day, lower, upper = self._bounds(term_id, as_of, start_date, end_date)
            history = self._history(student)
            current_group = self._get(Group, student.group_id).name
            result = dict(id=student.id, name=' '.join(filter(None, [student.surname, student.first_name, student.patronymic])),
                          current_group=current_group, status=student.status, memberships=history,
                          courses=[], legacy_marks=[], behavior=[], warnings=[], as_of=day)
            group_on_date = [row['group'] for row in history if row['start'] <= day
                             and (row['end'] is None or row['end'] > day) and row['known_from'] <= day]
            result['group_on_date'] = group_on_date[0] if len(group_on_date) == 1 else None
            courses = self._rows(CourseOffering, *([CourseOffering.term_id == term_id] if term_id else []))
            if offering_ids is not None:
                courses = [course for course in courses if course.id in offering_ids]
            for course in courses:
                if student.id not in self._course_ids(course, lower, upper, day):
                    continue
                summary = self.teaching.summary(course.id, student.id, as_of=day, start_date=lower, end_date=upper)
                term = self._get(AcademicTerm, course.term_id)
                discipline = self._get(Discipline, course.discipline_id)
                year = self._get(AcademicYear, term.year_id)
                group_ids = {link.group_id for link in self._rows(CourseOfferingGroup, CourseOfferingGroup.offering_id == course.id)}
                complete = not any(row['group_id'] in group_ids and row['origin'] == 'migrated_unknown'
                                   and row['known_from'] > max(lower or term.start_date, term.start_date) for row in history)
                event_ids = {row['id'] for row in summary['events']}
                configuration_known = day >= date.today() or all(row.configured_at is not None for row in
                    self._rows(AssessmentEvent, AssessmentEvent.id.in_(event_ids)))
                complete = complete and configuration_known
                attempts = self._rows(AssessmentAttempt, AssessmentAttempt.event_id.in_(event_ids),
                                      AssessmentAttempt.student_id == student.id, AssessmentAttempt.finalized.is_(True))
                attempts = [row for row in attempts if utc(row.occurred_at) <= cutoff_for(day)]
                payload = dict(id=course.id, name=discipline.name, offering_name=course.name, term_id=term.id,
                    term_name=term.name, year_name=year.name, earned=summary['earned'], maximum=summary['maximum'],
                    remaining=summary['remaining'], debts=summary['debts'], pending=summary['pending'],
                    event_results=summary['events'], modules=summary['modules'], history_complete=complete,
                    scale100=summary['maximum'] == Decimal(100), attempts=[dict(id=row.id,event_id=row.event_id,
                        number=row.attempt_number, points=row.points, passed=row.passed, work_completed=row.work_completed,
                        defended=row.defended, occurred_at=row.occurred_at, checklist_version_id=row.checklist_version_id,
                        consultation_visit_id=row.consultation_visit_id) for row in attempts])
                payload['excellent'] = (payload['scale100'] and complete and not payload['debts'] and not payload['pending']
                                        and Decimal(85) <= payload['earned'] <= Decimal(100))
                result['courses'].append(payload)
            marks = self._rows(Mark, Mark.student_id == student.id)
            for mark in marks:
                lesson = self._get(Lesson, mark.lesson_id)
                if offering_ids is not None and lesson.schedule.offering_id not in offering_ids:
                    continue
                if lesson.date <= upper and (lower is None or lesson.date >= lower):
                    result['legacy_marks'].append(dict(id=mark.id, lesson_id=lesson.id, lesson_date=lesson.date,
                        topic=lesson.topic or '', value=mark.data,
                        group_name=', '.join(link.group.name for link in lesson.schedule.group_links)))
            result['attendance'] = self.attendance(student.id, term_id=term_id, as_of=day, start_date=lower,
                end_date=upper, offering_ids=offering_ids)
            try:
                from app.services.journal_activity import ActivityService
            except ImportError:
                ActivityService = None
            if ActivityService is not None:
                result['behavior'] = ActivityService(self.session).behavior_for_student(student.id,
                    start_date=lower, end_date=upper + timedelta(days=1), as_of=cutoff_for(day))
                if offering_ids is not None:
                    result['behavior'] = [row for row in result['behavior'] if
                        self._get(Lesson, row['lesson_id']).schedule.offering_id in offering_ids]
            if not result['attendance']['complete']:
                result['warnings'].append('Attendance history is incomplete; no precise percentage is available.')
            if any(not course['history_complete'] for course in result['courses']):
                result['warnings'].append('Earlier group membership or assessment configuration is uncertain.')
            if result['legacy_marks']:
                result['warnings'].append('Legacy marks are separate; past edits have no reconstructible grading history.')
            self._student_cache[cache_key] = result
            return result

    def group(self, group_id, term_id=None, as_of=None, start_date=None, end_date=None, offering_ids=None):
        with self.session.no_autoflush:
            group = self._get(Group, group_id)
            day, lower, upper = self._bounds(term_id, as_of, start_date, end_date)
            exact_date = term_id is None and start_date is None and end_date is None
            roster_lower = upper if exact_date else lower
            memberships = self._members(group.id, roster_lower, upper) if roster_lower is None or roster_lower <= upper else []
            ids = {row.student_id for row in memberships}
            evidence = select(LessonParticipant.student_id).join(Lesson).where(
                LessonParticipant.group_id == group.id, Lesson.date <= upper)
            if roster_lower is not None:
                evidence = evidence.where(Lesson.date >= roster_lower)
            evidence_ids = set(self.session.scalars(evidence))
            for student_id in evidence_ids:
                if exact_date:
                    known = self._rows(GroupMembership, GroupMembership.student_id == student_id,
                        GroupMembership.start_date <= upper, GroupMembership.known_from <= upper,
                        or_(GroupMembership.end_date.is_(None), GroupMembership.end_date > upper))
                    if known and all(row.group_id != group.id for row in known):
                        continue
                ids.add(student_id)
            relevant_courses = set(self.session.scalars(select(CourseOfferingGroup.offering_id).where(
                CourseOfferingGroup.group_id == group.id)))
            if offering_ids is not None:
                relevant_courses.intersection_update(offering_ids)
            students = []
            for key in ids:
                base = self.student(key, term_id, day, lower, upper, sorted(relevant_courses))
                group_attendance = self.attendance(key, term_id=term_id, as_of=day, start_date=lower,
                    end_date=upper, offering_ids=offering_ids, group_id=group.id)
                # Do not mutate cached general student views reused by another group/report.
                warnings = [item for item in base['warnings'] if not item.startswith('Attendance history')]
                if not group_attendance['complete']:
                    warnings.append('Attendance history is incomplete; no precise percentage is available.')
                row = dict(base, attendance=group_attendance, warnings=warnings)
                if offering_ids is None:
                    unfiltered = self.student(key, term_id, day, lower, upper)
                    row['legacy_marks'] = [mark for mark in unfiltered['legacy_marks'] if any(
                        link.group_id == group.id for link in self._get(Lesson, mark['lesson_id']).schedule.group_links)]
                students.append(row)
            students.sort(key=lambda row: (row['name'].casefold(), row['id']))
            complete = not any(row.origin == 'migrated_unknown' and row.known_from > (roster_lower or date.min)
                               for row in memberships)
            # A migrated period which is not yet known can hide otherwise missing members.
            complete = complete and not any(row.known_from > upper for row in self._rows(GroupMembership,
                GroupMembership.group_id == group.id, GroupMembership.start_date <= upper))
            result = dict(id=group.id, name=group.name, as_of=day, students=students,
                membership_complete=complete, warnings=[], courses=[], debtors_count=0, attention=[], excellent=[])
            result['debtors_count'] = sum(any(course['debts'] for course in row['courses']) for row in students)
            result['attention'] = [row['id'] for row in students if any(course['debts'] for course in row['courses'])
                or row['attendance']['absent'] or row['attendance']['late'] or any(
                    item['polarity'] == 'negative' for item in row['behavior'])]
            result['excellent'] = [row['id'] for row in students if row['courses'] and all(course['excellent'] for course in row['courses'])]
            attendance = dict(present=0, late=0, excused=0, absent=0, unknown=0, total=0, late_seconds=0,
                              complete=complete, percentage=None)
            historical_ids = {row.student_id for row in self._members(group.id, lower, upper)}
            history_evidence = select(LessonParticipant.student_id).join(Lesson).where(
                LessonParticipant.group_id == group.id, Lesson.date <= upper)
            if lower is not None:
                history_evidence = history_evidence.where(Lesson.date >= lower)
            historical_ids.update(self.session.scalars(history_evidence))
            historical_ids.update(ids)
            for student_id in historical_ids:
                values = self.attendance(student_id, term_id=term_id, as_of=day, start_date=lower,
                                         end_date=upper, offering_ids=offering_ids, group_id=group.id)
                for key in ('present','late','excused','absent','unknown','total','late_seconds'):
                    attendance[key] += values[key]
                attendance['complete'] = attendance['complete'] and values['complete']
            if attendance['complete'] and attendance['total']:
                attendance['percentage'] = (Decimal(attendance['present']+attendance['late'])*100/attendance['total']).quantize(Decimal('0.01'))
            result['attendance'] = attendance
            course_ids = sorted({course['id'] for student in students for course in student['courses']})
            for course_id in course_ids:
                values = [course for student in students for course in student['courses'] if course['id'] == course_id]
                observed = [course for course in values if course['attempts']]
                same_scale = len({row['maximum'] for row in observed}) <= 1
                exact = same_scale and all(row['history_complete'] for row in observed)
                result['courses'].append(dict(id=course_id, name=values[0]['name'], maximum=values[0]['maximum'],
                    students=len(values), observed=len(observed),
                    comparable=same_scale,
                    average=(sum((row['earned'] for row in observed), Decimal(0))/len(observed)).quantize(Decimal('0.01')) if observed and exact else None,
                    debtors=sum(bool(row['debts']) for row in values)))
            if not complete:
                result['warnings'].append('Group roster is incomplete or based on uncertain migrated dates.')
            if not attendance['complete']:
                result['warnings'].append('Attendance denominator is not fully known.')
            return result

    def offering(self, offering_id, as_of=None, start_date=None, end_date=None):
        with self.session.no_autoflush:
            offering = self._get(CourseOffering, offering_id)
            term = self._get(AcademicTerm, offering.term_id)
            day, lower, upper = self._bounds(term.id, as_of, start_date, end_date)
            discipline = self._get(Discipline, offering.discipline_id)
            year = self._get(AcademicYear, term.year_id)
            students = [self.student(key, term.id, day, lower, upper, [offering.id])
                        for key in self._course_ids(offering, lower, upper, day)]
            students.sort(key=lambda row: (row['name'].casefold(), row['id']))
            return dict(id=offering.id, name=discipline.name, offering_name=offering.name,
                        term_id=term.id, term_name=term.name, year_name=year.name,
                        groups=[dict(id=link.group_id, name=self._get(Group, link.group_id).name)
                                for link in self._rows(CourseOfferingGroup, CourseOfferingGroup.offering_id == offering.id)],
                        modules=[dict(id=row.id,name=row.name,position=row.position,start=row.start_date,end=row.end_date)
                                 for row in self._rows(TeachingModule, TeachingModule.offering_id == offering.id)],
                        students=students, distribution=[dict(student_id=row['id'],name=row['name'],
                            earned=row['courses'][0]['earned'], maximum=row['courses'][0]['maximum'])
                            for row in students if row['courses']])
