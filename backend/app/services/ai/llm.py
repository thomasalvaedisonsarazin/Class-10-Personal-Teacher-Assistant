"""LLM client abstraction (OpenAI Structured Outputs) with a deterministic fake.

Usage::

    from app.services.ai.llm import get_llm_client

    result = get_llm_client().generate_json(system_prompt, user_prompt, MySchema)
"""

from __future__ import annotations

import base64
import logging
import types
import typing
from collections.abc import Callable
from datetime import date, datetime
from enum import Enum
from functools import lru_cache
from typing import Any, Literal, Protocol, TypeVar, get_args, get_origin

from pydantic import BaseModel, ValidationError

from app.config import settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class LLMError(Exception):
    """Raised when the LLM call fails, is refused, or returns unusable output."""


class LLMClient(Protocol):
    """Interface for structured-output LLM calls."""

    def generate_json(
        self, system: str, user: str, schema: type[T], effort: str | None = None
    ) -> T:
        """Generate a response that validates against ``schema``.

        ``effort`` overrides the reasoning effort for this call (reasoning models only).

        Raises:
            LLMError: on API failure, refusal, or invalid output.
        """
        ...

    def generate_json_with_images(
        self,
        system: str,
        user: str,
        images: list[tuple[bytes, str]],
        schema: type[T],
        effort: str | None = None,
    ) -> T:
        """Like :meth:`generate_json`, with ``(data, mime_type)`` images attached to ``user``.

        Raises:
            LLMError: on API failure, refusal, or invalid output.
        """
        ...


class OpenAILLMClient:
    """OpenAI implementation using the Responses API with Structured Outputs."""

    def __init__(
        self,
        api_key: str,
        model: str,
        timeout: float = 60.0,
        max_retries: int = 2,
        vision_model: str | None = None,
        vision_timeout: float | None = None,
    ) -> None:
        import openai

        self._openai = openai
        self.model = model
        self.vision_model = vision_model or model
        self._vision_timeout = vision_timeout or timeout
        self._extra: dict[str, Any] = (
            {"reasoning": {"effort": settings.LLM_REASONING_EFFORT}}
            if model.startswith(("gpt-5", "o1", "o3", "o4"))
            else {}
        )
        self._client = openai.OpenAI(api_key=api_key, timeout=timeout, max_retries=max_retries)

    def generate_json(
        self, system: str, user: str, schema: type[T], effort: str | None = None
    ) -> T:
        """Call ``responses.parse`` with ``text_format=schema`` and return the parsed model."""
        return self._parse(system, user, schema, effort, self.model, None)

    def generate_json_with_images(
        self,
        system: str,
        user: str,
        images: list[tuple[bytes, str]],
        schema: type[T],
        effort: str | None = None,
    ) -> T:
        """Send the images as data URLs to the vision model (``GRADING_MODEL``)."""
        content: list[dict[str, str]] = [{"type": "input_text", "text": user}]
        for data, mime in images:
            encoded = base64.b64encode(data).decode("ascii")
            content.append(
                {
                    "type": "input_image",
                    "image_url": f"data:{mime};base64,{encoded}",
                    "detail": "high",
                }
            )
        return self._parse(
            system,
            [{"role": "user", "content": content}],
            schema,
            effort,
            self.vision_model,
            self._vision_timeout,
        )

    def _parse(
        self,
        system: str,
        user_input: str | list[dict[str, Any]],
        schema: type[T],
        effort: str | None,
        model: str,
        timeout: float | None,
    ) -> T:
        extra = dict(self._extra)
        if not model.startswith(("gpt-5", "o1", "o3", "o4")):
            extra.pop("reasoning", None)
        elif effort:
            extra["reasoning"] = {"effort": effort}
        client = self._client.with_options(timeout=timeout) if timeout else self._client
        try:
            response = client.responses.parse(
                model=model,
                instructions=system,
                input=user_input,
                text_format=schema,
                **extra,
            )
        except self._openai.OpenAIError as exc:
            logger.warning("OpenAI request failed: %s", type(exc).__name__)
            raise LLMError(f"LLM request failed: {type(exc).__name__}") from exc
        except ValidationError as exc:
            raise LLMError("LLM output did not match schema") from exc

        for item in response.output or []:
            for content in getattr(item, "content", None) or []:
                if getattr(content, "type", None) == "refusal":
                    raise LLMError(f"LLM refused: {getattr(content, 'refusal', '')}")

        parsed = response.output_parsed
        if parsed is None:
            raise LLMError("LLM returned no parsed output")
        if not isinstance(parsed, schema):
            try:
                return schema.model_validate(parsed)
            except ValidationError as exc:
                raise LLMError("LLM output did not match schema") from exc
        return parsed


# --------------------------------------------------------------------------- fake

FakeFactory = Callable[[str, str], BaseModel]


