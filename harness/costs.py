"""Per-call token + USD cost tracker with a hard budget abort.

Prices come from config.yaml (USD per 1e6 tokens) and are used verbatim. Verify
provider pricing before reporting any dollar figure.
"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Dict


class BudgetExceeded(RuntimeError):
    pass


class CostTracker:
    def __init__(self, pricing: Dict[str, Dict[str, float]], budget_usd: float,
                 spend_log_path: str | Path):
        self.pricing = pricing
        self.budget_usd = float(budget_usd)
        self.spend_log_path = Path(spend_log_path)
        self.spend_log_path.parent.mkdir(parents=True, exist_ok=True)
        self._total = 0.0
        self._calls = 0
        self._lock = threading.Lock()

    def _unit_price(self, model: str) -> Dict[str, float]:
        if model not in self.pricing:
            raise KeyError(
                f"No pricing entry for model '{model}'. Add it to config.yaml:pricing."
            )
        return self.pricing[model]

    def cost_of(self, model: str, input_tokens: int, output_tokens: int) -> float:
        p = self._unit_price(model)
        return (input_tokens * p["input"] + output_tokens * p["output"]) / 1_000_000.0

    def record(self, model: str, input_tokens: int, output_tokens: int,
               meta: Dict | None = None) -> float:
        cost = self.cost_of(model, input_tokens, output_tokens)
        with self._lock:
            self._total += cost
            self._calls += 1
            total = self._total
            calls = self._calls
        rec = {
            "ts": time.time(), "model": model,
            "input_tokens": input_tokens, "output_tokens": output_tokens,
            "call_usd": round(cost, 6), "running_usd": round(total, 6),
            "call_index": calls,
        }
        if meta:
            rec["meta"] = meta
        with self._lock:
            with self.spend_log_path.open("a") as f:
                f.write(json.dumps(rec) + "\n")
        if total > self.budget_usd:
            raise BudgetExceeded(
                f"Budget ${self.budget_usd:.2f} exceeded: running ${total:.4f} "
                f"after {calls} calls. Aborting (this is by design)."
            )
        return cost

    @property
    def total_usd(self) -> float:
        with self._lock:
            return self._total

    @property
    def num_calls(self) -> int:
        with self._lock:
            return self._calls
