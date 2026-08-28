from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BriefIntent:
    raw_query: str
    topic: str
    company_or_asset: str
    commodity: str
    days: int
    pdf_url: str


@dataclass(frozen=True)
class ToolPlan:
    news_query: str
    news_days: int
    article_limit: int
    pdf_url: str
    commodities: list[str]

