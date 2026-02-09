"""Utilities for parameterizing merit tests."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from typing import Any

from merit.testing.models import ParameterSet, ParametrizeModifier


def _normalize_argnames(argnames: str | Sequence[str]) -> tuple[tuple[str, ...] | None, str | None]:
    if isinstance(argnames, str):
        parts = [name.strip() for name in argnames.split(",") if name.strip()]
    else:
        parts = [str(name) for name in argnames]
    if not parts:
        return None, "parametrize() requires at least one argument name"
    return tuple(parts), None


def _normalize_values(raw: Any, expected: int) -> tuple[tuple[Any, ...] | None, str | None]:
    if expected == 1 and not isinstance(raw, (tuple, list)):
        return (raw,), None
    if not isinstance(raw, (tuple, list)):
        return None, "parametrize() values must be tuples or lists"
    values = tuple(raw)
    if len(values) != expected:
        return None, f"parametrize() expected {expected} values, got {len(values)}"
    return values, None


def _format_id(names: tuple[str, ...], values: tuple[Any, ...]) -> str:
    formatted = []
    for name, value in zip(names, values):
        if isinstance(value, (int, float, str, bool)) or value is None:
            val = str(value)
        else:
            val = value.__class__.__name__
        formatted.append(f"{name}={val}")
    return "-".join(formatted)


def _build_modifier(
    argnames: str | Sequence[str],
    argvalues: Iterable[Any],
    ids: Sequence[str] | None,
) -> tuple[ParametrizeModifier | None, str | None]:
    names, names_error = _normalize_argnames(argnames)
    if names_error:
        return None, names_error
    if names is None:
        return None, "parametrize() requires at least one argument name"

    values_list: list[tuple[Any, ...]] = []
    for raw_value in argvalues:
        values, values_error = _normalize_values(raw_value, len(names))
        if values_error:
            return None, values_error
        if values is not None:
            values_list.append(values)

    if not values_list:
        return None, "parametrize() requires at least one value set"

    ids_tuple: tuple[str, ...] | None = None
    if ids is not None:
        ids_tuple = tuple(str(identifier) for identifier in ids)
        if len(ids_tuple) != len(values_list):
            return None, "parametrize() ids must match number of value sets"

    parameter_sets = tuple(
        ParameterSet(
            values=dict(zip(names, vals)),
            id_suffix=ids_tuple[i] if ids_tuple else _format_id(names, vals),
        )
        for i, vals in enumerate(values_list)
    )

    return ParametrizeModifier(parameter_sets=parameter_sets), None


def parametrize(
    argnames: str | Sequence[str],
    argvalues: Iterable[Any],
    *,
    ids: Sequence[str] | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Parameterize a test function or method.

    Examples:
    --------
    >>> @parametrize("prompt,expected", [("hi", "Hello hi"), ("hey", "Hello hey")])
    ... def merit_chat(prompt, expected): ...
    """
    modifier, definition_error = _build_modifier(argnames, argvalues, ids)

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        if definition_error:
            fn.__merit_definition_error__ = definition_error  # type: ignore[attr-defined]
            return fn

        if modifier is None:
            return fn

        modifiers: list[Any] = getattr(fn, "__merit_modifiers__", [])
        modifiers.append(modifier)
        fn.__merit_modifiers__ = modifiers  # type: ignore[attr-defined]
        return fn

    return decorator
