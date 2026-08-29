from __future__ import annotations

import asyncio
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.daily_brief_agent import run_daily_brief  # noqa: E402


FRONTEND_DIR = ROOT / "frontend"
DIST_DIR = FRONTEND_DIR / "dist"


class Handler(BaseHTTPRequestHandler):
    server_version = "MiningAgentFrontend/0.1"

    def do_GET(self) -> None:  # noqa: N802
        path = unquote(self.path.split("?", 1)[0])
        if path == "/":
            path = "/index.html"
        static_root = DIST_DIR if DIST_DIR.exists() else FRONTEND_DIR
        file_path = (static_root / path.lstrip("/")).resolve()
        if not str(file_path).startswith(str(static_root.resolve())):
            self.send_error(403)
            return
        if not file_path.exists() or not file_path.is_file():
            if DIST_DIR.exists():
                file_path = DIST_DIR / "index.html"
            else:
                self.send_error(404)
                return
        if not file_path.exists() or not file_path.is_file():
            self.send_error(404)
            return
        content_type = {
            ".html": "text/html; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".js": "application/javascript; charset=utf-8",
        }.get(file_path.suffix, "application/octet-stream")
        self._send(200, file_path.read_bytes(), content_type)

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/api/run":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", "0"))
        try:
            body = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            query = body.get("query") or "给我生成一份关于 Pilbara 锂矿的今日简报"
            llm_config = body.get("llm") if isinstance(body.get("llm"), dict) else None
            result = asyncio.run(run_daily_brief(query, llm_overrides=llm_config))
            payload = {
                "topic": result.topic,
                "markdown": result.markdown,
                "news": result.news,
                "resources": result.resources,
                "prices": result.prices,
                "risks": result.risks,
                "citations": result.citations,
                "warnings": result.warnings,
                "run_report": result.run_report,
                "evidence_summary": {
                    "news_count": len(result.news),
                    "resource_count": len(result.resources.get("resources", [])),
                    "price_series_count": len(result.prices),
                    "live_source_count": sum(
                        1 for citation in result.citations if str(citation.get("source", "")).startswith("live:")
                    ),
                    "source_breakdown": result.run_report.get("source_breakdown", {}),
                },
            }
            self._send_json(200, payload)
        except Exception as exc:  # noqa: BLE001 - UI should show failed run feedback
            self._send_json(500, {"error": str(exc)})

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def log_message(self, fmt: str, *args: object) -> None:
        sys.stderr.write("[frontend] " + fmt % args + "\n")

    def _send_json(self, status: int, payload: dict) -> None:
        self._send(
            status,
            json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"),
            "application/json; charset=utf-8",
        )

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    host = "127.0.0.1"
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"Agent API/static server: http://{host}:{port}", flush=True)
    if not DIST_DIR.exists():
        print("Vue dev mode: run `npm install` then `npm run dev` in frontend/.", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
