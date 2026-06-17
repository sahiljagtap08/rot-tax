"""Pre-registration power simulation (DESIGN §7).

Fixes the statistics blocker: 'R=8 is underpowered, no power analysis exists.' This sizes R per
cell for the two registered confirmatory endpoints under a clustered binary design.

Simplified, defensible proxy: the primary degradation contrast (peak vs floor accuracy) tested
as a two-proportion comparison with a clustering design-effect inflation deff = 1 + (m-1)*ICC.
The full registered method is a clustered GLMM / parametric bootstrap on the slope; this proxy is
a lower bound on the achievable power and is enough to reject R=8 and pick a sane R.

Run:  python -m harness.power_sim
"""
from __future__ import annotations

import math
from scipy import stats


def two_prop_power(p1, p2, n_per_arm, deff, alpha=0.05):
    """Power of a two-sided two-proportion z-test with variance inflated by the design effect."""
    n_eff = n_per_arm / deff
    if n_eff < 2:
        return 0.0
    pbar = (p1 + p2) / 2
    se0 = math.sqrt(2 * pbar * (1 - pbar) / n_eff)
    se1 = math.sqrt(p1 * (1 - p1) / n_eff + p2 * (1 - p2) / n_eff)
    if se1 == 0:
        return 1.0
    zcrit = stats.norm.ppf(1 - alpha / 2)
    z = (abs(p1 - p2) - zcrit * se0) / se1
    return float(stats.norm.cdf(z))


def main():
    # Effects to size for (the contrast is acc at peak vs acc at the largest T).
    scenarios = [
        ("strong rot  (0.90 -> 0.50)", 0.90, 0.50),
        ("moderate rot (0.85 -> 0.65)", 0.85, 0.65),
        ("subtle rot  (0.80 -> 0.70)", 0.80, 0.70),
    ]
    Rs = [8, 16, 24, 32, 40, 60]
    m = 5            # observations per cluster (T-levels per content-seed)
    iccs = [0.1, 0.3]
    print("Power for the primary degradation contrast (peak vs largest-T), alpha=0.05")
    print("clusters m=5 obs/seed; deff = 1+(m-1)*ICC\n")
    for name, p1, p2 in scenarios:
        print(f"== {name} ==")
        for icc in iccs:
            deff = 1 + (m - 1) * icc
            row = "  ".join(f"R={R:>2}:{two_prop_power(p1, p2, R, deff):.2f}" for R in Rs)
            print(f"  ICC={icc} (deff={deff:.1f}): {row}")
        print()
    print("Reading: pick the smallest R giving >=0.80 in your assumed scenario/ICC AFTER")
    print("multiplicity. The C1 (held-out delta-AUC) and C2 (timing contrast) endpoints are")
    print("sized separately; the timing contrast typically needs the LARGEST R (paired forking")
    print("is used to cut its variance). R=8 is rejected: it is <0.80 except for strong rot.")


if __name__ == "__main__":
    main()
