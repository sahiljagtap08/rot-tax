"""Cheap, label-free live signals — candidate inputs to a real-time rot detector.

In the controlled lab, session-derived signals are computed from the constructed filler
(which we control); response-side signals come from the model output. In the live-agent
study (future) these are read from a real session. Either way they carry NO ground-truth
label, which is the point: §5 validates which ones predict the true probe drop.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from typing import Dict, List


def _ngrams(tokens: List[str], n: int) -> List[tuple]:
    return [tuple(tokens[i:i + n]) for i in range(len(tokens) - n + 1)]


def _self_repetition(text: str, n: int = 3) -> float:
    toks = re.findall(r"\w+", (text or "").lower())
    grams = _ngrams(toks, n)
    if not grams:
        return 0.0
    counts = Counter(grams)
    repeated = sum(c for c in counts.values() if c > 1)
    return repeated / len(grams)


def _entropy(text: str) -> float:
    toks = re.findall(r"\w+", (text or "").lower())
    if not toks:
        return 0.0
    counts = Counter(toks)
    total = len(toks)
    return -sum((c / total) * math.log2(c / total) for c in counts.values())


def extract_signals(filler_turns: List[str], response_text: str,
                    est_input_tokens: int) -> Dict[str, float]:
    n = max(1, len(filler_turns))
    # tool-call repetition: fraction of filler turns that are near-duplicates
    norm = [re.sub(r"\d+", "#", t)[:120] for t in filler_turns]
    dup = len(norm) - len(set(norm))
    tool_call_repetition_rate = dup / n

    reread = sum(1 for t in filler_turns if "re-read" in t.lower() or "double-check" in t.lower())
    file_reads = sum(1 for t in filler_turns if "i read" in t.lower() or "i re-read" in t.lower())
    distinct_edits = len(set(re.findall(r"`(src/[^`]+)`", " ".join(filler_turns))))
    diff_progress_per_token = distinct_edits / max(1, est_input_tokens) * 1000.0  # per 1k tok
    edit_revert_count = sum(1 for t in filler_turns
                            if "revert" in t.lower() or "undo" in t.lower())

    return {
        "tool_call_repetition_rate": round(tool_call_repetition_rate, 4),
        "diff_progress_per_token": round(diff_progress_per_token, 5),
        "file_reread_count": float(reread + max(0, file_reads - 1)),
        "edit_revert_count": float(edit_revert_count),
        "output_entropy": round(_entropy(response_text), 4),
        "self_repetition": round(_self_repetition(response_text), 4),
    }
