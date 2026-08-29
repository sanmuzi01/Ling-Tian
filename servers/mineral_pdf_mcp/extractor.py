from __future__ import annotations

import json
import re
import tempfile
from pathlib import Path

from shared.cache import JsonCache, stable_key
from shared.config import FIXTURE_DIR
from shared.http import fetch_bytes, utc_now


class MineralPdfExtractor:
    def __init__(self, offline: bool = True) -> None:
        self.offline = offline
        self.cache = JsonCache("pdf")

    def extract_resources(self, pdf_url: str) -> dict:
        cache_key = stable_key("resources:v5", pdf_url, str(self.offline))
        cached = self.cache.get(cache_key)
        if cached:
            return cached

        if not self._safe_url(pdf_url):
            raise ValueError("Only http(s) or fixture URLs are accepted.")

        if not self.offline and pdf_url.startswith(("http://", "https://")):
            try:
                result = self._extract_live_pdf(pdf_url)
                self.cache.set(cache_key, result)
                return result
            except Exception as exc:  # noqa: BLE001 - return reliable degraded output
                fixture = self._fixture(pdf_url)
                fixture["status"] = "partial"
                fixture["warnings"].append(f"Live PDF extraction failed and fixture fallback was used: {exc}")
                self.cache.set(cache_key, fixture)
                return fixture

        fixture = self._fixture(pdf_url)
        self.cache.set(cache_key, fixture)
        return fixture

    def _fixture(self, pdf_url: str) -> dict:
        fetched_at = utc_now()
        fixture = json.loads(
            (FIXTURE_DIR / "pdf" / "pilbara_resources.json").read_text(encoding="utf-8")
        )
        fixture["trace"] = [
            {
                "tool": "mineral-pdf-mcp.extract_resources",
                "source": "fixture:technical-report",
                "url": fixture.get("pdf_url", pdf_url),
                "published_at": (fixture.get("citations") or [{}])[0].get("published_at"),
                "fetched_at": fetched_at,
                "status": "fallback",
            }
        ]
        if pdf_url != "fixture://pilbara-ni-43101":
            fixture = {
                **fixture,
                "pdf_url": pdf_url,
                "status": "partial",
                "warnings": fixture["warnings"]
                + ["Live PDF parsing adapter is not enabled; returned closest fixture shape."],
            }
        return fixture

    def _extract_live_pdf(self, pdf_url: str) -> dict:
        import pdfplumber

        fetched_at = utc_now()
        body, content_type = fetch_bytes(pdf_url, timeout=30)
        if b"%PDF" not in body[:1024] and (content_type or "").lower().find("pdf") < 0:
            raise ValueError("URL did not return a PDF response.")

        records: list[dict] = []
        warnings: list[str] = []
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "report.pdf"
            path.write_bytes(body)
            with pdfplumber.open(path) as pdf:
                candidate_pages = []
                for idx, page in enumerate(pdf.pages, start=1):
                    text = page.extract_text() or ""
                    lowered = text.lower()
                    if "indicated" in lowered and "inferred" in lowered and (
                        "mineral resource" in lowered or "resources" in lowered
                    ):
                        candidate_pages.append((idx, text))
                    if len(candidate_pages) >= 8:
                        break

                for page_num, text in candidate_pages:
                    records.extend(self._parse_resource_text(text, page_num, pdf_url))

        if not records:
            return {
                "pdf_url": pdf_url,
                "status": "abstain",
                "project": "Unknown",
                "resources": [],
                "warnings": ["No high-confidence Indicated/Inferred resource table was detected."],
                "citations": [
                    {
                        "id": "S21",
                        "title": "Live technical report PDF",
                        "url": pdf_url,
                        "source": "live:pdf",
                        "published_at": "2026-08-23T00:00:00Z",
                        "page": None,
                        "fetched_at": fetched_at,
                    }
                ],
                "trace": [
                    {
                        "tool": "mineral-pdf-mcp.extract_resources",
                        "source": "live:pdf",
                        "url": pdf_url,
                        "published_at": "2026-08-23T00:00:00Z",
                        "fetched_at": fetched_at,
                        "status": "abstain",
                    }
                ],
            }

        return {
            "pdf_url": pdf_url,
            "status": "ok" if all(item["confidence"] >= 0.8 for item in records) else "partial",
            "project": records[0]["project"],
            "resources": records,
            "warnings": warnings,
            "citations": [
                {
                    "id": "S21",
                    "title": "Live technical report PDF resource extraction",
                    "url": pdf_url,
                    "source": "live:pdf",
                    "published_at": "2026-08-23T00:00:00Z",
                    "page": records[0].get("page"),
                    "fetched_at": fetched_at,
                }
            ],
            "trace": [
                {
                    "tool": "mineral-pdf-mcp.extract_resources",
                    "source": "live:pdf",
                    "url": pdf_url,
                    "published_at": "2026-08-23T00:00:00Z",
                    "fetched_at": fetched_at,
                    "status": "ok",
                }
            ],
        }

    def _parse_resource_text(self, text: str, page_num: int, pdf_url: str) -> list[dict]:
        del pdf_url
        project = "Live PDF technical report"
        if "Pilgangoora" in text:
            project = "Pilgangoora Lithium Operation"
        rows: list[dict] = []
        for category in ("Indicated", "Inferred"):
            pattern = rf"{category}\s+([\d,.]+)\s+([\d.]+)"
            for match in re.finditer(pattern, text, flags=re.I):
                tonnage = _to_float(match.group(1))
                grade = _to_float(match.group(2))
                if tonnage is None or grade is None:
                    continue
                rows.append(
                    {
                        "project": project,
                        "category": category,
                        "ore_tonnage_mt": tonnage,
                        "grade": grade,
                        "grade_unit": "% Li2O / reported grade",
                        "contained_metal": round(tonnage * grade / 100, 3),
                        "contained_metal_unit": "Mt contained grade units",
                        "page": page_num,
                        "confidence": 0.72,
                        "citation_id": "S21",
                    }
                )
                break
        return rows

    @staticmethod
    def _safe_url(url: str) -> bool:
        return url.startswith("https://") or url.startswith("http://") or url.startswith("fixture://")


def _to_float(value: str) -> float | None:
    try:
        return float(value.replace(",", ""))
    except ValueError:
        return None
