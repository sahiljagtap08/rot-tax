# The Rot Tax — Pre-Registered Pilot Design (v0.2)

**Author:** Sahil Jagtap (George Mason University) · sjagtap2@gmu.edu · jagtap.tech
**Status:** Frozen pre-registration. Revised after a blind adversarial red-team (see `docs/REDTEAM.md`)
that reviewed v0.1 and returned "reject-but-resubmittable." Every must-fix is folded in below.
Deviations after this point are logged in `docs/DEVIATIONS.md`.

> **Why v0.2 exists:** v0.1's headline ("rot exists") is subsumed by Chroma's *Context Rot* (2025),
> and its geometry confounded volume with position/distance (the *lost-in-the-middle* alternative).
> v0.2 repositions onto two claims nobody has established and fixes identification, measurement,
> and power **before** any money is spent. This is the point of pre-registering.

---

## 0. Contributions (what is actually new)

- **C0 (manipulation check, NOT a contribution):** agentic-coding context rot exists — accuracy
  on fixed-difficulty probes falls as session context grows. Chroma established this for generic
  haystacks; we only confirm it transfers to agentic filler. It *gates nothing on its own.*
- **C1 (primary):** **latent rot is predictable live from cheap signals *beyond what context
  length alone predicts*.** A signal must add incremental skill over a `log(T)`-only baseline on a
  held-out split. This is the "thermostat" claim and is the paper's spine.
- **C2 (primary):** **intervention *timing* matters, separable from intervention *mechanism*.**
  Forking at the detected peak beats forking at a random point (timing), which we isolate from
  "preserving state beats summarizing" (mechanism) via a dedicated arm.
- **C3 (secondary):** **the three probe types have different half-lives** (retrieval vs
  state-tracking vs instruction-adherence rot at different rates). We refuse to report only the
  aggregate — directly citing *Search Discipline* (2606.11522): a scalar can hide an inversion.

---

## 1. The identification problem and our factorial (fixes red-team BLOCKER #1)

In v0.1, growing filler between an early needle and a final probe made **volume, needle→probe
distance, and relative needle position perfectly collinear.** *Lost-in-the-middle* (Liu et al.,
TACL 2024) predicts a curve from position alone, with zero appeal to "rot." So v0.1 could not
attribute any drop to context accumulation.

**Fix — needle-position × volume factorial.** `needle_position ∈ {front, mid, end}` crossed with
`T`:
- **front:** `[needle][filler...][probe]` — needle→probe distance grows with T (≈ v0.1).
- **mid:** `[filler/2][needle][filler/2][probe]` — recovers the U-shape.
- **end:** `[filler...][needle][probe]` — **needle adjacent to probe, distance ≈ 0 at every T.**

**The decisive test:** if accuracy still falls with `T` at `position = end` (distance held ≈ 0),
the effect is **volume-driven rot**, not position. If moving the needle adjacent to the probe
restores accuracy, the effect is pure distance/position and we report it as such. The full
position × T surface is reported; the rot claim (C0) is licensed only by the `end` column.

---

## 2. Difficulty invariance, operationalized and enforced (fixes BLOCKER #2)

"Difficulty held constant" is only true if nothing about the probe's intrinsic hardness changes
with T. v0.1 broke this for B and C (more filler ⇒ more edit-like distractors / more temptation).

**Fix — separate two filler streams:**
- **neutral_volume(T):** semantically inert tokens that scale with T (the only thing that grows).
- **structured_load:** a **fixed count, independent of T**, of (i) edit-like distractor events
  (for Probe B) and (ii) `tests/`-edit temptations (for Probe C).

The harness asserts these counts are constant across T (`assert_invariants()`), and a
**standalone difficulty audit** confirms each probe answered *in isolation* (needle + probe only)
is flat across T. Any residual difficulty drift must surface as a composition main effect, not a
length effect.

---

## 3. Measurement validity (fixes BLOCKER #3 and the scorer blockers)

