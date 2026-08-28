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
    citations: list[dict[str, Any]],
    degraded_notes: list[str],
) -> str:
    lines: list[str] = [
        f"# {topic} 今日矿权简报",
        "",
        "## 1. 执行摘要",
    ]

    lithium = next((trend for trend in price_trends if trend["commodity"] == "lithium"), None)
    if lithium:
        lines.append(
            f"Pilbara 相关锂矿资产的短期关注点集中在发运恢复、"
            f"西澳 royalty 政策评估和锂价走势。锂价近 7 日"
            f"{'下跌' if lithium['trend'] == 'down' else '上涨' if lithium['trend'] == 'up' else '基本持平'}"
            f" {abs(lithium['change_pct'])}% [S5]。"
        )
    else:
        lines.append("本次简报未取得锂价趋势，需结合外部价格源复核。")

    lines.extend(["", "## 2. 新闻动态"])
    for hit in news_hits[:3]:
        lines.append(
            f"- {hit['title']}：{hit['snippet']} [{hit['citation_id']}]"
        )

    lines.extend(["", "## 3. 资源量 / 储量信息"])
    if resources.get("resources"):
        lines.append("| 项目 | 类别 | 矿石量 Mt | 品位 | 金属量 | 置信度 | 来源 |")
        lines.append("|---|---:|---:|---:|---:|---:|---|")
        for item in resources["resources"]:
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
                f"| {item['project']} | {item['category']} | "
                f"{item.get('ore_tonnage_mt', 'N/A')} | {grade} | {metal} | "
                f"{item['confidence']:.2f} | [{item['citation_id']}] |"
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
    lines.append("- 政策风险：西澳 royalty 和本地加工政策变化可能影响项目现金流时点 [S2]。")
    lines.append("- 市场风险：中国转化厂补库偏谨慎，可能压制短期 spodumene 价格弹性 [S3]。")
    lines.append("- 数据风险：资源量来自技术报告抽取结果，低置信度或 fixture 数据必须人工复核 [S4]。")

    lines.extend(["", "## 6. 数据完整性说明"])
    if degraded_notes or resources.get("warnings"):
        for note in degraded_notes + resources.get("warnings", []):
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

