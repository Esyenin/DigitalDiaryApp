"""
Канонический реестр схем и табличных правил сущностей.

Это единственный источник:

1. create/filter strict-схем;
2. alias-ов прямых и ссылочных полей;
3. нормализации заголовков;
4. набора обязательных и известных полей;
5. strict-заголовков;
6. классификации заголовков таблицы.
"""
from __future__ import annotations

from dataclasses import dataclass
import re

from pydantic import BaseModel

from app.io_tools.shared.tabular.mapping_profile import TabularMappingProfile
from app.io_tools.shared.tabular.models import HeaderBinding
from app.io_tools.shared.xlsx.config import (
    XLSX_COLUMNS_BY_SHEET,
    XLSX_REQUIRED_COLUMNS_BY_SHEET,
    normalize_sheet_keys,
)
from app.schemas import (
    AttendanceCreateSchema,
    AttendanceFilterSchema,
    CommentCreateSchema,
    CommentFilterSchema,
    GroupCreateSchema,
    GroupFilterSchema,
    LessonCreateSchema,
    LessonFilterSchema,
    MarkCreateSchema,
    MarkFilterSchema,
    ScheduleCreateSchema,
    ScheduleFilterSchema,
    ScheduleGroupLinkCreateSchema,
    ScheduleGroupLinkFilterSchema,
    StudentCreateSchema,
    StudentFilterSchema,
)


