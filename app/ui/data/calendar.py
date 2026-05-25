from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta


DEFAULT_SEMESTER_START = date(2026, 2, 2)
DEFAULT_SEMESTER_WEEKS = 17

DAY_NAMES = (
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
)

DAY_INDEX = {name.lower(): index for index, name in enumerate(DAY_NAMES)}


@dataclass(frozen=True)
class SemesterSettings:
    start_date: date = DEFAULT_SEMESTER_START
    total_weeks: int = DEFAULT_SEMESTER_WEEKS

    @property
    def end_date(self) -> date:
        return self.start_date + timedelta(days=self.total_weeks * 7 - 1)

    @property
    def first_week_start(self) -> date:
        return self.start_date

    @property
    def last_week_start(self) -> date:
        return self.start_date + timedelta(weeks=self.total_weeks - 1)


def monday_for(day: date) -> date:
    return day - timedelta(days=day.weekday())


def clamp_week_start(week_start: date, settings: SemesterSettings) -> date:
    if week_start < settings.first_week_start:
        return settings.first_week_start
    if week_start > settings.last_week_start:
        return settings.last_week_start
    return week_start


def week_number_for(week_start: date, settings: SemesterSettings) -> int | None:
    week_start = monday_for(week_start)
    days_delta = (week_start - settings.start_date).days
    if days_delta < 0 or days_delta % 7 != 0:
        return None

    week_number = days_delta // 7 + 1
    if week_number > settings.total_weeks:
        return None

    return week_number


def week_type_for_number(week_number: int | None) -> str | None:
    if week_number is None:
        return None
    return "even" if week_number % 2 == 1 else "odd"


def week_type_label(week_type: str | None) -> str:
    if week_type == "even":
        return "Even Week"
    if week_type == "odd":
        return "Odd Week"
    return "Outside Semester"


def parse_date_input(value: str) -> date:
    cleaned = value.strip()
    for pattern in ("%Y-%m-%d", "%d.%m.%Y", "%m/%d/%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(cleaned, pattern).date()
        except ValueError:
            continue
    raise ValueError("Use YYYY-MM-DD, DD.MM.YYYY, or MM/DD/YYYY.")


def parse_week_count(value: str) -> int:
    weeks = int(value.strip())
    if weeks < 1 or weeks > 52:
        raise ValueError("Weeks count must be between 1 and 52.")
    return weeks


def format_input_date(value: date) -> str:
    return value.strftime("%Y-%m-%d")


def format_short_date(value: date) -> str:
    return value.strftime("%m/%d/%Y")


def format_long_date(value: date) -> str:
    return f"{value.strftime('%A, %B')} {value.day}, {value.year}"


def format_week_range(week_start: date) -> str:
    week_end = week_start + timedelta(days=6)
    return f"{format_short_date(week_start)} - {format_short_date(week_end)}"


def day_index(day_name: str) -> int:
    normalized = day_name.strip().lower()
    if normalized in DAY_INDEX:
        return DAY_INDEX[normalized]
    for name, index in DAY_INDEX.items():
        if normalized.startswith(name[:3]):
            return index
    return 0
