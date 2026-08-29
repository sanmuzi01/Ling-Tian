from __future__ import annotations

from typing import Any

from servers.mining_risk_mcp.analyzer import MiningRiskAnalyzer
from shared.mcp_stdio import MCPServer, run_server


analyzer = MiningRiskAnalyzer()
server = MCPServer("mining-risk-mcp")


@server.tool(
    name="assess_risks",
    description="Assess market, resource, operating, and policy risks from collected mining evidence.",
    input_schema={
        "type": "object",
        "properties": {
            "topic": {"type": "string"},
            "news": {"type": "array", "items": {"type": "object"}},
            "resources": {"type": "object"},
            "prices": {"type": "array", "items": {"type": "object"}},
        },
        "required": ["topic", "news", "resources", "prices"],
    },
)
def assess_risks(
    topic: str,
    news: list[dict[str, Any]],
    resources: dict[str, Any],
    prices: list[dict[str, Any]],
) -> dict[str, Any]:
    return analyzer.assess_risks(topic=topic, news=news, resources=resources, prices=prices)


if __name__ == "__main__":
    run_server(server)
