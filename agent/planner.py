from __future__ import annotations

from agent.models import BriefIntent, ToolPlan
from shared.config import load_settings


def parse_intent(user_query: str) -> BriefIntent:
    settings = load_settings()
    normalized = user_query.lower()
    commodity = "lithium" if ("锂" in user_query or "lithium" in normalized) else "copper"
    asset = "Pilbara" if "pilbara" in normalized or "皮尔巴拉" in user_query else "target asset"
    topic = f"{asset} {commodity}"
    return BriefIntent(
        raw_query=user_query,
        topic=topic,
        company_or_asset=asset,
        commodity=commodity,
        days=7,
        pdf_url=settings.default_pdf_url,
    )


def build_plan(intent: BriefIntent) -> ToolPlan:
    related = [intent.commodity]
    if intent.commodity == "lithium":
        related.append("copper")
    return ToolPlan(
        news_query=f"{intent.company_or_asset} {intent.commodity} mining policy price",
        news_days=intent.days,
        article_limit=5,
        pdf_url=intent.pdf_url,
        commodities=related,
    )
