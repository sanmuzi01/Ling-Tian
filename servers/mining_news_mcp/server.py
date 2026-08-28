from __future__ import annotations

from servers.mining_news_mcp.sources import MiningNewsService
from shared.config import load_settings
from shared.mcp_stdio import MCPServer, run_server


settings = load_settings()
service = MiningNewsService(offline=settings.offline)
server = MCPServer("mining-news-mcp")


@server.tool(
    name="search",
    description="Search recent mining news by query and day window.",
    input_schema={
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "days": {"type": "integer", "minimum": 1, "maximum": 90, "default": 7},
        },
        "required": ["query"],
    },
)
def search(query: str, days: int = 7) -> list[dict]:
    return [hit.__dict__ for hit in service.search(query, days)]


@server.tool(
    name="fetch_article",
    description="Fetch and extract a mining article by URL.",
    input_schema={
        "type": "object",
        "properties": {"url": {"type": "string"}},
        "required": ["url"],
    },
)
def fetch_article(url: str) -> dict:
    article = service.fetch_article(url)
    return {
        **article.__dict__,
        "citations": [citation.__dict__ for citation in article.citations],
    }


if __name__ == "__main__":
    run_server(server)

