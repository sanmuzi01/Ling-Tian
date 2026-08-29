from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal


def to_json(value: Any) -> Any:
    if hasattr(value, "__dataclass_fields__"):
        return asdict(value)
    if isinstance(value, list):
        return [to_json(item) for item in value]
    if isinstance(value, dict):
        return {key: to_json(item) for key, item in value.items()}
    return value


@dataclass(frozen=True)
class Citation:
    id: str
    title: str
    url: str
    source: str
    published_at: str | None = None
    page: int | None = None
    fetched_at: str | None = None


@dataclass(frozen=True)
class NewsHit:
    title: str
    url: str
    source: str
    published_at: str
    snippet: str
    score: float
    citation_id: str
    fetched_at: str | None = None


@dataclass(frozen=True)
class Article:
    title: str
    url: str
    source: str
    published_at: str
    text: str
    authors: list[str]
    citations: list[Citation]
    fetched_at: str | None = None


@dataclass(frozen=True)
class ResourceRecord:
    project: str
    category: Literal["Measured", "Indicated", "Inferred", "Unknown"]
    ore_tonnage_mt: float | None
    grade: float | None
    grade_unit: str | None
    contained_metal: float | None
    contained_metal_unit: str | None
    page: int | None
    confidence: float
    citation_id: str


@dataclass(frozen=True)
class ResourceExtractionResult:
    pdf_url: str
    status: Literal["ok", "partial", "abstain"]
    project: str
    resources: list[ResourceRecord]
    warnings: list[str]
    citations: list[Citation]


@dataclass(frozen=True)
class PricePoint:
    commodity: str
    date: str
    price: float
    currency: str
    unit: str
    citation_id: str


@dataclass(frozen=True)
class PriceTrend:
    commodity: str
    currency: str
    unit: str
    points: list[PricePoint]
    change_pct: float
    volatility: float
    trend: Literal["up", "down", "flat"]
    citations: list[Citation]


@dataclass
class BriefResult:
    topic: str
    markdown: str
    news: list[dict[str, Any]]
    resources: dict[str, Any]
    prices: list[dict[str, Any]]
    citations: list[dict[str, Any]]
    risks: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    run_report: dict[str, Any] = field(default_factory=dict)
