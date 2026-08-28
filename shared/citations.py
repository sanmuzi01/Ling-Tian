from __future__ import annotations

import re
from typing import Any


CITATION_RE = re.compile(r"\[S(\d+)\]")


def collect_citation_ids(items: list[dict[str, Any]]) -> set[str]:
    return {str(item["id"]) for item in items if item.get("id")}


def cited_ids(markdown: str) -> set[str]:
    return {f"S{match}" for match in CITATION_RE.findall(markdown)}


def validate_citations(markdown: str, citations: list[dict[str, Any]]) -> list[str]:
    known = collect_citation_ids(citations)
    used = cited_ids(markdown)
    warnings: list[str] = []
    missing = sorted(used - known)
    if missing:
        warnings.append(f"Unknown citation ids used in brief: {', '.join(missing)}")
    if not used:
        warnings.append("No citations were used in the generated brief.")
    return warnings

