"""Red contract tests for LEG-010 — Patterns YAML schema v1.

These tests define the public contract for loading and validating pattern
definitions written in the v1 YAML schema, resolving dotted template paths /
system variables, and compiling ``output_schema`` into pydantic models.

The modules imported here (``legio.patterns``, ``legio.patterns.compile``,
``legio.patterns.template``) do NOT exist yet. This file is intentionally
red: it must fail because the production code is not implemented.
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel, ValidationError

from legio.patterns import kind, load_pattern_specs, loads_pattern_spec
from legio.patterns.compile import compile_output_schema
from legio.patterns.template import resolve_template

SMALL_MAIN_YAML = """
name: main_a
kind: main
main: true
sequence:
  - stage: extract
    kind: atomic
    tool: true
    tool_type: text_extractor
    input_mapping:
      payload: input.payload
    output_as: extracted
  - stage: processors
    kind: composite
    parallel:
      - name: summ
      - name: cata
      - name: keys
    input_mapping:
      text: extracted.text
    output_as: results
"""

HeAVY_MAIN_YAML = """
name: main_b
kind: main
main: true
sequence:
  - stage: extract
    kind: atomic
    tool: true
    tool_type: text_extractor
    input_mapping:
      payload: input.payload
    output_as: extracted
  - stage: fanout
    kind: composite
    parallel:
      - name: summ
      - name: cata
      - name: keys
      - name: goal
      - name: draft_flow
        sequence:
          - stage: outline_step
            kind: atomic
            tool_type: outliner
            input_mapping:
              payload: input.payload
            output_as: stage_b
          - stage: inline
            kind: linguistic
            prompt: |
              Draft from {input.payload} and {stage_b.outline}.
            input_mapping:
              payload: input.payload
              outline: stage_b.outline
            output_as: draft
            output_schema:
              type: object
              properties:
                outline:
                  type: array
                  items:
                    $ref: "#/$defs/node"
              $defs:
                node:
                  type: object
                  properties:
                    key:
                      type: string
                    children:
                      type: array
                      items:
                        $ref: "#/$defs/node"
"""


def test_loads_small_main_pattern() -> None:
    spec = loads_pattern_spec(SMALL_MAIN_YAML)
    assert spec.name == "main_a"
    assert spec.kind == kind.MAIN
    assert spec.main is True


def test_loads_heavy_main_pattern() -> None:
    spec = load_pattern_specs(HeAVY_MAIN_YAML)
    assert len(spec) == 1
    assert spec[0].name == "main_b"
    assert spec[0].kind == kind.MAIN
    assert spec[0].main is True


def test_atomic_tool_kind_declares_tool_type() -> None:
    spec = loads_pattern_spec(SMALL_MAIN_YAML)
    first = spec.sequence[0]
    assert first.kind == kind.ATOMIC
    assert first.tool is True
    assert first.tool_type == "text_extractor"


def test_parallel_inline_stage_gets_auto_named_agent() -> None:
    """H1: inline parallel is materialised as an auto-named agent (own queue)."""
    spec = loads_pattern_spec(SMALL_MAIN_YAML)
    inline = spec.sequence[1]
    assert inline.kind == kind.COMPOSITE
    assert inline.auto_named is True
    assert inline.queue_name is not None
    assert inline.queue_name.startswith("main_a_")
    assert [child.name for child in inline.parallel] == ["summ", "cata", "keys"]


def test_inline_linguistic_stage_is_self_executed() -> None:
    """H1: inline linguistic stage is self-executed, no intermediate queue."""
    spec = loads_pattern_spec(HeAVY_MAIN_YAML)
    draft_flow = next(child for child in spec.sequence[1].parallel if child.name == "draft_flow")
    inline = draft_flow.sequence[1]
    assert inline.kind == kind.ATOMIC
    assert inline.linguistic is True
    assert inline.prompt is not None
    assert inline.self_executed is True
    assert inline.queue_name is None


def test_dotted_template_paths_resolve_against_payload() -> None:
    """H2: dotted paths resolve against the payload."""
    payload = {
        "input": {"payload": {"text": "hello"}, "lang": "en"},
        "stage_b": {"outline": ["intro", "body", "close"]},
    }
    system_vars = {"current_date": "2026-08-27"}

    rendered = resolve_template(
        "{input.payload.text} in {input.lang} on {current_date}", payload, system_vars
    )
    assert rendered == "hello in en on 2026-08-27"


def test_merge_is_flat_union_via_output_as() -> None:
    """H3: fan-in merge is a flat union of child outputs."""
    spec = loads_pattern_spec(HeAVY_MAIN_YAML)
    fanout = spec.sequence[1]
    assert fanout.output_as == ["summ", "cata", "keys", "goal", "draft"]
    assert fanout.merge_rename == {}


def test_compile_output_schema_with_union_array_nested_recursive() -> None:
    """H4: output_schema compiles unions, arrays, nested objects, recursion."""
    schema = {
        "type": "object",
        "properties": {
            "tags": {"type": "array", "items": {"type": "string"}},
            "score": {"type": ["string", "null"]},
            "notes": {"type": "object"},
            "outline": {
                "type": "array",
                "items": {"$ref": "#/$defs/node"},
            },
        },
        "$defs": {
            "node": {
                "type": "object",
                "properties": {
                    "key": {"type": "string"},
                    "children": {"type": "array", "items": {"$ref": "#/$defs/node"}},
                },
            }
        },
    }

    model: type[BaseModel] = compile_output_schema(schema)
    assert issubclass(model, BaseModel)

    good = model(
        tags=["a", "b"],
        score=None,
        notes={"a": 1},
        outline=[{"key": "n1", "children": [{"key": "n1.1", "children": []}]}],
    )
    assert good.tags == ["a", "b"]  # type: ignore[attr-defined]
    assert good.score is None  # type: ignore[attr-defined]

    with pytest.raises(ValidationError):
        model(tags=[1, 2], score="1.5", notes=None, outline=[])


def test_compile_output_schema_rejects_bad_payload() -> None:
    """H4: a payload violating the compiled schema is rejected."""
    schema = {"type": "object", "properties": {"score": {"type": "integer"}}}
    model = compile_output_schema(schema)
    with pytest.raises(ValidationError):
        model(score="not-an-int")
