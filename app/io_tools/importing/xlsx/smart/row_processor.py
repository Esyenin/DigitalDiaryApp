"""
Processor smart-импорта XLSX-таблиц.

Модуль содержит реальную логику smart-сценария и является единственным
активным источником:
1. нормализации строк;
2. распознавания заголовков;
3. выделения ссылочных признаков;
4. разрешения ссылок;
5. сборки legacy-результатов smart-импорта для обратной совместимости.
"""
from __future__ import annotations

from collections.abc import Callable
from pydantic import BaseModel, ValidationError

from app.io_tools.shared.results import (
    DataProcessingResult,
    ImportProcessingResult,
)
from app.io_tools.shared.tabular.models import (
    ExtractedTable,
    HeaderBinding,
    NormalizedRow,
    ProcessedRow,
    ResolvedRow,
)
from app.io_tools.shared.tabular.schema_registry import TabularSchemaRegistry
from app.io_tools.shared.tabular.schema_registry import normalize_tabular_header
from app.io_tools.shared.xlsx.config import SMART_IMPORT_ENTITY_TYPES
from app.schemas import GroupFilterSchema


ResolverCallback = Callable[[dict[str, object]], dict[str, object] | None]


def validation_errors_to_messages(exc: ValidationError) -> list[str]:
    """
    Приводит ошибки Pydantic к компактному текстовому виду.
    """
    messages: list[str] = []
    for error in exc.errors():
        location = ".".join(str(part) for part in error["loc"])
        messages.append(f"{location}: {error['msg']}")
    return messages


