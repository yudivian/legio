"""`legio.patterns.schema1` — Schema 1 agent spec models (LEG-010).

One agent spec: `type` × `kind` with mandatory symmetric contracts
and terse call vocabulary. No v1 legacy fields (`input_mapping`, etc.).
"""

from __future__ import annotations

from collections.abc import Iterable
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator


class AgentType(str, Enum):
    ATOMIC = "atomic"
    COMPOSITE = "composite"


class AgentKind(str, Enum):
    TOOL = "tool"
    LINGUISTIC = "linguistic"
    SEQUENCE = "sequence"
    PARALLEL = "parallel"


class IOType(str, Enum):
    TEXT = "text"
    JSON = "json"
    BINARY = "binary"


class InputContract(BaseModel):
    """Mandatory entry contract for every agent."""

    input_as: str = Field(..., description="Read alias (no reserved words)")
    input_type: IOType
    input_schema: dict[str, Any] | None = Field(
        default=None, description="Mandatory for json/binary; absent for text"
    )

    @model_validator(mode="after")
    def _validate_schema_for_type(self) -> InputContract:
        if self.input_type in (IOType.JSON, IOType.BINARY):
            if self.input_schema is None:
                raise ValueError(f"{self.input_type.value} requires input_schema")
        else:  # text
            if self.input_schema is not None:
                raise ValueError("text type must not have input_schema")
        return self


class OutputContract(BaseModel):
    """Mandatory output contract for every agent."""

    output_as: str = Field(..., description="Write alias")
    output_type: IOType
    output_schema: dict[str, Any] | None = Field(
        default=None, description="Mandatory for json/binary; absent for text"
    )

    @model_validator(mode="after")
    def _validate_schema_for_type(self) -> OutputContract:
        if self.output_type in (IOType.JSON, IOType.BINARY):
            if self.output_schema is None:
                raise ValueError(f"{self.output_type.value} requires output_schema")
        else:  # text
            if self.output_schema is not None:
                raise ValueError("text type must not have output_schema")
        return self


class AgentSpec(BaseModel):
    """One agent spec: type × kind with mandatory symmetric contracts."""

    type: AgentType
    kind: AgentKind
    name: str
    description: str | None = None
    main: bool = False

    # Mandatory symmetric contracts
    input: InputContract
    output: OutputContract

    # Interior (exactly one by kind)
    tool: str | None = Field(
        default=None, description="available_tools key (kind: tool)"
    )
    parameters: dict[str, str | int | float | bool] | None = Field(
        default=None, description="Terse call: {arg: dotted.path | literal}"
    )
    prompt: str | None = Field(
        default=None, description="Prompt template (kind: linguistic)"
    )
    sequence: list[AgentSpec] | None = Field(
        default=None, description="Child specs (kind: sequence)"
    )
    parallel: list[AgentSpec] | None = Field(
        default=None, description="Child specs (kind: parallel)"
    )

    @model_validator(mode="after")
    def _validate_kind_fields(self) -> AgentSpec:
        # Discriminators
        if self.kind is AgentKind.TOOL:
            if self.tool is None:
                raise ValueError("kind: tool requires tool (available_tools key)")
            if self.parameters is None:
                raise ValueError("kind: tool requires parameters")
            if self.prompt is not None:
                raise ValueError("kind: tool must not have prompt")
        elif self.kind is AgentKind.LINGUISTIC:
            if self.prompt is None:
                raise ValueError("kind: linguistic requires prompt")
            if self.tool is not None:
                raise ValueError("kind: linguistic must not have tool")
            if self.parameters is not None:
                raise ValueError("kind: linguistic must not have parameters")
        elif self.kind is AgentKind.SEQUENCE:
            if self.sequence is None:
                raise ValueError("kind: sequence requires sequence")
            if self.tool is not None:
                raise ValueError("kind: sequence must not have tool")
            if self.prompt is not None:
                raise ValueError("kind: sequence must not have prompt")
        elif self.kind is AgentKind.PARALLEL:
            if self.parallel is None:
                raise ValueError("kind: parallel requires parallel")
            if self.tool is not None:
                raise ValueError("kind: parallel must not have tool")
            if self.prompt is not None:
                raise ValueError("kind: parallel must not have prompt")
        else:
            raise ValueError(f"unknown kind: {self.kind}")

        # Branch-exclusive
        interior_fields = [
            ("tool", self.tool),
            ("parameters", self.parameters),
            ("prompt", self.prompt),
            ("sequence", self.sequence),
            ("parallel", self.parallel),
        ]
        present = [name for name, val in interior_fields if val is not None]
        # For atomic kinds, tool/parameters/prompt are expected; for composites, sequence/parallel
        if self.type is AgentType.ATOMIC:
            if self.kind is AgentKind.TOOL:
                expected = {"tool", "parameters"}
            elif self.kind is AgentKind.LINGUISTIC:
                expected = {"prompt"}
            else:
                expected = set()
        else:  # COMPOSITE
            if self.kind is AgentKind.SEQUENCE:
                expected = {"sequence"}
            elif self.kind is AgentKind.PARALLEL:
                expected = {"parallel"}
            else:
                expected = set()

        if set(present) != expected:
            raise ValueError(
                f"kind {self.kind.value} with type {self.type.value} "
                f"requires exactly {expected}, got {set(present)}"
            )

        # Composite children: for parallel, children bind only from entry (input_as)
        # This is validated at load-time in the loader (LEG-021)

        return self


# Rebuild for forward references
AgentSpec.model_rebuild()


class Catalog(BaseModel):
    """Read-only catalog of loaded agent specs."""

    specs: dict[str, AgentSpec] = Field(default_factory=dict)

    def get(self, name: str) -> AgentSpec | None:
        return self.specs.get(name)

    def values(self) -> Iterable[AgentSpec]:
        return self.specs.values()

    def __contains__(self, name: str) -> bool:
        return name in self.specs

    def __len__(self) -> int:
        return len(self.specs)


__all__ = [
    "AgentKind",
    "AgentSpec",
    "AgentType",
    "Catalog",
    "IOType",
    "InputContract",
    "OutputContract",
]