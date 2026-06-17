"""Structured logger: one JSONL line per event for full provenance."""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any, Dict


class StructuredLogger:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def log(self, session_id: str, phase: str, event_type: str,
            tokens_so_far: int | None = None, payload: Dict[str, Any] | None = None) -> None:
        rec = {
            "ts": time.time(),
            "session_id": session_id,
            "phase": phase,
            "event_type": event_type,
            "tokens_so_far": tokens_so_far,
            "payload": payload or {},
        }
        line = json.dumps(rec, default=str)
        with self._lock:
            with self.path.open("a") as f:
                f.write(line + "\n")
