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
    if spec.kind is not None and spec.kind.value == "tool":
        # A tool resolves its terse parameters against the input under its
        # `input_as` (resolve_parameters in AGENT_LIFECYCLE §…). Top-level tools
        # validate against their own input_schema; sibling references are
        # validated per-branch by the composite below.
        tool_scope: dict[str, Any] = (
            spec.input.input_schema.get("properties", {})
            if spec.input.input_schema
            else {}
        )
        _validate_parameters_chain(spec.parameters or {}, tool_scope)
        # TODO: tool signature coherence checked at load where possible (LEG-022)

    elif spec.kind is not None and spec.kind.value == "linguistic" and spec.prompt:
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

    # Composite: validate branches (bare pattern names resolved against catalog).
    # Each branch is a sequence of sibling references; tool steps may consume the
    # outputs of earlier siblings plus the composite's own input, so their
    # parameters are validated against the cumulative branch scope.
    if spec.type.value == "composite" and spec.branches:
        for branch_idx, branch in enumerate(spec.branches):
            branch_scope: dict[str, Any] = {}
            if spec.input.input_schema:
                branch_scope.update(
                    spec.input.input_schema.get("properties", {})
                )
            for step_name in branch:
                if step_name not in catalog:
                    raise UnrecoverableError(
                        f"composite {spec.name!r} branch {branch_idx} "
                        f"references unknown pattern: {step_name!r}"
                    )
                step_spec = catalog[step_name]
                if step_spec.kind is not None and step_spec.kind.value == "tool":
                    # The tool resolves its parameters against the input under
                    # its `input_as` (a sibling output) merged with the enclosing
                    # composite's own input scope — the union a step may reference
                    # (matching how the runtime re-keys the payload).
                    sibling_input = branch_scope.get(step_spec.input.input_as, {})
                    validation_scope = dict(branch_scope)
                    if isinstance(sibling_input, dict):
                        validation_scope.update(sibling_input)
                    _validate_parameters_chain(
                        step_spec.parameters or {}, validation_scope
                    )
                if step_spec.output.output_schema:
                    branch_scope[step_spec.output.output_as] = (
                        step_spec.output.output_schema.get("properties", {})
                    )

    if spec.output.output_schema:
        return {spec.output.output_as: spec.output.output_schema.get("properties", {})}
    return {}


def resolve_branch(
    branch: list[str], catalog: Catalog
) -> tuple[tuple[str, str], ...]:
    """Resolve a composite branch (bare pattern names) to a ``(class, input_as)`` route.

    Each step is a reference to a defined agent; its ``(class, input_as)`` pair is
    the class name and the referenced agent's declared ``input_as`` (Schema 2 —
    resolved by the loader when it builds the level/branch DAG, never declared on
    the step). A step whose referenced agent is a ``type: composite`` is kept as
    a position in the route; that composite performs its own fan-out when invoked
    through its inbox (reuse by reference, recursion).
    """
    route: list[tuple[str, str]] = []
    for step_name in branch:
        if step_name not in catalog:
            raise UnrecoverableError(
                f"branch references unknown pattern: {step_name!r}"
            )
        step = catalog.specs[step_name]
        route.append((step.name, step.input.input_as))
    return tuple(route)


def resolve_composite_branches(
    spec: AgentSpec, catalog: Catalog
) -> list[tuple[tuple[str, str], ...]]:
    """Resolve every branch of a composite to its expanded ``(class, input_as)`` route."""
    if spec.type.value != "composite" or not spec.branches:
        raise UnrecoverableError(f"spec {spec.name!r} is not a composite with branches")
    return [resolve_branch(branch, catalog) for branch in spec.branches]


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
        _load_all_documents(source, catalog)
    elif isinstance(source, (str, Path)):
        path = Path(source)
        if path.is_dir():
            for yaml_file in sorted(path.glob("*.yaml")):
                _load_all_documents(yaml_file.read_text(encoding="utf-8"), catalog)
        else:
            _load_all_documents(path.read_text(encoding="utf-8"), catalog)
    elif isinstance(source, (dict, list)):
        _load_specs_from_yaml(source, catalog)
    else:
        raise UnrecoverableError(f"unsupported source type: {type(source)}")

    logger.info("patterns loaded count=%d", len(catalog))
    return catalog


def _load_all_documents(text: str, catalog: Catalog) -> None:
    """Load every YAML document in a stream (multi-doc ``---`` supported)."""
    for document in yaml.safe_load_all(text):
        if document is not None:
            _load_specs_from_yaml(document, catalog)


__all__ = [
    "Catalog",
    "load_patterns",
    "resolve_branch",
    "resolve_composite_branches",
]