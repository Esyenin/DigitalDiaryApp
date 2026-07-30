"""
Общий реестр объектов по ключу.

Небольшой generic-реестр используется в нескольких местах:
для flow-ов, для будущих destination-handler'ов и для иных расширяемых
точек конфигурации. Он нужен, чтобы не размазывать `if/elif` по коду.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Generic, TypeVar


KeyT = TypeVar("KeyT")
ValueT = TypeVar("ValueT")


@dataclass(slots=True)
class KeyedRegistry(Generic[KeyT, ValueT]):
    """
    Простой реестр объектов по ключу.
    """

    _items: dict[KeyT, ValueT] = field(default_factory=dict)

    def register(self, key: KeyT, value: ValueT) -> None:
        """
        Регистрирует объект по ключу.
        """
        self._items[key] = value

    def get(self, key: KeyT) -> ValueT:
        """
        Возвращает объект по ключу.

        :raises KeyError: Если ключ не зарегистрирован.
        """
        return self._items[key]

    def keys(self) -> tuple[KeyT, ...]:
        """
        Возвращает все зарегистрированные ключи.
        """
        return tuple(self._items.keys())

    def values(self) -> tuple[ValueT, ...]:
        """
        Возвращает все зарегистрированные значения.
        """
        return tuple(self._items.values())

    def items(self) -> tuple[tuple[KeyT, ValueT], ...]:
        """
        Возвращает пары `ключ -> значение`.
        """
        return tuple(self._items.items())
