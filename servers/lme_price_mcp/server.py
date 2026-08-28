from __future__ import annotations

from servers.lme_price_mcp.providers import CommodityPriceProvider
from shared.config import load_settings
from shared.mcp_stdio import MCPServer, run_server


settings = load_settings()
provider = CommodityPriceProvider(offline=settings.offline)
server = MCPServer("lme-price-mcp")


@server.tool(
    name="get_price",
    description="Get a commodity price point for a date.",
    input_schema={
        "type": "object",
        "properties": {
            "commodity": {"type": "string"},
            "date": {"type": "string", "description": "YYYY-MM-DD"},
        },
        "required": ["commodity", "date"],
    },
)
def get_price(commodity: str, date: str) -> dict:
    return provider.get_price(commodity, date)


@server.tool(
    name="get_trend",
    description="Get recent commodity price trend, change percentage, and volatility.",
    input_schema={
        "type": "object",
        "properties": {
            "commodity": {"type": "string"},
            "days": {"type": "integer", "minimum": 2, "maximum": 90, "default": 7},
        },
        "required": ["commodity"],
    },
)
def get_trend(commodity: str, days: int = 7) -> dict:
    return provider.get_trend(commodity, days)


if __name__ == "__main__":
    run_server(server)