DIRECT_FIELD_ALIASES: dict[str, dict[str, set[str]]] = {
    "groups": {
        "name": {"name", "group", "groups", "группа", "группы"},
        "speciality": {
            "speciality",
            "specialities",
            "специальность",
            "специальности",
        },
    },
    "schedules": {
        "odd_or_even": {
            "odd_or_even",
            "odd or even",
            "четность",
            "нечетность",
        },
        "type": {"type", "тип"},
        "is_assessment": {"is_assessment", "assessment", "аттестация"},
        "day": {"day", "день", "день недели"},
        "time": {"time", "время"},
    },
    "students": {
        "surname": {
            "surname",
            "last name",
            "lastname",
            "фамилия",
            "фамилии",
        },
        "first_name": {
            "first name",
            "firstname",
            "first_name",
            "имя",
            "name",
            "имена",
        },
        "patronymic": {
            "patronymic",
            "middle name",
            "middlename",
            "отчество",
            "отчества",
        },
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


REFERENCE_FIELD_ALIASES: dict[str, dict[str, dict[str, set[str]]]] = {
    "students": {
        "group": {
            "name": {"group", "group name", "группа", "название группы"},
        }
    }
}


FILTER_SCHEMA_BY_ENTITY: dict[str, type[BaseModel]] = {
    "groups": GroupFilterSchema,
    "schedules": ScheduleFilterSchema,
    "students": StudentFilterSchema,
    "schedule_group_links": ScheduleGroupLinkFilterSchema,
    "lessons": LessonFilterSchema,
    "attendances": AttendanceFilterSchema,
    "marks": MarkFilterSchema,
    "comments": CommentFilterSchema,
}


CREATE_SCHEMA_BY_ENTITY: dict[str, type[BaseModel]] = {
    "groups": GroupCreateSchema,
    "schedules": ScheduleCreateSchema,
    "students": StudentCreateSchema,
}


STRICT_CREATE_SCHEMA_BY_ENTITY: dict[str, type[BaseModel]] = {
    "schedule_group_links": ScheduleGroupLinkCreateSchema,
    "lessons": LessonCreateSchema,
    "attendances": AttendanceCreateSchema,
    "marks": MarkCreateSchema,
    "comments": CommentCreateSchema,
}


@dataclass(slots=True, frozen=True)
class HeaderClassification:
    """
    Результат классификации набора заголовков таблицы.
    """

    known_headers: tuple[str, ...]
    unknown_headers: tuple[str, ...]
    missing_required_headers: tuple[str, ...]


def normalize_tabular_header(header: str) -> str:
    """
    Приводит заголовок колонки к нормализованному виду.
    """
    normalized_header = header.strip().lower().replace("ё", "е")
    normalized_header = re.sub(r"[_\-]+", " ", normalized_header)
    normalized_header = re.sub(r"\s+", " ", normalized_header)
    return normalized_header


def build_direct_alias_index() -> dict[str, dict[str, str]]:
    """
    Строит индекс прямых alias-ов по сущностям.
    """
    alias_index: dict[str, dict[str, str]] = {}
    for entity_type, fields in DIRECT_FIELD_ALIASES.items():
        alias_index[entity_type] = {}
        for field_name, aliases in fields.items():
            for alias in aliases:
                alias_index[entity_type][normalize_tabular_header(alias)] = field_name
    return alias_index


def build_reference_alias_index() -> dict[str, dict[str, tuple[str, str]]]:
    """
    Строит индекс ссылочных alias-ов по сущностям.
    """
    alias_index: dict[str, dict[str, tuple[str, str]]] = {}
    for entity_type, references in REFERENCE_FIELD_ALIASES.items():
        alias_index[entity_type] = {}
        for reference_key, fields in references.items():
            for field_name, aliases in fields.items():
                for alias in aliases:
                    alias_index[entity_type][normalize_tabular_header(alias)] = (
                        reference_key,
                        field_name,
                    )
    return alias_index


def get_known_fields(entity_type: str) -> tuple[str, ...]:
    """
    Возвращает известные поля сущности по filter-схеме.
    """
    schema = FILTER_SCHEMA_BY_ENTITY.get(entity_type)
    if schema is None:
        return ()
    return tuple(schema.model_fields.keys())


def get_required_fields(entity_type: str) -> tuple[str, ...]:
    """
    Возвращает обязательные поля сущности для табличного импорта.
    """
    return tuple(XLSX_REQUIRED_COLUMNS_BY_SHEET.get(entity_type, ()))


def classify_tabular_headers(
    entity_type: str | None,
    headers: tuple[str, ...],
) -> HeaderClassification:
    """
    Разделяет заголовки на известные, неизвестные и пропущенные обязательные.
    """
    if entity_type is None:
        return HeaderClassification(
            known_headers=(),
            unknown_headers=headers,
            missing_required_headers=(),
        )

    known_fields = get_known_fields(entity_type)
    required_fields = get_required_fields(entity_type)
    known_headers = tuple(header for header in headers if header in known_fields)
    unknown_headers = tuple(header for header in headers if header not in known_fields)
    missing_required_headers = tuple(
        header for header in required_fields if header not in headers
    )
    return HeaderClassification(
        known_headers=known_headers,
        unknown_headers=unknown_headers,
        missing_required_headers=missing_required_headers,
    )


class TabularSchemaRegistry:
    """
    Предоставляет единый доступ к схемам и табличным правилам сущностей.
    """

    def __init__(self) -> None:
        self._direct_alias_index = build_direct_alias_index()
        self._reference_alias_index = build_reference_alias_index()

    @staticmethod
    def normalize_entity_type(entity_type: str | None) -> str | None:
        if entity_type is None:
            return None
        return normalize_sheet_keys([entity_type])[0]

    def get_create_schema(self, entity_type: str) -> type[BaseModel] | None:
        return CREATE_SCHEMA_BY_ENTITY.get(self.normalize_entity_type(entity_type) or "")

    def get_filter_schema(self, entity_type: str) -> type[BaseModel] | None:
        return FILTER_SCHEMA_BY_ENTITY.get(self.normalize_entity_type(entity_type) or "")

    def get_strict_create_schema(self, entity_type: str) -> type[BaseModel] | None:
        return STRICT_CREATE_SCHEMA_BY_ENTITY.get(
            self.normalize_entity_type(entity_type) or ""
        )

    def get_field_aliases(self, entity_type: str) -> dict[str, str]:
        canonical = self.normalize_entity_type(entity_type)
        return dict(self._direct_alias_index.get(canonical or "", {}))

    def get_reference_aliases(self, entity_type: str) -> dict[str, tuple[str, str]]:
        canonical = self.normalize_entity_type(entity_type)
        return dict(self._reference_alias_index.get(canonical or "", {}))

    def get_required_fields(self, entity_type: str) -> set[str]:
        canonical = self.normalize_entity_type(entity_type)
        if canonical is None:
            return set()
        return set(get_required_fields(canonical))

    def get_known_fields(self, entity_type: str) -> set[str]:
        canonical = self.normalize_entity_type(entity_type)
        if canonical is None:
            return set()
        return set(get_known_fields(canonical))

    def get_strict_headers(self, entity_type: str) -> list[str]:
        canonical = self.normalize_entity_type(entity_type)
        if canonical is None:
            return []
        return list(XLSX_COLUMNS_BY_SHEET.get(canonical, ()))

    def get_mapping_profile(self, entity_type: str) -> TabularMappingProfile:
        canonical = self.normalize_entity_type(entity_type)
        if canonical is None:
            raise ValueError("Entity type is required for mapping profile.")
        return TabularMappingProfile(
            entity_type=canonical,
            direct_aliases=self.get_field_aliases(canonical),
            reference_aliases=self.get_reference_aliases(canonical),
        )

    def classify_header(self, entity_type: str, header: str) -> HeaderBinding:
        canonical = self.normalize_entity_type(entity_type)
        if canonical is None:
            raise ValueError("Entity type is required for header classification.")

        normalized_header = normalize_tabular_header(header)
        direct_aliases = self._direct_alias_index.get(canonical, {})
        if normalized_header in direct_aliases:
            return HeaderBinding(
                source_header=header,
                normalized_header=normalized_header,
                binding_type="direct",
                target_path=direct_aliases[normalized_header],
            )

        reference_aliases = self._reference_alias_index.get(canonical, {})
        if normalized_header in reference_aliases:
            reference_key, field_name = reference_aliases[normalized_header]
            return HeaderBinding(
                source_header=header,
                normalized_header=normalized_header,
                binding_type="reference",
                target_path=f"{reference_key}.{field_name}",
            )

        return HeaderBinding(
            source_header=header,
            normalized_header=normalized_header,
            binding_type="unmapped",
            target_path=None,
        )

    def classify_headers(
        self,
        entity_type: str | None,
        headers: tuple[str, ...],
    ) -> HeaderClassification:
        canonical = self.normalize_entity_type(entity_type) if entity_type else None
        return classify_tabular_headers(canonical, headers)
