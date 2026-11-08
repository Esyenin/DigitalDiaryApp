"""Transactional academic configuration shared by the repository and Qt views."""

from datetime import timedelta

from sqlalchemy import select

from app.models import (AcademicYear, AcademicTerm, AcademicSelection, Discipline,
                        CourseOffering, CourseOfferingGroup, TeachingModule, Group)
from app.ui.data.calendar import SemesterSettings


class AcademicError(ValueError):
    pass


class AcademicService:
    def __init__(self, session):
        self.session = session

    def _name(self, name):
        name = name.strip()
        if not name or len(name) > 128:
            raise AcademicError("Name must contain 1 to 128 characters.")
        return name

    def _add(self, record):
        self.session.add(record)
        self.session.flush()
        return record

    def create_year(self, name, start_date, end_date):
        if end_date <= start_date:
            raise AcademicError("Year end must be later than its start.")
        return self._add(AcademicYear(name=self._name(name), start_date=start_date, end_date=end_date))

    def create_term(self, year_id, name, start_date, total_weeks, *, origin="recorded"):
        year = self.session.get(AcademicYear, year_id)
        if year is None or not 1 <= total_weeks <= 52 or start_date.weekday() != 0:
            raise AcademicError("Choose a year, a Monday and 1 to 52 weeks.")
        end_date = start_date + timedelta(weeks=total_weeks)
        if not year.start_date <= start_date < end_date <= year.end_date:
            raise AcademicError("Term must fit inside its academic year.")
        return self._add(AcademicTerm(year_id=year_id, name=self._name(name), start_date=start_date,
                                      total_weeks=total_weeks, origin=origin))

    def require_open(self, term_id):
        term = self.session.get(AcademicTerm, term_id)
        if term is None or term.status != "open":
            raise AcademicError("Academic term is missing or closed.")
        return term

    def create_discipline(self, name):
        return self._add(Discipline(name=self._name(name)))

    def create_offering(self, term_id, discipline_id, name, group_ids):
        self.require_open(term_id)
        if self.session.get(Discipline, discipline_id) is None:
            raise AcademicError("Discipline was not found.")
        groups = [self.session.get(Group, key) for key in set(group_ids)]
        if not groups or any(group is None or group.is_archived for group in groups):
            raise AcademicError("Choose at least one active group.")
        offering = self._add(CourseOffering(term_id=term_id, discipline_id=discipline_id, name=self._name(name)))
        for group in groups:
            self._add(CourseOfferingGroup(offering_id=offering.id, group_id=group.id))
        return offering

    def create_module(self, offering_id, name, position, start_date, end_date):
        offering = self.session.get(CourseOffering, offering_id)
        if offering is None:
            raise AcademicError("Course offering was not found.")
        term = self.require_open(offering.term_id)
        if position < 1 or not term.start_date <= start_date < end_date <= term.start_date + timedelta(weeks=term.total_weeks):
            raise AcademicError("Module dates must fit inside the term; position must be positive.")
        if self.session.scalar(select(TeachingModule.id).where(
            TeachingModule.offering_id == offering_id, TeachingModule.start_date < end_date,
            TeachingModule.end_date > start_date,
        ).limit(1)) is not None:
            raise AcademicError("Module periods cannot overlap.")
        return self._add(TeachingModule(offering_id=offering_id, name=self._name(name),
                                        position=position, start_date=start_date, end_date=end_date))

    def select_term(self, term_id):
        if self.session.get(AcademicTerm, term_id) is None:
            raise AcademicError("Term was not found.")
        selection = self.session.get(AcademicSelection, 1)
        if selection is None:
            self._add(AcademicSelection(id=1, term_id=term_id))
        else:
            selection.term_id = term_id
        return self.session.get(AcademicTerm, term_id)

    def calendar_settings(self):
        selection = self.session.get(AcademicSelection, 1)
        if selection is None:
            return None
        term = self.session.get(AcademicTerm, selection.term_id)
        return SemesterSettings(term.start_date, term.total_weeks)

    def close_term(self, term_id):
        term = self.require_open(term_id)
        term.status = "closed"
        return term

    def import_legacy_calendar(self, settings):
        if self.session.get(AcademicSelection, 1) is not None:
            return self.calendar_settings()
        year = self.create_year("Imported calendar", settings.start_date,
                                settings.start_date + timedelta(weeks=settings.total_weeks))
        term = self.create_term(year.id, "Imported semester", settings.start_date,
                                settings.total_weeks, origin="legacy_settings")
        self.select_term(term.id)
        return settings
