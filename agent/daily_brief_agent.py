from __future__ import annotations

import argparse
import asyncio
import json
import time
from pathlib import Path
from typing import Any

from agent.composer import compose_markdown
from agent.planner import build_plan, parse_intent
from agent.verifier import unique_citations, verify_evidence
from shared.mcp_client import StdioMCPClient
from shared.schemas import BriefResult


SERVER_MODULES = {
    "news": "servers.mining_news_mcp.server",
    "pdf": "servers.mineral_pdf_mcp.server",
    "price": "servers.lme_price_mcp.server",
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


async def run_daily_brief(user_query: str) -> BriefResult:
    started = time.perf_counter()
    intent = parse_intent(user_query)
    plan = build_plan(intent)
    report: dict[str, Any] = {"tools": {}, "topic": intent.topic}
    tool_errors: list[str] = []

    async with (
        StdioMCPClient(SERVER_MODULES["news"], "news") as news_client,
        StdioMCPClient(SERVER_MODULES["pdf"], "pdf") as pdf_client,
        StdioMCPClient(SERVER_MODULES["price"], "price") as price_client,
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
        async with StdioMCPClient(SERVER_MODULES["news"], "news") as news_client:
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

    citations = unique_citations(articles, resources, price_trends)
    markdown = compose_markdown(
        topic=intent.topic,
        news_hits=news_hits,
        articles=articles,
        resources=resources,
        price_trends=price_trends,
        citations=citations,
        degraded_notes=tool_errors,
    )
    warnings = verify_evidence(markdown, citations, resources, tool_errors)
    report["total_latency_ms"] = round((time.perf_counter() - started) * 1000, 2)
    report["citation_count"] = len(citations)
    report["warning_count"] = len(warnings)

    return BriefResult(
        topic=intent.topic,
        markdown=markdown,
        news=news_hits,
        resources=resources,
        prices=price_trends,
        citations=citations,
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
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = asyncio.run(run_daily_brief(args.query))
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
            "citations": result.citations,
            "warnings": result.warnings,
            "run_report": result.run_report,
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

