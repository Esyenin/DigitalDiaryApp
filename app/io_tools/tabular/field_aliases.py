"""
Алиасы и нормализация заголовков табличных форматов.
"""
from __future__ import annotations

import re


CanonicalEntityType = str
ReferenceKey = str


DIRECT_FIELD_ALIASES: dict[CanonicalEntityType, dict[str, set[str]]] = {
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
        "is_assessment": {
            "is_assessment",
            "assessment",
            "аттестация",
        },
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


REFERENCE_FIELD_ALIASES: dict[
    CanonicalEntityType,
    dict[ReferenceKey, dict[str, set[str]]],
] = {
    "students": {
        "group": {
            "name": {"group", "group name", "группа", "название группы"},
        }
    }
}


def normalize_tabular_header(header: str) -> str:
    """
    Приводит заголовок колонки к нормализованному виду.

    :param header: Исходный текст заголовка.
    :return: Нормализованный заголовок для сравнения.
    """
    normalized_header = header.strip().lower().replace("ё", "е")
    normalized_header = re.sub(r"[_\-]+", " ", normalized_header)
    normalized_header = re.sub(r"\s+", " ", normalized_header)
    return normalized_header


def build_direct_alias_index() -> dict[CanonicalEntityType, dict[str, str]]:
    """
    Строит индекс прямых алиасов по сущностям.

    :return: Словарь вида `entity_type -> normalized_alias -> field_name`.
    """
    alias_index: dict[CanonicalEntityType, dict[str, str]] = {}

    for entity_type, fields in DIRECT_FIELD_ALIASES.items():
        alias_index[entity_type] = {}
        for field_name, aliases in fields.items():
            for alias in aliases:
                alias_index[entity_type][normalize_tabular_header(alias)] = field_name

    return alias_index


def build_reference_alias_index() -> dict[
    CanonicalEntityType,
    dict[str, tuple[ReferenceKey, str]],
]:
    """
    Строит индекс ссылочных алиасов по сущностям.

    :return: Словарь вида
        `entity_type -> normalized_alias -> (reference_key, field_name)`.
    """
    alias_index: dict[CanonicalEntityType, dict[str, tuple[ReferenceKey, str]]] = {}

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