- **Synthetic substrate is mandatory.** Function names and return values are **random nonces per
  content-seed**, so no model can answer from parametric/memorized knowledge.
- **Probe A is mechanical.** The needle states the target function returns a unique 12-char
  **nonce**; the probe asks for it; scoring is **exact string match** (no LLM judge — kills the
  "judge rots too" confound). Probes B and C were already mechanical.
- **Controls (each run per composition × T, not aggregate):**
  - **needle-free-but-probed:** remove the needle, keep filler. Must score **at chance** *and not
    rise with T.* (If it rises, the model is exploiting filler — reject the batch.)
  - **counterfactual/corrupted-needle:** an authoritative needle gives nonce `N2` after a stale
    earlier mention of `N1`; gold = `N2`. A model using in-context info reports `N2`; one using
    recency/other heuristics reports `N1`. (Primary on the synthetic substrate; the real-repo
    robustness substrate uses the recall-vs-context variant.)
  - **per-probe chance baseline** is defined empirically (Probe C is near-ceiling by default, not
    0.5) and controls use a **TOST non-inferiority** test against it, not "not significant."

---

## 4. Conditions (the frozen grid)

| Factor | Levels |
|---|---|
| context length `T` | {5k, 20k, 50k, 100k, 150k} tokens (named tokenizer; verified at collection) |
| needle position | {front, mid, end} |
| probe type | {A_retrieval, B_state, C_instruction} |
| composition | {diverse (primary), redundant, distracting} |
| needle mode | {present, absent (control), counterfactual (control)} |
| content-seed | R seeds (R set by §7 power sim; v0.1's R=8 is a placeholder, **not** final) |
| substrate | ≥3 synthetic repos for the pilot; real-repo substrate for robustness |
| agent model | ≥2 pinned dated model IDs from ≥2 providers |

Every cell's **full context string is serialized and content-addressed (hash-pinned)** and
released. `T` is recorded in **characters and in tokens under a named tokenizer**, verified by the
provider count-tokens endpoint at collection. **content-seed** (deterministic assembly) is separate
from **sampling-seed** (model stochasticity: temperature=0 + all determinism knobs pinned; if the
endpoint is non-deterministic we replay each frozen context K times and report within-cell
variance). Collection **order is randomized/interleaved**; a **drift-anchor cell** is re-run
periodically and the run aborts if anchor accuracy moves beyond tolerance. Per row we log model
version, tokenizer version, and timestamp.

---

## 5. Live-signal validation — the C1 test (fixes the circularity blockers)

Signals: `tool_call_repetition_rate`, `diff_progress_per_token`, `file_reread_count`,
`edit_revert_count`, `output_entropy`, `self_repetition` (each defined in **tokenizer-independent**
terms and pinned).

Both signals and probe-drop rise with `T`, so raw correlation is confounded by `T`. Therefore:
- **Partial association controlling for `log(T)`:** fit `fail ~ log(T)` (baseline) vs
  `fail ~ log(T) + signal`; a signal is eligible only if it adds skill via likelihood-ratio test
  **and** improves **out-of-sample AUC** on a **held-out composition/model split** over the
  `log(T)`-only baseline by a pre-set margin (Δ-AUC ≥ 0.03, justified below).
- **Unit of analysis:** per-seed/cluster-robust, never pooled raw runs (no pseudo-replication).
- **Multiplicity:** the family is *all* signal × probe × composition (× model) tests, BH-FDR over
  the full enumerated family (secondary/exploratory tier; see §7 hierarchy).
- **GO for C1:** ≥1 signal beats the `log(T)`-only baseline on held-out Δ-AUC with CI excluding the
  margin. If nothing beats `log(T)`, C1 is a null and we say so — "length is all you need."

---

## 6. Operational definitions (frozen)

- **Probe accuracy** `acc(T, pos, probe, comp)`: mean pass-rate per cell.
- **Half-life** `T½` (re-used from METR/DDI, cited, not re-coined): the `T` at which `acc` reaches
  the midpoint between its peak and floor, per probe type (C3).
- **Rot tax — primary, dimensionless:** **excess context-to-fixed-quality** = extra accumulated
  tokens a naive run consumes to hold a target quality that a governed run holds, OR the
  accuracy-deficit area (governed − naive) in **accuracy-token units**. Provider-agnostic,
  reproducible, directly comparable to METR-style horizons.
- **Rot tax — secondary, USD:** the dimensionless quantity × a **pinned, dated price table**,
  reported with a **±50% price sensitivity band**. Never the headline. Charged only against the
  governed-vs-naive counterfactual (no "a non-rotting run still pays the tax" incoherence).

---

## 7. Statistics, power, decision rule (fixes the statistics blockers)

**Primary model (re-specified, crossed random effects + random slope + interaction):**
```
fail ~ log(T) + needle_position + probe_type + composition + log(T):composition
       + (log(T) | content_seed) + (1 | substrate_item)
```
Random slope on `log(T)` lets degradation rate vary (the heterogeneity the hypothesis is about).
Fallback if it won't converge: cluster-bootstrapped GEE or a weakly-informative Bayesian GLMM
(pre-committed, not chosen post-hoc).

**Power:** a pre-registration **power simulation** (`harness/power_sim.py`) over the clustered
binary design fixes **R** for ≥80% power at the stated minimum effect of interest (MEI) after
multiplicity — for both the C1 Δ-AUC test and the **C2 timing contrast**. v0.1's R=8 (CI
half-width ≈ 0.35) is explicitly **insufficient** and is replaced by the sim's output.

