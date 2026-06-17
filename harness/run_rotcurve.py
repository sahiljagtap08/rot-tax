"""Phase 2 — the rot-curve experiment (v0.2).

Grid: substrate item x context-length T x needle-position x probe x composition x needle-mode
x content-seed. For each cell, construct a hash-pinned controlled context, query the model under
study (temperature=0), score the probe mechanically, log cheap live signals + full provenance,
and append one JSONL record. Streams spend to logs/spend.jsonl and ABORTS on budget. The mock
provider needs no key/money and exists only to validate plumbing.

Usage:
    python -m harness.run_rotcurve --provider mock --quick
    ANTHROPIC_API_KEY=... python -m harness.run_rotcurve --provider anthropic
"""
from __future__ import annotations

import argparse
import json
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from . import config as cfg_mod
from .costs import BudgetExceeded, CostTracker
from .logging_utils import StructuredLogger
from .models import ModelClient
from .context_builder import generate_substrate, assemble_trial, assert_invariants
from .probes import make_probes, gold_and_mockgold
from .scorers import score_A, score_B, score_C
from .signals import extract_signals

REPO_ROOT = Path(__file__).resolve().parent.parent
_WRITE_LOCK = threading.Lock()

try:
    import tiktoken  # noqa
    TOKENIZER = "cl100k_base"
except Exception:
    TOKENIZER = "heuristic-4chars"


def _positions(kind, quick, positions_override):
    if kind == "C":
        return ["na"]
    if positions_override:
        return positions_override
    return (["front", "end"] if quick else ["front", "mid", "end"])


def _needle_modes(kind, quick, primary_only):
    if kind != "A" or primary_only:
        return ["present"]
    return (["present", "absent"] if quick else ["present", "absent", "counterfactual"])


def build_cells(cfg, quick, *, reps=None, items=None, primary_only=False,
                levels=None, positions=None):
    items = items if items is not None else cfg_mod.get(cfg, "experiment.num_substrate_items", 10)
    levels = levels or cfg_mod.get(cfg, "experiment.probe_milestones_tokens")
    comps = ["diverse"] if primary_only else cfg_mod.get(cfg, "experiment.compositions")
    reps = reps if reps is not None else cfg_mod.get(cfg, "experiment.repetitions", 8)
    if quick:
        items, levels, comps, reps = 2, [5000, 50000, 120000], ["diverse"], 2
    seed0 = cfg_mod.get(cfg, "run.seed", 42)
    nf = cfg_mod.get(cfg, "substrate.n_files", 6)
    ng = cfg_mod.get(cfg, "substrate.n_functions_per_file", 5)
    cells = []
    for item in range(items):
        sub = generate_substrate(item, seed0, nf, ng)
        assert_invariants(sub)
        for probe in make_probes(sub):
            for pos in _positions(probe.kind, quick, positions):
                for nm in _needle_modes(probe.kind, quick, primary_only):
                    for comp in comps:
                        for T in levels:
                            for rep in range(reps):
                                cells.append((sub, probe, T, pos, comp, nm, seed0 + rep, item, rep))
    return cells


def estimate_cost(cells, model, pricing):
    """Dry cost estimate (no API). Sizes input tokens from a representative trial per
    (probe_kind, T, needle_mode) cell shape and assumes ~400 output tokens/call."""
    cache, total_in = {}, 0
    for (sub, probe, T, pos, comp, nm, seed, item, rep) in cells:
        key = (probe.kind, T, nm)
        if key not in cache:
            tr = assemble_trial(sub, probe.kind, probe.text, T, position=pos, composition=comp,
                                needle_mode=nm, content_seed=seed)
            cache[key] = tr.est_input_tokens
        total_in += cache[key]
    total_out = 400 * len(cells)
    p = pricing.get(model)
    if not p:
        raise KeyError(f"No pricing for '{model}' in config.yaml:pricing")
    cost = (total_in * p["input"] + total_out * p["output"]) / 1_000_000.0
    return total_in, total_out, cost


