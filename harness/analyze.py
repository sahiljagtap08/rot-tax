"""Analysis + figures for the rot-curve experiment (v0.2).

Key analyses:
  - The identification test: accuracy vs T at needle_position='end' (needle adjacent to probe,
    distance ~0). A drop here is volume-driven rot, not lost-in-the-middle. We also show the full
    position x T surface (front/mid/end).
  - Controls: needle_mode='absent' must sit at chance (~0 for nonce retrieval) and NOT rise with T.
  - Signal validation (C1): PARTIAL Spearman of each signal vs failure, controlling for log(T).
    Raw correlation is confounded because both rise with T; the partial association is the test
    that a signal carries information BEYOND length.

Usage:
    python -m harness.analyze --input results/rot_raw.jsonl --signals
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent


def load(path: Path) -> pd.DataFrame:
    rows = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
    df = pd.DataFrame(rows)
    if df.empty:
        raise SystemExit(f"No records in {path}. Run the experiment first.")
    sig = pd.json_normalize(df["signals"]).add_prefix("sig.")
    return pd.concat([df.drop(columns=["signals"]), sig], axis=1)


def bootstrap_ci(vals, n=10000, seed=42):
    vals = np.asarray(vals, dtype=float)
    if len(vals) == 0:
        return (np.nan, np.nan, np.nan)
    rng = np.random.default_rng(seed)
    means = vals[rng.integers(0, len(vals), size=(n, len(vals)))].mean(axis=1)
    return float(vals.mean()), float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def acc_by(df, keys):
    out = []
    for vals, g in df.groupby(keys):
        m, lo, hi = bootstrap_ci(g["passed"].astype(float).to_numpy())
        row = dict(zip(keys if isinstance(keys, list) else [keys],
                       vals if isinstance(vals, tuple) else (vals,)))
        row.update({"n": len(g), "acc": m, "ci_lo": lo, "ci_hi": hi})
        out.append(row)
    return pd.DataFrame(out)


def plot_position_surface(df_present, out_png, is_mock):
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    tbl = acc_by(df_present, ["probe_id", "needle_position", "target_tokens"]).sort_values(
        ["probe_id", "needle_position", "target_tokens"])
    probes = sorted(df_present["probe_id"].unique())
    fig, axes = plt.subplots(1, len(probes), figsize=(5 * len(probes), 4.5), sharey=True)
    if len(probes) == 1:
        axes = [axes]
    for ax, probe in zip(axes, probes):
        s = tbl[tbl["probe_id"] == probe]
        for pos in sorted(s["needle_position"].unique()):
            ss = s[s["needle_position"] == pos].sort_values("target_tokens")
            yerr = [ss["acc"] - ss["ci_lo"], ss["ci_hi"] - ss["acc"]]
            ax.errorbar(ss["target_tokens"], ss["acc"], yerr=yerr, marker="o", capsize=2,
                        label=f"pos={pos}")
        ax.set_xscale("log"); ax.set_ylim(0, 1.02); ax.grid(True, alpha=0.3)
        ax.set_title(probe); ax.set_xlabel("accumulated tokens"); ax.legend(fontsize=8)
    axes[0].set_ylabel("probe accuracy")
    sup = "Position x volume factorial (end = needle adjacent to probe -> isolates rot)"
    if is_mock:
        sup = "[MOCK — NOT A RESULT] " + sup
    fig.suptitle(sup); fig.tight_layout()
    fig.savefig(out_png, dpi=150)
    print(f"[analyze] wrote {out_png}")
    return tbl


def identification_readout(df_present):
    print("\n----- IDENTIFICATION TEST (needle_position='end', distance~0) -----")
    end = df_present[df_present["needle_position"] == "end"]
    if end.empty:
        print("  (no position='end' rows; cannot run the decisive test)")
        return
    tbl = acc_by(end, ["probe_id", "target_tokens"]).sort_values(["probe_id", "target_tokens"])
    for probe in sorted(tbl["probe_id"].unique()):
        s = tbl[tbl["probe_id"] == probe]
        peak, last = s.loc[s["acc"].idxmax()], s.iloc[-1]
        verdict = ("VOLUME-DRIVEN ROT" if peak["acc"] - last["acc"] > 0.10
                   else "no volume effect at fixed distance")
        print(f"  {probe:14s} acc {peak['acc']:.3f}@{int(peak['target_tokens'])} -> "
              f"{last['acc']:.3f}@{int(last['target_tokens'])} drop={peak['acc']-last['acc']:+.3f}"
              f"  => {verdict}")


def controls_readout(df):
    print("\n----- CONTROLS -----")
    absent = df[(df["needle_mode"] == "absent")]
    if not absent.empty:
        t = acc_by(absent, ["target_tokens"]).sort_values("target_tokens")
        rng = t["acc"].max() - t["acc"].min()
        print("  no-needle (must be ~chance and flat): "
              + ", ".join(f"{int(r.target_tokens)//1000}k={r.acc:.2f}" for r in t.itertuples())
              + f"  | range={rng:.3f} {'OK' if t['acc'].max()<0.1 else 'WARN: above chance'}")
    cf = df[(df["needle_mode"] == "counterfactual")]
    if not cf.empty:
        m, lo, hi = bootstrap_ci(cf["passed"].astype(float).to_numpy())
        print(f"  counterfactual-needle (in-context use): acc={m:.3f} [{lo:.3f},{hi:.3f}]")


def _rankresid(x, z):
    rx, rz = pd.Series(x).rank().to_numpy(), pd.Series(z).rank().to_numpy()
    A = np.vstack([rz, np.ones_like(rz)]).T
    beta, *_ = np.linalg.lstsq(A, rx, rcond=None)
    return rx - A @ beta


def signal_validation(df):
    from scipy import stats
    d = df[df["needle_mode"] == "present"].copy()
    y = (~d["passed"].astype(bool)).astype(float).to_numpy()   # failure
    z = np.log(d["target_tokens"].astype(float).to_numpy())    # control variable log(T)
    sig_cols = [c for c in d.columns if c.startswith("sig.")]
    rows = []
    ry = _rankresid(y, z)
    for c in sig_cols:
        x = d[c].astype(float).to_numpy()
        if np.nanstd(x) == 0:
            rows.append({"signal": c, "raw_rho": np.nan, "partial_rho": np.nan, "p": np.nan})
            continue
        raw, _ = stats.spearmanr(x, y)
        rx = _rankresid(x, z)
        pr, pp = stats.pearsonr(rx, ry)
        rows.append({"signal": c, "raw_rho": raw, "partial_rho": pr, "p": pp})
    res = pd.DataFrame(rows)
    valid = res.dropna(subset=["p"]).sort_values("p").reset_index(drop=True)
    m = len(valid)
    valid["bh_thresh"] = [(i + 1) / m * 0.05 for i in range(m)]
    valid["passes_bh"] = valid["p"] <= valid["bh_thresh"]
    print("\n----- SIGNAL VALIDATION (C1: partial assoc controlling for log T) -----")
    print("  raw_rho is CONFOUNDED by T; partial_rho is the real test (info BEYOND length).")
    for _, r in valid.iterrows():
        star = "*" if (abs(r["partial_rho"]) >= 0.1 and r["passes_bh"]) else " "
        print(f"  {star} {r['signal']:28s} raw={r['raw_rho']:+.3f}  partial={r['partial_rho']:+.3f}"
              f"  p={r['p']:.1e}")
    print("  (* = nonzero partial association surviving BH. NOTE: the registered GO test is a")
    print("   held-out delta-AUC over a log(T)-only baseline; this partial-rho is the screen.)")
    return valid


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--signals", action="store_true")
    args = ap.parse_args()
    path = Path(args.input)
    is_mock = ".MOCK." in path.name
    if is_mock:
        print("=" * 64)
        print("  MOCK DATA — plumbing test, NOT a research finding.")
        print("=" * 64)
    df = load(path)
    df_present = df[df["needle_mode"] == "present"]
    out_png = REPO_ROOT / "results" / ("rot_curve.MOCK.png" if is_mock else "rot_curve.png")
    plot_position_surface(df_present, out_png, is_mock)
    identification_readout(df_present)
    controls_readout(df)
    if args.signals:
        signal_validation(df)
    print()


if __name__ == "__main__":
    main()
