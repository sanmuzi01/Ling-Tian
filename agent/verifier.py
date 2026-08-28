from __future__ import annotations

from typing import Any

from shared.citations import validate_citations


def unique_citations(*groups: Any) -> list[dict[str, Any]]:
    seen: dict[str, dict[str, Any]] = {}

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            if {"id", "title", "url", "source"} <= set(value):
                seen.setdefault(str(value["id"]), value)
            for item in value.values():
                visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)

    for group in groups:
        visit(group)
    return [seen[key] for key in sorted(seen)]


def verify_evidence(
    markdown: str,
    citations: list[dict[str, Any]],
    resources: dict[str, Any],
    tool_errors: list[str],
) -> list[str]:
    warnings = validate_citations(markdown, citations)
    warnings.extend(tool_errors)
    if resources.get("status") in {"partial", "abstain"}:
        warnings.append(f"Resource extraction status is {resources.get('status')}.")
    for record in resources.get("resources", []):
        if record.get("confidence", 1.0) < 0.8:
            warnings.append(
                f"Low confidence resource record: {record.get('project')} {record.get('category')}"
            )
    return warnings

