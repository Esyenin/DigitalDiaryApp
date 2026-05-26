"""
Маленькие шаги smart-импорта и их вспомогательные сервисы.
"""
from __future__ import annotations

from collections.abc import Callable

from pydantic import BaseModel, ValidationError

from app.io_tools.engine.operation_context import ImportOperationContext
from app.io_tools.engine.processing_models import (
    DataProcessingResult,
    HeaderBinding,
    ImportProcessingResult,
    NormalizedRow,
    ProcessedRow,
    ResolvedRow,
)
from app.io_tools.engine.steps.base import BaseImportStep
from app.io_tools.tabular.entity_schema_rules import (
    CREATE_SCHEMA_BY_ENTITY,
    FILTER_SCHEMA_BY_ENTITY,
)
from app.io_tools.tabular.field_aliases import (
    build_direct_alias_index,
    build_reference_alias_index,
    normalize_tabular_header,
)
from app.io_tools.xlsx_config import is_smart_import_entity_type
from app.schemas import GroupFilterSchema
from app.io_tools.tabular.models import ExtractedTable


ResolverCallback = Callable[[dict[str, object]], dict[str, object] | None]


def validation_errors_to_messages(exc: ValidationError) -> list[str]:
    """
    Приводит ошибки Pydantic к компактному текстовому виду.

    :param exc: Исключение валидации.
    :return: Список текстов ошибок.
    """
    messages: list[str] = []

    for error in exc.errors():
        location = ".".join(str(part) for part in error["loc"])
        messages.append(f"{location}: {error['msg']}")

    return messages


