"""`legio.patterns.compile` — compile ``output_schema`` to pydantic (H4 / LEG-072).

Compiles a JSON-schema-style v1 ``output_schema`` into a validating pydantic
model: unions, arrays, nested objects and recursive ``$ref`` definitions.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, create_model


def _pytype(schema: Any, defs: Mapping[str, Any], memo: dict[str, Any]) -> Any:
    if isinstance(schema, list):
        non_null = [s for s in schema if s != "null"]
        inner = _pytype({"type": non_null[0]}, defs, memo) if non_null else Any
        return Any if "null" in schema and len(non_null) == 1 else inner | None

    if not isinstance(schema, Mapping):
        return Any

    ref = schema.get("$ref")
    if ref:
        name = ref.split("/")[-1]
        if name not in memo:
            memo[name] = create_model(f"Ref_{name}", __base__=BaseModel)
            memo[name] = _compile_submodel(defs[name], defs, memo)
        return memo[name]

    stype = schema.get("type")
    if isinstance(stype, list):
        return _pytype(stype, defs, memo)

    if stype == "string":
        return str
    if stype == "integer":
        return int
    if stype == "number":
        return float
    if stype == "boolean":
        return bool
    if stype == "array":
        items = schema.get("items")
        return list[_pytype(items, defs, memo)] if items is not None else list
    if stype == "object":
        return _compile_submodel(schema, defs, memo)
    if stype is None:
        props = schema.get("properties")
        if props is not None:
            return _compile_submodel(schema, defs, memo)
    return Any


def _compile_submodel(
    schema: Mapping[str, Any], defs: Mapping[str, Any], memo: dict[str, Any]
) -> type[BaseModel]:
    props = schema.get("properties") or {}
    fields: dict[str, Any] = {}
    for name, subschema in props.items():
        fields[name] = (_pytype(subschema, defs, memo), ...)
    return create_model("OutputModel", __base__=BaseModel, **fields)


def compile_output_schema(schema: dict[str, Any]) -> type[BaseModel]:
    """Return a pydantic model validating the given ``output_schema``."""
    defs: dict[str, Any] = dict(schema.get("$defs") or {})
    memo: dict[str, Any] = {}
    return _compile_submodel(schema, defs, memo)


__all__ = ["compile_output_schema"]
