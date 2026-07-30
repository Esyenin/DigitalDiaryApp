"""
Профиль табличного маппинга для сущности.

Профиль нужен как компактное описание того, какие прямые поля и какие
ссылочные поля понимает процессор для конкретной сущности. Это удобная
точка сборки правил, если в будущем появятся настраиваемые профили
распознавания колонок.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class TabularMappingProfile:
    """
    Хранит индексы алиасов для одной сущности.
    """

    entity_type: str
    direct_aliases: dict[str, str] = field(default_factory=dict)
    reference_aliases: dict[str, tuple[str, str]] = field(default_factory=dict)
