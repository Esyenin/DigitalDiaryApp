"""
Нормализация и подготовка нестандартных XLSX-данных к импорту.

Модуль объединяет три последовательных слоя обработки:

1. `DataNormalizer`
   Преобразует прочитанную таблицу в понятный для приложения вид. На этом
   этапе заголовки сопоставляются с внутренними полями, полезные значения
   отделяются от лишних колонок, а ссылочные данные сохраняются отдельно.
2. `DataResolver`
   Пытается разрешить ссылочные данные в реальные поля импорта. Например,
   если у студента нет `group_id`, но есть имя группы, резолвер может через
   переданный callback вернуть уже готовый `group_id`.
3. `ImportProcessor`
   Объединяет оба шага и подготавливает итоговые `create_payloads`, которые
   уже можно передавать в create-схемы и сервисы приложения.

Модуль не работает с SQLAlchemy-сессией напрямую. Все обращения к базе должны
происходить снаружи, через callbacks или следующий слой импорта.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
import logging
import re
from typing import Any

from pydantic import BaseModel, ValidationError

from app.io_tools.xlsx_importer.raw_reader import ExtractedTable
from app.io_tools.xlsx_config import is_smart_import_entity_type
from app.schemas import (
    GroupCreateSchema,
    GroupFilterSchema,
    StudentCreateSchema,
    StudentFilterSchema,
)


logger = logging.getLogger(__name__)


CanonicalEntityType = str
ReferenceKey = str
ResolverCallback = Callable[[dict[str, object]], dict[str, object] | None]


DIRECT_FIELD_ALIASES: dict[CanonicalEntityType, dict[str, set[str]]] = {
    "groups": {
        "name": {"name", "group", "groups", "группа", "группы"},
        "speciality": {"speciality", "specialities", "специальность", "специальности"},
    },
    "students": {
        "surname": {
            "surname",
            "last name",
            "lastname",
            "фамилия",
            "фамилии",
            "фамилии",
        },
        "first_name": {"first name", "firstname", "first_name", "имя", "name", "имена"},
        "patronymic": {"patronymic", "middle name", "middlename", "отчество", "отчества"},
        "group_id": {"group id", "group_id"},
        "personal_data": {
            "personal data",
            "personal_data",
            "личное дело",
            "личное_дело",
        },
        "bmstu_email": {
            "bmstu email",
            "bmstu_email",
            "email",
            "e mail",
            "почта",
            "корпоративная_почта",
        },
    },
}


REFERENCE_FIELD_ALIASES: dict[CanonicalEntityType, dict[ReferenceKey, dict[str, set[str]]]] = {
    "students": {
        "group": {
            "name": {"group", "group name", "группа", "название группы"},
        }
    }
}


FILTER_SCHEMA_BY_ENTITY: dict[CanonicalEntityType, type[BaseModel]] = {
    "groups": GroupFilterSchema,
    "students": StudentFilterSchema,
}


CREATE_SCHEMA_BY_ENTITY: dict[CanonicalEntityType, type[BaseModel]] = {
    "groups": GroupCreateSchema,
    "students": StudentCreateSchema,
}


@dataclass(slots=True)
class NormalizedRow:
    """
    Хранит результат нормализации одной строки нестандартной таблицы.

    Экземпляр показывает, какие данные удалось распознать как прямые поля
    сущности, какие значения были отнесены к ссылкам, а какие колонки пока
    не удалось сопоставить ни с одной известной частью модели.
    """

    source_sheet: str
    source_range: str
    source_row_number: int
    entity_type: CanonicalEntityType
    data: dict[str, object] = field(default_factory=dict)
    references: dict[ReferenceKey, dict[str, object]] = field(default_factory=dict)
    unmapped: dict[str, object] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """
        Показывает, прошла ли строка базовую нормализацию без ошибок.

        :return: `True`, если критических ошибок не найдено.
        """
        return not self.errors


@dataclass(slots=True)
class ResolvedRow:
    """
    Хранит строку после разрешения ссылочных данных.

    После этого этапа часть значений из `references` уже должна быть
    преобразована в реальные поля импорта, например в `group_id`.
    """

    normalized_row: NormalizedRow
    data: dict[str, object]
    resolved_references: dict[ReferenceKey, dict[str, object]] = field(default_factory=dict)
    unresolved_references: dict[ReferenceKey, dict[str, object]] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """
        Показывает, удалось ли разрешить строку до пригодного состояния.

        :return: `True`, если критических ошибок не найдено.
        """
        return not self.errors


@dataclass(slots=True)
class ImportProcessingResult:
    """
    Хранит полный результат подготовки таблицы к импорту.

    Внутри объекта собираются все промежуточные шаги обработки: нормализованные
    строки, строки после разрешения ссылок, готовые payload-словари и итоговые
    сообщения о проблемах.
    """

    entity_type: CanonicalEntityType
    normalized_rows: list[NormalizedRow] = field(default_factory=list)
    resolved_rows: list[ResolvedRow] = field(default_factory=list)
    create_payloads: list[dict[str, object]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """
        Показывает, можно ли безопасно переходить к реальному импорту в БД.

        :return: `True`, если итоговый результат не содержит ошибок.
        """
        return not self.errors


class DataNormalizer:
    """
    Преобразует нестандартные строки таблицы во внутренний нормализованный вид.

    Класс используется только для smart-импорта. Он не ищет данные в базе и
    не пытается сам что-либо сохранить. Его зона ответственности — понять,
    какие колонки Excel соответствуют полям сущности, и привести строку к
    стабильному промежуточному виду.

    Как использовать:

    1. Получить `ExtractedTable` из `XlsxRangeReader`.
    2. Передать его в `normalize_table(...)`.
    3. Получить список `NormalizedRow`, где:
       - `data` содержит прямые поля сущности;
       - `references` содержит ссылочные данные;
       - `unmapped` содержит лишние или пока нераспознанные колонки.
    """

    def __init__(self) -> None:
        """
        Создает нормализатор данных.
        """
        self._direct_alias_index = self._build_direct_alias_index()
        self._reference_alias_index = self._build_reference_alias_index()

    def normalize_table(self, extracted_table: ExtractedTable) -> list[NormalizedRow]:
        """
        Нормализует все строки выбранной таблицы.

        :param extracted_table: Ранее прочитанная таблица из XLSX.
        :return: Список нормализованных строк с распознанными полями,
            ссылочными данными и диагностикой по каждой строке.
        :raises ValueError: Если у таблицы не указан тип сущности или если
            сущность не поддерживается в режиме smart import.
        """
        if extracted_table.entity_type is None:
            raise ValueError("Extracted table must contain entity_type.")
        if not is_smart_import_entity_type(extracted_table.entity_type):
            raise ValueError(
                f"Entity type {extracted_table.entity_type!r} is not supported for smart import."
            )

        logger.info(
            "DataNormalizer started. sheet=%s range=%s entity_type=%s rows=%s.",
            extracted_table.sheet,
            extracted_table.range,
            extracted_table.entity_type,
            len(extracted_table.rows),
        )

        normalized_rows = [
            self.normalize_row(
                extracted_table.entity_type,
                row,
                source_sheet=extracted_table.sheet,
                source_range=extracted_table.range,
                source_row_number=index + 2,
            )
            for index, row in enumerate(extracted_table.rows)
        ]

        logger.info(
            "DataNormalizer finished. entity_type=%s rows=%s errors=%s.",
            extracted_table.entity_type,
            len(normalized_rows),
            sum(len(row.errors) for row in normalized_rows),
        )
        return normalized_rows

    def normalize_row(
        self,
        entity_type: CanonicalEntityType,
        raw_row: dict[str, object],
        *,
        source_sheet: str,
        source_range: str,
        source_row_number: int,
    ) -> NormalizedRow:
        """
        Нормализует одну строку таблицы.

        :param entity_type: Канонический тип сущности.
        :param raw_row: Сырая строка, прочитанная из диапазона Excel.
        :param source_sheet: Имя листа-источника.
        :param source_range: Диапазон, из которого была прочитана строка.
        :param source_row_number: Номер строки в исходном диапазоне Excel.
        :return: Нормализованная строка.
        """
        if not is_smart_import_entity_type(entity_type):
            raise ValueError(
                f"Entity type {entity_type!r} is not supported for smart import."
            )

        normalized_row = NormalizedRow(
            source_sheet=source_sheet,
            source_range=source_range,
            source_row_number=source_row_number,
            entity_type=entity_type,
        )

        direct_index = self._direct_alias_index.get(entity_type, {})
        reference_index = self._reference_alias_index.get(entity_type, {})

        for header, raw_value in raw_row.items():
            cleaned_value = self._clean_value(raw_value)
            if cleaned_value is None:
                continue

            normalized_header = self.normalize_header(header)

            if normalized_header in direct_index:
                field_name = direct_index[normalized_header]
                self._assign_value(
                    normalized_row.data,
                    field_name,
                    cleaned_value,
                    normalized_row.warnings,
                    context=f"field {field_name}",
                )
                continue

            if normalized_header in reference_index:
                reference_key, field_name = reference_index[normalized_header]
                self._assign_value(
                    normalized_row.references.setdefault(reference_key, {}),
                    field_name,
                    cleaned_value,
                    normalized_row.warnings,
                    context=f"reference {reference_key}.{field_name}",
                )
                continue

            normalized_row.unmapped[header] = cleaned_value

        self._validate_direct_data(normalized_row)
        self._validate_references(normalized_row)
        return normalized_row

    @staticmethod
    def normalize_header(header: str) -> str:
        """
        Приводит заголовок колонки к нормализованному виду для сравнения.

        :param header: Исходный заголовок колонки.
        :return: Нормализованное представление заголовка.
        """
        header = header.strip().lower().replace("ё", "е")
        header = re.sub(r"[_\-]+", " ", header)
        header = re.sub(r"\s+", " ", header)
        return header

    def describe_header_binding(
        self,
        entity_type: CanonicalEntityType,
        header: str,
    ) -> tuple[str, str | None]:
        """
        Определяет, как заголовок таблицы сопоставляется с внутренними полями.

        :param entity_type: Канонический тип сущности smart-импорта.
        :param header: Исходный заголовок колонки из Excel.
        :return: Пара из типа связи и целевого пути.
            Возможные типы связи:
            - `direct` — колонка сопоставлена прямому полю сущности;
            - `reference` — колонка сопоставлена ссылочному полю;
            - `unmapped` — колонка пока не распознана.
            Для `unmapped` второй элемент равен `None`.
        """
        normalized_header = self.normalize_header(header)
        direct_index = self._direct_alias_index.get(entity_type, {})
        if normalized_header in direct_index:
            return "direct", direct_index[normalized_header]

        reference_index = self._reference_alias_index.get(entity_type, {})
        if normalized_header in reference_index:
            reference_key, field_name = reference_index[normalized_header]
            return "reference", f"{reference_key}.{field_name}"

        return "unmapped", None

    @staticmethod
    def _clean_value(value: object) -> object | None:
        """
        Очищает значение ячейки перед нормализацией.

        :param value: Исходное значение ячейки.
        :return: Очищенное значение или `None`, если оно фактически пустое.
        """
        if value is None:
            return None

        if isinstance(value, str):
            value = value.strip()
            if value == "":
                return None

        return value

    @staticmethod
    def _assign_value(
        target: dict[str, object],
        key: str,
        value: object,
        warnings: list[str],
        *,
        context: str,
    ) -> None:
        """
        Записывает значение в словарь и фиксирует конфликт, если он есть.

        :param target: Словарь назначения.
        :param key: Ключ внутри словаря назначения.
        :param value: Новое значение.
        :param warnings: Список предупреждений строки.
        :param context: Краткое описание поля для текста предупреждения.
        """
        if key not in target:
            target[key] = value
            return

        existing_value = target[key]
        if existing_value != value:
            warnings.append(
                f"Conflicting values for {context}: {existing_value!r} and {value!r}."
            )

    def _validate_direct_data(self, normalized_row: NormalizedRow) -> None:
        """
        Проверяет типы и структуру прямых полей строки через filter-схему.

        :param normalized_row: Нормализованная строка.
        :return: `None`.
        """
        schema = FILTER_SCHEMA_BY_ENTITY.get(normalized_row.entity_type)
        if schema is None or not normalized_row.data:
            return

        try:
            validated_schema = schema.model_validate(normalized_row.data)
        except ValidationError as exc:
            normalized_row.errors.extend(self._validation_errors_to_messages(exc))
            return

        normalized_row.data = validated_schema.model_dump(exclude_unset=True)

    def _validate_references(self, normalized_row: NormalizedRow) -> None:
        """
        Проверяет структуру ссылочных данных строки.

        :param normalized_row: Нормализованная строка.
        :return: `None`.
        """
        for reference_key, reference_data in normalized_row.references.items():
            reference_schema = self._reference_filter_schema(reference_key)
            if reference_schema is None:
                normalized_row.warnings.append(
                    f"Unsupported reference type {reference_key!r} was left unresolved."
                )
                continue

            try:
                validated_schema = reference_schema.model_validate(reference_data)
            except ValidationError as exc:
                normalized_row.errors.extend(self._validation_errors_to_messages(exc))
                continue

            normalized_row.references[reference_key] = validated_schema.model_dump(
                exclude_unset=True
            )

    @staticmethod
    def _reference_filter_schema(reference_key: ReferenceKey) -> type[BaseModel] | None:
        """
        Возвращает filter-схему для конкретного ссылочного типа.

        :param reference_key: Имя ссылочной сущности.
        :return: Класс filter-схемы или `None`.
        """
        if reference_key == "group":
            return GroupFilterSchema

        return None

    @staticmethod
    def _validation_errors_to_messages(exc: ValidationError) -> list[str]:
        """
        Преобразует ошибки Pydantic в компактные текстовые сообщения.

        :param exc: Исключение валидации Pydantic.
        :return: Список текстов ошибок.
        """
        messages: list[str] = []

        for error in exc.errors():
            location = ".".join(str(part) for part in error["loc"])
            messages.append(f"{location}: {error['msg']}")

        return messages

    @staticmethod
    def _build_direct_alias_index() -> dict[CanonicalEntityType, dict[str, str]]:
        """
        Строит обратный индекс алиасов прямых полей.

        :return: Словарь вида `entity_type -> normalized_alias -> field_name`.
        """
        alias_index: dict[CanonicalEntityType, dict[str, str]] = {}

        for entity_type, fields in DIRECT_FIELD_ALIASES.items():
            alias_index[entity_type] = {}
            for field_name, aliases in fields.items():
                for alias in aliases:
                    alias_index[entity_type][DataNormalizer.normalize_header(alias)] = (
                        field_name
                    )

        return alias_index

    @staticmethod
    def _build_reference_alias_index() -> dict[
        CanonicalEntityType,
        dict[str, tuple[ReferenceKey, str]],
    ]:
        """
        Строит обратный индекс алиасов ссылочных полей.

        :return: Словарь вида
            `entity_type -> normalized_alias -> (reference_key, field_name)`.
        """
        alias_index: dict[CanonicalEntityType, dict[str, tuple[ReferenceKey, str]]] = {}

        for entity_type, references in REFERENCE_FIELD_ALIASES.items():
            alias_index[entity_type] = {}
            for reference_key, fields in references.items():
                for field_name, aliases in fields.items():
                    for alias in aliases:
                        alias_index[entity_type][
                            DataNormalizer.normalize_header(alias)
                        ] = (reference_key, field_name)

        return alias_index


class DataResolver:
    """
    Разрешает ссылочные данные в реальные поля импорта.

    Класс не знает ничего о том, как именно устроена база данных. Он получает
    callbacks извне и через них пытается заменить ссылочные признаки на
    реальные значения полей импорта.

    Как использовать:

    1. Создать объект, передав callbacks для нужных ссылок.
    2. Вызвать `resolve_rows(...)` после нормализации.
    3. Получить строки, в которых, например, `group.name` уже превращен в
       `group_id`, если callback смог его определить.
    """

    def __init__(
        self,
        *,
        reference_resolvers: dict[ReferenceKey, ResolverCallback] | None = None,
    ) -> None:
        """
        Создает резолвер ссылочных данных.

        :param reference_resolvers: Словарь callbacks по типу ссылки. Каждый
            callback получает словарь критериев поиска и возвращает словарь
            уже разрешенных полей, например `{"group_id": 15}`.
        """
        self.reference_resolvers = reference_resolvers or {}

    def resolve_rows(self, normalized_rows: list[NormalizedRow]) -> list[ResolvedRow]:
        """
        Разрешает ссылки для набора нормализованных строк.

        :param normalized_rows: Нормализованные строки таблицы.
        :return: Список строк после попытки разрешения ссылок.
        """
        logger.info(
            "DataResolver started. rows=%s resolvers=%s.",
            len(normalized_rows),
            tuple(sorted(self.reference_resolvers)),
        )
        resolved_rows = [self.resolve_row(row) for row in normalized_rows]
        logger.info(
            "DataResolver finished. rows=%s errors=%s.",
            len(resolved_rows),
            sum(len(row.errors) for row in resolved_rows),
        )
        return resolved_rows

    def resolve_row(self, normalized_row: NormalizedRow) -> ResolvedRow:
        """
        Разрешает ссылки одной нормализованной строки.

        :param normalized_row: Нормализованная строка.
        :return: Строка после попытки разрешения ссылок.
        """
        resolved_row = ResolvedRow(
            normalized_row=normalized_row,
            data=dict(normalized_row.data),
            warnings=list(normalized_row.warnings),
            errors=list(normalized_row.errors),
        )

        for reference_key, reference_data in normalized_row.references.items():
            resolver = self.reference_resolvers.get(reference_key)
            if resolver is None:
                resolved_row.unresolved_references[reference_key] = dict(reference_data)
                resolved_row.warnings.append(
                    f"No resolver was configured for reference {reference_key!r}."
                )
                continue

            logger.debug(
                "DataResolver resolving reference. reference_key=%s criteria=%s.",
                reference_key,
                reference_data,
            )
            resolved_values = resolver(dict(reference_data))

            if not resolved_values:
                resolved_row.unresolved_references[reference_key] = dict(reference_data)
                resolved_row.errors.append(
                    f"Could not resolve reference {reference_key!r} with criteria {reference_data!r}."
                )
                continue

            resolved_row.resolved_references[reference_key] = dict(resolved_values)
            resolved_row.data.update(resolved_values)

        return resolved_row


class ImportProcessor:
    """
    Оркестрирует нормализацию, разрешение ссылок и сбор итоговых payload-ов.

    Это верхний шаг умной подготовки таблицы. Он берет уже прочитанный
    диапазон, прогоняет его через нормализацию, затем через резолвер и в конце
    валидирует итоговые данные create-схемой нужной сущности.

    Как использовать:

    1. Получить `ExtractedTable` из `XlsxRangeReader`.
    2. Создать `ImportProcessor`, при необходимости передав callbacks
       разрешения ссылок.
    3. Вызвать `process_table(...)`.
    4. Использовать `result.create_payloads` как данные для create-схем и
       сервисов приложения.
    """

    def __init__(
        self,
        *,
        data_normalizer: DataNormalizer | None = None,
        data_resolver: DataResolver | None = None,
    ) -> None:
        """
        Создает процессор подготовки данных к импорту.

        :param data_normalizer: Пользовательский нормализатор данных.
        :param data_resolver: Пользовательский резолвер ссылочных данных.
        """
        self.data_normalizer = data_normalizer or DataNormalizer()
        self.data_resolver = data_resolver or DataResolver()

    def process_table(self, extracted_table: ExtractedTable) -> ImportProcessingResult:
        """
        Полностью обрабатывает выбранную таблицу до create-payload-ов.

        :param extracted_table: Извлеченная таблица из XLSX.
        :return: Полный результат обработки, включая промежуточные строки,
            итоговые payload-словари, предупреждения и ошибки.
        :raises ValueError: Если у таблицы отсутствует тип сущности.
        """
        if extracted_table.entity_type is None:
            raise ValueError("Extracted table must contain entity_type.")

        logger.info(
            "ImportProcessor started. entity_type=%s sheet=%s range=%s.",
            extracted_table.entity_type,
            extracted_table.sheet,
            extracted_table.range,
        )

        result = ImportProcessingResult(entity_type=extracted_table.entity_type)
        result.normalized_rows = self.data_normalizer.normalize_table(extracted_table)
        result.resolved_rows = self.data_resolver.resolve_rows(result.normalized_rows)

        create_schema = CREATE_SCHEMA_BY_ENTITY.get(extracted_table.entity_type)
        if create_schema is None:
            result.errors.append(
                f"Unsupported entity type for import processing: {extracted_table.entity_type!r}."
            )
            return result

        for resolved_row in result.resolved_rows:
            result.warnings.extend(resolved_row.warnings)
            result.errors.extend(resolved_row.errors)

            if not resolved_row.is_valid:
                continue

            try:
                validated_schema = create_schema.model_validate(resolved_row.data)
            except ValidationError as exc:
                result.errors.extend(
                    f"row {resolved_row.normalized_row.source_row_number}: {message}"
                    for message in self.data_normalizer._validation_errors_to_messages(exc)
                )
                continue

            result.create_payloads.append(
                validated_schema.model_dump(exclude_unset=True)
            )

        logger.info(
            "ImportProcessor finished. entity_type=%s payloads=%s errors=%s.",
            result.entity_type,
            len(result.create_payloads),
            len(result.errors),
        )
        return result