class FakeLLMClient:
    """Deterministic offline LLM.

    * If a factory is registered for the schema class, it is called with
      ``(system, user)`` and must return an instance of the schema.
    * Otherwise a schema-valid instance is synthesised from field types
      (strings, numbers, lists of one item, nested models, enums, literals...).

    ``calls`` records ``(system, user, schema)`` for assertions in tests.
    """

    def __init__(self) -> None:
        self._factories: dict[type[BaseModel], FakeFactory] = {}
        self._defaults: dict[type[BaseModel], FakeFactory] = {}
        self.calls: list[tuple[str, str, type[BaseModel]]] = []
        self.image_counts: list[int] = []

    def register(self, schema: type[BaseModel], factory: FakeFactory) -> None:
        """Register a canned factory used for ``schema``."""
        self._factories[schema] = factory

    def register_default(self, schema: type[BaseModel], factory: FakeFactory) -> None:
        """Register a built-in factory that survives :meth:`clear` (used by services)."""
        self._defaults[schema] = factory

    def generate_json_with_images(
        self,
        system: str,
        user: str,
        images: list[tuple[bytes, str]],
        schema: type[T],
        effort: str | None = None,
    ) -> T:
        """Same as :meth:`generate_json`; ``image_counts`` records how many images were sent."""
        self.image_counts.append(len(images))
        return self.generate_json(system, user, schema, effort)

    def unregister(self, schema: type[BaseModel]) -> None:
        """Remove a registered factory (no-op if absent)."""
        self._factories.pop(schema, None)

    def clear(self) -> None:
        """Remove all factories and recorded calls."""
        self._factories.clear()
        self.calls.clear()
        self.image_counts.clear()

    def generate_json(
        self, system: str, user: str, schema: type[T], effort: str | None = None
    ) -> T:
        """Return a canned or synthesised instance of ``schema``."""
        self.calls.append((system, user, schema))
        factory = self._factories.get(schema) or self._defaults.get(schema)
        if factory is not None:
            result = factory(system, user)
            if not isinstance(result, schema):
                raise LLMError(f"Fake factory for {schema.__name__} returned wrong type")
            return result
        try:
            return schema.model_validate(build_fake_data(schema))
        except ValidationError as exc:
            raise LLMError(f"Could not synthesise fake {schema.__name__}") from exc


def build_fake_data(schema: type[BaseModel], _depth: int = 0) -> dict[str, Any]:
    """Build a dict of deterministic placeholder values that validates against ``schema``."""
    data: dict[str, Any] = {}
    for name, field in schema.model_fields.items():
        if not field.is_required() and _depth > 3:
            continue
        data[name] = _fake_value(field.annotation, name, _depth)
    return data


def _fake_value(annotation: Any, name: str, depth: int) -> Any:  # noqa: C901 - type switch
    origin = get_origin(annotation)
    args = get_args(annotation)

    if origin is typing.Annotated:
        return _fake_value(args[0], name, depth)
    if origin in (typing.Union, types.UnionType):
        non_none = [a for a in args if a is not type(None)]
        return _fake_value(non_none[0], name, depth) if non_none else None
    if origin is Literal:
        return args[0]
    if origin in (list, set, frozenset, tuple) or annotation in (list, set, tuple):
        if origin is tuple and args and args[-1] is not Ellipsis:
            return [_fake_value(a, name, depth + 1) for a in args]
        item_type = args[0] if args else str
        return [_fake_value(item_type, name, depth + 1)]
    if origin is dict or annotation is dict:
        return {}
    if isinstance(annotation, type):
        if issubclass(annotation, BaseModel):
            return build_fake_data(annotation, depth + 1)
        if issubclass(annotation, Enum):
            return next(iter(annotation)).value
        if annotation is bool:
            return True
        if annotation is int:
            return 1
        if annotation is float:
            return 1.0
        if annotation is str:
            return f"Sample {name.replace('_', ' ')}"
        if annotation is datetime:
            return datetime(2026, 1, 1).isoformat()
        if annotation is date:
            return date(2026, 1, 1).isoformat()
    if annotation is Any or annotation is None:
        return f"Sample {name}"
    return f"Sample {name}"


_fake_singleton = FakeLLMClient()


@lru_cache(maxsize=1)
def _openai_client() -> OpenAILLMClient:
    return OpenAILLMClient(
        api_key=settings.OPENAI_API_KEY,
        model=settings.LLM_MODEL,
        timeout=settings.LLM_TIMEOUT_SECONDS,
        max_retries=settings.LLM_MAX_RETRIES,
        vision_model=settings.GRADING_MODEL or None,
        vision_timeout=settings.GRADING_TIMEOUT_SECONDS,
    )


def get_fake_llm_client() -> FakeLLMClient:
    """Return the process-wide fake LLM (useful to register factories in tests)."""
    return _fake_singleton


def get_llm_client() -> LLMClient:
    """Return the OpenAI client when ``OPENAI_API_KEY`` is set (and not testing), else the fake."""
    if settings.OPENAI_API_KEY and not settings.is_test:
        return _openai_client()
    return _fake_singleton