class SmartRowNormalizer:
    """
    Нормализует строки smart-таблицы в общий промежуточный вид.
    """

    def __init__(self) -> None:
        """
        Создаёт нормализатор строк.
        """
        self._direct_alias_index = build_direct_alias_index()
        self._reference_alias_index = build_reference_alias_index()

    def normalize_table(
        self,
        source: ImportOperationContext | ExtractedTable,
    ) -> list[NormalizedRow]:
        """
        Нормализует все строки извлечённой таблицы.

        :param context: Контекст операции.
        :return: Нормализованные строки.
        """
        if isinstance(source, ImportOperationContext):
            extracted_table = source.state.extracted_table
        else:
            extracted_table = source
        if extracted_table is None:
            raise ValueError("Import context does not contain extracted_table.")
        if extracted_table.entity_type is None:
            raise ValueError("Extracted table must contain entity_type.")
        if not is_smart_import_entity_type(extracted_table.entity_type):
            raise ValueError(
                f"Entity type {extracted_table.entity_type!r} is not supported for smart import."
            )

        return [
            self.normalize_row(
                extracted_table.entity_type,
                row,
                source_sheet=extracted_table.sheet,
                source_range=extracted_table.range,
                source_row_number=index + 2,
            )
            for index, row in enumerate(extracted_table.rows)
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

        :param entity_type: Тип сущности.
        :param raw_row: Исходная строка Excel.
        :param source_sheet: Имя листа.
        :param source_range: Диапазон таблицы.
        :param source_row_number: Номер строки в диапазоне.
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
            cleaned_value = self.clean_value(raw_value)
            if cleaned_value is None:
                continue

            normalized_header = self.normalize_header(header)

            if normalized_header in direct_index:
                field_name = direct_index[normalized_header]
                self.assign_value(
                    normalized_row.data,
                    field_name,
                    cleaned_value,
                    normalized_row.warnings,
                    context=f"field {field_name}",
                )
                continue

            if normalized_header in reference_index:
                reference_key, field_name = reference_index[normalized_header]
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

    def describe_header_binding(
        self,
        entity_type: str,
        header: str,
    ) -> tuple[str, str | None]:
        """
        Описывает, как заголовок сопоставляется с моделью данных.

        :param entity_type: Тип сущности.
        :param header: Исходный заголовок.
        :return: Пара вида `(тип_привязки, путь_назначения)`.
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
    def normalize_header(header: str) -> str:
        """
        Нормализует заголовок колонки.

        :param header: Исходный заголовок.
        :return: Нормализованный заголовок.
        """
        return normalize_tabular_header(header)

    @staticmethod
    def clean_value(value: object) -> object | None:
        """
        Очищает значение ячейки перед разбором.

        :param value: Исходное значение.
        :return: Очищенное значение или `None`.
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
    def validate_direct_data(normalized_row: NormalizedRow) -> None:
        """
        Валидирует прямые поля строки через filter-схему.
        """
        schema = FILTER_SCHEMA_BY_ENTITY.get(normalized_row.entity_type)
        if schema is None or not normalized_row.data:
            return

        try:
            validated_schema = schema.model_validate(normalized_row.data)
        except ValidationError as exc:
            normalized_row.errors.extend(validation_errors_to_messages(exc))
            return

        normalized_row.data = validated_schema.model_dump(exclude_unset=True)

    @staticmethod
    def validate_references(normalized_row: NormalizedRow) -> None:
        """
        Валидирует ссылочные признаки строки.
        """
        for reference_key, reference_data in normalized_row.references.items():
            reference_schema = SmartRowNormalizer.reference_filter_schema(reference_key)
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


class SmartReferenceResolver:
    """
    Разрешает ссылочные признаки строк в реальные поля импорта.
    """

    def __init__(
        self,
        *,
        reference_resolvers: dict[str, ResolverCallback] | None = None,
    ) -> None:
        self.reference_resolvers = reference_resolvers or {}

    def resolve_rows(self, normalized_rows: list[NormalizedRow]) -> list[ResolvedRow]:
        return [self.resolve_row(row) for row in normalized_rows]

    def resolve_row(self, normalized_row: NormalizedRow) -> ResolvedRow:
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


class SmartImportAssembler:
    """
    Собирает итоговые результаты smart-импорта из шагов pipeline.
    """

    def build_import_result(self, context: ImportOperationContext) -> ImportProcessingResult:
        extracted_table = context.state.extracted_table
        if extracted_table is None or extracted_table.entity_type is None:
            raise ValueError("Import context does not contain a valid extracted_table.")

        result = ImportProcessingResult(
            entity_type=extracted_table.entity_type,
            normalized_rows=list(context.state.normalized_rows),
            resolved_rows=list(context.state.resolved_rows),
        )
        create_schema = CREATE_SCHEMA_BY_ENTITY.get(extracted_table.entity_type)
        if create_schema is None:
            result.errors.append(
                f"Unsupported entity type for import processing: {extracted_table.entity_type!r}."
            )
            return result

        for resolved_row in context.state.resolved_rows:
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

    def build_processing_result(
        self,
        context: ImportOperationContext,
    ) -> DataProcessingResult:
        extracted_table = context.state.extracted_table
        import_result = context.state.import_result
        if extracted_table is None or extracted_table.entity_type is None:
            raise ValueError("Import context does not contain a valid extracted_table.")
        if import_result is None:
            raise ValueError("Import context does not contain import_result.")

        return DataProcessingResult(
            entity_type=extracted_table.entity_type,
            source_sheet=extracted_table.sheet,
            source_range=extracted_table.range,
            header_bindings=list(context.state.header_bindings),
            rows=list(context.state.processed_rows),
            create_payloads=list(import_result.create_payloads),
            warnings=list(extracted_table.warnings) + list(import_result.warnings),
            errors=list(extracted_table.errors) + list(import_result.errors),
        )

    def build_processed_rows(self, context: ImportOperationContext) -> list[ProcessedRow]:
        extracted_table = context.state.extracted_table
        import_result = context.state.import_result
        if extracted_table is None or import_result is None:
            raise ValueError("Import context is not ready for processed rows building.")

        payload_by_row_number = {
            row.normalized_row.source_row_number: payload
            for row, payload in zip(
                (
                    resolved_row
                    for resolved_row in import_result.resolved_rows
                    if resolved_row.is_valid
                ),
                import_result.create_payloads,
            )
        }
        normalized_by_row_number = {
            row.source_row_number: row
            for row in import_result.normalized_rows
        }
        resolved_by_row_number = {
            row.normalized_row.source_row_number: row
            for row in import_result.resolved_rows
        }

        processed_rows: list[ProcessedRow] = []
        for row_index, source_values in enumerate(extracted_table.rows, start=2):
            normalized_row = normalized_by_row_number.get(row_index)
            resolved_row = resolved_by_row_number.get(row_index)
            processed_rows.append(
                ProcessedRow(
                    source_row_number=row_index,
                    source_values=dict(source_values),
                    normalized_data=dict(normalized_row.data) if normalized_row else {},
                    references=dict(normalized_row.references) if normalized_row else {},
                    resolved_data=dict(resolved_row.data) if resolved_row else {},
                    resolved_references=(
                        dict(resolved_row.resolved_references) if resolved_row else {}
                    ),
                    unresolved_references=(
                        dict(resolved_row.unresolved_references) if resolved_row else {}
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

    def build_header_bindings(
        self,
        context: ImportOperationContext,
        row_normalizer: SmartRowNormalizer,
    ) -> list[HeaderBinding]:
        extracted_table = context.state.extracted_table
        if extracted_table is None or extracted_table.entity_type is None:
            raise ValueError("Import context does not contain a valid extracted_table.")

        bindings: list[HeaderBinding] = []
        for header in extracted_table.headers:
            binding_type, target_path = row_normalizer.describe_header_binding(
                extracted_table.entity_type,
                header,
            )
            bindings.append(
                HeaderBinding(
                    source_header=header,
                    normalized_header=row_normalizer.normalize_header(header),
                    binding_type=binding_type,
                    target_path=target_path,
                )
            )

        return bindings

    @staticmethod
    def merge_messages(
        first_messages: list[str],
        second_messages: list[str],
    ) -> list[str]:
        return list(first_messages) + list(second_messages)


class NormalizeRowsStep(BaseImportStep):
    """
    Шаг нормализации строк smart-таблицы.
    """

    def __init__(self, row_normalizer: SmartRowNormalizer) -> None:
        self.row_normalizer = row_normalizer

    def run(self, context: ImportOperationContext) -> None:
        context.state.normalized_rows = self.row_normalizer.normalize_table(context)


class ResolveRowsStep(BaseImportStep):
    """
    Шаг разрешения ссылок smart-таблицы.
    """

    def __init__(self, reference_resolver: SmartReferenceResolver) -> None:
        self.reference_resolver = reference_resolver

    def run(self, context: ImportOperationContext) -> None:
        context.state.resolved_rows = self.reference_resolver.resolve_rows(
            context.state.normalized_rows
        )


class BuildSmartImportResultStep(BaseImportStep):
    """
    Шаг сборки итогового smart-результата.
    """

    def __init__(self, assembler: SmartImportAssembler) -> None:
        self.assembler = assembler

    def run(self, context: ImportOperationContext) -> None:
        context.state.import_result = self.assembler.build_import_result(context)
        context.result = context.state.import_result


class BuildHeaderBindingsStep(BaseImportStep):
    """
    Шаг построения карты распознавания заголовков.
    """

    def __init__(
        self,
        assembler: SmartImportAssembler,
        row_normalizer: SmartRowNormalizer,
    ) -> None:
        self.assembler = assembler
        self.row_normalizer = row_normalizer

    def run(self, context: ImportOperationContext) -> None:
        context.state.header_bindings = self.assembler.build_header_bindings(
            context,
            self.row_normalizer,
        )


class BuildProcessedRowsStep(BaseImportStep):
    """
    Шаг построения построчной трассировки smart-обработки.
    """

    def __init__(self, assembler: SmartImportAssembler) -> None:
        self.assembler = assembler

    def run(self, context: ImportOperationContext) -> None:
        context.state.processed_rows = self.assembler.build_processed_rows(context)
