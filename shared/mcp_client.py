from __future__ import annotations

import asyncio
import json
import sys
from dataclasses import dataclass, field
from typing import Any


@dataclass
class StdioMCPClient:
    module: str
    name: str
    proc: asyncio.subprocess.Process | None = None
    next_id: int = 1
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def __aenter__(self) -> "StdioMCPClient":
        self.proc = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            self.module,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await self.request("initialize", {"clientInfo": {"name": "daily-brief-agent"}})
        await self.notify("notifications/initialized", {})
        return self

    async def __aexit__(self, *_: object) -> None:
        if self.proc and self.proc.returncode is None:
            self.proc.terminate()
            try:
                await asyncio.wait_for(self.proc.wait(), timeout=2)
            except asyncio.TimeoutError:
                self.proc.kill()

    async def notify(self, method: str, params: dict[str, Any]) -> None:
        assert self.proc and self.proc.stdin
        payload = {"jsonrpc": "2.0", "method": method, "params": params}
        self.proc.stdin.write((json.dumps(payload) + "\n").encode("utf-8"))
        await self.proc.stdin.drain()

    async def request(self, method: str, params: dict[str, Any] | None = None) -> Any:
        async with self._lock:
            assert self.proc and self.proc.stdin and self.proc.stdout
            request_id = self.next_id
            self.next_id += 1
            payload = {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {}}
            self.proc.stdin.write((json.dumps(payload) + "\n").encode("utf-8"))
            await self.proc.stdin.drain()
            line = await self.proc.stdout.readline()
            if not line:
                raise RuntimeError(f"{self.name} closed stdout")
            response = json.loads(line.decode("utf-8"))
            if "error" in response:
                raise RuntimeError(response["error"]["message"])
            return response["result"]

    async def list_tools(self) -> list[dict[str, Any]]:
        result = await self.request("tools/list")
        return result["tools"]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        result = await self.request("tools/call", {"name": name, "arguments": arguments})
        text = result["content"][0]["text"]
        return json.loads(text)
