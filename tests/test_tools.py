"""Test tools for LEG-022 ToolAgent tests."""

def fake_transform(text: str, factor: int = 2) -> dict:
    """Domain-free fake tool: plain callable, signature is its contract."""
    return {"transformed": str(text).upper() * factor}


def fake_flip(text: str) -> dict:
    """Domain-free fake tool: plain callable, signature is its contract."""
    return {"flipped": str(text)[::-1]}


def fake_upper(text: str) -> dict:
    """Domain-free fake tool: plain callable, signature is its contract."""
    return {"upper": str(text).upper()}