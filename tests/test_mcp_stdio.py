from __future__ import annotations

import asyncio
import unittest

from shared.mcp_client import StdioMCPClient


class MCPStdioTests(unittest.TestCase):
    def test_server_lists_tools(self) -> None:
        async def run() -> list[dict]:
            async with StdioMCPClient("servers.mining_news_mcp.server", "news") as client:
                return await client.list_tools()

        tools = asyncio.run(run())
        self.assertEqual({"search", "fetch_article"}, {tool["name"] for tool in tools})


if __name__ == "__main__":
    unittest.main()

