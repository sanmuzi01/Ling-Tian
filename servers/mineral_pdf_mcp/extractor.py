from __future__ import annotations

import json

from shared.cache import JsonCache, stable_key
from shared.config import FIXTURE_DIR


class MineralPdfExtractor:
    def __init__(self, offline: bool = True) -> None:
        self.offline = offline
        self.cache = JsonCache("pdf")

    def extract_resources(self, pdf_url: str) -> dict:
        cache_key = stable_key("resources", pdf_url, str(self.offline))
        cached = self.cache.get(cache_key)
        if cached:
            return cached

        if not self._safe_url(pdf_url):
            raise ValueError("Only http(s) or fixture URLs are accepted.")

        # Offline fixture path is the deterministic interview route. The parser
        # boundary is kept here so a real pdfplumber provider can replace it.
        fixture = json.loads(
            (FIXTURE_DIR / "pdf" / "pilbara_resources.json").read_text(encoding="utf-8")
        )
        if pdf_url != "fixture://pilbara-ni-43101":
            fixture = {
                **fixture,
                "pdf_url": pdf_url,
                "status": "partial",
                "warnings": fixture["warnings"]
                + ["Live PDF parsing adapter is not enabled; returned closest fixture shape."],
            }
        self.cache.set(cache_key, fixture)
        return fixture

    @staticmethod
    def _safe_url(url: str) -> bool:
        return url.startswith("https://") or url.startswith("http://") or url.startswith("fixture://")

