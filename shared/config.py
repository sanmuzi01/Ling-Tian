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
    offline: bool = env_bool("MINING_AGENT_OFFLINE", True)
    strict_citations: bool = env_bool("MINING_AGENT_STRICT_CITATIONS", True)
    timeout_seconds: float = float(os.getenv("MINING_AGENT_TIMEOUT_SECONDS", "30"))


def load_settings() -> Settings:
    return Settings()

