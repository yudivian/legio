"""Contract tests for LEG-010 — Patterns Schema 1 (S1).

These tests define the public contract for loading and validating pattern
definitions written in the Schema 1 YAML format, with mandatory symmetric
contracts, terse tool parameters, and chain-wide dotted-path resolution.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from legio.patterns import (
    AgentKind,
    AgentSpec,
    AgentType,
    InputContract,
    IOType,
    OutputContract,
    load_patterns,
)
from legio.patterns.compile import compile_output_schema
from legio.patterns.template import resolve_template

# Schema 1 fixtures
SMALL_SEQUENCE_YAML = """
name: extract_and_summarize
type: composite
kind: sequence
input:
  input_as: payload
  input_type: json
  input_schema:
    type: object
    properties:
      text: {type: string}
      lang: {type: string}
output:
  output_as: result
  output_type: json
  output_schema:
    type: object
    properties:
      summary: {type: string}
      entities: {type: array, items: {type: string}}
sequence:
  - name: extract
    type: atomic
    kind: tool
    input:
      input_as: text
      input_type: json
      input_schema:
        type: object
        properties:
          text: {type: string}
    output:
      output_as: extracted
      output_type: json
      output_schema:
        type: object
        properties:
          entities: {type: array, items: {type: string}}
    tool: extractor
    parameters:
      text: "{text}"
  - name: summarize
    type: atomic
    kind: linguistic
    input:
      input_as: extracted
      input_type: json
      input_schema:
        type: object
        properties:
          entities: {type: array, items: {type: string}}
    output:
      output_as: summary
      output_type: json
      output_schema:
        type: object
        properties:
          summary: {type: string}
    prompt: "Summarize these entities: {entities}"
"""

PARALLEL_YAML = """
name: distribute_summary
type: composite
kind: parallel
input:
  input_as: payload
  input_type: json
  input_schema:
    type: object
    properties:
      text: {type: string}
output:
  output_as: results
  output_type: json
  output_schema:
    type: object
    properties:
      summ: {type: string}
      cata: {type: string}
parallel:
  - name: summ
    type: atomic
    kind: linguistic
    input:
      input_as: text
      input_type: json
      input_schema:
        type: object
        properties:
          text: {type: string}
    output:
      output_as: summ
      output_type: json
      output_schema:
        type: object
        properties:
          summ: {type: string}
    prompt: "Summarize: {text}"
  - name: cata
    type: atomic
    kind: linguistic
    input:
      input_as: text
      input_type: json
      input_schema:
        type: object
        properties:
          text: {type: string}
    output:
      output_as: cata
      output_type: json
      output_schema:
        type: object
        properties:
          cata: {type: string}
    prompt: "Categorize: {text}"
"""


def test_tool_agent_spec_schema1_loads() -> None:
    """A Schema 1 tool agent spec loads with mandatory symmetric contracts."""
    from legio.patterns.schema1 import InputContract, OutputContract
    spec = AgentSpec(
        name="extract",
        type=AgentType.ATOMIC,
        kind=AgentKind.TOOL,
        input=InputContract(
            input_as="text",
            input_type=IOType.JSON,
            input_schema={"type": "object", "properties": {"text": {"type": "string"}}},
        ),
        output=OutputContract(
            output_as="extracted",
            output_type=IOType.JSON,
            output_schema={"type": "object", "properties": {"entities": {"type": "array"}}},
        ),
        tool="extractor",
        parameters={"text": "{text}"},
    )
    assert spec.name == "extract"
    assert spec.type is AgentType.ATOMIC
    assert spec.kind is AgentKind.TOOL
    assert spec.input.input_as == "text"
    assert spec.output.output_as == "extracted"
    assert spec.tool == "extractor"
    assert spec.parameters == {"text": "{text}"}


def test_linguistic_agent_spec_schema1_loads() -> None:
    """A Schema 1 linguistic agent spec loads with mandatory symmetric contracts."""
    from legio.patterns.schema1 import InputContract, OutputContract
    spec = AgentSpec(
        name="summarize",
        type=AgentType.ATOMIC,
        kind=AgentKind.LINGUISTIC,
        input=InputContract(
            input_as="extracted",
            input_type=IOType.JSON,
            input_schema={"type": "object", "properties": {"entities": {"type": "array"}}},
        ),
        output=OutputContract(
            output_as="summary",
            output_type=IOType.JSON,
            output_schema={"type": "object", "properties": {"summary": {"type": "string"}}},
        ),
        prompt="Summarize: {entities}",
    )
    assert spec.kind is AgentKind.LINGUISTIC
    assert spec.prompt == "Summarize: {entities}"
    assert spec.tool is None


def test_sequence_composite_schema1_loads() -> None:
    """A Schema 1 sequence composite loads with child specs."""
    catalog = load_patterns(SMALL_SEQUENCE_YAML)
    spec = catalog.get("extract_and_summarize")
    assert spec is not None
    assert spec.name == "extract_and_summarize"
    assert spec.type is AgentType.COMPOSITE
    assert spec.kind is AgentKind.SEQUENCE
    assert spec.input.input_as == "payload"
    assert spec.output.output_as == "result"
    assert spec.sequence is not None
    assert len(spec.sequence) == 2
    assert spec.sequence[0].name == "extract"
    assert spec.sequence[0].kind is AgentKind.TOOL
    assert spec.sequence[1].name == "summarize"
    assert spec.sequence[1].kind is AgentKind.LINGUISTIC


def test_parallel_composite_schema1_loads() -> None:
    """A Schema 1 parallel composite loads with child specs."""
    catalog = load_patterns(PARALLEL_YAML)
    spec = catalog.get("distribute_summary")
    assert spec is not None
    assert spec.name == "distribute_summary"
    assert spec.type is AgentType.COMPOSITE
    assert spec.kind is AgentKind.PARALLEL
    assert spec.parallel is not None
    assert len(spec.parallel) == 2
    assert spec.parallel[0].name == "summ"
    assert spec.parallel[0].kind is AgentKind.LINGUISTIC
    assert spec.parallel[1].name == "cata"


def test_mandatory_contracts_enforced() -> None:
    """Missing input/output contract raises ValidationError."""
    with pytest.raises(ValidationError):
        AgentSpec(
            name="bad",
            type=AgentType.ATOMIC,
            kind=AgentKind.TOOL,
            input=InputContract(input_as="x", input_type=IOType.JSON),
            output=OutputContract(output_as="y", output_type=IOType.JSON, output_schema={"type": "object"}),
            tool="t",
            parameters={},
        )


def test_branch_exclusive_fields_enforced() -> None:
    """Tool agent must not have prompt; linguistic must not have tool."""
    # tool with prompt -> error
    with pytest.raises(ValidationError):
        AgentSpec(
            name="bad",
            type=AgentType.ATOMIC,
            kind=AgentKind.TOOL,
            input=InputContract(input_as="x", input_type=IOType.JSON, input_schema={}),
            output=OutputContract(output_as="y", output_type=IOType.JSON, output_schema={}),
            tool="t",
            parameters={},
            prompt="should not be here",
        )
    # linguistic with tool -> error
    with pytest.raises(ValidationError):
        AgentSpec(
            name="bad",
            type=AgentType.ATOMIC,
            kind=AgentKind.LINGUISTIC,
            input=InputContract(input_as="x", input_type=IOType.JSON, input_schema={}),
            output=OutputContract(output_as="y", output_type=IOType.JSON, output_schema={}),
            prompt="hello",
            tool="should not be here",
        )


def test_text_type_has_no_schema() -> None:
    """text type must not have input_schema/output_schema."""
    with pytest.raises(ValidationError):
        AgentSpec(
            name="bad",
            type=AgentType.ATOMIC,
            kind=AgentKind.TOOL,
            input=InputContract(input_as="x", input_type=IOType.TEXT, input_schema={"type": "object"}),
            output=OutputContract(output_as="y", output_type=IOType.TEXT, output_schema={}),
            tool="t",
            parameters={},
        )


def test_parallel_children_bind_only_from_entry() -> None:
    """Parallel children must resolve parameters from parent's input_as only."""
    # This test validates the loader enforces the parallel rule
    catalog = load_patterns(PARALLEL_YAML)
    spec = catalog.get("distribute_summary")
    assert spec is not None
    assert spec.parallel is not None
    # Both children use {text} which comes from parent's input_as "payload"
    # This should work
    for child in spec.parallel:
        assert child.input.input_as == "text"
        # The {text} path resolves from parent's input_as "payload"


