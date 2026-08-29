from __future__ import annotations

from typing import Any

from shared.http import utc_now


class MiningRiskAnalyzer:
    def assess_risks(
        self,
        topic: str,
        news: list[dict[str, Any]],
        resources: dict[str, Any],
        prices: list[dict[str, Any]],
    ) -> dict[str, Any]:
        fetched_at = utc_now()
        risks = [
            self._market_risk(news, prices),
            self._resource_risk(resources),
            self._operational_risk(news),
            self._policy_risk(news),
        ]
        score = round(sum(item["score"] for item in risks) / max(len(risks), 1), 2)
        level = "high" if score >= 0.7 else "medium" if score >= 0.4 else "low"
        return {
            "topic": topic,
            "risk_score": score,
            "risk_level": level,
            "risks": risks,
            "citations": self._citations(news, resources, prices),
            "trace": [
                {
                    "tool": "mining-risk-mcp.assess_risks",
                    "source": "agent:derived-risk-model",
                    "url": "mcp://mining-risk-mcp/assess_risks",
                    "title": f"{topic} risk assessment",
                    "published_at": fetched_at,
                    "fetched_at": fetched_at,
                    "status": "ok",
                }
            ],
        }

    def _market_risk(self, news: list[dict[str, Any]], prices: list[dict[str, Any]]) -> dict[str, Any]:
        lithium = next((item for item in prices if item.get("commodity") == "lithium"), None)
        change = abs(float(lithium.get("change_pct", 0))) if lithium else 0.0
        score = min(0.9, 0.35 + change / 20)
        citation_id = lithium.get("citations", [{}])[0].get("id", "S31") if lithium else _news_citation(news, 0)
        return {
            "category": "市场价格",
            "level": _level(score),
            "score": round(score, 2),
            "summary": "锂价代理指标短期波动会影响精矿销售价格、库存重估和项目估值敏感性。",
            "citation_id": citation_id,
        }

    def _resource_risk(self, resources: dict[str, Any]) -> dict[str, Any]:
        status = resources.get("status")
        low_confidence = [
            item for item in resources.get("resources", []) if float(item.get("confidence", 1.0)) < 0.8
        ]
        score = 0.25
        if status in {"partial", "abstain"}:
            score += 0.25
        score += min(0.25, len(low_confidence) * 0.06)
        return {
            "category": "资源量可信度",
            "level": _level(score),
            "score": round(score, 2),
            "summary": "PDF 表格抽取存在低置信度字段时，应在投资或面试演示前人工复核原报告页码。",
            "citation_id": (resources.get("citations") or [{"id": "S21"}])[0].get("id", "S21"),
        }

    def _operational_risk(self, news: list[dict[str, Any]]) -> dict[str, Any]:
        text = " ".join(f"{item.get('title', '')} {item.get('snippet', '')}" for item in news).lower()
        keywords = ("expansion", "production", "operation", "shipments", "guidance")
        score = 0.55 if any(keyword in text for keyword in keywords) else 0.35
        return {
            "category": "运营执行",
            "level": _level(score),
            "score": round(score, 2),
            "summary": "扩产、产量指引和发运节奏变化会影响单位成本摊薄和现金流兑现时间。",
            "citation_id": _news_citation(news, 1),
        }

    def _policy_risk(self, news: list[dict[str, Any]]) -> dict[str, Any]:
        text = " ".join(f"{item.get('title', '')} {item.get('snippet', '')}" for item in news).lower()
        keywords = ("policy", "royalty", "permit", "government", "approval", "regulation")
        score = 0.5 if any(keyword in text for keyword in keywords) else 0.3
        return {
            "category": "政策许可",
            "level": _level(score),
            "score": round(score, 2),
            "summary": "矿权许可、royalty、本地加工或出口规则变化可能改变项目现金流时点。",
            "citation_id": _news_citation(news, 2),
        }

    def _citations(
        self,
        news: list[dict[str, Any]],
        resources: dict[str, Any],
        prices: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        citations: list[dict[str, Any]] = []
        for item in news[:3]:
            citations.append(
                {
                    "id": item.get("citation_id"),
                    "title": item.get("title"),
                    "url": item.get("url"),
                    "source": item.get("source"),
                    "published_at": item.get("published_at"),
                    "fetched_at": item.get("fetched_at"),
                }
            )
        citations.extend(resources.get("citations", []))
        for trend in prices:
            citations.extend(trend.get("citations", []))
        return [item for item in citations if item.get("id")]


def _news_citation(news: list[dict[str, Any]], index: int) -> str:
    if not news:
        return "S31"
    return news[min(index, len(news) - 1)].get("citation_id", "S31")


def _level(score: float) -> str:
    return "high" if score >= 0.7 else "medium" if score >= 0.4 else "low"
