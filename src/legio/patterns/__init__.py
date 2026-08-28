"""`legio.patterns` — the v1 patterns schema and loader (LEG-021).

Patterns are the only place where domain knowledge lives (YAML data). This
module parses YAML v1 into typed, immutable pydantic models (LEG-010) and loads
a catalog. Compilation of ``output_schema`` lives in ``legio.patterns.compile``
(LEG-072); template resolution in ``legio.patterns.template``.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

import yaml
from pydantic import BaseModel, Field, ValidationError, model_validator


class kind(str, Enum):
    """Pattern / stage kinds."""

    MAIN = "main"
    ATOMIC = "atomic"
    COMPOSITE = "composite"


def _normalize_stage(raw: Any) -> Any:
    """Map ``kind: tool|linguistic`` onto atomic with the matching flag."""
    if isinstance(raw, dict):
        raw = dict(raw)
        raw_kind = raw.get("kind")
        if raw_kind in ("tool", "linguistic"):
            raw["kind"] = "atomic"
            raw[f"{raw_kind}"] = True if raw_kind == "tool" else raw.get("linguistic", True)
        for child_key in ("sequence", "parallel"):
            if child_key in raw and isinstance(raw[child_key], list):
                raw[child_key] = [_normalize_stage(c) for c in raw[child_key]]
    return raw


class Stage(BaseModel):
    """A single stage: an atomic (tool/linguistic) or a nested composite."""

    @model_validator(mode="before")
    @classmethod
    def _normalize(cls, value: Any) -> Any:
        return _normalize_stage(value)

    name: str | None = None
    stage: str | None = None
    kind: kind = kind.ATOMIC
    main: bool = False
    tool: bool = False
    linguistic: bool = False
    tool_type: str | None = None
    prompt: str | None = None
    input_mapping: dict[str, str] = Field(default_factory=dict)
    output_as: Any = None
    output_schema: dict[str, Any] | None = None
    tool_config: dict[str, Any] = Field(default_factory=dict)
    sequence: list[Stage] = Field(default_factory=list)
    parallel: list[Stage] = Field(default_factory=list)
    auto_named: bool = False
    queue_name: str | None = None
    self_executed: bool = False
    merge_rename: dict[str, str] = Field(default_factory=dict)


class PatternSpec(BaseModel):
    """A parsed v1 pattern (main, atomic, or composite)."""

    @model_validator(mode="before")
    @classmethod
    def _normalize(cls, value: Any) -> Any:
        return _normalize_stage(value)

    name: str
    kind: kind = kind.ATOMIC
    main: bool = False
    description: str | None = None
    tool: bool = False
    linguistic: bool = False
    tool_type: str | None = None
    prompt: str | None = None
    input_mapping: dict[str, str] = Field(default_factory=dict)
    output_as: Any = None
    output_schema: dict[str, Any] | None = None
    tool_config: dict[str, Any] = Field(default_factory=dict)
    sequence: list[Stage] = Field(default_factory=list)
    parallel: list[Stage] = Field(default_factory=list)


def _parse_stage(raw: dict[str, Any], owner_name: str) -> Stage:
    raw = dict(raw)
    raw_kind = raw.get("kind", "atomic")
    if raw_kind == "linguistic":
        raw["kind"] = "atomic"
        raw["linguistic"] = True

    stage = Stage(**raw)
    if raw_kind == "linguistic":
        stage.self_executed = True
        stage.queue_name = None
    return stage


def _materialize(stage: Stage, owner_name: str, is_root_main: bool) -> None:
    """Derive H1/H3 virtual fields (auto_named, queue_name, output_as, merge)."""

    if (
        (stage.kind is kind.COMPOSITE or "parallel" in stage.model_fields_set)
        and stage.auto_named is False
        and stage.parallel
    ):
        stage.auto_named = True
        if stage.queue_name is None:
            stage.queue_name = f"{owner_name}_{stage.name or stage.stage or 'processors'}"

    if stage.kind is kind.ATOMIC:
        if stage.linguistic or stage.prompt:
            stage.self_executed = True
            stage.queue_name = None
        elif stage.tool:
            stage.queue_name = stage.name or stage.stage

    if stage.parallel:
        outputs: list[str] = []
        for child in stage.parallel:
            outputs.append(_child_output(child))
        if stage.output_as is None:
            stage.output_as = outputs

    for child in stage.sequence:
        _materialize(child, owner_name, False)
    for child in stage.parallel:
        _materialize(child, owner_name, False)


def _child_output(child: Stage) -> str:
    if isinstance(child.output_as, str):
        return child.output_as
    if child.sequence and isinstance(child.sequence[-1].output_as, str):
        return str(child.sequence[-1].output_as)
    if child.parallel:
        last = child.parallel[-1]
        if isinstance(last.output_as, str):
            return str(last.output_as)
    return child.name or child.stage or "outcome"


def loads_pattern_spec(yaml_text: str) -> PatternSpec:
    """Parse a single pattern from YAML text and materialise virtual fields."""
    result = _loads(yaml_text, multiple=False)
    assert isinstance(result, PatternSpec)
    return result


def load_pattern_specs(yaml_text: str) -> list[PatternSpec]:
    """Parse one or more patterns from YAML text."""
    result = _loads(yaml_text, multiple=True)
    return [r for r in result] if isinstance(result, list) else [result]


def _loads(yaml_text: str, *, multiple: bool) -> PatternSpec | list[PatternSpec]:
    data = yaml.safe_load(yaml_text)
    if data is None:
        return [] if multiple else PatternSpec(name="empty")

    return _load(data, multiple=multiple)


def _load(data: Any, *, multiple: bool) -> PatternSpec | list[PatternSpec]:
    docs: list[dict[str, Any]] = []
    if isinstance(data, dict) and any(
        k in data for k in ("name", "kind", "main", "sequence", "parallel")
    ):
        docs = [data]
    elif isinstance(data, list):
        docs = [d for d in data if isinstance(d, dict)]
    else:
        raise ValidationError.from_exception_data("pattern", [])

    parsed: list[PatternSpec] = []
    for doc in docs:
        spec = PatternSpec(**doc)
        for s in spec.sequence:
            _materialize(s, spec.name, spec.main)
        for s in spec.parallel:
            _materialize(s, spec.name, spec.main)
        parsed.append(spec)

    if not multiple:
        if parsed:
            return parsed[0]
        raise ValidationError.from_exception_data("pattern", [])
    return parsed


__all__ = [
    "PatternSpec",
    "Stage",
    "kind",
    "load_pattern_specs",
    "loads_pattern_spec",
]
