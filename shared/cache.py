from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from shared.config import CACHE_DIR


def stable_key(*parts: str) -> str:
    raw = "::".join(parts).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:32]


class JsonCache:
    def __init__(self, namespace: str) -> None:
        self.dir = CACHE_DIR / namespace
        self.dir.mkdir(parents=True, exist_ok=True)

    def path_for(self, key: str) -> Path:
        return self.dir / f"{key}.json"

    def get(self, key: str) -> Any | None:
        path = self.path_for(key)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def set(self, key: str, value: Any) -> None:
        self.path_for(key).write_text(
            json.dumps(value, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

