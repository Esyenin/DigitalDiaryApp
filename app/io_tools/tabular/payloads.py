"""
Общие типы payload-ов для табличного импорта и экспорта.

Модуль нужен, чтобы верхние слои API и нижние форматные адаптеры опирались на
один и тот же контракт данных, а не импортировали типы друг у друга по
случайному направлению зависимости.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date, datetime, time

from pydantic import BaseModel

from app.models import Base


RowValue = str | int | float | bool | datetime | date | time | None
ExportRow = Mapping[str, object] | BaseModel | Base
ExportPayload = Mapping[str, Iterable[ExportRow]]
