from __future__ import annotations

from typing import Generic, TypeVar

T = TypeVar("T")


class Repository(Generic[T]):
    """Generic repository base interface."""

    def __init__(self) -> None:
        self._storage: dict[str, T] = {}

    def save(self, entity_id: str, entity: T) -> T:
        self._storage[entity_id] = entity
        return entity

    def find_by_id(self, entity_id: str) -> T | None:
        return self._storage.get(entity_id)
