from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
FIXTURE_DIR = DATA_DIR / "fixtures"
CACHE_DIR = DATA_DIR / "cache"


def env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    offline: bool = env_bool("MINING_AGENT_OFFLINE", False)
    strict_citations: bool = env_bool("MINING_AGENT_STRICT_CITATIONS", True)
    timeout_seconds: float = float(os.getenv("MINING_AGENT_TIMEOUT_SECONDS", "30"))
    default_pdf_url: str = os.getenv(
        "MINING_AGENT_PDF_URL",
        "https://cdn.financialreports.eu/financialreports/media/filings/65576/2026/RNS/65576_rns_2026-08-23_c3d18a66-1f27-477f-92de-45222c0b4f78.pdf",
    )


def load_settings() -> Settings:
    return Settings()
