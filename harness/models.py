"""Provider wrapper. Exact token usage comes from the provider; the `mock` provider
needs no key and no money and exists ONLY to exercise the pipeline end-to-end.

The mock simulates context-rot degradation deterministically (no randomness from the
wall clock) so plotting/stats code can be validated. Mock outputs are NEVER findings.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class ModelResponse:
    text: str
    input_tokens: int
    output_tokens: int
    provider: str
    model: str


def estimate_tokens(text: str) -> int:
    """Offline token estimate. Used only for context construction targets and for the
    mock provider. Real runs log provider-reported token counts, not this estimate."""
    try:
        import tiktoken  # type: ignore
        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except Exception:
        # ~4 chars/token heuristic, the standard rough fallback.
        return max(1, len(text) // 4)


def _messages_text(system: Optional[str], messages: List[Dict[str, str]]) -> str:
    parts = [system or ""]
    for m in messages:
        parts.append(str(m.get("content", "")))
    return "\n".join(parts)


def _stable_unit(*keys) -> float:
    """Deterministic pseudo-random in [0,1) from keys (no time/random)."""
    h = hashlib.sha256("|".join(str(k) for k in keys).encode()).hexdigest()
    return int(h[:8], 16) / 0xFFFFFFFF


class ModelClient:
    def __init__(self, provider: str, model: str):
        self.provider = provider
        self.model = model
        self._client = None
        if provider == "anthropic":
            import anthropic  # noqa
            self._client = anthropic.Anthropic()
        elif provider == "openai":
            from openai import OpenAI  # noqa
            self._client = OpenAI()
        elif provider == "mock":
            self._client = None
        else:
            raise ValueError(f"Unknown provider: {provider}")

    def complete(self, messages: List[Dict[str, str]], system: Optional[str] = None,
                 max_tokens: int = 512, mock_meta: Optional[Dict] = None,
                 temperature: float = 0.0) -> ModelResponse:
        if self.provider == "mock":
            return self._complete_mock(messages, system, mock_meta or {})
        fn = self._complete_anthropic if self.provider == "anthropic" else self._complete_openai
        return self._with_retries(fn, messages, system, max_tokens, temperature)

    @staticmethod
    def _is_transient(e: Exception) -> bool:
        s = (str(e) + " " + type(e).__name__).lower()
        codes = ("429", "500", "502", "503", "529")
        words = ("rate", "overloaded", "timeout", "timed out", "temporarily",
                 "connection", "unavailable", "internalserver")
        return any(c in s for c in codes) or any(w in s for w in words)

    def _with_retries(self, fn, messages, system, max_tokens, temperature,
                      attempts: int = 6) -> ModelResponse:
        import random
        import time
        last = None
        for i in range(attempts):
            try:
                return fn(messages, system, max_tokens, temperature)
            except Exception as e:  # retry only transient errors; re-raise the rest immediately
                last = e
                if not self._is_transient(e) or i == attempts - 1:
                    raise
                time.sleep(min(60.0, 2.0 ** i) + random.uniform(0, 1.0))
        raise last  # pragma: no cover

    # ---- real providers -------------------------------------------------
    def _complete_anthropic(self, messages, system, max_tokens, temperature) -> ModelResponse:
        kwargs = dict(model=self.model, max_tokens=max_tokens, messages=messages,
                      temperature=temperature)
        if system:
            kwargs["system"] = system
        resp = self._client.messages.create(**kwargs)
        text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
        return ModelResponse(text, resp.usage.input_tokens, resp.usage.output_tokens,
                             "anthropic", self.model)

    @staticmethod
    def _openai_reasoning(model: str) -> bool:
        return model.startswith(("gpt-5", "o1", "o3", "o4"))

    def _complete_openai(self, messages, system, max_tokens, temperature) -> ModelResponse:
        msgs = ([{"role": "system", "content": system}] if system else []) + messages
        if self._openai_reasoning(self.model):
            # gpt-5.x / o-series: require max_completion_tokens, reject temperature override.
            # Headroom for reasoning tokens so a real answer survives the budget.
            resp = self._client.chat.completions.create(
                model=self.model, messages=msgs, max_completion_tokens=max(4000, max_tokens))
        else:
            resp = self._client.chat.completions.create(
                model=self.model, messages=msgs, max_tokens=max_tokens, temperature=temperature)
        text = resp.choices[0].message.content or ""
        u = resp.usage
        return ModelResponse(text, u.prompt_tokens, u.completion_tokens, "openai", self.model)

    # ---- mock provider --------------------------------------------------
    def _complete_mock(self, messages, system, meta) -> ModelResponse:
        """Deterministic degradation model for plumbing tests only.

        Success probability decays log-linearly with target context tokens, with a
        per-probe floor and seeded noise. On success it emits the gold answer (which a
        real model would have had to read from the needle); on failure it emits a wrong
        answer. The REAL scorers then run on this text.
        """
        probe_type = meta.get("probe_type", "A_retrieval")
        gold = meta.get("gold")
        T = float(meta.get("target_tokens", 5000))
        seed = meta.get("seed", 0)
        item = meta.get("item", 0)
        position = meta.get("position", "front")
        needle_mode = meta.get("needle_mode", "present")

        # No-needle control: the answer is not in context, so retrieval must be at chance (~0).
        if needle_mode == "absent" and probe_type == "A_retrieval":
            text = self._mock_answer(probe_type, gold, False)
            in_tok = estimate_tokens(_messages_text(system, messages))
            return ModelResponse(text, in_tok, estimate_tokens(text), "mock", "mock")

        lo, hi = math.log(5000.0), math.log(150000.0)
        frac = (math.log(max(T, 5000.0)) - lo) / (hi - lo)
        base = {"A_retrieval": 0.95, "B_state": 0.90, "C_instruction": 0.92}.get(probe_type, 0.9)
        floor = {"A_retrieval": 0.35, "B_state": 0.25, "C_instruction": 0.45}.get(probe_type, 0.3)
        # Position effect (mock only, ARBITRARY): needle-adjacent ('end', distance~0) rots less
        # than 'front'/'mid'. This exists so the factorial analysis has structure to find.
        pos_relief = {"end": 0.55, "mid": 0.15, "front": 0.0, "na": 0.2}.get(position, 0.0)
        p_success = base - (base - floor) * frac * (1.0 - pos_relief)
        noise = (_stable_unit(probe_type, T, seed, item, position) - 0.5) * 0.10
        p_success = min(0.98, max(0.02, p_success + noise))
        roll = _stable_unit("roll", probe_type, T, seed, item, position, needle_mode)
        success = roll < p_success

        text = self._mock_answer(probe_type, gold, success)
        in_tok = estimate_tokens(_messages_text(system, messages))
        out_tok = estimate_tokens(text)
        return ModelResponse(text, in_tok, out_tok, "mock", "mock")

    @staticmethod
    def _mock_answer(probe_type: str, gold, success: bool) -> str:
        if probe_type == "A_retrieval":
            if success and gold is not None:
                return f"The function returns the sentinel {gold}."
            return "The function returns the sentinel NXWRONG00000."  # fails exact nonce match
        if probe_type == "B_state":
            if success and gold is not None:
                if isinstance(gold, (str, int)):  # hard B2: count gold
                    return f"{gold}"
                lines = [f"- {f}: {c}" for f, c in gold]  # easy B: list of [file, change]
                return "Files edited so far:\n" + "\n".join(lines)
            return "0" if isinstance(gold, (str, int)) else \
                   "Files edited so far:\n- (unable to reconstruct the full edit history)"
        if probe_type == "C_instruction":
            if success:
                return ("I won't modify anything under tests/. I'll change the source "
                        "module instead and leave the test directory untouched.")
            return "Sure — I'll update tests/test_core.py to make that change."
        return "(mock) no answer"
