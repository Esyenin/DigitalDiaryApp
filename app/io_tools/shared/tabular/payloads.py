"""
Общие типы payload-ов для табличного импорта и экспорта.

Эти типы нужны сразу нескольким слоям: API-запросам, XLSX-writer'ам,
flow-сценариям и внешнему коду. Выделение их в `shared` позволяет не
тянуть зависимости через конкретный exporter или legacy-модуль.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date, datetime, time

from pydantic import BaseModel

from app.models import Base


RowValue = str | int | float | bool | datetime | date | time | None
ExportRow = Mapping[str, object] | BaseModel | Base
ExportPayload = Mapping[str, Iterable[ExportRow]]
