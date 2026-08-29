"""Red contract tests for LEG-031 — structured output / template values.

Formalizes the structured-output contract for R-3 atomics:

- Every atomic output is one validated pydantic record (this is satisfied where
  it is produced: ToolAgent validates ``output_schema``, LinguisticAgent
  validates ``output_model``); the record is dot-opened into the scoped board
  for later steps.
- ``resolve_template`` resolves dotted paths against that dot-opened record and
  system variables (e.g. ``{current_date}``) are always available.
- An **undefined path is an explicit error, never silent** (AGENTS.md rule 9):
  today ``resolve_template`` silently substitutes ``""``; this file pins the
  fixed contract.
"""

from __future__ import annotations

import pytest

from legio.errors import TemplateResolutionError
from legio.patterns.template import resolve_template

DOT_OPENED_RECORD = {
    "input": {"payload": {"text": "The quick brown fox"}, "lang": "en"},
    "step_a": {
        "title": "Foxes",
        "stats": {"count": 1, "tags": ["nouns", "animals"]},
        "summary": "A short note about foxes.",
    },
}

SYSTEM_VARS = {"current_date": "2026-08-28"}


def test_structured_record_flows_into_later_template() -> None:
    """A previous step's dot-opened record fills a downstream step's prompt."""
    rendered = resolve_template(
        "Draft {input.payload.text} from {step_a.title} and {step_a.stats.count} tags.",
        DOT_OPENED_RECORD,
        SYSTEM_VARS,
    )
    assert rendered == "Draft The quick brown fox from Foxes and 1 tags."


def test_system_vars_always_available() -> None:
    rendered = resolve_template(
        "On {current_date}: {step_a.summary}", DOT_OPENED_RECORD, SYSTEM_VARS
    )
    assert rendered == "On 2026-08-28: A short note about foxes."


def test_undefined_path_is_an_explicit_error_never_silent() -> None:
    """An undefined dotted path raises, never substitutes an empty string."""
    with pytest.raises(TemplateResolutionError):
        resolve_template("{input.missing.field}", DOT_OPENED_RECORD, SYSTEM_VARS)


def test_undefined_top_level_path_is_an_explicit_error() -> None:
    with pytest.raises(TemplateResolutionError):
        resolve_template("{step_z.outline}", DOT_OPENED_RECORD, SYSTEM_VARS)


def test_missing_value_is_an_explicit_error() -> None:
    """A path that resolves to ``None`` is treated as undefined (never silent)."""
    record = {"input": {"payload": {"text": None}}}
    with pytest.raises(TemplateResolutionError):
        resolve_template("{input.payload.text}", record, SYSTEM_VARS)