class SmartRowProcessor:
    """
    Выполняет полную smart-обработку таблицы.

    Класс специально собран как один понятный processor без промежуточных
    legacy-слоёв: flow вызывает его напрямую, а старые API-обёртки
    делегируют ему нужные операции для сохранения обратной совместимости.
    """

    def __init__(
        self,
        *,
        schema_registry: TabularSchemaRegistry | None = None,
        reference_resolvers: dict[str, ResolverCallback] | None = None,
    ) -> None:
        self.schema_registry = schema_registry or TabularSchemaRegistry()
        self.reference_resolvers = reference_resolvers or {}

    def process(
        self,
        table: ExtractedTable,
        *,
        detailed: bool = False,
    ) -> ImportProcessingResult | DataProcessingResult:
        """
        Выполняет smart-обработку таблицы и возвращает совместимый результат.
        """
        normalized_rows = self.normalize_table(table)
        resolved_rows = self.resolve_rows(normalized_rows)
        import_result = self.build_import_result(
            table.entity_type or "",
            normalized_rows,
            resolved_rows,
        )
        if not detailed:
            return import_result

        header_bindings = self.build_header_bindings(table)
        processed_rows = self.build_processed_rows(
            table,
            import_result,
        )
        return DataProcessingResult(
            entity_type=table.entity_type or "",
            source_sheet=table.sheet,
            source_range=table.range,
            header_bindings=header_bindings,
            rows=processed_rows,
            create_payloads=list(import_result.create_payloads),
            warnings=list(table.warnings) + list(import_result.warnings),
            errors=list(table.errors) + list(import_result.errors),
        )

    def normalize_table(self, table: ExtractedTable) -> list[NormalizedRow]:
        """
        Нормализует все строки извлечённой smart-таблицы.
        """
        entity_type = self._require_supported_entity_type(table.entity_type)
        return [
            self.normalize_row(
                entity_type,
                row,
                source_sheet=table.sheet,
                source_range=table.range,
                source_row_number=index + 2,
            )
            for index, row in enumerate(table.rows)
        ]

    def normalize_row(
        self,
        entity_type: str,
        raw_row: dict[str, object],
        *,
        source_sheet: str,
        source_range: str,
        source_row_number: int,
    ) -> NormalizedRow:
        """
        Нормализует одну строку таблицы.
        """
        canonical_entity_type = self._require_supported_entity_type(entity_type)
        normalized_row = NormalizedRow(
            source_sheet=source_sheet,
            source_range=source_range,
            source_row_number=source_row_number,
            entity_type=canonical_entity_type,
        )
        direct_aliases = self.schema_registry.get_field_aliases(canonical_entity_type)
        reference_aliases = self.schema_registry.get_reference_aliases(
            canonical_entity_type
        )

        for header, raw_value in raw_row.items():
            cleaned_value = self.clean_value(raw_value)
            if cleaned_value is None:
                continue

            normalized_header = self.normalize_header(header)
            if normalized_header in direct_aliases:
                field_name = direct_aliases[normalized_header]
                self.assign_value(
                    normalized_row.data,
                    field_name,
                    cleaned_value,
                    normalized_row.warnings,
                    context=f"field {field_name}",
                )
                continue

            if normalized_header in reference_aliases:
                reference_key, field_name = reference_aliases[normalized_header]
                self.assign_value(
                    normalized_row.references.setdefault(reference_key, {}),
                    field_name,
                    cleaned_value,
                    normalized_row.warnings,
                    context=f"reference {reference_key}.{field_name}",
                )
                continue

            normalized_row.unmapped[header] = cleaned_value

        self.validate_direct_data(normalized_row)
        self.validate_references(normalized_row)
        return normalized_row

    def resolve_rows(self, normalized_rows: list[NormalizedRow]) -> list[ResolvedRow]:
        """
        Разрешает ссылки у набора строк.
        """
        return [self.resolve_row(row) for row in normalized_rows]

    def resolve_row(self, normalized_row: NormalizedRow) -> ResolvedRow:
        """
        Разрешает ссылочные признаки одной строки.
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

    def build_import_result(
        self,
        entity_type: str,
        normalized_rows: list[NormalizedRow],
        resolved_rows: list[ResolvedRow],
    ) -> ImportProcessingResult:
        """
        Собирает итог smart-подготовки create-payload-ов.
        """
        result = ImportProcessingResult(
            entity_type=entity_type,
            normalized_rows=list(normalized_rows),
            resolved_rows=list(resolved_rows),
        )
        create_schema = self.schema_registry.get_create_schema(entity_type)
        if create_schema is None:
            result.errors.append(
                f"Unsupported entity type for import processing: {entity_type!r}."
            )
            return result

        for resolved_row in resolved_rows:
            result.warnings.extend(resolved_row.warnings)
            result.errors.extend(resolved_row.errors)
            if not resolved_row.is_valid:
                continue

            try:
                validated_schema = create_schema.model_validate(resolved_row.data)
            except ValidationError as exc:
                result.errors.extend(
                    f"row {resolved_row.normalized_row.source_row_number}: {message}"
                    for message in validation_errors_to_messages(exc)
                )
                continue

            result.create_payloads.append(
                validated_schema.model_dump(exclude_unset=True)
            )

        return result

    def build_header_bindings(self, table: ExtractedTable) -> list[HeaderBinding]:
        """
        Строит карту распознавания заголовков.
        """
        entity_type = self._require_supported_entity_type(table.entity_type)
        return [
            HeaderBinding(
                source_header=header,
                normalized_header=self.normalize_header(header),
                binding_type=binding.binding_type,
                target_path=binding.target_path,
            )
            for header, binding in (
                (
                    header,
                    self.schema_registry.classify_header(entity_type, header),
                )
                for header in table.headers
            )
        ]

    def build_processed_rows(
        self,
        table: ExtractedTable,
        import_result: ImportProcessingResult,
    ) -> list[ProcessedRow]:
        """
        Строит построчную трассировку smart-обработки.
        """
        payload_by_row_number = {
            resolved_row.normalized_row.source_row_number: payload
            for resolved_row, payload in zip(
                (
                    row
                    for row in import_result.resolved_rows
                    if row.is_valid
                ),
                import_result.create_payloads,
            )
        }
        normalized_by_row_number = {
            row.source_row_number: row for row in import_result.normalized_rows
        }
        resolved_by_row_number = {
            row.normalized_row.source_row_number: row
            for row in import_result.resolved_rows
        }

        processed_rows: list[ProcessedRow] = []
        for row_index, source_values in enumerate(table.rows, start=2):
            normalized_row = normalized_by_row_number.get(row_index)
            resolved_row = resolved_by_row_number.get(row_index)
            processed_rows.append(
                ProcessedRow(
                    source_row_number=row_index,
                    source_values=dict(source_values),
                    normalized_data=dict(normalized_row.data) if normalized_row else {},
                    references=(
                        dict(normalized_row.references) if normalized_row else {}
                    ),
                    resolved_data=dict(resolved_row.data) if resolved_row else {},
                    resolved_references=(
                        dict(resolved_row.resolved_references)
                        if resolved_row
                        else {}
                    ),
                    unresolved_references=(
                        dict(resolved_row.unresolved_references)
                        if resolved_row
                        else {}
                    ),
                    unmapped=dict(normalized_row.unmapped) if normalized_row else {},
                    warnings=self.merge_messages(
                        normalized_row.warnings if normalized_row else [],
                        resolved_row.warnings if resolved_row else [],
                    ),
                    errors=self.merge_messages(
                        normalized_row.errors if normalized_row else [],
                        resolved_row.errors if resolved_row else [],
                    ),
                    create_payload=payload_by_row_number.get(row_index),
                )
            )
        return processed_rows

    def describe_header_binding(
        self,
        entity_type: str,
        header: str,
    ) -> tuple[str, str | None]:
        """
        Возвращает тип привязки заголовка и путь назначения.
        """
        binding = self.schema_registry.classify_header(
            self._require_supported_entity_type(entity_type),
            header,
        )
        return binding.binding_type, binding.target_path

    def validate_direct_data(self, normalized_row: NormalizedRow) -> None:
        """
        Валидирует прямые поля строки через filter-схему.
        """
        schema = self.schema_registry.get_filter_schema(normalized_row.entity_type)
        if schema is None or not normalized_row.data:
            return
        try:
            validated_schema = schema.model_validate(normalized_row.data)
        except ValidationError as exc:
            normalized_row.errors.extend(validation_errors_to_messages(exc))
            return
        normalized_row.data = validated_schema.model_dump(exclude_unset=True)

    def validate_references(self, normalized_row: NormalizedRow) -> None:
        """
        Валидирует ссылочные признаки строки.
        """
        for reference_key, reference_data in normalized_row.references.items():
            reference_schema = self.reference_filter_schema(reference_key)
            if reference_schema is None:
                normalized_row.warnings.append(
                    f"Unsupported reference type {reference_key!r} was left unresolved."
                )
                continue
            try:
                validated_schema = reference_schema.model_validate(reference_data)
            except ValidationError as exc:
                normalized_row.errors.extend(validation_errors_to_messages(exc))
                continue
            normalized_row.references[reference_key] = validated_schema.model_dump(
                exclude_unset=True
            )

    @staticmethod
    def reference_filter_schema(reference_key: str) -> type[BaseModel] | None:
        """
        Возвращает filter-схему для ссылочного типа.
        """
        if reference_key == "group":
            return GroupFilterSchema
        return None

    @staticmethod
    def normalize_header(header: str) -> str:
        """
        Нормализует заголовок колонки.
        """
        return normalize_tabular_header(header)

    @staticmethod
    def clean_value(value: object) -> object | None:
        """
        Очищает значение ячейки перед разбором.
        """
        if value is None:
            return None
        if isinstance(value, str):
            value = value.strip()
            if value == "":
                return None
        return value

    @staticmethod
    def assign_value(
        target: dict[str, object],
        key: str,
        value: object,
        warnings: list[str],
        *,
        context: str,
    ) -> None:
        """
        Присваивает значение и фиксирует конфликт, если он есть.
        """
        if key not in target:
            target[key] = value
            return
        existing_value = target[key]
        if existing_value != value:
            warnings.append(
                f"Conflicting values for {context}: {existing_value!r} and {value!r}."
            )

    @staticmethod
    def merge_messages(
        first_messages: list[str],
        second_messages: list[str],
    ) -> list[str]:
        """
        Склеивает два набора сообщений в исходном порядке.
        """
        return list(first_messages) + list(second_messages)

    def _require_supported_entity_type(self, entity_type: str | None) -> str:
        """
        Проверяет, что сущность поддерживается smart-импортом.
        """
        canonical = self.schema_registry.normalize_entity_type(entity_type)
        if canonical is None:
            raise ValueError("Extracted table must contain entity_type.")
        if canonical not in SMART_IMPORT_ENTITY_TYPES:
            raise ValueError(
                f"Entity type {canonical!r} is not supported for smart import."
            )
        return canonical
