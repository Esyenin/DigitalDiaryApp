"""Teaching operations within the caller's transaction; no nested commits."""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation

from sqlalchemy import func, or_, select, text

from app.models import (
    AcademicTerm, AssessmentAttempt, AssessmentEvent, Attendance, AttendanceRevision,
    ChecklistCriterion, ChecklistVersion, Consultation, ConsultationVisit, CourseOffering,
    CourseOfferingGroup, CriterionAnswer, EventCancellation, GroupMembership, IndividualPlan,
    LabWork, Lesson, LessonDisposition, LessonParticipant, NonTeachingDay, PlanEntry,
    PlanStage, ResultCorrection, Schedule, Student, TeachingAudit, TeachingModule,
)
from app.models.education import utc_now
from app.services.academic import AcademicError, AcademicService


class TeachingError(AcademicError):
    pass


def points_value(value):
    try:
        result = Decimal(str(value))
        if not result.is_finite() or result < 0 or result > Decimal("9999999999.99"):
            raise ValueError
        if result != result.quantize(Decimal("0.01")):
            raise ValueError
        return result.quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError, ValueError):
        raise TeachingError("Points must be nonnegative with at most two decimal places.") from None


def aware_utc(value):
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise TeachingError("Date and time must include a timezone.")
    return value.astimezone(timezone.utc)


