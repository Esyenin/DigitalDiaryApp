"""Activity operations share the caller transaction and never alter academic points."""
from sqlalchemy import select, func, text
from app.models.journal_activity import (Classroom, SeatingLayout, Seat, LessonLayout,
    SeatAssignment, BehaviorCategory, BehaviorEvent, BehaviorCorrection)
from app.models import Lesson, Student
from app.services.academic import AcademicError


class ActivityError(AcademicError):
    pass


TYPICAL_CATEGORIES = (
    ('Demonstration of knowledge', 'positive'), ('Active participation', 'positive'),
    ('Plagiarism', 'negative'), ('Sleeping in class', 'negative'),
    ('Off-task activity', 'negative'), ('Disruptive conversations', 'negative'),
    ('Safety violation', 'negative'), ('Untidy workplace', 'negative'),
)
DEFAULT_CATEGORIES = TYPICAL_CATEGORIES + (('Helping others', 'positive'), ('Good contribution', 'positive'),
                                          ('Disruption', 'negative'), ('Off-task', 'negative'))


class ActivityService:
    def __init__(self, session):
        self.session = session

    def _add(self, item):
        self.session.add(item)
        self.session.flush()
        return item

    def _text(self, value):
        if not isinstance(value, str) or not value.strip():
            raise ActivityError('A nonempty value is required.')
        return value.strip()

    def _lock(self, model, key):
        # Row locks serialize both service and trigger-based writers on PostgreSQL.
        if self.session.bind.dialect.name == 'sqlite':
            self.session.connection().exec_driver_sql('BEGIN IMMEDIATE') if not self.session.connection().connection.driver_connection.in_transaction else None
        item = self.session.scalar(select(model).where(model.id == key).with_for_update())
        if item is None:
            raise ActivityError('Record not found.')
        return item

    def create_room(self, name):
        return self._add(Classroom(name=self._text(name)))

    def create_layout(self, room_id, name, seats):
        self._lock(Classroom, room_id)
        revision = (self.session.scalar(select(func.max(SeatingLayout.revision)).where(SeatingLayout.room_id == room_id)) or 0) + 1
        layout = self._add(SeatingLayout(room_id=room_id, name=self._text(name), revision=revision))
        for seat in seats:
            self._add(Seat(layout_id=layout.id, label=self._text(seat['label']), x=float(seat['x']), y=float(seat['y'])))
        layout.sealed = True
        self.session.flush()
        return layout

    def attach_layout(self, lesson_id, layout_id):
        self._lock(Lesson, lesson_id)
        return self._add(LessonLayout(lesson_id=lesson_id, layout_id=layout_id))

    def _assignment(self, lesson_id, student_id, seat_id, reason, operation_key):
        self._lock(Lesson, lesson_id)
        values = dict(lesson_id=lesson_id, student_id=student_id, seat_id=seat_id, reason=self._text(reason), operation_key=self._text(operation_key))
        existing = self.session.scalar(select(SeatAssignment).where(SeatAssignment.operation_key == operation_key))
        if existing:
            if any(getattr(existing, k) != v for k, v in values.items()):
                raise ActivityError('Operation key reused with different data.')
            return existing
        previous = self.session.scalar(select(SeatAssignment).where(SeatAssignment.lesson_id == lesson_id, SeatAssignment.student_id == student_id).order_by(SeatAssignment.id.desc()).limit(1))
        return self._add(SeatAssignment(**values, previous_id=previous.id if previous else None))

    def assign_seat(self, lesson_id, student_id, seat_id, reason, operation_key):
        return self._assignment(lesson_id, student_id, seat_id, reason, operation_key)

    def unassign_seat(self, lesson_id, student_id, reason, operation_key):
        return self._assignment(lesson_id, student_id, None, reason, operation_key)

    def create_category(self, name, polarity):
        return self._add(BehaviorCategory(name=self._text(name), polarity=polarity))

    def record_behavior(self, student_id, lesson_id, category_id, comment, source, operation_key):
        self._lock(Lesson, lesson_id)
        values = dict(student_id=student_id, lesson_id=lesson_id, category_id=category_id,
                      comment=comment, source=self._text(source), operation_key=self._text(operation_key))
        existing = self.session.scalar(select(BehaviorEvent).where(BehaviorEvent.operation_key == operation_key))
        if existing:
            if any(getattr(existing, k) != v for k, v in values.items()):
                raise ActivityError('Operation key reused with different data.')
            return existing
        return self._add(BehaviorEvent(**values))

    def record_typical_behavior(self, student_id, lesson_id, name, operation_key):
        polarity = dict(DEFAULT_CATEGORIES).get(name)
        if polarity is None:
            raise ActivityError('Unknown typical category.')
        self._lock(Lesson, lesson_id)
        category = self.session.scalar(select(BehaviorCategory).where(BehaviorCategory.name == name))
        if category is None:
            category = self.create_category(name, polarity)
        return self.record_behavior(student_id, lesson_id, category.id, '', 'teacher', operation_key)

    def correct_behavior(self, event_id, student_id, reason, source='teacher'):
        self._lock(BehaviorEvent, event_id)
        return self._add(BehaviorCorrection(event_id=event_id, student_id=student_id,
                         reason=self._text(reason), source=self._text(source)))

    def seating(self, lesson_id):
        link = self.session.scalar(select(LessonLayout).where(LessonLayout.lesson_id == lesson_id))
        seats = list(self.session.scalars(select(Seat).where(Seat.layout_id == link.layout_id).order_by(Seat.id))) if link else []
        history = list(self.session.scalars(select(SeatAssignment).where(SeatAssignment.lesson_id == lesson_id).order_by(SeatAssignment.id)))
        latest = {row.student_id: row for row in history}
        return dict(layout=self.session.get(SeatingLayout, link.layout_id) if link else None,
                    seats=seats, assignments=[row for row in latest.values() if row.seat_id is not None], history=history)

    def behavior_for_student(self, student_id, start_date=None, end_date=None, as_of=None):
        if as_of is not None and as_of.tzinfo is None:
            raise ActivityError('as_of must include a timezone.')
        result = []
        for event in self.session.scalars(select(BehaviorEvent).order_by(BehaviorEvent.id)):
            if as_of and event.occurred_at > as_of:
                continue
            calendar_date = event.occurred_at.astimezone().date()
            if start_date and calendar_date < start_date or end_date and calendar_date >= end_date:
                continue
            query = select(BehaviorCorrection).where(BehaviorCorrection.event_id == event.id)
            if as_of:
                query = query.where(BehaviorCorrection.occurred_at <= as_of)
            corrections = list(self.session.scalars(query.order_by(BehaviorCorrection.id)))
            effective = corrections[-1].student_id if corrections else event.student_id
            if effective == student_id:
                category = self.session.get(BehaviorCategory, event.category_id)
                result.append(dict(id=event.id, student_id=effective, effective_student_id=effective,
                    corrected=bool(corrections), original_student_id=event.student_id,
                    lesson_id=event.lesson_id, category=category.name, category_id=category.id, polarity=category.polarity,
                    comment=event.comment, time=event.occurred_at, occurred_at=event.occurred_at, source=event.source,
                    corrections=[dict(id=c.id, student_id=c.student_id, reason=c.reason, source=c.source, time=c.occurred_at) for c in corrections]))
        return result

    def behavior_history(self, lesson_id=None):
        """Unfiltered original recipients and all corrections for audit screens."""
        query = select(BehaviorEvent).order_by(BehaviorEvent.id)
        if lesson_id is not None:
            query = query.where(BehaviorEvent.lesson_id == lesson_id)
        return [dict(id=e.id, student_id=e.student_id, lesson_id=e.lesson_id,
                     category_id=e.category_id, comment=e.comment, source=e.source,
                     occurred_at=e.occurred_at, operation_key=e.operation_key,
                     corrections=[dict(id=c.id, student_id=c.student_id, reason=c.reason,
                                       source=c.source, occurred_at=c.occurred_at)
                         for c in self.session.scalars(select(BehaviorCorrection).where(
                             BehaviorCorrection.event_id == e.id).order_by(BehaviorCorrection.id))])
                for e in self.session.scalars(query)]