def run_one(cell, agent_client, cost, logger, model_version):
    sub, probe, T, pos, comp, nm, seed, item, rep = cell
    sid = f"i{item}-L{T}-{pos}-{nm}-{comp}-s{seed}-{probe.probe_id}"
    gold, mock_gold = gold_and_mockgold(sub, probe, nm)
    trial = assemble_trial(sub, probe.kind, probe.text, T, position=pos, composition=comp,
                           needle_mode=nm, content_seed=seed)
    mm = {"probe_type": probe.probe_id, "gold": mock_gold, "target_tokens": T, "seed": seed,
          "item": item, "position": pos, "needle_mode": nm}
    resp = agent_client.complete(trial.messages, system=trial.system, max_tokens=400,
                                 mock_meta=mm, temperature=0.0)
    cost.record(agent_client.model, resp.input_tokens, resp.output_tokens,
                meta={"session_id": sid})

    if probe.kind == "A":
        passed, detail = score_A(resp.text, gold)
    elif probe.kind == "B":
        passed, detail = score_B(resp.text, gold)
    else:
        passed, detail = score_C(resp.text)

    sig = extract_signals(trial.filler_turns, resp.text, resp.input_tokens)
    return {
        "session_id": sid, "item": item, "rep": rep, "content_seed": seed,
        "probe_id": probe.probe_id, "probe_kind": probe.kind, "target_tokens": T,
        "needle_position": pos, "composition": comp, "needle_mode": nm,
        "input_tokens_actual": resp.input_tokens, "output_tokens": resp.output_tokens,
        "passed": bool(passed), "score_detail": detail, "signals": sig,
        "content_hash": trial.content_hash, "provider": agent_client.provider,
        "model": agent_client.model, "model_version": model_version, "tokenizer": TOKENIZER,
        "answer_preview": (resp.text or "")[:200], "ts": time.time(),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", default=None)
    ap.add_argument("--config", default=None)
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--max-parallel", type=int, default=None)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--model", default=None, help="override agent model (writes a per-model file)")
    ap.add_argument("--reps", type=int, default=None)
    ap.add_argument("--items", type=int, default=None)
    ap.add_argument("--primary-only", action="store_true",
                    help="diverse composition + present needle only (cheap confirmation subset)")
    ap.add_argument("--levels", default=None, help="comma list of token milestones to override")
    ap.add_argument("--positions", default=None, help="comma list, e.g. front,end")
    ap.add_argument("--estimate", action="store_true", help="dry cost estimate, no API calls")
    ap.add_argument("--budget", type=float, default=None, help="per-run USD ceiling override")
    ap.add_argument("--shuffle", action="store_true",
                    help="randomize collection order (recommended for real runs; DESIGN §4)")
    args = ap.parse_args()

    cfg = cfg_mod.load_config(args.config)
    provider = args.provider or cfg_mod.get(cfg, "run.provider", "mock")
    is_mock = provider == "mock"
    agent_model = args.model or cfg_mod.get(cfg, "models.agent_model")
    pricing = cfg_mod.get(cfg, "pricing")
    budget = args.budget if args.budget is not None else cfg_mod.get(cfg, "run.budget_usd_ceiling", 25.0)
    maxp = args.max_parallel or cfg_mod.get(cfg, "run.max_parallel_sessions", 4)

    levels = [int(x) for x in args.levels.split(",")] if args.levels else None
    positions = args.positions.split(",") if args.positions else None
    cells = build_cells(cfg, args.quick, reps=args.reps, items=args.items,
                        primary_only=args.primary_only, levels=levels, positions=positions)
    if args.shuffle:
        random.Random(cfg_mod.get(cfg, "run.seed", 42)).shuffle(cells)
    if args.limit:
        cells = cells[: args.limit]

    if args.estimate:
        price_model = "mock" if is_mock else agent_model
        tin, tout, cost = estimate_cost(cells, price_model, pricing)
        print(f"[estimate] model={price_model} cells={len(cells)}")
        print(f"[estimate] input_tokens~{tin:,} output_tokens~{tout:,}")
        print(f"[estimate] EST COST ~ ${cost:.2f}  (budget ceiling ${budget:.2f})")
        print(f"[estimate] {'OK, fits budget' if cost <= budget else 'OVER BUDGET — reduce grid'}")
        return

    slug = "" if is_mock else "__" + agent_model.replace("/", "-").replace(":", "-").replace(".", "_")
    suffix = ".MOCK" if is_mock else ""
    out_path = REPO_ROOT / "results" / f"rot_raw{suffix}{slug}.jsonl"
    spend_path = REPO_ROOT / "logs" / f"spend{suffix}{slug}.jsonl"
    event_path = REPO_ROOT / "logs" / f"events{suffix}{slug}.jsonl"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("")

    cost = CostTracker(pricing, budget, spend_path)
    logger = StructuredLogger(event_path)
    agent_client = ModelClient("mock", "mock") if is_mock else ModelClient(provider, agent_model)
    model_version = "mock" if is_mock else agent_model

    print(f"[rot-curve] provider={provider} model={agent_client.model} tokenizer={TOKENIZER} "
          f"cells={len(cells)} budget=${budget:.2f} parallel={maxp}")
    if is_mock:
        print("[rot-curve] *** MOCK RUN — output is NOT a finding, only a plumbing test. ***")

    n_done, aborted = 0, False
    with ThreadPoolExecutor(max_workers=maxp) as ex:
        futs = {ex.submit(run_one, c, agent_client, cost, logger, model_version): c for c in cells}
        for fut in as_completed(futs):
            try:
                rec = fut.result()
            except BudgetExceeded as e:
                print(f"[rot-curve] BUDGET ABORT: {e}"); aborted = True; break
            except Exception as e:
                print(f"[rot-curve] ERROR on a cell: {type(e).__name__}: {e}"); aborted = True; break
            with _WRITE_LOCK:
                with out_path.open("a") as f:
                    f.write(json.dumps(rec) + "\n")
            n_done += 1
            if n_done % 50 == 0:
                print(f"[rot-curve] {n_done}/{len(cells)} done, spend=${cost.total_usd:.4f}")

    print("\n===== CHECKPOINT =====")
    print(f"completed cells : {n_done}/{len(cells)}{' (ABORTED)' if aborted else ''}")
    print(f"total spend     : ${cost.total_usd:.4f} over {cost.num_calls} API calls")
    print(f"raw output      : {out_path}")
    print(f"next            : python -m harness.analyze --input {out_path} --signals")
    if is_mock:
        print("REMINDER        : MOCK data. Do not interpret as a result.")


if __name__ == "__main__":
    main()
