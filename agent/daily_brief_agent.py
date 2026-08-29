from __future__ import annotations

import argparse
import asyncio
import json
import time
from pathlib import Path
from typing import Any

from agent.composer import compose_markdown
from agent.llm_composer import maybe_compose_with_llm, settings_with_llm_overrides
from agent.planner import build_plan, parse_intent
from agent.verifier import unique_citations, verify_evidence
from shared.config import load_settings
from shared.mcp_client import StdioMCPClient
from shared.schemas import BriefResult


SERVER_MODULES = {
    "news": "servers.mining_news_mcp.server",
    "pdf": "servers.mineral_pdf_mcp.server",
    "price": "servers.lme_price_mcp.server",
    "risk": "servers.mining_risk_mcp.server",
}


async def _timed(label: str, coro: Any, report: dict[str, Any]) -> Any:
    started = time.perf_counter()
    try:
        result = await coro
        report[label] = {"ok": True, "latency_ms": round((time.perf_counter() - started) * 1000, 2)}
        return result
    except Exception as exc:  # noqa: BLE001 - degraded mode should capture all tool errors
        report[label] = {
            "ok": False,
            "latency_ms": round((time.perf_counter() - started) * 1000, 2),
            "error": str(exc),
        }
        return exc


async def run_daily_brief(user_query: str, llm_overrides: dict[str, Any] | None = None) -> BriefResult:
    started = time.perf_counter()
    intent = parse_intent(user_query)
    settings = settings_with_llm_overrides(load_settings(), llm_overrides)
    plan = build_plan(intent)
    report: dict[str, Any] = {
        "tools": {},
        "topic": intent.topic,
        "mode": "offline-fixture" if settings.offline else "live-first",
        "plan": {
            "news_query": plan.news_query,
            "news_days": plan.news_days,
            "pdf_url": plan.pdf_url,
            "commodities": plan.commodities,
        },
        "mcp_contract": {
            "agent_client": "agent.daily_brief_agent",
            "servers": [
                {
                    "name": "mining-news-mcp",
                    "module": SERVER_MODULES["news"],
                    "tools": ["search(query, days)", "fetch_article(url)"],
                },
                {
                    "name": "mineral-pdf-mcp",
                    "module": SERVER_MODULES["pdf"],
                    "tools": ["extract_resources(pdf_url)"],
                },
                {
                    "name": "lme-price-mcp",
                    "module": SERVER_MODULES["price"],
                    "tools": ["get_price(commodity, date)", "get_trend(commodity, days)"],
                },
                {
                    "name": "mining-risk-mcp",
                    "module": SERVER_MODULES["risk"],
                    "tools": ["assess_risks(topic, news, resources, prices)"],
                },
            ],
        },
    }
    tool_errors: list[str] = []
    server_env = {"MINING_AGENT_OFFLINE": "true" if settings.offline else "false"}

    async with (
        StdioMCPClient(SERVER_MODULES["news"], "news", env=server_env) as news_client,
        StdioMCPClient(SERVER_MODULES["pdf"], "pdf", env=server_env) as pdf_client,
        StdioMCPClient(SERVER_MODULES["price"], "price", env=server_env) as price_client,
    ):
        news_task = _timed(
            "news.search",
            news_client.call_tool("search", {"query": plan.news_query, "days": plan.news_days}),
            report["tools"],
        )
        pdf_task = _timed(
            "pdf.extract_resources",
            pdf_client.call_tool("extract_resources", {"pdf_url": plan.pdf_url}),
            report["tools"],
        )
        price_tasks = [
            _timed(
                f"price.get_trend.{commodity}",
                price_client.call_tool("get_trend", {"commodity": commodity, "days": 7}),
                report["tools"],
            )
            for commodity in plan.commodities
        ]

        gathered = await asyncio.gather(news_task, pdf_task, *price_tasks)

    news_hits = gathered[0] if not isinstance(gathered[0], Exception) else []
    resources = gathered[1] if not isinstance(gathered[1], Exception) else {"resources": [], "warnings": []}
    price_trends = [item for item in gathered[2:] if not isinstance(item, Exception)]

    for label, item in zip(["news", "pdf", *plan.commodities], gathered):
        if isinstance(item, Exception):
            tool_errors.append(f"{label} tool failed: {item}")

    articles: list[dict[str, Any]] = []
    if news_hits:
        async with StdioMCPClient(SERVER_MODULES["news"], "news", env=server_env) as news_client:
            article_results = await asyncio.gather(
                *[
                    _timed(
                        f"news.fetch_article.{idx}",
                        news_client.call_tool("fetch_article", {"url": hit["url"]}),
                        report["tools"],
                    )
                    for idx, hit in enumerate(news_hits[: plan.article_limit], start=1)
                ]
            )
            articles = [item for item in article_results if not isinstance(item, Exception)]

    risk_assessment: dict[str, Any] = {"risks": [], "citations": [], "trace": []}
    async with StdioMCPClient(SERVER_MODULES["risk"], "risk", env=server_env) as risk_client:
        risk_result = await _timed(
            "risk.assess_risks",
            risk_client.call_tool(
                "assess_risks",
                {
                    "topic": intent.topic,
                    "news": news_hits,
                    "resources": resources,
                    "prices": price_trends,
                },
            ),
            report["tools"],
        )
        if isinstance(risk_result, Exception):
            tool_errors.append(f"risk tool failed: {risk_result}")
        else:
            risk_assessment = risk_result

    news_citations = [
        {
            "id": hit["citation_id"],
            "title": hit["title"],
            "url": hit["url"],
            "source": hit["source"],
            "published_at": hit.get("published_at"),
            "page": None,
            "fetched_at": hit.get("fetched_at"),
        }
        for hit in news_hits[: plan.article_limit]
    ]
    citations = unique_citations(news_citations, resources, price_trends, risk_assessment)
    draft_markdown = compose_markdown(
        topic=intent.topic,
        news_hits=news_hits,
        articles=articles,
        resources=resources,
        price_trends=price_trends,
        risk_assessment=risk_assessment,
        citations=citations,
        degraded_notes=tool_errors,
    )
    markdown, llm_status = maybe_compose_with_llm(
        draft_markdown=draft_markdown,
        evidence={
            "topic": intent.topic,
            "news": news_hits[: plan.article_limit],
            "articles": articles,
            "resources": resources,
            "prices": price_trends,
            "risks": risk_assessment,
            "citations": citations,
            "warnings": tool_errors,
        },
        settings=settings,
    )
    warnings = verify_evidence(markdown, citations, resources, tool_errors)
    report["total_latency_ms"] = round((time.perf_counter() - started) * 1000, 2)
    report["citation_count"] = len(citations)
    report["warning_count"] = len(warnings)
    report["source_breakdown"] = source_breakdown(citations)
    report["crawl_trace"] = crawl_trace(news_hits, articles, resources, price_trends, risk_assessment)
    report["llm"] = llm_status

    return BriefResult(
        topic=intent.topic,
        markdown=markdown,
        news=news_hits,
        resources=resources,
        prices=price_trends,
        citations=citations,
        risks=risk_assessment,
        warnings=warnings,
        run_report=report,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a mining rights daily brief.")
    parser.add_argument("query", help="Natural-language brief request.")
    parser.add_argument("--offline", action="store_true", help="Use fixture-backed deterministic mode.")
    parser.add_argument("--output", help="Write Markdown brief to this path.")
    parser.add_argument("--json-output", help="Write structured JSON result to this path.")
    parser.add_argument("--run-report", default="run_report.json", help="Write run telemetry JSON.")
    parser.add_argument("--llm-enabled", action="store_true", help="Enable optional LLM composition.")
    parser.add_argument("--llm-disabled", action="store_true", help="Disable optional LLM composition.")
    parser.add_argument("--llm-model", help="OpenAI-compatible model name.")
    parser.add_argument("--llm-base-url", help="OpenAI-compatible API base URL, for example https://api.openai.com/v1.")
    parser.add_argument("--llm-api-key", help="API key for the selected OpenAI-compatible endpoint.")
    return parser.parse_args()


def source_breakdown(citations: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for citation in citations:
        source = str(citation.get("source", "unknown"))
        bucket = "live" if source.startswith("live:") else "fallback"
        counts[bucket] = counts.get(bucket, 0) + 1
        if "rss" in source or "html" in source or "company-page" in source:
            key = "news"
        elif "pdf" in source or "technical-report" in source:
            key = "pdf"
        elif "price" in source or "yahoo" in source:
            key = "price"
        else:
            key = "other"
        counts[key] = counts.get(key, 0) + 1
    return counts


def crawl_trace(
    news_hits: list[dict[str, Any]],
    articles: list[dict[str, Any]],
    resources: dict[str, Any],
    price_trends: list[dict[str, Any]],
    risk_assessment: dict[str, Any],
) -> list[dict[str, Any]]:
    trace: list[dict[str, Any]] = []
    article_by_url = {article.get("url"): article for article in articles}
    for hit in news_hits[:5]:
        matching_article = article_by_url.get(hit.get("url"), {})
        published_at = matching_article.get("published_at") or hit.get("published_at")
        trace.append(
            {
                "tool": "mining-news-mcp.search",
                "source": hit.get("source"),
                "url": hit.get("url"),
                "title": hit.get("title"),
                "published_at": published_at,
                "fetched_at": hit.get("fetched_at"),
                "status": "ok" if str(hit.get("source", "")).startswith("live:") else "fallback",
            }
        )
    for article in articles:
        matching_hit = next((hit for hit in news_hits if hit.get("url") == article.get("url")), {})
        trace.append(
            {
                "tool": "mining-news-mcp.fetch_article",
                "source": article.get("source"),
                "url": article.get("url"),
                "title": article.get("title"),
                "published_at": article.get("published_at") or matching_hit.get("published_at"),
                "fetched_at": article.get("fetched_at")
                or (article.get("citations") or [{}])[0].get("fetched_at"),
                "status": "ok"
                if str(article.get("source", "")).startswith("live:")
                else "fallback",
            }
        )
    trace.extend(resources.get("trace", []))
    for trend in price_trends:
        trace.extend(trend.get("trace", []))
    trace.extend(risk_assessment.get("trace", []))
    return sorted(trace, key=lambda item: item.get("fetched_at") or "")


def main() -> None:
    args = parse_args()
    if args.offline:
        import os

        os.environ["MINING_AGENT_OFFLINE"] = "true"
    llm_overrides = {
        key: value
        for key, value in {
            "enabled": False if args.llm_disabled else True if args.llm_enabled else None,
            "model": args.llm_model,
            "base_url": args.llm_base_url,
            "api_key": args.llm_api_key,
        }.items()
        if value is not None
    }
    result = asyncio.run(run_daily_brief(args.query, llm_overrides=llm_overrides or None))
    print(result.markdown)

    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(result.markdown, encoding="utf-8")
    if args.json_output:
        payload = {
            "topic": result.topic,
            "news": result.news,
            "resources": result.resources,
            "prices": result.prices,
            "risks": result.risks,
            "citations": result.citations,
            "warnings": result.warnings,
            "run_report": result.run_report,
            "evidence_summary": {
                "news_count": len(result.news),
                "resource_count": len(result.resources.get("resources", [])),
                "price_series_count": len(result.prices),
                "live_source_count": sum(
                    1
                    for citation in result.citations
                    if str(citation.get("source", "")).startswith("live:")
                ),
                "source_breakdown": result.run_report.get("source_breakdown", {}),
            },
        }
        Path(args.json_output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json_output).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    Path(args.run_report).write_text(
        json.dumps(result.run_report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
