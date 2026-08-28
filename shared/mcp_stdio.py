from __future__ import annotations

import asyncio
import inspect
import json
import sys
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from shared.schemas import to_json


ToolHandler = Callable[..., Any | Awaitable[Any]]


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    input_schema: dict[str, Any]
    handler: ToolHandler


class MCPServer:
    """Small MCP stdio server for the subset needed by this project."""

    def __init__(self, name: str, version: str = "0.1.0") -> None:
        self.name = name
        self.version = version
        self.tools: dict[str, Tool] = {}

    def tool(self, name: str, description: str, input_schema: dict[str, Any]) -> Callable:
        def decorator(func: ToolHandler) -> ToolHandler:
            self.tools[name] = Tool(name, description, input_schema, func)
            return func

        return decorator

    async def handle(self, request: dict[str, Any]) -> dict[str, Any] | None:
        method = request.get("method")
        request_id = request.get("id")

        if method == "notifications/initialized":
            return None

        try:
            if method == "initialize":
                result = {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": self.name, "version": self.version},
                }
            elif method == "tools/list":
                result = {
                    "tools": [
                        {
                            "name": tool.name,
                            "description": tool.description,
                            "inputSchema": tool.input_schema,
                        }
                        for tool in self.tools.values()
                    ]
                }
            elif method == "tools/call":
                params = request.get("params") or {}
                tool_name = params.get("name")
                arguments = params.get("arguments") or {}
                if tool_name not in self.tools:
                    raise ValueError(f"Unknown tool: {tool_name}")
                value = self.tools[tool_name].handler(**arguments)
                if inspect.isawaitable(value):
                    value = await value
                result = {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(to_json(value), ensure_ascii=False, indent=2),
                        }
                    ],
                    "isError": False,
                }
            else:
                raise ValueError(f"Unsupported method: {method}")
            return {"jsonrpc": "2.0", "id": request_id, "result": result}
        except Exception as exc:  # noqa: BLE001 - returned through JSON-RPC error channel
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32000, "message": str(exc)},
            }

    async def run(self) -> None:
        while line := await asyncio.to_thread(sys.stdin.readline):
            if not line.strip():
                continue
            response = await self.handle(json.loads(line))
            if response is not None:
                print(json.dumps(response, ensure_ascii=False), flush=True)


def run_server(server: MCPServer) -> None:
    asyncio.run(server.run())

