from __future__ import annotations

from servers.mineral_pdf_mcp.extractor import MineralPdfExtractor
from shared.config import load_settings
from shared.mcp_stdio import MCPServer, run_server


settings = load_settings()
extractor = MineralPdfExtractor(offline=settings.offline)
server = MCPServer("mineral-pdf-mcp")


@server.tool(
    name="extract_resources",
    description="Extract Indicated/Inferred mineral resources from a technical-report PDF URL.",
    input_schema={
        "type": "object",
        "properties": {"pdf_url": {"type": "string"}},
        "required": ["pdf_url"],
    },
)
def extract_resources(pdf_url: str) -> dict:
    return extractor.extract_resources(pdf_url)


if __name__ == "__main__":
    run_server(server)

