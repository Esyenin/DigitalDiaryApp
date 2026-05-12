"""
Строгая подготовка XLSX-таблиц к импорту.

Модуль используется для внутренних сущностей приложения, для которых нельзя
допускать угадывание структуры. Таблица может находиться в любом месте листа,
но ее заголовки и смысл колонок должны совпадать со стандартным форматом,
который понимает приложение.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import logging

from pydantic import BaseModel, ValidationError

from app.io_tools.xlsx_config import (
    STRICT_IMPORT_ENTITY_TYPES,
    XLSX_COLUMNS_BY_SHEET,
    is_strict_import_entity_type,
)
from app.io_tools.xlsx_importer.raw_reader import ExtractedTable
from app.schemas import (
    AttendanceCreateSchema,
    CommentCreateSchema,
    LessonCreateSchema,
    MarkCreateSchema,
    ScheduleGroupLinkCreateSchema,
)


logger = logging.getLogger(__name__)


CREATE_SCHEMA_BY_STRICT_ENTITY: dict[str, type[BaseModel]] = {
    "schedule_group_links": ScheduleGroupLinkCreateSchema,
    "lessons": LessonCreateSchema,
    "attendances": AttendanceCreateSchema,
    "marks": MarkCreateSchema,
    "comments": CommentCreateSchema,
}


@dataclass(slots=True)
class StrictImportResult:
    """
    Хранит итог строгой подготовки выбранной таблицы.

    Объект содержит исходные строки диапазона, собранные `create_payloads`,
    предупреждения и ошибки, которые надо показать пользователю перед реальным
    импортом в базу данных.
    """

    entity_type: str
    rows: list[dict[str, object]] = field(default_factory=list)
    create_payloads: list[dict[str, object]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """
        Показывает, прошла ли таблица строгую подготовку без ошибок.

        :return: `True`, если итог не содержит ошибок.
        """
        return not self.errors


class StrictImportProcessor:
    """
    Подготавливает таблицы строгого формата к импорту.

    Процессор применяется для сущностей, которые должны импортироваться только
    в стандартном внутреннем формате. Он не пытается распознавать смысл
    колонок по алиасам и не делает допущений по структуре данных.

    Порядок использования:

    1. Получить `ExtractedTable` через `XlsxRangeReader`.
    2. Передать его в `process_table(...)`.
    3. Использовать `result.create_payloads` как вход для create-схем и
       сервисов приложения.
    """

    def process_table(self, extracted_table: ExtractedTable) -> StrictImportResult:
        """
        Проверяет структуру таблицы и собирает payload-ы строгого импорта.

        Метод последовательно:

        - проверяет, что сущность поддержана в режиме strict import;
        - сверяет фактические заголовки с конфигурацией стандартного формата;
        - валидирует каждую строку через create-схему нужной сущности;
        - собирает payload-словари для следующего слоя импорта.

        :param extracted_table: Таблица, прочитанная из произвольного диапазона
            листа Excel.
        :return: Результат строгой обработки с готовыми payload-ами и
            сообщениями о проблемах.
        :raises ValueError: Если у таблицы не указан `entity_type` или если
            сущность не поддерживается в режиме strict import.
        """
        if extracted_table.entity_type is None:
            raise ValueError("Extracted table must contain entity_type.")

        entity_type = extracted_table.entity_type
        if not is_strict_import_entity_type(entity_type):
            raise ValueError(
                f"Entity type {entity_type!r} is not supported for strict import."
            )

        logger.info(
            "StrictImportProcessor started. entity_type=%s sheet=%s range=%s rows=%s.",
            entity_type,
            extracted_table.sheet,
            extracted_table.range,
            len(extracted_table.rows),
        )

        result = StrictImportResult(entity_type=entity_type, rows=list(extracted_table.rows))
        expected_headers = XLSX_COLUMNS_BY_SHEET[entity_type]
        actual_headers = extracted_table.headers

        missing_headers = tuple(
            header for header in expected_headers if header not in actual_headers
        )
        unknown_headers = tuple(
            header for header in actual_headers if header not in expected_headers
        )

        if missing_headers:
            result.errors.append(
                "Missing strict headers: " + ", ".join(missing_headers) + "."
            )
        if unknown_headers:
            result.errors.append(
                "Unknown strict headers: " + ", ".join(unknown_headers) + "."
            )

        if not result.errors and tuple(actual_headers) != tuple(expected_headers):
            result.warnings.append(
                "Header order differs from the standard XLSX format."
            )

        create_schema = CREATE_SCHEMA_BY_STRICT_ENTITY.get(entity_type)
        if create_schema is None:
            result.errors.append(
                f"No strict create schema is configured for entity type {entity_type!r}."
            )
            return result

        if result.errors:
            logger.warning(
                "StrictImportProcessor header validation failed. entity_type=%s errors=%s.",
                entity_type,
                result.errors,
            )
            return result

        for row_index, row in enumerate(extracted_table.rows, start=1):
            strict_row = {
                header: row.get(header)
                for header in expected_headers
            }

            try:
                validated_schema = create_schema.model_validate(strict_row)
            except ValidationError as exc:
                result.errors.extend(
                    f"row {row_index}: {message}"
                    for message in self._validation_errors_to_messages(exc)
                )
                continue

            result.create_payloads.append(
                validated_schema.model_dump(exclude_unset=True)
            )

        logger.info(
            "StrictImportProcessor finished. entity_type=%s payloads=%s errors=%s.",
            entity_type,
            len(result.create_payloads),
            len(result.errors),
        )
        return result

    @staticmethod
    def _validation_errors_to_messages(exc: ValidationError) -> list[str]:
        """
        Преобразует ошибки Pydantic в компактные текстовые сообщения.

        :param exc: Исключение валидации Pydantic.
        :return: Список сообщений, которые можно показать пользователю или
            записать в лог без дополнительной обработки.
        """
        messages: list[str] = []

        for error in exc.errors():
            location = ".".join(str(part) for part in error["loc"])
            messages.append(f"{location}: {error['msg']}")

        return messages
