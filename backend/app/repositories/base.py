"""Minimal repository base class."""
from __future__ import annotations

from typing import Any, Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.base import Base as ModelBase

T = TypeVar("T", bound=ModelBase)


class BaseRepository(Generic[T]):
    model: type[T]

    def __init__(self, db: Session):
        self.db = db

    def get(self, obj_id: int) -> T | None:
        return self.db.get(self.model, obj_id)

    def list(self, **filters: Any):
        stmt = select(self.model)
        for key, value in filters.items():
            stmt = stmt.where(getattr(self.model, key) == value)
        return list(self.db.scalars(stmt).all())

    def create(self, **values: Any) -> T:
        obj = self.model(**values)
        self.db.add(obj)
        self.db.flush()
        return obj

    def save(self, obj: T) -> T:
        self.db.add(obj)
        self.db.flush()
        return obj
