# Deviation & Change Log

Append-only record of changes to the frozen design, for research-integrity provenance.

## v0.1 → v0.2 (pre-data) — driven by blind adversarial red-team (`docs/REDTEAM.md`)

Three independent reviewers (causal-confound, statistics-power, novelty-collision/reproducibility)
reviewed v0.1 and converged on "reject-but-resubmittable." All must-fix items were folded in
**before any data collection**, which is the point of pre-registering. Summary of changes:

1. **Headline repositioned.** "Rot exists" demoted to a manipulation check (Chroma 2025 owns it).
   Primary contributions are now C1 (live predictability *beyond* length) and C2 (intervention
   *timing* isolated from mechanism). Prevents an incrementalism desk-reject.
2. **Identification factorial added.** needle-position {front, mid, end} × volume, breaking the
   volume/distance/position collinearity that *lost-in-the-middle* (Liu 2024) would otherwise
   explain. The `end` arm (needle adjacent to probe) is the decisive rot test.
3. **Difficulty invariance enforced.** Filler split into neutral_volume(T) (scales) and a
   structured_load of FIXED count (B distractors, C temptations), asserted in code
   (`assert_invariants`). Removes the SlopCodeBench-style difficulty drift for Probes B/C.
4. **Probe A made mechanical.** Unique nonce + exact-match scoring replaces the LLM judge
   (which would rot too). Synthetic substrate mandatory with per-seed random nonces → no
   parametric-recall shortcut. Added no-needle and counterfactual-needle controls.
5. **Signal validation de-confounded.** Partial association controlling for `log(T)` + a
   held-out Δ-AUC test over a `log(T)`-only baseline replaces raw |ρ|≥0.5 (which any T-correlated
   signal passes trivially). Full BH family enumerated; cluster-robust unit of analysis.
6. **Statistics re-specified & powered.** Crossed random effects with a random slope on `log(T)`
   and a `log(T):composition` interaction; `harness/power_sim.py` sizes R (R=8 rejected as
   underpowered → R≈32 placeholder). GO/WEAK/NULL defined numerically via CI bounds + TOST.
7. **Intervention gains a 5th arm** (fork-at-random-time) so timing (peak vs random) is separable
   from mechanism (random vs blind-restart). Powered; within-session paired forking to cut variance.
8. **Metric fixed.** Primary rot-tax is now dimensionless (excess-context-to-fixed-quality /
   accuracy-token deficit area); USD is secondary with a pinned dated price table + ±50% band, and
   only as a governed-vs-naive counterfactual.
9. **Reproducibility hardened.** Hash-pinned per-cell context artifacts, named tokenizer, dated
   model IDs, per-row version/timestamp logging, randomized collection order (`--shuffle`),
   content-seed vs sampling-seed separation, drift-anchor plan.

Status after v0.2: harness implements items 1–6 and 8–9 for the rot-curve phase; item 7
(intervention) is designed and frozen but not yet built. No real data collected yet.
