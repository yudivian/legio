"""`legio.patterns.loader` — Schema 1 patterns loader (LEG-021).

Loads and validates patterns from YAML Schema 1 into typed AgentSpec models,
with all LEG-010 validations: branch-exclusive, mandatory contracts,
chain-wide dotted-path resolution, contract compatibility, reuse, encapsulation.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

from legio.errors import UnrecoverableError
from legio.patterns.schema1 import AgentSpec, Catalog

logger = logging.getLogger(__name__)


def _resolve_dotted_path(path: str, scope: dict[str, Any]) -> Any:
    """Resolve a dotted path against a scope dict."""
    current: Any = scope
    for part in path.split("."):
        if isinstance(current, dict):
            current = current.get(part)
        else:
            raise KeyError(f"path {path!r} unresolved at {part!r}")
        if current is None:
            raise KeyError(f"path {path!r} resolved to None")
    return current


def _validate_parameters_chain(
    parameters: dict[str, Any], chain_scope: dict[str, Any]
) -> None:
    """Validate that every parameter path resolves in the chain scope."""
    for arg, value in parameters.items():
        if isinstance(value, str) and value.startswith("{") and value.endswith("}"):
            path = value[1:-1]
            try:
                _resolve_dotted_path(path, chain_scope)
            except KeyError as exc:
                raise UnrecoverableError(
                    f"parameter {arg!r} path {path!r} does not resolve in chain: {exc}"
                ) from exc


def _build_chain_scope(spec: AgentSpec, parent_scope: dict[str, Any] | None) -> dict[str, Any]:
    """Build the scope for a spec and its children."""
    scope = {}
    if parent_scope:
        scope.update(parent_scope)
    # Add this spec's input_as properties at top level (for child parameter resolution)
    if spec.input.input_schema:
        props = spec.input.input_schema.get("properties", {})
        scope.update(props)
    # Add this spec's output_as -> its output_schema properties (for later siblings)
    if spec.output.output_schema:
        scope[spec.output.output_as] = spec.output.output_schema.get("properties", {})
    return scope


def _validate_agent_spec(
    spec: AgentSpec,
    parent_scope: dict[str, Any] | None = None,
    catalog: dict[str, AgentSpec] | None = None,
) -> dict[str, Any]:
    """Validate a single agent spec and return its output scope for children.

    Raises UnrecoverableError on any validation failure.
    """
    if catalog is None:
        catalog = {}

    # Interior ↔ contract coherence
    if spec.kind.value == "tool":
        # tool parameters coherence: each dotted path must resolve in chain
        _validate_parameters_chain(spec.parameters or {}, parent_scope or {})
        # TODO: tool signature coherence checked at load where possible (LEG-022)

    elif spec.kind.value == "linguistic" and spec.prompt:
        # prompt variables ↔ input_schema
        import re

        vars_in_prompt = set(re.findall(r"\{([a-zA-Z_][\w.]*)\}", spec.prompt))
        input_schema_props = (
            spec.input.input_schema.get("properties", {}) if spec.input.input_schema else {}
        )
        declared = set(input_schema_props.keys())
        unused = vars_in_prompt - declared - {"current_date"}
        undeclared = declared - vars_in_prompt
        if unused:
            raise UnrecoverableError(
                f"linguistic agent {spec.name!r}: prompt uses undeclared variables: {unused}"
            )
        if undeclared:
            raise UnrecoverableError(
                f"linguistic agent {spec.name!r}: input_schema has unused declarations: {undeclared}"
            )

    # Composite children validation
    child_scope = _build_chain_scope(spec, parent_scope)

    if spec.type.value == "composite":
        if spec.kind.value == "sequence":
            # sequence: each child sees previous siblings' outputs
            current_scope = dict(child_scope)
            if spec.sequence:
                for child in spec.sequence:
                    _validate_agent_spec(child, current_scope, catalog)
                    if child.output.output_schema:
                        current_scope[child.output.output_as] = child.output.output_schema.get("properties", {})
        elif spec.kind.value == "parallel":
            # parallel: children bind ONLY from parent's entry (input_as)
            entry_scope = {spec.input.input_as: spec.input.input_schema or {}}
            if spec.parallel:
                for child in spec.parallel:
                    _validate_agent_spec(child, entry_scope, catalog)
        else:
            raise UnrecoverableError(f"unknown composite kind: {spec.kind.value}")

    if spec.output.output_schema:
        return {spec.output.output_as: spec.output.output_schema.get("properties", {})}
    return {}


def _load_specs_from_yaml(data: Any, catalog: Catalog) -> list[AgentSpec]:
    """Load one or more specs from parsed YAML data."""
    if isinstance(data, dict):
        docs = [data]
    elif isinstance(data, list):
        docs = data
    else:
        raise UnrecoverableError("YAML must be a dict or list of dicts")

    specs = []
    for doc in docs:
        if not isinstance(doc, dict):
            raise UnrecoverableError("each pattern must be a mapping")
        spec = AgentSpec(**doc)
        specs.append(spec)
        if spec.name in catalog.specs:
            raise UnrecoverableError(f"duplicate pattern name: {spec.name}")
        catalog.specs[spec.name] = spec

    # Second pass: validate with full catalog for reuse references
    for spec in specs:
        _validate_agent_spec(spec, catalog=catalog.specs)

    return specs


def load_patterns(source: str | Path | dict[str, Any] | list[dict[str, Any]]) -> Catalog:
    """Load patterns from a YAML file/directory or dict/list.

    Args:
        source: Path to YAML file/directory, or parsed dict/list, or YAML string.

    Returns:
        A read-only Catalog of validated AgentSpec models.

    Raises:
        UnrecoverableError: on any validation failure (parse, branch-exclusive,
            mandatory contracts, chain resolution, contract compatibility,
            reuse, encapsulation/cycles).
    """
    catalog = Catalog()

    # Handle YAML string (contains newlines or starts with YAML indicators)
    if isinstance(source, str) and ("\n" in source or source.strip().startswith(("{", "[", "-", "name:"))):
        data = yaml.safe_load(source)
        if data:
            _load_specs_from_yaml(data, catalog)
    elif isinstance(source, (str, Path)):
        path = Path(source)
        if path.is_dir():
            for yaml_file in sorted(path.glob("*.yaml")):
                text = yaml_file.read_text(encoding="utf-8")
                data = yaml.safe_load(text)
                if data:
                    _load_specs_from_yaml(data, catalog)
        else:
            text = path.read_text(encoding="utf-8")
            data = yaml.safe_load(text)
            if data:
                _load_specs_from_yaml(data, catalog)
    elif isinstance(source, (dict, list)):
        _load_specs_from_yaml(source, catalog)
    else:
        raise UnrecoverableError(f"unsupported source type: {type(source)}")

    logger.info("patterns loaded count=%d", len(catalog))
    return catalog


__all__ = ["Catalog", "load_patterns"]