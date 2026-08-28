from __future__ import annotations

import asyncio
import sys

from shared.mcp_client import StdioMCPClient


async def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python -m shared.mcp_smoke <server.module>")
    async with StdioMCPClient(sys.argv[1], "smoke") as client:
        for tool in await client.list_tools():
            print(f"{tool['name']}: {tool['description']}")


if __name__ == "__main__":
    asyncio.run(main())