class TeachingService:
    def __init__(self, session):
        self.session = session
        self.academic = AcademicService(session)

    def _get(self, model, key):
        item = self.session.get(model, key)
        if item is None:
            raise TeachingError(f"{model.__name__} was not found.")
        return item

    def _lock(self, model, key):
        if self.session.bind.dialect.name == "sqlite":
            self.session.execute(text(f"UPDATE {model.__tablename__} SET id = id WHERE id = :id"), {"id": key})
        else:
            self.session.execute(select(model.id).where(model.id == key).with_for_update()).first()
        return self._get(model, key)

    def _add(self, item):
        self.session.add(item)
        self.session.flush()
        return item

    def _text(self, value, label="Text", maximum=None):
        cleaned = str(value).strip()
        if not cleaned or (maximum and len(cleaned) > maximum):
            raise TeachingError(f"{label} is required" + (f" (up to {maximum} characters)." if maximum else "."))
        return cleaned

    def _audit(self, action, item, reason="", source="teacher"):
        self._add(TeachingAudit(action=action, entity_type=item.__tablename__, entity_id=item.id,
                                reason=reason, source=self._text(source, "Source", 128)))

    def _offering(self, module_id):
        module = self._get(TeachingModule, module_id)
        offering = self._get(CourseOffering, module.offering_id)
        self.academic.require_open(offering.term_id)
        return module, offering

    def _eligible(self, offering, student_id):
        student = self._get(Student, student_id)
        term = self._get(AcademicTerm, offering.term_id)
        groups = select(CourseOfferingGroup.group_id).where(CourseOfferingGroup.offering_id == offering.id)
        found = self.session.scalar(select(GroupMembership.id).where(
            GroupMembership.student_id == student_id, GroupMembership.group_id.in_(groups),
            GroupMembership.start_date < term.start_date + timedelta(weeks=term.total_weeks),
            or_(GroupMembership.end_date.is_(None), GroupMembership.end_date > term.start_date),
            or_(GroupMembership.origin != "migrated_unknown",
                GroupMembership.known_from < term.start_date + timedelta(weeks=term.total_weeks)),
        ).limit(1))
        evidence = self.session.scalar(select(LessonParticipant.id).join(
            Lesson, Lesson.id == LessonParticipant.lesson_id).join(Schedule, Schedule.id == Lesson.schedule_id).where(
                LessonParticipant.student_id == student_id, Schedule.offering_id == offering.id).limit(1))
        results = self.session.scalar(select(AssessmentAttempt.id).join(
            AssessmentEvent, AssessmentEvent.id == AssessmentAttempt.event_id).join(
            TeachingModule, TeachingModule.id == AssessmentEvent.module_id).where(
                AssessmentAttempt.student_id == student_id, AssessmentAttempt.finalized.is_(True),
                TeachingModule.offering_id == offering.id).limit(1))
        if found is None and evidence is None and results is None:
            raise TeachingError("Student has no membership or lesson participation in this course.")
        return student

    def _retry(self, model, operation_key, values):
        key = self._text(operation_key, "Operation key", 64)
        existing = self.session.scalar(select(model).where(model.operation_key == key))
        if existing is not None:
            if any(getattr(existing, field) != value for field, value in values.items()):
                raise TeachingError("Operation key was reused with different data.")
        return existing

    def create_event(self, module_id, title, category, max_points, required, attempt_policy,
                     max_attempts=None, conditions="", due_at=None, lesson_id=None, custom_type=None):
        module, offering = self._offering(module_id)
        if category not in {"seminar_start", "seminar_end", "lab", "checkpoint", "additional"}:
            raise TeachingError("Unknown assessment category.")
        if category in {"seminar_start", "seminar_end"} and lesson_id is None:
            raise TeachingError("A seminar test requires a concrete lesson in its course and module.")
        if attempt_policy not in {"best", "latest"} or (max_attempts is not None and max_attempts < 1):
            raise TeachingError("Choose best/latest policy and a positive attempt limit, or no limit.")
        if lesson_id is not None:
            lesson = self._get(Lesson, lesson_id)
            if lesson.schedule.offering_id != offering.id or not module.start_date <= lesson.date < module.end_date:
                raise TeachingError("Lesson must belong to this course and module period.")
            if category in {"seminar_start", "seminar_end"} and self.session.scalar(select(AssessmentEvent.id).where(
                AssessmentEvent.lesson_id == lesson_id, AssessmentEvent.category == category,
                ~select(EventCancellation.id).where(EventCancellation.event_id == AssessmentEvent.id).exists()).limit(1)):
                raise TeachingError("This seminar test slot is already configured.")
        event = self._add(AssessmentEvent(module_id=module_id, title=self._text(title, "Title", 256),
            custom_type=self._text(custom_type, "Custom type", 128) if custom_type and category == "additional" else None,
            category=category, max_points=points_value(max_points), required=bool(required),
            conditions=conditions.strip(), due_at=aware_utc(due_at) if due_at else None,
            attempt_policy=attempt_policy, max_attempts=max_attempts, lesson_id=lesson_id))
        self._audit("create_event", event)
        return event

    def create_lab(self, event_id, title):
        event = self._get(AssessmentEvent, event_id)
        self._offering(event.module_id)
        if event.category != "lab":
            raise TeachingError("A lab must use an event in the lab category.")
        return self._add(LabWork(event_id=event_id, title=self._text(title, "Lab title", 256)))

    def create_checklist(self, lab_id, criteria):
        lab = self._lock(LabWork, lab_id)
        event = self._get(AssessmentEvent, lab.event_id)
        self._offering(event.module_id)
        labels = [self._text(label, "Criterion", 512) for label in criteria]
        if not labels or len(set(labels)) != len(labels):
            raise TeachingError("Provide at least one distinct binary criterion.")
        revision = (self.session.scalar(select(func.max(ChecklistVersion.revision)).where(
            ChecklistVersion.lab_id == lab_id)) or 0) + 1
        version = self._add(ChecklistVersion(lab_id=lab_id, revision=revision))
        for position, label in enumerate(labels, 1):
            self._add(ChecklistCriterion(version_id=version.id, position=position, label=label))
        self._audit("create_checklist", version)
        return version

    def record_attempt(self, event_id, student_id, points, work_completed, defended, passed, operation_key,
                       occurred_at=None, checklist_version_id=None, answers=None, additional_answer="",
                       question_passed=None, comment="", consultation_visit_id=None):
        event = self._get(AssessmentEvent, event_id)
        values = dict(event_id=event_id, student_id=student_id, points=points_value(points),
            work_completed=bool(work_completed), defended=bool(defended), passed=bool(passed),
            checklist_version_id=checklist_version_id, additional_answer=additional_answer.strip(),
            question_passed=question_passed, comment=comment.strip(), consultation_visit_id=consultation_visit_id)
        if occurred_at is not None:
            values["occurred_at"] = aware_utc(occurred_at)
        existing = self._retry(AssessmentAttempt, operation_key, values)
        if existing is not None:
            if not existing.finalized:
                raise TeachingError("The previous attempt is not finalized.")
            stored_answers = dict(self.session.execute(select(CriterionAnswer.criterion_id, CriterionAnswer.satisfied)
                                                       .where(CriterionAnswer.attempt_id == existing.id)).all())
            if stored_answers != (answers or {}):
                raise TeachingError("Operation key was reused with different checklist answers.")
            return existing
        event = self._lock(AssessmentEvent, event_id)
        raced = self._retry(AssessmentAttempt, operation_key, values)
        if raced is not None:
            if not raced.finalized:
                raise TeachingError("The previous attempt is not finalized.")
            stored = dict(self.session.execute(select(CriterionAnswer.criterion_id, CriterionAnswer.satisfied)
                                               .where(CriterionAnswer.attempt_id == raced.id)).all())
            if stored != (answers or {}):
                raise TeachingError("Operation key was reused with different checklist answers.")
            return raced
        module, offering = self._offering(event.module_id)
        self._eligible(offering, student_id)
        if self.session.scalar(select(EventCancellation.id).where(EventCancellation.event_id == event_id)):
            raise TeachingError("This event was cancelled.")
        if values["points"] > event.max_points or (not passed and values["points"] != 0):
            raise TeachingError("Points exceed the event maximum or a failed attempt has nonzero points.")
        if passed and not work_completed:
            raise TeachingError("A passed assessment must have completed work.")
        number = (self.session.scalar(select(func.max(AssessmentAttempt.attempt_number)).where(
            AssessmentAttempt.event_id == event_id, AssessmentAttempt.student_id == student_id)) or 0) + 1
        if event.max_attempts is not None and number > event.max_attempts:
            raise TeachingError("The configured attempt limit was reached.")
        if consultation_visit_id is not None:
            visit = self._get(ConsultationVisit, consultation_visit_id)
            if visit.student_id != student_id:
                raise TeachingError("Consultation visit belongs to a different student.")
        answer_values = answers or {}
        if event.category == "lab":
            if checklist_version_id is None:
                raise TeachingError("A lab defense requires a checklist version.")
            version = self._get(ChecklistVersion, checklist_version_id)
            if self._get(LabWork, version.lab_id).event_id != event_id:
                raise TeachingError("Checklist belongs to a different laboratory work.")
            criteria = set(self.session.scalars(select(ChecklistCriterion.id).where(ChecklistCriterion.version_id == version.id)))
            if not criteria or set(answer_values) != criteria or any(type(value) is not bool for value in answer_values.values()):
                raise TeachingError("Answer every criterion of the selected checklist with yes/no.")
            if passed and not (work_completed and defended and all(answer_values.values()) and question_passed is True):
                raise TeachingError("Successful defense requires completed work, all criteria and an answered question.")
        elif checklist_version_id is not None or answer_values:
            raise TeachingError("Only a laboratory defense can contain checklist answers.")
        attempt = self._add(AssessmentAttempt(**values, attempt_number=number, operation_key=operation_key,
            **({"occurred_at": utc_now()} if occurred_at is None else {})))
        for criterion_id, satisfied in answer_values.items():
            self._add(CriterionAnswer(attempt_id=attempt.id, criterion_id=criterion_id, satisfied=satisfied))
        attempt.finalized = True
        self.session.flush()
        self._audit("record_attempt", attempt, comment)
        return attempt

    def correct_result(self, attempt_id, points, passed, reason, operation_key, source="teacher"):
        values = dict(attempt_id=attempt_id, points=points_value(points), passed=bool(passed),
                      reason=self._text(reason, "Correction reason"), source=self._text(source, "Source", 128))
        existing = self._retry(ResultCorrection, operation_key, values)
        if existing is not None:
            return existing
        attempt = self._get(AssessmentAttempt, attempt_id)
        if not attempt.finalized:
            raise TeachingError("An unfinished attempt cannot be corrected.")
        event = self._lock(AssessmentEvent, attempt.event_id)
        self._offering(event.module_id)
        if values["points"] > event.max_points or (not passed and values["points"] != 0):
            raise TeachingError("Corrected points must fit the event maximum; failed result must be zero.")
        if event.category == "lab" and passed and not attempt.passed:
            raise TeachingError("A failed defense needs a new attempt with its checklist, not a passed-score override.")
        correction = self._add(ResultCorrection(**values, operation_key=operation_key))
        self._audit("correct_result", correction, values["reason"], source)
        return correction

    def cancel_event(self, event_id, reason):
        event = self._lock(AssessmentEvent, event_id)
        self._offering(event.module_id)
        existing = self.session.scalar(select(EventCancellation).where(EventCancellation.event_id == event_id))
        if existing is not None:
            if existing.reason != reason.strip():
                raise TeachingError("The event is already cancelled with a different reason.")
            return existing
        if self.session.scalar(select(AssessmentAttempt.id).where(AssessmentAttempt.event_id == event_id).limit(1)):
            raise TeachingError("An event with results cannot be cancelled; retain its history.")
        item = self._add(EventCancellation(event_id=event_id, reason=self._text(reason, "Cancellation reason")))
        self._audit("cancel_event", item, reason)
        return item

    def summary(self, offering_id, student_id, module_id=None, *, as_of=None, start_date=None, end_date=None):
        offering = self._get(CourseOffering, offering_id)
        self._eligible(offering, student_id)
        modules = list(self.session.scalars(select(TeachingModule).where(TeachingModule.offering_id == offering_id)
                                           .order_by(TeachingModule.position)))
        if module_id is not None:
            modules = [module for module in modules if module.id == module_id]
            if not modules:
                raise TeachingError("Module does not belong to the course.")
        cutoff = datetime.combine(as_of, datetime.max.time()).astimezone(timezone.utc) if as_of else None
        def known_at(value):
            if cutoff is None or value is None:
                return True
            value = value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
            return value <= cutoff
        result = dict(earned=Decimal(0), maximum=Decimal(0), remaining=Decimal(0), debts=[], pending=[], modules=[], events=[])
        for module in modules:
            if start_date and module.end_date <= start_date or end_date and module.start_date > end_date:
                continue
            total = dict(id=module.id, name=module.name, earned=Decimal(0), maximum=Decimal(0), remaining=Decimal(0))
            for event in self.session.scalars(select(AssessmentEvent).where(AssessmentEvent.module_id == module.id).order_by(AssessmentEvent.id)):
                if not known_at(event.configured_at):
                    continue
                if event.lesson_id is not None:
                    event_day = self._get(Lesson, event.lesson_id).date
                    if start_date and event_day < start_date or end_date and event_day > end_date:
                        continue
                cancellation = self.session.scalar(select(EventCancellation).where(EventCancellation.event_id == event.id))
                if cancellation is not None and known_at(cancellation.occurred_at):
                    continue
                attempts = list(self.session.scalars(select(AssessmentAttempt).where(
                    AssessmentAttempt.event_id == event.id, AssessmentAttempt.student_id == student_id)
                    .where(AssessmentAttempt.finalized.is_(True))
                    .order_by(AssessmentAttempt.attempt_number)))
                attempts = [attempt for attempt in attempts if known_at(attempt.occurred_at)]
                effective = []
                for attempt in attempts:
                    corrections = list(self.session.scalars(select(ResultCorrection).where(ResultCorrection.attempt_id == attempt.id)
                                                           .order_by(ResultCorrection.id.desc())))
                    correction = next((item for item in corrections if known_at(item.occurred_at)), None)
                    effective.append((correction.points, correction.passed) if correction else (attempt.points, attempt.passed))
                chosen = (max(effective, key=lambda value: (value[0], value[1])) if event.attempt_policy == "best"
                          else effective[-1]) if effective else (Decimal(0), False)
                earned, passed = chosen
                remaining = event.max_points - earned if event.max_attempts is None or len(attempts) < event.max_attempts else Decimal(0)
                row = dict(id=event.id, title=event.title, earned=earned, maximum=event.max_points,
                           category=event.category, custom_type=event.custom_type, required=event.required,
                           passed=passed, debt=event.required and not passed and (cutoff is None or event.due_at is None or known_at(event.due_at)),
                           pending=event.required and not passed and cutoff is not None and event.due_at is not None and not known_at(event.due_at),
                           attempts=len(attempts))
                result["events"].append(row)
                if row["debt"]:
                    result["debts"].append(dict(id=event.id, title=event.title))
                if row["pending"]:
                    result["pending"].append(dict(id=event.id, title=event.title))
                for key, value in (("earned", earned), ("maximum", event.max_points), ("remaining", remaining)):
                    total[key] += value
                    result[key] += value
            result["modules"].append(total)
        return result

    def create_consultation(self, starts_at, title="Consultation"):
        return self._add(Consultation(starts_at=aware_utc(starts_at), title=self._text(title, "Title", 256)))

    def register_visit(self, consultation_id, student_id, purpose, question="", comment=""):
        self._get(Consultation, consultation_id)
        self._get(Student, student_id)
        visit = self._add(ConsultationVisit(consultation_id=consultation_id, student_id=student_id,
            purpose=self._text(purpose, "Purpose", 128), question=question.strip(), comment=comment.strip()))
        self._audit("consultation_visit", visit, comment)
        return visit

    def create_plan(self, student_id, title, kind, offering_id=None):
        self._get(Student, student_id)
        if kind not in {"coursework", "diploma", "project"}:
            raise TeachingError("Unknown individual plan kind.")
        if offering_id is not None:
            offering = self._get(CourseOffering, offering_id)
            self.academic.require_open(offering.term_id)
            self._eligible(offering, student_id)
        return self._add(IndividualPlan(student_id=student_id, title=self._text(title, "Title", 256),
                                        kind=kind, offering_id=offering_id))

    def add_plan_stage(self, plan_id, title, position):
        self._get(IndividualPlan, plan_id)
        if position < 1:
            raise TeachingError("Stage position must be positive.")
        return self._add(PlanStage(plan_id=plan_id, title=self._text(title, "Stage", 512), position=position))

    def record_plan_entry(self, stage_id, completed, comment, consultation_visit_id=None):
        stage = self._get(PlanStage, stage_id)
        plan = self._get(IndividualPlan, stage.plan_id)
        if consultation_visit_id is not None and self._get(ConsultationVisit, consultation_visit_id).student_id != plan.student_id:
            raise TeachingError("Consultation visit belongs to a different student.")
        entry = self._add(PlanEntry(stage_id=stage_id, completed=bool(completed),
            comment=self._text(comment, "Progress comment"), consultation_visit_id=consultation_visit_id))
        self._audit("plan_progress", entry, comment)
        return entry

    def record_attendance(self, lesson_id, student_id, status, reason, operation_key, source="teacher", arrived_at=None,
                          mode="arrival"):
        reason = self._text(reason, "Attendance reason")
        if mode not in {"arrival", "correction"}:
            raise TeachingError("Choose arrival registration or attendance correction.")
        lesson = self._lock(Lesson, lesson_id)
        if lesson.date > date.today():
            raise TeachingError("Attendance cannot be recorded for a future lesson.")
        disposition = self.session.scalar(select(LessonDisposition).where(LessonDisposition.lesson_id == lesson_id)
                                          .order_by(LessonDisposition.id.desc()).limit(1))
        if disposition and disposition.status in {"cancelled", "holiday", "moved"}:
            raise TeachingError("Attendance cannot be recorded for a cancelled or replaced lesson.")
        student = self._get(Student, student_id)
        if status not in {"absent", "present", "late", "excused"}:
            raise TeachingError("Unknown attendance status.")
        participant = self.session.scalar(select(LessonParticipant).where(
            LessonParticipant.lesson_id == lesson_id, LessonParticipant.student_id == student_id))
        if lesson.participants_complete and participant is None:
            raise TeachingError("Student is not in the fixed lesson roster.")
        if participant is None:
            group_ids = {link.group_id for link in lesson.schedule.group_links}
            memberships = list(self.session.scalars(select(GroupMembership).where(
                GroupMembership.student_id == student_id, GroupMembership.group_id.in_(group_ids),
                GroupMembership.start_date <= lesson.date, GroupMembership.known_from <= lesson.date,
                or_(GroupMembership.end_date.is_(None), GroupMembership.end_date > lesson.date))))
            if not memberships:
                raise TeachingError("Student has no known membership for this lesson.")
            participant = self._add(LessonParticipant(lesson_id=lesson_id, student_id=student_id,
                group_id=memberships[0].group_id, source="evidence"))
        attendance = self.session.scalar(select(Attendance).where(Attendance.lesson_id == lesson_id,
                                                                 Attendance.student_id == student_id))
        if attendance is None:
            attendance = self._add(Attendance(lesson_id=lesson_id, student_id=student_id, is_visited=False))
        previous_revision = self.session.scalar(select(AttendanceRevision).where(
            AttendanceRevision.attendance_id == attendance.id).order_by(AttendanceRevision.id.desc()).limit(1))
        previous_status = previous_revision.status if previous_revision else ('present' if attendance.is_visited else 'absent')
        arrival = aware_utc(arrived_at) if arrived_at is not None else None
        late_seconds = None
        if status in {"present", "late"}:
            if mode == "correction" and status == "late" and arrival is None:
                raise TeachingError("A lateness correction requires an explicit arrival time.")
            if mode == "arrival":
                arrival = arrival or utc_now()
            if lesson.participants_complete and arrival is not None:
                if lesson.roster_completed_at is None or lesson.roster_time_basis != "utc":
                    raise TeachingError("Legacy roll-call time has no reliable timezone; exact lateness cannot be calculated.")
                completed = lesson.roster_completed_at
                completed = completed.replace(tzinfo=timezone.utc) if completed.tzinfo is None else completed.astimezone(timezone.utc)
                late_seconds = max(0, int((arrival - completed).total_seconds()))
                status = "late" if late_seconds > 0 else "present"
            elif status == "late":
                raise TeachingError("Complete roll call before calculating lateness.")
        elif arrival is not None:
            raise TeachingError("Absent/excused attendance cannot have an arrival time.")
        values = dict(attendance_id=attendance.id, status=status, reason=reason, source=self._text(source, "Source", 128))
        if arrived_at is not None:
            values["arrived_at"] = arrival
        retry = self._retry(AttendanceRevision, operation_key, values)
        if retry is not None:
            return retry
        revision = self._add(AttendanceRevision(**values, operation_key=operation_key, late_seconds=late_seconds,
            previous_status=previous_status,
            previous_arrived_at=previous_revision.arrived_at if previous_revision else None,
            previous_late_seconds=previous_revision.late_seconds if previous_revision else None,
            **({"arrived_at": arrival} if arrived_at is None else {})))
        attendance.is_visited = status in {"present", "late"}
        self.session.flush()
        self._audit("attendance_" + mode, revision, reason, source)
        return revision

    def set_lesson_disposition(self, lesson_id, status, reason, new_date=None):
        lesson = self._lock(Lesson, lesson_id)
        reason = self._text(reason, "Calendar change reason")
        if status not in {"cancelled", "holiday", "moved", "held"}:
            raise TeachingError("Unknown lesson state.")
        previous = self.session.scalar(select(LessonDisposition).where(LessonDisposition.lesson_id == lesson_id)
                                       .order_by(LessonDisposition.id.desc()).limit(1))
        if previous and previous.status == status and previous.reason == reason:
            replacement_date = (self._get(Lesson, previous.replacement_lesson_id).date
                                if previous.replacement_lesson_id else None)
            if replacement_date == new_date:
                return previous
        if previous and previous.status == "moved":
            raise TeachingError("The original lesson was already moved; change its replacement instead.")
        if lesson.schedule.offering_id is not None:
            offering = self._get(CourseOffering, lesson.schedule.offering_id)
            self.academic.require_open(offering.term_id)
        protected = (lesson.participants_complete or lesson.attendances or lesson.marks or lesson.comments
                     or lesson.participants or lesson.date < date.today()
                     or (previous is not None and previous.status == "held")
                     or self.session.scalar(select(AssessmentAttempt.id).join(AssessmentEvent).where(
                         AssessmentEvent.lesson_id == lesson.id, AssessmentAttempt.finalized.is_(True)).limit(1)) is not None)
        if status != "held" and protected:
            raise TeachingError("A conducted or filled lesson cannot be cancelled or moved automatically.")
        if status == "held" and lesson.date > date.today():
            raise TeachingError("A future lesson cannot be marked as held.")
        replacement = None
        if status == "moved":
            if new_date is None or new_date <= date.today() or new_date == lesson.date:
                raise TeachingError("Choose a different future date for the replacement lesson.")
            schedule = lesson.schedule
            if new_date < schedule.effective_from or (schedule.effective_until and new_date >= schedule.effective_until):
                raise TeachingError("Replacement date is outside this schedule version.")
            if schedule.offering_id is not None:
                term = self._get(AcademicTerm, self._get(CourseOffering, schedule.offering_id).term_id)
                if not term.start_date <= new_date < term.start_date + timedelta(weeks=term.total_weeks):
                    raise TeachingError("Replacement date is outside the academic term.")
            replacement = self._add(Lesson(schedule_id=schedule.id, date=new_date, topic=lesson.topic))
        item = self._add(LessonDisposition(lesson_id=lesson_id, status=status, reason=reason,
            replacement_lesson_id=replacement.id if replacement else None))
        self._audit("lesson_" + status, item, reason)
        return item

    def add_non_teaching_day(self, term_id, day, reason):
        term = self.academic.require_open(term_id)
        if not term.start_date <= day < term.start_date + timedelta(weeks=term.total_weeks):
            raise TeachingError("Non-teaching day is outside the academic term.")
        if day <= date.today():
            raise TeachingError("Only a future non-teaching day can change the generated calendar.")
        existing = self.session.scalar(select(NonTeachingDay).where(NonTeachingDay.term_id == term_id,
                                                                  NonTeachingDay.date == day))
        if existing is not None:
            if existing.reason != reason.strip():
                raise TeachingError("This non-teaching day already has a different reason.")
            return existing
        item = self._add(NonTeachingDay(term_id=term_id, date=day, reason=self._text(reason, "Holiday reason")))
        lessons = list(self.session.scalars(select(Lesson).join(Schedule).join(
            CourseOffering, Schedule.offering_id == CourseOffering.id).where(
                CourseOffering.term_id == term_id, Lesson.date == day)))
        for lesson in lessons:
            self.set_lesson_disposition(lesson.id, "holiday", reason)
        self._audit("non_teaching_day", item, reason)
        return item
