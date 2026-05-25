"""
Экспорт табличных данных приложения в формат XLSX.

Модуль отвечает только за техническую запись книги Excel из уже подготовленного
payload-а. Он не принимает архитектурных решений о том:

1. Какие сущности нужно выгружать.
2. Откуда брать данные.
3. Куда дальше передавать результат.

Эти вопросы остаются на уровнях application и API. Здесь задача уже уже:
получить табличные строки и корректно сохранить их в XLSX-файл.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date, datetime, time
from decimal import Decimal
import logging
from pathlib import Path
from typing import Any

from openpyxl import Workbook
from pydantic import BaseModel

from app.io_tools.tabular.payloads import ExportPayload, ExportRow, RowValue
from app.io_tools.xlsx_config import XLSX_COLUMNS_BY_SHEET, XLSX_SHEETS_ORDER
from app.models import Base
logger = logging.getLogger(__name__)


class XlsxExporter:
    """
    Экспортирует подготовленные данные приложения в XLSX-файл.

    Экспортер принимает уже структурированные данные в виде словаря
    `имя_листа -> набор_строк`. Благодаря этому один и тот же публичный метод
    подходит как для полного экспорта, так и для частичного: нужно лишь
    передать нужный набор листов и строк.
    """

    def export(
        self,
        payload: ExportPayload,
        file_path: str | Path,
    ) -> Path:
        """
        Создает XLSX-файл из переданного набора листов и строк.

        :param payload: Словарь вида `имя_листа -> строки`. Каждая строка может
            быть словарем, Pydantic-схемой или ORM-объектом.
        :param file_path: Путь, по которому нужно сохранить XLSX-файл.
        :return: Путь к сохраненному файлу.
        :raises ValueError: Если набор листов пустой, имя листа пустое или хотя
            бы одна строка имеет неподдерживаемый тип.
        """
        logger.info(
            "XlsxExporter export started. sheets_count=%s target=%s.",
            len(payload),
            file_path,
        )
        if not payload:
            logger.warning("XlsxExporter export rejected: empty payload.")
            raise ValueError("Для экспорта нужно передать хотя бы один лист.")

        workbook = Workbook()
        first_sheet = True
        ordered_sheet_names = self._resolve_sheet_names(payload)
        logger.debug(
            "XlsxExporter resolved sheet order: %s.",
            ordered_sheet_names,
        )

        for sheet_name in ordered_sheet_names:
            rows = payload[sheet_name]
            validated_name = self._normalize_sheet_name(sheet_name)
            normalized_rows = self._normalize_rows(rows)
            logger.debug(
                "XlsxExporter prepared sheet=%s rows_count=%s.",
                sheet_name,
                len(normalized_rows),
            )

            worksheet = (
                workbook.active
                if first_sheet
                else workbook.create_sheet()
            )
            worksheet.title = validated_name
            self._write_sheet(
                worksheet,
                normalized_rows,
                XLSX_COLUMNS_BY_SHEET.get(sheet_name),
            )
            first_sheet = False

        target_path = Path(file_path)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        workbook.save(target_path)
        logger.info("XlsxExporter export finished. target=%s.", target_path)
        return target_path

    @staticmethod
    def _resolve_sheet_names(payload: ExportPayload) -> list[str]:
        """
        Определяет итоговый порядок листов для экспорта.

        Известные листы идут в порядке из общей XLSX-конфигурации. Любые
        дополнительные листы, которых нет в конфигурации, записываются после
        них в порядке появления во входном словаре.

        :param payload: Набор листов для экспорта.
        :return: Упорядоченный список имен листов.
        """
        payload_names = list(payload.keys())
        ordered_names = [
            sheet_name
            for sheet_name in XLSX_SHEETS_ORDER
            if sheet_name in payload
        ]
        ordered_names.extend(
            sheet_name
            for sheet_name in payload_names
            if sheet_name not in ordered_names
        )
        return ordered_names

    @staticmethod
    def _normalize_sheet_name(sheet_name: str) -> str:
        """
        Приводит имя листа Excel к допустимому виду.

        :param sheet_name: Исходное имя листа.
        :return: Очищенное и укороченное имя листа.
        :raises ValueError: Если имя листа пустое после очистки.
        """
        normalized = sheet_name.strip()
        if not normalized:
            raise ValueError("Имя листа Excel не должно быть пустым.")

        invalid_chars = set(r'[]:*?/\\')
        cleaned = "".join(
            character
            for character in normalized
            if character not in invalid_chars
        ).strip()
        if not cleaned:
            raise ValueError("Имя листа Excel не должно быть пустым.")

        return cleaned[:31]

    def _normalize_rows(
        self,
        rows: Iterable[ExportRow],
    ) -> list[dict[str, RowValue]]:
        """
        Преобразует строки экспорта к единому словарному виду.

        :param rows: Набор строк в произвольном допустимом формате.
        :return: Список словарей с простыми значениями, готовыми к записи
            в Excel.
        :raises ValueError: Если встречен неподдерживаемый тип строки.
        """
        normalized_rows: list[dict[str, RowValue]] = []

        for row in rows:
            normalized_rows.append(self._normalize_row(row))

        return normalized_rows

    def _normalize_row(
        self,
        row: ExportRow
    ) -> dict[str, RowValue]:
        """
        Преобразует одну строку экспорта к словарю простых значений.

        :param row: Строка экспорта в виде словаря, схемы или ORM-объекта.
        :return: Словарь значений, пригодных для записи в Excel.
        :raises ValueError: Если тип строки не поддерживается.
        """
        raw_row: dict[str, object]

        if isinstance(row, BaseModel):
            raw_row = row.model_dump(exclude_unset=False)
        elif isinstance(row, Mapping):
            raw_row = dict(row)
        elif isinstance(row, Base):
            raw_row = {
                key: value
                for key, value in row.__dict__.items()
                if not key.startswith("_")
            }
        else:
            raise ValueError(
                "Строка экспорта должна быть словарем, схемой или ORM-объектом."
            )

        return {
            key: self._normalize_value(value)
            for key, value in raw_row.items()
        }

    @staticmethod
    def _normalize_value(value: object) -> RowValue:
        """
        Приводит значение поля к типу, который можно безопасно записать в Excel.

        :param value: Исходное значение поля.
        :return: Нормализованное значение.
        """
        if value is None:
            return None

        if isinstance(value, Decimal):
            return float(value)

        if isinstance(value, (str, int, float, bool, datetime, date, time)):
            return value

        return str(value)

    def _write_sheet(
        self,
        worksheet: Any,
        rows: list[dict[str, RowValue]],
        configured_headers: tuple[str, ...] | None,
    ) -> None:
        """
        Записывает набор строк на один лист Excel.

        :param worksheet: Лист книги openpyxl.
        :param rows: Нормализованные строки для записи.
        :param configured_headers: Заранее заданный порядок колонок для листа.
        :return: `None`.
        """
        headers = self._collect_headers(rows, configured_headers)
        if not headers:
            logger.debug(
                "XlsxExporter skipped empty sheet write. title=%s.",
                worksheet.title,
            )
            return

        worksheet.append(headers)

        for row in rows:
            worksheet.append([row.get(header) for header in headers])

        logger.debug(
            "XlsxExporter wrote sheet=%s headers=%s rows_count=%s.",
            worksheet.title,
            headers,
            len(rows),
        )

    @staticmethod
    def _collect_headers(
        rows: list[dict[str, RowValue]],
        configured_headers: tuple[str, ...] | None,
    ) -> list[str]:
        """
        Собирает итоговый порядок колонок для листа.

        Порядок берется из XLSX-конфигурации, если он задан. Поля, которых нет
        в конфигурации, но которые встретились в данных, дописываются в конец
        по первому появлению.

        :param rows: Нормализованные строки одного листа.
        :param configured_headers: Заранее заданный порядок колонок.
        :return: Список имен колонок.
        """
        headers = list(configured_headers or ())

        for row in rows:
            for key in row:
                if key not in headers:
                    headers.append(key)

        return headers