**Multiplicity hierarchy (enumerated):**
- **Confirmatory (FWER, Holm/fixed-sequence, α=0.05):** the C1 incremental-skill test and the C2
  timing contrast.
- **Exploratory (BH-FDR):** per-signal × probe × composition associations, composition arms,
  per-probe half-lives.

**GO / WEAK / NULL — numerical, via CI bounds + TOST (no significance stars):**
- **GO:** lower 95% CI bound of the C1 held-out Δ-AUC > margin **AND** lower bound of the C2 timing
  contrast > MEI₂ **AND** C0 manipulation check positive at `position=end`.
- **NULL:** upper CI bound below a pre-set negligible region (TOST equivalence) → publish the null.
- **WEAK:** CI spans the MEI → *inconclusive → collect more data*, not a publishable middle claim.

---

## 8. Intervention study (Phase 2; frozen here to prevent HARKing) — the C2 test

Five matched arms (was four; **fork-at-random added** to separate timing from mechanism):
1. naive long session
2. blind periodic compaction
3. blind restart + short summary
4. **fork-at-random-time** (same snapshot/fork mechanism as #5, cut at a non-detected `T`)
5. **fork-at-peak** (snapshot at the detected peak, same mechanism as #4)

- **Timing effect (primary C2):** #5 vs #4 (mechanism held constant). *This* proves timing adds
  value, not just "restarting helps."
- **Mechanism effect:** #4 vs #3 (state-fidelity vs summary).
- Powered per §7; a **within-session paired fork** (same seed forked into #4 and #5) is used to
  cut variance. Endpoints: task success, dimensionless rot tax recovered (USD secondary). A
  negative result is a publishable finding.

---

## 9. Threats to validity (live)
Construction artifacts → per-composition×T no-needle TOST + filler↔gold similarity cap.
Position vs length → the factorial (§1). Parametric recall → synthetic nonces + counterfactual
needle. Judge rot → mechanical Probe A. Tokenizer/provider drift → pinned IDs, anchor cell,
per-row versioning. Single-substrate overfit → ≥3 substrates, ≥2 models. Pseudo-replication →
cluster-robust units. Metric arbitrariness → dimensionless primary + dated price band secondary.

## 10. What we will NOT claim from the pilot
No claim about live Claude Code sessions until the opt-in, metadata-only field study runs;
the controlled lab establishes causality, the field study establishes breadth, reported
separately and never blended. "Rot exists" is a manipulation check, never the headline.