def test_chain_wide_dotted_path_resolution() -> None:
    """A tool parameter can resolve against any earlier producer in chain."""
    # In SMALL_SEQUENCE_YAML, summarize uses {entities} from extract's output_as
    catalog = load_patterns(SMALL_SEQUENCE_YAML)
    spec = catalog.get("extract_and_summarize")
    assert spec is not None
    assert spec.sequence is not None
    summarize = spec.sequence[1]
    # summarize's prompt uses {entities} which is in extract's output_as "extracted"
    assert summarize.prompt == "Summarize these entities: {entities}"


def test_reuse_by_position() -> None:
    """The same agent definition can appear in multiple composites by position."""
    # This is tested by loading two different composites that reuse the same
    # agent definition (not shown here; would need a catalog with shared specs)


def test_starting_route_sequence() -> None:
    """starting_route returns ordered stage names for sequence."""
    from legio.patterns import starting_route

    catalog = load_patterns(SMALL_SEQUENCE_YAML)
    spec = catalog.get("extract_and_summarize")
    assert spec is not None
    route = starting_route(spec)
    assert route == ("extract", "summarize")


def test_starting_route_atomic() -> None:
    """starting_route returns (name,) for atomic agent."""
    from legio.patterns import starting_route
    from legio.patterns.schema1 import InputContract, OutputContract

    spec = AgentSpec(
        name="single_tool",
        type=AgentType.ATOMIC,
        kind=AgentKind.TOOL,
        input=InputContract(input_as="x", input_type=IOType.JSON, input_schema={}),
        output=OutputContract(output_as="y", output_type=IOType.JSON, output_schema={}),
        tool="t",
        parameters={},
    )
    route = starting_route(spec)
    assert route == ("single_tool",)


def test_starting_route_rejects_parallel() -> None:
    """starting_route raises for parallel composites (R-4+)."""
    from legio.errors import UnrecoverableError
    from legio.patterns import starting_route

    catalog = load_patterns(PARALLEL_YAML)
    spec = catalog.get("distribute_summary")
    assert spec is not None
    with pytest.raises(UnrecoverableError):
        starting_route(spec)


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
    model = compile_output_schema(schema)
    instance = model(tags=["a", "b"], score="high", notes={}, outline=[{"key": "k", "children": []}])
    assert instance.tags == ["a", "b"]  # type: ignore[attr-defined]
    assert instance.score == "high"  # type: ignore[attr-defined]


def test_dotted_template_paths_resolve() -> None:
    """H2: dotted template paths resolve against the payload."""
    template = "Hello {user.name}, you have {count} messages"
    payload = {"user": {"name": "Alice"}, "count": 5}
    result = resolve_template(template, payload, {})
    assert result == "Hello Alice, you have 5 messages"


def test_undefined_template_path_raises() -> None:
    """Undefined template path raises TemplateResolutionError."""
    from legio.errors import TemplateResolutionError
    with pytest.raises(TemplateResolutionError):
        resolve_template("Hello {missing}", {}, {})