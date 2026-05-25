"""
Классификация заголовков табличных файлов.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.io_tools.tabular.entity_schema_rules import (
    get_known_fields,
    get_required_fields,
)


@dataclass(slots=True)
class HeaderClassification:
    """
    Хранит результат разбора заголовков таблицы.
    """

    known_headers: tuple[str, ...]
    unknown_headers: tuple[str, ...]
    missing_required_headers: tuple[str, ...]


def classify_tabular_headers(
    entity_type: str | None,
    headers: tuple[str, ...],
) -> HeaderClassification:
    """
    Разделяет заголовки на известные, неизвестные и пропущенные обязательные.

    :param entity_type: Канонический тип сущности или `None`.
    :param headers: Заголовки таблицы в исходном порядке.
    :return: Результат классификации заголовков.
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
        header
        for header in required_fields
        if header not in headers
    )

    return HeaderClassification(
        known_headers=known_headers,
        unknown_headers=unknown_headers,
        missing_required_headers=missing_required_headers,
    )
