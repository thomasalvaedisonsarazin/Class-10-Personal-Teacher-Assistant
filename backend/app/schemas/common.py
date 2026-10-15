"""Shared schema base classes.

API payloads use camelCase on the wire (TypeScript clients) and snake_case in
Python. ``ORMModel`` subclasses accept either form on input and always
serialise by alias (camelCase).
"""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

T = TypeVar("T")


class CamelModel(BaseModel):
    """Base schema with camelCase aliases that serialises by alias by default."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        validate_by_name=True,
        validate_by_alias=True,
        serialize_by_alias=True,
    )


class ORMModel(CamelModel):
    """CamelCase schema that can be built from ORM objects (``from_attributes``)."""

    model_config = ConfigDict(from_attributes=True)


class Page(CamelModel, Generic[T]):
    """A page of results."""

    items: list[T]
    total: int
    page: int
    size: int


class Message(CamelModel):
    """Simple message response."""

    message: str
