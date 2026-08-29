from __future__ import annotations

from typing import Any


def _fmt_money(value: float) -> str:
    return f"{value:,.0f}"


def compose_markdown(
    topic: str,
    news_hits: list[dict[str, Any]],
    articles: list[dict[str, Any]],
    resources: dict[str, Any],
    price_trends: list[dict[str, Any]],
    risk_assessment: dict[str, Any],
    citations: list[dict[str, Any]],
    degraded_notes: list[str],
) -> str:
    focused_news = news_hits[:3]
    resource_records = resources.get("resources", [])
    indicated = [item for item in resource_records if item.get("category") == "Indicated"]
    inferred = [item for item in resource_records if item.get("category") == "Inferred"]
    total_indicated = sum(float(item.get("ore_tonnage_mt") or 0) for item in indicated)
    total_inferred = sum(float(item.get("ore_tonnage_mt") or 0) for item in inferred)

    lines: list[str] = [
        f"# {topic} 今日矿权简报",
        "",
        "## 1. 执行摘要",
    ]

    lithium = next((trend for trend in price_trends if trend["commodity"] == "lithium"), None)
    if lithium:
        lithium_citation = lithium["citations"][0]["id"]
        resource_citation = resource_records[0]["citation_id"] if resource_records else "S21"
        lines.append(
            f"本次 Agent 对 {topic} 做了新闻、技术报告 PDF 和行情三路采集。"
            f"资源量抽取显示 Indicated 合计约 {total_indicated:.2f} Mt，"
            f"Inferred 合计约 {total_inferred:.2f} Mt，PDF 抽取状态为 "
            f"{resources.get('status', 'unknown')} [{resource_citation}]。"
            f"锂相关公开行情代理近 7 日"
            f"{'下跌' if lithium['trend'] == 'down' else '上涨' if lithium['trend'] == 'up' else '基本持平'}"
            f" {abs(lithium['change_pct'])}% [{lithium_citation}]。"
        )
    else:
        lines.append("本次简报未取得锂价趋势，需结合外部价格源复核。")

    lines.extend(["", "## 2. 资产动态与新闻证据"])
    if not focused_news:
        lines.append("- 未抓到足够相关的实时新闻，建议扩大关键词或检查目标源可访问性。")
    for hit in focused_news:
        lines.append(
            f"- {hit['title']}：{hit['snippet']} "
            f"(source={hit['source']}, relevance={hit['score']:.2f}) [{hit['citation_id']}]"
        )

    lines.extend(["", "## 3. 资源量 / 储量信息"])
    if resource_records:
        for item in resource_records:
            grade = (
                f"{item['grade']} {item['grade_unit']}"
                if item.get("grade") is not None
                else "N/A"
            )
            metal = (
                f"{item['contained_metal']} {item['contained_metal_unit']}"
                if item.get("contained_metal") is not None
                else "N/A"
            )
            lines.append(
                f"- {item['project']} / {item['category']}：矿石量 "
                f"{item.get('ore_tonnage_mt', 'N/A')} Mt，品位 {grade}，"
                f"金属量 {metal}，抽取置信度 {item['confidence']:.2f} "
                f"[{item['citation_id']}]."
            )
    else:
        lines.append("未能高置信度抽取资源量表格，建议人工复核。")

    lines.extend(["", "## 4. 价格走势"])
    for trend in price_trends:
        start = trend["points"][0]
        end = trend["points"][-1]
        direction = "上涨" if trend["trend"] == "up" else "下跌" if trend["trend"] == "down" else "持平"
        citation = trend["citations"][0]["id"]
        lines.append(
            f"- {trend['commodity']}: {start['date']} 至 {end['date']} 从 "
            f"{_fmt_money(start['price'])} {trend['currency']}/{trend['unit']} 到 "
            f"{_fmt_money(end['price'])}，{direction} {abs(trend['change_pct'])}% "
            f"，波动率 {trend['volatility']} [{citation}]。"
        )

    lines.extend(["", "## 5. 风险提示"])
    risk_items = risk_assessment.get("risks", [])
    if risk_items:
        lines.append(
            f"- 综合风险等级：{risk_assessment.get('risk_level', 'unknown')}，"
            f"评分 {risk_assessment.get('risk_score', 'N/A')}。"
        )
        for item in risk_items:
            lines.append(
                f"- {item['category']}：{item['summary']} "
                f"(level={item['level']}, score={item['score']}) [{item['citation_id']}]。"
            )
    else:
        policy_citation = focused_news[1]["citation_id"] if len(focused_news) > 1 else focused_news[0]["citation_id"] if focused_news else "S31"
        market_citation = focused_news[2]["citation_id"] if len(focused_news) > 2 else policy_citation
        resource_citation = (
            resources["resources"][0]["citation_id"] if resources.get("resources") else "S21"
        )
        lines.append(f"- 政策风险：政策、许可、royalty 或本地加工规则变化可能影响项目现金流时点 [{policy_citation}]。")
        lines.append(f"- 市场风险：电池材料需求、补库节奏和相关金属价格波动会影响 spodumene 定价弹性 [{market_citation}]。")
        lines.append(f"- 数据风险：资源量来自技术报告抽取结果，低置信度字段必须人工复核 [{resource_citation}]。")

    lines.extend(["", "## 6. 数据完整性说明"])
    quality_notes = list(degraded_notes) + list(resources.get("warnings", []))
    low_confidence = [
        item for item in resources.get("resources", []) if item.get("confidence", 1.0) < 0.8
    ]
    if resources.get("status") in {"partial", "abstain"}:
        quality_notes.append(f"PDF 资源量抽取状态为 {resources.get('status')}，建议人工复核。")
    if low_confidence:
        quality_notes.append(f"发现 {len(low_confidence)} 条资源量记录置信度低于 0.80。")
    if quality_notes:
        for note in quality_notes:
            lines.append(f"- {note}")
    else:
        lines.append("- 本次运行未触发降级。")

    lines.extend(["", "## 7. 引用来源"])
    for citation in citations:
        page = f", p.{citation['page']}" if citation.get("page") else ""
        lines.append(
            f"- [{citation['id']}] {citation['title']} ({citation['source']}{page}) - {citation['url']}"
        )

    return "\n".join(lines) + "\n"
